"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from rest_framework.permissions import AllowAny

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    # OpenAPI 3 schema, plus two readers for it. Swagger UI is interactive —
    # requests can be sent from the page; ReDoc is the nicer read-only view.
    #
    # Left public: the schema describes the interface, not the data. Trying an
    # endpoint out still requires a session, so nothing is exposed by it.
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="redoc",
    ),
    path("api/", include("users.urls")),
    path("api/", include("brainvar.urls")),
    path("api/", include("activity.urls")),
    # DRF's browsable-API login, handy when demoing the endpoints.
    path("api-auth/", include("rest_framework.urls")),
]
