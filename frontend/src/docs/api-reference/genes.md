---
title: Genes
description: Search for a gene and retrieve its expression trajectory.
order: 1
---

Base URL: `https://api.brainvar.haseebakhlaq.com` (locally, `http://localhost:8001`).

All endpoints are read-only, unauthenticated, and return JSON.

> **Try the API live.** The same endpoints are documented as an interactive
> OpenAPI 3 reference where requests can be sent from the page:
>
> - [Swagger UI](https://api.brainvar.haseebakhlaq.com/api/docs/) — expand an
>   endpoint, press *Try it out*, and execute a real request
> - [ReDoc](https://api.brainvar.haseebakhlaq.com/api/redoc/) — a cleaner
>   read-only view of the same schema
> - [OpenAPI schema](https://api.brainvar.haseebakhlaq.com/api/schema/) — the raw
>   document, for generating clients
>
> Locally these are at `/api/docs/`, `/api/redoc/` and `/api/schema/` on port
> 8001. The schema is generated from the serializers by `drf-spectacular`, so
> it cannot drift from the code.

## Search

```text
GET /api/genes/?q=SCN&limit=10
```

Autocomplete over symbols, Ensembl ids and HGNC names. Exact matches rank first,
then prefixes alphabetically.

| parameter | default | notes |
|---|---|---|
| `q` | — | the query; an empty value returns no results, not the whole table |
| `limit` | 10 | capped at **50** |

```json
{
  "query": "SCN",
  "count": 3,
  "results": [
    {
      "ensembl_id": "ENSG00000144285",
      "symbol": "SCN1A",
      "name": "sodium voltage-gated channel alpha subunit 1",
      "mean_log2": 6.355,
      "is_expressed": true
    }
  ]
}
```

Results deliberately **exclude** the expression array — ten results would
otherwise carry 1,760 floats nobody asked for.

## Gene detail

```text
GET /api/genes/SCN2A/
GET /api/genes/ENSG00000136531/
GET /api/genes/scn2a/
```

Everything needed to draw the chart. Accepts a symbol or an Ensembl id,
case-insensitively.

| parameter | default | notes |
|---|---|---|
| `curve` | `true` | pass `false` to skip the LOESS fit and return points only |

```json
{
  "gene": {
    "ensembl_id": "ENSG00000136531",
    "symbol": "SCN2A",
    "name": "sodium voltage-gated channel alpha subunit 2",
    "hgnc_id": "HGNC:10588",
    "entrez_id": "6326",
    "mean_log2": 8.894,
    "is_expressed": true
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
      "cpm": 559.743,
      "log2_cpm": 9.128
    }
  ],
  "curve": {
    "age_days": [43.0, "…", 7566.0],
    "log2_age_days": [5.43, "…", 12.88],
    "fitted": [8.155, "…", 9.754],
    "lower": [7.594, "…", 9.506],
    "upper": [8.716, "…", 10.001]
  }
}
```

**Points arrive sorted by age** — plot order. `log2_cpm` is precomputed with the
same `+1e-3` pseudocount the original script uses, so clients need not
reimplement the transform.

**The curve is evaluated at 200 evenly spaced points** across the age range,
rather than at the 176 donor positions. Donors cluster in the second trimester,
and drawing through them makes the line zig-zag where samples bunch up.

### Not found

A miss returns `404` with suggestions rather than a bare error:

```json
{
  "detail": "No gene found matching 'SCN2'.",
  "query": "SCN2",
  "suggestions": ["SCN2A", "SCN2B"]
}
```

### Silent genes

Genes with no expression in cortex return normally, flagged:

```json
{ "gene": { "symbol": "CDKL3", "is_expressed": false }, "…": "…" }
```

The curve is still computed — a flat line at `log2(0.001)` = −9.97 — but
`is_expressed` lets the interface say the gene is not expressed rather than
showing an apparently empty chart.

## Dataset statistics

```text
GET /api/stats/
```

```json
{
  "genes": 60155,
  "genes_expressed": 47475,
  "samples": 176,
  "age_days_min": 43.0,
  "age_days_max": 7566.002
}
```

## Health

```text
GET /api/health/
```

```json
{ "status": "ok", "service": "brainvar-api", "database": "ok" }
```

Used by the container health check and by nginx as an upstream probe. It runs
`SELECT 1`, so it fails if the database is unreachable rather than reporting
healthy while broken.

## Errors

| status | when |
|---|---|
| `400` | a malformed parameter, such as `?limit=abc` |
| `404` | no gene matches — carries `suggestions` |
