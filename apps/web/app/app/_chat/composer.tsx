import { useRef, type RefObject } from "react";
import { Spinner } from "@/components/activity";
import { ArrowUpIcon, ClipIcon, StopIcon } from "@/components/icons";
import { ACCEPT } from "@/lib/uploads";
import type { DocMeta } from "../hero";

const MODES: { key: string; label: string }[] = [
  { key: "chat", label: "Chat" },
  { key: "analyse", label: "Analyse" },
  { key: "report", label: "Report" },
  { key: "financial", label: "Financial" },
  { key: "slides", label: "Slide deck" },
  { key: "research", label: "Research" },
];

/** The message box: task mode, attachment chips, the textarea with send or
 *  stop, and the two retrieval switches. State lives in the panel; this only
 *  renders it. */
export default function Composer({
  mode,
  onModeChange,
  webSearchEnabled,
  attachments,
  uploadingCount,
  onAttach,
  draft,
  onDraftChange,
  inputRef,
  streaming,
  onSend,
  onStop,
  useVault,
  onToggleVault,
  useCompany,
  onToggleCompany,
}: {
  mode: string;
  onModeChange: (mode: string) => void;
  webSearchEnabled: boolean;
  attachments: DocMeta[];
  uploadingCount: number;
  onAttach: (files: FileList) => void;
  draft: string;
  onDraftChange: (draft: string) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  /** A reply is streaming in: Send becomes Stop. */
  streaming: boolean;
  onSend: (e?: React.FormEvent) => void;
  onStop: () => void;
  useVault: boolean;
  onToggleVault: () => void;
  useCompany: boolean;
  onToggleCompany: () => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const availableModes = MODES.filter((m) => m.key !== "research" || webSearchEnabled);

  return (
    <div className="px-4 pt-2 pb-4 sm:px-6 sm:pb-6">
      <form
        onSubmit={onSend}
        className="mx-auto w-full max-w-[720px] rounded-[18px] border border-edge-strong bg-card p-3 shadow-card"
      >
        <div
          role="radiogroup"
          aria-label="Mode"
          className="flex gap-1.5 overflow-x-auto px-0.5 pb-2.5 [scrollbar-width:none]"
        >
          {availableModes.map((m) => (
            <button
              key={m.key}
              type="button"
              role="radio"
              aria-checked={mode === m.key}
              onClick={() => onModeChange(m.key)}
              className={`shrink-0 rounded-full px-[13px] py-1.5 text-xs font-bold whitespace-nowrap transition ${
                mode === m.key ? "bg-deep-violet text-white" : "text-subtle hover:bg-sidebar"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        {(attachments.length > 0 || uploadingCount > 0) && (
          <div className="flex flex-wrap gap-1.5 px-0.5 pb-2">
            {attachments.map((d) => (
              <span
                key={d.id}
                className={`flex items-center gap-1.5 rounded-full border border-edge px-2.5 py-1 text-xs font-semibold ${
                  d.status === "failed" ? "bg-danger-soft text-danger" : "bg-sidebar text-subtle"
                }`}
                title={d.status === "failed" ? (d.error ?? "Failed to read") : d.title}
              >
                <ClipIcon className="h-3 w-3" />
                <span className="max-w-44 truncate">{d.title}</span>
                {d.status !== "ready" && (
                  <span className="text-xs font-bold uppercase">
                    {d.status === "failed" ? "failed" : "reading…"}
                  </span>
                )}
              </span>
            ))}
            {uploadingCount > 0 && (
              <span className="flex items-center gap-1.5 rounded-full border border-edge bg-sidebar px-2.5 py-1 text-xs font-semibold text-subtle">
                <Spinner className="h-3 w-3" /> Uploading…
              </span>
            )}
          </div>
        )}
        <div className="flex items-end gap-2.5">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploadingCount > 0}
            aria-label="Attach a file to this chat"
            title="Attach a file — it joins your documents and this chat reads it first"
            className="mb-1.5 flex-none rounded-lg p-1.5 text-subtle transition hover:bg-sidebar hover:text-ink disabled:opacity-50"
          >
            <ClipIcon className="h-[18px] w-[18px]" />
          </button>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.length) onAttach(e.target.files);
              // Same file again (a failed upload, a corrected copy) must
              // still fire a change event.
              e.target.value = "";
            }}
          />
          <textarea
            ref={inputRef}
            rows={1}
            value={draft}
            onChange={(e) => {
              onDraftChange(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                onSend();
              }
            }}
            aria-label="Message"
            placeholder={
              mode === "research"
                ? "Research a question across the web…"
                : useVault
                  ? "Ask about your documents — or draft something new…"
                  : "Ask anything…"
            }
            className="max-h-[200px] w-full resize-none bg-transparent px-0.5 py-2 text-base leading-normal text-ink placeholder:text-faint focus:outline-none sm:text-[15px]"
          />
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              className="inline-flex flex-none items-center gap-2 rounded-btn bg-ink px-[18px] py-[9px] text-[13.5px] font-medium text-on-ink hover:bg-stone"
            >
              <StopIcon className="h-3.5 w-3.5" />
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!draft.trim()}
              className="inline-flex flex-none items-center gap-2 rounded-btn bg-accent px-[18px] py-[9px] text-[13.5px] font-medium text-accent-ink transition hover:bg-accent-deep disabled:cursor-not-allowed disabled:bg-edge disabled:text-subtle"
            >
              Send
              <ArrowUpIcon className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-edge px-1 pt-[11px]">
          {/* The two retrieval sources: the shared document vault, and the
              workspace's own records (claims register, community profile,
              contact book). Both default on; both cover the whole
              workspace, not just this user's uploads. */}
          <span className="flex items-center gap-2.5">
            <button
              type="button"
              role="switch"
              aria-checked={useVault}
              aria-label="Include workspace documents"
              onClick={onToggleVault}
              className={`relative h-[18px] w-8 flex-none rounded-full transition after:absolute after:top-0.5 after:left-0.5 after:h-3.5 after:w-3.5 after:rounded-full after:bg-white after:transition after:content-[''] ${
                useVault ? "bg-grounded after:translate-x-[14px]" : "bg-edge-strong"
              }`}
            />
            <span className="text-xs font-semibold text-subtle">Include workspace documents</span>
          </span>
          <span className="flex items-center gap-2.5">
            <button
              type="button"
              role="switch"
              aria-checked={useCompany}
              aria-label="Include company data"
              onClick={onToggleCompany}
              className={`relative h-[18px] w-8 flex-none rounded-full transition after:absolute after:top-0.5 after:left-0.5 after:h-3.5 after:w-3.5 after:rounded-full after:bg-white after:transition after:content-[''] ${
                useCompany ? "bg-grounded after:translate-x-[14px]" : "bg-edge-strong"
              }`}
            />
            <span className="text-xs font-semibold text-subtle">Include company data</span>
          </span>
          <span className="ml-auto hidden text-xs font-semibold text-faint sm:block">
            <kbd className="rounded-[5px] border border-edge bg-sidebar px-1.5 py-0.5 text-xs font-bold">
              ↵
            </kbd>{" "}
            Send ·{" "}
            <kbd className="rounded-[5px] border border-edge bg-sidebar px-1.5 py-0.5 text-xs font-bold">
              ⇧↵
            </kbd>{" "}
            New line
          </span>
          {streaming && <Spinner className="ml-2 text-accent sm:ml-0" />}
        </div>
      </form>
    </div>
  );
}

/** In place of the composer on a chat this person cannot write to. */
export function ReadOnlyNotice({
  ownerUnknown,
  ownerEmail,
}: {
  ownerUnknown: boolean;
  ownerEmail: string | null;
}) {
  return (
    <div className="px-4 pt-2 pb-4 sm:px-6 sm:pb-6">
      <p className="mx-auto w-full max-w-[720px] rounded-[18px] border border-edge bg-sidebar px-5 py-3.5 text-center text-[13px] font-semibold text-subtle">
        {ownerUnknown
          ? "Couldn't check who owns this chat — refresh to reply"
          : `Shared by ${ownerEmail ?? "a teammate"} — read only`}
      </p>
    </div>
  );
}
