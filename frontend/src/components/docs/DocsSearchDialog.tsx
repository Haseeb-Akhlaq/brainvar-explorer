import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";

import { searchDocs } from "../../lib/docs/loader";

interface Props {
  onClose: () => void;
}

/**
 * Rendered only while open, so it mounts fresh each time and its state starts
 * empty without an effect having to reset it.
 */
export function DocsSearchDialog({ onClose }: Props) {
  const [query, setQuery] = useState("");
  const [requestedActive, setRequestedActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // The index is built at module load, so searching is synchronous.
  const results = useMemo(() => searchDocs(query), [query]);

  // Derived rather than reset in an effect: a shorter result list simply
  // clamps the highlighted row instead of triggering another render.
  const active = Math.min(requestedActive, Math.max(results.length - 1, 0));

  useEffect(() => {
    // Focus once the dialog has painted.
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    return () => clearTimeout(t);
  }, []);

  const choose = (path: string) => {
    navigate(path);
    onClose();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setRequestedActive(Math.min(active + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setRequestedActive(Math.max(active - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      choose(results[active].page.path);
    }
  };

  return (
    <div className="docs-search-backdrop" onClick={onClose} role="presentation">
      <div
        className="docs-search-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Search documentation"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="docs-search-box">
          <Search size={16} aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setRequestedActive(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search the documentation…"
            aria-label="Search documentation"
            spellCheck={false}
            autoComplete="off"
          />
          <kbd>Esc</kbd>
        </div>

        {query.trim().length >= 2 && (
          <ul className="docs-search-results" role="listbox">
            {results.length === 0 ? (
              <li className="docs-search-none">No matches for “{query.trim()}”</li>
            ) : (
              results.map((r, i) => (
                <li key={r.page.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={i === active}
                    className={i === active ? "is-active" : ""}
                    onMouseEnter={() => setRequestedActive(i)}
                    onClick={() => choose(r.page.path)}
                  >
                    <span className="docs-search-section">{r.sectionTitle}</span>
                    <span className="docs-search-title">{r.page.title}</span>
                    <span className="docs-search-excerpt">{r.excerpt}</span>
                  </button>
                </li>
              ))
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
