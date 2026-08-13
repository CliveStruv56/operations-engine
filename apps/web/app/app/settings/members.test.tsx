import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Tenant } from "../workspace";

const api = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: (...args: unknown[]) => api(...args),
}));

const { default: Members } = await import("./members");

const TENANT = { id: "t1", role: "owner" } as Tenant;

const ADE = {
  id: "m-ade",
  user_id: "u1",
  role: "member",
  email: "ade@example.com",
  created_at: "2026-01-01T00:00:00Z",
};
const OWNER = { ...ADE, id: "m-own", user_id: "u0", role: "owner", email: "boss@example.com" };

/** The member list, then whatever the removal answers. */
function respond(claimsDisowned: number) {
  let removed = false;
  api.mockImplementation((path: string, init?: RequestInit) => {
    if (init?.method === "DELETE") {
      removed = true;
      return Promise.resolve({ claims_disowned: claimsDisowned });
    }
    return Promise.resolve(removed ? [OWNER] : [OWNER, ADE]);
  });
}

/** Every row has a Remove button, so this works within Ade's own row. */
async function removeAde() {
  const row = (await screen.findByText("ade@example.com")).closest("tr") as HTMLElement;
  await userEvent.click(within(row).getByRole("button", { name: /^remove$/i }));
  await userEvent.click(within(row).getByRole("button", { name: /^yes$/i }));
}

describe("removing somebody who looked after facts", () => {
  beforeEach(() => api.mockReset());

  it("says how many facts are now nobody's, and offers to reassign them", async () => {
    // §14.2. The count already reached `audit_log`, which nobody reads. This is
    // the only moment the admin can actually hand these facts to somebody else.
    respond(4);
    render(<Members tenant={TENANT} />);
    await removeAde();

    expect(await screen.findByText(/4 facts about your organisation/i)).toBeInTheDocument();
    expect(screen.getByText(/ade@example.com/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /hand them to somebody/i })).toHaveAttribute(
      "href",
      "/app/claims?owner=none"
    );
  });

  it("says nothing when they looked after nothing", async () => {
    // Ownership is optional and most facts never have an owner, so this is the
    // ordinary case. A notice reading "0 facts" on every removal is noise.
    respond(0);
    render(<Members tenant={TENANT} />);
    await removeAde();

    expect(screen.queryByRole("link", { name: /hand/i })).toBeNull();
  });

  it("does not present the release as an error", async () => {
    // The facts are still true and still used in drafts; they just have nobody
    // named against them.
    respond(2);
    render(<Members tenant={TENANT} />);
    await removeAde();

    const notice = await screen.findByText(/2 facts about your organisation/i);
    expect(notice).toHaveTextContent(/still in your register/i);
    expect(notice.closest(".text-danger")).toBeNull();
  });
});
