"""
HTTP contract for the API the frontend depends on.

These assert the response shape as well as the values, because the React client
reads specific keys — a rename would break it silently otherwise.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .factories import make_gene, make_samples


class AuthenticatedApiTestCase(TestCase):
    """
    Base for the data endpoints, which require a session.

    Access control itself is tested in users/tests/test_auth_api.py; these
    tests are about the response contract, so they sign in first.
    """

    def setUp(self):
        super().setUp()
        user = get_user_model().objects.create_user(
            email="tester@example.com", password="a-good-test-password-123"
        )
        self.client.force_login(user)


class GeneSearchApiTests(AuthenticatedApiTestCase):
    @classmethod
    def setUpTestData(cls):
        make_samples()
        make_gene("SCN2A", "ENSG00000136531", [10.0] * 5, name="sodium channel")
        make_gene("SCN1A", "ENSG00000144285", [5.0] * 5)
        make_gene("MEF2C", "ENSG00000081189", [8.0] * 5)

    def test_returns_matches_with_the_expected_shape(self):
        res = self.client.get("/api/genes/", {"q": "SCN2A"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["query"], "SCN2A")
        self.assertEqual(body["count"], 1)
        self.assertEqual(
            set(body["results"][0]),
            {"ensembl_id", "symbol", "name", "mean_log2", "is_expressed"},
        )
        self.assertEqual(body["results"][0]["symbol"], "SCN2A")

    def test_search_results_omit_the_expression_array(self):
        res = self.client.get("/api/genes/", {"q": "SCN"})
        self.assertNotIn("values", res.json()["results"][0])

    def test_prefix_search_returns_several(self):
        body = self.client.get("/api/genes/", {"q": "SCN"}).json()
        self.assertEqual([r["symbol"] for r in body["results"]], ["SCN1A", "SCN2A"])

    def test_missing_query_returns_empty_not_the_whole_table(self):
        body = self.client.get("/api/genes/").json()
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["results"], [])

    def test_limit_is_honoured(self):
        body = self.client.get("/api/genes/", {"q": "SCN", "limit": 1}).json()
        self.assertEqual(body["count"], 1)

    def test_limit_is_capped(self):
        """A huge limit must not turn search into a table scan."""
        res = self.client.get("/api/genes/", {"q": "SCN", "limit": 100000})
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(res.json()["count"], 50)

    def test_non_numeric_limit_is_a_400_not_a_500(self):
        res = self.client.get("/api/genes/", {"q": "SCN", "limit": "abc"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("detail", res.json())


class GeneDetailApiTests(AuthenticatedApiTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.samples = make_samples(ages=tuple(float(a) for a in range(50, 3050, 100)))
        cls.values = [float(i + 1) for i in range(len(cls.samples))]
        make_gene(
            "SCN2A", "ENSG00000136531", cls.values,
            name="sodium voltage-gated channel alpha subunit 2",
            hgnc_id="HGNC:10588", entrez_id="6326",
        )
        make_gene("SCN2B", "ENSG00000149575", [1.0] * len(cls.samples))

    def test_top_level_shape(self):
        body = self.client.get("/api/genes/SCN2A/").json()
        self.assertEqual(
            set(body), {"gene", "resolved_from", "n_samples", "points", "curve"}
        )

    def test_gene_block_carries_cross_references(self):
        gene = self.client.get("/api/genes/SCN2A/").json()["gene"]
        self.assertEqual(gene["ensembl_id"], "ENSG00000136531")
        self.assertEqual(gene["hgnc_id"], "HGNC:10588")
        self.assertEqual(gene["entrez_id"], "6326")

    def test_one_point_per_sample_with_full_metadata(self):
        body = self.client.get("/api/genes/SCN2A/").json()
        self.assertEqual(body["n_samples"], len(self.samples))
        self.assertEqual(len(body["points"]), len(self.samples))
        self.assertEqual(
            set(body["points"][0]),
            {"braincode", "age_days", "age", "age_units", "period", "sex", "cpm", "log2_cpm"},
        )

    def test_points_are_sorted_by_age_for_plotting(self):
        points = self.client.get("/api/genes/SCN2A/").json()["points"]
        ages = [p["age_days"] for p in points]
        self.assertEqual(ages, sorted(ages))

    def test_expression_is_aligned_to_the_right_donor(self):
        points = {p["braincode"]: p["cpm"] for p in self.client.get("/api/genes/SCN2A/").json()["points"]}
        for sample in self.samples:
            self.assertEqual(points[sample.braincode], self.values[sample.column_index])

    def test_curve_shape(self):
        curve = self.client.get("/api/genes/SCN2A/").json()["curve"]
        self.assertEqual(
            set(curve), {"age_days", "log2_age_days", "fitted", "lower", "upper"}
        )
        n = len(curve["fitted"])
        self.assertTrue(all(len(curve[k]) == n for k in curve))

    def test_curve_can_be_skipped(self):
        body = self.client.get("/api/genes/SCN2A/", {"curve": "false"}).json()
        self.assertIsNone(body["curve"])
        self.assertEqual(len(body["points"]), len(self.samples))

    def test_lookup_by_ensembl_id(self):
        body = self.client.get("/api/genes/ENSG00000136531/").json()
        self.assertEqual(body["gene"]["symbol"], "SCN2A")
        self.assertEqual(body["resolved_from"], "ENSG00000136531")

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(
            self.client.get("/api/genes/scn2a/").json()["gene"]["symbol"], "SCN2A"
        )

    def test_unknown_gene_is_404_with_suggestions(self):
        res = self.client.get("/api/genes/SCN2/")
        self.assertEqual(res.status_code, 404)
        body = res.json()
        self.assertEqual(body["query"], "SCN2")
        self.assertCountEqual(body["suggestions"], ["SCN2A", "SCN2B"])

    def test_completely_unknown_gene_is_404_without_suggestions(self):
        body = self.client.get("/api/genes/ZZZZNOPE/").json()
        self.assertEqual(body["suggestions"], [])

    def test_silent_gene_is_reported_not_hidden(self):
        make_gene("CDKL3", "ENSG00000006837", [0.0] * len(self.samples))
        body = self.client.get("/api/genes/CDKL3/").json()
        self.assertFalse(body["gene"]["is_expressed"])
        self.assertTrue(all(p["cpm"] == 0 for p in body["points"]))
        self.assertIsNotNone(body["curve"])

    def test_detail_is_a_small_fixed_number_of_queries(self):
        """
        Two indexed lookups for the data — the alias join and the samples —
        with no per-sample N+1.

        Only queries against the brainvar tables are counted: authentication
        adds a session and a user lookup, which are not what this guards.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            self.client.get("/api/genes/SCN2A/")

        data_queries = [q for q in ctx.captured_queries if "brainvar_" in q["sql"]]
        self.assertEqual(len(data_queries), 2, "\n\n".join(q["sql"] for q in data_queries))


