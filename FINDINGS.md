# Findings

*BrainVar Trajectory Explorer*

Notes made while porting `per_gene_cpm_brainvar.py`, a legacy analysis script, to
a web application.
Every number below was measured, and the commands to reproduce each one are
included.

---

## 1. The LOESS curve differs from the script's, and the script's is the approximation

**What was measured.** The original script was executed unmodified via `runpy`,
with `plt.plot` and `plt.fill_between` intercepted to capture the exact arrays it
passes to matplotlib. Those arrays were compared against the web API's response
for the same gene.

| gene | scatter x | scatter y | fitted curve | band lower | band upper |
|---|---|---|---|---|---|
| SCN2A | 1.8e-15 | 1.8e-15 | 0.176 | 0.217 | 0.146 |
| SYNGAP1 | 1.8e-15 | 8.9e-16 | 0.175 | 0.227 | 0.157 |
| XIST | 1.8e-15 | 1.8e-15 | **0.849** | 1.280 | 1.063 |
| MEF2C | 1.8e-15 | 1.8e-15 | 0.252 | 0.335 | 0.169 |

*(units: log2 CPM; max absolute difference across all 176 points)*

**The data points are identical** — 1.8e-15 is floating-point epsilon. Every
sample, both axes, all four genes.

**The curves differ**, by up to 0.85 log2 on XIST.

**Why.** `skmisc.loess` defaults to `surface="interpolate"`, which evaluates the
fit on a kd-tree and interpolates between vertices, and to
`statistics="approximate"` for the variance terms. The script uses those
defaults. The web app computes the exact local-regression solution.

Measured against skmisc's *own* exact mode (`surface="direct",
statistics="exact"`), the web app agrees to **1e-13**, while skmisc's default
deviates from its own exact answer by the amounts in the table. The divergence
appears where samples are sparse — clearest on XIST between 6 months and 6
years, which is where the kd-tree has fewest vertices to interpolate between.

**This is a judgement call, not a bug.** Either behaviour is defensible; the
app currently computes the exact fit. Matching the script exactly would mean
reproducing the interpolating surface.

```bash
# reproduce (backend must be running: docker compose -f docker-compose.local.yml up -d)
.venv/bin/python verification/capture_script.py SCN2A SYNGAP1 XIST MEF2C  # runs the original script via runpy
.venv/bin/python verification/compare_against_script.py                   # diffs it against the API
.venv/bin/python verification/overlay_plot.py                             # draws the overlay figure
```

---

## 2. The script cannot run on a clean machine

Three problems prevent `per_gene_cpm_brainvar.py` executing anywhere but the
machine it was written on:

1. **Paths are hardcoded to a home directory** — `~/gene_to_gene_human.txt.gz`,
   `~/brainVar.CPM-10042019.tsv`, `~/brainvar_meta_data.txt`.
2. **The gene map is opened with `gzip.open`**, but the file that accompanies it
   is uncompressed (`gene_to_gene_human.txt`), so the call raises
   `BadGzipFile`.
3. **Output goes to `~/Data/BrainVar2/Images_gene/`**, which does not exist and
   is never created, so the final `savefig` raises `FileNotFoundError`.

Also worth noting: `scikit-misc` publishes **no linux/aarch64 wheels** (checked
against PyPI for every release up to 0.5.2). It therefore cannot be installed in
a container on Apple Silicon without x86 emulation or a Fortran toolchain in the
image. This is why the LOESS fit was reimplemented on numpy.

---

## 3. Negative axis labels render as `?` in the output PDFs

The script sets `plt.rcParams['pdf.use14corefonts'] = True`. That selects the
PDF base-14 fonts, whose encoding lacks U+2212 (the Unicode minus matplotlib
uses for negative tick labels).

Every negative y-axis label in the generated PDFs is therefore a question mark.
It is visible on any gene with negative log2 values — XIST most obviously, where
the axis reads `?5` and `?10` instead of `-5` and `-10`.

```
$ pdftotext -layout gene_CPM_ENSG00000229807_XIST.pdf -
  10
  5
  0
  ?5
  ?10
