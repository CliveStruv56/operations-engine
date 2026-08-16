"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ChatIcon, DocIcon, PeopleIcon, SearchIcon } from "@/components/icons";
import { useWorkspace } from "./workspace";

type SearchResults = {
  conversations: {
    id: string;
    title: string | null;
    project_id: string | null;
    is_mine: boolean;
  }[];
  documents: { id: string; title: string; project_id: string | null; status: string }[];
  contacts: { id: string; name: string; job_title: string | null; company_name: string | null }[];
};

type Row =
  | { kind: "conversation"; id: string; title: string; projectId: string | null; shared: boolean }
  | { kind: "document"; id: string; title: string; projectId: string | null }
  | { kind: "contact"; id: string; title: string; detail: string | null };

const EMPTY: SearchResults = { conversations: [], documents: [], contacts: [] };

/** ⌘K palette: searches chats & documents via GET /search. Opened by the
 * sidebar search button (custom event) or the keyboard shortcut. */
export default function CommandPalette() {
  const ws = useWorkspace();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResults>(EMPTY);
  const [active, setActive] = useState(0);
  const [failed, setFailed] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tenantId = ws.tenant?.id;

  const openPalette = useCallback(() => {
    setQ("");
    setResults(EMPTY);
    setActive(0);
    setFailed(false);
    setOpen(true);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (open) setOpen(false);
        else openPalette();
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("open-command-palette", openPalette);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("open-command-palette", openPalette);
    };
  }, [open, openPalette]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const search = useCallback(
    (query: string) => {
      if (!tenantId || !query.trim()) {
        setResults(EMPTY);
        return;
      }
      api<SearchResults>(`/search?q=${encodeURIComponent(query.trim())}`, {}, tenantId)
        .then((r) => {
          setResults(r);
          setActive(0);
          setFailed(false);
        })
        .catch((err) => {
          console.error("Search failed", err);
          setFailed(true);
        });
    },
    [tenantId]
  );

  function onQueryChange(value: string) {
    setQ(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(value), 200);
  }

  const rows: Row[] = [
    ...results.conversations.map(
      (c): Row => ({
        kind: "conversation",
        id: c.id,
        title: c.title ?? "Untitled",
        projectId: c.project_id,
        shared: !c.is_mine,
      })
    ),
    ...results.documents.map(
      (d): Row => ({ kind: "document", id: d.id, title: d.title, projectId: d.project_id })
    ),
    ...results.contacts.map(
      (c): Row => ({
        kind: "contact",
        id: c.id,
        title: c.name,
        detail: [c.job_title, c.company_name].filter(Boolean).join(", ") || null,
      })
    ),
  ];

  function go(row: Row) {
    setOpen(false);
    if (row.kind === "contact") {
      router.push(`/app/contacts?c=${row.id}`);
      return;
    }
    const params = new URLSearchParams();
    if (row.kind === "conversation") {
      if (row.projectId) params.set("project", row.projectId);
      params.set("c", row.id);
    } else {
      params.set("view", "vault");
      if (row.projectId) params.set("project", row.projectId);
    }
    router.push(`/app?${params.toString()}`);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, rows.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && rows[active]) {
      e.preventDefault();
      go(rows[active]);
    }
  }

  if (!open || !tenantId) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 p-4 pt-[12vh]"
      onClick={() => setOpen(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search chats and documents"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg overflow-hidden rounded-[14px] border border-edge-strong bg-card shadow-card"
      >
        <div className="flex items-center gap-2.5 border-b border-edge px-4 py-3">
          <SearchIcon className="h-4 w-4 text-faint" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search chats & documents…"
            aria-label="Search chats and documents"
            className="w-full bg-transparent text-[15px] text-ink placeholder:text-faint focus:outline-none"
          />
          <kbd className="rounded-[5px] border border-edge bg-sidebar px-1.5 py-0.5 text-[10.5px] font-bold text-faint">
            esc
          </kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto p-2">
          {failed && (
            <p className="px-3 py-2 text-sm font-semibold text-danger">
              Search failed — try again.
            </p>
          )}
          {!failed && q.trim() && rows.length === 0 && (
            <p className="px-3 py-2 text-sm text-faint">No matches for “{q.trim()}”.</p>
          )}
          {!q.trim() && (
            <p className="px-3 py-2 text-sm text-faint">
              Type to search your conversations and vault documents.
            </p>
          )}
          {(["conversation", "document", "contact"] as const).map((kind) => {
            const group = rows
              .map((row, i) => ({ row, i }))
              .filter(({ row }) => row.kind === kind);
            if (group.length === 0) return null;
            const label =
              kind === "conversation" ? "Chats" : kind === "document" ? "Documents" : "Contacts";
            return (
              <div key={kind}>
                <p className="px-3 pt-2 pb-1 text-[10.5px] font-bold tracking-[.1em] text-faint uppercase">
                  {label}
                </p>
                {group.map(({ row, i }) => (
                  <button
                    key={`${row.kind}-${row.id}`}
                    onClick={() => go(row)}
                    onMouseEnter={() => setActive(i)}
                    className={`flex w-full items-center gap-2.5 rounded-[10px] px-3 py-2 text-left text-[13.5px] font-semibold ${
                      i === active ? "bg-accent-tint text-electric-blue" : "text-subtle"
                    }`}
                  >
                    {row.kind === "conversation" ? (
                      <ChatIcon className="h-3.5 w-3.5" />
                    ) : row.kind === "document" ? (
                      <DocIcon className="h-3.5 w-3.5" />
                    ) : (
                      <PeopleIcon className="h-3.5 w-3.5" />
                    )}
                    <span className="truncate">{row.title}</span>
                    {row.kind === "contact" && row.detail && (
                      <span className="truncate text-[11.5px] font-medium text-faint">
                        {row.detail}
                      </span>
                    )}
                    <span className="ml-auto text-[10.5px] font-bold text-faint uppercase">
                      {row.kind === "conversation"
                        ? row.shared
                          ? "shared"
                          : "chat"
                        : row.kind === "document"
                          ? "vault"
                          : "contact"}
                    </span>
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
