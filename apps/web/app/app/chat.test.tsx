import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { withWorkspace } from "@/test/workspace";
import { routerMock } from "@/vitest.setup";
import type { Conversation, Tenant } from "./workspace";

// next/navigation is mocked globally in vitest.setup; reuse that router rather
// than a second mock, which would silently shadow it.
const replace = routerMock.replace;

const apiFn = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: (...args: unknown[]) => apiFn(...args),
  apiStream: vi.fn(),
}));

const { default: ChatPanel } = await import("./chat");

const TENANT = { id: "t-1", features: {} } as unknown as Tenant;
const GONE = "e1f3e58e-0fa1-4d3b-9d16-54cd306c3077";

/** The workspace as it is a moment after a chat is deleted: the list has
 *  reloaded successfully and simply no longer contains it. */
const afterDelete = (conversations: Conversation[] = []) => ({
  tenant: TENANT,
  conversations,
  conversationsLoaded: true,
});

describe("an open conversation that no longer exists", () => {
  beforeEach(() => {
    replace.mockReset();
    apiFn.mockReset();
    apiFn.mockResolvedValue([]);
  });

  it("drops it from the URL instead of stranding the composer", async () => {
    // Deleting the open chat left `?c=<deleted-id>` in the address. The
    // read-only guard then called it somebody else's chat and offered no way
    // back — a dead end also reachable by refresh, back button or a bookmark.
    render(
      withWorkspace(
        <ChatPanel activeProjectId={null} activeConversationId={GONE} />,
        afterDelete()
      )
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/app"));
  });

  it("keeps the project scope when clearing the dead conversation", async () => {
    render(
      withWorkspace(
        <ChatPanel activeProjectId="p-9" activeConversationId={GONE} />,
        afterDelete()
      )
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/app?project=p-9"));
  });

  it("does not request messages for it, so no error banner paints", async () => {
    render(
      withWorkspace(
        <ChatPanel activeProjectId={null} activeConversationId={GONE} />,
        afterDelete()
      )
    );
    await waitFor(() => expect(replace).toHaveBeenCalled());
    const asked = apiFn.mock.calls.some((c) => String(c[0]).includes(GONE));
    expect(asked).toBe(false);
    expect(screen.queryByText(/isn't one of yours/i)).toBeNull();
  });

  it("still fails closed when the list could not be loaded at all", async () => {
    // The distinction the fix has to preserve: a list that *failed* tells us
    // nothing about ownership, so the composer must stay shut and the URL
    // must be left alone rather than discarding a chat that may be fine.
    render(
      withWorkspace(<ChatPanel activeProjectId={null} activeConversationId={GONE} />, {
        tenant: TENANT,
        conversations: [],
        conversationsLoaded: false,
      })
    );
    expect(await screen.findByText(/couldn't check who owns this chat/i)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("leaves a conversation that does exist alone", async () => {
    const mine = {
      id: GONE,
      title: "still here",
      project_id: null,
      visibility: "private",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_mine: true,
      owner_email: "member@example.com",
    } as unknown as Conversation;
    render(
      withWorkspace(
        <ChatPanel activeProjectId={null} activeConversationId={GONE} />,
        afterDelete([mine])
      )
    );
    await waitFor(() =>
      expect(apiFn.mock.calls.some((c) => String(c[0]).includes(GONE))).toBe(true)
    );
    expect(replace).not.toHaveBeenCalled();
  });
});
