import csv
import json
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from PIL import Image, UnidentifiedImageError

from .forms import AssignmentForm, DeliveryForm, VehicleForm
from .models import Delivery, DeliveryEvent, DriverLocation, LocationPing, Notification, Vehicle

User = get_user_model()


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.can_view_operations:
            return view_func(request, *args, **kwargs)
        messages.error(request, "This area is restricted to operations staff.")
        return redirect("deliveries:driver_dashboard")
    return wrapper



def dispatcher_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.can_manage_deliveries:
            return view_func(request, *args, **kwargs)
        messages.error(request, "You do not have permission to perform dispatch changes.")
        return redirect("deliveries:dashboard")
    return wrapper


def driver_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_driver:
            return view_func(request, *args, **kwargs)
        messages.error(request, "This area is for delivery drivers only.")
        return redirect("deliveries:dashboard")
    return wrapper


def log_event(delivery, actor, event_type, description, latitude=None, longitude=None):
    return DeliveryEvent.objects.create(
        delivery=delivery, actor=actor, event_type=event_type,
        description=description, latitude=latitude, longitude=longitude,
    )


def notify(user, title, message, url=""):
    if user:
        Notification.objects.create(user=user, title=title, message=message, url=url)


@staff_required
def dashboard(request):
    qs = Delivery.objects.all()
    today = timezone.localdate()
    active = qs.exclude(status__in=["delivered", "failed", "returned", "cancelled"])
    recent = qs.select_related("assigned_driver").order_by("-created_at")[:8]
    by_status = list(qs.values("status").annotate(total=Count("id")).order_by("status"))
    drivers_online = DriverLocation.objects.filter(is_sharing=True, updated_at__gte=timezone.now() - timedelta(minutes=5)).count()
    context = {
        "total": qs.count(),
        "pending": qs.filter(status="pending").count(),
        "active": active.count(),
        "in_transit": qs.filter(status="in_transit").count(),
        "delivered_today": qs.filter(status="delivered", delivered_at__date=today).count(),
        "failed": qs.filter(status="failed").count(),
        "recent_deliveries": recent,
        "by_status_json": json.dumps(by_status),
        "drivers_online": drivers_online,
    }
    return render(request, "deliveries/dashboard.html", context)


@staff_required
def delivery_list(request):
    qs = Delivery.objects.select_related("assigned_driver", "assigned_vehicle")
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    if search:
        search_query = (
            Q(customer_name__icontains=search) | Q(customer_phone__icontains=search) |
            Q(dropoff_address__icontains=search) | Q(pickup_address__icontains=search) |
            Q(tracking_code__icontains=search)
        )
        if search.isdigit():
            search_query |= Q(pk=int(search))
        qs = qs.filter(search_query)
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    page_obj = Paginator(qs.order_by("-created_at"), 15).get_page(request.GET.get("page"))
    return render(request, "deliveries/delivery_list.html", {
        "page_obj": page_obj, "deliveries": page_obj.object_list,
        "search": search, "selected_status": status, "selected_priority": priority,
        "status_choices": Delivery.STATUS_CHOICES, "priority_choices": Delivery.PRIORITY_CHOICES,
    })


@dispatcher_required
def create_delivery(request):
    if request.method == "POST":
        form = DeliveryForm(request.POST)
        if form.is_valid():
            delivery = form.save(commit=False)
            delivery.created_by = request.user
            delivery.save()
            log_event(delivery, request.user, "created", "Delivery order created")
            messages.success(request, f"Delivery DMTS-{delivery.pk} created. Tracking code: {delivery.short_tracking_code}")
            return redirect("deliveries:delivery_detail", pk=delivery.pk)
    else:
        form = DeliveryForm()
    return render(request, "deliveries/delivery_form.html", {"form": form, "creating": True})


