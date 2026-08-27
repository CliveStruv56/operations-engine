import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { withWorkspace } from "@/test/workspace";
import type { Tenant } from "../workspace";
import type { CommunityAsset, CommunityProfile, CommunityStat } from "@/lib/community";

const getCommunityProfile = vi.fn();
const listCommunityAssets = vi.fn();
const listCommunityStats = vi.fn();
const listClaimKinds = vi.fn();

vi.mock("@/lib/community", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/community")>()),
  getCommunityProfile: () => getCommunityProfile(),
  listCommunityAssets: () => listCommunityAssets(),
  listCommunityStats: () => listCommunityStats(),
}));
vi.mock("@/lib/claims", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/claims")>()),
  listClaimKinds: () => listClaimKinds(),
}));

const { default: CommunityPage } = await import("./page");

const enabled = { features: { community: true } } as unknown as Tenant;

const profile: CommunityProfile = {
  id: "p1",
  place_name: "Sanday",
  description: "The largest of Orkney's north isles.",
  geography_note: "80 minutes by ferry from Kirkwall.",
  council_area: "Orkney Islands Council",
  settlements: ["Lady Village", "Kettletoft"],
  census_area_codes: [],
  data_sources_note: "Scotland's Census 2022.",
  created_by: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

const school: CommunityAsset = {
  id: "a1",
  category: "education",
  subcategory: "primary and secondary",
  name: "Sanday Community School",
  description: null,
  attributes: { pupils: 68, nursery: true },
  status: "open",
  settlement: "Lady Village",
  contact: null,
  url: null,
  notes: null,
  created_by: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

const households: CommunityStat = {
  id: "s1",
  label: "Households",
  value: 240,
  unit: "households",
  period: "2022",
  as_of: null,
  claim_kind: "community_households",
  source: "Scotland's Census 2022",
  source_url: null,
  notes: null,
  claim_id: null,
  created_by: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

describe("the community profile page", () => {
  beforeEach(() => {
    getCommunityProfile.mockReset().mockResolvedValue(profile);
    listCommunityAssets.mockReset().mockResolvedValue([school]);
    listCommunityStats.mockReset().mockResolvedValue([households]);
    listClaimKinds.mockReset().mockResolvedValue([]);
  });

  it("shows the disabled panel when the workspace lacks the module", () => {
    render(
      withWorkspace(<CommunityPage />, {
        tenant: { features: {} } as unknown as Tenant,
      })
    );
    expect(screen.getByRole("heading")).toHaveTextContent(
      "The community profile isn't switched on"
    );
    // Nothing was fetched for a module the tenant does not have.
    expect(getCommunityProfile).not.toHaveBeenCalled();
  });

  it("renders the place, its headline figures and its facilities", async () => {
    render(withWorkspace(<CommunityPage />, { tenant: enabled }));

    expect(await screen.findByRole("heading", { name: "Sanday" })).toBeInTheDocument();
    // A register-feeding figure leads the page.
    expect(await screen.findByText("240")).toBeInTheDocument();
    expect(screen.getByText("Households")).toBeInTheDocument();
    // Assets group under their category heading with their details inline.
    expect(screen.getByText("Schools and learning")).toBeInTheDocument();
    expect(screen.getByText("Sanday Community School")).toBeInTheDocument();
    expect(screen.getByText(/pupils: 68/)).toBeInTheDocument();
    expect(screen.getByText(/nursery: yes/)).toBeInTheDocument();
    // The profile's own source note closes the page.
    expect(screen.getByText(/Sources: Scotland's Census 2022\./)).toBeInTheDocument();
  });

  it("points an empty workspace at describing the place first", async () => {
    getCommunityProfile.mockResolvedValue(null);
    listCommunityAssets.mockResolvedValue([]);
    listCommunityStats.mockResolvedValue([]);
    render(withWorkspace(<CommunityPage />, { tenant: enabled }));

    expect(await screen.findByText("Nothing here yet")).toBeInTheDocument();
    // Header and empty-state card both offer it; either is a fine way in.
    expect(screen.getAllByRole("button", { name: "Describe the place" }).length).toBeGreaterThan(0);
  });
});
