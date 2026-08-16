"use client";

// Replaces window.confirm / window.prompt.
//
// A native prompt cannot be styled, cannot show a real label or hint, cannot
// explain what is about to happen in more than one line, and is dismissed by
// browsers in ways the app never learns about. It also drops the user into
// chrome UI with no relationship to the workspace they were in.
//
// The API is promise-based so call sites read the same as the native ones they
// replace:
//
//   const ask = useAsk();
//   if (!(await ask.confirm({ ... }))) return;
//   const reason = await ask.text({ ... });   // string | null
//
// z-index: panels sit at 40/50 and toasts at 60. Dialogs go between, at 55,
// because a dialog can be raised from inside a slide-over but must never cover
// the toast that reports its result.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { Button } from "./button";
import { Input, Textarea } from "./field";

type Tone = "default" | "danger";

type ConfirmRequest = {
  kind: "confirm";
  title: string;
  body?: ReactNode;
  confirmLabel: string;
  tone?: Tone;
};

type TextRequest = {
  kind: "text";
  title: string;
  body?: ReactNode;
  /** Visible field label, e.g. "Reason for signing off anyway". */
  label: string;
  hint?: string;
  confirmLabel: string;
  placeholder?: string;
  /** Renders a textarea instead of a single line. */
  multiline?: boolean;
  inputType?: "text" | "email" | "number";
  /** Enforced by the control as well as the API that will reject it. */
  maxLength?: number;
  tone?: Tone;
};

type TypedRequest = {
  kind: "typed";
  title: string;
  body?: ReactNode;
  label: string;
  /** The exact string the user must type. A mistype cancels. */
  expected: string;
  confirmLabel: string;
  tone?: Tone;
};

type Request = ConfirmRequest | TextRequest | TypedRequest;

type Ask = {
  confirm: (r: Omit<ConfirmRequest, "kind">) => Promise<boolean>;
  text: (r: Omit<TextRequest, "kind">) => Promise<string | null>;
  /** Resolves true only if the typed value matches `expected` exactly. */
  confirmTyped: (r: Omit<TypedRequest, "kind">) => Promise<boolean>;
};

const noop = async () => {
  throw new Error("useAsk() requires <DialogProvider> above it");
};

const AskContext = createContext<Ask>({
  confirm: noop,
  text: noop,
  confirmTyped: noop,
});

export const useAsk = () => useContext(AskContext);

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function DialogProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<Request | null>(null);
  // Held across the dialog's lifetime; settled exactly once, on close.
  const resolve = useRef<((v: unknown) => void) | null>(null);

  const open = useCallback(<T,>(r: Request): Promise<T> => {
    return new Promise<T>((res) => {
      resolve.current = res as (v: unknown) => void;
      setRequest(r);
    });
  }, []);

  const settle = useCallback((value: unknown) => {
    resolve.current?.(value);
    resolve.current = null;
    setRequest(null);
  }, []);

  const ask: Ask = {
    confirm: useCallback((r) => open<boolean>({ ...r, kind: "confirm" }), [open]),
    text: useCallback((r) => open<string | null>({ ...r, kind: "text" }), [open]),
    confirmTyped: useCallback((r) => open<boolean>({ ...r, kind: "typed" }), [open]),
  };

  return (
    <AskContext.Provider value={ask}>
      {children}
      {request && <Dialog request={request} settle={settle} />}
    </AskContext.Provider>
  );
}

/** The cancelled value for each kind — what a dismissed native prompt returns. */
function cancelValue(kind: Request["kind"]) {
  return kind === "text" ? null : false;
}

function Dialog({
  request,
  settle,
}: {
  request: Request;
  settle: (value: unknown) => void;
}) {
  const [value, setValue] = useState("");
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const bodyId = useId();

  const cancel = useCallback(
    () => settle(cancelValue(request.kind)),
    [settle, request.kind]
  );

  // Focus moves into the dialog on open and returns to the trigger on close,
  // so a keyboard user is not dropped back at the top of the document.
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    const first = panel.current?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
    return () => trigger?.focus?.();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        cancel();
        return;
      }
      // Contain Tab: a modal that lets focus wander into the page behind it is
      // a modal only for people using a mouse.
      if (e.key !== "Tab" || !panel.current) return;
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const edge = e.shiftKey ? items[0] : items[items.length - 1];
      if (document.activeElement === edge) {
        e.preventDefault();
        (e.shiftKey ? items[items.length - 1] : items[0]).focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cancel]);

  const tone = request.tone === "danger" ? "danger" : "primary";
  const needsValue = request.kind !== "confirm";
  const blocked =
    (request.kind === "text" && value.trim() === "") ||
    (request.kind === "typed" && value !== request.expected);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (blocked) return;
    settle(request.kind === "text" ? value.trim() : true);
  }

  return (
    <div className="fixed inset-0 z-[55] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/40" onClick={cancel} aria-hidden="true" />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={request.body ? bodyId : undefined}
        className="relative w-full max-w-md rounded-card border border-edge bg-card p-5 shadow-card"
      >
        <h2 id={titleId} className="font-display text-hearth-section leading-tight font-medium">
          {request.title}
        </h2>
        {request.body && (
          <div id={bodyId} className="mt-2 text-sm text-subtle">
            {request.body}
          </div>
        )}

        <form onSubmit={submit}>
          {needsValue &&
            (request.kind === "text" && request.multiline ? (
              <Textarea
                label={request.label}
                hint={request.hint}
                maxLength={request.maxLength}
                className="mt-4"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                autoFocus
              />
            ) : (
              <Input
                label={request.label}
                hint={request.kind === "text" ? request.hint : undefined}
                type={request.kind === "text" ? (request.inputType ?? "text") : "text"}
                placeholder={request.kind === "text" ? request.placeholder : undefined}
                maxLength={request.kind === "text" ? request.maxLength : undefined}
                className="mt-4"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                autoComplete="off"
                autoFocus
              />
            ))}

          <div className="mt-5 flex justify-end gap-3">
            <Button variant="secondary" onClick={cancel}>
              Cancel
            </Button>
            <Button type="submit" variant={tone} disabled={blocked}>
              {request.confirmLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
