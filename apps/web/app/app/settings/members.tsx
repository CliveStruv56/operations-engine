"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Spinner } from "@/components/activity";
import type { Member, MemberRemoved } from "@/lib/members";
import type { Tenant } from "../workspace";

type Invite = {
  id: string;
  email: string;
  role: string;
  token: string;
  expires_at: string;
  email_sent: boolean;
};

const input = "rounded-[10px] border border-line bg-surface px-3 py-2 text-sm";
const btn =
  "rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";

export default function Members({ tenant }: { tenant: Tenant }) {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null);
  const [released, setReleased] = useState<{ email: string | null; count: number } | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [inviteEmailed, setInviteEmailed] = useState(false);
  const [copied, setCopied] = useState(false);

  const isOwner = tenant.role === "owner";

  const load = useCallback(async () => {
    try {
      setMembers(await api<Member[]>("/members", {}, tenant.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [tenant.id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    setError(null);
    setInviteLink(null);
    setCopied(false);
    try {
      const created = await api<Invite>(
        "/invites",
        { method: "POST", body: JSON.stringify({ email: inviteEmail, role: inviteRole }) },
        tenant.id
      );
      setInviteEmail("");
      setInviteLink(`${window.location.origin}/invite/${created.token}`);
      setInviteEmailed(created.email_sent);
    } catch (err) {
      if (err instanceof ApiError && err.code === "seat_limit") {
        setError(`${err.message}. Remove a member or expired invite to free a seat.`);
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setInviting(false);
    }
  }

  async function changeRole(member: Member, role: string) {
    setBusyId(member.id);
    setError(null);
    try {
      await api(`/members/${member.id}`, { method: "PATCH", body: JSON.stringify({ role }) }, tenant.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function remove(member: Member) {
    setBusyId(member.id);
    setError(null);
    setReleased(null);
    try {
      const result = await api<MemberRemoved>(
        `/members/${member.id}`,
        { method: "DELETE" },
        tenant.id
      );
      // Their facts are still true; they are simply nobody's now. This is the
      // one moment an admin can hand them to somebody else, and until the
      // count came back in the response it only reached the audit log.
      if (result.claims_disowned > 0) {
        setReleased({ email: member.email, count: result.claims_disowned });
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
      setConfirmRemoveId(null);
    }
  }

  return (
    <section className="rounded-card border border-edge bg-card p-5 shadow-card">
      <h2 className="data mb-3 text-ink-muted uppercase">People</h2>

      {members === null ? (
        <p className="data flex items-center gap-2 text-ink-muted">
          <Spinner className="text-accent" /> Loading members…
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="data border-b border-line text-left text-ink-muted uppercase">
                <th className="py-2 pr-4">Email</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2 pr-4">Joined</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {members.map((m) => (
                <tr key={m.id}>
                  <td className="py-2.5 pr-4">{m.email ?? "—"}</td>
                  <td className="py-2.5 pr-4">
                    <select
                      value={m.role}
                      disabled={busyId === m.id || (m.role === "owner" && !isOwner)}
                      onChange={(e) => changeRole(m, e.target.value)}
                      className={`${input} py-1`}
                      aria-label={`Role for ${m.email ?? m.user_id}`}
                    >
                      {isOwner && <option value="owner">owner</option>}
                      {!isOwner && m.role === "owner" && <option value="owner">owner</option>}
                      <option value="admin">admin</option>
                      <option value="member">member</option>
                    </select>
                  </td>
                  <td className="data py-2.5 pr-4 text-ink-muted">
                    {new Date(m.created_at).toLocaleDateString("en-GB")}
                  </td>
                  <td className="py-2.5 text-right">
                    {confirmRemoveId === m.id ? (
                      <span className="flex items-center justify-end gap-2 text-xs">
                        <span className="text-danger">Remove?</span>
                        <button
                          onClick={() => remove(m)}
                          disabled={busyId === m.id}
                          className="font-medium text-danger underline disabled:opacity-50"
                        >
                          Yes
                        </button>
                        <button
                          onClick={() => setConfirmRemoveId(null)}
                          className="text-ink-muted underline"
                        >
                          No
                        </button>
                      </span>
                    ) : (
                      <button
                        onClick={() => setConfirmRemoveId(m.id)}
                        disabled={busyId !== null}
                        className="text-xs text-ink-muted underline hover:text-danger"
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {released && (
        <div className="mt-3 rounded-[10px] bg-accent-soft px-3 py-2 text-sm">
          <p>
            {released.count} {released.count === 1 ? "fact" : "facts"} about your organisation
            {released.email ? ` that ${released.email} looked after ` : " "}
            {released.count === 1 ? "has" : "have"} nobody looking after{" "}
            {released.count === 1 ? "it" : "them"} now. {released.count === 1 ? "It is" : "They are"}{" "}
            still in your register and still used in drafts.
          </p>
          <Link href="/app/claims?owner=none" className="mt-1 inline-block font-medium underline">
            Hand {released.count === 1 ? "it" : "them"} to somebody →
          </Link>
        </div>
      )}

      <form onSubmit={invite} className="mt-4 flex flex-wrap items-end gap-2 border-t border-line pt-4">
        <label className="min-w-0 flex-1 text-sm">
          Invite by email
          <input
            required
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="colleague@company.co.uk"
            className={`mt-1 w-full ${input}`}
          />
        </label>
        <label className="text-sm">
          Role
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className={`mt-1 block ${input}`}
          >
            <option value="member">member</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <button type="submit" disabled={inviting} className={btn}>
          {inviting ? <Spinner /> : "Invite"}
        </button>
      </form>

      {inviteLink && (
        <div className="mt-3 flex items-center gap-2 rounded-[10px] bg-accent-soft px-3 py-2">
          <p className="data min-w-0 flex-1 truncate text-accent">{inviteLink}</p>
          <button
            onClick={() => {
              navigator.clipboard.writeText(inviteLink);
              setCopied(true);
            }}
            className="shrink-0 text-xs font-medium text-accent underline"
          >
            {copied ? "Copied" : "Copy link"}
          </button>
        </div>
      )}
      <p className="mt-2 text-xs text-ink-faint">
        {inviteLink && inviteEmailed
          ? "We've emailed the invite — the link here is a spare in case it doesn't arrive."
          : "Send the link yourself — the invite hasn't been emailed."}{" "}
        Links expire after 7 days.
      </p>

      {error && <p className="mt-3 text-sm text-danger">{error}</p>}
    </section>
  );
}
