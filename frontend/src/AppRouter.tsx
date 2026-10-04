import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./lib/AuthProvider";
import { RequireAuth } from "./components/RequireAuth";
import { RequirePermission } from "./components/RequirePermission";
import { PERMISSIONS } from "./lib/auth";

// The docs pull in shiki and mermaid, so they are split out of the main bundle
// and only fetched when someone visits /docs.
const DocsPage = lazy(() => import("./pages/docs/DocsPage"));
const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
// Split out too: most sessions never open it.
const AdminPage = lazy(() => import("./pages/admin/AdminPage"));
const ActivityPage = lazy(() => import("./pages/admin/ActivityPage"));

const suspend = (node: React.ReactNode) => (
  <Suspense fallback={<div className="auth-splash">Loading…</div>}>{node}</Suspense>
);

export function AppRouter() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={suspend(<LoginPage />)} />

          {/* The explorer keeps its hash deep links (#SCN2A); the hash is
              independent of the path, so routing does not disturb them. */}
          <Route
            path="/"
            element={
              <RequireAuth>
                <App />
              </RequireAuth>
            }
          />

          {/* Gated on the `users.view_user` permission. Django's own admin
              is on the API host, so this path is free on the app host. */}
          <Route
            path="/admin"
            element={
              <RequirePermission permission={PERMISSIONS.viewUsers}>
                {suspend(<AdminPage />)}
              </RequirePermission>
            }
          />

          {/* Gated on the audit permission rather than on view_user: reading
              everyone's activity is a separate power from managing accounts,
              and either can be granted without the other. */}
          <Route
            path="/admin/activity"
            element={
              <RequirePermission permission={PERMISSIONS.viewAuditLogs}>
                {suspend(<ActivityPage />)}
              </RequirePermission>
            }
          />

          {/* The documentation describes the interface rather than exposing
              data, so it is readable without a session. */}
          <Route path="/docs" element={suspend(<DocsPage />)} />
          <Route path="/docs/:section/:page" element={suspend(<DocsPage />)} />

          <Route
            path="*"
            element={
              <RequireAuth>
                <App />
              </RequireAuth>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
