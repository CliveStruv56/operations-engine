import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AdminTenantRow } from "@/lib/admin";

const updateFeatures = vi.fn().mockResolvedValue({});
vi.mock("@/lib/admin", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/admin")>()),
  // A module the hand-mirrored FEATURE_FLAGS list has never heard of.
  listModules: () =>
    Promise.resolve([
      { flag: "projects", label: "Development projects", kinds: [], addons: [] },
      { flag: "tenders", label: "Tenders", kinds: [], addons: [] },
    ]),
  updateFeatures: (...args: unknown[]) => updateFeatures(...args),
}));

const { ModulesEditor } = await import("./ModulesEditor");

const TENANT = {
  id: "t1",
  name: "Riverside",
  features: { projects: true },
} as unknown as AdminTenantRow;

describe("the modules editor", () => {
  it("saves a module the API lists even if the console's own list lacks it", async () => {
    render(<ModulesEditor tenant={TENANT} onClose={() => {}} onSaved={() => {}} />);
    await userEvent.click(await screen.findByRole("checkbox", { name: /Tenders/ }));
    await userEvent.click(screen.getByRole("button", { name: "Save modules" }));
    expect(updateFeatures).toHaveBeenCalledWith("t1", { tenders: true });
  });

  it("reads untouched boxes from the workspace's own row", async () => {
    render(<ModulesEditor tenant={TENANT} onClose={() => {}} onSaved={() => {}} />);
    expect(await screen.findByRole("checkbox", { name: /Development projects/ })).toBeChecked();
    expect(screen.getByRole("button", { name: "No changes" })).toBeDisabled();
  });
});
