"""Invite acceptance checks the signed-in email against the invite.

Until now an invite token was a bearer credential: whoever was signed in when
the link was opened became the member, and for an owner invite became the
owner. The founder hit this on 2 Sep 2026 — an owner invite addressed to a
client account was opened in a browser already signed in as the platform
operator, and the operator silently took the owner seat. A forwarded link had
the same property for any role.

The function now refuses when the acceptor's JWT email does not match the
invite's email (case-insensitively), raising `invite_email_mismatch:<invited
email>` so the API can tell the person which address the invite was for. The
membership still records the acceptor's own claim, as 0007 decided.

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-02
"""

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

_ACCEPT_INVITE_CHECKED = """
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
    if p_email is null or lower(p_email) <> lower(v_invite.email) then
        raise 'invite_email_mismatch:%', v_invite.email;
    end if;
    insert into memberships (user_id, tenant_id, role, email)
    values (p_user, v_invite.tenant_id, v_invite.role, p_email)
    on conflict (user_id, tenant_id) do nothing;
    update invites set accepted_at = now() where id = v_invite.id;
    return query select v_invite.tenant_id, v_invite.role;
end
$$
"""

_ACCEPT_INVITE_UNCHECKED = """
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


def _swap(body: str) -> None:
    op.execute("drop function accept_invite(text, uuid, text)")
    op.execute(body)
    op.execute("revoke execute on function accept_invite(text, uuid, text) from public")
    op.execute("grant execute on function accept_invite(text, uuid, text) to ops_app")


def upgrade() -> None:
    _swap(_ACCEPT_INVITE_CHECKED)


def downgrade() -> None:
    _swap(_ACCEPT_INVITE_UNCHECKED)
