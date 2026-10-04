"""
Read-only API for gene lookup and expression trajectories.

Views parse the request and serialise the result; the data logic lives in
services.py so it can be tested without HTTP.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from django.db.models import Max, Min
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema

from activity.models import AccessEvent
from activity.services import record

from . import services
from .models import Gene, Sample
from .serializers import (
    CurveSerializer,
    DatasetStatsSerializer,
    ErrorSerializer,
    GeneDetailResponseSerializer,
    GeneDetailSerializer,
    GeneNotFoundSerializer,
    GeneSearchResponseSerializer,
    GeneSummarySerializer,
    TrajectoryPointSerializer,
)

# Keeps a stray ?limit=100000 from turning search into a full table scan.
MAX_SEARCH_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 10


@extend_schema(
    tags=["genes"],
    # Explicit: both gene endpoints would otherwise generate the same
    # operationId, which clients use to name their generated methods.
    operation_id="searchGenes",
    summary="Search genes",
    description=(
        "Autocomplete over gene symbols, Ensembl ids and HGNC names.\n\n"
        "Exact matches rank first, then prefix matches alphabetically. An "
        "empty query returns an empty list rather than the whole table.\n\n"
        "Results deliberately omit the expression array — ten results would "
        "otherwise carry 1,760 floats."
    ),
    parameters=[
        OpenApiParameter(
            "q",
            OpenApiTypes.STR,
            description="Symbol, Ensembl id or partial name. Case-insensitive.",
            examples=[
                OpenApiExample("Partial symbol", value="SCN"),
                OpenApiExample("Exact symbol", value="SCN2A"),
                OpenApiExample("Ensembl id", value="ENSG00000136531"),
            ],
        ),
        OpenApiParameter(
            "limit",
            OpenApiTypes.INT,
            description=f"Maximum results. Defaults to {DEFAULT_SEARCH_LIMIT}, capped at {MAX_SEARCH_LIMIT}.",
        ),
    ],
    responses={200: GeneSearchResponseSerializer, 400: ErrorSerializer},
    examples=[
        OpenApiExample(
            "Prefix search",
            value={
                "query": "SCN",
                "count": 2,
                "results": [
                    {
                        "ensembl_id": "ENSG00000144285",
                        "symbol": "SCN1A",
                        "name": "sodium voltage-gated channel alpha subunit 1",
                        "mean_log2": 6.355522097669114,
                        "is_expressed": True,
                    },
                    {
                        "ensembl_id": "ENSG00000136531",
                        "symbol": "SCN2A",
                        "name": "sodium voltage-gated channel alpha subunit 2",
                        "mean_log2": 8.894744217436363,
                        "is_expressed": True,
                    },
                ],
            },
            response_only=True,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gene_search(request):
    """Autocomplete over gene symbols, Ensembl ids and HGNC names."""
    query = request.query_params.get("q", "")

    try:
        limit = int(request.query_params.get("limit", DEFAULT_SEARCH_LIMIT))
    except ValueError:
        return Response(
            {"detail": "limit must be an integer."}, status=status.HTTP_400_BAD_REQUEST
        )
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))

    genes = services.search_genes(query, limit=limit)
    return Response(
        {
            "query": query,
            "count": len(genes),
            "results": GeneSummarySerializer(genes, many=True).data,
        }
    )


@extend_schema(
    tags=["genes"],
    operation_id="getGeneTrajectory",
    summary="Gene expression trajectory",
    description=(
        "The gene, its expression across all 176 donors sorted by age, and "
        "the LOESS trend with a 95% confidence band — everything needed to "
        "draw the plot.\n\n"
        "Accepts a symbol or an Ensembl id, case-insensitively. Names resolve "
        "through an alias table built from both id sources, so genes the two "
        "files disagree about still resolve to the data that exists.\n\n"
        "The curve is evaluated at 200 evenly spaced points across the age "
        "range rather than at the donor positions, which cluster in the "
        "second trimester."
    ),
    parameters=[
        OpenApiParameter(
            "query",
            OpenApiTypes.STR,
            OpenApiParameter.PATH,
            description="Gene symbol or Ensembl id.",
            examples=[
                OpenApiExample("Symbol", value="SCN2A"),
                OpenApiExample("Lowercase", value="scn2a"),
                OpenApiExample("Ensembl id", value="ENSG00000136531"),
                OpenApiExample("Sex-linked, a good correctness check", value="XIST"),
            ],
        ),
        OpenApiParameter(
            "curve",
            OpenApiTypes.BOOL,
            description="Set false to skip the LOESS fit and return points only. Defaults to true.",
        ),
    ],
    responses={200: GeneDetailResponseSerializer, 404: GeneNotFoundSerializer},
    examples=[
        OpenApiExample(
            "SCN2A (arrays truncated for readability)",
            value={
                "gene": {
                    "ensembl_id": "ENSG00000136531",
                    "symbol": "SCN2A",
                    "name": "sodium voltage-gated channel alpha subunit 2",
                    "hgnc_id": "HGNC:10588",
                    "entrez_id": "6326",
                    "mean_log2": 8.894744217436363,
                    "is_expressed": True,
                },
                "resolved_from": "SCN2A",
                "n_samples": 176,
                "points": [
                    {
                        "braincode": "HSB272",
                        "age_days": 43.0,
                        "age": 6.14,
                        "age_units": "PCW",
                        "period": 1,
                        "sex": "Male",
                        "cpm": 559.74333491626,
                        "log2_cpm": 9.128624211638526,
                    }
                ],
                "curve": {
                    "age_days": [43.0, 7566.002],
                    "log2_age_days": [5.426264754702098, 12.885], 
                    "fitted": [8.155, 9.754],
                    "lower": [7.594, 9.506],
                    "upper": [8.716, 10.001],
                },
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "Unknown gene, with suggestions",
            value={
                "detail": "No gene found matching 'SCN2'.",
                "query": "SCN2",
                "suggestions": ["SCN2A", "SCN2B"],
            },
            response_only=True,
            status_codes=["404"],
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gene_detail(request, query: str):
    """Expression across all donors, with the fitted LOESS trend."""
    try:
        gene, matched = services.resolve_gene(query)
    except services.GeneNotFound as exc:
        return Response(
            {"detail": str(exc), "query": exc.query, "suggestions": exc.suggestions},
            status=status.HTTP_404_NOT_FOUND,
        )

    points = services.build_trajectory(gene)

    payload = {
        "gene": GeneDetailSerializer(gene).data,
        "resolved_from": matched,
        "n_samples": len(points),
        "points": TrajectoryPointSerializer(points, many=True).data,
        "curve": None,
    }

    if request.query_params.get("curve", "true").lower() != "false":
        payload["curve"] = CurveSerializer(services.fit_curve(points)).data

    # Recorded on the resolved symbol, not the raw query, so a lookup by
    # Ensembl id and one by symbol land on the same row. Repeats inside the
    # dedupe window collapse — see ACTIVITY_GENE_VIEW_DEDUPE_SECONDS.
    record(request, AccessEvent.Action.GENE_VIEW, target=gene.symbol or gene.ensembl)

    return Response(payload)


@extend_schema(
    tags=["dataset"],
    operation_id="getDatasetStats",
    summary="Dataset statistics",
    description=(
        "Counts and the age range of the loaded dataset, so a client can "
        "describe what it is showing without downloading the gene index."
    ),
    responses={200: DatasetStatsSerializer},
    examples=[
        OpenApiExample(
            "Loaded dataset",
            value={
                "genes": 60155,
                "genes_expressed": 47475,
                "samples": 176,
                "age_days_min": 43.0,
                "age_days_max": 7566.002,
            },
            response_only=True,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dataset_stats(request):
    """Counts and the age range of the loaded dataset."""
    ages = Sample.objects.aggregate(min=Min("age_days"), max=Max("age_days"))
    return Response(
        {
            "genes": Gene.objects.count(),
            "genes_expressed": Gene.objects.filter(is_expressed=True).count(),
            "samples": Sample.objects.count(),
            "age_days_min": ages["min"],
            "age_days_max": ages["max"],
        }
    )
