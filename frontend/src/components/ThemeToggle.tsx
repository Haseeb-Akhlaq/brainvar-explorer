import { useEffect, useState } from "react";

import { applyTheme, initTheme, persistTheme, storedTheme, systemTheme, type Theme } from "../lib/theme";

/**
 * Light/dark switch.
 *
 * Reads the theme already applied to <html> rather than choosing again, so the
 * button agrees with what is on screen from the first render.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.dataset.theme as Theme | undefined) ?? initTheme(),
  );

  // Follow the system preference until an explicit choice has been made.
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: light)");
    if (!media) return;

    const onChange = () => {
      if (storedTheme()) return;
      const next = systemTheme();
      applyTheme(next);
      setTheme(next);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    persistTheme(next);
    setTheme(next);
  };

  const label = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={label}
      title={label}
    >
      {theme === "dark" ? (
        // Sun: clicking moves to the light theme.
        <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true">
          <circle cx="10" cy="10" r="3.6" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            <line x1="10" y1="1.6" x2="10" y2="3.6" />
            <line x1="10" y1="16.4" x2="10" y2="18.4" />
            <line x1="1.6" y1="10" x2="3.6" y2="10" />
            <line x1="16.4" y1="10" x2="18.4" y2="10" />
            <line x1="4.2" y1="4.2" x2="5.6" y2="5.6" />
            <line x1="14.4" y1="14.4" x2="15.8" y2="15.8" />
            <line x1="15.8" y1="4.2" x2="14.4" y2="5.6" />
            <line x1="5.6" y1="14.4" x2="4.2" y2="15.8" />
          </g>
        </svg>
      ) : (
        // Moon: clicking moves to the dark theme.
        <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true">
          <path
            d="M16.2 12.4A6.8 6.8 0 0 1 7.6 3.8a6.8 6.8 0 1 0 8.6 8.6Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}
