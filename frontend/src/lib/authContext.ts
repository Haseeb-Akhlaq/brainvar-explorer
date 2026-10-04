import { createContext, useContext } from "react";

import type { User } from "./auth";

export interface AuthState {
  user: User | null;
  /** True until the first session check completes. */
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

/**
 * Kept apart from AuthContext.tsx so that file exports only a component,
 * which is what React Fast Refresh needs to update it without a full reload.
 */
export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside an AuthProvider");
  return context;
}
