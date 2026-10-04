"""
Load the BrainVar dataset from the three raw files into the database.

    python manage.py load_brainvar

The work happens in five steps, in this order:

    1. Read the CPM header          -> which donor sits in which column
    2. Load the sample metadata     -> Sample rows (176)
    3. Load the gene name mapping   -> descriptions from HGNC
    4. Stream the CPM matrix        -> Gene rows (60,156), values + summaries
    5. Build the alias table        -> every name that should find a gene

Steps 1 and 2 must run before 4, because a gene's `values` array is positional
and has to line up with Sample.column_index.
"""

import math
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from brainvar.models import Gene, GeneAlias, Sample

# Added to every CPM value before taking log2, because log2(0) is undefined.
# Matches the original script, so our numbers match its plots.
MIN_CPM = 1e-3

# How many Gene rows to send to Postgres at a time. Large enough to be fast,
# small enough that we never hold the whole 10.6M-value matrix in memory.
BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Load BrainVar samples, genes and aliases from the raw data files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            default=str(settings.BRAINVAR_DATA_DIR),
            help="Directory holding the three source files.",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing rows first. Required to re-run.",
        )

    def handle(self, *args, **options):
        data_dir = Path(options["data_dir"])

        cpm_file = data_dir / "brainVar.CPM-10042019.tsv"
        meta_file = data_dir / "brainvar_meta_data.txt"
        map_file = data_dir / "gene_to_gene_human.txt"

        for path in (cpm_file, meta_file, map_file):
            if not path.exists():
                raise CommandError(f"Missing source file: {path}")

        if options["flush"]:
            self._flush()
        elif Gene.objects.exists() or Sample.objects.exists():
            raise CommandError("Tables already contain data. Re-run with --flush.")

        with transaction.atomic():
            column_of = self.step_1_read_cpm_header(cpm_file)
            self.step_2_load_samples(meta_file, column_of)
            gene_info = self.step_3_load_gene_map(map_file)
            self.step_4_load_genes(cpm_file, gene_info, n_samples=len(column_of))
            self.step_5_build_aliases(gene_info)

        self.stdout.write(self.style.SUCCESS("\nDone."))
        self.stdout.write(
            f"  {Sample.objects.count():>7,} samples\n"
            f"  {Gene.objects.count():>7,} genes\n"
            f"  {GeneAlias.objects.count():>7,} aliases"
        )

    # -- helpers ------------------------------------------------------------

    def _flush(self):
        """Delete everything. GeneAlias goes first — it points at Gene."""
        GeneAlias.objects.all().delete()
        Gene.objects.all().delete()
        Sample.objects.all().delete()
        self.stdout.write("Existing rows deleted.")

    # -- step 1 -------------------------------------------------------------

    def step_1_read_cpm_header(self, cpm_file: Path) -> dict[str, int]:
        """
        Read only the first line of the matrix: the donor codes, in order.

            HSB100  HSB105  HSB107  ...

        Returns {"HSB100": 0, "HSB105": 1, ...} — each donor's column number.
        That number is the position their value occupies in every gene's array,
        so it is the link between the matrix and the metadata.
        """
        with cpm_file.open() as f:
            braincodes = f.readline().rstrip("\n").split("\t")

        column_of = {code: i for i, code in enumerate(braincodes)}
        self.stdout.write(f"Step 1: {len(column_of)} samples in the matrix header.")
        return column_of

    # -- step 2 -------------------------------------------------------------

    def step_2_load_samples(self, meta_file: Path, column_of: dict[str, int]):
        """
        Create one Sample per donor, from brainvar_meta_data.txt.

            Braincode  AgeDays  Age   AgeUnits  Period  sex   Epoch  tissue
            HSB272     43       6.14  PCW       1       Male  0      cortex

        Each row is matched to its column number from step 1. A donor in the
        metadata but not in the matrix has no data to plot, so it is skipped.
        """
        samples, skipped = [], []

        with meta_file.open() as f:
            header = f.readline().rstrip("\n").split("\t")
            for line in f:
                if not line.strip():
                    continue
                row = dict(zip(header, line.rstrip("\n").split("\t")))
                braincode = row["Braincode"]

                if braincode not in column_of:
                    skipped.append(braincode)
                    continue

                samples.append(
                    Sample(
                        braincode=braincode,
                        age_days=float(row["AgeDays"]),
                        age=float(row["Age"]),
                        age_units=row["AgeUnits"],
                        period=int(row["Period"]),
                        epoch=int(row["Epoch"]),
                        sex=row["sex"],
                        tissue=row["tissue"],
                        column_index=column_of[braincode],
                    )
                )

        Sample.objects.bulk_create(samples)
        self.stdout.write(f"Step 2: {len(samples)} samples created.")
        if skipped:
            self.stdout.write(self.style.WARNING(f"        skipped (no matrix column): {skipped}"))

    # -- step 3 -------------------------------------------------------------

    def step_3_load_gene_map(self, map_file: Path) -> dict[str, dict]:
        """
        Read gene_to_gene_human.txt into a lookup keyed by Ensembl id.

            symbol  name                     hgnc_id  entrez_id  ensembl_gene_id
            A1BG    alpha-1-B glycoprotein   HGNC:5   1          ENSG00000121410

        This file only supplies descriptions and cross-references. The genes
        themselves come from the matrix in step 4, because that is the only
        source that actually has data to plot.

        Returns {"ENSG00000121410": {"symbol": "A1BG", "name": ..., ...}, ...}
        """
        info: dict[str, dict] = {}

        with map_file.open() as f:
            header = f.readline().rstrip("\n").split("\t")
            for line in f:
                row = dict(zip(header, line.rstrip("\n").split("\t")))
                ensembl = row.get("ensembl_gene_id", "")

                # "." is this file's way of writing "no value".
                if not ensembl or ensembl == ".":
                    continue
                if ensembl in info:  # keep the first entry for an id
                    continue

                info[ensembl] = {
                    "symbol": _clean(row.get("symbol")),
                    "name": _clean(row.get("name")),
                    "hgnc_id": _clean(row.get("hgnc_id")),
                    "entrez_id": _clean(row.get("entrez_id")),
                }

        self.stdout.write(f"Step 3: {len(info):,} genes described in the mapping file.")
        return info

    # -- step 4 -------------------------------------------------------------

    def step_4_load_genes(self, cpm_file: Path, gene_info: dict[str, dict], n_samples: int):
        """
        Stream the matrix and create one Gene per row.

            ENSG00000000003|TSPAN6   12.35   4.31   8.24   ...

        The row label carries both ids, split on "|". Descriptions are filled
        in from step 3 where available. Two summaries are computed here so the
        API never has to touch the array to answer "how expressed is this?":

            mean_log2     average of log2(value + 0.001), the plotted transform
            is_expressed  False when the gene is zero in every sample

        Rows are written in batches so the whole matrix is never in memory.
        """
        batch: list[Gene] = []
        created = 0

        with cpm_file.open() as f:
            f.readline()  # header, already handled in step 1

            for line in f:
                if not line.strip():
                    continue

                label, _, rest = line.rstrip("\n").partition("\t")
                ensembl_id, _, symbol = label.partition("|")

                values = [float(v) for v in rest.split("\t")]
                if len(values) != n_samples:
                    raise CommandError(
                        f"{ensembl_id}: expected {n_samples} values, found {len(values)}"
                    )

                logs = [math.log2(v + MIN_CPM) for v in values]
                described = gene_info.get(ensembl_id, {})

                batch.append(
                    Gene(
                        ensembl_id=ensembl_id,
                        # Prefer the matrix's own symbol; fall back to HGNC's.
                        symbol=symbol or described.get("symbol", "") or ensembl_id,
                        name=described.get("name", ""),
                        hgnc_id=described.get("hgnc_id", ""),
                        entrez_id=described.get("entrez_id", ""),
                        values=values,
                        mean_log2=sum(logs) / len(logs),
                        is_expressed=any(v > 0 for v in values),
                    )
                )

                if len(batch) >= BATCH_SIZE:
                    Gene.objects.bulk_create(batch)
                    created += len(batch)
                    batch = []
                    self.stdout.write(f"\r  ...{created:,} genes", ending="")

        if batch:
            Gene.objects.bulk_create(batch)
            created += len(batch)

        self.stdout.write(f"\rStep 4: {created:,} genes created.          ")

    # -- step 5 -------------------------------------------------------------

    def step_5_build_aliases(self, gene_info: dict[str, dict]):
        """
        Build the name -> gene lookup the API searches.

        Three kinds of name are registered, in this order of priority:

            1. the Ensembl id             ENSG00000136531
            2. the matrix's own symbol    SCN2A
            3. the HGNC symbol            (only when it adds something new)

        Order matters because an alias must be unique. The matrix wins ties,
        since it is the only source whose genes can actually be plotted — the
        two files disagree on 295 genes, having been built against different
        Ensembl releases.

        Symbols are stored uppercase so lookups are case-insensitive.
        """
        # id -> primary key, so aliases can be built without re-querying.
        pk_of = dict(Gene.objects.values_list("ensembl_id", "pk"))
        symbol_of = dict(Gene.objects.values_list("ensembl_id", "symbol"))

        taken: set[str] = set()
        aliases: list[GeneAlias] = []

        def add(name: str, source: str, ensembl_id: str):
            """Register one name, unless something already claimed it."""
            key = (name or "").strip().upper()
            if not key or key in taken:
                return
            taken.add(key)
            aliases.append(GeneAlias(alias=key, source=source, gene_id=pk_of[ensembl_id]))

        # 1 + 2: everything the matrix knows about itself.
        for ensembl_id, symbol in symbol_of.items():
            add(ensembl_id, GeneAlias.Source.ENSEMBL, ensembl_id)
            add(symbol, GeneAlias.Source.CPM, ensembl_id)

        # 3: HGNC names, but only for genes the matrix actually contains.
        for ensembl_id, described in gene_info.items():
            if ensembl_id in pk_of:
                add(described["symbol"], GeneAlias.Source.HGNC, ensembl_id)

        GeneAlias.objects.bulk_create(aliases, batch_size=BATCH_SIZE)
        self.stdout.write(f"Step 5: {len(aliases):,} aliases created.")


def _clean(value: str | None) -> str:
    """This dataset writes missing values as '.' — treat that as empty."""
    value = (value or "").strip()
    return "" if value == "." else value
