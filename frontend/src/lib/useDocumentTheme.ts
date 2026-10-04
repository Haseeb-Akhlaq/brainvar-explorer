import { useEffect, useState } from "react";

import type { Theme } from "./theme";

/**
 * The theme currently applied to <html>.
 *
 * Components that need to re-render on a theme change — the syntax
 * highlighter and mermaid, which bake colours into their output — subscribe
 * here rather than having the theme threaded down to them.
 */
export function useDocumentTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.dataset.theme as Theme | undefined) ?? "dark",
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme((document.documentElement.dataset.theme as Theme | undefined) ?? "dark");
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => observer.disconnect();
  }, []);

  return theme;
}
