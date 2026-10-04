import type { Sample, ServerCurve } from "./data";
import { Loess } from "./loess";
import { MILESTONES } from "./milestones";

/** Pseudocount matches the original script: log2(CPM + 1e-3). */
export const MIN_CPM = 1e-3;

export interface TrajectoryPoint {
  x: number; // log2(ageDays)
  y: number; // log2(cpm + 1e-3)
  cpm: number;
  sample: Sample;
}

export interface Curve {
  x: number[];
  fitted: number[];
  lower: number[];
  upper: number[];
}

export interface Series {
  key: "all" | "Female" | "Male";
  points: TrajectoryPoint[];
  curve: Curve;
}

export interface GeneStats {
  peakLog2: number;
  peakX: number;
  peakPeriod: number;
  /** postnatal mean − prenatal mean, in log2 units. */
  birthShift: number;
  detectedFraction: number;
  nPrenatal: number;
  nPostnatal: number;
}

export interface Trajectory {
  points: TrajectoryPoint[];
  series: Series[];
  stats: GeneStats;
  xDomain: [number, number];
  yDomain: [number, number];
}

export function periodOfX(x: number): number {
  let period = 1;
  for (const m of MILESTONES) {
    if (x >= m.x) period++;
  }
  return period;
}

function fitSeries(key: Series["key"], points: TrajectoryPoint[], gridN = 120): Series {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const model = new Loess(xs, ys);
  const x0 = xs[0];
  const x1 = xs[xs.length - 1];
  const grid: number[] = [];
  for (let i = 0; i < gridN; i++) grid.push(x0 + ((x1 - x0) * i) / (gridN - 1));
  const band = model.confidence(grid);
  return {
    key,
    points,
    curve: { x: grid, fitted: band.fitted, lower: band.lower, upper: band.upper },
  };
}

export function buildTrajectory(
  samples: Sample[],
  cpm: number[],
  splitSex: boolean,
  /**
   * The fit computed by the API. Used for the combined series so the chart
   * shows exactly what the backend produced; the per-sex series are still fit
   * in the browser, since the API returns one curve per gene.
   */
  serverCurve?: ServerCurve | null,
): Trajectory {
  const points: TrajectoryPoint[] = samples
    .map((sample, i) => ({
      x: Math.log2(sample.ageDays),
      y: Math.log2(cpm[i] + MIN_CPM),
      cpm: cpm[i],
      sample,
    }))
    .sort((a, b) => a.x - b.x);

  const combined: Series = serverCurve
    ? { key: "all", points, curve: { ...serverCurve } }
    : fitSeries("all", points);

  const series: Series[] = splitSex
    ? (["Female", "Male"] as const).map((sex) =>
        fitSeries(sex, points.filter((p) => p.sample.sex === sex)),
      )
    : [combined];

  const all = combined;
  let peakI = 0;
  all.curve.fitted.forEach((v, i) => {
    if (v > all.curve.fitted[peakI]) peakI = i;
  });
  // Classify from the metadata itself (PCW = prenatal): two newborns sit at
  // 266 days, left of the 280-day Birth axis mark, but are postnatal (P8).
  const pre = points.filter((p) => p.sample.ageUnits === "PCW");
  const post = points.filter((p) => p.sample.ageUnits !== "PCW");
  const mean = (vs: number[]) => vs.reduce((a, b) => a + b, 0) / Math.max(vs.length, 1);
  const stats: GeneStats = {
    peakLog2: all.curve.fitted[peakI],
    peakX: all.curve.x[peakI],
    peakPeriod: periodOfX(all.curve.x[peakI]),
    birthShift: mean(post.map((p) => p.y)) - mean(pre.map((p) => p.y)),
    detectedFraction: points.filter((p) => p.cpm >= 1).length / points.length,
    nPrenatal: pre.length,
    nPostnatal: post.length,
  };

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const lows = series.flatMap((s) => s.curve.lower);
  const highs = series.flatMap((s) => s.curve.upper);
  const yMin = Math.min(...ys, ...lows);
  const yMax = Math.max(...ys, ...highs);
  const pad = Math.max((yMax - yMin) * 0.06, 0.4);
  return {
    points,
    series,
    stats,
    xDomain: [Math.min(...xs), Math.max(...xs)],
    yDomain: [yMin - pad, yMax + pad],
  };
}
