import { useEffect, useState } from "react";
import type { TocHeading } from "../../lib/docs/types";

interface Props {
  headings: TocHeading[];
}

/**
 * On-page contents, with the visible heading highlighted.
 *
 * Uses IntersectionObserver rather than scroll offsets so it stays correct
 * when images or diagrams change the layout after load.
 */
export function DocsTableOfContents({ headings }: Props) {
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      // Only count headings in the upper part of the viewport, so the
      // highlight tracks what is being read rather than what is scrolling in.
      { rootMargin: "0px 0px -70% 0px", threshold: 1 },
    );

    for (const { id } of headings) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [headings]);

  if (headings.length < 2) return null;

  return (
    <aside className="docs-toc" aria-label="On this page">
      <div className="docs-toc-title">On this page</div>
      <ul>
        {headings.map((h) => (
          <li key={h.id} className={h.level === 3 ? "is-sub" : ""}>
            <a
              href={`#${h.id}`}
              className={h.id === activeId ? "is-active" : ""}
              onClick={(e) => {
                // Scroll smoothly and keep the hash out of the router.
                e.preventDefault();
                document.getElementById(h.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                setActiveId(h.id);
              }}
            >
              {h.text}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
