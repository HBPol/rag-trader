import AuthGate from '@/components/AuthGate';
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';

export default function Home() {
  return (
    <AuthGate>
      <main className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-xl">
          <CardHeader>
            <CardTitle>RAGTrader</CardTitle>
            <CardDescription>
              Monorepo scaffold ready. Subsequent tasks will bring live price and sentiment analytics to
              life.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-sm text-muted-foreground">
              You are signed in via the mock auth provider—swap the environment flag to review the locked
              experience.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-muted-foreground">
                Review the new shadcn/ui primitives wired into the application shell.
              </div>
              <Button className="w-full sm:w-auto">Explore components</Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </AuthGate>
  );
}
