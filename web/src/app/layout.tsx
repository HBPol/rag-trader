import type { Metadata } from 'next';
import { createContext } from 'react';
import type { ReactNode } from 'react';
import './globals.css';
import { cn } from '@/lib/utils';

export const metadata: Metadata = {
  title: 'RAGTrader',
  description: 'Retrieve. Reason. Trade.',
};

export type AuthContextValue = {
  isAuthenticated: boolean;
};

export const AuthContext = createContext<AuthContextValue>({
  isAuthenticated: false,
});

function resolveDefaultAuthValue(): AuthContextValue {
  const mockState = process.env.NEXT_PUBLIC_AUTH_MOCK_STATE ?? 'locked';

  return {
    isAuthenticated: mockState.toLowerCase() === 'authenticated',
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

  return <AuthContext.Provider value={resolvedValue}>{children}</AuthContext.Provider>;
}

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={cn('min-h-screen bg-background font-sans antialiased text-foreground')}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