class StatsAndHealthApiTests(AuthenticatedApiTestCase):
    @classmethod
    def setUpTestData(cls):
        make_samples(ages=(43.0, 280.0, 3000.0))
        make_gene("A", "ENSG00000000001", [1.0, 2.0, 3.0])
        make_gene("B", "ENSG00000000002", [0.0, 0.0, 0.0])

    def test_stats_reports_counts_and_age_range(self):
        body = self.client.get("/api/stats/").json()
        self.assertEqual(body["genes"], 2)
        self.assertEqual(body["genes_expressed"], 1)
        self.assertEqual(body["samples"], 3)
        self.assertEqual(body["age_days_min"], 43.0)
        self.assertEqual(body["age_days_max"], 3000.0)

    def test_health_reports_database_status(self):
        body = self.client.get(reverse("health")).json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "brainvar-api")
        self.assertEqual(body["database"], "ok")


class OpenApiSchemaTests(TestCase):
    """
    The published schema is part of the contract, so a rename that silently
    breaks generated clients should fail the build rather than ship.
    """

    def test_schema_is_served(self):
        res = self.client.get("/api/schema/")
        self.assertEqual(res.status_code, 200)

    def test_swagger_ui_renders(self):
        res = self.client.get("/api/docs/")
        self.assertEqual(res.status_code, 200)

    def test_redoc_renders(self):
        res = self.client.get("/api/redoc/")
        self.assertEqual(res.status_code, 200)

    def test_schema_documents_every_endpoint(self):
        from drf_spectacular.generators import SchemaGenerator

        schema = SchemaGenerator().get_schema(request=None, public=True)
        self.assertEqual(
            set(schema["paths"]),
            {
                "/api/genes/",
                "/api/genes/{query}/",
                "/api/stats/",
                "/api/health/",
                "/api/auth/csrf/",
                "/api/auth/login/",
                "/api/auth/logout/",
                "/api/users/",
                "/api/users/{id}/",
                "/api/users/{id}/invite/",
                "/api/groups/",
                "/api/auth/me/",
                "/api/activity/",
                "/api/activity/actors/",
                "/api/activity/report/",
            },
        )

    def test_operation_ids_are_explicit_and_unique(self):
        """
        Auto-generated ids collide between the two gene endpoints, and clients
        name their generated methods after them.
        """
        from drf_spectacular.generators import SchemaGenerator

        schema = SchemaGenerator().get_schema(request=None, public=True)
        ids = [op["operationId"] for path in schema["paths"].values() for op in path.values()]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate operationIds: {ids}")
        self.assertIn("getGeneTrajectory", ids)
        self.assertIn("searchGenes", ids)
