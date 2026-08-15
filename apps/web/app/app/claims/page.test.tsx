import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { withWorkspace } from "@/test/workspace";
import type { Claim } from "@/lib/claims";

const listClaims = vi.fn();
const updateClaim = vi.fn();
const deleteClaim = vi.fn();
const listClaimKinds = vi.fn();
const createClaim = vi.fn();
const listMembers = vi.fn();
const push = vi.fn();
// Mutable so a test can put the page on ?owner=none, which is how Settings
// links here after releasing somebody's facts.
const searchParams = { current: new URLSearchParams() };

vi.mock("@/lib/claims", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/claims")>()),
  listClaims: () => listClaims(),
  listClaimKinds: () => listClaimKinds(),
  createClaim: (...args: unknown[]) => createClaim(...args),
  updateClaim: (...args: unknown[]) => updateClaim(...args),
  deleteClaim: (...args: unknown[]) => deleteClaim(...args),
}));
vi.mock("@/lib/members", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/members")>()),
  listMembers: () => listMembers(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  useSearchParams: () => searchParams.current,
  usePathname: () => "/app/claims",
}));

const { default: ClaimsPage } = await import("./page");

const ADE = { id: "m-ade", user_id: "u1", role: "member", email: "ade@example.com" };
const SAM = { id: "m-sam", user_id: "u2", role: "admin", email: "sam@example.com" };

const claim = (over: Partial<Claim> = {}): Claim =>
  ({
    id: "c-1",
    kind: "annual_income",
    label: "Annual income",
    category: "finance",
    subject: null,
    period: null,
    statement: "The organisation's annual income was £412,000.",
    value: 412000,
    unit: "GBP",
    as_of: null,
    expires_on: null,
    status: "confirmed",
    source: "register",
    source_ref: null,
    source_document_id: null,
    source_document_title: null,
    source_chunk_id: null,
    owner_membership_id: null,
    last_verified: "2026-08-01",
    next_review: "2026-11-01",
    notes: null,
    stale: false,
    expired: false,
    ...over,
  }) as Claim;

/** The owner picker for a row, found by the fact it belongs to. */
const picker = (statement: string) =>
  screen.getByLabelText(`Who looks after “${statement}”`, { exact: false });

describe("who looks after a fact", () => {
  beforeEach(() => {
    listClaims.mockReset();
    updateClaim.mockReset();
    listMembers.mockReset().mockResolvedValue([ADE, SAM]);
    push.mockReset();
    searchParams.current = new URLSearchParams();
    updateClaim.mockResolvedValue(claim());
  });

  it("offers the workspace's people against a confirmed fact", async () => {
    listClaims.mockResolvedValue([claim()]);
    render(withWorkspace(<ClaimsPage />));

    const select = await waitFor(() => picker("The organisation's annual income was £412,000."));
    expect(select).toHaveValue("");
    expect(screen.getByRole("option", { name: "ade@example.com" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /nobody looks after this/i })).toBeInTheDocument();
  });

  it("does not ask who owns a fact nobody has asserted yet", async () => {
    // A proposal is a question about whether the fact is right. Who keeps it
    // right only becomes a question once somebody has said it is.
    listClaims.mockResolvedValue([claim({ status: "proposed" })]);
    render(withWorkspace(<ClaimsPage />));

    await screen.findByText(/1 fact to check/i);
    expect(screen.queryByLabelText(/who looks after/i)).toBeNull();
  });

  it("hands a fact to somebody", async () => {
    listClaims.mockResolvedValue([claim()]);
    render(withWorkspace(<ClaimsPage />));

    const select = await waitFor(() => picker("The organisation's annual income was £412,000."));
    await userEvent.selectOptions(select, "m-ade");
    expect(updateClaim).toHaveBeenCalledWith("c-1", { owner_membership_id: "m-ade" });
  });

  it("hands a fact back to nobody by sending an explicit null", async () => {
    // The contract this whole half rests on: null clears the owner, and an
    // omitted field leaves it alone. Sending "" or omitting it would silently
    // make handing something back impossible.
    listClaims.mockResolvedValue([claim({ owner_membership_id: "m-ade" })]);
    render(withWorkspace(<ClaimsPage />));

    const select = await waitFor(() => picker("The organisation's annual income was £412,000."));
    expect(select).toHaveValue("m-ade");
    await userEvent.selectOptions(select, "");
    expect(updateClaim).toHaveBeenCalledWith("c-1", { owner_membership_id: null });
  });

  it("still names an owner who has just been removed elsewhere", async () => {
    listClaims.mockResolvedValue([claim({ owner_membership_id: "m-gone" })]);
    render(withWorkspace(<ClaimsPage />));

    expect(await screen.findByRole("option", { name: /somebody who has left/i })).toBeInTheDocument();
  });
});

