import type { ReactNode } from "react";

import { hasPerm } from "../lib/auth";
import { useAuth } from "../lib/authContext";
import { RequireAuth } from "./RequireAuth";

/**
 * Gate for a route that needs a permission as well as a session.
 *
 * Wraps RequireAuth, so an anonymous visitor is sent to the login page and
 * only a signed-in one without the right is told no — otherwise someone who
 * has simply been logged out by an expired session would be told they lack
 * access, which is the wrong diagnosis.
 *
 * As with RequireAuth this is presentation. The permission is enforced on
 * every request by the API; editing it in devtools yields a page whose only
 * content is a 403.
 */
export function RequirePermission({
  permission,
  children,
}: {
  permission: string;
  children: ReactNode;
}) {
  return (
    <RequireAuth>
      <PermissionGate permission={permission}>{children}</PermissionGate>
    </RequireAuth>
  );
}

function PermissionGate({ permission, children }: { permission: string; children: ReactNode }) {
  const { user } = useAuth();

  if (!hasPerm(user, permission)) {
    return (
      <div className="app">
        <div className="denied-card" role="alert">
          <h1>Not available to your account</h1>
          <p>
            This page needs the <code>{permission}</code> permission. Ask an
            administrator to grant it, then sign in again.
          </p>
          <a className="denied-back" href="/">
            Back to the explorer
          </a>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
