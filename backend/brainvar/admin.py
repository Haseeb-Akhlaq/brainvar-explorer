"""
Admin for the BrainVar dataset.

These tables are populated by the loader, not by hand, so the admin is tuned
for inspection: expression arrays are summarised rather than rendered, and the
60k-row Gene table is reached by search rather than by paging.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Gene, GeneAlias, Sample


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("braincode", "display_age", "age_days", "period", "epoch", "sex", "column_index")
    list_filter = ("sex", "age_units", "epoch", "period", "tissue")
    search_fields = ("braincode",)
    ordering = ("age_days",)
    list_per_page = 50

    @admin.display(description="age", ordering="age_days")
    def display_age(self, obj: Sample) -> str:
        return f"{obj.age:g} {obj.age_units}"


class GeneAliasInline(admin.TabularInline):
    model = GeneAlias
    extra = 0
    fields = ("alias", "source")
    # Aliases are derived from the source files; editing them here would drift
    # from the loader's output.
    readonly_fields = ("alias", "source")
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Gene)
class GeneAdmin(admin.ModelAdmin):
    list_display = ("symbol", "ensembl_id", "short_name", "mean_log2", "is_expressed")
    list_filter = ("is_expressed",)
    search_fields = ("symbol", "ensembl_id", "name")
    ordering = ("symbol",)
    list_per_page = 50
    # 60k rows: skip the unfiltered COUNT(*) that the paginator would otherwise
    # run on every search.
    show_full_result_count = False
    inlines = [GeneAliasInline]

    # `values` is 176 floats — summarised below rather than shown as a field.
    exclude = ("values",)
    readonly_fields = ("expression_summary",)

    fieldsets = (
        (None, {"fields": ("ensembl_id", "symbol", "name")}),
        ("Cross-references", {"fields": ("hgnc_id", "entrez_id")}),
        ("Expression", {"fields": ("mean_log2", "is_expressed", "expression_summary")}),
    )

    @admin.display(description="name")
    def short_name(self, obj: Gene) -> str:
        return (obj.name[:60] + "...") if len(obj.name) > 60 else obj.name

    @admin.display(description="values")
    def expression_summary(self, obj: Gene) -> str:
        vals = obj.values or []
        if not vals:
            return "—"
        head = ", ".join(f"{v:.4g}" for v in vals[:8])
        # Numbers are formatted before the call: format_html escapes each
        # argument to SafeString first, which cannot take a numeric format spec.
        return format_html(
            "<code>{}</code><br>{} samples &middot; min {} &middot; max {} &middot; {} zero",
            f"[{head}, ...]",
            len(vals),
            f"{min(vals):.4g}",
            f"{max(vals):.4g}",
            sum(1 for v in vals if v == 0),
        )


@admin.register(GeneAlias)
class GeneAliasAdmin(admin.ModelAdmin):
    list_display = ("alias", "source", "gene")
    list_filter = ("source",)
    search_fields = ("alias",)
    ordering = ("alias",)
    list_per_page = 50
    show_full_result_count = False
    # Avoids rendering a 60k-option <select> on the change form.
    autocomplete_fields = ("gene",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("gene")
