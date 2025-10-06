import AuthGate from '../components/AuthGate';

export default function Home() {
  return (
    <AuthGate>
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-slate-950 p-8 text-slate-100">
        <h1 className="text-3xl font-semibold">RAGTrader</h1>
        <p className="max-w-xl text-center text-base text-slate-300">
          Monorepo scaffold ready. Subsequent tasks will bring live price and sentiment
          analytics to life.
        </p>
        <p className="text-sm text-slate-400">
          You are signed in via the mock auth provider—swap the environment flag to review the
          locked experience.
        </p>
      </main>
    </AuthGate>
  );
}
