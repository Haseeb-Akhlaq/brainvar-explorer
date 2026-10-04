import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Menu, X } from "lucide-react";

interface Props {
  /** The links and buttons that live in the bar — a row on desktop, a
   *  drawer below the mobile breakpoint. */
  children: ReactNode;
  /** Rendered between the drawer and the menu button, so it stays on the
   *  first row at every width. The theme toggle, in practice. */
  trailing?: ReactNode;
}

/**
 * The top bar's link cluster.
 *
 * One flex row on desktop. Below the mobile breakpoint (see `.topbar-menu` in
 * index.css) the same nodes become a drawer opened by a hamburger, because
 * seven items do not fit across a phone and wrapping them strands the last
 * one on a row of its own.
 *
 * The breakpoint lives only in CSS — this renders the same tree at every
 * width, so there is no resize listener and nothing to get out of step with
 * the media query.
 */
export function TopBarNav({ children, trailing }: Props) {
  const [open, setOpen] = useState(false);
  const navId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  // Escape closes, and a pointer outside the bar does too — the drawer sits
  // over the page, so leaving it open while reading is never what was meant.
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };

    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  return (
    <div className="topbar-nav" ref={rootRef}>
      {/* Closing on any activation inside covers every link and the sign-out
          button without each caller having to remember to wire it up. */}
      <nav
        id={navId}
        className={`topbar-links${open ? " is-open" : ""}`}
        onClick={() => setOpen(false)}
      >
        {children}
      </nav>
      {trailing}
      <button
        type="button"
        className="topbar-menu"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls={navId}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
      </button>
    </div>
  );
}
