import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Series, Trajectory, TrajectoryPoint } from "../lib/trajectory";
import { BIRTH_X, MILESTONES, PERIOD_NAMES, periodSpans } from "../lib/milestones";
import { formatAge, formatCpm, formatLog2, formatMetaAge, niceTicks } from "../lib/format";
import { useThemeColors } from "../lib/useThemeColors";

/**
 * Colours come from useThemeColors, which resolves the CSS custom properties
 * in index.css to concrete values. They are applied as literal hex rather than
 * `var(…)` so the serialised SVG still renders correctly during PNG export,
 * which has no stylesheet to resolve variables against.
 */
const MONO = "'Spline Sans Mono', ui-monospace, SFMono-Regular, monospace";
const SANS = "'Instrument Sans', system-ui, sans-serif";
/** Tooltip width on a roomy chart; narrower charts shrink it to fit. */
const TOOLTIP_W_MAX = 216;

interface Hover {
  /** Index into trajectory.points, or null when only the crosshair is live. */
  pointIndex: number | null;
  /** Crosshair position in domain (log2 days). */
  gx: number;
  /** Anchor in pixel space for the tooltip. */
  px: number;
  py: number;
}

interface Props {
  trajectory: Trajectory;
  symbol: string;
  ensembl: string;
  splitSex: boolean;
  /** True while the next gene's shard is in flight — keeps the frame, dims it. */
  stale?: boolean;
}

function linePath(xs: number[], ys: number[], sx: (v: number) => number, sy: (v: number) => number): string {
  let d = "";
  for (let i = 0; i < xs.length; i++) {
    d += `${i === 0 ? "M" : "L"}${sx(xs[i]).toFixed(2)},${sy(ys[i]).toFixed(2)}`;
  }
  return d;
}

function bandPath(s: Series, sx: (v: number) => number, sy: (v: number) => number): string {
  const { x, upper, lower } = s.curve;
  let d = "";
  for (let i = 0; i < x.length; i++) {
    d += `${i === 0 ? "M" : "L"}${sx(x[i]).toFixed(2)},${sy(upper[i]).toFixed(2)}`;
  }
  for (let i = x.length - 1; i >= 0; i--) {
    d += `L${sx(x[i]).toFixed(2)},${sy(lower[i]).toFixed(2)}`;
  }
  return d + "Z";
}

/** Interpolated fitted value of a series at domain x (for the tooltip). */
function curveAt(s: Series, gx: number): number | null {
  const { x, fitted } = s.curve;
  if (gx < x[0] || gx > x[x.length - 1]) return null;
  let i = 1;
  while (i < x.length && x[i] < gx) i++;
  if (i >= x.length) return fitted[x.length - 1];
  const t = (gx - x[i - 1]) / (x[i] - x[i - 1] || 1);
  return fitted[i - 1] + t * (fitted[i] - fitted[i - 1]);
}

