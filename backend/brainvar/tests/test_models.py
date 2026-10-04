"""
Model constraints.

The important ones are the uniqueness guarantees: they are what stops a bad
load silently mis-plotting every gene in the application.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from brainvar.models import Gene, GeneAlias, Sample

from .factories import make_gene, make_samples


class SampleTests(TestCase):
    def test_braincode_is_unique(self):
        make_samples(ages=(43.0,))
        with self.assertRaises(IntegrityError):
            Sample.objects.create(
                braincode="HSB900", age_days=100, age=14, age_units="PCW",
                period=2, epoch=0, sex="Male", column_index=99,
            )

    def test_column_index_is_unique(self):
        """
        Two samples cannot claim the same slot in Gene.values. Without this the
        expression-to-donor join could silently scramble every plot.
        """
        make_samples(ages=(43.0,))
        with self.assertRaises(IntegrityError):
            Sample.objects.create(
                braincode="HSB999", age_days=100, age=14, age_units="PCW",
                period=2, epoch=0, sex="Male", column_index=0,
            )

    def test_default_ordering_is_by_age(self):
        make_samples(ages=(3000.0, 43.0, 280.0))
        ages = list(Sample.objects.values_list("age_days", flat=True))
        self.assertEqual(ages, sorted(ages))

    def test_str_shows_code_and_age(self):
        s = make_samples(ages=(43.0,))[0]
        self.assertIn("HSB900", str(s))
        self.assertIn("PCW", str(s))


class GeneTests(TestCase):
    def test_ensembl_id_is_unique(self):
        make_gene("AAA", "ENSG00000000001", [1.0], aliases=False)
        with self.assertRaises(IntegrityError):
            make_gene("BBB", "ENSG00000000001", [2.0], aliases=False)

    def test_symbol_need_not_be_unique(self):
        """2,158 symbols are shared by more than one gene in the real matrix."""
        make_gene("DUP", "ENSG00000000001", [1.0], aliases=False)
        make_gene("DUP", "ENSG00000000002", [2.0], aliases=False)
        self.assertEqual(Gene.objects.filter(symbol="DUP").count(), 2)

    def test_values_round_trip_as_floats(self):
        g = make_gene("AAA", "ENSG00000000001", [1.5, 0.0, 12.75], aliases=False)
        stored = Gene.objects.get(pk=g.pk).values
        self.assertEqual(stored, [1.5, 0.0, 12.75])
        self.assertIsInstance(stored[0], float)

    def test_silent_gene_is_flagged(self):
        g = make_gene("SILENT", "ENSG00000000003", [0.0] * 5, aliases=False)
        self.assertFalse(g.is_expressed)

    def test_expressed_gene_is_flagged(self):
        g = make_gene("LOUD", "ENSG00000000004", [0.0, 0.0, 0.1], aliases=False)
        self.assertTrue(g.is_expressed)


class GeneAliasTests(TestCase):
    def test_alias_is_unique_across_genes(self):
        """
        One name resolves to exactly one gene, so the 295 build-mismatch cases
        cannot produce an ambiguous lookup.
        """
        g1 = make_gene("AAA", "ENSG00000000001", [1.0])
        g2 = make_gene("BBB", "ENSG00000000002", [1.0])
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GeneAlias.objects.create(alias="AAA", source="hgnc", gene=g2)
        self.assertEqual(GeneAlias.objects.get(alias="AAA").gene, g1)

    def test_deleting_a_gene_removes_its_aliases(self):
        g = make_gene("AAA", "ENSG00000000001", [1.0])
        self.assertEqual(GeneAlias.objects.count(), 2)
        g.delete()
        self.assertEqual(GeneAlias.objects.count(), 0)

    def test_gene_exposes_its_aliases(self):
        g = make_gene("AAA", "ENSG00000000001", [1.0])
        self.assertCountEqual(
            g.aliases.values_list("alias", flat=True), ["AAA", "ENSG00000000001"]
        )
