---
title: Overview
description: What this application does and why it exists.
order: 1
---

The BrainVar Trajectory Explorer replaces `per_gene_cpm_brainvar.py`, a legacy
script that plots how a gene's expression changes across human brain development.

Type a gene symbol — `SCN2A`, `SYNGAP1`, `XIST` — and the application shows its
expression across **176 RNA-seq samples**, from 6 post-conception weeks to
adulthood, with a LOESS trend and a 95% confidence band.

## What the original script did

Given a gene symbol on the command line, it would:

1. Look the symbol up in `gene_to_gene_human.txt` to get an Ensembl id
2. Read a **98 MB** expression matrix with pandas to retrieve one row
3. Join those 176 values to each donor's age
4. Fit a LOESS curve and write a PDF to a hardcoded path

It worked, but every run re-parsed the whole matrix to fetch 176 numbers, and
the output was a file on one person's laptop.

## What changed

| | script | this application |
|---|---|---|
| time per gene | ~12 s | **~26 ms** |
| output | a PDF on disk | an interactive chart in a browser |
| gene lookup | one mapping file | an index over both id sources |
| access | a terminal on one machine | a URL |

## The dataset

BrainVar is bulk RNA-seq of developing human cortex.

- **176 donors**, 43 to 7,566 days post-conception — birth falls at ~280
- **60,155 genes**, of which 47,475 are expressed at all in cortex
- Values are **CPM** (counts per million), plotted as `log2(CPM + 0.001)`

The pseudocount matters: 53.7% of the matrix is exactly zero, and `log2(0)` is
undefined. Adding `0.001` puts silent genes on a floor at −9.97 rather than
discarding them.

## A quick correctness check

Search for **XIST**, then switch the chart to *By sex*.

XIST is transcribed only from the inactive X chromosome, so it should separate
almost perfectly: female samples high, male samples on the floor. That split
appears without the application being told anything about sex — which is the
strongest single indication that expression values are joined to the right
donors.
