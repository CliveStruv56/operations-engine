import { Spinner } from "@/components/activity";

export default function AppLoading() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-paper">
      <p className="flex items-center gap-2 text-sm text-ink-muted">
        <Spinner className="text-accent" /> Loading…
      </p>
    </main>
  );
}
