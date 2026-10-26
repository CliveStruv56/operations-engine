"use client";

import { useWorkspace } from "../../workspace";
import { ContactsTab } from "./tabs/ContactsTab";
import { GrantApplicationsTab } from "./tabs/GrantApplicationsTab";

/** The tab each add-on draws on a project page. The API's registry decides
 *  which add-ons exist and which are on; an add-on this client has no tab
 *  for is skipped rather than drawn empty. */
function AddonTab({ addon, id }: { addon: string; id: string }) {
  switch (addon) {
    case "contacts":
      return <ContactsTab id={id} />;
    case "grants":
      return <GrantApplicationsTab id={id} />;
    default:
      return null;
  }
}

const KNOWN_ADDONS = new Set(["contacts", "grants"]);

export type ProjectTab = { label: string; render: (id: string) => React.ReactNode };

/** The add-on tabs for this workspace, in registry order, on every kind of
 *  project (docs/project-types-brief.md §5.1). */
export function useAddonTabs(): ProjectTab[] {
  const ws = useWorkspace();
  return ws.projectKinds.addons
    .filter((addon) => addon.available && KNOWN_ADDONS.has(addon.key))
    .map((addon) => ({
      label: addon.label,
      render: (id: string) => <AddonTab addon={addon.key} id={id} />,
    }));
}

/** The tab strip shared by both project pages. */
export function TabStrip({
  tabs,
  current,
  onSelect,
}: {
  tabs: string[];
  current: string;
  onSelect: (tab: string) => void;
}) {
  return (
    <nav className="mb-5 flex flex-wrap gap-1 border-b border-line">
      {tabs.map((t) => (
        <button
          key={t}
          onClick={() => onSelect(t)}
          aria-current={t === current ? "page" : undefined}
          className={`px-3 py-2 text-sm ${
            t === current
              ? "border-b-2 border-deep-violet font-medium text-deep-violet"
              : "text-ink-muted hover:text-ink"
          }`}
        >
          {t}
        </button>
      ))}
    </nav>
  );
}
