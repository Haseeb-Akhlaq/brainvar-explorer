---
title: The LOESS Fit
description: Why the smoothing was reimplemented, and how it was verified.
order: 4
---

The blue trend line is **LOESS** — locally estimated scatterplot smoothing.

## What it does

Gene expression against age is noisy, and the shape is not known in advance:
some genes rise and plateau, some peak in infancy, some fall. A straight line or
a parabola would impose a shape the data may not have.

LOESS refuses to assume one. At each point on the x-axis it:

1. takes the nearest 75% of samples (the *span*)
2. weights them by closeness, using a tricube kernel
3. fits a small quadratic through just those
4. keeps that fit's value at the point

Slide along, repeat, join the answers. The grey band is the 95% confidence
interval — narrow where samples are dense, wide where they are sparse.

## Why it was reimplemented

The original script uses `skmisc.loess`, a Fortran library. It publishes **no
`linux/aarch64` wheels**:

```
scikit_misc-0.5.2-cp312-macosx_11_0_arm64.whl
scikit_misc-0.5.2-cp312-manylinux_2_24_x86_64.whl   ← x86 only
```

Docker on Apple Silicon builds `linux/arm64`, so pip falls back to compiling
from source, which fails. The options were x86 emulation, a Fortran toolchain in
the image, or reimplementing the fit.

`backend/brainvar/loess.py` is that reimplementation: local quadratic regression
with tricube weights and the exact smoother-matrix inference — about 300 lines
of numpy, which has wheels everywhere.

```python
sigma^2 = RSS / d1     d1 = tr[(I-L)'(I-L)]
df      = d1^2 / d2    d2 = tr[((I-L)'(I-L))^2]
```

The Student-t quantile needed for the band is computed directly rather than
importing scipy, which would add roughly 90 MB to the image for one function.

## How it was verified

The original script is executed **unmodified** through `runpy`, with its
matplotlib calls intercepted to capture exactly what it plots. Those arrays are
compared against the API's response for the same gene.

| gene | data points | fitted curve |
|---|---|---|
| SCN2A | 1.8e-15 | 0.176 |
| SYNGAP1 | 1.8e-15 | 0.175 |
| XIST | 1.8e-15 | 0.849 |
| MEF2C | 1.8e-15 | 0.252 |

*max absolute difference, log2 CPM*

**The data points are identical** — 1.8e-15 is floating-point epsilon.

## Why the curves differ

`skmisc` defaults to `surface="interpolate"`, evaluating the fit on a kd-tree
and interpolating between vertices. That is an approximation of its own exact
solution, and on this data it deviates from that solution by up to **0.85 log2
units** on XIST — visible where samples are sparse, between 6 months and 6
years.

This implementation computes the exact solution, and matches `skmisc`'s exact
mode (`surface="direct", statistics="exact"`) to **1e-13**.

So where the two differ, the web application is the exact local-regression fit
and the script is the faster approximation. Both are defensible; they are not
the same thing, and the difference is measured rather than assumed.

## Reproducing it

```bash
python verification/capture_script.py SCN2A SYNGAP1 XIST MEF2C
python verification/compare_against_script.py
python verification/overlay_plot.py
```
