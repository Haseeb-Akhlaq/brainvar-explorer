from django.apps import AppConfig


class ActivityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "activity"
    # Distinct from django-auditlog's own "Audit log" section in the Django
    # admin: that one holds model diffs, this one holds auth and access.
    verbose_name = "Activity log"
