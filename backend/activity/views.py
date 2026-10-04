"""Read API over the merged activity feed, plus the client-reported endpoint."""

from auditlog.models import LogEntry
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AccessEvent
from .serializers import (
    CHANGE_ACTIONS,
    ActivityEntrySerializer,
    ReportedEventSerializer,
    from_access_event,
    from_log_entry,
)
from .services import record

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
# Beyond this the merge below would have to pull an unreasonable number of
# rows from both tables to answer one page. Deep history is a filter question,
# not a paging one.
MAX_OFFSET = 5000


class CanViewActivity(BasePermission):
    """
    Deliberately not `users.view_user`.

    Managing accounts and reading everyone's activity are different powers;
    granting the first should not silently confer the second.
    """

    message = "You do not have permission to view the activity log."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.has_perm("users.view_audit_logs"))
        )


def _int_param(params, name):
    try:
        return int(params[name])
    except (KeyError, TypeError, ValueError):
        return None


class ActivityListView(APIView):
    """
    GET /api/activity/

    One reverse-chronological feed over both sources. `source=change` or
    `source=access` narrows it to one.
    """

    permission_classes = [CanViewActivity]

    @extend_schema(
        parameters=[
            OpenApiParameter("source", str, description="change | access"),
            OpenApiParameter("action", str, description="create, update, delete, sign_in, …"),
            OpenApiParameter("user_id", int, description="Filter to one actor."),
            OpenApiParameter("search", str, description="Matches target or actor email."),
            OpenApiParameter("date_from", str, description="ISO date, inclusive."),
            OpenApiParameter("date_to", str, description="ISO date, inclusive."),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int, description=f"Max {MAX_PAGE_SIZE}."),
        ],
        responses=ActivityEntrySerializer(many=True),
    )
    def get(self, request):
        params = request.query_params
        source = params.get("source") or ""
        action = params.get("action") or ""
        user_id = _int_param(params, "user_id")
        search = (params.get("search") or "").strip()
        date_from = params.get("date_from") or ""
        date_to = params.get("date_to") or ""

        page_size = min(_int_param(params, "page_size") or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
        page = max(_int_param(params, "page") or 1, 1)
        offset = min((page - 1) * page_size, MAX_OFFSET)

        changes = self._changes_queryset(action, user_id, search, date_from, date_to)
        accesses = self._access_queryset(action, user_id, search, date_from, date_to)

        if source == "change":
            accesses = accesses.none()
        elif source == "access":
            changes = changes.none()

        total = changes.count() + accesses.count()

        # Two tables with different columns cannot be paged by one SQL query
        # without a UNION over a common projection, which the JSON `changes`
        # column makes awkward. Instead each side supplies enough rows to
        # cover the requested window on its own — the merged page can never
        # need more than that from either — and the merge is done here.
        window = offset + page_size
        merged = [from_log_entry(e) for e in changes[:window]]
        merged += [from_access_event(e) for e in accesses[:window]]
        merged.sort(key=lambda row: row["timestamp"], reverse=True)

        rows = merged[offset : offset + page_size]
        return Response(
            {
                "results": ActivityEntrySerializer(rows, many=True).data,
                "count": total,
                "page": page,
                "page_size": page_size,
                "total_pages": max(1, -(-total // page_size)),
            }
        )

    def _changes_queryset(self, action, user_id, search, date_from, date_to):
        qs = LogEntry.objects.select_related("actor", "content_type").order_by("-timestamp")
        if action:
            codes = {v: k for k, (v, _) in CHANGE_ACTIONS.items()}
            # An access-only action (say sign_in) matches no change rows.
            qs = qs.filter(action=codes[action]) if action in codes else qs.none()
        if user_id is not None:
            qs = qs.filter(actor_id=user_id)
        if search:
            qs = qs.filter(Q(object_repr__icontains=search) | Q(actor__email__icontains=search))
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        return qs

    def _access_queryset(self, action, user_id, search, date_from, date_to):
        qs = AccessEvent.objects.select_related("actor").order_by("-timestamp")
        if action:
            valid = {choice.value for choice in AccessEvent.Action}
            qs = qs.filter(action=action) if action in valid else qs.none()
        if user_id is not None:
            qs = qs.filter(actor_id=user_id)
        if search:
            qs = qs.filter(Q(target__icontains=search) | Q(actor_email__icontains=search))
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        return qs


class ActivityActorsView(APIView):
    """GET /api/activity/actors/ — the people who appear in the log, for the filter."""

    permission_classes = [CanViewActivity]

    @extend_schema(responses={200: None})
    def get(self, request):
        seen: dict[int, str] = {}
        for pk, email in AccessEvent.objects.exclude(actor__isnull=True).values_list(
            "actor_id", "actor__email"
        ).distinct():
            seen[pk] = email
        for pk, email in LogEntry.objects.exclude(actor__isnull=True).values_list(
            "actor_id", "actor__email"
        ).distinct():
            seen[pk] = email
        actors = [{"id": pk, "email": email} for pk, email in seen.items() if email]
        actors.sort(key=lambda a: a["email"])
        return Response(actors)


class ReportEventView(APIView):
    """
    POST /api/activity/report/

    For the one action the server cannot observe: the PNG export runs entirely
    in the browser. The accepted actions are whitelisted in the serializer so
    this cannot be used to write arbitrary history, and the actor is always
    taken from the session rather than the body.
    """

    @extend_schema(request=ReportedEventSerializer, responses={202: None})
    def post(self, request):
        serializer = ReportedEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record(
            request,
            serializer.validated_data["action"],
            target=serializer.validated_data["target"],
        )
        return Response(status=status.HTTP_202_ACCEPTED)
