from django.urls import path
from . import views

app_name = "deliveries"
urlpatterns = [
    path("", views.home_redirect, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("deliveries/", views.delivery_list, name="delivery_list"),
    path("deliveries/new/", views.create_delivery, name="create_delivery"),
    path("deliveries/<int:pk>/", views.delivery_detail, name="delivery_detail"),
    path("deliveries/<int:pk>/edit/", views.edit_delivery, name="edit_delivery"),
    path("deliveries/<int:pk>/assign/", views.assign_delivery, name="assign_delivery"),
    path("live-map/", views.live_map, name="live_map"),
    path("fleet/", views.fleet_list, name="fleet_list"),
    path("fleet/<int:pk>/toggle/", views.toggle_vehicle, name="toggle_vehicle"),
    path("reports/", views.reports, name="reports"),
    path("reports/export.csv", views.export_deliveries_csv, name="export_deliveries_csv"),
    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/<int:pk>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("driver/", views.driver_dashboard, name="driver_dashboard"),
    path("driver/location/toggle/", views.toggle_location_sharing, name="toggle_location_sharing"),
    path("driver/location/update/", views.update_driver_location, name="update_driver_location"),
    path("driver/deliveries/<int:pk>/status/", views.update_delivery_status, name="update_delivery_status"),
    path("deliveries/<int:pk>/proof-photo/", views.proof_photo, name="proof_photo"),
    path("api/live-locations/", views.api_live_locations, name="api_live_locations"),
    path("api/track/<str:tracking_code>/", views.api_public_tracking, name="api_public_tracking"),
    path("track/<str:tracking_code>/", views.public_tracking, name="public_tracking"),
]
