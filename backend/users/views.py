"""
Session authentication for the browser client.

Sessions rather than tokens: the frontend is a first-party application on a
sibling subdomain, and a cookie the browser will not hand to JavaScript is a
better place for a credential than localStorage.
"""

import logging

from django.contrib.auth import login, logout
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Q
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .emails import generate_password, send_invitation
from .models import User
from .permissions import CanChangeUsers, DjangoModelViewPermissions
from activity.models import AccessEvent
from activity.services import record

from .serializers import (
    GroupSerializer,
    LoginSerializer,
    UserListResponseSerializer,
    UserListSerializer,
    UserSerializer,
    UserWriteSerializer,
)

logger = logging.getLogger(__name__)


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Hands the client a CSRF cookie before it attempts to log in."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        operation_id="getCsrfToken",
        summary="Obtain a CSRF token",
        description=(
            "Sets the `csrftoken` cookie and returns the same value in the "
            "body. The login and logout endpoints require it in the "
            "`X-CSRFToken` header.\n\n"
            "Call this once before showing the login form."
        ),
        responses={200: None},
        examples=[OpenApiExample("Token", value={"csrfToken": "aBcD…"}, response_only=True)],
    )
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    """Exchange credentials for a session cookie."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        operation_id="login",
        summary="Log in",
        description=(
            "Authenticates by email and password and starts a session.\n\n"
            "Requires the `X-CSRFToken` header, obtained from "
            "`/api/auth/csrf/`. Email is matched case-insensitively."
        ),
        request=LoginSerializer,
        responses={200: UserSerializer, 400: None},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            # A refused attempt is the entry an auditor most wants, so it is
            # recorded before the 400 is raised. Only the address typed in is
            # kept — never the password, and never whether that address
            # exists, which would turn the log into an account oracle.
            record(
                request,
                AccessEvent.Action.SIGN_IN_FAILED,
                actor_email=str(request.data.get("email", ""))[:254],
            )
            serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        # Rotates the session key, so a session fixated before login is void.
        login(request, user)
        record(request, AccessEvent.Action.SIGN_IN, actor=user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    """End the session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["auth"],
        operation_id="logout",
        summary="Log out",
        description="Flushes the session. Requires the `X-CSRFToken` header.",
        request=None,
        responses={204: None},
    )
    def post(self, request):
        # logout() clears request.user, so the actor is taken first.
        record(request, AccessEvent.Action.SIGN_OUT, actor=request.user)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Who the session belongs to."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["auth"],
        operation_id="getCurrentUser",
        summary="Current user",
        description=(
            "The user the session belongs to, including every permission "
            "they hold as `app_label.codename`. The client uses those to "
            "decide which controls to offer.\n\n"
            "Returns 403 when there is no session, which is how the client "
            "decides to show the login page."
        ),
        responses={200: UserSerializer, 403: None},
    )
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserViewSet(ModelViewSet):
    """
    Account administration for the in-app admin panel.

    Every method is gated on the matching Django model permission rather than
    on `is_staff` or a group name — list needs `users.view_user`, create needs
    `users.add_user`, edit `users.change_user`, delete `users.delete_user`.
    They are granted together to the Admin group, but nothing here knows that:
    a direct grant to one person works identically.
    """

    permission_classes = [IsAuthenticated, DjangoModelViewPermissions]
    # DjangoModelPermissions reads the model off the queryset, so this
    # attribute is what tells it which permissions to look for.
    # prefetch: groups are serialised per row, and without it the list is N+1.
    queryset = User.objects.prefetch_related("groups").all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserListSerializer

    # -- the lockout invariant ------------------------------------------------
    #
    # Every write below is wrapped in a transaction, applied, and then checked:
    # at least one active account must still be able to reach this panel. Doing
    # it afterwards rather than predicting it in advance means one rule covers
    # every route to the same accident — deleting the last admin, deactivating
    # them, or moving them out of the Admin group all fail the same way.

    def _admins_remaining(self) -> int:
        """Active accounts that would still hold `users.view_user`."""
        permission = Permission.objects.filter(
            codename="view_user", content_type__app_label="users"
        ).first()
        if permission is None:  # pragma: no cover - the migration creates it
            return 0
        return (
            User.objects.filter(is_active=True)
            .filter(
                # Mirrors ModelBackend: superusers hold every permission,
                # otherwise it can come from a direct grant or from a group.
                Q(is_superuser=True)
                | Q(user_permissions=permission)
                | Q(groups__permissions=permission)
            )
            .distinct()
            .count()
        )

    def _assert_an_admin_remains(self):
        if self._admins_remaining() == 0:
            raise ValidationError(
                {
                    "detail": (
                        "This would leave no active account able to manage users, "
                        "locking everyone out of this page. Give another account "
                        "the Admin group first."
                    )
                }
            )

    @extend_schema(
        tags=["users"],
        summary="Create an account",
        description=(
            "Creates the account **inactive and without a password**, so it "
            "cannot sign in yet. A password is set in the Django admin; the "
            "account can then be activated from this panel.\n\n"
            "Requires the `users.add_user` permission. `is_staff` and "
            "`is_superuser` cannot be set here."
        ),
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Inactive with an unusable password: an account this panel creates is
        # a placeholder until someone sets credentials, and neither flag is
        # taken from the request so it cannot be talked out of that.
        user = serializer.save(is_active=False)
        user.set_unusable_password()
        user.save(update_fields=["password"])

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()
        self._assert_an_admin_remains()

    @extend_schema(
        tags=["users"],
        operation_id="inviteUser",
        summary="Send an account invitation",
        description=(
            "Generates a password, activates the account and emails the "
            "credentials.\n\n"
            "Safe to call again to re-send: doing so issues a **new** "
            "password and invalidates the previous one.\n\n"
            "Requires `users.change_user` — an invitation changes an existing "
            "account rather than creating one."
        ),
        request=None,
        responses={200: UserListSerializer, 400: None, 403: None},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanChangeUsers])
    def invite(self, request, pk=None):
        user = self.get_object()
        password = generate_password()

        # The write and the send share a transaction, so the two cannot
        # disagree. If SMTP fails the password is rolled back and the account
        # keeps the credentials it had — rather than being left holding a
        # password that only the server ever saw.
        try:
            with transaction.atomic():
                user.set_password(password)
                user.is_active = True
                user.invited_at = timezone.now()
                user.save(update_fields=["password", "is_active", "invited_at"])
                send_invitation(user, password)
        except OSError as exc:
            # smtplib raises OSError subclasses for refused connections,
            # timeouts and authentication failures alike.
            logger.exception("Invitation to %s failed", user.email)
            raise ValidationError(
                {"detail": f"The invitation could not be sent: {exc}"}
            ) from exc

        # Only after the transaction commits: a rolled-back invitation was
        # never sent, and must not appear in the log as though it were.
        record(request, AccessEvent.Action.INVITE_SENT, target=user.email)
        return Response(UserListSerializer(user).data)

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            # Separate from the invariant below, and worth its own message:
            # deleting yourself is almost always a misclick, and the generic
            # lockout text would not explain what happened.
            raise ValidationError({"detail": "You cannot delete your own account."})
        instance.delete()
        self._assert_an_admin_remains()

    @extend_schema(
        tags=["users"],
        summary="List users",
        description=(
            "All accounts, ordered by email address.\n\n"
            "Requires the `users.view_user` permission. An authenticated user "
            "without it gets 403 — being signed in is not sufficient."
        ),
        responses={200: UserListResponseSerializer, 403: None},
    )
    def list(self, request, *args, **kwargs):
        # Envelope matches /api/genes/ rather than DRF's bare array, so every
        # list in this API reads the same way on the client.
        users = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(users, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data})


@extend_schema(
    tags=["users"],
    operation_id="listGroups",
    summary="List groups",
    description=(
        "The groups an account can belong to, for the membership picker.\n\n"
        "Requires `auth.view_group`."
    ),
    responses={200: GroupSerializer(many=True)},
)
class GroupListView(ListAPIView):
    """Supporting lookup for the add/edit form."""

    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, DjangoModelViewPermissions]
    queryset = Group.objects.order_by("name")

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({"count": len(serializer.data), "results": serializer.data})
