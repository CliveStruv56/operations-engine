/** Shared customer-facing names and availability.
 *
 * Inside the workspace every surface uses the plain `function` name
 * ("Development projects", "Grant funding", "Documents"): an office admin
 * should not have to learn a brand to find a page. The `brand` names belong
 * to the marketing site, where they name what is being sold. */
export const PRODUCT_LANGUAGE = {
  organisation: {
    navigation: "Your organisation",
    description: "Confirmed organisational facts",
    model: "organisation facts",
  },
  documents: {
    navigation: "Documents",
  },
  projects: {
    all: "All projects",
  },
  groundwork: {
    brand: "Groundwork",
    function: "Development projects",
    combined: "Groundwork · Development projects",
    href: "/solutions/groundwork",
    appHref: "/app/projects",
    availability: "Available in pilot",
  },
  grantwork: {
    brand: "Grantwork",
    function: "Grant funding",
    combined: "Grantwork · Grant funding",
    href: "/solutions/grantwork",
    appHref: "/app/grants",
    availability: "Available in pilot",
  },
} as const;

export const WORKFLOW_OPTIONS = [
  { value: "core", label: "Core platform" },
  { value: "development-projects", label: PRODUCT_LANGUAGE.groundwork.combined },
  { value: "grants", label: PRODUCT_LANGUAGE.grantwork.combined },
  { value: "not-sure", label: "Not sure yet" },
] as const;
