"""
One shape for two sources.

Model changes live in django-auditlog's LogEntry; auth and access events live
in AccessEvent. The reader wants a single chronological feed, so both are
normalised to the same fields here rather than making the client join them.
"""

from auditlog.models import LogEntry
from rest_framework import serializers

from .models import AccessEvent

# LogEntry.action is an integer; the API speaks the same verbs as AccessEvent.
CHANGE_ACTIONS = {
    LogEntry.Action.CREATE: ("create", "Created"),
    LogEntry.Action.UPDATE: ("update", "Updated"),
    LogEntry.Action.DELETE: ("delete", "Deleted"),
}


def actor_name(user) -> str:
    if user is None:
        return ""
    return (getattr(user, "full_name", "") or "").strip() or user.email


class ActivityEntrySerializer(serializers.Serializer):
    """Read-only projection. Both sources are mapped to this by the functions below."""

    id = serializers.CharField()
    source = serializers.ChoiceField(choices=["change", "access"])
    timestamp = serializers.DateTimeField()
    actor_id = serializers.IntegerField(allow_null=True)
    actor_email = serializers.CharField(allow_blank=True)
    actor_name = serializers.CharField(allow_blank=True)
    action = serializers.CharField()
    action_display = serializers.CharField()
    target = serializers.CharField(allow_blank=True)
    target_type = serializers.CharField(allow_null=True)
    changes = serializers.DictField(allow_null=True)
    metadata = serializers.DictField()
    remote_addr = serializers.CharField(allow_null=True)


def from_log_entry(entry: LogEntry) -> dict:
    action, display = CHANGE_ACTIONS.get(entry.action, ("unknown", "Unknown"))
    return {
        # Prefixed because the two tables number their rows independently.
        "id": f"change:{entry.pk}",
        "source": "change",
        "timestamp": entry.timestamp,
        "actor_id": entry.actor_id,
        # auditlog denormalises the address too, so an entry survives the
        # deletion of the account that made it — the same reason AccessEvent
        # carries its own copy.
        "actor_email": (entry.actor.email if entry.actor else "") or entry.actor_email or "",
        "actor_name": actor_name(entry.actor) or entry.actor_email or "",
        "action": action,
        "action_display": display,
        "target": entry.object_repr or "",
        "target_type": entry.content_type.model if entry.content_type else None,
        "changes": _pair_changes(entry.changes),
        "metadata": {},
        "remote_addr": entry.remote_addr,
    }


def from_access_event(event: AccessEvent) -> dict:
    return {
        "id": f"access:{event.pk}",
        "source": "access",
        "timestamp": event.timestamp,
        "actor_id": event.actor_id,
        "actor_email": event.actor_email,
        # A deleted account leaves actor null, so fall back to the email that
        # was denormalised onto the row when it was written.
        "actor_name": actor_name(event.actor) or event.actor_email,
        "action": event.action,
        "action_display": event.get_action_display(),
        "target": event.target,
        "target_type": None,
        "changes": None,
        "metadata": event.metadata or {},
        "remote_addr": event.remote_addr,
    }


def _pair_changes(changes) -> dict:
    """auditlog stores [old, new]; name the halves so the UI need not index."""
    if not changes:
        return {}
    out = {}
    for field, values in changes.items():
        if isinstance(values, list) and len(values) == 2:
            out[field] = {"old": values[0], "new": values[1]}
        else:
            out[field] = {"old": None, "new": values}
    return out


class ReportedEventSerializer(serializers.Serializer):
    """
    Body for the client-reported event endpoint.

    Only actions the browser is the sole witness to are accepted — the PNG is
    rendered and saved entirely client-side, so the server never sees it
    otherwise. Everything else is recorded server-side and must not be
    forgeable by a caller.
    """

    REPORTABLE = {AccessEvent.Action.EXPORT_PNG}

    action = serializers.ChoiceField(choices=sorted(REPORTABLE))
    target = serializers.CharField(max_length=255, allow_blank=True, default="")
