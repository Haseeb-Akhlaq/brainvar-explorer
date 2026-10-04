from django.conf import settings
from django.db import models


class AccessEvent(models.Model):
    """
    Something a user *did* that is not a model change.

    django-auditlog covers create/update/delete, which in this project means
    account administration. It cannot see the rest: signing in, looking a gene
    up, exporting a chart. Those are the whole of an ordinary researcher's
    activity, so they are recorded here and the two streams are merged by the
    API into one chronological feed.
    """

    class Action(models.TextChoices):
        SIGN_IN = "sign_in", "Signed in"
        SIGN_IN_FAILED = "sign_in_failed", "Failed sign-in"
        SIGN_OUT = "sign_out", "Signed out"
        GENE_VIEW = "gene_view", "Viewed gene"
        EXPORT_PNG = "export_png", "Exported PNG"
        INVITE_SENT = "invite_sent", "Sent invitation"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="access_events",
    )
    # Denormalised on purpose, and the reason the FK may be null:
    #   - a failed sign-in has no user to point at, only an address typed in
    #   - deleting an account must not silently orphan its history, which is
    #     often the history someone is auditing precisely *because* it was
    #     deleted
    actor_email = models.EmailField("actor email", blank=True)
    action = models.CharField(max_length=32, choices=Action.choices)
    # Free text rather than a generic FK: the target is usually a gene symbol,
    # which is not a row in this database at all.
    target = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    remote_addr = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "access event"
        verbose_name_plural = "access events"
        ordering = ["-timestamp"]
        indexes = [
            # The three ways the log is actually read: newest first, one
            # person's history, and one kind of event.
            models.Index(fields=["-timestamp"], name="activity_recent_idx"),
            models.Index(fields=["actor", "-timestamp"], name="activity_actor_idx"),
            models.Index(fields=["action", "-timestamp"], name="activity_action_idx"),
        ]

    def __str__(self) -> str:
        who = self.actor_email or "anonymous"
        return f"{who} {self.get_action_display().lower()}"
