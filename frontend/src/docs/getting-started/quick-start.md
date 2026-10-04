---
title: Quick Start
description: Running the whole stack locally with one command.
order: 2
---

## Prerequisites

Docker with the Compose plugin. Nothing else — Python, Node and PostgreSQL all
run inside containers.

## Start the stack

```bash
docker compose -f docker-compose.local.yml up -d --build
```

Three containers come up: PostgreSQL, Django, and the Vite dev server. The
backend waits for the database, applies migrations, then serves.

| | |
|---|---|
| Application | http://localhost:5173 |
| API | http://localhost:8001/api/genes/SCN2A/ |
| Admin | http://localhost:8001/admin/ |
| Documentation | http://localhost:5173/docs |
| Interactive API reference | http://localhost:8001/api/docs/ |

## Load the data

The three source files are **not in version control** — the expression matrix
alone is 94 MB, and it is data rather than source code. Copy it in,
then run the loader:

```bash
mkdir -p data && cp -r /path/to/brainvar-files data/brainvar

docker compose -f docker-compose.local.yml exec backend \
  python manage.py load_brainvar
```

It takes about 17 seconds and reports what it created:

```
    176 samples
 60,155 genes
121,953 aliases
```

Re-running requires `--flush`, so the tables cannot be double-loaded by
accident.

## Create an admin user

```bash
docker compose -f docker-compose.local.yml exec backend \
  python manage.py createsuperuser
```

Authentication is by email — there is no username field.

## Run the tests

```bash
# 119 backend tests
docker compose -f docker-compose.local.yml exec backend python manage.py test

# 18 frontend tests
cd frontend && npm test
```

## Stopping

```bash
docker compose -f docker-compose.local.yml down     # keeps the database
docker compose -f docker-compose.local.yml down -v  # deletes it
```
