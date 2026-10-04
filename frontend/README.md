# Frontend — BrainVar Trajectory Explorer

React + TypeScript + Vite. See the [root README](../README.md) for the whole
application, and [DEPLOYMENT.md](../DEPLOYMENT.md) for production.

## Development

The frontend is normally run through the compose stack, which also brings up the
API and database it needs:

```bash
docker compose -f ../docker-compose.local.yml up -d --build
```

To run it directly against an already-running API:

```bash
npm install
VITE_API_URL=http://localhost:8001 npm run dev
```

`VITE_API_URL` is read at build time. Leave it empty to call the API on the same
origin.

```bash
npm test              # 18 tests — the LOESS port against skmisc fixtures
npx tsc -b --noEmit   # type check
npm run lint          # oxlint
```

## Structure

```
src/lib/
  data.ts          API client — search, gene detail, stats
  loess.ts         LOESS in TypeScript, kept as a verified reference
  trajectory.ts    joins points to metadata, derives stats and domains
  milestones.ts    the developmental period boundaries (8w … 12y)
src/components/
  ExpressionChart  hand-built SVG chart with hover and PNG export
  GeneSearch       debounced, server-side autocomplete
  StatTiles        peak, change across birth, detection rate
  SampleTable      all 176 donors with their values
```

## Two notes

**The chart is hand-built SVG, not D3 or Plotly.** The developmental-period
axis — twelve labelled bands, a solid line at birth, log-scaled age — is
specific enough that a charting library would have been fought rather than used,
and it avoids a large dependency for one chart.

**`loess.ts` is no longer on the request path.** The fit is computed server-side
in numpy. The TypeScript implementation is kept because it is independently
verified against the same `skmisc` fixtures, and its tests would catch a
divergence in either implementation.
