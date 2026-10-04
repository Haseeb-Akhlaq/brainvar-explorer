import { useEffect, useId, useState } from "react";

import { useDocumentTheme } from "../../lib/useDocumentTheme";

interface Props {
  chart: string;
}

let mermaidReady: Promise<typeof import("mermaid").default> | null = null;

/**
 * Mermaid is ~500 KB, so it is imported dynamically the first time a diagram
 * appears rather than bundled into the main chunk.
 */
function loadMermaid() {
  mermaidReady ??= import("mermaid").then(({ default: mermaid }) => mermaid);
  return mermaidReady;
}

export function MermaidDiagram({ chart }: Props) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Mermaid needs a unique DOM id; useId is stable across renders and
  // does not reach for an impure source during render.
  const domId = `mermaid-${useId().replace(/:/g, "")}`;
  const theme = useDocumentTheme();

  useEffect(() => {
    let cancelled = false;
    loadMermaid()
      .then((mermaid) => {
        // initialize is re-run per render so a theme change is picked up.
        mermaid.initialize({
          startOnLoad: false,
          theme: theme === "dark" ? "dark" : "default",
          securityLevel: "strict",
          fontFamily: "inherit",
        });
        return mermaid.render(domId, chart);
      })
      .then(({ svg }) => {
        if (!cancelled) setSvg(svg);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not render diagram");
      });
    return () => {
      cancelled = true;
    };
  }, [chart, domId, theme]);

  if (error) {
    // Show the source rather than nothing, so the content is not lost.
    return (
      <pre className="mermaid-error">
        <code>{chart}</code>
      </pre>
    );
  }

  return svg ? (
    <div className="mermaid-diagram" dangerouslySetInnerHTML={{ __html: svg }} />
  ) : (
    <div className="mermaid-loading">Rendering diagram…</div>
  );
}
