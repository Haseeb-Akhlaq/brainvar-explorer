import { useMemo } from "react";

import type { Theme } from "./theme";
import { useDocumentTheme } from "./useDocumentTheme";

/**
 * Chart colours resolved from the CSS custom properties on <html>.
 *
 * The SVG sets fill and stroke as attributes, which cannot take `var(…)`
 * reliably and would not survive PNG export, so the values are resolved to
 * concrete hex here. index.css stays the single source of truth.
 *
 * The read happens during render, keyed on the theme, rather than inside the
 * MutationObserver that detects the change: that callback is a microtask and
 * runs before the style engine has recalculated, so it would read the previous
 * theme's values and appear to do nothing.
 */
export interface ChartColors {
  surface: string;
  ink: string;
  ink2: string;
  ink3: string;
  grid: string;
  baseline: string;
  birth: string;
  prenatal: string;
  /** "rgba(r,g,b" — an alpha and ")" are appended per use. */
  bandTint: string;
  series: { all: string; Female: string; Male: string };
}

/** Used only if a custom property is missing, e.g. during a test render. */
const FALLBACKS: Record<Theme, ChartColors> = {
  dark: {
    surface: "#171f2e",
    ink: "#f2f4f7",
    ink2: "#d0d5dd",
    ink3: "#98a2b3",
    grid: "#1d2939",
    baseline: "#344054",
    birth: "#98a2b3",
    prenatal: "#7592ff",
    bandTint: "rgba(255,255,255",
    series: { all: "#3987e5", Female: "#3987e5", Male: "#d95926" },
  },
  light: {
    surface: "#ffffff",
    ink: "#101828",
    ink2: "#344054",
    ink3: "#667085",
    grid: "#e4e7ec",
    baseline: "#d0d5dd",
    birth: "#667085",
    prenatal: "#465fff",
    bandTint: "rgba(16,24,40",
    series: { all: "#1f63b8", Female: "#1f63b8", Male: "#b2431a" },
  },
};

function read(theme: Theme): ChartColors {
  const fallback = FALLBACKS[theme];
  const style = getComputedStyle(document.documentElement);
  const token = (name: string, value: string) =>
    style.getPropertyValue(name).trim() || value;

  const seriesOne = token("--series-1", fallback.series.all);
  return {
    surface: token("--surface", fallback.surface),
    ink: token("--ink", fallback.ink),
    ink2: token("--ink-2", fallback.ink2),
    ink3: token("--ink-3", fallback.ink3),
    grid: token("--chart-grid", fallback.grid),
    baseline: token("--chart-baseline", fallback.baseline),
    birth: token("--chart-birth", fallback.birth),
    prenatal: token("--chart-prenatal", fallback.prenatal),
    bandTint: fallback.bandTint,
    series: {
      all: seriesOne,
      Female: seriesOne,
      Male: token("--series-2", fallback.series.Male),
    },
  };
}

export function useThemeColors(): ChartColors {
  const theme = useDocumentTheme();
  return useMemo(() => read(theme), [theme]);
}
