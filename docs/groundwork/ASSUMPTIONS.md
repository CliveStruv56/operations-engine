# Groundwork Module — Assumptions & divergences log

Per PRD §0.2: where the repo's conventions differ from the spec, the repo wins,
and every divergence is recorded here.

## Recorded at orientation (30 Jul 2026, approved by founder)

1. **Unified project concept.** The core gained a `projects` table (Slice 4.5:
   vault partitioning + chat scoping) after the PRD was written. `proj_projects`
   is therefore a **1:1 extension** of `projects`
   (`id uuid primary key references projects(id) on delete cascade`) rather than
   a standalone table. `name`, `created_by`, `created_at` live on the core row;
   the extension holds the development-specific fields. Groundwork projects
   automatically appear in the core sidebar, partition the vault, and scope chat
   retrieval — the feasibility workflow depends on that scoping.
2. **Route collisions with core.** `/api/v1/projects` (POST + GET) already
   exists in the core (container CRUD). Module routes therefore are:
   - `POST /projects/{id}/setup` — attach the Groundwork extension to an
     existing core project and seed the spine (the UI's "New development
     project" form calls core create + setup in sequence).
   - `GET /projects/portfolio` — the module portfolio list.
   - `GET`/`PATCH /projects/{id}/groundwork` — module detail/update (the core
     owns `PATCH /projects/{id}` for container rename/archive, and wins by
     registration order; discovered in W2).
   - All other PRD routes are `/projects/{id}/…` subresources as specified (no
     collisions).
3. **`usage_events.kind`** is CHECK-constrained in the core schema; migration
   0003 extends it with `draft`.
4. **Vault excerpt format.** Core prompts wrap chunks as
   `[c:<id>] (from "title", p.x)` inside `<vault-excerpts>`, not
   `<vault_chunk id=…>`. Drafting pipelines reuse the core format and its
   citation-resolution rules (unresolvable ids stripped and logged).
5. **RLS pattern.** Core policies use the `app_current_tenant()` helper with
   `for all … using … with check`, not the PRD's literal snippet. Module tables
   follow the core pattern. Reference tables get a select-only policy
   (`using (true)`) — with no write policies, the non-owner runtime role cannot
   write them; only the owner (migrations/seed) can.
6. **Frontend client.** No OpenAPI→TS generation exists (`packages/shared` is a
   stub); the web app uses a hand-rolled `apps/web/lib/api.ts`. Module UI
   follows that.
7. **Core prerequisite caveats.** Stripe billing is not built (re-sequenced
   after this module; pilot invoiced manually per PRD §6 — no impact).
   Production R2 is not yet provisioned (dev uses MinIO) — required before the
   W4 staging/pilot step.
8. **Worker upload helper.** The worker currently only downloads from storage;
   W3 adds a small upload helper for registering generated DOCX files.
