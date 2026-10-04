"""
Helpers for building BrainVar test data.

The real dataset is 98 MB, so tests build a small matrix with the same shape
and invariants: samples carry contiguous column_index values, and each gene's
`values` array is positional against them.
"""

import math

from brainvar.models import Gene, GeneAlias, Sample

MIN_CPM = 1e-3


def make_samples(ages=(43.0, 140.0, 280.0, 700.0, 3000.0), sexes=None) -> list[Sample]:
    """
    Create one Sample per age, in ascending order, with column_index 0..n-1.

    Ages are days post-conception, so 280 is birth.
    """
    sexes = sexes or ["Female" if i % 2 else "Male" for i in range(len(ages))]
    samples = []
    for i, (age_days, sex) in enumerate(zip(ages, sexes)):
        prenatal = age_days < 280
        samples.append(
            Sample.objects.create(
                braincode=f"HSB{900 + i}",
                age_days=age_days,
                age=age_days / 7 if prenatal else age_days / 365,
                age_units="PCW" if prenatal else "Years",
                period=min(12, i + 1),
                epoch=0 if prenatal else 1,
                sex=sex,
                tissue="cortex",
                column_index=i,
            )
        )
    return samples


def make_gene(symbol, ensembl_id, values, *, name="", aliases=True, **kwargs) -> Gene:
    """Create a Gene with derived summaries computed the way the loader does."""
    logs = [math.log2(v + MIN_CPM) for v in values]
    gene = Gene.objects.create(
        ensembl_id=ensembl_id,
        symbol=symbol,
        name=name,
        values=list(values),
        mean_log2=sum(logs) / len(logs),
        is_expressed=any(v > 0 for v in values),
        **kwargs,
    )
    if aliases:
        GeneAlias.objects.create(alias=ensembl_id.upper(), source=GeneAlias.Source.ENSEMBL, gene=gene)
        GeneAlias.objects.create(alias=symbol.upper(), source=GeneAlias.Source.CPM, gene=gene)
    return gene
