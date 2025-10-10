"use client";

import type { ReactNode } from "react";
import { useContext } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui";
import { AuthContext } from "@/app/providers";

type AuthGateProps = {
  children: ReactNode;
  lockedContent?: ReactNode;
};

const defaultLockedView = (
  <main className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
    <Card className="w-full max-w-lg text-center">
      <CardHeader>
        <CardTitle>RAGTrader</CardTitle>
        <CardDescription>
          Sign in to unlock market insights, watchlists, and custom retrieval
          workflows.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Authentication is coming soon—use the mocked auth flag while
          integration is in flight.
        </p>
      </CardContent>
    </Card>
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
