"""
Give the Admin group the rest of the account-management permissions.

Kept as its own migration rather than an edit to 0002 so environments that
already ran the first one pick these up. Each API method maps to its own
permission, so granting them individually is what actually opens up create,
edit and delete in the panel.
"""

from django.db import migrations

# (app_label, model, codename, human name) — the name is only used when the
# row has to be created, which happens on a database whose post_migrate
# signal has not run yet.
PERMISSIONS = [
    ("users", "user", "add_user", "Can add user"),
    ("users", "user", "change_user", "Can change user"),
    ("users", "user", "delete_user", "Can delete user"),
    # The add/edit form offers group membership, so the panel needs to be able
    # to read the list of groups. Gated on the group model's own permission
    # rather than piggy-backing on `view_user`: it is a different model, and
    # the mechanism is the same one everything else here uses.
    ("auth", "group", "view_group", "Can view group"),
]


def grant(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    admin_group, _ = Group.objects.get_or_create(name="Admin")

    for app_label, model, codename, name in PERMISSIONS:
        content_type, _ = ContentType.objects.get_or_create(app_label=app_label, model=model)
        permission, _ = Permission.objects.get_or_create(
            codename=codename, content_type=content_type, defaults={"name": name}
        )
        admin_group.permissions.add(permission)


def revoke(apps, schema_editor):
    """
    Reverses cleanly: it takes back exactly what this migration granted and
    leaves `view_user` from 0002 in place, so reversing returns the panel to
    read-only rather than removing access to it.
    """
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    admin_group = Group.objects.filter(name="Admin").first()
    if admin_group is None:
        return

    for app_label, _model, codename, _name in PERMISSIONS:
        permission = Permission.objects.filter(
            codename=codename, content_type__app_label=app_label
        ).first()
        if permission is not None:
            admin_group.permissions.remove(permission)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_seed_groups"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
