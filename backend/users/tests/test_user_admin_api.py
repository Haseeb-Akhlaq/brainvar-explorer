"""
Account administration: the list, and creating, editing and deleting accounts.

The interesting assertions are the negative ones. These endpoints hand out and
take away access to the whole instance, so the failures that matter are not
"an admin cannot do it" but "somebody who should not can", and "an admin did
something that cannot be undone from inside the app".
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

User = get_user_model()
PASSWORD = "a-good-test-password-123"
URL = "/api/users/"


def permission(codename: str, app_label: str = "users") -> Permission:
    return Permission.objects.get(codename=codename, content_type__app_label=app_label)


def make_admin(email: str = "admin@example.com") -> "User":
    """An account in the Admin group — the full set of panel permissions."""
    user = User.objects.create_user(email=email, password=PASSWORD)
    user.groups.add(Group.objects.get(name="Admin"))
    return user


class GroupSeedingTests(TestCase):
    """The data migrations run against the freshly built test database."""

    def test_both_groups_exist(self):
        self.assertTrue(Group.objects.filter(name="Admin").exists())
        self.assertTrue(Group.objects.filter(name="User").exists())

    def test_admin_group_carries_every_panel_permission(self):
        """
        Also proves the migrations cope with a fresh database, where the
        permission rows do not exist yet when they run.
        """
        held = {
            f"{p.content_type.app_label}.{p.codename}"
            for p in Group.objects.get(name="Admin").permissions.all()
        }
        self.assertEqual(
            held,
            {
                "users.view_user",
                "users.add_user",
                "users.change_user",
                "users.delete_user",
                "auth.view_group",
            },
        )

    def test_user_group_carries_no_permissions(self):
        """An ordinary account gains nothing beyond being signed in."""
        self.assertEqual(Group.objects.get(name="User").permissions.count(), 0)


class ReadAccessTests(TestCase):
    """Who may read the list."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.plain = User.objects.create_user(email="plain@example.com", password=PASSWORD)
        cls.plain.groups.add(Group.objects.get(name="User"))

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_authenticated_without_the_permission_is_refused(self):
        """
        The regression test for DRF's DjangoModelPermissions default, which
        maps GET to no permission at all. If reads ever stop requiring
        `users.view_user`, this fails — rather than the endpoint quietly
        serving the account list to everyone with a login.
        """
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_permission_via_group_is_allowed(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(URL).status_code, 200)

    def test_permission_granted_directly_is_allowed(self):
        """
        Nothing checks group membership, so a direct grant works identically.

        This is why the check is on the permission rather than on
        `groups__name="Admin"`: access can be given to one person without
        inventing a group or touching this code.
        """
        self.plain.user_permissions.add(permission("view_user"))
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get(URL).status_code, 200)

    def test_superuser_is_allowed_without_a_group(self):
        superuser = User.objects.create_superuser(email="root@example.com", password=PASSWORD)
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(URL).status_code, 200)

    def test_is_staff_alone_is_not_enough(self):
        """
        `is_staff` means "may open the Django admin", not "may read this".

        Worth pinning down: it is the flag people reach for by reflex, and it
        grants nothing here.
        """
        staff = User.objects.create_user(
            email="staff@example.com", password=PASSWORD, is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_deactivated_admin_is_refused(self):
        """
        `has_perm` returns False for an inactive user, so deactivating an
        account withdraws its access without unpicking group membership.
        """
        self.client.force_login(self.admin)
        self.admin.is_active = False
        self.admin.save()
        self.assertEqual(self.client.get(URL).status_code, 403)


class WritePermissionTests(TestCase):
    """Each method needs its own permission, not one blanket "is admin" flag."""

    @classmethod
    def setUpTestData(cls):
        # Only `view_user`, granted directly — can read the panel, nothing more.
        cls.reader = User.objects.create_user(email="reader@example.com", password=PASSWORD)
        cls.reader.user_permissions.add(permission("view_user"))
        cls.target = User.objects.create_user(email="target@example.com", password=PASSWORD)

    def setUp(self):
        self.client.force_login(self.reader)

    def test_create_needs_add_user(self):
        res = self.client.post(
            URL, {"email": "new@example.com"}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 403)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_edit_needs_change_user(self):
        res = self.client.patch(
            f"{URL}{self.target.pk}/", {"full_name": "Nope"}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 403)

    def test_delete_needs_delete_user(self):
        res = self.client.delete(f"{URL}{self.target.pk}/")
        self.assertEqual(res.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())

    def test_granting_add_user_alone_opens_only_create(self):
        """Permissions are independent: add does not imply change or delete."""
        self.reader.user_permissions.add(permission("add_user"))
        self.assertEqual(
            self.client.post(
                URL, {"email": "new@example.com"}, content_type="application/json"
            ).status_code,
            201,
        )
        self.assertEqual(self.client.delete(f"{URL}{self.target.pk}/").status_code, 403)


class CreateTests(TestCase):
    """Creating an account, which deliberately cannot sign in yet."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()

    def setUp(self):
        self.client.force_login(self.admin)

    def create(self, **payload):
        return self.client.post(URL, payload, content_type="application/json")

    def test_new_account_is_inactive_and_has_no_password(self):
        """
        The panel has no way to set a password, so it must not produce an
        account that looks ready to use. Inactive plus an unusable password
        means neither half of sign-in can succeed.
        """
        res = self.create(email="new@example.com", full_name="New Person")
        self.assertEqual(res.status_code, 201)

        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())

    def test_is_active_in_the_request_is_ignored(self):
        """A client cannot talk the endpoint into an immediately live account."""
        self.create(email="new@example.com", is_active=True)
        self.assertFalse(User.objects.get(email="new@example.com").is_active)

    def test_new_account_cannot_sign_in(self):
        """The end-to-end version of the two assertions above."""
        self.create(email="new@example.com")
        other = self.client_class()
        res = other.post(
            "/api/auth/login/",
            {"email": "new@example.com", "password": ""},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_email_is_normalised(self):
        self.create(email="Mixed.Case@EXAMPLE.COM")
        self.assertTrue(User.objects.filter(email="mixed.case@example.com").exists())

    def test_duplicate_email_is_rejected_case_insensitively(self):
        """
        Without normalising before the uniqueness check this passes validation
        and then collides at the database, which is a 500 rather than a 400.
        """
        res = self.create(email="ADMIN@example.com")
        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.json())

    def test_groups_can_be_assigned_on_creation(self):
        user_group = Group.objects.get(name="User")
        self.create(email="new@example.com", groups=[user_group.pk])
        self.assertEqual(
            list(User.objects.get(email="new@example.com").groups.values_list("name", flat=True)),
            ["User"],
        )

    def test_staff_and_superuser_cannot_be_set(self):
        """
        The escalation guard. `users.change_user` is a narrow permission; if
        these fields were writable it would silently be the widest one in the
        project, since a superuser holds every permission there is.
        """
        self.create(email="new@example.com", is_staff=True, is_superuser=True)
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)


class UpdateTests(TestCase):
    """Editing an account."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.other_admin = make_admin("second@example.com")
        cls.target = User.objects.create_user(
            email="target@example.com", password=PASSWORD, full_name="Old Name"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def patch(self, user, **payload):
        return self.client.patch(
            f"{URL}{user.pk}/", payload, content_type="application/json"
        )

    def test_details_can_be_edited(self):
        res = self.patch(self.target, full_name="New Name", orcid="0000-0002-1825-0097")
        self.assertEqual(res.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.full_name, "New Name")
        self.assertEqual(self.target.orcid, "0000-0002-1825-0097")

    def test_active_status_can_be_toggled(self):
        self.patch(self.target, is_active=False)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_deactivating_revokes_access_immediately(self):
        """The point of the toggle: it is access control, not a label."""
        self.target.user_permissions.add(permission("view_user"))
        self.patch(self.target, is_active=False)

        other = self.client_class()
        other.force_login(self.target)
        self.assertEqual(other.get(URL).status_code, 403)

    def test_groups_can_be_changed(self):
        self.patch(self.target, groups=[Group.objects.get(name="User").pk])
        self.assertEqual(
            list(self.target.groups.values_list("name", flat=True)), ["User"]
        )

    def test_superuser_cannot_be_granted(self):
        """The escalation guard again, on the edit path."""
        self.patch(self.target, is_superuser=True, is_staff=True)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_superuser)
        self.assertFalse(self.target.is_staff)

    def test_email_can_be_changed_but_not_onto_another_account(self):
        self.assertEqual(self.patch(self.target, email="moved@example.com").status_code, 200)
        self.assertEqual(self.patch(self.target, email="ADMIN@example.com").status_code, 400)


class LockoutGuardTests(TestCase):
    """
    Nothing may leave the instance with no active account able to manage users.

    That state is unrecoverable from inside the app — the panel is the only
    way in, and it would refuse everyone — so the API refuses to enter it
    rather than relying on the interface to hide the button.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.plain = User.objects.create_user(email="plain@example.com", password=PASSWORD)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_cannot_delete_your_own_account(self):
        res = self.client.delete(f"{URL}{self.admin.pk}/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("your own account", res.json()["detail"])
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_cannot_delete_the_last_admin(self):
        """
        Deleting someone else who happens to be the last one able to read the
        panel.

        The deleter here holds `delete_user` but not `view_user`, which is a
        real combination rather than a contrived one — the permissions are
        independent, so an account can be able to remove users without being
        able to list them. It is also the only way to reach this case: anyone
        holding `view_user` would themselves be the admin who remains.
        """
        remover = User.objects.create_user(email="remover@example.com", password=PASSWORD)
        remover.user_permissions.add(permission("delete_user"))
        self.client.force_login(remover)

        res = self.client.delete(f"{URL}{self.admin.pk}/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("locking everyone out", res.json()["detail"])
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_cannot_deactivate_the_last_admin(self):
        res = self.client.patch(
            f"{URL}{self.admin.pk}/", {"is_active": False}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_cannot_move_the_last_admin_out_of_the_admin_group(self):
        """
        The same accident by a different route, which is why the invariant is
        checked after the write rather than special-cased per field.
        """
        res = self.client.patch(
            f"{URL}{self.admin.pk}/",
            {"groups": [Group.objects.get(name="User").pk]},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(list(self.admin.groups.values_list("name", flat=True)), ["Admin"])

    def test_a_refused_write_is_rolled_back_completely(self):
        """
        The check runs after the change is applied, so the transaction is what
        makes the refusal safe — otherwise the name would stick while the
        group change was rejected.
        """
        self.client.patch(
            f"{URL}{self.admin.pk}/",
            {"full_name": "Renamed", "groups": []},
            content_type="application/json",
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.full_name, "")
        self.assertEqual(list(self.admin.groups.values_list("name", flat=True)), ["Admin"])

    def test_the_last_admin_can_be_removed_once_another_exists(self):
        """The guard is about the invariant, not about protecting a person."""
        make_admin("second@example.com")
        res = self.client.patch(
            f"{URL}{self.admin.pk}/", {"is_active": False}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)

    def test_an_active_superuser_counts_as_an_admin(self):
        """
        Mirrors ModelBackend, where a superuser holds every permission. If the
        count missed them, the guard would block a perfectly safe change.
        """
        User.objects.create_superuser(email="root@example.com", password=PASSWORD)
        res = self.client.patch(
            f"{URL}{self.admin.pk}/", {"is_active": False}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)

    def test_an_inactive_admin_does_not_count(self):
        """They cannot sign in, so they cannot rescue anyone."""
        dormant = make_admin("dormant@example.com")
        dormant.is_active = False
        dormant.save()
        res = self.client.patch(
            f"{URL}{self.admin.pk}/", {"is_active": False}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)

    def test_deleting_an_ordinary_account_is_allowed(self):
        res = self.client.delete(f"{URL}{self.plain.pk}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(User.objects.filter(pk=self.plain.pk).exists())


class PayloadTests(TestCase):
    """What the list contains."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.admin.full_name = "Ada Lovelace"
        cls.admin.save()
        cls.inactive = User.objects.create_user(
            email="dormant@example.com", password=PASSWORD, is_active=False
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_lists_every_account_including_inactive_ones(self):
        """
        Inactive accounts are a reason to look at this page, so they must
        appear rather than be filtered out as "not real users".
        """
        body = self.client.get(URL).json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(
            [row["email"] for row in body["results"]], ["admin@example.com", "dormant@example.com"]
        )

    def test_rows_report_status_groups_and_password_state(self):
        rows = {row["email"]: row for row in self.client.get(URL).json()["results"]}
        self.assertTrue(rows["admin@example.com"]["is_active"])
        self.assertFalse(rows["dormant@example.com"]["is_active"])
        self.assertEqual(rows["admin@example.com"]["groups"], ["Admin"])
        self.assertTrue(rows["admin@example.com"]["has_usable_password"])

    def test_an_account_created_here_is_reported_as_having_no_password(self):
        """
        What makes "Inactive" legible in the interface: the account was made
        by the panel and cannot sign in until someone sets credentials.
        """
        self.client.post(URL, {"email": "new@example.com"}, content_type="application/json")
        rows = {row["email"]: row for row in self.client.get(URL).json()["results"]}
        self.assertFalse(rows["new@example.com"]["has_usable_password"])

    def test_no_password_hash_is_exposed(self):
        """A serializer built on a field list, so a new model field cannot leak."""
        row = self.client.get(URL).json()["results"][0]
        self.assertNotIn("password", row)
        self.assertEqual(
            set(row),
            {
                "id", "email", "full_name", "orcid", "is_active", "is_staff",
                "is_superuser", "groups", "group_ids", "has_usable_password",
                "invited_at", "date_joined", "last_login",
            },
        )

    def test_groups_do_not_cost_a_query_per_row(self):
        """
        The property is that the query count does not grow with the number of
        accounts, so the test measures that rather than pinning a number — the
        fixed cost includes Django's own session and permission lookups, which
        are not this view's business to freeze.

        Drop the `prefetch_related` and this fails: serialising group names
        would issue one query per row.
        """
        with CaptureQueriesContext(connection) as few:
            small = self.client.get(URL).json()["count"]

        for i in range(10):
            User.objects.create_user(email=f"u{i}@example.com", password=PASSWORD)

        with CaptureQueriesContext(connection) as many:
            large = self.client.get(URL).json()["count"]

        # Guards against the test passing because neither request returned rows.
        self.assertEqual((small, large), (2, 12))
        self.assertEqual(len(many.captured_queries), len(few.captured_queries))


class GroupListTests(TestCase):
    """The supporting lookup behind the membership picker."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.plain = User.objects.create_user(email="plain@example.com", password=PASSWORD)

    def test_admin_sees_both_groups(self):
        self.client.force_login(self.admin)
        body = self.client.get("/api/groups/").json()
        self.assertEqual([g["name"] for g in body["results"]], ["Admin", "User"])

    def test_needs_the_group_permission(self):
        """Gated on `auth.view_group`, not on being signed in."""
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get("/api/groups/").status_code, 403)

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get("/api/groups/").status_code, 403)


class CurrentUserPermissionsTests(TestCase):
    """`/api/auth/me/` carries the permissions the client branches on."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.plain = User.objects.create_user(email="plain@example.com", password=PASSWORD)

    def test_permission_holder_sees_them_listed(self):
        self.client.force_login(self.admin)
        permissions = self.client.get("/api/auth/me/").json()["permissions"]
        self.assertIn("users.view_user", permissions)
        self.assertIn("users.delete_user", permissions)

    def test_ordinary_user_sees_an_empty_list(self):
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get("/api/auth/me/").json()["permissions"], [])

    def test_login_response_carries_permissions_too(self):
        """
        So the client renders the right controls immediately, rather than
        showing the panel button only after a reload.
        """
        res = self.client.post(
            "/api/auth/login/",
            {"email": "admin@example.com", "password": PASSWORD},
            content_type="application/json",
        )
        self.assertIn("users.view_user", res.json()["permissions"])

    def test_only_the_requesting_users_permissions_are_returned(self):
        """Not a directory of who can do what — just the caller's own rights."""
        self.client.force_login(self.plain)
        body = self.client.get("/api/auth/me/").json()
        self.assertEqual(body["email"], "plain@example.com")
        self.assertEqual(body["permissions"], [])
