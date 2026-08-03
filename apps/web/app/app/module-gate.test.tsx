import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ModuleDisabled, PROJECTS_DISABLED, useModuleEnabled } from "./module-gate";
import type { Tenant } from "./workspace";
import { withWorkspace } from "@/test/workspace";

/** Reads the hook's three-state answer out into the DOM so it can be asserted. */
function Probe({ flag }: { flag: string }) {
  const enabled = useModuleEnabled(flag);
  return <span data-testid="state">{String(enabled)}</span>;
}

describe("useModuleEnabled", () => {
  it("is undefined while the workspace is still loading", () => {
    // The distinction that stops the disabled panel flashing on every load:
    // "don't know yet" must not read as "not enabled".
    render(withWorkspace(<Probe flag="projects" />, { loading: true, tenant: null }));
    expect(screen.getByTestId("state")).toHaveTextContent("undefined");
  });

  it("is false when the tenant does not have the flag", () => {
    render(
      withWorkspace(<Probe flag="projects" />, {
        tenant: { features: { contacts: true } } as unknown as Tenant,
      })
    );
    expect(screen.getByTestId("state")).toHaveTextContent("false");
  });

  it("is true only for a flag set to exactly true", () => {
    render(
      withWorkspace(<Probe flag="projects" />, {
        tenant: { features: { projects: true } } as unknown as Tenant,
      })
    );
    expect(screen.getByTestId("state")).toHaveTextContent("true");
  });

  it("treats a truthy-but-not-true flag as off, matching the API gate", () => {
    // The API tests `features->>'projects' = 'true'`; a stray "yes" or 1 must
    // not open the module client-side when the routes would still 404.
    render(
      withWorkspace(<Probe flag="projects" />, {
        tenant: { features: { projects: "yes" } } as unknown as Tenant,
      })
    );
    expect(screen.getByTestId("state")).toHaveTextContent("false");
  });
});

describe("ModuleDisabled", () => {
  it("explains the module is off and offers a way back", () => {
    render(withWorkspace(<ModuleDisabled {...PROJECTS_DISABLED} />, { tenant: null }));
    expect(screen.getByRole("heading")).toHaveTextContent(
      "Development projects aren't switched on"
    );
    expect(screen.getByRole("link", { name: /back to your workspace/i })).toHaveAttribute(
      "href",
      "/app"
    );
  });

  it("does not present itself as an error", () => {
    // It is a workspace without the module, not a fault the member can fix.
    const { container } = render(
      withWorkspace(<ModuleDisabled {...PROJECTS_DISABLED} />, { tenant: null })
    );
    expect(container.querySelector(".text-danger")).toBeNull();
  });
});
