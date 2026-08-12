import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Sidebar from "./sidebar";
import type { Tenant } from "./workspace";
import { withWorkspace } from "@/test/workspace";
import type { ClaimSummary } from "@/lib/claims";

const TENANT = {
  id: "t1",
  name: "Riverside Community Trust",
  plan: "trial",
  seats: 3,
  brand: {},
  features: {},
  trial_ends_at: null,
  role: "owner",
  logo_url: null,
} as Tenant;

const summary = (over: Partial<ClaimSummary> = {}): ClaimSummary => ({
  needs_attention: 0,
  stale: 0,
  expired: 0,
  proposals: 0,
  ...over,
});

function mount(claimSummary: ClaimSummary | null) {
  return render(
    withWorkspace(<Sidebar open onClose={() => {}} />, { tenant: TENANT, claimSummary })
  );
}

/** The badge, found via the nav item it hangs off rather than by class. */
const organisation = () => screen.getByRole("link", { name: /your organisation/i });

describe("the organisation nav item's count", () => {
  it("shows nothing when the register is in good order", () => {
    // Eighty healthy facts must read the same as none: a number that is always
    // there is not read, which is the rule claims_warning already follows.
    mount(summary());
    expect(organisation()).toHaveTextContent(/^Your organisation$/);
  });

  it("shows nothing while the count is unknown", () => {
    // Null covers both "not fetched yet" and "the fetch failed". Either way a
    // guess is worse than silence.
    mount(null);
    expect(organisation()).toHaveTextContent(/^Your organisation$/);
  });

  it("counts proposals and gone-off facts together", () => {
    mount(summary({ needs_attention: 2, stale: 2, expired: 1, proposals: 3 }));
    expect(organisation()).toHaveTextContent("5");
  });

  it("names the problem rather than gesturing at it", () => {
    // A bare "3" cannot tell lapsed cover apart from an unread proposal, and
    // they are different jobs. The lapsed one is said first, and said once —
    // every expired fact is past review too.
    mount(summary({ needs_attention: 2, stale: 2, expired: 1, proposals: 3 }));
    expect(organisation()).toHaveAccessibleName(
      "Your organisation — 1 lapsed, 1 past review, 3 to check"
    );
  });

  it("does not dress a pile of proposals up as a warning", () => {
    // Facts found for somebody to tick are an opportunity, not a fault.
    const { container } = mount(summary({ proposals: 4 }));
    expect(organisation()).toHaveTextContent("4");
    expect(container.querySelector(".text-warn")).toBeNull();
  });

  it("warns when a fact has actually gone off", () => {
    const { container } = mount(summary({ needs_attention: 1, stale: 1, expired: 1 }));
    expect(container.querySelector(".text-warn")).toHaveTextContent("1");
  });
});
