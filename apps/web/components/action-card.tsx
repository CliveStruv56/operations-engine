"use client";

import { useId } from "react";
import type { ReactNode } from "react";
import { Button, Card, ErrorNote, Stamp } from "@/components/ui";

/**
 * The one card for a setup question, a confirmation or a proposed action
 * (enhancement plan principle 5). It shows what will change, who proposed it,
 * and up to three actions: confirm, edit, reject.
 *
 * It is a pure view: the caller owns the request and passes `status` back in.
 * Release is always a person's click. Nothing here confirms on a timer, on
 * mount, or from a key other than activating the Confirm button itself.
 */

export type ActionCardProposer = {
  kind: "assistant" | "automation" | "register";
  /** Names the source: "Companies House", "Monthly digest". Optional. */
  name?: string;
};

export type ActionCardChange = {
  /** The field or thing that changes: "Registered address". */
  label: string;
  /** Current value. Omit for a new value with nothing before it. */
  before?: ReactNode;
  /** Proposed value. */
  after: ReactNode;
};

export type ActionCardAction = "confirm" | "edit" | "reject";

export type ActionCardStatus = "idle" | "busy" | "error" | "done" | "disabled";

const PROPOSER_LABEL: Record<ActionCardProposer["kind"], string> = {
  assistant: "Proposed by the assistant",
  automation: "Proposed by an automation",
  register: "Found in a public register",
};

export type ActionCardProps = {
  title: string;
  description?: ReactNode;
  proposer: ActionCardProposer;
  /** Before and after, or just the new values. Rendered as a list. */
  changes?: ActionCardChange[];
  /** Extra content under the changes, e.g. an edit form. */
  children?: ReactNode;

  /** Each action shows only if its handler is passed. */
  onConfirm?: () => void;
  onEdit?: () => void;
  onReject?: () => void;
  confirmLabel?: string;
  editLabel?: string;
  rejectLabel?: string;

  /** idle: ready. busy: a request is running. error: the last try failed.
   *  done: settled, no actions. disabled: shown but inert. */
  status?: ActionCardStatus;
  /** Which action is running while `status` is "busy". */
  busyAction?: ActionCardAction;
  /** Shown with `status` "error". */
  errorMessage?: string;
  /** Shown with `status` "done": what happened, in words. */
  doneMessage?: string;

  /** False when the signed-in member's role cannot release this. All actions
   *  are disabled and the reason is shown in words. */
  canRelease?: boolean;
  cannotReleaseReason?: string;

  /** Heading level, so the card nests correctly. Default 3. */
  headingLevel?: 2 | 3 | 4;
  className?: string;
};

export function ActionCard({
  title,
  description,
  proposer,
  changes,
  children,
  onConfirm,
  onEdit,
  onReject,
  confirmLabel = "Confirm",
  editLabel = "Edit",
  rejectLabel = "Reject",
  status = "idle",
  busyAction,
  errorMessage,
  doneMessage,
  canRelease = true,
  cannotReleaseReason = "You can't release this. Ask someone with the right role.",
  headingLevel = 3,
  className = "",
}: ActionCardProps) {
  const uid = useId();
  const titleId = `${uid}-title`;
  const gateId = `${uid}-gate`;
  const Heading = `h${headingLevel}` as "h2" | "h3" | "h4";

  const busy = status === "busy";
  const done = status === "done";
  const gated = !canRelease;
  const inert = busy || status === "disabled" || gated;
  const hasActions = Boolean(onConfirm || onEdit || onReject);

  const loadingFor = (a: ActionCardAction) => busy && busyAction === a;

  return (
    <Card className={className}>
      <section aria-labelledby={titleId} aria-busy={busy || undefined} data-status={status}>
        <div className="flex flex-wrap items-center gap-2">
          <Stamp tone="neutral">
            {PROPOSER_LABEL[proposer.kind]}
            {proposer.name ? `: ${proposer.name}` : ""}
          </Stamp>
          {done && <Stamp tone="rose">Done</Stamp>}
        </div>

        <Heading
          id={titleId}
          className="mt-3 font-display text-lg leading-tight font-medium tracking-[-0.01em]"
        >
          {title}
        </Heading>
        {description && <p className="mt-1.5 max-w-[60ch] text-sm text-subtle">{description}</p>}

        {changes && changes.length > 0 && (
          <dl className="mt-4 divide-y divide-edge border-y border-edge">
            {changes.map((c) => (
              <div key={c.label} className="grid gap-1 py-2.5 sm:grid-cols-[10rem_1fr] sm:gap-4">
                <dt className="text-xs font-medium text-subtle">{c.label}</dt>
                <dd className="min-w-0 text-sm break-words">
                  {c.before !== undefined && (
                    <p className="text-subtle">
                      <span className="font-medium">Currently: </span>
                      <span className="line-through">{c.before}</span>
                    </p>
                  )}
                  <p>
                    <span className="font-medium">{c.before !== undefined ? "Proposed: " : "New: "}</span>
                    {c.after}
                  </p>
                </dd>
              </div>
            ))}
          </dl>
        )}

        {children && <div className="mt-4">{children}</div>}

        {status === "error" && (
          <ErrorNote className="mt-4">{errorMessage ?? "That didn't work. Try again."}</ErrorNote>
        )}

        {done && doneMessage && (
          <p role="status" className="mt-4 text-sm">
            {doneMessage}
          </p>
        )}

        {gated && !done && (
          <p id={gateId} className="mt-4 rounded-btn border border-edge px-3 py-2 text-sm text-subtle">
            {cannotReleaseReason}
          </p>
        )}

        {hasActions && !done && (
          <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label={`Actions for ${title}`}>
            {onConfirm && (
              <Button
                variant="primary"
                onClick={onConfirm}
                disabled={inert}
                loading={loadingFor("confirm")}
                loadingLabel="Working"
                aria-describedby={gated ? gateId : undefined}
              >
                {confirmLabel}
              </Button>
            )}
            {onEdit && (
              <Button
                variant="secondary"
                onClick={onEdit}
                disabled={inert}
                loading={loadingFor("edit")}
                loadingLabel="Working"
                aria-describedby={gated ? gateId : undefined}
              >
                {editLabel}
              </Button>
            )}
            {onReject && (
              <Button
                variant="quiet"
                onClick={onReject}
                disabled={inert}
                loading={loadingFor("reject")}
                loadingLabel="Working"
                aria-describedby={gated ? gateId : undefined}
              >
                {rejectLabel}
              </Button>
            )}
          </div>
        )}
      </section>
    </Card>
  );
}
