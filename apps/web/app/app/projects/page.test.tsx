import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { withWorkspace } from "@/test/workspace";
import type { Tenant } from "../workspace";

const gw = vi.fn();
vi.mock("@/lib/groundwork", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/groundwork")>()),
  gw: (...args: unknown[]) => gw(...args),
  tenantId: () => "11111111-1111-1111-1111-111111111111",
}));

const { default: PortfolioPage } = await import("./page");

const withFlag = (projects: unknown) =>
  ({ tenant: { features: { projects } } as unknown as Tenant });

describe("development projects portfolio", () => {
  beforeEach(() => gw.mockReset());

  it("shows the disabled panel instead of a raw error when the module is off", async () => {
    render(withWorkspace(<PortfolioPage />, withFlag(false)));
    expect(
      await screen.findByText(/development projects aren't switched on/i)
    ).toBeInTheDocument();
  });

  it("does not call the API for a module the workspace does not have", () => {
    // The point of reading the flag from workspace state: no doomed request,
    // and no 404 to render.
    render(withWorkspace(<PortfolioPage />, withFlag(false)));
    expect(gw).not.toHaveBeenCalled();
  });

  it("waits for the workspace before deciding, so the panel cannot flash", () => {
    render(withWorkspace(<PortfolioPage />, { loading: true, tenant: null }));
    expect(screen.queryByText(/aren't switched on/i)).toBeNull();
    expect(gw).not.toHaveBeenCalled();
  });

  it("loads the portfolio when the module is on", async () => {
    gw.mockResolvedValue([]);
    render(withWorkspace(<PortfolioPage />, withFlag(true)));
    await waitFor(() => expect(gw).toHaveBeenCalledWith("/projects/portfolio"));
    expect(
      await screen.findByText(/track each development scheme/i)
    ).toBeInTheDocument();
  });
});
