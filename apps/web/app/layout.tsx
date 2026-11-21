import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import { connection } from "next/server";
import { META_POLICY } from "@/lib/csp";
import "./globals.css";

const inter = Inter({
  variable: "--font-ui",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Flowgrid",
  description: "Your company documents, working for you",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Every page renders per request so its scripts carry that request's CSP
  // nonce (proxy.ts, lib/csp.ts). A page prerendered at build time has no
  // nonce, and the policy would refuse every script on it.
  await connection();
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        {/* The 12 Oct baseline, enforced while the full nonce policy is still
            report-only (lib/csp.ts). Harmless once that is enforced. */}
        <meta httpEquiv="Content-Security-Policy" content={META_POLICY} />
      </head>
      {/* suppressHydrationWarning: browser extensions (e.g. ColorZilla's
          cz-shortcut-listen) stamp attributes on <body> before hydration;
          this scopes only to this element's attributes, not children. */}
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
