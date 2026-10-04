import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { hasPerm, PERMISSIONS } from "../../lib/auth";
import { useAuth } from "../../lib/authContext";
import { ThemeToggle } from "../../components/ThemeToggle";
import { TopBarNav } from "../../components/TopBarNav";

/**
 * Shell shared by the admin pages: top bar and the tab strip.
 *
 * Each tab is shown only when the account holds the permission that gates the
 * route behind it, so someone granted the audit permission alone lands on a
 * panel with one tab rather than on a link that 403s.
 */
export function AdminChrome({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();

  const canViewUsers = hasPerm(user, PERMISSIONS.viewUsers);
  const canViewActivity = hasPerm(user, PERMISSIONS.viewAuditLogs);
  const tabs = [
    { to: "/admin", label: "Manage users", show: canViewUsers, end: true },
    { to: "/admin/activity", label: "Activity", show: canViewActivity, end: false },
  ].filter((t) => t.show);

  return (
    <div className="app">
      <div className="bg-glow" aria-hidden="true" />

      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand-mark" aria-hidden="true" />
          BrainVar
          <span className="brand-sub">Admin</span>
        </a>
        <div className="topbar-spacer" />
        <TopBarNav trailing={<ThemeToggle />}>
          <a className="topbar-docs" href="/">
            Explorer
          </a>
          <a className="topbar-docs" href="/docs">
            Docs
          </a>
          {user && (
            <button
              type="button"
              className="topbar-signout"
              onClick={() => void signOut()}
              title={`Signed in as ${user.email}`}
            >
              Sign out
            </button>
          )}
        </TopBarNav>
      </header>

      {/* One tab is not a choice, so the strip only appears when there are two. */}
      {tabs.length > 1 && (
        <nav className="admin-tabs" aria-label="Admin sections">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) => `admin-tab${isActive ? " is-active" : ""}`}
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      )}

      <main>{children}</main>
    </div>
  );
}
