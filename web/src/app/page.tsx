export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <section className="w-full max-w-2xl rounded-xl border border-border bg-card text-card-foreground shadow-sm">
        <header className="space-y-3 p-6 text-center">
          <h1 className="text-3xl font-semibold leading-none tracking-tight">
            RAGTrader
          </h1>
          <p className="text-sm text-muted-foreground">
            Monorepo scaffold ready. Subsequent tasks will bring live price and
            sentiment analytics to life.
          </p>
        </header>
        <div className="space-y-6 p-6 pt-0">
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
            <a
              className="inline-flex w-full items-center justify-center whitespace-nowrap rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:w-auto"
              href="/dashboard"
            >
              Enter dashboard
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
