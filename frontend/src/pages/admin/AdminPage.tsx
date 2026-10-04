import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Mail, Pencil, Plus, Search, Trash2 } from "lucide-react";

import { ApiError } from "../../lib/api";
import { hasPerm, PERMISSIONS } from "../../lib/auth";
import { useAuth } from "../../lib/authContext";
import {
  fetchAccounts,
  fetchGroups,
  setAccountActive,
  type AccountRow,
  type GroupRef,
} from "../../lib/users";
import { AdminChrome } from "./AdminChrome";
import { UserFormModal } from "./UserFormModal";
import { DeleteUserModal } from "./DeleteUserModal";
import { InviteUserModal } from "./InviteUserModal";

/** "6 Sept 2026", or a dash for a user who has never signed in. */
function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

type Dialog =
  | { kind: "add" }
  | { kind: "edit"; account: AccountRow }
  | { kind: "delete"; account: AccountRow }
  | { kind: "invite"; account: AccountRow }
  | null;

export default function AdminPage() {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState<AccountRow[] | null>(null);
  const [groups, setGroups] = useState<GroupRef[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canAdd = hasPerm(user, PERMISSIONS.addUser);
  const canChange = hasPerm(user, PERMISSIONS.changeUser);
  const canDelete = hasPerm(user, PERMISSIONS.deleteUser);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const rows = await fetchAccounts(signal);
      if (signal?.aborted) return;
      setAccounts(rows);
      setError(null);
    } catch (err) {
      if (signal?.aborted) return;
      // The 403 is worth naming: it is what a user sees if the permission was
      // revoked while their session was open, and "could not load" would send
      // them looking for a fault that is not there.
      setError(
        err instanceof ApiError && err.status === 403
          ? "Your account no longer has permission to view this page."
          : "Could not load the account list. Is the API running?",
      );
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    void (async () => {
      // Both requests start together. The group picker is secondary, so its
      // failure falls back to an empty list rather than blanking the page.
      const [, groupRows] = await Promise.all([
        load(controller.signal),
        fetchGroups(controller.signal).catch(() => [] as GroupRef[]),
      ]);
      if (!controller.signal.aborted) setGroups(groupRows);
    })();

    return () => controller.abort();
  }, [load]);

  const filtered = useMemo(() => {
    if (!accounts) return null;
    const q = query.trim().toLowerCase();
    if (!q) return accounts;
    return accounts.filter(
      (a) =>
        a.email.toLowerCase().includes(q) ||
        a.fullName.toLowerCase().includes(q) ||
        a.groups.some((g) => g.toLowerCase().includes(q)),
    );
  }, [accounts, query]);

  async function onToggleActive(account: AccountRow) {
    setBusyId(account.id);
    setError(null);
    try {
      await setAccountActive(account.id, !account.isActive);
      await load();
    } catch (err) {
      // Refusals here are meaningful — deactivating the last account able to
      // manage users is blocked by the API — so the server's wording is kept.
      setError(err instanceof ApiError ? err.message : "Could not update this account.");
    } finally {
      setBusyId(null);
    }
  }

  const total = accounts?.length ?? 0;
  const active = accounts?.filter((a) => a.isActive).length ?? 0;

  return (
    <AdminChrome>
        <section className="admin">
          <div className="page-head">
            <div>
              <h1>Manage users</h1>
              <p>
                {accounts
                  ? `${total} ${total === 1 ? "account" : "accounts"} · ${active} active`
                  : "Accounts with access to the BrainVar dataset."}
              </p>
            </div>
            {canAdd && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setDialog({ kind: "add" })}
              >
                <Plus size={16} aria-hidden="true" />
                Add user
              </button>
            )}
          </div>

          <div className="search-field">
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, email or group…"
              aria-label="Search accounts"
            />
          </div>

          {error && (
            <div className="error-card" role="alert">
              {error}
            </div>
          )}

          {notice && (
            <div className="notice-card" role="status">
              {notice}
            </div>
          )}

          <div className="card">
            {!filtered && !error && (
              <div className="card-empty">
                <Loader2 size={22} className="spin" aria-hidden="true" />
                <p>Loading accounts…</p>
              </div>
            )}

            {filtered && filtered.length === 0 && (
              <div className="card-empty">
                <p>{query ? "No accounts match your search." : "No accounts yet."}</p>
              </div>
            )}

            {filtered && filtered.length > 0 && (
              <div className="data-table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">User</th>
                      <th scope="col">Groups</th>
                      <th scope="col">Status</th>
                      <th scope="col">Joined</th>
                      <th scope="col">Last sign-in</th>
                      {(canChange || canDelete) && (
                        <th scope="col" className="col-actions">
                          Actions
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((a) => (
                      <tr key={a.id}>
                        <td data-cell="user">
                          <div className="cell-user">
                            <span className="cell-name">{a.fullName || "—"}</span>
                            <span className="cell-email">{a.email}</span>
                          </div>
                        </td>
                        <td data-cell="groups">
                          {a.groups.length ? (
                            <div className="pill-row">
                              {a.groups.map((g) => (
                                <span key={g} className="pill pill-brand">
                                  {g}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                        <td data-cell="status">
                          <div className="pill-row">
                            <span className={`pill ${a.isActive ? "pill-ok" : "pill-muted"}`}>
                              {a.isActive ? "Active" : "Inactive"}
                            </span>
                            {/* An account created here has no password, so
                                "Inactive" alone would not explain why marking
                                it active still will not let anyone in. */}
                            {!a.hasPassword && (
                              <span className="pill pill-warn" title="Send the invitation to issue a password">
                                Not invited
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="muted" data-cell="date" data-label="Joined">
                          {formatDate(a.dateJoined)}
                        </td>
                        <td className="muted" data-cell="date" data-label="Last sign-in">
                          {formatDate(a.lastLogin)}
                        </td>
                        {(canChange || canDelete) && (
                          <td className="col-actions" data-cell="actions">
                            <div className="row-actions">
                              {canChange && (
                                <button
                                  type="button"
                                  className="switch"
                                  role="switch"
                                  aria-checked={a.isActive}
                                  aria-label={`${a.isActive ? "Deactivate" : "Activate"} ${a.email}`}
                                  disabled={busyId === a.id}
                                  onClick={() => void onToggleActive(a)}
                                >
                                  <span className="switch-knob" />
                                </button>
                              )}
                              {/* Keyed on whether the account can actually
                                  sign in, not on whether an invite was ever
                                  recorded — accounts that predate invitations,
                                  or had a password set in the Django admin,
                                  need a reset rather than a first invite. */}
                              {canChange &&
                                (a.hasPassword ? (
                                  <button
                                    type="button"
                                    className="icon-btn"
                                    title={
                                      a.invitedAt
                                        ? `Re-send invitation (last sent ${formatDate(a.invitedAt)})`
                                        : "Send a new password by email"
                                    }
                                    aria-label={`Re-send invitation to ${a.email}`}
                                    onClick={() => setDialog({ kind: "invite", account: a })}
                                  >
                                    <Mail size={15} aria-hidden="true" />
                                  </button>
                                ) : (
                                  // Spelled out rather than an icon while the
                                  // account still cannot sign in: it is the
                                  // one thing that row is waiting for.
                                  <button
                                    type="button"
                                    className="btn btn-outline btn-sm"
                                    onClick={() => setDialog({ kind: "invite", account: a })}
                                  >
                                    <Mail size={14} aria-hidden="true" />
                                    Send invite
                                  </button>
                                ))}
                              {canChange && (
                                <button
                                  type="button"
                                  className="icon-btn"
                                  title="Edit"
                                  aria-label={`Edit ${a.email}`}
                                  onClick={() => setDialog({ kind: "edit", account: a })}
                                >
                                  <Pencil size={15} aria-hidden="true" />
                                </button>
                              )}
                              {canDelete && (
                                <button
                                  type="button"
                                  className="icon-btn icon-btn-danger"
                                  title="Delete"
                                  aria-label={`Delete ${a.email}`}
                                  onClick={() => setDialog({ kind: "delete", account: a })}
                                >
                                  <Trash2 size={15} aria-hidden="true" />
                                </button>
                              )}
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <p className="admin-note">
            Sending an invitation issues a new password and emails it. The
            staff and superuser flags are managed in the Django admin. Access
            here follows Django model permissions, so a group is only a way of
            carrying them.
          </p>
        </section>
      {dialog?.kind === "add" && (
        <UserFormModal
          account={null}
          groups={groups}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null);
            void load();
          }}
        />
      )}
      {dialog?.kind === "edit" && (
        <UserFormModal
          account={dialog.account}
          groups={groups}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null);
            void load();
          }}
        />
      )}
      {dialog?.kind === "invite" && (
        <InviteUserModal
          account={dialog.account}
          onClose={() => setDialog(null)}
          onSent={(message) => {
            setDialog(null);
            setNotice(message);
            void load();
          }}
        />
      )}
      {dialog?.kind === "delete" && (
        <DeleteUserModal
          account={dialog.account}
          onClose={() => setDialog(null)}
          onDeleted={() => {
            setDialog(null);
            void load();
          }}
        />
      )}
    </AdminChrome>
  );
}
