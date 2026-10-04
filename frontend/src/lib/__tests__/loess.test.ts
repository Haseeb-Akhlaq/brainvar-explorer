import { describe, expect, it } from "vitest";
import { Loess, tCdf, tQuantile } from "../loess";
import scn2a from "./reference/SCN2A.json";
import syngap1 from "./reference/SYNGAP1.json";
import xist from "./reference/XIST.json";
import mef2c from "./reference/MEF2C.json";

interface Reference {
  symbol: string;
  x: number[];
  y: number[];
  /** skmisc defaults: interpolating surface, approximate statistics. */
  fitted: number[];
  lower: number[];
  upper: number[];
  /** skmisc with surface="direct", statistics="exact" — the exact solution. */
  fittedExact: number[];
  lowerExact: number[];
  upperExact: number[];
}

const REFS: Reference[] = [scn2a, syngap1, xist, mef2c];

function maxAbsDiff(a: number[], b: number[]): number {
  let m = 0;
  for (let i = 0; i < a.length; i++) m = Math.max(m, Math.abs(a[i] - b[i]));
  return m;
}

function meanAbsDiff(a: number[], b: number[]): number {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += Math.abs(a[i] - b[i]);
  return s / a.length;
}

describe("Loess vs skmisc.loess reference (the library the original script uses)", () => {
  for (const ref of REFS) {
    it(`${ref.symbol}: matches the exact solution (surface=direct) to 1e-6`, () => {
      const model = new Loess(ref.x, ref.y);
      const { fitted } = model.predict(ref.x);
      expect(maxAbsDiff(fitted, ref.fittedExact)).toBeLessThan(1e-6);
    });

    it(`${ref.symbol}: exact 95% confidence band matches closely`, () => {
      const model = new Loess(ref.x, ref.y);
      const band = model.confidence(ref.x);
      // σ̂, δ1/δ2 and the t quantile are all computed exactly on our side;
      // small differences remain from skmisc's internal numerics.
      expect(maxAbsDiff(band.lower, ref.lowerExact)).toBeLessThan(2e-3);
      expect(maxAbsDiff(band.upper, ref.upperExact)).toBeLessThan(2e-3);
    });

    it(`${ref.symbol}: agrees with skmisc's default interpolating surface within its own error`, () => {
      const model = new Loess(ref.x, ref.y);
      const { fitted } = model.predict(ref.x);
      // The default surface="interpolate" is itself an approximation; it
      // deviates from the exact fit by up to ~0.85 log2 on these genes, so
      // only require our exact fit to sit within that same envelope.
      const skmiscOwnError = maxAbsDiff(ref.fitted, ref.fittedExact);
      expect(maxAbsDiff(fitted, ref.fitted)).toBeLessThanOrEqual(skmiscOwnError + 1e-9);
      expect(meanAbsDiff(fitted, ref.fitted)).toBeLessThan(0.1);
    });
  }
});

describe("Loess edge cases", () => {
  it("handles a constant series", () => {
    const x = Array.from({ length: 30 }, (_, i) => i);
    const y = x.map(() => 5);
    const model = new Loess(x, y);
    const { fitted } = model.predict([0, 7.5, 29]);
    for (const f of fitted) expect(f).toBeCloseTo(5, 8);
  });

  it("handles duplicate x values", () => {
    const x = [1, 1, 1, 2, 2, 3, 3, 3, 4, 5, 6, 7, 8, 9, 10];
    const y = x.map((v) => v * 2 + 1);
    const model = new Loess(x, y);
    const { fitted } = model.predict([2, 5, 9]);
    expect(fitted[0]).toBeCloseTo(5, 1);
    expect(fitted[1]).toBeCloseTo(11, 1);
    expect(fitted[2]).toBeCloseTo(19, 1);
  });

  it("recovers a quadratic exactly within the window", () => {
    const x = Array.from({ length: 50 }, (_, i) => i / 5);
    const y = x.map((v) => 3 + 2 * v - 0.5 * v * v);
    const model = new Loess(x, y, { span: 0.75, degree: 2 });
    const { fitted } = model.predict(x);
    for (let i = 0; i < x.length; i++) expect(fitted[i]).toBeCloseTo(y[i], 6);
  });

  it("accepts unsorted input", () => {
    const x = [5, 1, 4, 2, 3, 9, 7, 6, 8, 10];
    const y = x.map((v) => v * v);
    const model = new Loess(x, y);
    const { fitted } = model.predict([5]);
    expect(fitted[0]).toBeCloseTo(25, 4);
  });
});

describe("Student t helpers", () => {
  it("tCdf matches known values", () => {
    expect(tCdf(0, 10)).toBeCloseTo(0.5, 10);
    expect(tCdf(1.812, 10)).toBeCloseTo(0.95, 3);
    expect(tCdf(-1.812, 10)).toBeCloseTo(0.05, 3);
    expect(tCdf(1.96, 1e6)).toBeCloseTo(0.975, 3);
  });

  it("tQuantile inverts tCdf", () => {
    for (const df of [3, 10, 50, 170]) {
      for (const p of [0.6, 0.9, 0.975, 0.995]) {
        expect(tCdf(tQuantile(p, df), df)).toBeCloseTo(p, 6);
      }
    }
    expect(tQuantile(0.975, 10)).toBeCloseTo(2.228, 3);
  });
});
