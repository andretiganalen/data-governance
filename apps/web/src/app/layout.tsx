import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Montserrat, Open_Sans } from "next/font/google";
import { getActor } from "@/lib/session";
import "./globals.css";

// plan/interface-menu.md §2: Montserrat headings/buttons, Open Sans body/menu
const montserrat = Montserrat({
  variable: "--font-montserrat",
  subsets: ["latin"],
  weight: ["600", "700"],
});
const openSans = Open_Sans({
  variable: "--font-open-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: { default: "DG Projects", template: "%s · DG Projects" },
  description: "Project management for the Data Governance programme",
};

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

async function CurrentUser() {
  const actor = await getActor();
  return (
    <span className="flex items-center gap-3">
      <span className="hidden text-right leading-tight sm:block">
        <span className="block text-sm font-medium text-fg">{actor.name}</span>
        <span className="block font-mono text-[11px] text-muted-fg">{actor.role}</span>
      </span>
      <span
        aria-hidden="true"
        className="grid h-[34px] w-[34px] place-items-center rounded-full bg-accent font-heading text-xs font-semibold text-accent-fg"
      >
        {initials(actor.name)}
      </span>
    </span>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="id" className={`${montserrat.variable} ${openSans.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="relative z-10 border-b border-border bg-surface shadow-header">
          <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
            <Link href="/projects" className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className="grid h-[34px] w-[34px] place-items-center rounded bg-accent font-heading text-base font-bold text-accent-fg"
              >
                D
              </span>
              <span className="font-heading text-[17px] font-bold text-accent">DG Projects</span>
            </Link>
            <Suspense fallback={<span className="text-sm text-muted-fg">…</span>}>
              <CurrentUser />
            </Suspense>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">{children}</main>
      </body>
    </html>
  );
}
