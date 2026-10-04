from django.contrib import admin

from .models import AccessEvent


@admin.register(AccessEvent)
class AccessEventAdmin(admin.ModelAdmin):
    """Read-only: an audit trail that can be edited from the UI is not one."""

    list_display = ("timestamp", "actor_email", "action", "target", "remote_addr")
    list_filter = ("action", "timestamp")
    search_fields = ("actor_email", "target", "remote_addr")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Deletion is via `prune_activity`, which states a cutoff, rather than
        # by hand-picking rows out of the record.
        return False
