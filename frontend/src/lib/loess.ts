/**
 * LOESS (locally estimated scatterplot smoothing) with pointwise confidence
 * intervals — a TypeScript port of what `skmisc.loess` computes for the
 * original per_gene_cpm_brainvar.py (span 0.75, degree 2, gaussian family).
 *
 * Method: at each evaluation point x0, fit a weighted quadratic over the
 * q = floor(span·n) nearest neighbours with tricube weights, and read the
 * smoother vector l(x0) so that fit(x0) = l(x0)·y. Residual variance and
 * effective degrees of freedom come from the exact smoother matrix L over the
 * training points (σ² = RSS/δ1, δ1 = tr[(I−L)ᵀ(I−L)], δ2 = tr[((I−L)ᵀ(I−L))²]),
 * matching Cleveland, Grosse & Shyu's loess inference. skmisc evaluates on an
 * interpolating kd-tree surface and approximates δ1/δ2, so values agree to
 * within a small tolerance rather than bit-for-bit (verified in loess.test.ts).
 */

export interface LoessOptions {
  span?: number;
  degree?: 1 | 2;
}

export interface LoessBand {
  fitted: number[];
  se: number[];
  lower: number[];
  upper: number[];
}

const TINY = 1e-12;

function tricube(u: number): number {
  const t = 1 - u * u * u;
  return t * t * t;
}

/** Solve the symmetric 3x3 system Mb = e1 and return the first row of M⁻¹. */
function firstRowInverse3(m: Float64Array): [number, number, number] {
  const [a, b, c, , e, f, , , i] = m as unknown as number[];
  // M = [[a b c], [b e f], [c f i]] (symmetric)
  const A = e * i - f * f;
  const B = c * f - b * i;
  const C = b * f - c * e;
  const det = a * A + b * B + c * C;
  if (Math.abs(det) < TINY) return [NaN, NaN, NaN];
  return [A / det, B / det, C / det];
}

export class Loess {
  readonly x: number[];
  readonly y: number[];
  readonly n: number;
  readonly span: number;
  readonly degree: 1 | 2;
  /** Fitted values at the training points. */
  readonly fitted: number[];
  /** Residual scale estimate σ̂. */
  readonly sigma: number;
  /** Effective degrees of freedom δ1²/δ2 for the t quantile. */
  readonly df: number;
  private readonly order: number[];

