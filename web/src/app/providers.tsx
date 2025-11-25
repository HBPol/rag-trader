"use client";

import dynamic from "next/dynamic";
import { useState, createContext } from "react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const Devtools =
  process.env.NODE_ENV === "development"
    ? dynamic(
        () =>
          import("@tanstack/react-query-devtools").then(
            (mod) => mod.ReactQueryDevtools,
          ),
        { ssr: false },
      )
    : null;

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

export function AppProviders({
  children,
  value,
}: {
  children: ReactNode;
  value?: AuthContextValue;
}) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  const resolvedValue = value ?? resolveDefaultAuthValue();

  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={resolvedValue}>
        {children}
      </AuthContext.Provider>
      {Devtools ? <Devtools initialIsOpen={false} position="bottom" /> : null}
    </QueryClientProvider>
  );
}

// Backwards-compatible export for any legacy usage.
export const AuthProvider = AppProviders;
