/** Shared customer-facing names and availability. */
export const PRODUCT_LANGUAGE = {
  organisation: {
    navigation: "Your organisation",
    description: "Confirmed organisational facts",
    model: "claims register",
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
