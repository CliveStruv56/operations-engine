import Link from "next/link";

const GROUPS: { heading: string; links: { href: string; label: string }[] }[] = [
  {
    heading: "Product",
    links: [
      { href: "/platform", label: "Platform" },
      { href: "/solutions/groundwork", label: "Groundwork" },
      { href: "/solutions/grantwork", label: "Grantwork" },
    ],
  },
  {
    heading: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/security-and-data", label: "Security & data" },
      { href: "/contact", label: "Contact" },
    ],
  },
  {
    heading: "Legal",
    links: [
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms" },
      { href: "/cookies", label: "Cookies" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-bone">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-12 px-6 py-16 md:flex-row md:justify-between">
        <div className="max-w-xs">
          <p className="text-[16px] font-medium uppercase tracking-[-0.01em] text-ink">
            Flowgrid&nbsp;OS
          </p>
          <p className="mt-3 text-[14px] leading-[1.5] text-slate">
            Turn what your organisation knows into work you can trust. Built
            for UK small organisations and specialist teams.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-10 sm:grid-cols-3">
          {GROUPS.map((group) => (
            <div key={group.heading}>
              <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
                {group.heading}
              </p>
              <ul className="mt-4 flex flex-col gap-1">
                {group.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="inline-flex min-h-[44px] items-center text-[14px] text-ink underline-offset-4 hover:underline"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-bone">
        <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-2 px-6 py-6 text-[13px] text-faint md:flex-row md:justify-between">
          <p>© {new Date().getFullYear()} Flowgrid OS. All rights reserved.</p>
          <p>Made in the United Kingdom.</p>
        </div>
      </div>
    </footer>
  );
}
