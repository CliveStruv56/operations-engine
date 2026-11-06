import { useCallback, useEffect, useRef, useState } from "react";

/** The text of the reply still streaming in, or null when none is.
 *
 *  Streamed deltas are coalesced and applied once per animation frame rather
 *  than once per token. A token-per-setState re-parsed the whole accumulated
 *  answer through ReactMarkdown every time — quadratic work over a reply,
 *  which made the stream *look* slower than it arrived. A frame is the
 *  fastest cadence a display can show anyway, so nothing is lost, and the
 *  panel's scroll effect drops to frame rate with it. */
export function useDeltaBuffer() {
  const [streamText, setStreamText] = useState<string | null>(null);
  const pendingRef = useRef("");
  const frameRef = useRef<number | null>(null);

  const flushDeltas = useCallback(() => {
    frameRef.current = null;
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = "";
    setStreamText((t) => (t ?? "") + pending);
  }, []);

  const pushDelta = useCallback(
    (delta: string) => {
      pendingRef.current += delta;
      frameRef.current ??= requestAnimationFrame(flushDeltas);
    },
    [flushDeltas]
  );

  // Drop anything buffered without applying it. Every stream ending clears
  // streamText, so a queued frame would otherwise fire afterwards and revive
  // the bubble with a stray fragment of the reply that just finished.
  const discardDeltas = useCallback(() => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    pendingRef.current = "";
  }, []);

  useEffect(() => discardDeltas, [discardDeltas]);

  return { streamText, setStreamText, pushDelta, discardDeltas };
}
