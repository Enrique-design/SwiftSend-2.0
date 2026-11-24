from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from deliveries.models import LocationPing


class Command(BaseCommand):
    help = "Delete driver GPS history older than the configured retention window (default: 30 days)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="Retain this many days of GPS history (default 30).")

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            self.stderr.write("--days must be at least 1.")
            return
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = LocationPing.objects.filter(recorded_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} old GPS history records (retention: {days} days)."))
