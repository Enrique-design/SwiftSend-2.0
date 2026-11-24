from django.contrib import admin
from .models import Delivery, DeliveryEvent, DriverLocation, LocationPing, Notification, Vehicle


class DeliveryEventInline(admin.TabularInline):
    model = DeliveryEvent
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "event_type", "description", "latitude", "longitude", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "status", "priority", "assigned_driver", "assigned_vehicle", "created_at")
    list_filter = ("status", "priority", "created_at")
    search_fields = ("customer_name", "customer_phone", "tracking_code", "dropoff_address")
    readonly_fields = ("status", "tracking_code", "created_at", "updated_at", "delivered_at", "assigned_driver", "assigned_vehicle")
    inlines = [DeliveryEventInline]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "make_model", "vehicle_type", "assigned_driver", "is_active")
    list_filter = ("vehicle_type", "is_active", "assigned_driver")
    search_fields = ("registration_number", "make_model")


class ReadOnlyOperationalAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(DeliveryEvent, ReadOnlyOperationalAdmin)
admin.site.register(DriverLocation, ReadOnlyOperationalAdmin)
admin.site.register(LocationPing, ReadOnlyOperationalAdmin)
admin.site.register(Notification)
