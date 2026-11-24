from django import forms
from django.contrib.auth import get_user_model
from .models import Delivery, Vehicle

User = get_user_model()


class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = [
            "customer_name", "customer_phone", "customer_email",
            "pickup_address", "pickup_latitude", "pickup_longitude",
            "dropoff_address", "dropoff_latitude", "dropoff_longitude",
            "package_description", "package_weight_kg", "priority",
            "scheduled_for", "estimated_delivery", "special_instructions", "internal_notes",
        ]
        widgets = {
            "customer_name": forms.TextInput(attrs={"placeholder": "Customer or recipient name"}),
            "customer_phone": forms.TextInput(attrs={"placeholder": "+27 ..."}),
            "customer_email": forms.EmailInput(attrs={"placeholder": "customer@example.com"}),
            "pickup_address": forms.TextInput(attrs={"placeholder": "Street, suburb, city"}),
            "dropoff_address": forms.TextInput(attrs={"placeholder": "Street, suburb, city"}),
            "pickup_latitude": forms.NumberInput(attrs={"step": "any", "placeholder": "Optional"}),
            "pickup_longitude": forms.NumberInput(attrs={"step": "any", "placeholder": "Optional"}),
            "dropoff_latitude": forms.NumberInput(attrs={"step": "any", "placeholder": "Optional"}),
            "dropoff_longitude": forms.NumberInput(attrs={"step": "any", "placeholder": "Optional"}),
            "package_description": forms.TextInput(attrs={"placeholder": "e.g. Documents, electronics, parcel"}),
            "package_weight_kg": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "scheduled_for": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "estimated_delivery": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "special_instructions": forms.Textarea(attrs={"rows": 3, "placeholder": "Gate codes, access notes, handling instructions..."}),
            "internal_notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Internal operations notes (not visible to customer)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_for"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["estimated_delivery"].input_formats = ["%Y-%m-%dT%H:%M"]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["priority"].widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned = super().clean()
        for prefix in ("pickup", "dropoff"):
            lat = cleaned.get(f"{prefix}_latitude")
            lon = cleaned.get(f"{prefix}_longitude")
            if (lat is None) != (lon is None):
                self.add_error(f"{prefix}_latitude", "Enter both latitude and longitude, or leave both blank.")
        weight = cleaned.get("package_weight_kg")
        if weight is not None and weight < 0:
            self.add_error("package_weight_kg", "Package weight cannot be negative.")
        scheduled = cleaned.get("scheduled_for")
        eta = cleaned.get("estimated_delivery")
        if scheduled and eta and eta < scheduled:
            self.add_error("estimated_delivery", "Estimated delivery cannot be earlier than the scheduled collection time.")
        return cleaned


class AssignmentForm(forms.Form):
    assigned_driver = forms.ModelChoiceField(
        queryset=User.objects.none(), required=False, empty_label="Leave unassigned",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assigned_vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.none(), required=False, empty_label="No vehicle selected",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        self.instance_delivery_id = kwargs.pop("delivery_id", None)
        super().__init__(*args, **kwargs)
        self.fields["assigned_driver"].queryset = User.objects.filter(role__iexact="driver", is_active=True).order_by("first_name", "last_name", "username")
        self.fields["assigned_vehicle"].queryset = Vehicle.objects.filter(is_active=True).order_by("registration_number")

    def clean(self):
        cleaned = super().clean()
        driver = cleaned.get("assigned_driver")
        vehicle = cleaned.get("assigned_vehicle")
        if vehicle and driver and vehicle.assigned_driver_id and vehicle.assigned_driver_id != driver.id:
            self.add_error("assigned_vehicle", "This vehicle is assigned to another primary driver.")
        if vehicle:
            busy = Delivery.objects.filter(assigned_vehicle=vehicle).exclude(status__in=["delivered", "failed", "returned", "cancelled"])
            if self.instance_delivery_id:
                busy = busy.exclude(pk=self.instance_delivery_id)
            if busy.exists():
                self.add_error("assigned_vehicle", "This vehicle is already allocated to an active delivery.")
        if driver:
            busy = Delivery.objects.filter(assigned_driver=driver).exclude(status__in=["delivered", "failed", "returned", "cancelled"])
            if self.instance_delivery_id:
                busy = busy.exclude(pk=self.instance_delivery_id)
            if busy.exists():
                self.add_error("assigned_driver", "This driver already has an active delivery.")
        return cleaned


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["registration_number", "make_model", "vehicle_type", "capacity_kg", "assigned_driver", "notes", "is_active"]
        widgets = {"notes": forms.TextInput(attrs={"placeholder": "Optional fleet notes"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["vehicle_type"].widget.attrs["class"] = "form-select"
        self.fields["assigned_driver"].queryset = User.objects.filter(role__iexact="driver", is_active=True).order_by("first_name", "last_name", "username")
        self.fields["assigned_driver"].required = False
        self.fields["assigned_driver"].widget.attrs["class"] = "form-select"

    def clean_capacity_kg(self):
        capacity = self.cleaned_data.get("capacity_kg")
        if capacity is not None and capacity < 0:
            raise forms.ValidationError("Vehicle capacity cannot be negative.")
        return capacity
