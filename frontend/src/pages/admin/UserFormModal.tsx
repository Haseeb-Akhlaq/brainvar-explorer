import { useState } from "react";
import { Loader2 } from "lucide-react";

import { ApiError } from "../../lib/api";
import { Modal } from "../../components/ui/Modal";
import {
  createAccount,
  updateAccount,
  type AccountInput,
  type AccountRow,
  type GroupRef,
} from "../../lib/users";

interface Props {
  /** null when adding; the row being edited otherwise. */
  account: AccountRow | null;
  groups: GroupRef[];
  onClose: () => void;
  onSaved: () => void;
}

export function UserFormModal({ account, groups, onClose, onSaved }: Props) {
  const editing = account !== null;
  const [form, setForm] = useState<AccountInput>({
    email: account?.email ?? "",
    fullName: account?.fullName ?? "",
    orcid: account?.orcid ?? "",
    groupIds: account?.groupIds ?? [],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  const set = <K extends keyof AccountInput>(key: K, value: AccountInput[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const toggleGroup = (id: number) =>
    set(
      "groupIds",
      form.groupIds.includes(id)
        ? form.groupIds.filter((g) => g !== id)
        : [...form.groupIds, id],
    );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      if (account) await updateAccount(account.id, form);
      else await createAccount(form);
      onSaved();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setFieldErrors(err.fields);
      } else {
        setError("Could not save. Please try again.");
      }
      setSaving(false);
    }
  }

  const fieldError = (name: string) => fieldErrors[name]?.[0];

  return (
    <Modal
      title={editing ? "Edit user" : "Add user"}
      description={
        editing
          ? "Update this account's details and group membership."
          : "The account is created inactive and without a password."
      }
      onClose={onClose}
    >
      <form onSubmit={onSubmit} noValidate>
        <div className="modal-body">
          {error && (
            <p className="form-banner" role="alert">
              {error}
            </p>
          )}

          <div className="field">
            <label htmlFor="user-email">
              Email address <span aria-hidden="true">*</span>
            </label>
            <input
              id="user-email"
              type="email"
              required
              autoComplete="off"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              placeholder="name@example.com"
              aria-invalid={fieldError("email") ? true : undefined}
            />
            {fieldError("email") && <p className="field-error">{fieldError("email")}</p>}
          </div>

          <div className="field">
            <label htmlFor="user-name">Full name</label>
            <input
              id="user-name"
              type="text"
              autoComplete="off"
              value={form.fullName}
              onChange={(e) => set("fullName", e.target.value)}
              placeholder="Ada Lovelace"
            />
            {fieldError("full_name") && <p className="field-error">{fieldError("full_name")}</p>}
          </div>

          <div className="field">
            <label htmlFor="user-orcid">ORCID iD</label>
            <input
              id="user-orcid"
              type="text"
              autoComplete="off"
              value={form.orcid}
              onChange={(e) => set("orcid", e.target.value)}
              placeholder="0000-0002-1825-0097"
            />
            {fieldError("orcid") && <p className="field-error">{fieldError("orcid")}</p>}
          </div>

          <fieldset className="field">
            <legend>Groups</legend>
            <div className="group-picker">
              {groups.map((group) => (
                <label key={group.id} className="group-option">
                  <input
                    type="checkbox"
                    checked={form.groupIds.includes(group.id)}
                    onChange={() => toggleGroup(group.id)}
                  />
                  {group.name}
                </label>
              ))}
            </div>
            <p className="field-hint">
              Permissions come from the group. <strong>Admin</strong> can manage
              accounts; <strong>User</strong> can use the explorer only.
            </p>
          </fieldset>

          {!editing && (
            <p className="field-hint field-hint-boxed">
              New accounts cannot sign in until a password is set in the Django
              admin. Until then they stay inactive.
            </p>
          )}
        </div>

        <footer className="modal-foot">
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving && <Loader2 size={15} className="spin" aria-hidden="true" />}
            {saving ? "Saving…" : editing ? "Save changes" : "Create account"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
