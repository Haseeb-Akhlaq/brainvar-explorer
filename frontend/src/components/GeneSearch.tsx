import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { searchGenes, type GeneRef } from "../lib/data";

interface Props {
  onSelect: (gene: GeneRef) => void;
}

/** Wait this long after the last keystroke before querying the API. */
const DEBOUNCE_MS = 150;

/** Range used to draw the tiny mean-expression bar in each result row. */
const MEAN_LOG2_MIN = -10;
const MEAN_LOG2_MAX = 14;

export function GeneSearch({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [fetched, setFetched] = useState<{ query: string; genes: GeneRef[] } | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  // Debounced server-side search. The in-flight request is aborted whenever the
  // query changes, so results can never arrive out of order.
  useEffect(() => {
    const q = query.trim();
    // Nothing to search for. The empty case is handled during render instead
    // of by clearing state here, which would trigger a cascading re-render.
    if (!q) return;

    const controller = new AbortController();
    const timer = setTimeout(() => {
      searchGenes(q, 8, controller.signal)
        .then((genes) => setFetched({ query: q, genes }))
        .catch(() => {
          /* aborted or offline — leave the previous results in place */
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  // ⌘K / "/" focuses the search from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const inField =
        document.activeElement instanceof HTMLInputElement ||
        document.activeElement instanceof HTMLTextAreaElement;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      } else if (e.key === "/" && !inField) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Click outside closes the dropdown.
  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", onDown);
    return () => window.removeEventListener("pointerdown", onDown);
  }, []);

  const choose = (gene: GeneRef) => {
    onSelect(gene);
    setQuery("");
    setOpen(false);
    // Focus stays in the combobox (ARIA pattern): next Tab moves forward
    // into the page instead of restarting from <body>.
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      choose(results[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const trimmed = query.trim();
  // Stale results from a previous query must not be shown against a new one.
  const isCurrent = fetched !== null && fetched.query === trimmed;
  const results = isCurrent ? fetched.genes : [];
  const showEmpty = open && trimmed.length > 0 && isCurrent && results.length === 0;

  return (
    <div className="search" ref={rootRef}>
      <div className="search-box">
        <svg className="search-icon" viewBox="0 0 20 20" aria-hidden="true">
          <circle cx="9" cy="9" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <line x1="13.5" y1="13.5" x2="17.5" y2="17.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <input
          ref={inputRef}
          value={query}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open && (results.length > 0 || !!showEmpty)}
          aria-controls="gene-search-listbox"
          aria-activedescendant={
            open && results.length > 0 && results[active]
              ? `gene-opt-${results[active].ensembl}`
              : undefined
          }
          aria-label="Search genes"
          placeholder="Search a gene — SCN2A, XIST…"
          spellCheck={false}
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
        <kbd className="search-kbd">⌘K</kbd>
      </div>
      <AnimatePresence>
        {open && (results.length > 0 || showEmpty) && (
          <motion.ul
            id="gene-search-listbox"
            role="listbox"
            className="search-results"
            initial={{ opacity: 0, y: -6, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.995 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
          >
            {showEmpty ? (
              <li className="search-none" role="option" aria-disabled={true} aria-selected={false}>
                No gene matches “{query.trim()}”. Try a symbol like SCN2A or an
                Ensembl id like ENSG00000136531.
              </li>
            ) : (
              results.map((r, i) => {
                const frac = Math.min(
                  1,
                  Math.max(0, (r.meanLog2 - MEAN_LOG2_MIN) / (MEAN_LOG2_MAX - MEAN_LOG2_MIN)),
                );
                return (
                  <li
                    key={r.ensembl + r.symbol}
                    id={`gene-opt-${r.ensembl}`}
                    role="option"
                    aria-selected={i === active}
                    className={`search-row${i === active ? " is-active" : ""}`}
                    onPointerEnter={() => setActive(i)}
                    onPointerDown={(e) => {
                      e.preventDefault();
                      choose(r);
                    }}
                  >
                    <span className="search-symbol">{r.symbol}</span>
                    <span className="search-name">{r.name || r.ensembl}</span>
                    <span className="search-meter" title={`mean log2 CPM ${r.meanLog2}`}>
                      <span style={{ width: `${Math.round(frac * 100)}%` }} />
                    </span>
                  </li>
                );
              })
            )}
          </motion.ul>
        )}
      </AnimatePresence>
      <div role="status" className="visually-hidden">
        {showEmpty ? `No gene matches ${query.trim()}` : ""}
      </div>
    </div>
  );
}
