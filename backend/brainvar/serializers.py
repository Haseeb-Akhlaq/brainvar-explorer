"""Serializers for the BrainVar API."""

from rest_framework import serializers

from .models import Gene


class GeneSummarySerializer(serializers.ModelSerializer):
    """A gene without its expression array — for search results."""

    class Meta:
        model = Gene
        fields = ("ensembl_id", "symbol", "name", "mean_log2", "is_expressed")


class GeneDetailSerializer(serializers.ModelSerializer):
    """A gene's identity and cross-references. Expression is sent separately."""

    class Meta:
        model = Gene
        fields = (
            "ensembl_id",
            "symbol",
            "name",
            "hgnc_id",
            "entrez_id",
            "mean_log2",
            "is_expressed",
        )


class TrajectoryPointSerializer(serializers.Serializer):
    """One donor's expression for one gene — a dot on the plot."""

    braincode = serializers.CharField()
    age_days = serializers.FloatField()
    age = serializers.FloatField()
    age_units = serializers.CharField()
    period = serializers.IntegerField()
    sex = serializers.CharField()
    cpm = serializers.FloatField()
    log2_cpm = serializers.FloatField()


class CurveSerializer(serializers.Serializer):
    """The fitted LOESS trend and its confidence band."""

    age_days = serializers.ListField(child=serializers.FloatField())
    log2_age_days = serializers.ListField(child=serializers.FloatField())
    fitted = serializers.ListField(child=serializers.FloatField())
    lower = serializers.ListField(child=serializers.FloatField())
    upper = serializers.ListField(child=serializers.FloatField())


# --- response envelopes -----------------------------------------------------
# These exist for the OpenAPI schema: the views build plain dicts, and without
# a declared shape drf-spectacular can only report "object".


class GeneSearchResponseSerializer(serializers.Serializer):
    """The payload of GET /api/genes/."""

    query = serializers.CharField(help_text="The query as received.")
    count = serializers.IntegerField(help_text="Number of results returned, not total matches.")
    results = GeneSummarySerializer(many=True)


class GeneDetailResponseSerializer(serializers.Serializer):
    """The payload of GET /api/genes/{query}/."""

    gene = GeneDetailSerializer()
    resolved_from = serializers.CharField(
        help_text="The alias the query matched — a symbol or an Ensembl id.",
    )
    n_samples = serializers.IntegerField(help_text="Always 176 for this dataset.")
    points = TrajectoryPointSerializer(many=True, help_text="One per donor, sorted by age.")
    curve = CurveSerializer(allow_null=True, help_text="Null when curve=false was passed.")


class GeneNotFoundSerializer(serializers.Serializer):
    """The 404 body, which carries near-miss suggestions."""

    detail = serializers.CharField()
    query = serializers.CharField()
    suggestions = serializers.ListField(
        child=serializers.CharField(),
        help_text="Symbols that start with the query, if any.",
    )


class ErrorSerializer(serializers.Serializer):
    """A 400 caused by a malformed parameter."""

    detail = serializers.CharField()


class DatasetStatsSerializer(serializers.Serializer):
    """The payload of GET /api/stats/."""

    genes = serializers.IntegerField()
    genes_expressed = serializers.IntegerField(
        help_text="Genes with a non-zero value in at least one sample.",
    )
    samples = serializers.IntegerField()
    age_days_min = serializers.FloatField(allow_null=True, help_text="Days post-conception.")
    age_days_max = serializers.FloatField(allow_null=True)


class HealthSerializer(serializers.Serializer):
    """The payload of GET /api/health/."""

    status = serializers.CharField()
    service = serializers.CharField()
    database = serializers.CharField(help_text='"ok", or the error class if unreachable.')
