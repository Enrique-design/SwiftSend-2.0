import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial deployment administrator when credentials are configured."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not all((username, email, password)):
            self.stdout.write("Admin setup skipped: credentials are not configured.")
            return

        User = get_user_model()

        user = User.objects.filter(username=username).first()

        if user:
            if user.is_staff and user.is_superuser:
                self.stdout.write("Administrator already exists. No changes made.")
                return

            raise CommandError(
                "That username already belongs to a non-administrator account. "
                "Choose a different username."
            )

        user = User(
            username=username,
            email=email,
            is_staff=True,
            is_superuser=True,
            is_active=True,
            role="staff",
        )
        user.set_password(password)
        user.save()

        self.stdout.write(
            self.style.SUCCESS("Deployment administrator created successfully.")
        )