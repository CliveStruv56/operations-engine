# One Projects list, with a project type

**Status: proposed, 26 Oct 2026. Not approved and not built.** §8 lists the
decisions needed before work starts. It follows on from the UI review merged
in #11. That review found two project sections side by side in the sidebar,
and the operator asked for one section with a "type" on each project.

## 1. The problem

The sidebar shows two lists of projects:

- **Development projects** (Groundwork, behind the `projects` feature flag),
  with a "See all" link and a ↗ on each row.
- **Projects**, holding everything else, headed by "All projects".

To an office admin these look like the same thing listed twice. They also
behave differently:

- Clicking a development project's name opens a **chat** scoped to it.
- Its small ↗ opens the **project room**.
- Clicking any other project opens its chat.

So the same name leads to two places, depending on where you click.

## 2. What exists today

A project already has one of three kinds. Every one is a row in `projects`,
and the database already records which kind it is:

| Kind | How the data says so | What it offers |
|---|---|---|
| **Documents** | `has_plan = false`, no `proj_projects` row | Scoped chat and documents |
| **With a plan** | `projects.has_plan = true` (0018) | Chat, documents, project brief, checklist of tasks (`project_tasks`) |
| **Development** | a `proj_projects` row exists (0003, 1:1, `on delete cascade`) | Chat, documents, the project room (10 tabs: stages and gates, tasks, funding, budget, risks…) |

What the code already does with these kinds:

- **Sidebar sorting:** `GET /projects` derives `is_development` with a left
  join to `proj_projects` (`routers/projects.py:25-36`). The sidebar uses it
  to put each project in one section or the other.
- **Creating a project, two different ways:**
  - The sidebar's "+ New" offers *Documents* or *With a plan*
    (`new-project-form.tsx`).
  - Development projects come from a separate page, `/app/projects/new`,
    which calls `POST /projects` and then `POST /projects/{id}/setup`.
- **Upgrading a project, one way at a time:**
  - Documents → plan works today (`POST /projects/{id}/plan`).
  - Documents → development works today, through `setup`.
  - Plan ↔ development is refused by design (ASSUMPTIONS #51, `setup`
    returns 409).

**There is also a bug.** If a tenant's `projects` flag is turned off, its
development projects vanish from the sidebar entirely:

- `devProjects` is empty when the flag is off.
- `coreProjects` excludes anything with `is_development`.

Their chats and documents still exist, but nothing in the sidebar leads to
them.

## 3. Proposal: derive the type, don't store it

**Phase 1 needs no migration.** The type is already in the data, so storing it
again would only create a second copy that can drift from the first. Instead:

- **Add the field.** `ProjectOut` gains `type: "documents" | "plan" | "development"`,
  computed in the same query that computes `is_development` today:
  - `development` if a `proj_projects` row exists;
  - otherwise `plan` if `has_plan` is true;
  - otherwise `documents`.
- **Keep the old fields for now.** `is_development` and `has_plan` stay, so
  nothing else breaks. A later cleanup can remove `is_development`.
- **No security changes.** No new table and no new column means no new RLS
  policy and no new isolation test (hard constraint 2 is not triggered). RLS
  on `projects` and on the `proj_*` tables is unchanged.
- **ASSUMPTIONS #1 and #51 still hold.** All three kinds stay `projects` rows.
  A plan is still not Groundwork.

## 4. What users will see

**Sidebar: one "Projects" section**

- **"All projects"** comes first, as now.
- **Each project row** shows:
  - an icon for its type: document, checklist, or the existing pulse icon
    for development;
  - the name;
  - a short status on the right: a document count for *Documents*, open tasks
    for *With a plan*, and the current stage for *Development*.
  - The type's name is in the row's accessible name and its tooltip, so the
    icon is never the only signal.
- **One click rule:** clicking a project opens its home.
  - *Documents* and *With a plan* open the scoped chat, as today.
  - *Development* opens the **project room**. The room gets a "Chat about
    this project" button, so the scoped chat is one click away.
  - The ↗ glyph goes away.
- **Order:** most recently updated first.
- **Archived projects** stay hidden, as now.

**Creating a project: one "+ New project" button**

1. **Step 1, choose a type.** Three cards, each with a one-line description:
   *Documents*, *With a plan*, *Development project*. The development card
   only appears when the tenant has the module.
2. **Step 2, details.**
   - *Documents* and *With a plan* use the existing inline form.
   - *Development project* continues to the existing `/app/projects/new` setup
     page, with the name carried across.

**Changing type (phase 2)**

- A "Change type" item in each project's menu offers only the upgrades the
  API already allows: Documents → With a plan, and Documents → Development.
- All other directions are not offered, matching #51.

**Module switched off**

- Development projects still appear, as *Documents* rows that open their chat.
  This fixes the bug in §2.
- The project room stays behind the flag: its API routes return 404 when the module is off.

## 5. Changes by layer

| Layer | Change |
|---|---|
| API | `ProjectOut.type`, plus `stage_current` for development rows (already in the `proj_projects` join), both computed in `routers/projects.py`. No new endpoints. |
| API tests | Extend `test_projects_list_flags_development` to assert all three `type` values, plus the flag-off case. |
| Web types | `Project.type` in `workspace.tsx`. |
| Sidebar | Merge the two sections in `sidebar.tsx` into one list driven by `type`. The file shrinks, and is currently 383 lines. |
| New project | `new-project-form.tsx` gains the type step. The development card hands off to `/app/projects/new?name=…`. |
| Project room | Add a "Chat about this project" button. |
| Copy | Type names in `lib/product-language.ts`. |
| Web tests | A sidebar test: one section, a type label per row, the click target per type, and development rows shown when the flag is off. |
| Docs | ASSUMPTIONS #70: one list with a derived type. It supersedes the presentation half of #15. |

## 6. Phases

1. **Phase 1, one PR, about a day:**
   - the `type` field;
   - the single sidebar section;
   - the type step in "+ New project";
   - development rows open the room;
   - the flag-off fix;
   - tests and #70.
2. **Phase 2, later:**
   - the "Change type" menu;
   - a full "All projects" page with a filter by type;
   - a cap on sidebar length (latest 8, then "Show all").

## 7. Risks

- **Muscle memory.** People used to clicking a development project to chat will
  land in the room instead. The "Chat about this project" button covers this,
  and so does the scoped chat still reachable from "All projects".
- **A list with three kinds of project is busier.** The type icon and the
  status text carry the difference. If it still reads as crowded, phase 2's
  filter and cap are the answer, not two sections again.

## 8. Decisions needed

1. **What does "type" mean to you?**
   - It could be the three kinds above, which decide what a project can do.
     That needs no migration.
   - It could also mean your own labels, such as *Client*, *Internal* or
     *Bid*. Those would be a separate, optional addition: a nullable
     `projects.category` column, with a migration and an isolation-test
     update.
2. **Should a development project open its project room or its chat?** The
   room is recommended.
3. **What should the types be called?** Proposed: *Documents*, *With a plan*,
   *Development project*.
4. **How should the list be ordered?** By most recently updated (proposed),
   alphabetically, or grouped by type?