```

Confirmed with two independent renderers (poppler and macOS `sips`), and
isolated to the setting:

```
use14corefonts=True   ->  ['0', '10', '5', '?10', '?5']
use14corefonts=False  ->  ['0', '10', '5', '−10', '−5']
```

The web app is unaffected, since it renders SVG rather than PDF.

---

## 4. 295 named genes raise an error although their data is present

The script resolves a symbol through `gene_to_gene_human.txt` only, then looks
up the resulting Ensembl id in the CPM matrix. The two files were built against
different Ensembl releases, so for 295 genes the mapping returns an id that is
not in the matrix — and the script raises, even though the gene's row is there
under a different id.

| symbol | id in the CPM matrix | id the mapping returns | gene |
|---|---|---|---|
| ADORA3 | ENSG00000121933 | ENSG00000282608 | adenosine A3 receptor |
| EXOC3L2 | ENSG00000130201 | ENSG00000283632 | exocyst complex component 3 like 2 |
| DUX4L1–L8 | ENSG00000258389 … | ENSG00000280757 … | double homeobox 4 like family |

```
$ python data/per_gene_cpm_brainvar.py ADORA3
ValueError: Ensembl ID ENSG00000282608 not found in CPM file
```

**How the web app handles it.** Names are resolved through an alias table built
from *both* sources, with the matrix winning any conflict — because the matrix
is the only source whose genes can actually be plotted. `ADORA3` resolves to
`ENSG00000121933` and returns 176 points.

---

## 5. The mapping file is treated as authoritative, but the matrix names itself

The CPM matrix labels every row `ENSG…|SYMBOL`, carrying both identifiers. The
script discards the symbol (`cpm_df.index.str.split('|').str[0]`) and reloads
names from the mapping file instead.

| source | distinct symbols |
|---|---|
| CPM matrix (its own row labels) | 57,996 |
| `gene_to_gene_human.txt` | 37,491 |
| **resolvable by the script** | **36,838** |
| **resolvable from both sources** | **62,199** |

The +25,361 difference is real but should not be oversold: it is almost entirely
BAC clone identifiers (`RP11-506B6.6`, `CTC-260E6.7`), pseudogenes and small
RNAs. Every well-known gene checked — SCN2A, SYNGAP1, XIST, MEF2C, GRIN2B,
FOXP2, MECP2, FMR1, CHD8, ARID1B, MALAT1, NEAT1 — is already reachable through
the mapping file alone.

The mapping file does earn its place: 3,802 aliases come from it and nowhere
else. But the practical benefit is item 4 above, not the raw count.

---

## 6. 12,680 genes are silent in cortex and produce a meaningless plot

21% of the matrix (12,680 of 60,155 genes) is zero in all 176 samples. The
script adds a pseudocount of 1e-3 before taking log2, so those genes fit a flat
line at log2(0.001) = -9.97 and produce a valid-looking but empty chart with no
indication that nothing was measured.

```bash
$ python data/per_gene_cpm_brainvar.py CDKL3
Saved plot to .../gene_CPM_ENSG00000006837_CDKL3.pdf   # a flat line at -9.97
```

The API returns `is_expressed: false` for these, so the UI can say the gene is
not expressed in cortex rather than drawing an empty axis.

---

## 7. Runtime: 12 s per gene, almost all of it re-parsing the matrix

The script calls `pd.read_csv` on the 98 MB TSV on every invocation, to retrieve
one row of 176 values.

| | |
|---|---|
| original script, per gene | **~12 s** |
| web API, per gene | **~26 ms** (2 SQL queries + a 9 ms LOESS fit) |
| `?curve=false` | ~17 ms |

The data is loaded once into PostgreSQL (176 samples, 60,155 genes, 121,953
aliases) by a management command that takes 17 seconds end to end.

---

## 8. The test suite, and proof that it can fail

119 tests, 3.4 s, run with:

```bash
docker compose -f docker-compose.local.yml exec backend python manage.py test
```

| module | tests | covers |
|---|---|---|
| `test_loess.py` | 13 | the numpy fit against skmisc-generated fixtures |
| `test_loader.py` | 24 | the load command on a small dataset with known answers |
| `test_services.py` | 28 | search, resolution, trajectory assembly, curve fitting |
| `test_api.py` | 22 | HTTP contract — response shapes, status codes, query counts |
| `test_models.py` | 12 | uniqueness constraints and cascade behaviour |
| `test_user_model.py` | 20 | email authentication and normalisation |

Two are worth singling out:

- **`test_api.py` asserts `assertNumQueries(2)`** on the gene detail endpoint.
  That turns the performance claim into a regression guard: if an N+1 is ever
  introduced into the sample join, the suite fails rather than the application
  quietly getting slower.
- **`test_loader.py` builds its own three-sample matrix** with the metadata rows
  deliberately in a different order from the matrix columns, so the
  `column_index` mapping is exercised rather than assumed.

### Mutation testing found a real gap

A passing suite proves nothing unless it can fail, so three defects were
deliberately introduced to check the tests noticed:

| introduced defect | outcome |
|---|---|
| `values[column_index]` → `values[0]` (breaks donor alignment) | 3 tests failed |
| log2 pseudocount `1e-3` → `0.1` (breaks the transform) | 3 tests failed |
| alias precedence reversed: HGNC before the matrix | **suite still passed** |

The third exposed a genuine hole. The fixture contained no case where the two
sources assign the *same symbol to different genes* — which is the only
situation the precedence rule exists to resolve, and precisely the class of
conflict behind the 295 genes in item 4.

Fixing it took two attempts, both instructive:

1. Pointing the conflicting symbol at an Ensembl id that already had a mapping
   row did nothing — `gene_info` is keyed by id and keeps only the first symbol
   per id, so the conflict row was discarded before it could collide.
2. Pointing it at the gene used by the "absent from the mapping" test broke that
   test instead.

The fix uses a dedicated pair of genes. Re-running the mutation now fails
`test_matrix_wins_when_the_two_sources_claim_the_same_name`, as it should.

---

## Data integrity checks

Run while loading, to confirm nothing was mis-aligned:

- All 176 CPM values for SCN2A match the raw TSV exactly (max difference 0).
- All 176 ages match `brainvar_meta_data.txt` exactly.
- Every one of the 176 sample codes in the matrix header has a metadata row, and
  every metadata row has a matrix column — a clean 1:1, nothing dropped.
- **XIST separates by sex without being told to**: female median 1349.9 CPM,
  male median 0.373. This is the strongest single check that expression values
  are joined to the right donors, since XIST is only transcribed from the
  inactive X chromosome.
- The rendered chart's plotted values match the API response to 0.00000 log2
  (measured by inverting each SVG point's pixel position back to data units).
