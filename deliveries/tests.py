import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Delivery, DeliveryEvent, DriverLocation, Notification

User = get_user_model()


class DMTSEndToEndTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="ops", password="StrongPass123!", role="staff", first_name="Ops")
        self.driver = User.objects.create_user(username="driver01", password="StrongPass123!", role="driver", first_name="Sam")
        self.other_driver = User.objects.create_user(username="driver02", password="StrongPass123!", role="driver")
        self.delivery = Delivery.objects.create(
            customer_name="Test Customer", customer_phone="0820000000",
            pickup_address="Depot, Cape Town", dropoff_address="Sea Point, Cape Town",
            assigned_driver=self.driver, status="in_transit",
        )

    def test_staff_dashboard_and_driver_restriction(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("deliveries:dashboard")).status_code, 200)
        self.client.force_login(self.driver)
        response = self.client.get(reverse("deliveries:delivery_list"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("deliveries:driver_dashboard"))
        response = self.client.get(reverse("deliveries:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("deliveries:driver_dashboard"))

    def test_driver_only_sees_own_dashboard_jobs(self):
        Delivery.objects.create(customer_name="Other", pickup_address="A", dropoff_address="B", assigned_driver=self.other_driver)
        self.client.force_login(self.driver)
        response = self.client.get(reverse("deliveries:driver_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Customer")
        self.assertNotContains(response, "Other")

    def test_driver_can_enable_gps_and_update_location(self):
        self.client.force_login(self.driver)
        response = self.client.post(reverse("deliveries:toggle_location_sharing"), {"enabled": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(DriverLocation.objects.get(driver=self.driver).is_sharing)
        response = self.client.post(
            reverse("deliveries:update_driver_location"),
            data=json.dumps({"latitude": -33.9249, "longitude": 18.4241, "accuracy": 7.5}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        location = DriverLocation.objects.get(driver=self.driver)
        self.assertEqual(float(location.latitude), -33.9249)
        self.assertEqual(float(location.longitude), 18.4241)

    def test_customer_tracking_only_shows_location_for_live_transit(self):
        DriverLocation.objects.create(driver=self.driver, latitude=-33.92, longitude=18.42, is_sharing=True)
        location = DriverLocation.objects.get(driver=self.driver)
        from django.utils import timezone
        location.updated_at = timezone.now()
        location.save()
        response = self.client.get(reverse("deliveries:api_public_tracking", args=[self.delivery.tracking_code]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()["driver_location"])
        self.delivery.status = "assigned"
        self.delivery.save()
        response = self.client.get(reverse("deliveries:api_public_tracking", args=[self.delivery.tracking_code]))
        self.assertIsNone(response.json()["driver_location"])

    def test_driver_cannot_update_another_drivers_delivery(self):
        self.delivery.assigned_driver = self.other_driver
        self.delivery.save()
        self.client.force_login(self.driver)
        response = self.client.post(reverse("deliveries:update_delivery_status", args=[self.delivery.pk]), {"status": "delivered", "recipient_name": "Someone"})
        self.assertEqual(response.status_code, 404)

    def test_delivery_creation_records_audit_event(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("deliveries:create_delivery"), {
            "customer_name": "New Recipient", "pickup_address": "Cape Town Depot", "dropoff_address": "Woodstock",
            "priority": "high", "package_description": "Documents",
        })
        self.assertEqual(response.status_code, 302)
        delivery = Delivery.objects.get(customer_name="New Recipient")
        self.assertTrue(delivery.tracking_code)
        self.assertTrue(DeliveryEvent.objects.filter(delivery=delivery, event_type="created").exists())

    def test_staff_views_render(self):
        self.client.force_login(self.staff)
        urls = [
            reverse("deliveries:delivery_list"),
            reverse("deliveries:create_delivery"),
            reverse("deliveries:delivery_detail", args=[self.delivery.pk]),
            reverse("deliveries:assign_delivery", args=[self.delivery.pk]),
            reverse("deliveries:live_map"),
            reverse("deliveries:fleet_list"),
            reverse("deliveries:reports"),
            reverse("deliveries:notifications"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_admin_can_create_driver_accounts(self):
        admin_user = User.objects.create_superuser(username="root", password="StrongPass123!", email="root@example.com")
        self.client.force_login(admin_user)
        add_url = reverse("admin:users_user_add")
        response = self.client.get(add_url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(add_url, {
            "username": "newdriver", "email": "newdriver@example.com", "first_name": "New",
            "last_name": "Driver", "role": "driver", "phone_number": "0821112222",
            "password1": "AnotherStrong123!", "password2": "AnotherStrong123!",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newdriver", role="driver").exists())

    def test_public_tracking_page_renders_without_login(self):
        response = self.client.get(reverse("deliveries:public_tracking", args=[self.delivery.tracking_code]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"DMTS-{self.delivery.pk}")

    def test_assignment_creates_driver_notification(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("deliveries:assign_delivery", args=[self.delivery.pk]), {"assigned_driver": self.other_driver.pk, "assigned_vehicle": ""})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Notification.objects.filter(user=self.other_driver, title="New delivery assigned").exists())


class SwiftSendUpgradeTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="upgradeops", password="StrongPass123!", role="staff")
        self.support = User.objects.create_user(username="support", password="StrongPass123!", role="support")
        self.driver = User.objects.create_user(username="upgrade-driver", password="StrongPass123!", role="driver")
        from .models import Vehicle
        self.vehicle = Vehicle.objects.create(registration_number="UPG-001", assigned_driver=self.driver)

    def test_support_cannot_create_delivery(self):
        self.client.force_login(self.support)
        response = self.client.get(reverse("deliveries:create_delivery"))
        self.assertEqual(response.status_code, 302)

    def test_support_can_view_operations_dashboard(self):
        self.client.force_login(self.support)
        response = self.client.get(reverse("deliveries:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_profile_can_be_updated(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("users:profile"), {"first_name": "Updated", "last_name": "Operator", "email": "ops@example.com", "phone_number": "0820000000"})
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.first_name, "Updated")

    def test_opening_notifications_does_not_mark_them_read(self):
        note = Notification.objects.create(user=self.staff, title="Test", message="Unread")
        self.client.force_login(self.staff)
        self.client.get(reverse("deliveries:notifications"))
        note.refresh_from_db()
        self.assertFalse(note.is_read)
