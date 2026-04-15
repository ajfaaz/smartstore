from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Business, Profile


class Command(BaseCommand):
    help = "Create or update a default store owner, business, and profile."

    def add_arguments(self, parser):
        parser.add_argument("--business-name", default="SmartStore Demo Shop")
        parser.add_argument("--username", default="storeadmin")
        parser.add_argument("--email", default="storeadmin@example.com")
        parser.add_argument("--password", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        business_name = options["business_name"].strip()
        username = options["username"].strip()
        email = options["email"].strip()
        password = options["password"]

        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
            },
        )

        if not user_created:
            user.email = email
            user.is_staff = True
        user.set_password(password)
        user.save()

        business, business_created = Business.objects.get_or_create(
            name=business_name,
            defaults={"owner": user, "is_active": True},
        )

        if business.owner_id != user.id:
            business.owner = user
            business.save(update_fields=["owner"])

        profile, profile_created = Profile.objects.get_or_create(
            user=user,
            defaults={"business": business},
        )

        if profile.business_id != business.id:
            profile.business = business
            profile.save(update_fields=["business"])

        if user_created:
            self.stdout.write(self.style.SUCCESS(f"Created user: {username}"))
        else:
            self.stdout.write(self.style.WARNING(f"Updated existing user: {username}"))

        if business_created:
            self.stdout.write(self.style.SUCCESS(f"Created business: {business_name}"))
        else:
            self.stdout.write(self.style.WARNING(f"Using existing business: {business_name}"))

        if profile_created:
            self.stdout.write(self.style.SUCCESS("Created profile link"))
        else:
            self.stdout.write(self.style.WARNING("Updated profile link"))

        self.stdout.write(self.style.SUCCESS("Default store setup complete."))
