import { useState } from "react";
import { Loader2, Mail } from "lucide-react";

import { ApiError } from "../../lib/api";
import { Modal } from "../../components/ui/Modal";
import { sendInvitation, type AccountRow } from "../../lib/users";

interface Props {
  account: AccountRow;
  onClose: () => void;
  onSent: (message: string) => void;
}

/**
 * Confirmation for the welcome email.
 *
 * Both cases are confirmed, not just the re-send: this puts a message in
 * someone's inbox, which is not an action to take on a stray click. The
 * re-send additionally invalidates a password that may already be in use, so
 * the copy says so plainly rather than leaving it to be discovered.
 */
export function InviteUserModal({ account, onClose, onSent }: Props) {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Same signal as the table: an account that can already sign in is
  // having its password reset, not being invited for the first time.
  const resending = account.hasPassword;

  async function onConfirm() {
    setSending(true);
    setError(null);
    try {
      await sendInvitation(account.id);
      onSent(`Invitation sent to ${account.email}.`);
    } catch (err) {
      // SMTP failures are reported by the server with the underlying reason,
      // and the account is rolled back — so the message is worth showing.
      setError(err instanceof ApiError ? err.message : "The invitation could not be sent.");
      setSending(false);
    }
  }

  return (
    <Modal title={resending ? "Re-send invitation" : "Send invitation"} onClose={onClose} size="sm">
      <div className="modal-body modal-body-centered">
        <div className="brand-icon" aria-hidden="true">
          <Mail size={22} />
        </div>
        <h3>{resending ? "Re-send to" : "Send to"} {account.fullName || account.email}?</h3>
        <p>
          {resending ? (
            <>
              This generates a <strong>new</strong> password and emails it to{" "}
              {account.email}. Their current password will stop working
              immediately.
            </>
          ) : (
            <>
              This generates a password, activates the account and emails the
              sign-in details to {account.email}.
            </>
          )}
        </p>
        {error && (
          <p className="form-banner" role="alert">
            {error}
          </p>
        )}
      </div>
      <footer className="modal-foot">
        <button type="button" className="btn btn-ghost" onClick={onClose} disabled={sending}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void onConfirm()}
          disabled={sending}
        >
          {sending && <Loader2 size={15} className="spin" aria-hidden="true" />}
          {sending ? "Sending…" : resending ? "Re-send invitation" : "Send invitation"}
        </button>
      </footer>
    </Modal>
  );
}
