---
title: Data Model
description: Four tables, and what each one is responsible for.
order: 2
---

## Sample — 176 rows

One brain donor. Supplies the x-axis of every plot.

| column | type | example | purpose |
|---|---|---|---|
| `braincode` | text, unique | `HSB272` | the donor's identifier |
| `age_days` | float | `43` | days from conception — **the x-axis** |
| `age` + `age_units` | float, text | `6.14`, `PCW` | for display |
| `period` | small int | `1` | developmental period, 1–12 |
| `epoch` | small int | `0` | broader stage, 0–3 |
| `sex` | text | `Male` | powers the by-sex split |
| `tissue` | text | `cortex` | constant today, kept for future datasets |
| `column_index` | small int, **unique** | `0` | position in `Gene.values` |

Ages are **post-conception**, so birth is day ~280. That is why the chart has a
solid vertical line partway along rather than at the origin.

## Gene — 60,155 rows

| column | type | purpose |
|---|---|---|
| `ensembl_id` | text, unique, indexed | the stable identifier |
| `symbol` | text, indexed | the human-readable name |
| `name`, `hgnc_id`, `entrez_id` | text | descriptions, from the HGNC mapping |
| `values` | `double precision[]` | **176 CPM values, positional** |
| `mean_log2` | float, indexed | precomputed for search ranking |
| `is_expressed` | boolean, indexed | false when zero in every sample |

`symbol` is deliberately **not** unique — 2,158 symbols are shared by more than
one gene in this matrix.

`is_expressed` is false for **12,680 genes** (21%). Those are silent in cortex,
and the API reports the fact rather than drawing a flat line at the floor and
leaving the user to wonder whether something broke.

## GeneAlias — 121,953 rows

| column | type | purpose |
|---|---|---|
| `alias` | text, **unique**, indexed | what the user typed, uppercased |
| `source` | text | `cpm`, `hgnc` or `ensembl` |
| `gene` | FK → Gene, cascade | which gene it means |

Roughly two per gene: an Ensembl id and a symbol.

| source | from | count |
|---|---|---|
| `ensembl` | the CPM row label, before the `\|` | 60,155 |
| `cpm` | the CPM row label, after the `\|` | 57,996 |
| `hgnc` | names only the mapping file knew | 3,802 |

`alias` being unique means one name resolves to exactly one gene, so the 295
build-mismatch cases cannot produce an ambiguous result.

## User

Authentication is by **email**; `username`, `first_name` and `last_name` are
removed from Django's `AbstractUser`.

| column | purpose |
|---|---|
| `email` | unique, the login field |
| `full_name` | one field — first/last does not fit all names |
| `orcid` | the standard researcher identifier |

Email is lowercased in three places — the manager, `save()` and `clean()` — so
`Ada@EXAMPLE.COM` and `ada@example.com` cannot become two accounts. Django's own
`normalize_email` only lowercases the domain.

Defining a custom user model in the first migration costs nothing now and avoids
rebuilding the database later, since `AUTH_USER_MODEL` cannot be changed once
migrations exist.
