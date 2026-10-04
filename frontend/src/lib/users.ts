/**
 * Client for the account-administration endpoints.
 *
 * Separate from data.ts because it is a different resource with a different
 * guard: the gene endpoints need a session, these need the matching
 * `users.*` model permission on top of one.
 */

import { getJson, sendJson } from "./api";

export interface AccountRow {
  id: number;
  email: string;
  fullName: string;
  orcid: string;
  isActive: boolean;
  isStaff: boolean;
  isSuperuser: boolean;
  /** Group names, for display. */
  groups: string[];
  /** Group ids, for the edit form. */
  groupIds: number[];
  /**
   * False for an account created through this panel, which is made without
   * a password. Such an account cannot sign in even once marked active.
   */
  hasPassword: boolean;
  /** When the welcome email was last sent, or null if never invited. */
  invitedAt: string | null;
  dateJoined: string;
  lastLogin: string | null;
}

export interface GroupRef {
  id: number;
  name: string;
}

/** The editable fields. `is_staff` / `is_superuser` are not among them. */
export interface AccountInput {
  email: string;
  fullName: string;
  orcid: string;
  groupIds: number[];
  isActive?: boolean;
}

interface AccountWire {
  id: number;
  email: string;
  full_name: string;
  orcid: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  groups: string[];
  group_ids: number[];
  has_usable_password: boolean;
  invited_at: string | null;
  date_joined: string;
  last_login: string | null;
}

function toAccount(a: AccountWire): AccountRow {
  return {
    id: a.id,
    email: a.email,
    fullName: a.full_name,
    orcid: a.orcid,
    isActive: a.is_active,
    isStaff: a.is_staff,
    isSuperuser: a.is_superuser,
    groups: a.groups,
    groupIds: a.group_ids,
    hasPassword: a.has_usable_password,
    invitedAt: a.invited_at,
    dateJoined: a.date_joined,
    lastLogin: a.last_login,
  };
}

function toWire(input: AccountInput) {
  return {
    email: input.email,
    full_name: input.fullName,
    orcid: input.orcid,
    groups: input.groupIds,
    ...(input.isActive === undefined ? {} : { is_active: input.isActive }),
  };
}

/**
 * Every account, ordered by email.
 *
 * Throws ApiError with status 403 when the session lacks `users.view_user` —
 * which is the real access control; the hidden button is only tidiness.
 */
export async function fetchAccounts(signal?: AbortSignal): Promise<AccountRow[]> {
  const data = await getJson<{ count: number; results: AccountWire[] }>("/users/", signal);
  return data.results.map(toAccount);
}

/** The groups an account can belong to. Needs `auth.view_group`. */
export async function fetchGroups(signal?: AbortSignal): Promise<GroupRef[]> {
  const data = await getJson<{ count: number; results: GroupRef[] }>("/groups/", signal);
  return data.results;
}

/**
 * Create an account. Needs `users.add_user`.
 *
 * The server makes it inactive and without a password regardless of what is
 * sent, so the caller cannot produce an account that can sign in.
 */
export async function createAccount(input: AccountInput): Promise<void> {
  await sendJson("POST", "/users/", toWire(input));
}

/** Needs `users.change_user`. */
export async function updateAccount(id: number, input: AccountInput): Promise<void> {
  await sendJson("PATCH", `/users/${id}/`, toWire(input));
}

/**
 * Toggle the active flag alone, without touching anything else on the row.
 *
 * Rejected by the server if it would leave nobody able to manage users.
 */
export async function setAccountActive(id: number, isActive: boolean): Promise<void> {
  await sendJson("PATCH", `/users/${id}/`, { is_active: isActive });
}

/** Needs `users.delete_user`. Refused for your own account and the last admin. */
export async function deleteAccount(id: number): Promise<void> {
  await sendJson("DELETE", `/users/${id}/`);
}

/**
 * Send (or re-send) the welcome email.
 *
 * The server generates the password, activates the account and emails the
 * credentials — nothing secret comes back here, which is why this returns the
 * refreshed row rather than anything to display.
 *
 * Needs `users.change_user`: an invitation resets an existing account's
 * credentials, so it is a change rather than a creation.
 */
export async function sendInvitation(id: number): Promise<AccountRow> {
  const row = await sendJson<AccountWire>("POST", `/users/${id}/invite/`);
  if (!row) throw new Error("The server returned no account.");
  return toAccount(row);
}
