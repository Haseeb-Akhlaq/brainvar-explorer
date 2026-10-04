"""
The load_brainvar management command.

Run against a small hand-written dataset whose correct answers are known, so
the column alignment, derived summaries and alias precedence can all be
asserted exactly. A silent misalignment here would mis-plot every gene in the
application, so this is the most important thing in the suite.
"""

import math
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase

from brainvar.models import Gene, GeneAlias, Sample

# Deliberately awkward: the metadata rows are in a DIFFERENT order from the
# matrix columns, which is what the loader's column_index mapping has to fix.
CPM_HEADER = ["HSB001", "HSB002", "HSB003"]
CPM_ROWS = [
    ("ENSG00000000001|AAA", [10.0, 20.0, 30.0]),
    ("ENSG00000000002|BBB", [0.0, 0.0, 0.0]),      # silent everywhere
    ("ENSG00000000003|CCC", [1.0, 0.0, 3.0]),
    ("ENSG00000000004|", [7.0, 8.0, 9.0]),          # no symbol after the pipe
    ("ENSG00000000005|SHARED", [2.0, 4.0, 6.0]),    # the matrix's claim on "SHARED"
    ("ENSG00000000006|ZZZ", [5.0, 5.0, 5.0]),       # the mapping's rival claim
]
META_ROWS = [
    # Braincode, AgeDays, Age, AgeUnits, Period, sex, Epoch, tissue
    ("HSB003", "3000", "8.2", "Years", "12", "Female", "3", "cortex"),
    ("HSB001", "43", "6.14", "PCW", "1", "Male", "0", "cortex"),
    ("HSB002", "280", "40", "PCW", "7", "Female", "1", "cortex"),
]
MAP_ROWS = [
    # symbol, name, hgnc_id, entrez_id, ensembl_gene_id
    ("AAA", "alpha gene", "HGNC:1", "111", "ENSG00000000001"),
    ("CCC_OLD_NAME", "gamma gene", "HGNC:3", "333", "ENSG00000000003"),
    ("DDD", "delta gene", "HGNC:4", "444", "ENSG00000000004"),
    ("GHOST", "not in the matrix", "HGNC:9", "999", "ENSG00000000999"),
    ("NOID", "no ensembl id", "HGNC:8", "888", "."),
    # The mapping assigns SHARED to a DIFFERENT gene than the matrix does —
    # the real conflict behind the 295 genes built against another Ensembl
    # release. The matrix must win, because it is the only source with data.
    ("SHARED", "conflicting name", "HGNC:5", "555", "ENSG00000000006"),
]


def write_dataset(directory: Path):
    with (directory / "brainVar.CPM-10042019.tsv").open("w") as f:
        f.write("\t".join(CPM_HEADER) + "\n")
        for label, values in CPM_ROWS:
            f.write(label + "\t" + "\t".join(str(v) for v in values) + "\n")

    with (directory / "brainvar_meta_data.txt").open("w") as f:
        f.write("Braincode\tAgeDays\tAge\tAgeUnits\tPeriod\tsex\tEpoch\ttissue\n")
        for row in META_ROWS:
            f.write("\t".join(row) + "\n")

    with (directory / "gene_to_gene_human.txt").open("w") as f:
        f.write("symbol\tname\thgnc_id\tentrez_id\tensembl_gene_id\n")
        for row in MAP_ROWS:
            f.write("\t".join(row) + "\n")


