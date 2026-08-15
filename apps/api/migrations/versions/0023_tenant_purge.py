"""Tenant purge: the owner-run delete behind workspace offboarding.

0001 deliberately shipped no delete policy on `tenants` — the runtime role
cannot delete a workspace, and suspension has been the only offboarding
state since 0012. Purge is the second, irreversible step, and it keeps that
posture: rather than granting the runtime role a delete policy (which every
tenant-context handler would then carry), the delete lives in one owner-run
SECURITY DEFINER function, revoked from public — the `accept_invite` /
`claims_sweep_tenants` pattern.

The function refuses an unsuspended tenant even though the route checks too:
suspend-then-purge is the two-step that makes an irreversible act deliberate,
and the database is the layer that cannot be talked out of it. Every
tenant-scoped table references tenants(id) on delete cascade, so one row
delete takes the workspace's data with it. What Postgres cannot reach — the
R2 prefix and the LiteLLM key — is the API route's half.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-15
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create function purge_tenant(p_tenant uuid)
        returns boolean
        language plpgsql security definer set search_path = public as
        $$
        begin
            delete from tenants where id = p_tenant and suspended_at is not null;
            return found;
        end
        $$
        """
    )
    op.execute("revoke execute on function purge_tenant(uuid) from public")
    op.execute("grant execute on function purge_tenant(uuid) to ops_app")


def downgrade() -> None:
    op.execute("drop function if exists purge_tenant(uuid)")