  /** x need not be sorted; ties are fine. Requires n ≥ degree + 2. */
  constructor(x: number[], y: number[], { span = 0.75, degree = 2 }: LoessOptions = {}) {
    if (x.length !== y.length) throw new Error("x and y must have equal length");
    if (x.length < degree + 2) throw new Error(`need at least ${degree + 2} points`);
    this.span = span;
    this.degree = degree;
    this.n = x.length;
    this.order = Array.from(x.keys()).sort((a, b) => x[a] - x[b]);
    this.x = this.order.map((i) => x[i]);
    this.y = this.order.map((i) => y[i]);

    // Exact smoother matrix over the training points -> inference.
    const n = this.n;
    const L: Float64Array[] = new Array(n);
    for (let i = 0; i < n; i++) L[i] = this.lVector(this.x[i]);
    this.fitted = new Array(n);
    let rss = 0;
    for (let i = 0; i < n; i++) {
      let s = 0;
      for (let j = 0; j < n; j++) s += L[i][j] * this.y[j];
      this.fitted[i] = s;
      const r = this.y[i] - s;
      rss += r * r;
    }
    // I − L, then B = (I−L)ᵀ(I−L); δ1 = tr(B), δ2 = tr(B²) = Σ B_ij² (B symmetric).
    const M: Float64Array[] = new Array(n);
    for (let i = 0; i < n; i++) {
      M[i] = new Float64Array(L[i].map((v) => -v));
      M[i][i] += 1;
    }
    const B: Float64Array[] = new Array(n);
    for (let i = 0; i < n; i++) B[i] = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      for (let k = 0; k < n; k++) {
        const mki = M[k][i];
        if (mki === 0) continue;
        for (let j = i; j < n; j++) B[i][j] += mki * M[k][j];
      }
    }
    let d1 = 0;
    let d2 = 0;
    for (let i = 0; i < n; i++) {
      d1 += B[i][i];
      d2 += B[i][i] * B[i][i];
      for (let j = i + 1; j < n; j++) d2 += 2 * B[i][j] * B[i][j];
    }
    this.sigma = d1 > 0 ? Math.sqrt(Math.max(rss, 0) / d1) : 0;
    this.df = d2 > 0 ? (d1 * d1) / d2 : Math.max(n - 2, 1);
  }

  /** Smoother vector l(x0): fit(x0) = Σ l_i(x0)·y_i, over sorted training x. */
  private lVector(x0: number): Float64Array {
    const { x, n, degree } = this;
    let q = Math.floor(this.span * n);
    q = Math.max(q, degree + 1);
    q = Math.min(q, n);

    const dist = new Float64Array(n);
    for (let i = 0; i < n; i++) dist[i] = Math.abs(x[i] - x0);
    const sorted = Float64Array.from(dist).sort();
    let d = sorted[q - 1];
    // For span > 1 the C loess scales the max distance by span^(1/p) with
    // p = number of predictors (1 here). Unreachable at this app's span 0.75.
    if (this.span > 1) d *= this.span;
    if (d < TINY) {
      // Degenerate window (all neighbours at x0): average the exact matches.
      const l = new Float64Array(n);
      let m = 0;
      for (let i = 0; i < n; i++) if (dist[i] < TINY) m++;
      for (let i = 0; i < n; i++) if (dist[i] < TINY) l[i] = 1 / m;
      return l;
    }

    const w = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const u = dist[i] / d;
      if (u < 1) w[i] = tricube(u);
    }

    // Weighted least squares basis centred on x0: [1, dx, dx²].
    if (degree === 1) {
      let s0 = 0, s1 = 0, s2 = 0;
      for (let i = 0; i < n; i++) {
        if (w[i] === 0) continue;
        const dx = x[i] - x0;
        s0 += w[i];
        s1 += w[i] * dx;
        s2 += w[i] * dx * dx;
      }
      const det = s0 * s2 - s1 * s1;
      const l = new Float64Array(n);
      if (Math.abs(det) < TINY) {
        for (let i = 0; i < n; i++) if (w[i] > 0) l[i] = w[i] / s0;
        return l;
      }
      for (let i = 0; i < n; i++) {
        if (w[i] === 0) continue;
        const dx = x[i] - x0;
        l[i] = (w[i] * (s2 - s1 * dx)) / det;
      }
      return l;
    }

    let s0 = 0, s1 = 0, s2 = 0, s3 = 0, s4 = 0;
    for (let i = 0; i < n; i++) {
      if (w[i] === 0) continue;
      const dx = x[i] - x0;
      const dx2 = dx * dx;
      s0 += w[i];
      s1 += w[i] * dx;
      s2 += w[i] * dx2;
      s3 += w[i] * dx2 * dx;
      s4 += w[i] * dx2 * dx2;
    }
    const row = firstRowInverse3(
      Float64Array.of(s0, s1, s2, s1, s2, s3, s2, s3, s4),
    );
    const l = new Float64Array(n);
    if (Number.isNaN(row[0])) {
      // Singular (e.g. constant x in window) — fall back to a weighted mean.
      for (let i = 0; i < n; i++) if (w[i] > 0) l[i] = w[i] / s0;
      return l;
    }
    for (let i = 0; i < n; i++) {
      if (w[i] === 0) continue;
      const dx = x[i] - x0;
      l[i] = w[i] * (row[0] + row[1] * dx + row[2] * dx * dx);
    }
    return l;
  }

  predict(points: number[]): { fitted: number[]; se: number[] } {
    const fitted = new Array<number>(points.length);
    const se = new Array<number>(points.length);
    for (let k = 0; k < points.length; k++) {
      const l = this.lVector(points[k]);
      let f = 0;
      let norm2 = 0;
      for (let i = 0; i < this.n; i++) {
        f += l[i] * this.y[i];
        norm2 += l[i] * l[i];
      }
      fitted[k] = f;
      se[k] = this.sigma * Math.sqrt(norm2);
    }
    return { fitted, se };
  }

  /** Pointwise confidence band, default 95% (alpha = 0.05, as in the script). */
  confidence(points: number[], alpha = 0.05): LoessBand {
    const { fitted, se } = this.predict(points);
    const t = tQuantile(1 - alpha / 2, this.df);
    return {
      fitted,
      se,
      lower: fitted.map((f, i) => f - t * se[i]),
      upper: fitted.map((f, i) => f + t * se[i]),
    };
  }
}

