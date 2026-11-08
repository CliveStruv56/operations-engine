import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getSession = vi.fn();

const createClient = vi.fn(() => ({ auth: { getSession: () => getSession() } }));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => createClient(),
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

const { SiteHeader } = await import("./site-header");

describe("the marketing header and the session", () => {
  beforeEach(() => getSession.mockReset());

  it("offers the way back into the workspace to a signed-in visitor", async () => {
    // A signed-in visitor shown "Sign in" reads it as "you were logged out"
    // and retypes credentials that were never lost.
    getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
    render(<SiteHeader />);

    const link = await waitFor(() => screen.getByRole("link", { name: "Open app" }));
    expect(link).toHaveAttribute("href", "/app");
    expect(screen.queryByRole("link", { name: "Sign in" })).toBeNull();
  });

  it("offers sign-in when there is no session", async () => {
    getSession.mockResolvedValue({ data: { session: null } });
    render(<SiteHeader />);

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    const link = screen.getByRole("link", { name: "Sign in" });
    expect(link).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("link", { name: "Open app" })).toBeNull();
  });

  it("stays signed out when the Supabase client can't be created", async () => {
    // Previews have no NEXT_PUBLIC_SUPABASE_* values and createClient()
    // throws synchronously; that must not escape the effect and blank the page.
    createClient.mockImplementationOnce(() => {
      throw new Error("@supabase/ssr: Your project's URL and API key are required");
    });
    render(<SiteHeader />);

    await waitFor(() => expect(createClient).toHaveBeenCalled());
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(getSession).not.toHaveBeenCalled();
  });

  // No failure-path test for getSession: a rejected session read leaves `authed` at its
  // initial false, which the signed-out test already pins — and vitest's
  // unhandled-rejection tracker flags the mock however lazily it rejects.
});
