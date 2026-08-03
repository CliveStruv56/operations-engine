import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { withWorkspace } from "@/test/workspace";
import type { Tenant } from "../workspace";

const gr = vi.fn();
vi.mock("@/lib/grants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/grants")>()),
  gr: (...args: unknown[]) => gr(...args),
}));
vi.mock("@/lib/groundwork", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/groundwork")>()),
  tenantId: () => "11111111-1111-1111-1111-111111111111",
}));

const { default: GrantsPage } = await import("./page");

const withFlag = (grants: unknown) =>
  ({ tenant: { features: { grants } } as unknown as Tenant });

const row = (over: Record<string, unknown> = {}) => ({
  id: "app-1",
  title: "Community garden project",
  funder_id: null,
  funder_name: "Borough Community Foundation",
  status: "pipeline",
  stage_current: "case",
  amount_requested: 40000,
  amount_awarded: null,
  restricted: true,
  deadline: null,
  updated_at: "2026-08-01T00:00:00Z",
  weighted_value: 2000,
  open_conditions: 0,
  overdue_returns: 0,
  next_return_due: null,
  ...over,
});

/** Read one summary tile's figure — the same numbers also appear in the table
 *  rows, so an unscoped query cannot tell the two apart. */
const tile = (label: string) =>
  within(screen.getByText(label).parentElement as HTMLElement).getByText(/^£|^\d/);

/** The page loads the portfolio and the calendar together. */
const respond = (applications: unknown[], calendar: unknown[] = []) =>
  gr.mockImplementation((path: string) =>
    Promise.resolve(path === "/grants/applications" ? applications : calendar)
  );

describe("grant funding portfolio", () => {
  beforeEach(() => gr.mockReset());

  it("shows the disabled panel instead of a raw error when the module is off", async () => {
    render(withWorkspace(<GrantsPage />, withFlag(false)));
    expect(await screen.findByText(/grant funding isn't switched on/i)).toBeInTheDocument();
  });

  it("does not call the API for a module the workspace does not have", () => {
    render(withWorkspace(<GrantsPage />, withFlag(false)));
    expect(gr).not.toHaveBeenCalled();
  });

  it("waits for the workspace before deciding, so the panel cannot flash", () => {
    render(withWorkspace(<GrantsPage />, { loading: true, tenant: null }));
    expect(screen.queryByText(/isn't switched on/i)).toBeNull();
    expect(gr).not.toHaveBeenCalled();
  });

  it("loads the portfolio and the calendar when the module is on", async () => {
    respond([]);
    render(withWorkspace(<GrantsPage />, withFlag(true)));
    await waitFor(() => expect(gr).toHaveBeenCalledWith("/grants/applications"));
    expect(gr).toHaveBeenCalledWith("/grants/reporting-calendar");
    expect(await screen.findByText(/track every bid from case for support/i)).toBeInTheDocument();
  });

  it("weights the live pipeline by stage rather than showing the raw ask", async () => {
    // The point of the weighted figure: £40k asked at the 'case' stage is not
    // £40k of pipeline, and showing it as such would misinform a trustee board.
    respond([row()]);
    render(withWorkspace(<GrantsPage />, withFlag(true)));
    await screen.findByText("Community garden project");
    expect(tile("Pipeline, weighted")).toHaveTextContent("£2,000");
    expect(tile("Secured")).toHaveTextContent("£0");
  });

  it("counts an award as secured, not as pipeline", async () => {
    respond([row({ status: "awarded", amount_awarded: 27500, weighted_value: 27500 })]);
    render(withWorkspace(<GrantsPage />, withFlag(true)));
    await screen.findByText("Community garden project");
    expect(tile("Secured")).toHaveTextContent("£27,500");
    // Pipeline tile is zero: an awarded bid is no longer a live one.
    expect(tile("Pipeline, weighted")).toHaveTextContent("£0");
  });

  it("surfaces overdue returns on the calendar tab", async () => {
    respond(
      [row({ overdue_returns: 1, next_return_due: "2026-07-01" })],
      [
        {
          id: "p1",
          application_id: "app-1",
          label: "Year 1",
          period_start: "2026-04-01",
          period_end: "2027-03-31",
          due_date: "2026-07-01",
          status: "open",
          submitted_at: null,
          accepted_at: null,
          notes: null,
          overdue: true,
          application_title: "Community garden project",
          funder_name: "Borough Community Foundation",
          rag: "red",
        },
      ]
    );
    render(withWorkspace(<GrantsPage />, withFlag(true)));
    await screen.findByText("Community garden project");
    expect(tile("Returns overdue")).toHaveTextContent("1");

    const calendarTab = screen.getByRole("button", { name: /reporting calendar/i });
    expect(within(calendarTab).getByText(/1 overdue/)).toBeInTheDocument();
    await userEvent.click(calendarTab);
    expect(await screen.findByText("Year 1")).toBeInTheDocument();
  });
});
