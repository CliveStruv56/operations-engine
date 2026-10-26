# One Projects list, with project kinds and add-on modules

**Status: proposed, 26 Oct 2026. Revised the same day after the operator's
review. Not approved and not built.** The decisions needed before work starts
are listed in §10.

This follows on from the UI review merged in #11. That review found two project
sections side by side in the sidebar. The operator asked for one list, with a
type on each project, that can take new types in future.

## 1. The model

The operator's statement of the model:

> **Every project has a core set of capabilities. Development projects and
> grant funding add modules on top of that.**

This brief turns that statement into three terms.

| Term | Meaning | Today |
|---|---|---|
| **Core capability** | What every project gets: scoped chat, documents, and an optional plan (a project brief plus a checklist). | `projects`, `has_plan`, `project_tasks`. All of it is unflagged core (ASSUMPTIONS #51). |
| **Kind** | What a project fundamentally *is*. A project has exactly one kind, and it is stored on the project. A kind may be supplied by a module and may change what the project's home page is. | Implicit. Groundwork is detected by the presence of a `proj_projects` row. |
| **Add-on** | A module that adds a tab or panel to projects, whatever their kind. Several add-ons can apply to one project at once. | Contacts already behaves like one: `crm_contact_projects` links contacts to any core project. In the UI it only appears as a tab in the development room. |

The kinds at launch:

| Kind | Supplied by | Home when clicked | Adds |
|---|---|---|---|
| `standard` | Core (always available) | The project's scoped chat, as today | Nothing beyond the core capability |
| `development` | The `projects` module (Groundwork) | The project room, `/app/projects/{id}` | Stages and gates, tasks, funding, budget, risks, conditions, stakeholders, and drafts |

**"With a plan" stops being a type.** A plan is part of the core capability, so
any standard project can add one, as it can today through
`POST /projects/{id}/plan`. A development project has its own stage-based task
list instead, and the two stay mutually exclusive (#51). The open question about
grant funding is in §3.

## 2. The problem being solved

- **Two lists.** The sidebar lists "Development projects" and "Projects"
  separately. An office admin sees the same thing listed twice.
- **One name, two destinations.** Clicking a development project's name opens a
  chat. Its ↗ opens the project room.
- **Disappearing projects (a bug).** When a workspace's `projects` module is
  switched off, its development projects vanish from the sidebar completely:
  - `devProjects` is empty when the flag is off;
  - `coreProjects` excludes `is_development`.

  Their chats and documents still exist, but nothing leads to them.
- **Hard to extend.** The three ways of creating a project, and the rules about
  which kind can become which, are spread across the sidebar, `hero.tsx`,
  `chat.tsx`, `vault.tsx`, `routers/projects.py`, `project_plan.py` and
  `groundwork.py`. A new kind today would mean editing all of them.

## 3. The grant-funding decision

Today a grant application is a record of its own (`grant_applications`). It can
optionally link to a project through `grant_applications.project_id`. If that
project is deleted, the link is cleared and the application stays. ASSUMPTIONS #23 deliberately kept
applications out of the projects list, because there are too many of them for
the sidebar. Grant funding can join the project model in one of two ways.

**Option A: an add-on (recommended).** Grant funding becomes something any
project can use, whatever its kind.

- Every project gets a "Grant applications" tab listing the applications linked
  to it, with a "New application for this project" button.
- Applications without a project still work, as now.
- This fits the most common real case. A development scheme is exactly what
  people apply for grants for, and under Option B it could not also be a
  grant-funding project.
- The project picker can still offer a "Funding bid" starting point: a
  standard project with the grant tab shown up front.
- No change to #23 is needed.

**Option B: a kind.** A `grant` kind, supplied by the `grants` module.

- The project's home becomes its funding room: its applications, funders and
  reporting returns.
- This suits an organisation whose project *is* the fundraising, such as a
  programme raising money.
- Kinds are exclusive, so a development scheme could never be a grant project
  as well.
- #23 would need revisiting, so that applications belong to a grant project
  rather than standing alone.

The registry in §4 supports both options. The choice only changes which list
`grants` is registered in.

## 4. Design: a project-kind registry and a stored kind

### 4.1 The registry: one place in code

`app/projects/kinds.py` sits next to the module manifest in `app/modules.py`
and is written in the same style.

```python
@dataclass(frozen=True)
class ProjectKind:
    key: str                 # stored in projects.kind
    label: str               # "Development project"
    description: str         # one line, shown in the picker and the operator console
    module: str | None       # feature flag that provides it; None = core
    home: Literal["chat", "room"]
    create: Literal["inline", "setup"]   # inline form, or a setup page
    upgrades_to: tuple[str, ...]         # kinds this one may become

@dataclass(frozen=True)
class ProjectAddOn:
    key: str                 # "contacts", "grants"
    label: str               # tab label
    module: str              # feature flag
```

- **Kinds at launch:** `standard` (`upgrades_to=("development",)`) and
  `development` (`upgrades_to=()`).
- **Add-ons at launch:** `contacts`. Under Option A, `grants` is added too.
- **Adding a kind later** takes:
  - one registry entry;
  - its module (extension tables, setup endpoint, room);
  - a one-line migration to widen the CHECK constraint (§4.2);
  - an icon on the web side.

  The sidebar, the picker, the operator console and exports all follow the
  registry.
- **Startup check:** every kind's `module` must exist in `MODULES`, checked in
  the same way that `make_feature_gate` rejects unknown flags. A typo then fails
  at startup rather than in production.

### 4.2 The stored kind

Migration `00xx_project_kind`:

```sql
alter table projects add column kind text not null default 'standard'
  check (kind in ('standard', 'development'));
update projects p set kind = 'development'
  where exists (select 1 from proj_projects pp where pp.id = p.id);
create index projects_tenant_kind on projects (tenant_id, kind);
```

- **A CHECK constraint, not free text.** An unknown kind can then never reach
  the database. Adding a kind is one `alter … check` line in that kind's own
  migration.
- **No drift.** `POST /projects/{id}/setup` sets `kind = 'development'` in the
  same transaction that inserts the `proj_projects` row. Every future
  module-supplied kind follows this rule: the kind and its extension row are
  written together or not at all. A test asserts that every `development`
  project has a `proj_projects` row, and that no other project does.
- **Security.** `projects` already has RLS and is in the isolation suite's
  `TENANT_TABLES`. Adding a column adds no new table, but the isolation suite
  gains one assertion: filtering `GET /projects?kind=` never returns another
  tenant's rows. That meets hard constraint 2.
- **`is_development` stays during the change,** now computed as
  `kind = 'development'`. It is removed once the web no longer reads it.

### 4.3 What the API returns

- `ProjectOut` gains these fields:
  - `kind`;
  - `kind_available`, false when the kind's module is switched off;
  - `stage_current`, filled for development projects.
- `GET /projects?kind=` filters by kind.
- `GET /project-kinds` lists the kinds and add-ons for the current workspace.
  Each entry carries `key`, `label`, `description`, `home`, `create` and
  `available`.

  The web picker and sidebar are built from this list. The web keeps only a
  small map from kind key to icon. A kind with no icon falls back to the
  standard look, so a new kind degrades gracefully.
- `POST /projects` accepts `kind`, but only kinds whose `create` is `inline`. A
  module kind still goes through its own setup endpoint, which checks the flag.
- Today's `POST /projects` field `kind: "blank" | "planned"` is renamed to
  `with_plan: bool`. That frees the name `kind` for the project kind, and a
  standard project can still start with a plan.

## 5. What users see

**The sidebar has one "Projects" section.**

- "All projects" comes first.
- After it come projects, most recently updated first. Archived projects stay
  hidden.
- Each row shows:
  - the kind's icon;
  - the name;
  - a short status: open plan tasks or documents for standard projects, the
    current stage for development projects.
- The kind's label is in the row's accessible name and its tooltip, so the
  icon is never the only signal.
- Clicking a row goes to the kind's home: chat for `standard`, the project room
  for `development`. The ↗ glyph is removed.
- The room gets a "Chat about this project" button, so the chat is still one
  click away.

**Creating a project.** One "+ New project" button.

1. **Step 1:** choose a kind. The cards come from `GET /project-kinds` and show
   only the kinds that are available.
2. **Step 2:**
   - a standard project uses the inline form, with "Add a plan" as an option;
   - a module kind goes to its setup page, with the name carried across.

**Changing kind.** Phase 2 adds a "Change kind" menu item. It offers only the
kind's `upgrades_to` list, which today is standard → development.

**When a module is switched off.**

- Its projects stay in the list as standard rows that open the chat. Their
  documents and chats are untouched.
- Their kind-specific room and tabs are hidden, and the API returns 404, as
  now.
- Their stored `kind` is unchanged, so switching the module back on restores
  everything.

## 6. Admin and module switching

**Operator console** (`/admin`, `routers/admin.py`)

- **Module checkboxes show what each module adds.** For example: "Development
  projects: adds the *Development project* kind", or "Contacts: adds a
  *Contacts* tab to every project".
- **The checkboxes come from the API.** Today `apps/web/lib/admin.ts` keeps a
  hand-copied list of flags. A new `GET /admin/modules` returns the manifest
  together with the kinds and add-ons each module supplies, so the console stops
  needing an edit for every new module.
- **The switch-off warning is rewritten.** It currently says "hides it from the
  workspace". The new wording: "*N* development projects stay in the Projects
  list as ordinary projects. Their stages, budget and risks are hidden until you
  switch this back on. Nothing is deleted."
  - The count comes from `GET /admin/tenants/{id}` gaining project counts by
    kind.
  - The same counts appear on the workspace list.
- **The flag key `projects` stays.** It now reads as "development projects"
  while "Projects" is core. Renaming the key would mean rewriting every tenant's
  `features` JSON, which is not worth it. Every surface shows its label, and the
  reason is recorded in ASSUMPTIONS.

**Workspace settings** (`/app/settings`)

- A read-only "Your modules" list shows which modules the workspace has and
  what each one adds. When a kind is missing from the picker, the admin can see
  why. Modules are still switched on and off only by the operator (#22).

**Plan tiers**

- `tenants.plan` (trial / core / pro / managed) still gates nothing. Kinds hang
  off module flags, so if tiers later bundle modules, tiers will control kinds
  with no extra work.

**Exports**

- The workspace export's `projects.csv` gains `kind`.
- Module data is still exported whether or not the module is on. The data
  belongs to the tenant (#63).

## 7. Two different meanings of "type"

`proj_projects.project_type` already exists. It is always `clh_new_build`, and
it is read by the API, the web and the drafting worker. It is the **template** a
development project was set up from.

The roadmap (§2.4) plans more templates for built-environment firms, such as
architecture, planning and ecology, as new `proj_ref_templates` rows *within*
the development kind, not as new kinds. So the levels are:

- **kind:** `standard` or `development`. This decides what the project can do.
- **template:** within `development`, for example *CLH new build*, and later
  *Architecture scheme*. This decides which stages, tasks and checklists are
  seeded.

The new column is called `kind` so that the two do not collide. In the UI the
template is shown as "Scheme type".

## 8. Changes by layer

| Layer | Change |
|---|---|
| Migration | `00xx_project_kind`: the column, the CHECK constraint, the backfill and the index (§4.2). |
| API | `app/projects/kinds.py` registry; `kind`, `kind_available` and `stage_current` on `ProjectOut`; `?kind=` filter; `GET /project-kinds`; `setup` sets `kind`; `GET /admin/modules`; project counts by kind in the admin views. |
| API tests | Backfill and no-drift invariant; isolation assertion for `?kind=`; flag-off `kind_available`; the registry's startup check. |
| Web | `Project.kind`; a single sidebar section built from the kinds list; the kind step in the new-project flow; development rows open the room; "Chat about this project" in the room; the operator console's module descriptions and switch-off copy; a "Your modules" list in settings. |
| Web tests | Sidebar: one section, a kind label per row, the click target per kind, flag-off rows still shown. Picker: only available kinds appear. |
| Export | `kind` column in `projects.csv`. |
| Docs | ASSUMPTIONS #70: kinds, add-ons, the stored `kind`, and the `projects` flag key. It supersedes the presentation half of #15. Under Option B it also amends #23. Roadmap: a "module kit" line saying that a module may register kinds or add-ons. |

## 9. Phases

1. **Phase 1, one PR, about 1.5 days:**
   - the migration;
   - the registry and `GET /project-kinds`;
   - the single sidebar list;
   - the kind step in new-project;
   - development rows open the room;
   - the flag-off fix;
   - the operator console's module descriptions and switch-off copy;
   - the export column;
   - tests and #70.
2. **Phase 2:**
   - grant funding, as an add-on tab (Option A) or as a kind (Option B);
   - the Contacts tab on standard projects too;
   - the "Change kind" menu;
   - a full "All projects" page filtered by kind;
   - a cap on sidebar length;
   - the "Your modules" list in settings.

## 10. Decisions needed

1. **Grant funding: an add-on (Option A, recommended) or a kind (Option B)?** See §3.
2. **Should a development project open its project room or its chat?** The room
   is recommended.
3. **Kind names:** *Project* (standard) and *Development project*. The standard
   kind's label could instead be "Standard project" or "General project".
4. **Sidebar order:** most recently updated first (proposed), alphabetical, or
   grouped by kind?
5. **Should the Contacts tab appear on standard projects** too, making it a true
   add-on, or stay in development rooms only?
