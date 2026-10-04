import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../lib/authContext";

/**
 * Gate for the pages that show data.
 *
 * This is convenience, not security — the API enforces access on every
 * request. It exists so an unauthenticated visitor sees a login form instead
 * of a page full of failed requests.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Nothing is known until the session check resolves; rendering the login
  // page here would make it flash for users who are already signed in.
  if (loading) return <div className="auth-splash">Loading…</div>;

  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;

  return <>{children}</>;
}
