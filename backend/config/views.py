"""Project-level views that don't belong to a domain app."""

from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from brainvar.serializers import HealthSerializer


@extend_schema(
    tags=["health"],
    operation_id="getHealth",
    summary="Health check",
    description=(
        "Liveness and readiness. Runs `SELECT 1`, so it reports a failure "
        "when the database is unreachable rather than claiming health. Used "
        "by the container health check and as an nginx upstream probe."
    ),
    responses={200: HealthSerializer},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(_request):
    """Liveness/readiness probe: reports service and database status."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database = "ok"
    except Exception as exc:  # pragma: no cover - only on a broken DB
        database = f"error: {exc.__class__.__name__}"

    return Response({"status": "ok", "service": "brainvar-api", "database": database})