describe("the facts nobody looks after", () => {
  beforeEach(() => {
    listClaims.mockReset();
    updateClaim.mockReset();
    listMembers.mockReset().mockResolvedValue([ADE, SAM]);
    push.mockReset();
    searchParams.current = new URLSearchParams();
  });

  it("offers the view once somebody owns something", async () => {
    listClaims.mockResolvedValue([
      claim({ id: "c-1", owner_membership_id: "m-ade" }),
      claim({ id: "c-2", statement: "The organisation has 6 trustees.", kind: "trustee_count" }),
    ]);
    render(withWorkspace(<ClaimsPage />));

    const link = await screen.findByRole("button", { name: /1 fact has nobody looking after it/i });
    await userEvent.click(link);
    expect(push).toHaveBeenCalledWith("/app/claims?owner=none");
  });

  it("stays quiet while nobody owns anything", async () => {
    // Which is every workspace until somebody starts assigning. "See the 2
    // facts nobody owns" when that is both of them is noise, not a finding.
    listClaims.mockResolvedValue([claim({ id: "c-1" }), claim({ id: "c-2" })]);
    render(withWorkspace(<ClaimsPage />));

    await waitFor(() => expect(listClaims).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /nobody looking after/i })).toBeNull();
  });

  it("shows only the unowned facts, and not the proposals", async () => {
    searchParams.current = new URLSearchParams("owner=none");
    listClaims.mockResolvedValue([
      claim({ id: "c-1", owner_membership_id: "m-ade" }),
      claim({ id: "c-2", statement: "The organisation has 6 trustees." }),
      claim({ id: "c-3", statement: "The organisation employs 12 people.", status: "proposed" }),
    ]);
    render(withWorkspace(<ClaimsPage />));

    expect(await screen.findByText("The organisation has 6 trustees.")).toBeInTheDocument();
    expect(screen.queryByText("The organisation's annual income was £412,000.")).toBeNull();
    expect(screen.queryByText(/fact to check/i)).toBeNull();
  });

  it("does not present an unowned fact as a fault", async () => {
    // ASSUMPTIONS #43. Nothing here is wrong: these facts are true and simply
    // nobody's, which is the ordinary state of most of them.
    searchParams.current = new URLSearchParams("owner=none");
    listClaims.mockResolvedValue([claim()]);
    const { container } = render(withWorkspace(<ClaimsPage />));

    await screen.findByText(/nobody looking after it/i);
    expect(container.querySelector(".text-warn")).toBeNull();
  });

  it("offers a way back to the whole register", async () => {
    searchParams.current = new URLSearchParams("owner=none");
    listClaims.mockResolvedValue([claim()]);
    render(withWorkspace(<ClaimsPage />));

    await userEvent.click(await screen.findByRole("button", { name: /show everything/i }));
    expect(push).toHaveBeenCalledWith("/app/claims");
  });
});

const KIND = {
  key: "trading_name",
  label: "Trading name",
  category: "identity" as const,
  value_kind: "text" as const,
  unit: null,
  cardinality: "single" as const,
  periodic: false,
  review_days: 365,
  statement_template: "The organisation trades as {value}.",
  question_hints: [],
  register_key: null,
  notes: null,
};

