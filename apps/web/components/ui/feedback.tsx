import type { ReactNode } from "react";
import { Card } from "./card";

/**
 * Empty is not blank. Every one of these says what belongs here and offers the
 * one action that puts it there — a bare "No results" leaves the user to guess
 * whether the screen is broken.
 */
export function EmptyState({
  title,
  children,
  action,
  className = "",
}: {
  title: string;
  /** What belongs here, in a sentence. */
  children?: ReactNode;
  /** The one thing to do about it. */
  action?: ReactNode;
  className?: string;
}) {
  return (
    <Card className={`text-center ${className}`}>
      <h3 className="font-display text-hearth-section leading-tight font-medium">{title}</h3>
      {children && (
        <p className="mx-auto mt-2 max-w-[52ch] text-sm text-subtle">{children}</p>
      )}
      {action && <div className="mt-4 flex justify-center gap-3">{action}</div>}
    </Card>
  );
}

/**
 * A placeholder in the shape of the thing that is coming. Only worth using
 * when it matches the final layout — a skeleton that settles into something a
 * different size is worse than a spinner, because the page jumps.
 */
export function Skeleton({ className = "" }: { className?: string }) {
  return <span aria-hidden="true" className={`skeleton block ${className}`} />;
}

/** A loading region that keeps the layout stable and announces itself once. */
export function LoadingRegion({
  label,
  children,
}: {
  /** What is loading, e.g. "Loading usage". Read out, not shown. */
  label: string;
  children: ReactNode;
}) {
  return (
    <div role="status" aria-busy="true" aria-label={label}>
      {children}
    </div>
  );
}

/**
 * A persistent problem. Banners are for things that stay broken until someone
 * acts; transient success belongs in a toast, and the two should never both
 * fire for the same event.
 */
export function ErrorNote({
  children,
  action,
  className = "",
}: {
  children: ReactNode;
  /** Retry, usually. An error with no way out is a dead end. */
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={`flex flex-wrap items-center justify-between gap-3 rounded-btn border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-danger ${className}`}
    >
      <span>{children}</span>
      {action}
    </div>
  );
}
