# One Projects list, with project kinds and add-on modules

**Status: decisions settled 26 Oct 2026 (§10). Approved for build; not built
yet.** Revised the same day after the operator's review of the first draft.

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
| `general` (label: *General project*) | Core (always available) | The project's scoped chat, as today | Nothing beyond the core capability |
| `development` | The `projects` module (Groundwork) | The project room, `/app/projects/{id}` | Stages and gates, tasks, funding, budget, risks, conditions, stakeholders, and drafts |

**"With a plan" stops being a type.** A plan is part of the core capability, so
any general project can add one, as it can today through
`POST /projects/{id}/plan`. A development project has its own stage-based task
list instead, and the two stay mutually exclusive (#51).

The add-ons at launch are **Contacts** and **Grant applications**. Both appear on
every project, whatever its kind, when their module is on (§3, §5.1).

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

## 3. Grant funding is an add-on (decided)

Today a grant application is a record of its own (`grant_applications`). It can
optionally link to a project through `grant_applications.project_id`. If that
project is deleted, the link is cleared and the application stays. ASSUMPTIONS
#23 deliberately kept applications out of the projects list, because there are
too many of them for the sidebar. That stays true.

**Decision: grant funding is an add-on, not a kind.** When the `grants` module is
on, every project gets a **Grant applications** tab.

- The tab lists the applications linked to the project.
- It has a "New application for this project" button, which pre-fills
  `project_id`.
- Applications without a project still work, and still appear in Grant
  funding, as now.
- A development scheme can have grant applications too. This is the most common
  real case, and it is the main reason an add-on was chosen over a kind.
- #23 is unchanged.

**Considered and rejected: a `grant` kind.** Its home would have been a funding
room. It was rejected because kinds are exclusive, so a development scheme
could never also be a grant project, and because it would have meant reopening
#23.

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

- **Kinds at launch:** `general` (`upgrades_to=("development",)`) and
  `development` (`upgrades_to=()`).
- **Add-ons at launch:** `contacts` (tab "Contacts", module `contacts`) and
  `grants` (tab "Grant applications", module `grants`). Both apply to every
  kind.
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
alter table projects add column kind text not null default 'general'
  check (kind in ('general', 'development'));
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
  general look, so a new kind degrades gracefully.
- `POST /projects` accepts `kind`, but only kinds whose `create` is `inline`. A
  module kind still goes through its own setup endpoint, which checks the flag.
- Today's `POST /projects` field `kind: "blank" | "planned"` is renamed to
  `with_plan: bool`. That frees the name `kind` for the project kind, and a
  general project can still start with a plan.

## 5. What users see

**The sidebar has one "Projects" section.**

- "All projects" comes first.
- After it come projects, most recently updated first. Archived projects stay
  hidden.
- Each row shows:
  - the kind's icon;
  - the name;
  - a short status: open plan tasks or documents for general projects, the
    current stage for development projects.
- The kind's label is in the row's accessible name and its tooltip, so the
  icon is never the only signal.
- Clicking a row goes to the kind's home: chat for `general`, the project room
  for `development`. The ↗ glyph is removed.
- The room gets a "Chat about this project" button, so the chat is still one
  click away.

### 5.1 One project page for every kind

Add-on tabs need somewhere to live, and a general project's home is its chat.
So `/app/projects/{id}`, today the development room, becomes **the project page
for every kind**:

- **The page itself is core.** Only the development tabs are gated by the
  `projects` module; today the whole page is.
- **Tabs, in order:**
  1. *Overview*: the brief and plan for general projects, the current room
     overview for development projects.
  2. *Documents*.
  3. The kind's own tabs: stages and gates, tasks, funding, budget, risks,
     conditions and stakeholders for development projects.
  4. The add-on tabs, *Contacts* and *Grant applications*, each shown only when
     its module is on.
- **Reaching it.**
  - Development projects open straight onto it.
  - General projects open their chat, as decided. The chat's project banner
    gains a "Project page" link.
- **The development module switched off.** A development project's page shows
  only the core and add-on tabs.

**Creating a project.** One "+ New project" button.

1. **Step 1:** choose a kind. The cards come from `GET /project-kinds` and show
   only the kinds that are available.
2. **Step 2:**
   - a general project uses the inline form, with "Add a plan" as an option;
   - a module kind goes to its setup page, with the name carried across.

**Changing kind.** Phase 2 adds a "Change kind" menu item. It offers only the
kind's `upgrades_to` list, which today is general → development.

**When a module is switched off.**

- Its projects stay in the list as general rows that open the chat. Their
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

- **kind:** `general` or `development`. This decides what the project can do.
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
| Web | `Project.kind`; a single sidebar section built from the kinds list; the kind step in the new-project flow; development rows open the room; "Chat about this project" in the room; the operator console's module descriptions and switch-off copy; a "Your modules" list in settings. Phase 2: `/app/projects/{id}` becomes the core project page with add-on tabs (§5.1), plus a "Project page" link in the chat banner. |
| Web tests | Sidebar: one section, a kind label per row, the click target per kind, flag-off rows still shown. Picker: only available kinds appear. |
| Export | `kind` column in `projects.csv`. |
| Docs | ASSUMPTIONS #70: kinds, add-ons, the stored `kind`, and the `projects` flag key. It supersedes the presentation half of #15. #23 is unchanged. Roadmap: a "module kit" line saying that a module may register kinds or add-ons. |

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
   - the project page for every kind (§5.1);
   - the add-on tabs: Grant applications and Contacts, on every project;
   - the "Change kind" menu;
   - a full "All projects" page filtered by kind;
   - a cap on sidebar length;
   - the "Your modules" list in settings.

## 10. Decisions (settled by the operator, 26 Oct 2026)

1. **The kind is stored** on each project (`projects.kind`), behind the code
   registry (§4).
2. **Grant funding is an add-on**, not a kind (§3).
3. **A development project opens its project room.** A general project opens its
   chat.
4. **Kind names:** *General project* (key `general`) and *Development project*
   (key `development`).
5. **Sidebar order:** most recently updated first.
6. **The Contacts tab appears on every project,** general projects included. It
   is a true add-on (§5.1).
