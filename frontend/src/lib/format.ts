import type { Sample } from "./data";
import { BIRTH_DAYS } from "./milestones";

/** "17.3 pcw" prenatally, "4.2 mo" / "6.1 yr" postnatally. */
export function formatAge(ageDays: number): string {
  if (ageDays < BIRTH_DAYS) return `${(ageDays / 7).toFixed(1)} pcw`;
  const post = ageDays - BIRTH_DAYS;
  if (post < 365) return `${(post / 30.44).toFixed(1)} mo`;
  return `${(post / 365).toFixed(1)} yr`;
}

/** The metadata's own age representation, e.g. "19.4 PCW" or "2.5 Years". */
export function formatMetaAge(s: Sample): string {
  return `${s.age} ${s.ageUnits === "PCW" ? "pcw" : "yr"}`;
}

export function formatCpm(v: number): string {
  if (v >= 1000) return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (v >= 10) return v.toFixed(1);
  if (v >= 0.01) return v.toFixed(2);
  if (v === 0) return "0";
  return v.toExponential(1);
}

export function formatLog2(v: number): string {
  return v.toFixed(2);
}

/** Fold change from a log2 difference, e.g. 1.58 -> "3.0×". */
export function formatFold(log2Delta: number): string {
  const fold = Math.pow(2, Math.abs(log2Delta));
  return `${fold >= 10 ? fold.toFixed(0) : fold.toFixed(1)}×`;
}

/** Round-number ticks covering [min, max], aiming for ~count ticks. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  const span = max - min;
  if (span <= 0) return [min];
  const step0 = span / Math.max(count, 1);
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm >= 5 ? 10 : norm >= 2.5 ? 5 : norm >= 1.5 ? 2 : 1) * mag;
  // Generate by index and round to the step's precision so labels never carry
  // accumulated floating-point noise ("-10.200000000000001").
  const dp = Math.max(0, -Math.floor(Math.log10(step)));
  const ticks: number[] = [];
  for (let i = Math.ceil(min / step - 1e-9); i * step <= max + 1e-9; i++) {
    const v = Number((i * step).toFixed(dp));
    ticks.push(Math.abs(v) < 1e-9 ? 0 : v);
  }
  return ticks;
}
