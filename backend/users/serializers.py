"""Serializers for authentication and the current user."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """The current user, as returned by the session endpoints."""

    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "orcid", "is_staff", "permissions")
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, user) -> list[str]:
        """
        Every permission this user holds, as `app_label.codename`.

        Sent so the client can decide what to offer — the admin-panel button
        appears for `users.view_user`. It is a hint for the interface, not the
        control: the API checks the same permission on every request, so a
        client that invents an entry gets a 403 from an empty page.

        Only ever the requesting user's own permissions, and `get_all_permissions`
        already folds in group membership, direct grants and superuser status.
        """
        return sorted(user.get_all_permissions())


class GroupSerializer(serializers.ModelSerializer):
    """A group, for the membership picker in the add/edit form."""

    class Meta:
        model = Group
        fields = ("id", "name")
        read_only_fields = fields


class UserListSerializer(serializers.ModelSerializer):
    """A row in the admin panel's user list."""

    # Names, not ids: the list is read by a person, and the group a user sits
    # in is worth showing even though nothing branches on it.
    groups = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    group_ids = serializers.PrimaryKeyRelatedField(
        source="groups", many=True, read_only=True
    )
    has_usable_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "orcid",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "group_ids",
            "has_usable_password",
            "invited_at",
            "date_joined",
            "last_login",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_has_usable_password(self, user) -> bool:
        """
        False for an account created through this panel, which is made without
        a password. Surfaced because such an account cannot sign in even once
        it is marked active, and a status column alone would not say so.
        """
        return user.has_usable_password()


class UserWriteSerializer(serializers.ModelSerializer):
    """
    Fields the panel may create and edit.

    `is_staff` and `is_superuser` are deliberately absent. Both are read back
    in the list, but allowing either to be written here would let anyone with
    `users.change_user` grant themselves every permission in the project —
    the panel would become a privilege-escalation route. Changing them stays
    in the Django admin, which is what `is_staff` gates in the first place.
    """

    groups = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Group.objects.all(), required=False
    )

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "orcid", "is_active", "groups")

    def validate_email(self, value):
        """
        Uniqueness is checked against the normalised address, because the
        model lowercases on save — without this, "A@example.com" would pass
        validation and then collide at the database with "a@example.com".
        """
        normalised = User.objects.normalize_email(value)
        existing = User.objects.filter(email=normalised)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return normalised


class UserListResponseSerializer(serializers.Serializer):
    """The payload of GET /api/users/."""

    count = serializers.IntegerField(help_text="Number of accounts returned.")
    results = UserListSerializer(many=True)


class LoginSerializer(serializers.Serializer):
    """Credentials for POST /api/auth/login/."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        # authenticate() goes through the model backend, which uses
        # get_by_natural_key — normalised, so any casing of the address works.
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            # Deliberately identical for an unknown address and a wrong
            # password, so the endpoint cannot be used to enumerate accounts.
            raise serializers.ValidationError(
                {"detail": "Incorrect email address or password."}, code="authorization"
            )
        attrs["user"] = user
        return attrs
