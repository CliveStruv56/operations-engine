import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Onboarding } from "./layout";
import { withWorkspace } from "@/test/workspace";

describe("invite-led workspace entry", () => {
  it("does not offer workspace creation when a signed-in user has no membership", () => {
    render(withWorkspace(<Onboarding />, { memberships: [] }));

    expect(screen.getByRole("heading", { name: "No workspace yet" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create workspace/i })).toBeNull();
    expect(screen.getByRole("link", { name: "Contact Flowgrid" })).toHaveAttribute(
      "href",
      "/contact",
    );
  });

  it("preserves the chooser for users who belong to more than one workspace", () => {
    render(
      withWorkspace(<Onboarding />, {
        memberships: [
          { tenant_id: "one", name: "One Trust", role: "owner" },
          { tenant_id: "two", name: "Two Trust", role: "member" },
        ],
      }),
    );

    expect(screen.getByRole("heading", { name: "Choose a workspace" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /One Trust/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Two Trust/i })).toBeInTheDocument();
  });
});
