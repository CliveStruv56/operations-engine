# Backup & export — how a client's data stays safe and accessible

Two layers, and the client-confidence story needs both to be true: a
self-serve export the workspace can run whenever it wants its own copy, and
platform-side backups the operator maintains. This doc supersedes the spec's
line about "Supabase PITR" (`docs/phase-1-build-spec.md` §124), which was
written against a stack that is not the one deployed — staging runs Railway
Postgres and Cloudflare R2 (`docs/staging-deploy-checklist.md`).

## Layer 1 — self-serve workspace export (shipped 27 Aug 2026)

**Settings → Your data → Export workspace** (admin/owner only). Builds one
ZIP in the worker and hands back a download link; the button polls like every
other export job.

What the archive contains:

| Path | Contents |
| --- | --- |
| `data/*.json` | Every record: documents metadata, conversations + messages, claims + revision history, contacts/companies, projects + tasks, Groundwork and Grantwork tables whole, community profile/assets/figures, question sets, the audit trail, members |
| `csv/*.csv` | The registers as spreadsheets: claims, contacts, companies, community assets & figures, projects, grant applications — the "standard formats" the security page promises |
| `documents/` | Every vault file, named `<title-slug>-<id8>.<ext>` |
| `generated/` | Everything Flowgrid produced: drafted DOCX, health cards, impact cards, exported PDFs, slides, brand assets |
| `README.md` / `manifest.json` | What this is, counts, and an explicit list of anything that could not be fetched — never silent truncation |

Rules worth knowing:

- **Private chats are excluded.** The archive carries tenant-shared
  conversations and the exporter's own; other members' private chats — and
  the answer PDFs generated from them — stay out. The export mirrors the
  app's own read rule rather than the wider RLS boundary.
- Archives land at `{tenant_id}/exports/{job_id}.zip` in R2 and download
  under a readable filename. Old archives accumulate there and are removed
  by workspace purge; revisit if size ever becomes real.
- Plumbing: `workspace_export_jobs` (migration 0027, core/unflagged),
  `POST /tenants/me/export` + poll route (`app/routers/workspace_export.py`),
  worker `build_workspace_export` (`worker/workspace_export.py`, assembly in
  `worker/export_data.py`).

## Layer 2 — platform-side backups (operator checklist)

**Honest current state (27 Aug 2026): none of the following is verified as
enabled.** The export button is real; the disaster-recovery layer is a set of
dashboard actions still to do. Record the date beside each as it is done.

- [ ] **Railway Postgres backups** — enable daily backups on the `postgres`
  service (Railway dashboard → service → Backups). Verify the schedule and
  retention. Done: ______
- [ ] **LiteLLM Postgres backups** — same for the gateway's own database
  (it holds virtual keys and spend). Done: ______
- [ ] **R2 object versioning** — enable on the bucket (Cloudflare dashboard)
  so an accidental delete or overwrite is recoverable. Done: ______
- [ ] **Restore drill** — restore a Railway backup into a scratch database
  once, run `alembic current` against it, and note how long it took. The
  spec (§139) has required this since Phase 1; it has never been done.
  Done: ______
- [ ] **Offsite dump (optional hardening)** — a scheduled `pg_dump` to R2
  from a cron if Railway's retention proves thin.

## What to tell a client

"You can download everything yourself, any time, from Settings — your
documents as files, your records as spreadsheets and JSON. Behind that, the
database is backed up daily and file storage is versioned" — **the second
half of that sentence only after the checklist above is done.**
