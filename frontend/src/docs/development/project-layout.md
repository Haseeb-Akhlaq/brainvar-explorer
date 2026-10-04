---
title: Project Layout
description: Where things live and why.
order: 2
---

```
backend/
  config/          settings, root urls, health check
  brainvar/
    models.py      Gene, Sample, GeneAlias
    services.py    all data logic — views call into this
    loess.py       the numpy LOESS implementation
    views.py       thin: parse request, call service, serialise
    serializers.py
    management/commands/load_brainvar.py
    tests/         99 tests plus skmisc reference fixtures
  users/           custom user model, managers, admin
frontend/
  src/lib/         API client, LOESS port, trajectory assembly
  src/components/  chart, search, stat tiles, sample table
  src/docs/        this documentation, as markdown
nginx/             reverse proxy, TLS, security headers
verification/      runs the original script and diffs it against the API
```

## Conventions

**Views stay thin.** Everything that knows about the data lives in
`services.py`, so it can be tested without HTTP and reused by future endpoints.
A view parses the request, calls a service, and serialises the result.

**Two apps, not one.** `users` owns identity and access; `brainvar` owns the
dataset. The boundary is real rather than cosmetic — access control lives in one
place, separate from the science. The domain app is named for the **dataset**,
so a second one would sit beside it rather than inside it.

**Tests live beside the code they test**, one file per concern, with the
`skmisc` reference fixtures committed so the suite is self-contained.

## The documentation you are reading

Markdown under `src/docs/{section}/`, with a `_meta.json` per section giving its
title, order and icon.

```
src/docs/architecture/
  _meta.json          { "title": "Architecture", "order": 2, "icon": "Boxes" }
  system-design.md
  data-model.md
  loess.md
```

`import.meta.glob('/src/docs/**/*.md', { query: '?raw', eager: true })` pulls
every file into the bundle at build time, so the docs need no server and no
runtime fetching. Adding a page means adding a file — the sidebar, search index
and previous/next links all follow from the glob.
