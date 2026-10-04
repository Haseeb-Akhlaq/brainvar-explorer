/**
 * Developmental milestones and periods, identical to the annotations in
 * per_gene_cpm_brainvar.py. Ages are days post-conception; the x axis works
 * in log2(days), matching the script's log-scaled developmental axis.
 */

export interface Milestone {
  label: string;
  /** Days post-conception. */
  days: number;
  /** log2(days) — chart x coordinate. */
  x: number;
}

const DEFS: [string, number][] = [
  ["8w", 8 * 7],
  ["10w", 10 * 7],
  ["13w", 13 * 7],
  ["16w", 16 * 7],
  ["19w", 19 * 7],
  ["24w", 24 * 7],
  ["Birth", 40 * 7],
  ["6m", 40 * 7 + 365 / 2],
  ["1y", 40 * 7 + 365],
  ["6y", 40 * 7 + 365 * 6],
  ["12y", 40 * 7 + 365 * 12],
];

export const MILESTONES: Milestone[] = DEFS.map(([label, days]) => ({
  label,
  days,
  x: Math.log2(days),
}));

export const BIRTH_DAYS = 40 * 7;
export const BIRTH_X = Math.log2(BIRTH_DAYS);

/** Period spans P1..P12 over a given x-domain (log2 days). */
export function periodSpans(xMin: number, xMax: number): { period: number; x0: number; x1: number }[] {
  const edges = [xMin, ...MILESTONES.map((m) => m.x), xMax];
  const spans: { period: number; x0: number; x1: number }[] = [];
  for (let i = 0; i < edges.length - 1; i++) {
    const x0 = Math.max(edges[i], xMin);
    const x1 = Math.min(edges[i + 1], xMax);
    if (x1 > x0) spans.push({ period: i + 1, x0, x1 });
  }
  return spans;
}

/** Human description of a developmental period (Kang et al. windows). */
export const PERIOD_NAMES: Record<number, string> = {
  1: "Embryonic",
  2: "Early fetal",
  3: "Early fetal",
  4: "Early mid-fetal",
  5: "Early mid-fetal",
  6: "Late mid-fetal",
  7: "Late fetal",
  8: "Neonatal–early infancy",
  9: "Late infancy",
  10: "Early childhood",
  11: "Mid childhood",
  12: "Adolescence–adulthood",
};
