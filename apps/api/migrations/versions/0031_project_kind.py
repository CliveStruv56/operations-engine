"""Project kind: one stored column instead of two inferred ones.

A project's kind decides what it is and where it opens — `general` (chat,
documents, optional plan) or `development` (the Groundwork room). Until now
"development" was inferred from a `proj_projects` row at read time; the
registry in `app/projects/kinds.py` needs one column it can filter, sort,
export and count by (docs/project-types-brief.md §4.2).

The CHECK lists every kind the registry knows. Adding a kind widens it in that
kind's own migration, so an unknown value can never be written.

The kind cannot drift from the extension row that defines it: a trigger on
`proj_projects` sets `development` on insert and reverts to `general` if the
extension row alone is removed. It runs as the invoking role, inside the same
tenant transaction, so RLS on `projects` still applies to the update. Every
future module-supplied kind follows the same rule — its kind and its
extension row are written together, by the database.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-26
"""

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table projects add column kind text not null default 'general'
          constraint projects_kind_check check (kind in ('general', 'development'))
        """
    )
    op.execute(
        """
        update projects p set kind = 'development'
        where exists (select 1 from proj_projects pp where pp.id = p.id)
        """
    )
    op.execute("create index projects_tenant_kind on projects (tenant_id, kind)")

    op.execute(
        """
        create function sync_project_kind_from_proj() returns trigger
        language plpgsql as
        $$
        begin
            if tg_op = 'INSERT' then
                update projects set kind = 'development' where id = new.id;
                return new;
            end if;
            update projects set kind = 'general'
            where id = old.id and kind = 'development';
            return old;
        end
        $$
        """
    )
    op.execute(
        """
        create trigger proj_projects_sync_kind
        after insert or delete on proj_projects
        for each row execute function sync_project_kind_from_proj()
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists proj_projects_sync_kind on proj_projects")
    op.execute("drop function if exists sync_project_kind_from_proj()")
    op.execute("drop index if exists projects_tenant_kind")
    op.execute("alter table projects drop column if exists kind")
