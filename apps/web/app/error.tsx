"use client";

// Route-level error boundary: catches render/runtime errors anywhere under /.
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-paper p-6">
      <div className="max-w-md text-center">
        <p className="data text-ink-muted uppercase">Something went wrong</p>
        <h1 className="mt-2 font-display text-[22px] font-medium tracking-[-0.01em]">
          This page hit an unexpected error
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          {error.message || "An unexpected error occurred."}
        </p>
        <button
          onClick={reset}
          className="mt-4 rounded-btn bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
