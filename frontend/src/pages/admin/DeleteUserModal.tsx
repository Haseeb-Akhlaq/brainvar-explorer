import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";

import { ApiError } from "../../lib/api";
import { Modal } from "../../components/ui/Modal";
import { deleteAccount, type AccountRow } from "../../lib/users";

interface Props {
  account: AccountRow;
  onClose: () => void;
  onDeleted: () => void;
}

export function DeleteUserModal({ account, onClose, onDeleted }: Props) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onConfirm() {
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount(account.id);
      onDeleted();
    } catch (err) {
      // The server refuses two cases the interface cannot reliably predict —
      // your own account, and the last one able to manage users — so its
      // message is shown rather than a generic failure.
      setError(err instanceof ApiError ? err.message : "Could not delete this account.");
      setDeleting(false);
    }
  }

  return (
    <Modal title="Delete account" onClose={onClose} size="sm">
      <div className="modal-body modal-body-centered">
        <div className="danger-icon" aria-hidden="true">
          <Trash2 size={22} />
        </div>
        <h3>Delete {account.fullName || account.email}?</h3>
        <p>
          This removes the account and its access permanently. It cannot be
          undone — to suspend access instead, switch the account to inactive.
        </p>
        {error && (
          <p className="form-banner" role="alert">
            {error}
          </p>
        )}
      </div>
      <footer className="modal-foot">
        <button type="button" className="btn btn-ghost" onClick={onClose} disabled={deleting}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-danger"
          onClick={() => void onConfirm()}
          disabled={deleting}
        >
          {deleting && <Loader2 size={15} className="spin" aria-hidden="true" />}
          {deleting ? "Deleting…" : "Delete account"}
        </button>
      </footer>
    </Modal>
  );
}
