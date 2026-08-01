"use client";

import { useSearchParams } from "next/navigation";
import { useWorkspace } from "./workspace";
import ChatPanel from "./chat";
import VaultPanel from "./vault";

export default function WorkspacePage() {
  const sp = useSearchParams();
  const ws = useWorkspace();

  // The layout gates on loading / onboarding; nothing to render until then.
  if (!ws.tenant) return null;

  const view = sp.get("view") === "vault" ? "vault" : "chat";
  const activeProjectId = sp.get("project");

  return view === "chat" ? (
    <ChatPanel activeProjectId={activeProjectId} activeConversationId={sp.get("c")} />
  ) : (
    <VaultPanel
      tenantId={ws.tenant.id}
      projects={ws.projects}
      activeProjectId={activeProjectId}
      onProjectsChanged={ws.refreshProjects}
    />
  );
}
