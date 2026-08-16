import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      {/* suppressHydrationWarning: browser extensions (e.g. ColorZilla's
          cz-shortcut-listen) stamp attributes on <body> before hydration;
          this scopes only to this element's attributes, not children. */}
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
