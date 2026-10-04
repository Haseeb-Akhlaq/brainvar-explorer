/**
 * Theme selection, shared by the explorer and the documentation.
 *
 * The choice is stored on <html data-theme="…">, which both stylesheets key
 * off, and remembered in localStorage. With nothing stored, the operating
 * system preference decides.
 */

export type Theme = "light" | "dark";

const STORAGE_KEY = "brainvar-theme";

export function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function storedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    // Private browsing or blocked storage — fall back to the system preference.
    return null;
  }
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function persistTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Not fatal: the theme still applies for this page view.
  }
}

/** Called before React mounts so the first paint is already correct. */
export function initTheme(): Theme {
  const theme = storedTheme() ?? systemTheme();
  applyTheme(theme);
  return theme;
}
