/**
 * Session authentication against the Django backend.
 *
 * The session lives in an HttpOnly cookie the browser sends automatically —
 * nothing is kept in localStorage, so a cross-site script cannot read the
 * credential. Every request therefore needs `credentials: "include"`, and
 * every unsafe request needs the CSRF token Django issued.
 */

import { API, ensureCsrfToken } from "./api";

export interface User {
  id: number;
  email: string;
  fullName: string;
  orcid: string;
  isStaff: boolean;
  /** Django model permissions, as `app_label.codename`. */
  permissions: string[];
}

/**
 * Permission codenames this app branches on.
 *
 * Named constants rather than string literals at the call sites: a typo in
 * `"users.view_user"` fails open in the sense that matters — the control
 * simply never appears, with nothing to notice in a review.
 */
export const PERMISSIONS = {
  viewUsers: "users.view_user",
  addUser: "users.add_user",
  changeUser: "users.change_user",
  deleteUser: "users.delete_user",
  // Separate from viewUsers: managing accounts does not imply the right to
  // read everyone's activity, so the panel gates the two tabs independently.
  viewAuditLogs: "users.view_audit_logs",
} as const;

interface UserWire {
  id: number;
  email: string;
  full_name: string;
  orcid: string;
  is_staff: boolean;
  permissions?: string[];
}

function toUser(u: UserWire): User {
  return {
    id: u.id,
    email: u.email,
    fullName: u.full_name,
    orcid: u.orcid,
    isStaff: u.is_staff,
    // Absent on an older backend; an empty list hides the gated controls,
    // which is the safe direction to fail.
    permissions: u.permissions ?? [],
  };
}

/**
 * Whether a user holds a permission.
 *
 * Deliberately a permission check and not a group or `isStaff` check — it
 * mirrors what the API enforces, so the interface and the server agree on who
 * may do what. Presentation only: the API re-checks on every request, so a
 * forged answer here buys a page that fails with 403.
 */
export function hasPerm(user: User | null, permission: string): boolean {
  return user?.permissions.includes(permission) ?? false;
}

export class AuthError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

/** The signed-in user, or null when there is no session. */
export async function fetchCurrentUser(): Promise<User | null> {
  const res = await fetch(`${API}/api/auth/me/`, { credentials: "include" });
  if (res.status === 401 || res.status === 403) return null;
  if (!res.ok) throw new AuthError("Could not reach the server.", res.status);
  return toUser(await res.json());
}

export async function login(email: string, password: string): Promise<User> {
  const token = await ensureCsrfToken();

  const res = await fetch(`${API}/api/auth/login/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    let detail = "Could not sign in. Please try again.";
    try {
      const body = await res.json();
      // DRF reports either {detail: …} or {field: [messages]}.
      detail =
        body.detail ??
        (Array.isArray(body.non_field_errors) ? body.non_field_errors[0] : null) ??
        (Array.isArray(body.email) ? `Email: ${body.email[0]}` : null) ??
        (Array.isArray(body.password) ? `Password: ${body.password[0]}` : null) ??
        detail;
    } catch {
      // Non-JSON body — keep the generic message.
    }
    throw new AuthError(detail, res.status);
  }
  return toUser(await res.json());
}

export async function logout(): Promise<void> {
  const token = await ensureCsrfToken();
  await fetch(`${API}/api/auth/logout/`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRFToken": token },
  });
}
