import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

interface Props {
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  /** Wider variant for the account form. */
  size?: "sm" | "md";
}

/**
 * Dialog shell: backdrop, Escape, focus handling.
 *
 * Focus moves into the dialog on open and returns to whatever opened it on
 * close — without that, dismissing a modal drops the caret at the top of the
 * document and a keyboard user has to tab back through the whole page.
 */
export function Modal({ title, description, onClose, children, size = "md" }: Props) {
  const cardRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    openerRef.current = document.activeElement as HTMLElement | null;
    // The first field, or the dialog itself when there is nothing to type in.
    const target =
      cardRef.current?.querySelector<HTMLElement>("input, select, textarea, button") ??
      cardRef.current;
    target?.focus();

    return () => openerRef.current?.focus?.();
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      // Only a click that starts and ends on the backdrop dismisses, so a
      // drag that happens to release outside the card does not lose the form.
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={cardRef}
        className={`modal-card modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
        <header className="modal-head">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
