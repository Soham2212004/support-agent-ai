import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the default superuser from environment variables (idempotent)."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin@soham.com")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", username)
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "1234")

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Admin user '{username}' already exists - skipping.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'."))
