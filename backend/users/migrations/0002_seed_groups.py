"""
Create the Admin and User groups.

A data migration rather than a management command so the groups exist after
`migrate` on any environment, including a fresh production deploy, with no
step for someone to forget.

Membership is left alone deliberately — who belongs to which group is an
operational decision made in the Django admin, not something a migration
should assert over accounts that already exist.
"""

from django.db import migrations

# The permissions each group carries. `Admin` can read the account list;
# `User` is empty because the dataset endpoints gate on authentication alone
# today. It exists so ordinary accounts have somewhere to sit, and so the next
# restricted feature has an obvious place to grant from.
GROUP_PERMISSIONS: dict[str, list[tuple[str, str, str, str]]] = {
    "Admin": [("users", "user", "view_user", "Can view user")],
    "User": [],
}


def seed_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    for group_name, permissions in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)

        for app_label, model, codename, name in permissions:
            # Permissions are normally created by a post_migrate signal, which
            # fires only once the whole migration run has finished. On a fresh
            # database this migration executes first, so `users.view_user`
            # does not exist yet and a lookup would fail. Creating it here is
            # safe: post_migrate matches on (codename, content_type) and will
            # find this row rather than adding a second one.
            content_type, _ = ContentType.objects.get_or_create(
                app_label=app_label, model=model
            )
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": name},
            )
            group.permissions.add(permission)


def unseed_groups(apps, schema_editor):
    """
    Reversible, but as a no-op.

    Deleting the groups would silently drop hand-assigned membership, which is
    a worse outcome than leaving two rows behind. Reversing this migration
    unblocks the schema; tidying the groups is a separate, deliberate act.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(seed_groups, unseed_groups),
    ]
