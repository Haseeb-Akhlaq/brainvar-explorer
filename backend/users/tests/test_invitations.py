"""
The account invitation.

An account created in the panel deliberately cannot sign in: no password, not
active. Inviting is what makes it usable, so these cover both halves — that
the credentials work afterwards, and that a failed send leaves nothing behind.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.test import TestCase

from users.emails import AMBIGUOUS, generate_password

User = get_user_model()
PASSWORD = "a-good-test-password-123"


def permission(codename: str, app_label: str = "users") -> Permission:
    return Permission.objects.get(codename=codename, content_type__app_label=app_label)


class PasswordGeneratorTests(TestCase):
    """The credential itself."""

    def test_default_length(self):
        self.assertEqual(len(generate_password()), 16)

    def test_honours_a_requested_length(self):
        self.assertEqual(len(generate_password(24)), 24)

    def test_contains_every_character_class(self):
        """
        Checked over many draws rather than one: a single password could
        satisfy this by luck even if the guarantee were not implemented.
        """
        for _ in range(100):
            pw = generate_password()
            self.assertTrue(any(c.islower() for c in pw), pw)
            self.assertTrue(any(c.isupper() for c in pw), pw)
            self.assertTrue(any(c.isdigit() for c in pw), pw)
            self.assertTrue(any(not c.isalnum() for c in pw), pw)

    def test_omits_visually_ambiguous_characters(self):
        """These get read off a screen and retyped; l/1 and O/0 cost support."""
        for _ in range(100):
            self.assertFalse(set(generate_password()) & set(AMBIGUOUS))

    def test_classes_are_not_always_in_the_same_positions(self):
        """
        Without the shuffle the first four characters would be lower, upper,
        digit, symbol every time — handing away four positions.
        """
        firsts = {generate_password()[0] for _ in range(100)}
        self.assertGreater(len(firsts), 4)
        self.assertTrue(any(not c.islower() for c in firsts))

    def test_passwords_are_not_repeated(self):
        self.assertEqual(len({generate_password() for _ in range(200)}), 200)


class InvitationPermissionTests(TestCase):
    """Who may send one."""

    @classmethod
    def setUpTestData(cls):
        cls.target = User.objects.create_user(email="target@example.com", password=PASSWORD)
        cls.url = f"/api/users/{cls.target.pk}/invite/"

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_signed_in_without_permission_is_refused(self):
        plain = User.objects.create_user(email="plain@example.com", password=PASSWORD)
        self.client.force_login(plain)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_add_user_alone_is_not_enough(self):
        """
        The reason this action does not use DjangoModelPermissions: that maps
        every POST to `add_user`, but an invitation resets an existing
        person's credentials. Someone who may only create accounts must not be
        able to do that.
        """
        creator = User.objects.create_user(email="creator@example.com", password=PASSWORD)
        creator.user_permissions.add(permission("add_user"), permission("view_user"))
        self.client.force_login(creator)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_change_user_is_what_grants_it(self):
        inviter = User.objects.create_user(email="inviter@example.com", password=PASSWORD)
        inviter.user_permissions.add(permission("change_user"))
        self.client.force_login(inviter)
        self.assertEqual(self.client.post(self.url).status_code, 200)

    def test_the_admin_group_can_invite(self):
        admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        admin.groups.add(Group.objects.get(name="Admin"))
        self.client.force_login(admin)
        self.assertEqual(self.client.post(self.url).status_code, 200)


class InvitationEffectTests(TestCase):
    """What sending one does to the account."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        cls.admin.groups.add(Group.objects.get(name="Admin"))

    def setUp(self):
        self.client.force_login(self.admin)
        # Created the way the panel creates one: inactive, no password.
        res = self.client.post(
            "/api/users/",
            {"email": "new@example.com", "full_name": "New Starter"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        self.new = User.objects.get(email="new@example.com")
        self.url = f"/api/users/{self.new.pk}/invite/"

    def test_account_starts_unusable(self):
        """The precondition the rest of this class depends on."""
        self.assertFalse(self.new.is_active)
        self.assertFalse(self.new.has_usable_password())
        self.assertIsNone(self.new.invited_at)

    def test_invitation_activates_and_sets_a_password(self):
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.new.refresh_from_db()
        self.assertTrue(self.new.is_active)
        self.assertTrue(self.new.has_usable_password())
        self.assertIsNotNone(self.new.invited_at)

    def test_the_emailed_password_actually_signs_in(self):
        """
        The test that matters: an invitation is only correct if the credentials
        in the recipient's inbox open the app.
        """
        self.client.post(self.url)
        body = mail.outbox[0].body

        # Recover the password from the email exactly as the recipient would.
        line = next(l for l in body.splitlines() if "Temporary password:" in l)
        password = line.split("Temporary password:")[1].strip()

        visitor = self.client_class()
        res = visitor.post(
            "/api/auth/login/",
            {"email": "new@example.com", "password": password},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], "new@example.com")

    def test_a_password_containing_an_ampersand_survives_the_template(self):
        """
        Regression. Django autoescapes template output, so "&" in a password
        was rendered "&amp;" in the plain-text body — the recipient copied a
        password that had never been set and could not sign in. The symbol
        alphabet contains "&", so this was reached roughly one invitation in
        three, which is exactly the kind of intermittent report that is
        miserable to chase.
        """
        with patch("users.views.generate_password", return_value="Ab3&xY7!qZ&pQ2m"):
            self.client.post(self.url)

        line = next(l for l in mail.outbox[0].body.splitlines() if "Temporary password:" in l)
        self.assertEqual(line.split("Temporary password:")[1].strip(), "Ab3&xY7!qZ&pQ2m")

        visitor = self.client_class()
        res = visitor.post(
            "/api/auth/login/",
            {"email": "new@example.com", "password": "Ab3&xY7!qZ&pQ2m"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)

    def test_html_body_still_escapes_the_password(self):
        """
        The opposite requirement, in the same message: in HTML the password
        must be escaped or a "<" would break the markup. Only the text body
        opts out.
        """
        with patch("users.views.generate_password", return_value="a<b&c>d1!Ab"):
            self.client.post(self.url)
        html = {alt.mimetype: alt.content for alt in mail.outbox[0].alternatives}["text/html"]
        self.assertIn("a&lt;b&amp;c&gt;d1!Ab", html)

    def test_resending_issues_a_new_password_and_voids_the_old(self):
        self.client.post(self.url)
        first = mail.outbox[0].body
        first_password = first.split("Temporary password:")[1].split("\n")[0].strip()

        self.client.post(self.url)
        second_password = mail.outbox[1].body.split("Temporary password:")[1].split("\n")[0].strip()

        self.assertNotEqual(first_password, second_password)

        visitor = self.client_class()
        stale = visitor.post(
            "/api/auth/login/",
            {"email": "new@example.com", "password": first_password},
            content_type="application/json",
        )
        self.assertEqual(stale.status_code, 400)

    def test_invited_at_moves_on_a_resend(self):
        self.client.post(self.url)
        self.new.refresh_from_db()
        first = self.new.invited_at

        self.client.post(self.url)
        self.new.refresh_from_db()
        self.assertGreater(self.new.invited_at, first)

    def test_response_carries_the_updated_row(self):
        """So the panel can update in place without a second request."""
        body = self.client.post(self.url).json()
        self.assertTrue(body["is_active"])
        self.assertTrue(body["has_usable_password"])
        self.assertIsNotNone(body["invited_at"])

    def test_the_password_is_never_returned_by_the_api(self):
        """It goes to the mailbox, not back to the browser."""
        body = self.client.post(self.url).json()
        password = mail.outbox[0].body.split("Temporary password:")[1].split("\n")[0].strip()
        self.assertNotIn(password, str(body))
        self.assertNotIn("password", body)


class InvitationMessageTests(TestCase):
    """The email itself."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        cls.admin.groups.add(Group.objects.get(name="Admin"))
        cls.target = User.objects.create_user(
            email="target@example.com", password=PASSWORD, full_name="Ada Lovelace"
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.client.post(f"/api/users/{self.target.pk}/invite/")
        self.message = mail.outbox[0]

    def html(self) -> dict[str, str]:
        """Alternatives keyed by mimetype, whichever way Django orders them."""
        return {alt.mimetype: alt.content for alt in self.message.alternatives}

    def test_one_email_to_the_invited_address(self):
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.message.to, ["target@example.com"])

    def test_has_both_a_plain_text_body_and_an_html_alternative(self):
        """
        Plain text is not optional: some clients render it in preference, and
        an HTML-only message scores worse with spam filters.
        """
        self.assertIn("Temporary password:", self.message.body)
        self.assertIn("text/html", self.html())
        self.assertIn("Welcome, Ada", self.html()["text/html"])

    def test_addresses_the_recipient_by_name(self):
        self.assertIn("Ada", self.message.body)

    def test_carries_the_logo_inline_rather_than_as_a_link(self):
        """
        Referenced by Content-ID and attached, so it renders without a network
        fetch — most clients block remote images by default.
        """
        html = self.html()["text/html"]
        self.assertIn("cid:brainvar-logo", html)
        self.assertNotIn("<img src=\"http", html)

        self.assertEqual(len(self.message.attachments), 1)
        attachment = self.message.attachments[0]
        self.assertEqual(attachment.get("Content-ID"), "<brainvar-logo>")
        self.assertTrue(attachment.get_content_type().startswith("image/"))
        self.assertIn("inline", attachment.get("Content-Disposition"))

    def test_links_to_the_app_not_the_api(self):
        self.assertIn("/login", self.message.body)

    def test_subject_names_the_application(self):
        self.assertIn("BrainVar", self.message.subject)


class InvitationFailureTests(TestCase):
    """When the mail server does not cooperate."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        cls.admin.groups.add(Group.objects.get(name="Admin"))
        cls.target = User.objects.create_user(email="target@example.com", password=PASSWORD)
        cls.target.is_active = False
        cls.target.set_unusable_password()
        cls.target.save()

    def setUp(self):
        self.client.force_login(self.admin)

    def test_a_failed_send_leaves_the_account_untouched(self):
        """
        The write and the send share a transaction. Without it the account
        would be holding a password that only the server ever saw — the
        recipient could not sign in and nobody would know why.
        """
        with patch("users.views.send_invitation", side_effect=OSError("connection refused")):
            res = self.client.post(f"/api/users/{self.target.pk}/invite/")

        self.assertEqual(res.status_code, 400)
        self.assertIn("could not be sent", res.json()["detail"])

        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertFalse(self.target.has_usable_password())
        self.assertIsNone(self.target.invited_at)

    def test_a_missing_account_is_a_404(self):
        self.assertEqual(self.client.post("/api/users/999999/invite/").status_code, 404)
