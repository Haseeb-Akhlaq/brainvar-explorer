"""Recording helper for access events."""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import AccessEvent

logger = logging.getLogger(__name__)


def client_ip(request) -> str | None:
    """
    Caller's address, honouring the proxy header only when one is deployed.

    X-Forwarded-For is client-controlled unless something upstream overwrites
    it, so it is trusted only when USE_X_FORWARDED_FOR says a proxy is in
    front. Otherwise a caller could forge any address into the audit trail.
    """
    if getattr(settings, "USE_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record(request, action: str, *, target: str = "", actor=None, **metadata):
    """
    Write one access event.

    Never raises. An audit trail that can 500 the request it is auditing is
    worse than one with a gap in it, and the gap is visible in the log.
    """
    try:
        if actor is None:
            candidate = getattr(request, "user", None)
            actor = candidate if getattr(candidate, "is_authenticated", False) else None

        email = metadata.pop("actor_email", "") or (getattr(actor, "email", "") or "")

        if action == AccessEvent.Action.GENE_VIEW and _recently_seen(actor, target):
            return None

        return AccessEvent.objects.create(
            actor=actor,
            actor_email=email,
            action=action,
            target=target[:255],
            metadata=metadata,
            remote_addr=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:400],
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("Could not record access event %r", action)
        return None


def _recently_seen(actor, target: str) -> bool:
    """True when this user already logged this gene inside the dedupe window."""
    window = getattr(settings, "ACTIVITY_GENE_VIEW_DEDUPE_SECONDS", 0)
    if not window or actor is None or not target:
        return False
    since = timezone.now() - timedelta(seconds=window)
    return AccessEvent.objects.filter(
        actor=actor,
        action=AccessEvent.Action.GENE_VIEW,
        target=target,
        timestamp__gte=since,
    ).exists()
