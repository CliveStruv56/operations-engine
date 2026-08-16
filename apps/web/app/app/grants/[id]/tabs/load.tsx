"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { gr } from "@/lib/grants";

/**
 * Fetches a Grantwork resource on mount (and whenever `path` changes),
 * surfacing failures instead of leaving the tab silently blank. `refresh`
 * doubles as the post-mutation reload.
 */
export function useGrantLoad<T>(path: string, onData: (data: T) => void) {
  const onDataRef = useRef(onData);
  useEffect(() => {
    onDataRef.current = onData;
  });
  const [failed, setFailed] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const data = await gr<T>(path);
      onDataRef.current(data);
      setFailed(false);
    } catch (err) {
      console.error(`Failed to load ${path}`, err);
      setFailed(true);
    }
  }, [path]);
  useEffect(() => {
    // Fetch-on-mount: every setState in refresh happens after an await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);
  return { failed, refresh };
}

export function LoadError({ failed, onRetry }: { failed: boolean; onRetry: () => void }) {
  if (!failed) return null;
  return (
    <p
      role="alert"
      className="mb-3 flex items-center justify-between gap-3 rounded-card border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-danger"
    >
      Some of this application&rsquo;s data failed to load.
      <button onClick={onRetry} className="shrink-0 underline">
        Retry
      </button>
    </p>
  );
}
