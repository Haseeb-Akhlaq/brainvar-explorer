import { motion } from "motion/react";
import type { GeneStats } from "../lib/trajectory";
import { PERIOD_NAMES } from "../lib/milestones";
import { formatAge, formatFold, formatLog2 } from "../lib/format";

interface Props {
  stats: GeneStats;
  geneKey: string;
}

export function StatTiles({ stats, geneKey }: Props) {
  const peakAge = formatAge(Math.pow(2, stats.peakX));
  const shiftFold = formatFold(stats.birthShift);
  const postnatalUp = stats.birthShift > 0;
  const flat = Math.abs(stats.birthShift) < 0.263; // < 1.2× either way

  const tiles = [
    {
      label: "Peak of the trend",
      value: formatLog2(stats.peakLog2),
      unit: "log₂ CPM",
      note: `P${stats.peakPeriod} · ${PERIOD_NAMES[stats.peakPeriod] ?? ""} · ${peakAge}`,
    },
    {
      label: "Across birth",
      value: flat ? "steady" : shiftFold,
      unit: flat ? "" : postnatalUp ? "higher after" : "higher before",
      note: flat
        ? "similar prenatal and postnatal levels"
        : postnatalUp
          ? "rises into postnatal life"
          : "prenatal-biased expression",
    },
    {
      label: "Detected in",
      value: `${Math.round(stats.detectedFraction * 100)}%`,
      unit: "of samples",
      note: "CPM ≥ 1",
    },
    {
      label: "Samples",
      value: String(stats.nPrenatal + stats.nPostnatal),
      unit: "",
      note: `${stats.nPrenatal} prenatal · ${stats.nPostnatal} postnatal`,
    },
  ];

  return (
    <div className="stat-row" key={geneKey}>
      {tiles.map((t, i) => (
        <motion.div
          className="stat-tile"
          key={t.label}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 + i * 0.06, duration: 0.35, ease: "easeOut" }}
        >
          <div className="stat-label">{t.label}</div>
          <div className="stat-value">
            {t.value}
            {t.unit && <span className="stat-unit"> {t.unit}</span>}
          </div>
          <div className="stat-note">{t.note}</div>
        </motion.div>
      ))}
    </div>
  );
}
