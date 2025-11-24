import Link from "next/link";

import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui";

export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-2xl shadow-lg">
        <CardHeader className="space-y-3 text-center">
          <CardTitle className="text-3xl">RAGTrader</CardTitle>
          <CardDescription>
            Monorepo scaffold ready. Subsequent tasks will bring live price and
            sentiment analytics to life.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <p className="text-base text-muted-foreground">
            This marketing shell spotlights the new shadcn/ui experience that
            frames the dashboard, so stakeholders can review the polished
            primitives before wiring production data.
          </p>
          <div className="rounded-md border border-dashed border-muted-foreground/30 bg-muted/40 p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Mock auth preview</p>
            <p>
              You are signed in via the mock auth provider—swap the environment
              flag to review the locked experience.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-muted-foreground">
              Review the new shadcn/ui primitives wired into the application
              shell, then jump into the dashboard preview to see the complete
              flow.
            </div>
            <Button asChild className="w-full sm:w-auto">
              <Link href="/dashboard" prefetch={false}>
                Enter dashboard
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
