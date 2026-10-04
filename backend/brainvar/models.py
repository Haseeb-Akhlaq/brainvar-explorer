"""
Domain models for the BrainVar dataset.

The expression matrix is 60,156 genes x 176 samples. Rather than normalising
that into ~10.6M rows, each gene stores its 176 values in a Postgres array
ordered by Sample.column_index, so plotting a gene is two indexed lookups.
"""

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Sample(models.Model):
    """One brain donor. 176 rows; supplies the x-axis of every trajectory."""

    class Sex(models.TextChoices):
        MALE = "Male", "Male"
        FEMALE = "Female", "Female"

    braincode = models.CharField(max_length=32, unique=True, db_index=True)

    # Days post-conception, so birth falls at ~280. This is what gets plotted.
    age_days = models.FloatField(
        help_text="Age in days from conception; birth is ~280.",
        validators=[MinValueValidator(0.0)],
    )
    # The same age as reported by the study, for display only.
    age = models.FloatField(help_text="Age in age_units, as reported.")
    age_units = models.CharField(max_length=8, help_text="PCW or Years.")

    period = models.PositiveSmallIntegerField(
        help_text="Developmental period, 1-12.",
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    epoch = models.PositiveSmallIntegerField(help_text="Broad developmental stage, 0-3.")
    sex = models.CharField(max_length=6, choices=Sex.choices)
    tissue = models.CharField(max_length=32, default="cortex")

    # Position of this sample in Gene.values. The array is positional, so this
    # is the contract that keeps expression aligned to metadata.
    column_index = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        db_table = "brainvar_sample"
        ordering = ["age_days"]
        indexes = [models.Index(fields=["age_days"])]

    def __str__(self) -> str:
        return f"{self.braincode} ({self.age:g} {self.age_units})"


class Gene(models.Model):
    """
    One gene, with its expression across all 176 samples.

    `values` is a positional array aligned to Sample.column_index — element i
    is the CPM for the sample whose column_index is i.
    """

    ensembl_id = models.CharField(max_length=20, unique=True, db_index=True)
    symbol = models.CharField(max_length=64, db_index=True)

    # From the HGNC mapping; absent for ~9% of genes, which carry a CPM symbol
    # but no HGNC record.
    name = models.TextField(blank=True)
    hgnc_id = models.CharField(max_length=20, blank=True)
    entrez_id = models.CharField(max_length=20, blank=True)

    values = ArrayField(
        models.FloatField(),
        size=None,  # enforced against the Sample count at load time
        help_text="CPM per sample, ordered by Sample.column_index.",
    )

    # Precomputed at load time: mean of log2(CPM + 1e-3), matching the
    # transform the plot applies. Used to rank search results.
    mean_log2 = models.FloatField(db_index=True)
    # False when the gene is zero in every sample (~9% of the matrix), so the
    # API can say "not expressed in cortex" instead of drawing a flat line.
    is_expressed = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "brainvar_gene"
        ordering = ["symbol"]
        indexes = [models.Index(fields=["symbol", "ensembl_id"])]

    def __str__(self) -> str:
        return f"{self.symbol} ({self.ensembl_id})"


class GeneAlias(models.Model):
    """
    Every name that should resolve to a gene: the CPM file's own symbols, the
    HGNC symbols, and Ensembl ids.

    The two ID sources disagree for 295 named genes because they come from
    different Ensembl builds. Resolving through this table always lands on the
    gene that exists in the matrix, which is the only one that can be plotted.
    """

    class Source(models.TextChoices):
        CPM = "cpm", "CPM matrix"
        HGNC = "hgnc", "HGNC mapping"
        ENSEMBL = "ensembl", "Ensembl id"

    # Stored uppercase; lookups uppercase the query to match.
    alias = models.CharField(max_length=64, unique=True, db_index=True)
    source = models.CharField(max_length=10, choices=Source.choices)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE, related_name="aliases")

    class Meta:
        db_table = "brainvar_gene_alias"
        verbose_name_plural = "gene aliases"
        indexes = [models.Index(fields=["alias"])]

    def __str__(self) -> str:
        return f"{self.alias} -> {self.gene.ensembl_id}"
