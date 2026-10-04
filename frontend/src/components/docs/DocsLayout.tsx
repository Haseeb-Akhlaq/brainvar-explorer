import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { Menu, Search, X } from "lucide-react";

import {
  extractHeadings,
  getAllSections,
  getFirstPage,
  getNavigation,
  getPage,
} from "../../lib/docs/loader";
import { DocsContent } from "./DocsContent";
import { DocsSearchDialog } from "./DocsSearchDialog";
import { DocsSidebar } from "./DocsSidebar";
import { DocsTableOfContents } from "./DocsTableOfContents";
import { API_DOCS_URL } from "../../lib/data";
import { ThemeToggle } from "../ThemeToggle";

export function DocsLayout() {
  const { section, page: pageSlug } = useParams();
  const [searchOpen, setSearchOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  const sections = getAllSections();
  const page = section && pageSlug ? getPage(section, pageSlug) : null;

  const headings = useMemo(() => (page ? extractHeadings(page.content) : []), [page]);
  const navigation = useMemo(
    () => (page ? getNavigation(page) : { prev: null, next: null }),
    [page],
  );

  // Cmd/Ctrl-K opens search from anywhere on the page.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // A new page should start at the top, not wherever the last one was
  // scrolled. The mobile nav is closed by the link handler instead, so this
  // effect only touches the window.
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [section, pageSlug]);

  // Bare /docs redirects to the first page in the first section.
  if (!section || !pageSlug) {
    const first = getFirstPage();
    return first ? <Navigate to={first.path} replace /> : <p>No documentation found.</p>;
  }

  if (!page) {
    return (
      <div className="docs-missing">
        <h1>Page not found</h1>
        <p>
          No documentation page at <code>{`/docs/${section}/${pageSlug}`}</code>.
        </p>
        <Link to="/docs">Back to the documentation</Link>
      </div>
    );
  }

  return (
    <div className="docs">
      <header className="docs-topbar">
        <button
          type="button"
          className="docs-nav-toggle"
          aria-label={navOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={navOpen}
          onClick={() => setNavOpen((v) => !v)}
        >
          {navOpen ? <X size={18} /> : <Menu size={18} />}
        </button>

        <Link className="docs-brand" to="/">
          <span className="brand-mark" aria-hidden="true" />
          BrainVar
          <span className="brand-sub">Documentation</span>
        </Link>

        <button type="button" className="docs-search-trigger" onClick={() => setSearchOpen(true)}>
          <Search size={15} aria-hidden="true" />
          <span>Search</span>
          <kbd>⌘K</kbd>
        </button>

        <a
          className="docs-app-link"
          href={API_DOCS_URL}
          target="_blank"
          rel="noreferrer noopener"
        >
          API
        </a>

        <Link className="docs-app-link" to="/">
          Open the app
        </Link>

        <ThemeToggle />
      </header>

      <div className={`docs-body${navOpen ? " nav-open" : ""}`}>
        <DocsSidebar sections={sections} onNavigate={() => setNavOpen(false)} />
        <main className="docs-main">
          <DocsContent page={page} prev={navigation.prev} next={navigation.next} />
        </main>
        <DocsTableOfContents headings={headings} />
      </div>

      {searchOpen && <DocsSearchDialog onClose={() => setSearchOpen(false)} />}
    </div>
  );
}
