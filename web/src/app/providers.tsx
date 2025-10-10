"use client";

import { createContext } from "react";
import type { ReactNode } from "react";

export type AuthContextValue = {
  isAuthenticated: boolean;
};

export const AuthContext = createContext<AuthContextValue>({
  isAuthenticated: false,
});

export function resolveDefaultAuthValue(): AuthContextValue {
  const mockState = process.env.NEXT_PUBLIC_AUTH_MOCK_STATE ?? "locked";

  return {
    isAuthenticated: mockState.toLowerCase() === "authenticated",
  };
}

export function AuthProvider({
  children,
  value,
}: {
  children: ReactNode;
  value?: AuthContextValue;
}) {
  const resolvedValue = value ?? resolveDefaultAuthValue();

  return (
    <AuthContext.Provider value={resolvedValue}>
      {children}
    </AuthContext.Provider>
  );
}
