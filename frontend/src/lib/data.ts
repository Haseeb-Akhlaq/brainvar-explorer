/**
 * API client for the Django backend.
 *
 * Replaces the previous static-JSON shard loader: gene search, expression and
 * the LOESS fit all now come from the API, so the browser downloads only the
 * gene it is showing rather than a 400 KB shard.
 */

import { API, ApiError, getJson } from "./api";

// Re-exported so existing importers keep reaching it through the gene client.
export { ApiError };

export interface Sample {
  id: string;
  ageDays: number;
  age: number;
  ageUnits: string;
  period: number;
  sex: "Male" | "Female";
}

export interface GeneRef {
  symbol: string;
  /** Full Ensembl id, e.g. ENSG00000136531 */
  ensembl: string;
  /** Mean log2(CPM + 1e-3) across all samples, for search ranking/preview. */
  meanLog2: number;
  /** Full gene name from the HGNC mapping ("" when unmapped). */
  name: string;
  /** False when the gene is zero in every sample. */
  isExpressed: boolean;
}

/** The LOESS fit computed server-side, on the same log2 axes as the plot. */
export interface ServerCurve {
  x: number[]; // log2(ageDays)
  fitted: number[];
  lower: number[];
  upper: number[];
}

export interface GeneData {
  gene: GeneRef;
  /** Which alias the query resolved through — e.g. an Ensembl id. */
  resolvedFrom: string;
  samples: Sample[];
  /** CPM per sample, index-aligned to `samples`. */
  cpm: number[];
  curve: ServerCurve | null;
}

export interface DatasetStats {
  genes: number;
  genesExpressed: number;
  samples: number;
  ageDaysMin: number;
  ageDaysMax: number;
}

/**
 * The interactive OpenAPI reference, served by the backend.
 *
 * Derived from the same base as every request, so it resolves correctly
 * whether the API is on localhost:8001 or api.brainvar.haseebakhlaq.com.
 */
export const API_DOCS_URL = `${API}/api/docs/`;

// -- wire formats -------------------------------------------------------------
// snake_case from DRF, mapped to camelCase at the boundary so the rest of the
// app never sees the wire shape.

interface GeneWire {
  ensembl_id: string;
  symbol: string;
  name: string;
  mean_log2: number;
  is_expressed: boolean;
}

interface PointWire {
  braincode: string;
  age_days: number;
  age: number;
  age_units: string;
  period: number;
  sex: "Male" | "Female";
  cpm: number;
}

interface CurveWire {
  log2_age_days: number[];
  fitted: number[];
  lower: number[];
  upper: number[];
}

function toGeneRef(g: GeneWire): GeneRef {
  return {
    symbol: g.symbol,
    ensembl: g.ensembl_id,
    name: g.name,
    meanLog2: g.mean_log2,
    isExpressed: g.is_expressed,
  };
}

// -- endpoints ----------------------------------------------------------------

let statsPromise: Promise<DatasetStats> | null = null;

export function loadStats(): Promise<DatasetStats> {
  statsPromise ??= getJson<{
    genes: number;
    genes_expressed: number;
    samples: number;
    age_days_min: number;
    age_days_max: number;
  }>("/stats/").then((s) => ({
    genes: s.genes,
    genesExpressed: s.genes_expressed,
    samples: s.samples,
    ageDaysMin: s.age_days_min,
    ageDaysMax: s.age_days_max,
  }));
  return statsPromise;
}

/** Autocomplete. Ranked server-side: exact match first, then prefixes. */
export async function searchGenes(
  query: string,
  limit = 8,
  signal?: AbortSignal,
): Promise<GeneRef[]> {
  const q = query.trim();
  if (!q) return [];
  const data = await getJson<{ results: GeneWire[] }>(
    `/genes/?q=${encodeURIComponent(q)}&limit=${limit}`,
    signal,
  );
  return data.results.map(toGeneRef);
}

/**
 * Everything needed to plot one gene: its identity, the 176 donors with their
 * expression, and the server-fitted LOESS curve.
 *
 * Accepts a symbol or an Ensembl id, case-insensitively. Throws ApiError with
 * `suggestions` populated when nothing matches.
 */
export async function fetchGene(query: string, signal?: AbortSignal): Promise<GeneData> {
  const data = await getJson<{
    gene: GeneWire;
    resolved_from: string;
    points: PointWire[];
    curve: CurveWire | null;
  }>(`/genes/${encodeURIComponent(query)}/`, signal);

  return {
    gene: toGeneRef(data.gene),
    resolvedFrom: data.resolved_from,
    samples: data.points.map((p) => ({
      id: p.braincode,
      ageDays: p.age_days,
      age: p.age,
      ageUnits: p.age_units,
      period: p.period,
      sex: p.sex,
    })),
    cpm: data.points.map((p) => p.cpm),
    curve: data.curve && {
      x: data.curve.log2_age_days,
      fitted: data.curve.fitted,
      lower: data.curve.lower,
      upper: data.curve.upper,
    },
  };
}
