from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import Business
from inventory.views import send_trial_reminder_email


class Command(BaseCommand):
    help = "Send reminder emails to trial businesses nearing expiration."

    def handle(self, *args, **options):
        today = timezone.localdate()
        sent = 0
        skipped = 0

        for business in Business.objects.filter(subscription_plan="trial", is_active=True):
            if not business.trial_ends_at:
                skipped += 1
                continue

            days_left = (business.trial_ends_at - today).days
            if days_left not in {5, 3, 1, 0}:
                skipped += 1
                continue

            if business.last_trial_reminder_at == today:
                skipped += 1
                continue

            send_trial_reminder_email(business)
            business.last_trial_reminder_at = today
            business.save(update_fields=["last_trial_reminder_at"])
            sent += 1

        self.stdout.write(self.style.SUCCESS(f"Trial reminders sent: {sent}; skipped: {skipped}"))
