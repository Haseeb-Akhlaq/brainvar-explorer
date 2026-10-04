import { NavLink } from "react-router-dom";
import * as icons from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { DocsSection } from "../../lib/docs/types";

interface Props {
  sections: DocsSection[];
  onNavigate?: () => void;
}

/** Resolve an icon name from _meta.json to a lucide component. */
function iconFor(name: string | undefined): LucideIcon {
  const set = icons as unknown as Record<string, LucideIcon>;
  return (name && set[name]) || icons.FileText;
}

export function DocsSidebar({ sections, onNavigate }: Props) {
  return (
    <nav className="docs-sidebar" aria-label="Documentation">
      {sections.map((section) => {
        const Icon = iconFor(section.icon);
        return (
          <div className="docs-section" key={section.slug}>
            <div className="docs-section-title">
              <Icon size={15} aria-hidden="true" />
              {section.title}
            </div>
            <ul>
              {section.pages.map((page) => (
                <li key={page.id}>
                  <NavLink
                    to={page.path}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      `docs-link${isActive ? " is-active" : ""}`
                    }
                  >
                    {page.title}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