@dispatcher_required
def edit_delivery(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    if delivery.status in {"delivered", "returned", "cancelled"}:
        messages.warning(request, "Completed or closed deliveries are locked from editing.")
        return redirect("deliveries:delivery_detail", pk=delivery.pk)
    if request.method == "POST":
        form = DeliveryForm(request.POST, instance=delivery)
        if form.is_valid():
            form.save()
            log_event(delivery, request.user, "updated", "Delivery details updated")
            messages.success(request, "Delivery details saved.")
            return redirect("deliveries:delivery_detail", pk=delivery.pk)
    else:
        form = DeliveryForm(instance=delivery)
    return render(request, "deliveries/delivery_form.html", {"form": form, "creating": False, "delivery": delivery})


@staff_required
def delivery_detail(request, pk):
    delivery = get_object_or_404(Delivery.objects.select_related("assigned_driver", "assigned_vehicle", "created_by"), pk=pk)
    return render(request, "deliveries/delivery_detail.html", {"delivery": delivery, "events": delivery.events.select_related("actor")[:30]})


@dispatcher_required
def assign_delivery(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    if request.method == "POST":
        form = AssignmentForm(request.POST, delivery_id=delivery.pk)
        if form.is_valid():
            old_driver = delivery.assigned_driver
            driver = form.cleaned_data["assigned_driver"]
            vehicle = form.cleaned_data["assigned_vehicle"]
            delivery.assigned_driver = driver
            delivery.assigned_vehicle = vehicle
            if driver and delivery.status == "pending":
                delivery.status = "assigned"
            elif not driver and delivery.status == "assigned":
                delivery.status = "pending"
            delivery.save()
            if driver:
                display = driver.get_full_name() or driver.username
                log_event(delivery, request.user, "assigned", f"Assigned to {display}")
                notify(driver, "New delivery assigned", f"DMTS-{delivery.pk} has been assigned to you.", f"/driver/#delivery-{delivery.pk}")
                messages.success(request, f"DMTS-{delivery.pk} assigned to {display}.")
            else:
                log_event(delivery, request.user, "unassigned", "Driver assignment removed")
                messages.success(request, f"DMTS-{delivery.pk} is now unassigned.")
            if vehicle:
                log_event(delivery, request.user, "vehicle_assigned", f"Vehicle {vehicle.registration_number} allocated")
            if old_driver and old_driver != driver:
                notify(old_driver, "Delivery reassigned", f"DMTS-{delivery.pk} has been moved to another driver.")
            return redirect("deliveries:delivery_detail", pk=delivery.pk)
    else:
        form = AssignmentForm(initial={"assigned_driver": delivery.assigned_driver, "assigned_vehicle": delivery.assigned_vehicle}, delivery_id=delivery.pk)
    return render(request, "deliveries/assign_delivery.html", {"delivery": delivery, "form": form})


@staff_required
def live_map(request):
    return render(request, "deliveries/live_map.html")


@dispatcher_required
def fleet_list(request):
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save()
        messages.success(request, f"Vehicle {vehicle.registration_number} saved to fleet.")
        return redirect("deliveries:fleet_list")
    return render(request, "deliveries/fleet.html", {"vehicles": Vehicle.objects.all(), "form": form})


@dispatcher_required
@require_POST
def toggle_vehicle(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    vehicle.is_active = not vehicle.is_active
    vehicle.save(update_fields=["is_active"])
    messages.success(request, f"{vehicle.registration_number} is now {'active' if vehicle.is_active else 'inactive'}.")
    return redirect("deliveries:fleet_list")


@driver_required
def driver_dashboard(request):
    deliveries = Delivery.objects.filter(assigned_driver=request.user).select_related("assigned_vehicle").order_by("scheduled_for", "-created_at")
    active = deliveries.exclude(status__in=["delivered", "failed", "returned", "cancelled"])
    location, _ = DriverLocation.objects.get_or_create(driver=request.user)
    today = timezone.localdate()
    return render(request, "deliveries/driver_dashboard.html", {
        "deliveries": deliveries, "active_deliveries": active,
        "completed_today": deliveries.filter(status="delivered", delivered_at__date=today).count(),
        "total_assigned": deliveries.count(), "location": location,
        "unread_notifications": request.user.notifications.filter(is_read=False).count(),
    })


@staff_required
def reports(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_qs = Delivery.objects.filter(created_at__date__gte=week_start)
    total_week = week_qs.count()
    done_week = week_qs.filter(status="delivered").count()
    delivery_rows = week_qs.values("assigned_driver__first_name", "assigned_driver__last_name", "assigned_driver__username").annotate(
        total=Count("id"), delivered=Count("id", filter=Q(status="delivered")), failed=Count("id", filter=Q(status="failed"))
    ).order_by("-total")
    return render(request, "deliveries/reports.html", {
        "week_start": week_start, "total_week": total_week, "done_week": done_week,
        "completion_rate": round((done_week / total_week) * 100, 1) if total_week else 0,
        "failed_week": week_qs.filter(status="failed").count(),
        "driver_rows": delivery_rows,
    })


@staff_required
def export_deliveries_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="dmts-deliveries.csv"'
    writer = csv.writer(response)
    def safe_cell(value):
        value = "" if value is None else str(value)
        return "'" + value if value[:1] in {"=", "+", "-", "@", "\t", "\r"} else value
    writer.writerow(["Delivery ID", "Created", "Customer", "Phone", "Pickup", "Drop-off", "Driver", "Vehicle", "Status", "Priority", "Tracking code", "Delivered at"])
    for item in Delivery.objects.select_related("assigned_driver", "assigned_vehicle").order_by("-created_at"):
        writer.writerow([safe_cell(value) for value in [
            f"DMTS-{item.pk}", item.created_at.isoformat(), item.customer_name, item.customer_phone,
            item.pickup_address, item.dropoff_address,
            item.assigned_driver.get_full_name() or item.assigned_driver.username if item.assigned_driver else "",
            item.assigned_vehicle.registration_number if item.assigned_vehicle else "",
            item.get_status_display(), item.get_priority_display(), item.tracking_code, item.delivered_at.isoformat() if item.delivered_at else "",
        ]])
    return response


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    return render(request, "deliveries/notifications.html", {"notifications": notifications[:50]})


@login_required
@require_POST
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    if notification.url and url_has_allowed_host_and_scheme(notification.url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(notification.url)
    return redirect("deliveries:driver_dashboard" if request.user.is_driver else "deliveries:dashboard")


@driver_required
@require_POST
def toggle_location_sharing(request):
    location, _ = DriverLocation.objects.get_or_create(driver=request.user)
    data = _request_data(request)
    enabled = data.get("enabled") in [True, "true", "1", 1, "on"]
    location.is_sharing = enabled
    if not enabled:
        location.latitude = None
        location.longitude = None
        location.accuracy_metres = None
        location.speed_mps = None
        location.heading_degrees = None
    location.save()
    active_delivery = Delivery.objects.filter(assigned_driver=request.user, status__in=["picked_up", "in_transit"]).first()
    if active_delivery:
        log_event(active_delivery, request.user, "location_sharing", f"Driver location sharing {'enabled' if enabled else 'disabled'}")
    return JsonResponse({"success": True, "is_sharing": location.is_sharing})


def _request_data(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}
    return request.POST


@driver_required
@require_POST
def update_driver_location(request):
    data = _request_data(request)
    try:
        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "message": "Valid latitude and longitude are required."}, status=400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JsonResponse({"success": False, "message": "Coordinates are outside valid ranges."}, status=400)
    location, _ = DriverLocation.objects.get_or_create(driver=request.user)
    if not location.is_sharing:
        return JsonResponse({"success": False, "message": "Turn on location sharing first."}, status=409)
    try:
        accuracy = max(0, float(data.get("accuracy"))) if data.get("accuracy") not in (None, "") else None
        speed = max(0, float(data.get("speed"))) if data.get("speed") not in (None, "") else None
        heading = float(data.get("heading")) if data.get("heading") not in (None, "") else None
    except (TypeError, ValueError):
        accuracy, speed, heading = None, None, None
    now = timezone.now()
    location.latitude, location.longitude = lat, lon
    location.accuracy_metres, location.speed_mps, location.heading_degrees = accuracy, speed, heading
    location.updated_at = now
    location.save()
    active_delivery = Delivery.objects.filter(assigned_driver=request.user, status__in=["picked_up", "in_transit"]).first()
    # Store a trail point at most every 15 seconds; the current location updates on every GPS event.
    latest_ping = LocationPing.objects.filter(driver=request.user).order_by("-recorded_at").first()
    if not latest_ping or (now - latest_ping.recorded_at).total_seconds() >= 15:
        LocationPing.objects.create(driver=request.user, delivery=active_delivery, latitude=lat, longitude=lon,
                                    accuracy_metres=accuracy, speed_mps=speed, heading_degrees=heading)
    return JsonResponse({"success": True, "updated_at": now.isoformat()})


@staff_required
@never_cache
def api_live_locations(request):
    cutoff = timezone.now() - timedelta(minutes=5)
    locations = DriverLocation.objects.filter(is_sharing=True, updated_at__gte=cutoff).select_related("driver")
    result = []
    for loc in locations:
        active = Delivery.objects.filter(assigned_driver=loc.driver, status__in=["picked_up", "in_transit"]).first()
        result.append({
            "driver": loc.driver.get_full_name() or loc.driver.username,
            "latitude": float(loc.latitude) if loc.latitude is not None else None,
            "longitude": float(loc.longitude) if loc.longitude is not None else None,
            "accuracy": loc.accuracy_metres,
            "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
            "delivery_id": active.pk if active else None,
            "delivery_code": f"DMTS-{active.pk}" if active else "Available / between jobs",
            "customer": active.customer_name if active else "",
            "dropoff": active.dropoff_address if active else "",
        })
    return JsonResponse({"locations": result, "server_time": timezone.now().isoformat()})


@require_POST
@driver_required
def update_delivery_status(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk, assigned_driver=request.user)
    new_status = request.POST.get("status", "").strip()
    allowed = {
        "assigned": {"picked_up", "in_transit", "failed"},
        "picked_up": {"in_transit", "failed"},
        "in_transit": {"delivered", "failed"},
        "failed": {"assigned", "returned"},
    }
    if new_status not in allowed.get(delivery.status, set()):
        messages.error(request, "That status change is not allowed for this delivery.")
        return redirect("deliveries:driver_dashboard")
    if new_status == "delivered":
        recipient = request.POST.get("recipient_name", "").strip()
        if not recipient:
            messages.error(request, "Enter the name of the person who received the parcel before completing the delivery.")
            return redirect("deliveries:driver_dashboard")
        photo = request.FILES.get("proof_photo")
        if photo:
            if photo.size > 5 * 1024 * 1024:
                messages.error(request, "Proof photo must be 5 MB or smaller.")
                return redirect("deliveries:driver_dashboard")
            try:
                image = Image.open(photo)
                image.verify()
                photo.seek(0)
            except (UnidentifiedImageError, OSError, ValueError):
                messages.error(request, "The proof attachment must be a valid image file.")
                return redirect("deliveries:driver_dashboard")
        delivery.recipient_name = recipient
        delivery.delivery_notes = request.POST.get("delivery_notes", "").strip()
        if photo:
            delivery.proof_photo = photo
        delivery.delivered_at = timezone.now()
        loc = getattr(request.user, "location_status", None)
        if loc and loc.latitude is not None:
            log_event(delivery, request.user, "delivered", f"Delivered to {recipient}", loc.latitude, loc.longitude)
        else:
            log_event(delivery, request.user, "delivered", f"Delivered to {recipient}")
    elif new_status == "failed":
        reason = request.POST.get("failed_reason", "").strip()
        if not reason:
            messages.error(request, "Add a reason for the failed delivery.")
            return redirect("deliveries:driver_dashboard")
        delivery.failed_reason = reason
        log_event(delivery, request.user, "failed", f"Delivery attempt failed: {reason}")
    else:
        if new_status == "assigned":
            delivery.failed_reason = ""
        log_event(delivery, request.user, new_status, f"Status changed to {dict(Delivery.STATUS_CHOICES).get(new_status, new_status)}")
    delivery.status = new_status
    delivery.save()
    if new_status in {"delivered", "failed", "returned"}:
        other_active = Delivery.objects.filter(assigned_driver=request.user, status__in=["picked_up", "in_transit"]).exclude(pk=delivery.pk).exists()
        location = getattr(request.user, "location_status", None)
        if location and not other_active:
            location.is_sharing = False
            location.latitude = None
            location.longitude = None
            location.accuracy_metres = None
            location.speed_mps = None
            location.heading_degrees = None
            location.updated_at = None
            location.save()
    messages.success(request, f"DMTS-{delivery.pk} updated to {delivery.get_status_display()}.")
    return redirect("deliveries:driver_dashboard")


def public_tracking(request, tracking_code):
    delivery = get_object_or_404(Delivery, tracking_code=tracking_code)
    return render(request, "deliveries/public_tracking.html", {"delivery": delivery})


@require_POST
@login_required
def api_mark_read_all(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"success": True})


@staff_required
def weekly_report(request):
    return redirect("deliveries:reports")


@login_required
def home_redirect(request):
    if request.user.is_driver:
        return redirect("deliveries:driver_dashboard")
    return redirect("deliveries:dashboard")


@require_GET
@never_cache
def api_public_tracking(request, tracking_code):
    """Public tracking intentionally exposes only customer-safe delivery facts."""
    delivery = get_object_or_404(Delivery, tracking_code=tracking_code)
    payload = {
        "delivery": f"DMTS-{delivery.pk}",
        "status": delivery.status,
        "status_display": delivery.get_status_display(),
        "updated_at": delivery.updated_at.isoformat(),
        "estimated_delivery": delivery.estimated_delivery.isoformat() if delivery.estimated_delivery else None,
        "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
        "dropoff_address": delivery.dropoff_address,
        "driver_location": None,
    }
    # A customer can only see a driver's live position while that delivery is
    # actively on the road and the driver has explicitly enabled location sharing.
    if delivery.status == "in_transit" and delivery.assigned_driver_id:
        location = DriverLocation.objects.filter(
            driver_id=delivery.assigned_driver_id,
            is_sharing=True,
            updated_at__gte=timezone.now() - timedelta(minutes=5),
        ).first()
        if location and location.latitude is not None and location.longitude is not None:
            payload["driver_location"] = {
                "latitude": float(location.latitude),
                "longitude": float(location.longitude),
                "updated_at": location.updated_at.isoformat(),
            }
    return JsonResponse(payload)


@login_required
def proof_photo(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    allowed = request.user.can_manage_deliveries or (request.user.is_driver and delivery.assigned_driver_id == request.user.id)
    if not allowed:
        raise Http404
    if not delivery.proof_photo:
        raise Http404
    try:
        import mimetypes
        content_type = mimetypes.guess_type(delivery.proof_photo.name)[0] or "application/octet-stream"
        response = FileResponse(delivery.proof_photo.open("rb"), content_type=content_type)
        response["Cache-Control"] = "private, no-store"
        return response
    except (OSError, ValueError):
        raise Http404
