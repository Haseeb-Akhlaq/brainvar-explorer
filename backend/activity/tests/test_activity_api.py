"""
The activity log.

Two things are being asserted: that the log records what actually happened
(including the attempts that failed), and that it cannot be read, forged or
widened by someone who was not granted it.
"""

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings

from activity.models import AccessEvent
from brainvar.models import Gene, GeneAlias, Sample

User = get_user_model()
PASSWORD = "a-good-test-password-123"


def grant(user, codename):
    user.user_permissions.add(Permission.objects.get(codename=codename))
    # Permissions are cached on the instance after the first check.
    return User.objects.get(pk=user.pk)


class RecordingTests(TestCase):
    """What reaches the log when the application is used."""

    def setUp(self):
        self.user = User.objects.create_user(email="r@example.com", password=PASSWORD)

    def test_sign_in_is_recorded(self):
        self.client.post(
            "/api/auth/login/",
            {"email": "r@example.com", "password": PASSWORD},
            content_type="application/json",
        )
        event = AccessEvent.objects.get(action=AccessEvent.Action.SIGN_IN)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.actor_email, "r@example.com")

    def test_failed_sign_in_is_recorded_with_the_address_tried(self):
        """The refused attempt is the entry an auditor most wants."""
        res = self.client.post(
            "/api/auth/login/",
            {"email": "r@example.com", "password": "wrong"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        event = AccessEvent.objects.get(action=AccessEvent.Action.SIGN_IN_FAILED)
        self.assertIsNone(event.actor)
        self.assertEqual(event.actor_email, "r@example.com")

    def test_the_password_tried_is_never_recorded(self):
        self.client.post(
            "/api/auth/login/",
            {"email": "r@example.com", "password": "hunter2-should-not-appear"},
            content_type="application/json",
        )
        blob = "".join(str(e.metadata) + e.target for e in AccessEvent.objects.all())
        self.assertNotIn("hunter2", blob)

    def test_sign_out_is_attributed_before_the_session_is_flushed(self):
        self.client.force_login(self.user)
        self.client.post("/api/auth/logout/")
        event = AccessEvent.objects.get(action=AccessEvent.Action.SIGN_OUT)
        self.assertEqual(event.actor, self.user)

    def test_password_is_excluded_from_change_entries(self):
        """A password hash must not be reconstructable from the audit trail."""
        self.user.set_password("a-different-password-456")
        self.user.save()
        for entry in LogEntry.objects.all():
            self.assertNotIn("password", entry.changes or {})


class GeneViewDedupeTests(TestCase):
    """Gene views are the one high-volume event, so repeats collapse."""

    def setUp(self):
        # A real gene, so the endpoint returns 200 and actually records. With
        # no fixture the lookup 404s and the test would pass without ever
        # exercising the dedupe it claims to cover.
        # Five donors: the LOESS fit needs at least degree + 2 points, so a
        # single-sample fixture would 500 rather than exercise the recording.
        for i in range(5):
            Sample.objects.create(
                braincode=f"HSB10{i}",
                age_days=100.0 + i * 90,
                age=14.0 + i * 3,
                age_units="PCW",
                period=3 + i,
                epoch=0,
                sex=Sample.Sex.MALE if i % 2 else Sample.Sex.FEMALE,
                column_index=i,
            )
        gene = Gene.objects.create(
            ensembl_id="ENSG00000136531", symbol="SCN2A",
            name="sodium voltage-gated channel alpha subunit 2",
            values=[12.5, 14.0, 15.5, 13.0, 16.5],
            mean_log2=3.64,
        )
        for alias, source in (
            ("SCN2A", GeneAlias.Source.CPM),
            ("ENSG00000136531", GeneAlias.Source.ENSEMBL),
        ):
            GeneAlias.objects.create(alias=alias, source=source, gene=gene)
        self.user = User.objects.create_user(email="g@example.com", password=PASSWORD)
        self.client.force_login(self.user)

    def test_a_gene_view_is_recorded(self):
        res = self.client.get("/api/genes/SCN2A/")
        self.assertEqual(res.status_code, 200)
        event = AccessEvent.objects.get(action=AccessEvent.Action.GENE_VIEW)
        self.assertEqual(event.target, "SCN2A")
        self.assertEqual(event.actor, self.user)

    def test_repeat_views_of_one_gene_collapse(self):
        for _ in range(3):
            self.assertEqual(self.client.get("/api/genes/SCN2A/").status_code, 200)
        self.assertEqual(
            AccessEvent.objects.filter(action=AccessEvent.Action.GENE_VIEW).count(), 1
        )

    def test_dedupe_is_per_user(self):
        """One person's activity must not hide another's."""
        other = User.objects.create_user(email="h@example.com", password=PASSWORD)
        self.client.get("/api/genes/SCN2A/")
        self.client.force_login(other)
        self.client.get("/api/genes/SCN2A/")
        actors = set(
            AccessEvent.objects.filter(
                action=AccessEvent.Action.GENE_VIEW
            ).values_list("actor_id", flat=True)
        )
        self.assertEqual(actors, {self.user.id, other.id})

    @override_settings(ACTIVITY_GENE_VIEW_DEDUPE_SECONDS=0)
    def test_dedupe_can_be_switched_off(self):
        for _ in range(3):
            self.client.get("/api/genes/SCN2A/")
        self.assertEqual(
            AccessEvent.objects.filter(action=AccessEvent.Action.GENE_VIEW).count(), 3
        )

    def test_a_lookup_by_ensembl_id_records_the_symbol(self):
        """So one gene is one row however it was reached."""
        self.client.get("/api/genes/ENSG00000136531/")
        self.assertEqual(
            AccessEvent.objects.get(action=AccessEvent.Action.GENE_VIEW).target, "SCN2A"
        )


class PermissionTests(TestCase):
    """Reading the log is a power of its own."""

    def setUp(self):
        self.user = User.objects.create_user(email="p@example.com", password=PASSWORD)

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get("/api/activity/").status_code, 403)

    def test_a_plain_session_is_refused(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/activity/").status_code, 403)

    def test_managing_accounts_does_not_confer_reading_the_log(self):
        """The whole reason view_audit_logs exists separately from view_user."""
        self.client.force_login(grant(self.user, "view_user"))
        self.assertEqual(self.client.get("/api/activity/").status_code, 403)

    def test_the_audit_permission_grants_access(self):
        self.client.force_login(grant(self.user, "view_audit_logs"))
        self.assertEqual(self.client.get("/api/activity/").status_code, 200)

    def test_a_superuser_may_read_it(self):
        su = User.objects.create_superuser(email="su@example.com", password=PASSWORD)
        self.client.force_login(su)
        self.assertEqual(self.client.get("/api/activity/").status_code, 200)


class ReportedEventTests(TestCase):
    """The client may only report what the server cannot observe."""

    def setUp(self):
        self.user = User.objects.create_user(email="c@example.com", password=PASSWORD)
        self.client.force_login(self.user)

    def test_an_export_is_accepted(self):
        res = self.client.post(
            "/api/activity/report/",
            {"action": "export_png", "target": "SCN2A"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 202)
        event = AccessEvent.objects.get(action=AccessEvent.Action.EXPORT_PNG)
        self.assertEqual(event.target, "SCN2A")
        self.assertEqual(event.actor, self.user)

    def test_a_forged_action_is_rejected(self):
        """Otherwise anyone could write a sign-in they never made."""
        res = self.client.post(
            "/api/activity/report/",
            {"action": "sign_in", "target": "x"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(
            AccessEvent.objects.filter(action=AccessEvent.Action.SIGN_IN).exists()
        )

    def test_the_actor_comes_from_the_session_not_the_body(self):
        victim = User.objects.create_user(email="v@example.com", password=PASSWORD)
        self.client.post(
            "/api/activity/report/",
            {"action": "export_png", "target": "X", "actor": victim.id},
            content_type="application/json",
        )
        self.assertEqual(AccessEvent.objects.get().actor, self.user)

    def test_anonymous_cannot_report(self):
        self.client.logout()
        res = self.client.post(
            "/api/activity/report/",
            {"action": "export_png", "target": "X"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)


class FeedTests(TestCase):
    """The merged feed and its filters."""

    def setUp(self):
        self.admin = User.objects.create_superuser(email="a@example.com", password=PASSWORD)
        self.client.force_login(self.admin)
        AccessEvent.objects.all().delete()
        LogEntry.objects.all().delete()

    def _seed(self):
        AccessEvent.objects.create(
            actor=self.admin, actor_email=self.admin.email,
            action=AccessEvent.Action.SIGN_IN,
        )
        AccessEvent.objects.create(
            actor=self.admin, actor_email=self.admin.email,
            action=AccessEvent.Action.GENE_VIEW, target="SCN2A",
        )
        # A change entry, via a real request so the middleware attributes it.
        target = User.objects.create_user(email="t@example.com", password=PASSWORD)
        self.client.patch(
            f"/api/users/{target.id}/",
            {"full_name": "Renamed"},
            content_type="application/json",
        )

    def test_both_sources_appear_in_one_feed(self):
        self._seed()
        body = self.client.get("/api/activity/").json()
        sources = {row["source"] for row in body["results"]}
        self.assertEqual(sources, {"access", "change"})

    def test_entries_are_newest_first(self):
        self._seed()
        stamps = [row["timestamp"] for row in self.client.get("/api/activity/").json()["results"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_source_filter_narrows_to_one_stream(self):
        self._seed()
        body = self.client.get("/api/activity/", {"source": "access"}).json()
        self.assertTrue(all(r["source"] == "access" for r in body["results"]))

    def test_an_access_action_filter_excludes_change_rows(self):
        """The two streams share one action vocabulary in the API."""
        self._seed()
        body = self.client.get("/api/activity/", {"action": "sign_in"}).json()
        self.assertTrue(all(r["action"] == "sign_in" for r in body["results"]))
        self.assertGreaterEqual(body["count"], 1)

    def test_change_rows_carry_a_named_diff(self):
        self._seed()
        body = self.client.get("/api/activity/", {"source": "change"}).json()
        changes = [r["changes"] for r in body["results"] if r["changes"]]
        self.assertTrue(changes, "expected at least one diff")
        for pair in changes[0].values():
            self.assertIn("old", pair)
            self.assertIn("new", pair)

    def test_search_matches_a_gene_target(self):
        self._seed()
        body = self.client.get("/api/activity/", {"search": "SCN2A"}).json()
        self.assertTrue(any(r["target"] == "SCN2A" for r in body["results"]))

    def test_page_size_is_capped(self):
        body = self.client.get("/api/activity/", {"page_size": "9999"}).json()
        self.assertLessEqual(body["page_size"], 100)

    def test_paging_does_not_repeat_an_entry(self):
        for i in range(12):
            AccessEvent.objects.create(
                actor=self.admin, actor_email=self.admin.email,
                action=AccessEvent.Action.GENE_VIEW, target=f"GENE{i}",
            )
        first = self.client.get("/api/activity/", {"page_size": 5, "page": 1}).json()
        second = self.client.get("/api/activity/", {"page_size": 5, "page": 2}).json()
        ids = [r["id"] for r in first["results"]] + [r["id"] for r in second["results"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_a_deleted_account_keeps_its_history(self):
        """Often the history being audited is precisely the deleted one."""
        gone = User.objects.create_user(email="gone@example.com", password=PASSWORD)
        AccessEvent.objects.create(
            actor=gone, actor_email=gone.email, action=AccessEvent.Action.SIGN_IN
        )
        gone.delete()
        row = AccessEvent.objects.get(action=AccessEvent.Action.SIGN_IN)
        self.assertIsNone(row.actor)
        self.assertEqual(row.actor_email, "gone@example.com")
