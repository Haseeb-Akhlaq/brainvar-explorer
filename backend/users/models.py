from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    """
    Custom user, swapped in from the first migration.

    Authentication is by email; `username` is removed entirely. Defining this
    up front means access-control needs (dataset permissions, institutional
    affiliation) can be added later without the painful AUTH_USER_MODEL
    migration a project incurs once it has real users.
    """

    # Dropped from AbstractUser: email is the identifier, and a single
    # full_name field handles names that first/last cannot.
    username = None
    first_name = None
    last_name = None

    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(
        "full name",
        max_length=255,
        blank=True,
        help_text="Stored as a single field; first/last does not fit all names.",
    )
    orcid = models.CharField(
        "ORCID iD",
        max_length=19,
        blank=True,
        help_text="Researcher identifier, e.g. 0000-0002-1825-0097.",
    )
    invited_at = models.DateTimeField(
        "invitation sent",
        null=True,
        blank=True,
        help_text="When the welcome email was last sent. Null if never invited.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # prompted for by createsuperuser, besides USERNAME_FIELD

    objects = UserManager()

    class Meta:
        db_table = "users_user"
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["email"]
        permissions = [
            # Separate from view_user on purpose: managing accounts and
            # reading everyone's activity are different powers.
            ("view_audit_logs", "Can view the audit log"),
        ]

    def clean(self) -> None:
        """Normalise before form/model validation runs the uniqueness check."""
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def save(self, *args, **kwargs):
        """
        Last line of defence for the lowercase invariant.

        The manager normalises created users, but admin, ModelForms, DRF
        serializers and direct `User(...)` construction all reach save()
        without going through it.
        """
        self.email = self.__class__.objects.normalize_email(self.email)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else self.email
