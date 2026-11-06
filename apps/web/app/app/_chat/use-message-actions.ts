import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { openPresigned } from "@/lib/groundwork";
import { useToast } from "@/components/toast";
import type { Message } from "./types";

/** A vault title for a saved answer: its first heading or line, else dated. */
export function vaultTitle(content: string): string {
  const line = content
    .split("\n")
    .map((l) =>
      l
        .replace(/^#+\s*/, "")
        .replace(/\*\*/g, "")
        .trim()
    )
    .find(Boolean);
  return (line ?? `Chat answer — ${new Date().toLocaleDateString("en-GB")}`).slice(0, 120);
}

/** Put a file into Documents through the ordinary pipeline: register it,
 *  upload to the presigned URL, then mark it complete so ingest starts. */
export async function uploadDocument(
  tenantId: string,
  body: Blob,
  meta: {
    title: string;
    mime: string;
    project_id: string | null;
    conversation_id: string;
  }
): Promise<void> {
  const { id, upload_url } = await api<{ id: string; upload_url: string }>(
    "/documents",
    {
      method: "POST",
      body: JSON.stringify({
        title: meta.title,
        mime: meta.mime,
        size_bytes: body.size,
        project_id: meta.project_id,
        conversation_id: meta.conversation_id,
      }),
    },
    tenantId
  );
  const put = await fetch(upload_url, {
    method: "PUT",
    headers: { "Content-Type": meta.mime },
    body,
  });
  if (!put.ok) throw new Error(`Upload failed (${put.status})`);
  await api(`/documents/${id}/complete`, { method: "POST" }, tenantId);
}

/** The actions under each answer — slides, PDF, save to documents, and the
 *  two recoveries for an answer the documents could not back.
 *
 *  Every callback is a stable useCallback that takes the message id, and
 *  reads messages through a ref, so AssistantMessage's memo keeps holding
 *  while a reply streams. */
export function useMessageActions({
  conversationId,
  tenantId,
  activeProjectId,
  messages,
  refreshDocs,
  setError,
}: {
  conversationId: string | null;
  tenantId: string;
  activeProjectId: string | null;
  messages: Message[];
  refreshDocs: () => void;
  setError: (error: string | null) => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [pdfId, setPdfId] = useState<string | null>(null);

  const messagesRef = useRef<Message[]>([]);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const exportSlides = useCallback(
    async (messageId: string) => {
      if (!conversationId) return;
      setExportingId(messageId);
      setError(null);
      try {
        const out = await api<{ download_url: string }>(
          `/conversations/${conversationId}/messages/${messageId}/slides`,
          { method: "POST" },
          tenantId
        );
        openPresigned(out.download_url);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setExportingId(null);
      }
    },
    [conversationId, tenantId, setError]
  );

  const saveToVault = useCallback(
    async (messageId: string) => {
      const msg = messagesRef.current.find((x) => x.id === messageId);
      if (!msg || !conversationId) return;
      setSavingId(messageId);
      setError(null);
      try {
        const title = vaultTitle(msg.content);
        await uploadDocument(tenantId, new Blob([msg.content], { type: "text/markdown" }), {
          title,
          mime: "text/markdown",
          project_id: activeProjectId,
          conversation_id: conversationId,
        });
        toast({ message: `Saved to documents — “${title}” is indexing.` });
        refreshDocs();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setSavingId(null);
      }
    },
    [conversationId, tenantId, activeProjectId, toast, refreshDocs, setError]
  );

  const exportPdf = useCallback(
    async (messageId: string) => {
      if (!conversationId) return;
      setPdfId(messageId);
      setError(null);
      try {
        const job = await api<{ id: string }>(
          `/conversations/${conversationId}/messages/${messageId}/pdf`,
          { method: "POST" },
          tenantId
        );
        // Same shape as the health-card poll: the worker renders, we wait.
        for (;;) {
          await new Promise((r) => setTimeout(r, 2000));
          const j = await api<{
            status: string;
            error: string | null;
            download_url: string | null;
          }>(`/conversations/exports/${job.id}`, {}, tenantId);
          if (j.status === "succeeded" && j.download_url) {
            openPresigned(j.download_url);
            break;
          }
          if (j.status === "failed") throw new Error(j.error ?? "The PDF could not be built");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setPdfId(null);
      }
    },
    [conversationId, tenantId, setError]
  );

  // Recovery from "the vault does not contain X": put the missing thing in.
  const addDocument = useCallback(() => {
    const q = new URLSearchParams({ view: "vault", upload: "1" });
    if (activeProjectId) q.set("project", activeProjectId);
    router.push(`/app?${q}`);
  }, [router, activeProjectId]);

  const assertFact = useCallback(
    (messageId: string) => {
      // The thing that was missing is what the person asked — the user
      // message just before this answer.
      const list = messagesRef.current;
      const i = list.findIndex((x) => x.id === messageId);
      const asked = list
        .slice(0, Math.max(i, 0))
        .reverse()
        .find((x) => x.role === "user")?.content;
      const topic = (asked ?? "").slice(0, 200);
      router.push(`/app/claims?add=1${topic ? `&topic=${encodeURIComponent(topic)}` : ""}`);
    },
    [router]
  );

  return {
    exportingId,
    savingId,
    pdfId,
    exportSlides,
    saveToVault,
    exportPdf,
    addDocument,
    assertFact,
  };
}
