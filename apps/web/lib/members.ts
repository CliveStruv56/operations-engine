// The workspace's people. Shared between the settings screen that manages them
// and the register that hands facts to them — the type lived inline in settings
// until the claims register needed the same list to offer an owner picker.
import { api } from "@/lib/api";
import { tenantId } from "@/lib/groundwork";

export type Member = {
  id: string;
  user_id: string;
  role: "owner" | "admin" | "member";
  email: string | null;
  created_at: string;
  // Read-only: the digest preference belongs to the recipient and is changed
  // only through the signed link in the digest email itself.
  digest_opt_out: boolean;
};

/**
 * What removing somebody left behind.
 *
 * Removal used to answer 204 — honest about the membership, silent about
 * everything that person was responsible for. The claims they owned are
 * released rather than deleted, and the admin doing the removal is the only
 * person who can hand those facts to somebody else.
 */
export type MemberRemoved = { claims_disowned: number };

export const listMembers = () => api<Member[]>("/members", {}, tenantId() ?? undefined);

/** How to refer to whoever owns a fact, including when we cannot find them. */
export function memberName(members: Member[], membershipId: string | null): string | null {
  if (membershipId === null) return null;
  const found = members.find((m) => m.id === membershipId);
  // A membership that no longer exists means somebody has just been removed in
  // another tab — the fact is about to be released, so say so rather than
  // showing a raw id.
  return found?.email ?? "somebody who has left";
}
