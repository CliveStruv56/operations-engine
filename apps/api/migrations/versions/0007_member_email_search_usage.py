"""Member emails + 'search' usage kind.

memberships.email caches the JWT email claim so the members list can show
who a membership belongs to — the app database has no access to Supabase's
auth.users. Written at bootstrap/accept time and self-healed on tenant
resolution. accept_invite() gains a p_email parameter for the same reason;
the 2-arg version is dropped.

usage_events.kind gains 'search' for web-search (Exa) metering.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-01
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_KINDS_NEW = "('chat', 'embed', 'parse', 'summary', 'draft', 'search')"
_KINDS_OLD = "('chat', 'embed', 'parse', 'summary', 'draft')"

_ACCEPT_INVITE_3ARG = """
create function accept_invite(p_token text, p_user uuid, p_email text)
returns table (out_tenant_id uuid, out_role text)
language plpgsql security definer set search_path = public as
$$
declare
    v_invite invites%rowtype;
begin
    select * into v_invite
    from invites
    where token = p_token and accepted_at is null and expires_at > now();
    if not found then
        raise 'invalid_invite';
    end if;
    insert into memberships (user_id, tenant_id, role, email)
    values (p_user, v_invite.tenant_id, v_invite.role, coalesce(p_email, v_invite.email))
    on conflict (user_id, tenant_id) do nothing;
    update invites set accepted_at = now() where id = v_invite.id;
    return query select v_invite.tenant_id, v_invite.role;
end
$$
"""

_ACCEPT_INVITE_2ARG = """
create function accept_invite(p_token text, p_user uuid)
returns table (out_tenant_id uuid, out_role text)
language plpgsql security definer set search_path = public as
$$
declare
    v_invite invites%rowtype;
begin
    select * into v_invite
    from invites
    where token = p_token and accepted_at is null and expires_at > now();
    if not found then
        raise 'invalid_invite';
    end if;
    insert into memberships (user_id, tenant_id, role)
    values (p_user, v_invite.tenant_id, v_invite.role)
    on conflict (user_id, tenant_id) do nothing;
    update invites set accepted_at = now() where id = v_invite.id;
    return query select v_invite.tenant_id, v_invite.role;
end
$$
"""


def upgrade() -> None:
    op.execute("alter table memberships add column email text")

    op.execute("drop function accept_invite(text, uuid)")
    op.execute(_ACCEPT_INVITE_3ARG)
    op.execute("revoke execute on function accept_invite(text, uuid, text) from public")
    op.execute("grant execute on function accept_invite(text, uuid, text) to ops_app")

    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    op.execute(
        f"alter table usage_events add constraint usage_events_kind_check"
        f" check (kind in {_KINDS_NEW})"
    )


def downgrade() -> None:
    op.execute("alter table usage_events drop constraint usage_events_kind_check")
    # Narrowing validates existing rows — search metering does not survive.
    op.execute("delete from usage_events where kind = 'search'")
    op.execute(
        f"alter table usage_events add constraint usage_events_kind_check"
        f" check (kind in {_KINDS_OLD})"
    )

    op.execute("drop function accept_invite(text, uuid, text)")
    op.execute(_ACCEPT_INVITE_2ARG)
    op.execute("revoke execute on function accept_invite(text, uuid) from public")
    op.execute("grant execute on function accept_invite(text, uuid) to ops_app")

    op.execute("alter table memberships drop column email")