class LoaderTestCase(TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        write_dataset(self.data_dir)
        self.addCleanup(self._tmp.cleanup)

    def load(self, **kwargs):
        out = StringIO()
        call_command("load_brainvar", data_dir=str(self.data_dir), stdout=out, **kwargs)
        return out.getvalue()


class SampleLoadingTests(LoaderTestCase):
    def test_creates_one_sample_per_matrix_column(self):
        self.load()
        self.assertEqual(Sample.objects.count(), 3)

    def test_column_index_follows_the_matrix_header_not_the_metadata_order(self):
        """
        The metadata file lists HSB003 first, but it is the third column of the
        matrix. column_index must come from the header.
        """
        self.load()
        indexes = dict(Sample.objects.values_list("braincode", "column_index"))
        self.assertEqual(indexes, {"HSB001": 0, "HSB002": 1, "HSB003": 2})

    def test_metadata_fields_are_parsed(self):
        self.load()
        s = Sample.objects.get(braincode="HSB001")
        self.assertEqual(s.age_days, 43.0)
        self.assertEqual(s.age, 6.14)
        self.assertEqual(s.age_units, "PCW")
        self.assertEqual(s.period, 1)
        self.assertEqual(s.epoch, 0)
        self.assertEqual(s.sex, "Male")
        self.assertEqual(s.tissue, "cortex")

    def test_metadata_row_without_a_matrix_column_is_skipped(self):
        with (self.data_dir / "brainvar_meta_data.txt").open("a") as f:
            f.write("HSB999\t100\t14\tPCW\t2\tMale\t0\tcortex\n")
        output = self.load()
        self.assertEqual(Sample.objects.count(), 3)
        self.assertIn("HSB999", output)


class GeneLoadingTests(LoaderTestCase):
    def test_creates_one_gene_per_matrix_row(self):
        self.load()
        self.assertEqual(Gene.objects.count(), len(CPM_ROWS))

    def test_values_are_stored_in_matrix_column_order(self):
        self.load()
        self.assertEqual(Gene.objects.get(ensembl_id="ENSG00000000001").values,
                         [10.0, 20.0, 30.0])

    def test_each_value_belongs_to_the_right_donor(self):
        """End-to-end alignment: the matrix cell for HSB003 must be 30.0."""
        self.load()
        gene = Gene.objects.get(ensembl_id="ENSG00000000001")
        for braincode, expected in zip(CPM_HEADER, [10.0, 20.0, 30.0]):
            index = Sample.objects.get(braincode=braincode).column_index
            self.assertEqual(gene.values[index], expected)

    def test_symbol_comes_from_the_matrix_not_the_mapping(self):
        """CCC is the matrix's name; the mapping calls the same gene CCC_OLD_NAME."""
        self.load()
        self.assertEqual(Gene.objects.get(ensembl_id="ENSG00000000003").symbol, "CCC")

    def test_symbol_falls_back_to_the_mapping_when_the_matrix_has_none(self):
        self.load()
        self.assertEqual(Gene.objects.get(ensembl_id="ENSG00000000004").symbol, "DDD")

    def test_descriptions_are_filled_in_from_the_mapping(self):
        self.load()
        gene = Gene.objects.get(ensembl_id="ENSG00000000001")
        self.assertEqual(gene.name, "alpha gene")
        self.assertEqual(gene.hgnc_id, "HGNC:1")
        self.assertEqual(gene.entrez_id, "111")

    def test_gene_absent_from_the_mapping_still_loads(self):
        self.load()
        gene = Gene.objects.get(ensembl_id="ENSG00000000002")
        self.assertEqual(gene.name, "")

    def test_mean_log2_uses_the_original_pseudocount(self):
        self.load()
        gene = Gene.objects.get(ensembl_id="ENSG00000000001")
        expected = sum(math.log2(v + 1e-3) for v in [10.0, 20.0, 30.0]) / 3
        self.assertAlmostEqual(gene.mean_log2, expected, places=12)

    def test_is_expressed_flags_all_zero_genes(self):
        self.load()
        self.assertFalse(Gene.objects.get(ensembl_id="ENSG00000000002").is_expressed)
        self.assertTrue(Gene.objects.get(ensembl_id="ENSG00000000003").is_expressed)

    def test_row_with_the_wrong_number_of_values_is_rejected(self):
        with (self.data_dir / "brainVar.CPM-10042019.tsv").open("a") as f:
            f.write("ENSG00000000005|EEE\t1.0\t2.0\n")     # only two of three
        with self.assertRaises(CommandError):
            self.load()


class AliasLoadingTests(LoaderTestCase):
    def test_every_gene_is_reachable_by_its_ensembl_id(self):
        self.load()
        for ensembl_id, _ in [(r[0].split("|")[0], r[1]) for r in CPM_ROWS]:
            self.assertTrue(GeneAlias.objects.filter(alias=ensembl_id).exists())

    def test_matrix_symbols_are_registered(self):
        self.load()
        for alias in ["AAA", "BBB", "CCC"]:
            self.assertEqual(
                GeneAlias.objects.get(alias=alias).gene.symbol, alias
            )

    def test_mapping_only_names_are_registered_too(self):
        """CCC_OLD_NAME exists only in the mapping and must still resolve."""
        self.load()
        alias = GeneAlias.objects.get(alias="CCC_OLD_NAME")
        self.assertEqual(alias.gene.ensembl_id, "ENSG00000000003")
        self.assertEqual(alias.source, GeneAlias.Source.HGNC)

    def test_aliases_are_uppercased(self):
        self.load()
        self.assertFalse(GeneAlias.objects.filter(alias="aaa").exists())
        self.assertTrue(GeneAlias.objects.filter(alias="AAA").exists())

    def test_mapping_entries_absent_from_the_matrix_are_ignored(self):
        """GHOST maps to an Ensembl id with no data — nothing to plot."""
        self.load()
        self.assertFalse(GeneAlias.objects.filter(alias="GHOST").exists())

    def test_mapping_rows_without_an_ensembl_id_are_ignored(self):
        self.load()
        self.assertFalse(GeneAlias.objects.filter(alias="NOID").exists())

    def test_matrix_wins_when_the_two_sources_claim_the_same_name(self):
        """
        SHARED labels ENSG00000000005 in the matrix, but the mapping assigns it
        to ENSG00000000001. The matrix must win: it is the only source whose
        genes can actually be plotted. This is the rule that makes ADORA3 and
        the other 294 build-mismatch genes resolve to data rather than error.
        """
        self.load()
        alias = GeneAlias.objects.get(alias="SHARED")
        self.assertEqual(alias.gene.ensembl_id, "ENSG00000000005")
        self.assertEqual(alias.source, GeneAlias.Source.CPM)
        # The losing gene stays reachable by its Ensembl id.
        self.assertEqual(
            GeneAlias.objects.get(alias="ENSG00000000006").gene.ensembl_id,
            "ENSG00000000006",
        )


class ReRunTests(LoaderTestCase):
    def test_refuses_to_load_over_existing_data(self):
        self.load()
        with self.assertRaises(CommandError):
            self.load()

    def test_flush_allows_a_clean_reload(self):
        self.load()
        self.load(flush=True)
        self.assertEqual(Gene.objects.count(), len(CPM_ROWS))
        self.assertEqual(Sample.objects.count(), 3)

    def test_missing_source_file_is_reported_clearly(self):
        (self.data_dir / "brainvar_meta_data.txt").unlink()
        with self.assertRaises(CommandError):
            self.load()
