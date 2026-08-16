"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ctaPrimary } from "./ui";

const NAV = [
  { href: "/platform", label: "Platform" },
  { href: "/solutions/groundwork", label: "Groundwork" },
  { href: "/solutions/grantwork", label: "Grantwork" },
  { href: "/security-and-data", label: "Security & data" },
  { href: "/about", label: "About" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const panelRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);

  const closeMenu = () => setOpen(false);

  // Escape close + focus trap while the mobile menu is open.
  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    panel?.querySelector<HTMLElement>("a, button")?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const items = panel.querySelectorAll<HTMLElement>("a, button");
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className="border-b border-bone bg-canvas">
      <div className="mx-auto flex h-16 w-full max-w-[1200px] items-center justify-between gap-6 px-6">
        <Link
          href="/"
          className="text-[16px] font-medium uppercase tracking-[-0.01em] text-ink"
        >
          Flowgrid&nbsp;OS
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              className={`rounded-full px-4 py-2.5 text-[14px] transition-colors hover:bg-bone ${
                pathname === item.href ? "text-deep-violet" : "text-slate"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-4 lg:flex">
          <Link
            href="/login"
            className="px-2 py-2.5 text-[14px] text-slate underline-offset-4 hover:underline"
          >
            Sign in
          </Link>
          <Link
            href="/contact"
            className="inline-flex min-h-[44px] items-center rounded-full bg-accent px-5 py-2.5 text-[14px] font-medium text-accent-ink transition-colors hover:bg-accent-deep"
          >
            Book a demo
          </Link>
        </div>

        <button
          ref={toggleRef}
          type="button"
          className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full border border-ink px-4 text-[14px] font-medium text-ink lg:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>

      {open && (
        <div
          id="mobile-menu"
          ref={panelRef}
          className="border-t border-bone px-6 py-6 lg:hidden"
        >
          <nav aria-label="Main" className="flex flex-col gap-1">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={pathname === item.href ? "page" : undefined}
                onClick={closeMenu}
                className="rounded-lg px-3 py-3 text-[16px] text-ink hover:bg-bone"
              >
                {item.label}
              </Link>
            ))}
            <Link
              href="/login"
              onClick={closeMenu}
              className="rounded-lg px-3 py-3 text-[16px] text-slate hover:bg-bone"
            >
              Sign in
            </Link>
          </nav>
          <Link
            href="/contact"
            onClick={closeMenu}
            className={`${ctaPrimary} mt-4 w-full`}
          >
            Book a demo
          </Link>
        </div>
      )}
    </header>
  );
}
