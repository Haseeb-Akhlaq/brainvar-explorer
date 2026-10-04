"""
The authentication boundary.

These assert what is reachable without a session as much as what login does,
because "the API is protected" is only true if every data endpoint actually
refuses an anonymous request.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = "a-good-test-password-123"


class PublicEndpointTests(TestCase):
    """Endpoints that must stay reachable without signing in."""

    def test_health_is_public(self):
        """The container health check has no session."""
        self.assertEqual(self.client.get("/api/health/").status_code, 200)

    def test_schema_is_public(self):
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)

    def test_api_docs_are_public(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)

    def test_csrf_endpoint_is_public(self):
        res = self.client.get("/api/auth/csrf/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("csrfToken", res.json())


class ProtectedEndpointTests(TestCase):
    """Every endpoint that returns data must refuse an anonymous request."""

    def test_gene_search_requires_a_session(self):
        self.assertEqual(self.client.get("/api/genes/", {"q": "SCN"}).status_code, 403)

    def test_gene_detail_requires_a_session(self):
        self.assertEqual(self.client.get("/api/genes/SCN2A/").status_code, 403)

    def test_stats_requires_a_session(self):
        self.assertEqual(self.client.get("/api/stats/").status_code, 403)

    def test_me_requires_a_session(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)

    def test_logout_requires_a_session(self):
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 403)


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="ada@example.com", password=PASSWORD, full_name="Ada Lovelace"
        )

    def test_login_returns_the_user(self):
        res = self.client.post(
            "/api/auth/login/",
            {"email": "ada@example.com", "password": PASSWORD},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], "ada@example.com")
        self.assertEqual(res.json()["full_name"], "Ada Lovelace")

    def test_login_never_returns_the_password(self):
        res = self.client.post(
            "/api/auth/login/",
            {"email": "ada@example.com", "password": PASSWORD},
            content_type="application/json",
        )
        self.assertNotIn("password", res.json())

    def test_email_is_case_insensitive(self):
        res = self.client.post(
            "/api/auth/login/",
            {"email": "ADA@EXAMPLE.COM", "password": PASSWORD},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)

    def test_wrong_password_is_rejected(self):
        res = self.client.post(
            "/api/auth/login/",
            {"email": "ada@example.com", "password": "wrong"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_unknown_and_wrong_password_are_indistinguishable(self):
        """The endpoint must not reveal whether an address has an account."""
        unknown = self.client.post(
            "/api/auth/login/",
            {"email": "nobody@example.com", "password": PASSWORD},
            content_type="application/json",
        )
        wrong = self.client.post(
            "/api/auth/login/",
            {"email": "ada@example.com", "password": "wrong"},
            content_type="application/json",
        )
        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(unknown.json(), wrong.json())

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        res = self.client.post(
            "/api/auth/login/",
            {"email": "ada@example.com", "password": PASSWORD},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_session_key_rotates_on_login(self):
        """Guards against session fixation."""
        self.client.get("/api/auth/csrf/")
        before = self.client.session.session_key
        self.client.post(
            "/api/auth/login/",
            {"email": "ada@example.com", "password": PASSWORD},
            content_type="application/json",
        )
        self.assertNotEqual(self.client.session.session_key, before)


class AuthenticatedAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email="ada@example.com", password=PASSWORD)

    def setUp(self):
        self.client.force_login(self.user)

    def test_me_returns_the_signed_in_user(self):
        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], "ada@example.com")

    def test_data_endpoints_are_reachable(self):
        self.assertEqual(self.client.get("/api/stats/").status_code, 200)
        self.assertEqual(self.client.get("/api/genes/", {"q": "X"}).status_code, 200)

    def test_logout_ends_the_session(self):
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/stats/").status_code, 403)
