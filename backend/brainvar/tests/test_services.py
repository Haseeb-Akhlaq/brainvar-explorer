"""
Service layer: gene lookup, trajectory assembly and curve fitting.

These are the parts that know about the data, so they are tested directly
rather than through HTTP.
"""

import math

import numpy as np
from django.test import TestCase

from brainvar import services
from brainvar.models import GeneAlias

from .factories import make_gene, make_samples


class SearchGenesTests(TestCase):
    def setUp(self):
        make_gene("SCN2A", "ENSG00000136531", [10.0] * 5)
        make_gene("SCN1A", "ENSG00000144285", [5.0] * 5)
        make_gene("SCN1B", "ENSG00000105711", [2.0] * 5)
        make_gene("MEF2C", "ENSG00000081189", [8.0] * 5)

    def test_exact_match_ranks_first(self):
        results = services.search_genes("SCN1A")
        self.assertEqual(results[0].symbol, "SCN1A")

    def test_prefix_matches_are_alphabetical(self):
        symbols = [g.symbol for g in services.search_genes("SCN")]
        self.assertEqual(symbols, ["SCN1A", "SCN1B", "SCN2A"])

    def test_search_is_case_insensitive(self):
        self.assertEqual(services.search_genes("scn2a")[0].symbol, "SCN2A")

    def test_ensembl_prefix_matches(self):
        results = services.search_genes("ENSG00000136531")
        self.assertEqual(results[0].symbol, "SCN2A")

    def test_empty_query_returns_nothing(self):
        self.assertEqual(services.search_genes(""), [])
        self.assertEqual(services.search_genes("   "), [])

    def test_limit_is_respected(self):
        self.assertEqual(len(services.search_genes("SCN", limit=2)), 2)

    def test_no_match_returns_empty(self):
        self.assertEqual(services.search_genes("ZZZZNOPE"), [])

    def test_results_do_not_carry_the_expression_array(self):
        """
        Search must not ship 176 floats per result. The queryset defers
        `values`, so touching it would trigger an extra fetch.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            results = services.search_genes("SCN2A")
            _ = [g.symbol for g in results]
        self.assertTrue(all('"values"' not in q["sql"] for q in ctx.captured_queries))

        # Deferred, not loaded: reading it costs one more query.
        with self.assertNumQueries(1):
            _ = results[0].values

    def test_search_uses_a_bounded_number_of_queries(self):
        """Two at most: the exact match, then the prefix scan."""
        with self.assertNumQueries(2):
            list(services.search_genes("SCN"))


class ResolveGeneTests(TestCase):
    def setUp(self):
        self.gene = make_gene("SCN2A", "ENSG00000136531", [10.0] * 5)
        make_gene("SCN2B", "ENSG00000149575", [1.0] * 5)

    def test_resolves_by_symbol(self):
        gene, matched = services.resolve_gene("SCN2A")
        self.assertEqual(gene, self.gene)
        self.assertEqual(matched, "SCN2A")

    def test_resolves_by_ensembl_id(self):
        gene, matched = services.resolve_gene("ENSG00000136531")
        self.assertEqual(gene, self.gene)
        self.assertEqual(matched, "ENSG00000136531")

    def test_resolution_is_case_insensitive(self):
        self.assertEqual(services.resolve_gene("scn2a")[0], self.gene)
        self.assertEqual(services.resolve_gene("ScN2a")[0], self.gene)

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(services.resolve_gene("  SCN2A  ")[0], self.gene)

    def test_unknown_gene_raises_with_suggestions(self):
        with self.assertRaises(services.GeneNotFound) as ctx:
            services.resolve_gene("SCN2")
        self.assertEqual(ctx.exception.query, "SCN2")
        self.assertCountEqual(ctx.exception.suggestions, ["SCN2A", "SCN2B"])

    def test_completely_unknown_gene_has_no_suggestions(self):
        with self.assertRaises(services.GeneNotFound) as ctx:
            services.resolve_gene("ZZZZNOPE")
        self.assertEqual(ctx.exception.suggestions, [])

    def test_alias_from_a_second_source_resolves_to_the_matrix_gene(self):
        """
        Mirrors ADORA3: the HGNC mapping names a gene the matrix stores under a
        different Ensembl id. The alias must land on the gene that has data.
        """
        GeneAlias.objects.create(alias="OLDNAME", source="hgnc", gene=self.gene)
        gene, matched = services.resolve_gene("oldname")
        self.assertEqual(gene, self.gene)
        self.assertEqual(matched, "OLDNAME")


class BuildTrajectoryTests(TestCase):
    def setUp(self):
        self.samples = make_samples(ages=(43.0, 140.0, 280.0, 700.0, 3000.0))
        self.gene = make_gene("TEST", "ENSG00000000001", [1.0, 2.0, 4.0, 8.0, 16.0])

    def test_one_point_per_sample(self):
        points = services.build_trajectory(self.gene)
        self.assertEqual(len(points), 5)

    def test_points_are_sorted_by_age(self):
        points = services.build_trajectory(self.gene)
        ages = [p.age_days for p in points]
        self.assertEqual(ages, sorted(ages))

    def test_expression_is_aligned_to_the_right_donor(self):
        """
        The core invariant: values[i] belongs to the sample whose column_index
        is i, whatever order rows come back from the database in.
        """
        points = {p.braincode: p.cpm for p in services.build_trajectory(self.gene)}
        for sample in self.samples:
            self.assertEqual(points[sample.braincode], self.gene.values[sample.column_index])

    def test_log2_matches_the_original_transform(self):
        for p in services.build_trajectory(self.gene):
            self.assertAlmostEqual(p.log2_cpm, math.log2(p.cpm + 1e-3), places=12)

    def test_zero_cpm_lands_on_the_floor_not_an_error(self):
        gene = make_gene("SILENT", "ENSG00000000002", [0.0] * 5, aliases=False)
        for p in services.build_trajectory(gene):
            self.assertAlmostEqual(p.log2_cpm, math.log2(1e-3), places=12)

    def test_metadata_travels_with_each_point(self):
        by_code = {p.braincode: p for p in services.build_trajectory(self.gene)}
        for sample in self.samples:
            point = by_code[sample.braincode]
            self.assertEqual(point.sex, sample.sex)
            self.assertEqual(point.period, sample.period)
            self.assertEqual(point.age_units, sample.age_units)


class FitCurveTests(TestCase):
    def setUp(self):
        # Enough points for a stable degree-2 local fit.
        ages = tuple(float(a) for a in range(50, 3050, 100))
        make_samples(ages=ages)
        self.gene = make_gene(
            "RISING", "ENSG00000000001", [float(i + 1) for i in range(len(ages))]
        )

    def test_curve_has_the_configured_resolution(self):
        curve = services.fit_curve(services.build_trajectory(self.gene))
        self.assertEqual(len(curve.fitted), services.CURVE_RESOLUTION)
        self.assertEqual(len(curve.lower), services.CURVE_RESOLUTION)
        self.assertEqual(len(curve.age_days), services.CURVE_RESOLUTION)

    def test_resolution_is_configurable(self):
        curve = services.fit_curve(services.build_trajectory(self.gene), resolution=25)
        self.assertEqual(len(curve.fitted), 25)

    def test_x_grid_is_increasing_and_spans_the_samples(self):
        points = services.build_trajectory(self.gene)
        curve = services.fit_curve(points)
        self.assertEqual(curve.log2_age_days, sorted(curve.log2_age_days))
        self.assertAlmostEqual(curve.age_days[0], min(p.age_days for p in points), places=6)
        self.assertAlmostEqual(curve.age_days[-1], max(p.age_days for p in points), places=6)

    def test_both_x_representations_agree(self):
        curve = services.fit_curve(services.build_trajectory(self.gene))
        for days, log2_days in zip(curve.age_days, curve.log2_age_days):
            self.assertAlmostEqual(math.log2(days), log2_days, places=9)

    def test_band_brackets_the_fit(self):
        curve = services.fit_curve(services.build_trajectory(self.gene))
        for lo, fit, hi in zip(curve.lower, curve.fitted, curve.upper):
            self.assertLessEqual(lo, fit)
            self.assertLessEqual(fit, hi)

    def test_silent_gene_fits_a_flat_line_without_nans(self):
        gene = make_gene("SILENT", "ENSG00000000002", [0.0] * 30, aliases=False)
        curve = services.fit_curve(services.build_trajectory(gene))
        floor = math.log2(1e-3)
        self.assertTrue(np.allclose(curve.fitted, floor, atol=1e-8))
        self.assertFalse(any(math.isnan(v) for v in curve.lower))
        self.assertFalse(any(math.isnan(v) for v in curve.upper))
