"""
The custom user model.

Authentication is by email, so the interesting behaviour is normalisation:
`Ada@EXAMPLE.COM` and `ada@example.com` must be one account, and either casing must
log in. Django's own normalize_email only lowercases the domain, so this is
overridden — these tests pin that down.
"""

from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()
PASSWORD = "a-good-test-password-123"


class UserCreationTests(TestCase):
    def test_username_field_is_email(self):
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertEqual(User.REQUIRED_FIELDS, [])

    def test_username_and_name_fields_are_removed(self):
        fields = {f.name for f in User._meta.get_fields()}
        self.assertNotIn("username", fields)
        self.assertNotIn("first_name", fields)
        self.assertNotIn("last_name", fields)

    def test_create_user_defaults(self):
        user = User.objects.create_user(email="ada@example.com", password=PASSWORD)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))

    def test_create_superuser_defaults(self):
        user = User.objects.create_superuser(email="admin@example.com", password=PASSWORD)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_superuser_must_be_staff(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="a@example.com", password=PASSWORD, is_staff=False
            )

    def test_superuser_must_have_is_superuser(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="a@example.com", password=PASSWORD, is_superuser=False
            )

    def test_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password=PASSWORD)

    def test_str_is_the_email(self):
        user = User.objects.create_user(email="ada@example.com", password=PASSWORD)
        self.assertEqual(str(user), "ada@example.com")

    def test_full_name_helpers(self):
        user = User.objects.create_user(
            email="ada@example.com", password=PASSWORD, full_name="Ada Lovelace"
        )
        self.assertEqual(user.get_full_name(), "Ada Lovelace")
        self.assertEqual(user.get_short_name(), "Ada")

    def test_name_helpers_fall_back_to_email(self):
        user = User.objects.create_user(email="ada@example.com", password=PASSWORD)
        self.assertEqual(user.get_full_name(), "ada@example.com")
        self.assertEqual(user.get_short_name(), "ada@example.com")


class EmailNormalisationTests(TestCase):
    def test_whole_address_is_lowercased_not_just_the_domain(self):
        user = User.objects.create_user(email="Ada.Lovelace@EXAMPLE.COM", password=PASSWORD)
        self.assertEqual(user.email, "ada.lovelace@example.com")

    def test_direct_save_is_normalised_too(self):
        """Admin, ModelForms and DRF reach save() without the manager."""
        user = User(email="DIRECT@Example.Com")
        user.set_password(PASSWORD)
        user.save()
        self.assertEqual(User.objects.get(pk=user.pk).email, "direct@example.com")

    def test_clean_normalises_before_validation(self):
        user = User(email="Clean@EXAMPLE.COM")
        user.clean()
        self.assertEqual(user.email, "clean@example.com")

    def test_case_variant_duplicate_is_rejected(self):
        User.objects.create_user(email="ada@example.com", password=PASSWORD)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(email="ADA@EXAMPLE.COM", password=PASSWORD)

    def test_superuser_email_is_normalised(self):
        user = User.objects.create_superuser(email="Admin@EXAMPLE.COM", password=PASSWORD)
        self.assertEqual(user.email, "admin@example.com")


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email="ada@example.com", password=PASSWORD)

    def test_login_with_any_casing(self):
        for typed in ["ada@example.com", "Ada@EXAMPLE.COM", "ADA@example.com"]:
            with self.subTest(typed=typed):
                self.assertEqual(authenticate(username=typed, password=PASSWORD), self.user)

    def test_wrong_password_fails(self):
        self.assertIsNone(authenticate(username="ada@example.com", password="wrong"))

    def test_unknown_email_fails(self):
        self.assertIsNone(authenticate(username="nobody@example.com", password=PASSWORD))

    def test_inactive_user_cannot_authenticate(self):
        self.user.is_active = False
        self.user.save()
        self.assertIsNone(authenticate(username="ada@example.com", password=PASSWORD))

    def test_get_by_natural_key_is_case_insensitive(self):
        self.assertEqual(User.objects.get_by_natural_key("ADA@EXAMPLE.COM"), self.user)
