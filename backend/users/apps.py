from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "users"

    def ready(self):
        """
        Register the audited models.

        In ready() rather than at the bottom of models.py so registration
        happens once the app registry is populated — Group belongs to
        django.contrib.auth and is not importable from our own models module
        without an import cycle.
        """
        from auditlog.registry import auditlog
        from django.contrib.auth.models import Group

        from .models import User

        auditlog.register(
            User,
            exclude_fields=[
                # Never in the log, not even as a changed/unchanged marker.
                "password",
                # Both are recorded as explicit access events instead, so
                # logging the field write as well would double every entry.
                "last_login",
                "invited_at",
            ],
        )
        auditlog.register(Group)
        # Group membership is the interesting part of a permission change, and
        # it lives on the through table rather than on either model.
        auditlog.register(User.groups.through)
