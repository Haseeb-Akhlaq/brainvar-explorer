"""Trim both audit streams to a retention window."""

from datetime import timedelta

from auditlog.models import LogEntry
from django.core.management.base import BaseCommand
from django.utils import timezone

from activity.models import AccessEvent


class Command(BaseCommand):
    help = "Delete audit entries older than --days (default 365)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would go without deleting it.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)

        access = AccessEvent.objects.filter(timestamp__lt=cutoff)
        changes = LogEntry.objects.filter(timestamp__lt=cutoff)
        counts = (access.count(), changes.count())

        if options["dry_run"]:
            self.stdout.write(
                f"Would delete {counts[0]} access event(s) and {counts[1]} "
                f"change entr(ies) older than {days} days ({cutoff:%Y-%m-%d})."
            )
            return

        access.delete()
        changes.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {counts[0]} access event(s) and {counts[1]} "
                f"change entr(ies) older than {days} days."
            )
        )
