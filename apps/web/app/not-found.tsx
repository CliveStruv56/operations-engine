import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-canvas px-6 text-center">
      <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-slate">
        404 · Not found
      </p>
      <h1 className="mt-4 max-w-xl text-[40px] font-light leading-[1.15] tracking-[-0.92px] text-ink">
        That page isn&rsquo;t here.
      </h1>
      <p className="mt-4 max-w-md text-[16px] leading-[1.45] text-slate">
        The link may be out of date. Everything on the site is reachable from
        the homepage.
      </p>
      <Link
        href="/"
        className="mt-8 inline-flex min-h-[44px] items-center justify-center rounded-full bg-accent px-6 py-3 text-[16px] font-medium text-accent-ink transition-colors hover:bg-accent-deep"
      >
        Back to the homepage
      </Link>
    </main>
  );
}