export function ExpressionChart({ trajectory, symbol, ensembl, splitSex, stale }: Props) {
  // Resolved from CSS so the chart follows the light/dark toggle.
  const C = useThemeColors();
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const captureRef = useRef<SVGRectElement>(null);
  const [width, setWidth] = useState(900);
  const [hover, setHover] = useState<Hover | null>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      // Floored only at the point the axes stop being drawable. It used to be
      // 320, which is wider than the card on a 320px phone — `.chart-card`
      // clips its overflow, so the last samples were cut off with no scrollbar
      // and nothing on screen to say so.
      setWidth(Math.max(240, Math.round(entries[0].contentRect.width)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Below ~480px the gutters are the difference between a readable plot and a
  // sliver: the y labels are at most four glyphs, so 40px is enough for them.
  const narrow = width < 480;
  const H = width < 640 ? (narrow ? 380 : 430) : Math.min(560, Math.round(width * 0.52));
  const m = narrow
    ? { top: 30, right: 12, bottom: 84, left: 38 }
    : { top: 34, right: 26, bottom: 92, left: 62 };
  const tickFont = narrow ? 10 : 11;
  const tooltipW = Math.min(TOOLTIP_W_MAX, width - 16);
  const innerW = width - m.left - m.right;
  const plotBottom = H - m.bottom;
  const innerH = plotBottom - m.top;

  const [xd0, xd1] = trajectory.xDomain;
  const [yd0, yd1] = trajectory.yDomain;
  const xPad = (xd1 - xd0) * 0.015;
  const sx = (v: number) => m.left + ((v - (xd0 - xPad)) / (xd1 - xd0 + 2 * xPad)) * innerW;
  const sy = (v: number) => plotBottom - ((v - yd0) / (yd1 - yd0)) * innerH;

  const yTicks = useMemo(() => niceTicks(yd0, yd1, 5), [yd0, yd1]);
  const spans = useMemo(() => periodSpans(xd0 - xPad, xd1 + xPad), [xd0, xd1, xPad]);

  /**
   * Which milestones get a text label.
   *
   * The axis is log-scaled, so the early weeks bunch together and dropping
   * every other one is not enough — at phone widths "8w 13w 19w" still
   * collided. This measures instead: Birth is placed first because it is the
   * emphasised tick, then the rest fill in left to right, each kept only if it
   * clears everything already placed. Ticks are still drawn for all of them.
   */
  const axisLabels = useMemo(() => {
    // Spline Sans Mono advances ~0.6em per glyph.
    const halfWidth = (label: string) => (label.length * tickFont * 0.6) / 2;
    const kept: { label: string; x: number; isBirth: boolean }[] = [];

    const place = (ms: (typeof MILESTONES)[number]) => {
      const X = sx(ms.x);
      if (X < m.left - 1 || X > m.left + innerW + 1) return;
      const hw = halfWidth(ms.label);
      // Nudged inside the viewBox rather than dropped: the tick still marks
      // the true position, and losing the last label costs more than 2px.
      const x = Math.min(Math.max(X, hw + 2), width - hw - 2);
      const clash = kept.some((k) => Math.abs(x - k.x) < hw + halfWidth(k.label) + 6);
      if (!clash) kept.push({ label: ms.label, x, isBirth: ms.label === "Birth" });
    };

    const birth = MILESTONES.find((ms) => ms.label === "Birth");
    if (birth) place(birth);
    for (const ms of MILESTONES) if (ms.label !== "Birth") place(ms);
    return kept;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trajectory, width, H, tickFont]);

  const screenPts = useMemo(
    () => trajectory.points.map((p) => [sx(p.x), sy(p.y)] as const),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [trajectory, width, H],
  );

  // Points remount (and the entrance replays) only on gene change; the sex
  // toggle swaps the keyed band/curve paths and recolors circles in place.
  const animKey = ensembl;
  useEffect(() => setHover(null), [ensembl, splitSex]);

  const onPointerMove = (e: React.PointerEvent<SVGRectElement>) => {
    const rect = svgRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let best = -1;
    let bestD = 26 * 26;
    for (let i = 0; i < screenPts.length; i++) {
      const dx = screenPts[i][0] - mx;
      const dy = screenPts[i][1] - my;
      const d = dx * dx + dy * dy;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    const next: Hover =
      best >= 0
        ? {
            pointIndex: best,
            gx: trajectory.points[best].x,
            px: screenPts[best][0],
            py: screenPts[best][1],
          }
        : {
            pointIndex: null,
            gx: xd0 - xPad + ((mx - m.left) / innerW) * (xd1 - xd0 + 2 * xPad),
            px: mx,
            py: my,
          };
    // Bail out when nothing changed so pointermove doesn't re-render the chart.
    setHover((prev) =>
      prev &&
      prev.pointIndex === next.pointIndex &&
      prev.gx === next.gx &&
      prev.px === next.px &&
      prev.py === next.py
        ? prev
        : next,
    );
  };

  const moveSelection = (dir: 1 | -1) => {
    const n = trajectory.points.length;
    const cur = hover?.pointIndex ?? (dir === 1 ? -1 : n);
    const next = Math.min(n - 1, Math.max(0, cur + dir));
    setHover({
      pointIndex: next,
      gx: trajectory.points[next].x,
      px: screenPts[next][0],
      py: screenPts[next][1],
    });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") { e.preventDefault(); moveSelection(1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); moveSelection(-1); }
    else if (e.key === "Escape") setHover(null);
  };

  const hoveredPoint: TrajectoryPoint | null =
    hover?.pointIndex != null ? trajectory.points[hover.pointIndex] : null;

  // Prefer the right side of the point; flip left and clamp on-screen when
  // there is no room, so the tooltip is never clipped at the edges.
  const tooltipLeft = hover
    ? hover.px + 16 <= width - (tooltipW + 8)
      ? hover.px + 16
      : Math.max(8, Math.min(hover.px - (tooltipW + 16), width - tooltipW - 8))
    : 0;

  const pointFill = (p: TrajectoryPoint): string =>
    splitSex ? C.series[p.sample.sex] : C.series.all;

  const stagger = (i: number) =>
    reduced ? 0 : 0.15 + Math.min(i * 0.006, 0.85);

  // The static scene re-renders only when data or geometry changes — hover
  // updates reuse this exact element tree, so 176 circles aren't reconciled
  // on every pointermove.
  const scene = useMemo(
    () => (
      <>
        <rect x={0} y={0} width={width} height={H} fill={C.surface} />
        <defs>
          <linearGradient id="prenatalWash" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={C.prenatal} stopOpacity="0.10" />
            <stop offset="1" stopColor={C.prenatal} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Prenatal field — everything left of birth happened in utero */}
        <rect
          x={m.left}
          y={m.top}
          width={Math.max(0, sx(BIRTH_X) - m.left)}
          height={innerH}
          fill="url(#prenatalWash)"
        />

        {/* Horizontal grid + y ticks */}
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={m.left + innerW} y1={sy(t)} y2={sy(t)} stroke={C.grid} strokeWidth={1} />
            <text
              x={m.left - (narrow ? 6 : 10)}
              y={sy(t) + 3.5}
              textAnchor="end"
              fontFamily={MONO}
              fontSize={tickFont}
              fill={C.ink3}
            >
              {t}
            </text>
          </g>
        ))}
        <text
          x={Math.max(2, m.left - 44)}
          y={m.top - 12}
          fontFamily={MONO}
          fontSize={narrow ? 9.5 : 10.5}
          fill={C.ink3}
          letterSpacing="0.08em"
        >
          LOG₂(CPM + 0.001)
        </text>

        {/* Milestone verticals; birth is the solid, emphasized one */}
        {MILESTONES.map((ms) => {
          const X = sx(ms.x);
          if (X < m.left || X > m.left + innerW) return null;
          const isBirth = ms.label === "Birth";
          return (
            <line
              key={ms.label}
              x1={X}
              x2={X}
              y1={m.top}
              y2={plotBottom}
              stroke={isBirth ? C.birth : C.baseline}
              strokeWidth={isBirth ? 1.4 : 1}
              strokeOpacity={isBirth ? 0.75 : 0.35}
              strokeDasharray={isBirth ? undefined : "2 5"}
            />
          );
        })}

        <AnimatePresence mode="wait">
          <motion.g
            key={animKey}
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.12 } }}
          >
            {/* Confidence bands */}
            {trajectory.series.map((s) => (
              <motion.path
                key={`band-${s.key}`}
                d={bandPath(s, sx, sy)}
                fill={C.series[s.key]}
                fillOpacity={0.13}
                initial={reduced ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: reduced ? 0 : 0.75, duration: 0.6 }}
              />
            ))}

            {/* Data points — entrance animates a transform, so later cx/cy
                updates (e.g. the sex toggle reshaping the domain) are instant */}
            {trajectory.points.map((p, i) => (
              <motion.circle
                key={p.sample.id}
                cx={sx(p.x)}
                cy={sy(p.y)}
                r={4.2}
                fill={pointFill(p)}
                fillOpacity={0.82}
                stroke={C.surface}
                strokeWidth={2}
                initial={reduced ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: stagger(i), duration: 0.45, ease: "easeOut" }}
              />
            ))}

            {/* LOESS curves */}
            {trajectory.series.map((s) => (
              <motion.path
                key={`curve-${s.key}`}
                d={linePath(s.curve.x, s.curve.fitted, sx, sy)}
                fill="none"
                stroke={C.series[s.key]}
                strokeWidth={2.4}
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={reduced ? false : { pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ delay: reduced ? 0 : 0.25, duration: 1.1, ease: "easeInOut" }}
              />
            ))}
          </motion.g>
        </AnimatePresence>

        {/* Baseline + milestone axis */}
        <line x1={m.left} x2={m.left + innerW} y1={plotBottom} y2={plotBottom} stroke={C.baseline} strokeWidth={1} />
        {MILESTONES.map((ms) => {
          const X = sx(ms.x);
          if (X < m.left || X > m.left + innerW) return null;
          return (
            <line
              key={`tick-${ms.label}`}
              x1={X}
              x2={X}
              y1={plotBottom}
              y2={plotBottom + 5}
              stroke={C.baseline}
              strokeWidth={1}
            />
          );
        })}
        {axisLabels.map((l) => (
          <text
            key={l.label}
            x={l.x}
            y={plotBottom + 19}
            textAnchor="middle"
            fontFamily={MONO}
            fontSize={tickFont}
            fontWeight={l.isBirth ? 600 : 400}
            fill={l.isBirth ? C.ink2 : C.ink3}
          >
            {l.label}
          </text>
        ))}

        {/* Period band P1..P12 */}
        {spans.map((sp) => {
          const x0 = sx(sp.x0);
          const x1 = sx(sp.x1);
          const w = x1 - x0;
          return (
            <g key={sp.period}>
              <rect
                x={x0 + 1}
                y={plotBottom + (narrow ? 28 : 32)}
                width={Math.max(0, w - 2)}
                height={narrow ? 20 : 24}
                rx={4}
                // Alternating period bands. White in dark mode, dark in
                // light mode, so the banding reads the same way in both.
                fill={
                  sp.period % 2
                    ? `${C.bandTint},0.028)`
                    : `${C.bandTint},0.055)`
                }
              >
                <title>{`P${sp.period} — ${PERIOD_NAMES[sp.period] ?? ""}`}</title>
              </rect>
              {w > 26 && (
                <text
                  x={x0 + w / 2}
                  y={plotBottom + (narrow ? 42 : 48)}
                  textAnchor="middle"
                  fontFamily={SANS}
                  fontSize={narrow ? 10 : 11}
                  fill={C.ink3}
                >
                  {`P${sp.period}`}
                </text>
              )}
            </g>
          );
        })}
        <text
          x={narrow ? 2 : m.left}
          y={plotBottom + (narrow ? 68 : 74)}
          fontFamily={MONO}
          fontSize={narrow ? 9 : 10}
          fill={C.ink3}
          letterSpacing="0.08em"
        >
          {narrow ? "DEVELOPMENTAL PERIOD" : "DEVELOPMENTAL PERIOD · LOG-SCALED AGE"}
        </text>
      </>
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [trajectory, width, H, splitSex, reduced, animKey, axisLabels],
  );

  return (
    <div className={`chart-wrap${stale ? " is-stale" : ""}`} ref={containerRef}>
      <svg
        ref={svgRef}
        className="chart-svg"
        width={width}
        height={H}
        viewBox={`0 0 ${width} ${H}`}
        role="img"
        tabIndex={0}
        aria-label={`Expression trajectory of ${symbol}: log2 CPM against developmental age for ${trajectory.points.length} brain samples with a LOESS trend. Use left and right arrow keys to step through samples; full values are in the sample table below.`}
        onKeyDown={onKeyDown}
        onPointerDown={(e) => {
          e.preventDefault(); // keep click from grabbing focus; Tab still works
          // A tap outside the plot area dismisses a pinned tooltip on touch.
          if (e.target !== captureRef.current) setHover(null);
        }}
      >
        {scene}

        {/* Hover layer */}
        {hover && (
          <g pointerEvents="none">
            <line
              x1={sx(hover.gx)}
              x2={sx(hover.gx)}
              y1={m.top}
              y2={plotBottom}
              stroke={C.ink3}
              strokeWidth={1}
              strokeDasharray="3 3"
              strokeOpacity={0.8}
            />
            {hoveredPoint && (
              <circle
                cx={sx(hoveredPoint.x)}
                cy={sy(hoveredPoint.y)}
                r={7}
                fill="none"
                stroke={C.ink}
                strokeWidth={1.5}
              />
            )}
          </g>
        )}

        {/* Pointer capture area */}
        <rect
          ref={captureRef}
          x={m.left}
          y={m.top}
          width={innerW}
          height={innerH}
          fill="transparent"
          style={{ touchAction: "pan-y" }}
          onPointerMove={onPointerMove}
          onPointerDown={onPointerMove} /* tap-to-pin for touch */
          onPointerLeave={(e) => {
            if (e.pointerType === "mouse") setHover(null);
          }}
        />
      </svg>

      {/* Tooltip */}
      <AnimatePresence>
        {hover && (
          <motion.div
            className="chart-tooltip"
            style={{
              left: tooltipLeft,
              top: Math.max(8, Math.min(hover.py - 24, H - 170)),
              width: tooltipW,
            }}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
          >
            {hoveredPoint ? (
              <>
                <div className="tt-head">
                  <span className="tt-dot" style={{ background: pointFill(hoveredPoint) }} />
                  {hoveredPoint.sample.id}
                  <span className="tt-muted">{hoveredPoint.sample.sex}</span>
                </div>
                <div className="tt-value">
                  {formatCpm(hoveredPoint.cpm)} <span className="tt-unit">CPM</span>
                </div>
                <div className="tt-row">
                  <span>log₂(CPM+10⁻³)</span>
                  <strong>{formatLog2(hoveredPoint.y)}</strong>
                </div>
                <div className="tt-row">
                  <span>Age</span>
                  <strong>{formatMetaAge(hoveredPoint.sample)}</strong>
                </div>
                <div className="tt-row">
                  <span>Period</span>
                  <strong>
                    P{hoveredPoint.sample.period} · {PERIOD_NAMES[hoveredPoint.sample.period] ?? ""}
                  </strong>
                </div>
              </>
            ) : (
              <>
                <div className="tt-head">{formatAge(Math.pow(2, hover.gx))}</div>
                {trajectory.series.map((s) => {
                  const v = curveAt(s, hover.gx);
                  return (
                    <div className="tt-row" key={s.key}>
                      <span>
                        <span className="tt-key" style={{ background: C.series[s.key] }} />
                        {s.key === "all" ? "LOESS trend" : s.key}
                      </span>
                      <strong>{v == null ? "—" : `${formatLog2(v)} log₂`}</strong>
                    </div>
                  );
                })}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
