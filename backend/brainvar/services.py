"""
Business logic for gene lookup and expression trajectories.

Views stay thin: they parse the request and serialise the result. Everything
that knows about the data lives here, so it can be tested without HTTP and
reused by future endpoints (bulk export, comparisons, the LOESS fit).
"""

import math
from dataclasses import dataclass

import numpy as np
from django.db.models import QuerySet

from .loess import Loess
from .models import Gene, GeneAlias, Sample

# Matches the original script: log2(0) is undefined, so every value is nudged.
MIN_CPM = 1e-3

# How many points to evaluate the fitted curve at. The original script draws it
# through the 176 donor positions, which zig-zags where samples cluster; an even
# grid renders smoothly and costs nothing extra.
CURVE_RESOLUTION = 200

# Fields needed to describe a gene in a list. Deliberately excludes `values`,
# which is 176 floats per row and would dominate a search response.
LIST_FIELDS = ("id", "ensembl_id", "symbol", "name", "mean_log2", "is_expressed")


class GeneNotFound(Exception):
    """Raised when a query matches no gene. Carries near-miss suggestions."""

    def __init__(self, query: str, suggestions: list[str]):
        self.query = query
        self.suggestions = suggestions
        super().__init__(f"No gene found matching '{query}'.")


@dataclass(frozen=True)
class TrajectoryPoint:
    """One donor's expression for one gene — a single dot on the plot."""

    braincode: str
    age_days: float
    age: float
    age_units: str
    period: int
    sex: str
    cpm: float
    log2_cpm: float


def search_genes(query: str, limit: int = 10) -> list[Gene]:
    """
    Find genes whose name starts with `query`, best matches first.

    Searches the alias table, so a gene is reachable by its symbol, its
    Ensembl id, or an HGNC name the matrix does not carry. Ranking is:

        1. exact match on any alias
        2. alias starting with the query, alphabetically

    Returns Gene objects with `values` deferred — callers that need the
    expression array should fetch the gene directly.
    """
    q = (query or "").strip().upper()
    if not q:
        return []

    exact = list(
        Gene.objects.filter(aliases__alias=q).only(*LIST_FIELDS).distinct()[: limit]
    )
    if len(exact) >= limit:
        return exact

    seen = {g.pk for g in exact}
    prefix = (
        Gene.objects.filter(aliases__alias__startswith=q)
        .exclude(pk__in=seen)
        .only(*LIST_FIELDS)
        .distinct()
        .order_by("symbol")[: limit - len(exact)]
    )
    return exact + list(prefix)


def resolve_gene(query: str) -> tuple[Gene, str]:
    """
    Turn whatever the user typed into exactly one gene.

    Returns (gene, matched_alias). Raises GeneNotFound with suggestions when
    nothing matches, so the API can answer "did you mean ...?" rather than a
    bare 404.
    """
    q = (query or "").strip().upper()

    alias = GeneAlias.objects.select_related("gene").filter(alias=q).first()
    if alias:
        return alias.gene, alias.alias

    suggestions = [g.symbol for g in search_genes(q, limit=5)]
    raise GeneNotFound(query, suggestions)


def build_trajectory(gene: Gene, samples: QuerySet[Sample] | None = None) -> list[TrajectoryPoint]:
    """
    Join a gene's expression array to the donors, ordered for plotting.

    `gene.values` is positional: element i belongs to the sample whose
    column_index is i. Output is sorted by age, which is the x-axis.
    """
    if samples is None:
        samples = Sample.objects.all()

    points = [
        TrajectoryPoint(
            braincode=s.braincode,
            age_days=s.age_days,
            age=s.age,
            age_units=s.age_units,
            period=s.period,
            sex=s.sex,
            cpm=gene.values[s.column_index],
            log2_cpm=math.log2(gene.values[s.column_index] + MIN_CPM),
        )
        for s in samples
    ]
    points.sort(key=lambda p: p.age_days)
    return points


@dataclass(frozen=True)
class Curve:
    """The LOESS trend line and its 95% confidence band, ready to plot."""

    age_days: list[float]
    log2_age_days: list[float]
    fitted: list[float]
    lower: list[float]
    upper: list[float]


def fit_curve(points: list[TrajectoryPoint], resolution: int = CURVE_RESOLUTION) -> Curve:
    """
    Fit the LOESS trend through a gene's trajectory.

    Both axes are log2-transformed exactly as the original script does — x is
    log2(age in days), y is log2(CPM + 1e-3) — so the fit is comparable with
    the PDFs the script produces.

    Returned x values are given in both spaces: log2 for plotting against the
    script's axis, and days for labelling.
    """
    x = np.array([math.log2(p.age_days) for p in points])
    y = np.array([p.log2_cpm for p in points])

    model = Loess(x, y)
    grid = np.linspace(x.min(), x.max(), resolution)
    band = model.confidence(grid)

    return Curve(
        age_days=(2.0**grid).tolist(),
        log2_age_days=grid.tolist(),
        fitted=band.fitted.tolist(),
        lower=band.lower.tolist(),
        upper=band.upper.tolist(),
    )
