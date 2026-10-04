from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

app_name = "users"

# SimpleRouter rather than DefaultRouter: the api-root view DefaultRouter adds
# would sit at /api/ and duplicate what the OpenAPI schema already documents.
router = SimpleRouter()
router.register("users", views.UserViewSet, basename="user")

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view(), name="csrf"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("groups/", views.GroupListView.as_view(), name="group-list"),
    path("", include(router.urls)),
]
