import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ApiError,
  fetchGene,
  loadStats,
  type DatasetStats,
  type GeneData,
  type GeneRef,
  API_DOCS_URL,
} from "./lib/data";
import { buildTrajectory } from "./lib/trajectory";
import { GeneSearch } from "./components/GeneSearch";
import { ThemeToggle } from "./components/ThemeToggle";
import { TopBarNav } from "./components/TopBarNav";
import { useDocumentTheme } from "./lib/useDocumentTheme";
import { useAuth } from "./lib/authContext";
import { hasPerm, PERMISSIONS } from "./lib/auth";
import { ExpressionChart } from "./components/ExpressionChart";
import { exportChartPng } from "./lib/exportPng";
import { reportExport } from "./lib/activity";
import { StatTiles } from "./components/StatTiles";
import { SampleTable } from "./components/SampleTable";

const EXAMPLES: { symbol: string; hint: string }[] = [
  { symbol: "SCN2A", hint: "sodium channel" },
  { symbol: "SYNGAP1", hint: "synaptic GTPase" },
  { symbol: "XIST", hint: "X-inactivation" },
  { symbol: "MEF2C", hint: "neuronal TF" },
  { symbol: "GRIN2B", hint: "NMDA receptor" },
  { symbol: "FOXP2", hint: "speech & language" },
];