/** Regularised incomplete beta I_x(a, b) via continued fraction (NR-style). */
function betaIncomplete(a: number, b: number, x: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const lbeta =
    logGamma(a) + logGamma(b) - logGamma(a + b);
  const front = Math.exp(a * Math.log(x) + b * Math.log(1 - x) - lbeta);
  const symmetric = x >= (a + 1) / (a + b + 2);
  const [aa, bb, xx] = symmetric ? [b, a, 1 - x] : [a, b, x];
  // Lentz's continued fraction
  let c = 1;
  let d = 1 - ((aa + bb) * xx) / (aa + 1);
  if (Math.abs(d) < 1e-30) d = 1e-30;
  d = 1 / d;
  let h = d;
  for (let m = 1; m <= 300; m++) {
    const m2 = 2 * m;
    let num = (m * (bb - m) * xx) / ((aa + m2 - 1) * (aa + m2));
    d = 1 + num * d;
    if (Math.abs(d) < 1e-30) d = 1e-30;
    c = 1 + num / c;
    if (Math.abs(c) < 1e-30) c = 1e-30;
    d = 1 / d;
    h *= d * c;
    num = -((aa + m) * (aa + bb + m) * xx) / ((aa + m2) * (aa + m2 + 1));
    d = 1 + num * d;
    if (Math.abs(d) < 1e-30) d = 1e-30;
    c = 1 + num / c;
    if (Math.abs(c) < 1e-30) c = 1e-30;
    d = 1 / d;
    const del = d * c;
    h *= del;
    if (Math.abs(del - 1) < 1e-12) break;
  }
  const frontS = symmetric
    ? Math.exp(aa * Math.log(xx) + bb * Math.log(1 - xx) - lbeta)
    : front;
  const val = (frontS * h) / aa;
  return symmetric ? 1 - val : val;
}

function logGamma(z: number): number {
  // Lanczos approximation
  const g = [
    676.5203681218851, -1259.1392167224028, 771.32342877765313,
    -176.61502916214059, 12.507343278686905, -0.13857109526572012,
    9.9843695780195716e-6, 1.5056327351493116e-7,
  ];
  if (z < 0.5) {
    return Math.log(Math.PI / Math.sin(Math.PI * z)) - logGamma(1 - z);
  }
  z -= 1;
  let a = 0.99999999999980993;
  const t = z + 7.5;
  for (let i = 0; i < g.length; i++) a += g[i] / (z + i + 1);
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(a);
}

/** CDF of Student's t with `df` degrees of freedom. */
export function tCdf(t: number, df: number): number {
  const ib = betaIncomplete(df / 2, 0.5, df / (df + t * t));
  return t >= 0 ? 1 - ib / 2 : ib / 2;
}

/** Quantile of Student's t (p in (0, 1)) by bisection on the CDF. */
export function tQuantile(p: number, df: number): number {
  if (!(df > 0)) return NaN;
  if (p === 0.5) return 0;
  const sign = p > 0.5 ? 1 : -1;
  const target = p > 0.5 ? p : 1 - p;
  let lo = 0;
  let hi = 1;
  while (tCdf(hi, df) < target && hi < 1e6) hi *= 2;
  for (let i = 0; i < 200; i++) {
    const mid = (lo + hi) / 2;
    if (tCdf(mid, df) < target) lo = mid;
    else hi = mid;
    if (hi - lo < 1e-10) break;
  }
  return (sign * (lo + hi)) / 2;
}
