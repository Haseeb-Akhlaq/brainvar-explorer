#!/usr/bin/env python3
"""Generate ground-truth LOESS output with skmisc (the library the original
per_gene_cpm_brainvar.py uses) so the TypeScript port can be tested against it.

Replicates the exact transforms of the original script:
  x = log2(AgeDays), y = log2(CPM + 1e-3), sorted by x,
  loess(x, y) with library defaults, predict(stderror=True), .confidence()
"""
import json
import math
import os

import pandas as pd
from skmisc.loess import loess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data", "brainvar")
OUT = os.path.join(HERE, "..", "src", "lib", "__tests__", "reference")
os.makedirs(OUT, exist_ok=True)

GENES = {
    "SCN2A": "ENSG00000136531",
    "SYNGAP1": "ENSG00000197283",
    "XIST": "ENSG00000229807",
    "MEF2C": "ENSG00000081189",
}

cpm_df = pd.read_csv(os.path.join(DATA_DIR, "brainVar.CPM-10042019.tsv"), sep="\t", index_col=0)
cpm_df.index = cpm_df.index.str.split("|").str[0]
meta_df = pd.read_csv(os.path.join(DATA_DIR, "brainvar_meta_data.txt"), sep="\t")

for symbol, ensembl_id in GENES.items():
    series = cpm_df.loc[ensembl_id]
    expr = pd.DataFrame({"SampleID": series.index, "CPM": series.values})
    merged = pd.merge(meta_df, expr, left_on="Braincode", right_on="SampleID")

    y = [math.log(float(v) + 1e-3, 2) for v in merged["CPM"]]
    x = [math.log(k, 2) for k in merged["AgeDays"]]
    pairs = sorted(zip(x, y))
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    # What the original script computes: skmisc defaults (interpolating
    # kd-tree surface, approximate statistics).
    lm = loess(xs, ys)
    lm.fit()
    pred = lm.predict(xs, stderror=True)
    conf = pred.confidence()

    # The exact local-regression solution the defaults approximate:
    lm_exact = loess(xs, ys, surface="direct", statistics="exact")
    lm_exact.fit()
    pred_exact = lm_exact.predict(xs, stderror=True)
    conf_exact = pred_exact.confidence()

    out = {
        "symbol": symbol,
        "ensembl": ensembl_id,
        "x": xs,
        "y": ys,
        "fitted": [float(v) for v in pred.values],
        "lower": [float(v) for v in conf.lower],
        "upper": [float(v) for v in conf.upper],
        "fittedExact": [float(v) for v in pred_exact.values],
        "lowerExact": [float(v) for v in conf_exact.lower],
        "upperExact": [float(v) for v in conf_exact.upper],
    }
    path = os.path.join(OUT, f"{symbol}.json")
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"{symbol}: n={len(xs)}, fitted range "
          f"[{min(out['fitted']):.3f}, {max(out['fitted']):.3f}] -> {path}")
