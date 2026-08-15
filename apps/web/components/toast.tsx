"use client";

// Transient confirmations ("fact added", "removed — undo?"). Errors stay as
// inline banners next to the thing that failed; a toast is for success or for
// offering a way back, never the only record of a problem.
import { createContext, useCallback, useContext, useRef, useState } from "react";

type Toast = {
  id: number;
  message: string;
  action?: { label: string; onClick: () => void };
};

type ToastInput = Omit<Toast, "id">;

const ToastContext = createContext<(t: ToastInput) => void>(() => {});

export const useToast = () => useContext(ToastContext);

const DISMISS_MS = 6000;
const DISMISS_WITH_ACTION_MS = 10000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((ts) => ts.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (t: ToastInput) => {
      const id = nextId.current++;
      setToasts((ts) => [...ts, { ...t, id }]);
      setTimeout(() => dismiss(id), t.action ? DISMISS_WITH_ACTION_MS : DISMISS_MS);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto flex max-w-md items-center gap-3 rounded-card border border-edge bg-surface px-4 py-2.5 text-sm shadow-lg"
          >
            <span className="min-w-0">{t.message}</span>
            {t.action && (
              <button
                onClick={() => {
                  dismiss(t.id);
                  t.action?.onClick();
                }}
                className="shrink-0 font-medium text-accent-deep underline hover:text-ink"
              >
                {t.action.label}
              </button>
            )}
            <button
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss"
              className="shrink-0 text-ink-faint hover:text-ink"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