describe("adding a fact by hand", () => {
  beforeEach(() => {
    listClaims.mockReset().mockResolvedValue([]);
    listClaimKinds.mockReset().mockResolvedValue([KIND]);
    createClaim.mockReset().mockResolvedValue({ id: "c-new" });
    listMembers.mockReset().mockResolvedValue([]);
    searchParams.current = new URLSearchParams();
  });

  it("lets somebody type a fact the registers do not publish", async () => {
    render(withWorkspace(<ClaimsPage />));
    await userEvent.click(await screen.findByRole("button", { name: /add a fact yourself/i }));
    await screen.findByLabelText(/what kind of fact/i);
    await userEvent.type(screen.getByLabelText(/^value$/i), "Riverside Trust");
    await userEvent.click(screen.getByRole("button", { name: /add this fact/i }));
    await waitFor(() =>
      expect(createClaim).toHaveBeenCalledWith(
        expect.objectContaining({
          kind: "trading_name",
          value: "Riverside Trust",
          statement: "The organisation trades as Riverside Trust.",
        }),
      ),
    );
  });

  it("says what is missing instead of submitting an empty form", async () => {
    // The statement auto-fills from the template, so an untouched form still
    // reads as a sentence — the value check is what stops "…trades as .".
    render(withWorkspace(<ClaimsPage />));
    await userEvent.click(await screen.findByRole("button", { name: /add a fact yourself/i }));
    await screen.findByLabelText(/what kind of fact/i);
    await userEvent.click(screen.getByRole("button", { name: /add this fact/i }));
    expect(await screen.findByText("This fact needs a value")).toBeInTheDocument();
    expect(createClaim).not.toHaveBeenCalled();
  });
});

describe("removing a fact", () => {
  beforeEach(() => {
    listClaims.mockReset().mockResolvedValue([claim()]);
    deleteClaim.mockReset().mockResolvedValue(undefined);
    listMembers.mockReset().mockResolvedValue([]);
    searchParams.current = new URLSearchParams();
  });

  it("asks twice before deleting", async () => {
    render(withWorkspace(<ClaimsPage />));
    await userEvent.click(await screen.findByRole("button", { name: /^remove$/i }));
    expect(deleteClaim).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /remove for good/i }));
    await waitFor(() => expect(deleteClaim).toHaveBeenCalledWith("c-1"));
  });

  it("offers a way back from the first click", async () => {
    render(withWorkspace(<ClaimsPage />));
    await userEvent.click(await screen.findByRole("button", { name: /^remove$/i }));
    await userEvent.click(screen.getByRole("button", { name: /^keep$/i }));
    expect(deleteClaim).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /^remove$/i })).toBeInTheDocument();
  });
});

describe("ECCTA readiness strip", () => {
  const idv = (subject: string, value: string): Claim =>
    claim({
      id: `idv-${subject}`,
      kind: "director_idv",
      label: "Director identity verification",
      category: "governance",
      subject,
      value,
      statement: `${subject}'s Companies House identity is ${value}.`,
    });

  beforeEach(() => {
    listClaims.mockReset();
    listMembers.mockReset().mockResolvedValue([]);
    searchParams.current = new URLSearchParams();
  });

  it("warns while a director is unverified, with the filing date", async () => {
    listClaims.mockResolvedValue([
      idv("FRY, Sarah", "verified on 2025-07-16 via DE PINNA LLP"),
      idv("DUNN, Morag", "not yet verified"),
      claim({
        id: "cs-due",
        kind: "confirmation_statement_due",
        label: "Confirmation statement due",
        category: "governance",
        value: "2026-09-15",
        statement: "The organisation's next confirmation statement is due 2026-09-15.",
      }),
    ]);
    render(withWorkspace(<ClaimsPage />));
    const strip = await screen.findByText(/1 of 2 directors have verified their identity/i);
    expect(strip.textContent).toMatch(/18 Nov 2026/);
    expect(strip.textContent).toMatch(/due 15 Sept? 2026/);
  });

  it("reads as a trust state once everyone has verified", async () => {
    listClaims.mockResolvedValue([
      idv("FRY, Sarah", "verified on 2025-07-16 via DE PINNA LLP"),
      idv("OKAFOR, Ade", "verified — verification requirements complete (from 16 April 2026)"),
    ]);
    render(withWorkspace(<ClaimsPage />));
    const strip = await screen.findByText(/All 2 directors have verified their identity/i);
    expect(strip.textContent).not.toMatch(/blocks filings/);
  });

  it("stays silent for a workspace with no register directors", async () => {
    listClaims.mockResolvedValue([claim()]);
    render(withWorkspace(<ClaimsPage />));
    await screen.findAllByText(/annual income/i);
    expect(screen.queryByText(/verified their identity/i)).not.toBeInTheDocument();
  });
});
