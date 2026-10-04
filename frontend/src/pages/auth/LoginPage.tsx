import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../lib/authContext";
import { ThemeToggle } from "../../components/ThemeToggle";

export default function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;

    setError(null);
    setSubmitting(true);
    try {
      await signIn(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
      setSubmitting(false);
    }
  };

  return (
    <div className="login">
      <div className="login-toggle">
        <ThemeToggle />
      </div>

      <main className="login-card">
        {/* The trajectory mark, the same glyph as the favicon. Decorative:
            the heading below already names the app. */}
        <div className="login-logo">
          <svg viewBox="0 0 64 64" width="56" height="56" aria-hidden="true">
            <rect width="64" height="64" rx="14" fill="#465fff" />
            <g fill="#fff" fillOpacity="0.6">
              <circle cx="18" cy="34" r="2.6" />
              <circle cx="33" cy="43" r="2.6" />
              <circle cx="39" cy="14" r="2.6" />
              <circle cx="48" cy="30" r="2.6" />
            </g>
            <path
              d="M13 45C28 45 27 21 51 20"
              fill="none"
              stroke="#fff"
              strokeWidth="5"
              strokeLinecap="round"
            />
          </svg>
        </div>

        <h1>BrainVar Trajectory Explorer</h1>

        <form onSubmit={onSubmit} noValidate>
          <label htmlFor="email">Email address</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            autoFocus
            required
            placeholder="you@example.com"
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />

          {error && (
            <p className="login-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="login-submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="login-divider" role="separator">
          <span>or</span>
        </div>

        {/*
          Placeholder for institutional SSO. Research institutions commonly
          issue Microsoft Entra accounts, so this is where that flow would
          start — the button is deliberately inert until a tenant is
          registered.
        */}
        <button
          type="button"
          className="login-sso"
          title="Not configured in this demo"
        >
          <svg viewBox="0 0 21 21" width="17" height="17" aria-hidden="true">
            <rect x="1" y="1" width="9" height="9" fill="#f25022" />
            <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
            <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
            <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
          </svg>
          Sign in with your Microsoft account
        </button>

        <p className="login-note">
          Accounts are created by an administrator. There is no public sign-up —
          the dataset is available to named researchers only.
        </p>
      </main>

      <footer className="login-footer">
        BrainVar &middot; developing human cortex &middot; 176 RNA-seq samples
      </footer>
    </div>
  );
}
