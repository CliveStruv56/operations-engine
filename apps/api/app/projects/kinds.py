"""Project kinds and project add-ons: the one registry the app reads.

Every project has the core capability — scoped chat, documents, an optional
plan. A *kind* is what a project fundamentally is; it is stored on
`projects.kind`, a project has exactly one, and a module may supply it (a
development project is a `projects`-module kind with its own room). An
*add-on* is a module that adds a tab to every project whatever its kind;
several apply at once (docs/project-types-brief.md §1, §4).

Adding a kind is: an entry here, its module, a migration widening
`projects_kind_check` (see 0031), and an icon in the web app. The sidebar,
the new-project picker, the operator console and the export all read this
registry, so nothing else should need to learn the new kind's name.

Grant funding is an add-on, not a kind, by decision: kinds are exclusive, and
a development scheme is exactly the thing people apply for grants for.
"""

from dataclasses import dataclass
from typing import Literal

from app.modules import FEATURE_FLAGS, MODULES


@dataclass(frozen=True)
class ProjectKind:
    key: str  # stored in projects.kind
    label: str
    description: str  # one line, for the picker and the operator console
    module: str | None  # feature flag that supplies it; None = core
    home: Literal["chat", "room"]  # where clicking the project goes
    create: Literal["inline", "setup"]  # POST /projects, or the module's setup page
    upgrades_to: tuple[str, ...] = ()  # kinds this one may become


@dataclass(frozen=True)
class ProjectAddOn:
    key: str
    label: str  # tab label
    description: str
    module: str


PROJECT_KINDS: tuple[ProjectKind, ...] = (
    ProjectKind(
        key="general",
        label="General project",
        description="Chat and documents, with an optional plan of tasks.",
        module=None,
        home="chat",
        create="inline",
        upgrades_to=("development",),
    ),
    ProjectKind(
        key="development",
        label="Development project",
        description="A stage-gated housing scheme: gates, tasks, funding, budget and risks.",
        module="projects",
        home="room",
        create="setup",
    ),
)

PROJECT_ADDONS: tuple[ProjectAddOn, ...] = (
    ProjectAddOn(
        key="contacts",
        label="Contacts",
        description="Link contacts and companies to a project.",
        module="contacts",
    ),
    ProjectAddOn(
        key="grants",
        label="Grant applications",
        description="Track the grant applications made for a project.",
        module="grants",
    ),
)

DEFAULT_KIND = "general"
KINDS_BY_KEY: dict[str, ProjectKind] = {k.key: k for k in PROJECT_KINDS}


def _check_registry() -> None:
    """Fail at import, not in production, on a typo in the registry."""
    if DEFAULT_KIND not in KINDS_BY_KEY or KINDS_BY_KEY[DEFAULT_KIND].module is not None:
        raise RuntimeError("the default kind must exist and be core")
    for kind in PROJECT_KINDS:
        if kind.module is not None and kind.module not in FEATURE_FLAGS:
            raise RuntimeError(f"kind {kind.key!r} names unknown module {kind.module!r}")
        for target in kind.upgrades_to:
            if target not in KINDS_BY_KEY:
                raise RuntimeError(f"kind {kind.key!r} upgrades to unknown kind {target!r}")
    for addon in PROJECT_ADDONS:
        if addon.module not in FEATURE_FLAGS:
            raise RuntimeError(f"add-on {addon.key!r} names unknown module {addon.module!r}")


_check_registry()


def kind_available(kind: str, features: dict[str, object]) -> bool:
    """Whether a kind's module is on. Core kinds are always available; an
    unknown stored kind (a registry entry removed) is treated as unavailable,
    so its projects fall back to the default kind's behaviour."""
    spec = KINDS_BY_KEY.get(kind)
    if spec is None:
        return False
    return spec.module is None or features.get(spec.module) is True


def module_catalogue() -> list[dict[str, object]]:
    """Every module with the kinds and add-ons it supplies — what the operator
    console's checkboxes and a workspace's "Your modules" list both show."""
    return [
        {
            "flag": m.flag,
            "label": m.label,
            "kinds": [
                {"key": k.key, "label": k.label} for k in PROJECT_KINDS if k.module == m.flag
            ],
            "addons": [a.label for a in PROJECT_ADDONS if a.module == m.flag],
        }
        for m in MODULES
    ]
