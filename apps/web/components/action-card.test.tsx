import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ActionCard, type ActionCardProps } from "./action-card";

function setup(over: Partial<ActionCardProps> = {}) {
  const onConfirm = vi.fn();
  const onEdit = vi.fn();
  const onReject = vi.fn();
  render(
    <ActionCard
      title="Use these company details?"
      proposer={{ kind: "register", name: "Companies House" }}
      changes={[
        { label: "Registered address", before: "1 Old Road", after: "2 New Street" },
        { label: "Company number", after: "01234567" },
      ]}
      onConfirm={onConfirm}
      onEdit={onEdit}
      onReject={onReject}
      {...over}
    />,
  );
  return { onConfirm, onEdit, onReject };
}

describe("ActionCard", () => {
  it("renders title, proposer and the before/after in words", () => {
    setup();
    expect(screen.getByRole("heading", { name: "Use these company details?" })).toBeInTheDocument();
    expect(screen.getByText(/Found in a public register: Companies House/)).toBeInTheDocument();
    expect(screen.getByText("Currently:")).toBeInTheDocument();
    expect(screen.getByText("Proposed:")).toBeInTheDocument();
    expect(screen.getByText("New:")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Use these company details?" })).toBeInTheDocument();
  });

  it.each([
    ["assistant", /Proposed by the assistant/],
    ["automation", /Proposed by an automation/],
  ] as const)("names a %s proposer", (kind, re) => {
    setup({ proposer: { kind } });
    expect(screen.getByText(re)).toBeInTheDocument();
  });

  it("fires each action once on click", async () => {
    const u = userEvent.setup();
    const { onConfirm, onEdit, onReject } = setup();
    await u.click(screen.getByRole("button", { name: "Confirm" }));
    await u.click(screen.getByRole("button", { name: "Edit" }));
    await u.click(screen.getByRole("button", { name: "Reject" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it("shows only the actions that have a handler", () => {
    setup({ onEdit: undefined, onReject: undefined });
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
  });

  it("uses custom labels", () => {
    setup({ confirmLabel: "Import facts", rejectLabel: "Not us" });
    expect(screen.getByRole("button", { name: "Import facts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not us" })).toBeInTheDocument();
  });

  it("is reachable and operable by keyboard, and never confirms by itself", async () => {
    const u = userEvent.setup();
    const { onConfirm, onEdit } = setup();
    expect(onConfirm).not.toHaveBeenCalled();
    await u.tab();
    expect(screen.getByRole("button", { name: "Confirm" })).toHaveFocus();
    await u.keyboard("{Enter}");
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await u.tab();
    expect(screen.getByRole("button", { name: "Edit" })).toHaveFocus();
    await u.keyboard(" ");
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it("busy: marks the card and the running action busy and blocks every click", async () => {
    const u = userEvent.setup();
    const { onConfirm, onReject } = setup({ status: "busy", busyAction: "confirm" });
    expect(screen.getByRole("region")).toHaveAttribute("aria-busy", "true");
    const confirm = screen.getByRole("button", { name: /Working/ });
    expect(confirm).toHaveAttribute("aria-busy", "true");
    expect(confirm).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
    await u.click(confirm);
    await u.click(screen.getByRole("button", { name: "Reject" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onReject).not.toHaveBeenCalled();
  });

  it("error: announces the message and keeps the actions for a retry", async () => {
    const u = userEvent.setup();
    const { onConfirm } = setup({ status: "error", errorMessage: "Couldn't save. Try again." });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't save. Try again.");
    await u.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("done: says so in words, announces the result, and removes the actions", () => {
    setup({ status: "done", doneMessage: "Imported 6 confirmed facts." });
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Imported 6 confirmed facts.");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("disabled: every action is inert", async () => {
    const u = userEvent.setup();
    const { onConfirm } = setup({ status: "disabled" });
    for (const name of ["Confirm", "Edit", "Reject"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
    await u.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("role-gated: explains why in words, disables all actions and links the reason", async () => {
    const u = userEvent.setup();
    const { onConfirm, onEdit, onReject } = setup({ canRelease: false });
    const reason = screen.getByText(/You can't release this/);
    for (const name of ["Confirm", "Edit", "Reject"]) {
      const b = screen.getByRole("button", { name });
      expect(b).toBeDisabled();
      expect(b).toHaveAttribute("aria-describedby", reason.id);
    }
    await u.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onEdit).not.toHaveBeenCalled();
    expect(onReject).not.toHaveBeenCalled();
  });

  it("role-gated: shows a custom reason", () => {
    setup({ canRelease: false, cannotReleaseReason: "Only owners can release budget changes." });
    expect(screen.getByText("Only owners can release budget changes.")).toBeInTheDocument();
  });

  it("renders children and a chosen heading level", () => {
    setup({ headingLevel: 2, children: <input aria-label="Notes" /> });
    expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    expect(screen.getByLabelText("Notes")).toBeInTheDocument();
  });
});
