from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.crypto import get_random_string


def generate_tracking_code():
    return get_random_string(32)


class Vehicle(models.Model):
    VEHICLE_TYPES = (
        ("motorcycle", "Motorcycle"),
        ("car", "Car"),
        ("van", "Van"),
        ("truck", "Truck"),
    )
    registration_number = models.CharField(max_length=30, unique=True)
    make_model = models.CharField(max_length=100, blank=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default="van")
    capacity_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    assigned_driver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="primary_vehicles")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registration_number"]

    def __str__(self):
        return f"{self.registration_number} · {self.make_model or self.get_vehicle_type_display()}"


class Delivery(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("picked_up", "Picked up"),
        ("in_transit", "In transit"),
        ("delivered", "Delivered"),
        ("failed", "Delivery failed"),
        ("returned", "Returned to depot"),
        ("cancelled", "Cancelled"),
    ]
    PRIORITY_CHOICES = (
        ("standard", "Standard"),
        ("high", "High"),
        ("urgent", "Urgent"),
    )

    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=30, blank=True)
    customer_email = models.EmailField(blank=True)
    pickup_address = models.CharField(max_length=300)
    dropoff_address = models.CharField(max_length=300)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    dropoff_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    dropoff_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])

    package_description = models.CharField(max_length=180, blank=True)
    package_weight_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    priority = models.CharField(max_length=12, choices=PRIORITY_CHOICES, default="standard")
    scheduled_for = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)

    assigned_driver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="deliveries")
    assigned_vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="deliveries")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_deliveries")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    tracking_code = models.CharField(max_length=40, unique=True, default=generate_tracking_code, editable=False)
    recipient_name = models.CharField(max_length=160, blank=True)
    delivery_notes = models.TextField(blank=True)
    proof_photo = models.ImageField(upload_to="proof_of_delivery/%Y/%m/", blank=True, null=True)
    failed_reason = models.CharField(max_length=250, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["assigned_driver", "status"]),
        ]

    def __str__(self):
        return f"DMTS-{self.pk or 'NEW'} · {self.customer_name} · {self.get_status_display()}"

    @property
    def is_active(self):
        return self.status not in {"delivered", "failed", "returned", "cancelled"}

    @property
    def short_tracking_code(self):
        return self.tracking_code[:8].upper()

    def get_tracking_url(self):
        from django.urls import reverse
        return reverse("deliveries:public_tracking", kwargs={"tracking_code": self.tracking_code})


class DeliveryEvent(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="delivery_events")
    event_type = models.CharField(max_length=40)
    description = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.delivery_id}: {self.description}"


class DriverLocation(models.Model):
    driver = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="location_status")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    accuracy_metres = models.FloatField(null=True, blank=True)
    speed_mps = models.FloatField(null=True, blank=True)
    heading_degrees = models.FloatField(null=True, blank=True)
    is_sharing = models.BooleanField(default=False)
    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Location for {self.driver}"


class LocationPing(models.Model):
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="location_pings")
    delivery = models.ForeignKey(Delivery, null=True, blank=True, on_delete=models.SET_NULL, related_name="location_pings")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    accuracy_metres = models.FloatField(null=True, blank=True)
    speed_mps = models.FloatField(null=True, blank=True)
    heading_degrees = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["driver", "recorded_at"])]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} → {self.user}"