export default function App() {
  // Keys the chart so it remounts on a theme change: its colours are baked
  // into SVG attributes, and AnimatePresence otherwise holds the old subtree.
  const theme = useDocumentTheme();
  const { user, signOut } = useAuth();
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [gene, setGene] = useState<GeneRef | null>(null);
  const [data, setData] = useState<GeneData | null>(null);
  const [splitSex, setSplitSex] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);
  const chartAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    loadStats()
      .then((s) => {
        if (!cancelled) setStats(s);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Could not reach the API. Is the backend running?");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  /** Load a gene by symbol or Ensembl id. `ref` short-circuits the header. */
  const selectGene = (query: string, ref?: GeneRef) => {
    setError(null);
    if (ref) setGene(ref);
    history.replaceState(null, "", `#${ref?.symbol ?? query}`);

    const req = ++requestRef.current;
    fetchGene(query)
      .then((d) => {
        if (requestRef.current !== req) return;
        setGene(d.gene);
        setData(d);
      })
      .catch((err) => {
        if (requestRef.current !== req) return;
        if (err instanceof ApiError && err.status === 404) {
          const hint = err.suggestions.length ? ` Did you mean ${err.suggestions.join(", ")}?` : "";
          setError(`${err.message}${hint}`);
          setGene(null);
        } else {
          setError(`Couldn't load ${query}. Check the connection and try again.`);
        }
      });
  };

  // Deep link: #SCN2A opens that gene — on first load and on later hash edits.
  const geneRef = useRef<GeneRef | null>(null);
  geneRef.current = gene;
  useEffect(() => {
    const applyHash = () => {
      const hash = decodeURIComponent(location.hash.slice(1)).trim().toUpperCase();
      if (!hash) return;
      const current = geneRef.current;
      if (current && (current.symbol.toUpperCase() === hash || current.ensembl === hash)) return;
      selectGene(hash);
    };
    applyHash();
    window.addEventListener("hashchange", applyHash);
    return () => window.removeEventListener("hashchange", applyHash);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const trajectory = useMemo(() => {
    if (!data) return null;
    return buildTrajectory(data.samples, data.cpm, splitSex, data.curve);
  }, [data, splitSex]);

  const stale = gene != null && data?.gene.ensembl !== gene.ensembl;
  const shown = gene && data && trajectory && !stale ? { gene, trajectory } : null;
  const previous = gene && data && trajectory && stale ? trajectory : null;

  const chipRow = (compact: boolean) => (
    <div className={`chips${compact ? " chips-compact" : ""}`}>
      {!compact && <span className="chips-label">Try</span>}
      {EXAMPLES.map((ex, i) => (
        <motion.button
          key={ex.symbol}
          type="button"
          className={`chip${gene?.symbol === ex.symbol ? " is-current" : ""}`}
          aria-label={`Show ${ex.symbol} (${ex.hint})`}
          onClick={() => selectGene(ex.symbol)}
          initial={compact ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: compact ? 0 : 0.35 + i * 0.05, duration: 0.3 }}
        >
          <span className="chip-symbol">{ex.symbol}</span>
          {!compact && <span className="chip-hint">{ex.hint}</span>}
        </motion.button>
      ))}
    </div>
  );

  return (
    <div className="app">
      <div className="bg-glow" aria-hidden="true" />
      <header className="topbar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            requestRef.current++; // invalidate any in-flight request
            setGene(null);
            setData(null);
            setError(null);
            history.replaceState(null, "", location.pathname);
          }}
        >
          <span className="brand-mark" aria-hidden="true" />
          BrainVar
          <span className="brand-sub">Trajectory Explorer</span>
        </a>
        <GeneSearch onSelect={(ref) => selectGene(ref.symbol, ref)} />
        <TopBarNav trailing={<ThemeToggle />}>
          <a className="topbar-docs" href="/docs">
            Docs
          </a>
          <a
            className="topbar-docs"
            href={API_DOCS_URL}
            target="_blank"
            rel="noreferrer noopener"
          >
            API
          </a>
          {/* Shown on the permission, not on `isStaff` or a group name, so it
              tracks exactly what the API will allow. */}
          {hasPerm(user, PERMISSIONS.viewUsers) && (
            <a className="topbar-admin" href="/admin">
              Admin panel
            </a>
          )}
          {user && (
            <button
              type="button"
              className="topbar-signout"
              onClick={() => void signOut()}
              title={`Signed in as ${user.email}`}
            >
              Sign out
            </button>
          )}
        </TopBarNav>
      </header>

      <main>
        {error && (
          <div className="error-card" role="alert">
            {error}
          </div>
        )}

        {!gene && !error && (
          <section className="hero">
            <motion.p
              className="eyebrow"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              BrainVar · developing human cortex · 176 RNA-seq samples
            </motion.p>
            <motion.h1
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08, duration: 0.45, ease: "easeOut" }}
            >
              Watch a gene
              <br />
              grow up.
            </motion.h1>
            <motion.p
              className="hero-sub"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.18, duration: 0.4 }}
            >
              Trace the expression of any of{" "}
              {stats ? stats.genes.toLocaleString("en-US") : "60,155"} genes across human
              brain development — from 6 weeks post-conception to
              adulthood, LOESS-smoothed with confidence intervals.
            </motion.p>
            {chipRow(false)}
            <svg className="hero-curve" viewBox="0 0 900 220" aria-hidden="true" preserveAspectRatio="none">
              <motion.path
                d="M20,200 C180,195 240,60 380,50 C470,44 520,86 640,92 C760,98 830,70 880,62"
                fill="none"
                stroke="#3987E5"
                strokeWidth="2"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 0.5 }}
                transition={{ delay: 0.3, duration: 2.4, ease: "easeInOut" }}
              />
            </svg>
          </section>
        )}

        {gene && (
          <>
            <section className="gene-head">
              <div className="gene-title-row">
                <div>
                  <motion.h1
                    key={gene.symbol}
                    className="gene-title"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    {gene.symbol}
                  </motion.h1>
                  <div className="gene-sub">
                    {gene.name && <span className="gene-name">{gene.name}</span>}
                    <span className="gene-id">{gene.ensembl}</span>
                  </div>
                </div>
                {chipRow(true)}
              </div>
            </section>

            {shown && <StatTiles stats={shown.trajectory.stats} geneKey={gene.ensembl} />}

            <section className="chart-card" ref={chartAreaRef}>
              <div className="chart-head">
                <div>
                  <div className="chart-title">Expression trajectory</div>
                  <div className="chart-meta">
                    LOESS · span 0.75 · degree 2 · 95% CI · log₂(CPM + 0.001)
                  </div>
                </div>
                <div className="chart-controls">
                  <div className="segmented" role="group" aria-label="Point coloring">
                    <button
                      type="button"
                      className={splitSex ? "" : "is-on"}
                      aria-pressed={!splitSex}
                      onClick={() => setSplitSex(false)}
                    >
                      All samples
                    </button>
                    <button
                      type="button"
                      className={splitSex ? "is-on" : ""}
                      aria-pressed={splitSex}
                      onClick={() => setSplitSex(true)}
                    >
                      By sex
                    </button>
                  </div>
                  <button
                    type="button"
                    className="ghost-btn"
                    disabled={!shown}
                    onClick={() => {
                      // Reported rather than swallowed: the export failing
                      // silently is what hid the production CSP bug.
                      exportChartPng(
                        chartAreaRef.current,
                        `brainvar_${gene.ensembl}_${gene.symbol}.png`,
                      ).then(
                        // Only once the file is actually produced: a failed
                        // export is not an export, and the log should not
                        // claim otherwise.
                        () => reportExport(gene.symbol),
                      ).catch((err: unknown) =>
                        setError(
                          err instanceof Error
                            ? `Could not save the PNG. ${err.message}`
                            : "Could not save the PNG.",
                        ),
                      );
                    }}
                  >
                    Download PNG
                  </button>
                </div>
              </div>

              {splitSex && shown && (
                <div className="legend" aria-hidden="false">
                  {shown.trajectory.series.map((s) => (
                    <span className="legend-item" key={s.key}>
                      <span
                        className="legend-key"
                        style={{ background: s.key === "Male" ? "#D95926" : "#3987E5" }}
                      />
                      {s.key}
                      <span className="legend-n">n={s.points.length}</span>
                    </span>
                  ))}
                </div>
              )}

              <AnimatePresence mode="popLayout">
                {(shown || previous) && (
                  <motion.div
                    key={`chart-${theme}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.25 }}
                  >
                    {/* Identity props come from the loaded data, so a dimmed
                        stale frame stays labeled as the gene actually plotted */}
                    <ExpressionChart
                      trajectory={(shown ?? { trajectory: previous! }).trajectory}
                      symbol={data!.gene.symbol}
                      ensembl={data!.gene.ensembl}
                      splitSex={splitSex}
                      stale={stale}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
              {!shown && !previous && <div className="chart-skeleton">Loading expression…</div>}
            </section>

            {shown && <SampleTable points={shown.trajectory.points} symbol={gene.symbol} />}
          </>
        )}
      </main>

      <footer className="footer">
        <p>
          Data: BrainVar — bulk RNA-seq of developing human cortex, 176 samples spanning 6
          post-conception weeks to adulthood. Trend: LOESS (span 0.75, degree 2) with 95%
          pointwise confidence intervals, computed server-side in numpy and verified
          against skmisc.loess to 1e-13. Expression:
          log₂(CPM + 0.001), age log-scaled — matching the original analysis script.
        </p>
      </footer>
    </div>
  );
}
