'use client';

import type { ReactNode } from 'react';
import { useContext } from 'react';
import { AuthContext } from '../app/layout';

type AuthGateProps = {
  children: ReactNode;
  lockedContent?: ReactNode;
};

const defaultLockedView = (
  <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-950 p-8 text-center text-slate-100">
    <h1 className="text-3xl font-semibold">RAGTrader</h1>
    <p className="max-w-lg text-base text-slate-300">
      Sign in to unlock market insights, watchlists, and custom retrieval workflows.
    </p>
    <p className="text-sm text-slate-500">
      Authentication is coming soon—use the mocked auth flag while integration is in flight.
    </p>
  </main>
);

export function AuthGate({ children, lockedContent }: AuthGateProps) {
  const { isAuthenticated } = useContext(AuthContext);

  if (isAuthenticated) {
    return <>{children}</>;
  }

  return <>{lockedContent ?? defaultLockedView}</>;
}

export default AuthGate;
