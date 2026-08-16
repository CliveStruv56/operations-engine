"use client";

import { useEffect } from "react";

/** Right-hand slide-over used by the contact and company editors. */
export function Panel({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="fixed inset-0 z-40 bg-ink/40" onClick={onClose} aria-hidden="true" />
      <aside
        role="dialog"
        aria-label={title}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col overflow-y-auto border-l border-edge bg-surface p-6 shadow-card"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-xl font-medium tracking-[-0.01em]">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="grid h-7 w-7 place-items-center rounded-card text-ink-muted hover:bg-accent-soft hover:text-ink"
          >
            ✕
          </button>
        </div>
        {children}
      </aside>
    </>
  );
}
