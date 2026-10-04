---
title: Testing
description: 137 tests, and the mutation testing that found a gap in them.
order: 1
---

```bash
docker compose -f docker-compose.local.yml exec backend python manage.py test
cd frontend && npm test
```

Backend runs in about 3.4 seconds.

## What is covered

| module | tests | covers |
|---|---|---|
| `test_loess.py` | 13 | the numpy fit against skmisc-generated fixtures |
| `test_services.py` | 28 | search, resolution, trajectory assembly, curve fitting |
| `test_loader.py` | 25 | the load command on a dataset with known answers |
| `test_api.py` | 22 | HTTP contract — shapes, status codes, query counts |
| `test_models.py` | 12 | uniqueness constraints and cascade behaviour |
| `test_user_model.py` | 20 | email authentication and normalisation |
| frontend | 18 | the browser LOESS against the same fixtures |

## Two worth singling out

**`test_api.py` asserts `assertNumQueries(2)`** on the gene endpoint. That turns
a performance claim into a regression guard: if an N+1 is introduced into the
sample join, the suite fails rather than the application quietly getting slower.

**`test_loader.py` builds its own three-sample matrix**, with the metadata rows
deliberately in a different order from the matrix columns. The `column_index`
mapping is therefore exercised rather than assumed — and that mapping is what
keeps every plot correct.

## Mutation testing

A passing suite proves nothing unless it can fail. Three defects were introduced
deliberately to check the tests noticed:

| introduced defect | outcome |
|---|---|
| `values[column_index]` → `values[0]` | 3 tests failed |
| log2 pseudocount `1e-3` → `0.1` | 3 tests failed |
| alias precedence reversed: HGNC before the matrix | **suite still passed** |

The third exposed a real gap. The fixtures contained no case where the two id
sources assign the **same symbol to different genes** — which is the only
situation the precedence rule exists to resolve, and precisely the conflict
behind the 295 genes the original script fails on.

Closing it took two attempts, both instructive:

1. Pointing the conflicting symbol at an Ensembl id that already had a mapping
   row did nothing — the loader keys descriptions by id and keeps only the first
   symbol per id, so the conflict row was discarded before it could collide.
2. Pointing it at the gene used by the "absent from the mapping" test broke that
   test instead.

The fix uses a dedicated pair of genes. Re-running the mutation now fails
`test_matrix_wins_when_the_two_sources_claim_the_same_name`, as it should.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request:

- **backend** — Postgres service container, a missing-migration check, 119 tests
- **frontend** — `npm ci`, type check, lint, 18 tests
- **images** — builds all three Docker images and validates the production
  compose file

The `makemigrations --check --dry-run` step fails the build if a model changed
without a migration being generated — the classic error that passes locally and
breaks on deploy.
