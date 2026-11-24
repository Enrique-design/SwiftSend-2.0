from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = (
        ("staff", "Operations staff"),
        ("dispatcher", "Dispatcher"),
        ("driver", "Driver"),
        ("support", "Customer support"),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff", blank=True, null=True)
    phone_number = models.CharField(max_length=30, blank=True)

    @property
    def is_driver(self):
        return (self.role or "").lower() == "driver"

    @property
    def can_manage_deliveries(self):
        return self.is_superuser or self.is_staff or (self.role or "").lower() in {"staff", "dispatcher"}

    @property
    def can_view_operations(self):
        return self.can_manage_deliveries or (self.role or "").lower() == "support"

    @property
    def can_manage_fleet(self):
        return self.is_superuser or self.is_staff or (self.role or "").lower() in {"staff", "dispatcher"}

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display() if self.role else 'No role'})"
