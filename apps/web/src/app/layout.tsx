import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import { getActor } from "@/lib/session";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "DG Projects", template: "%s · DG Projects" },
  description: "Project management for the Data Governance programme",
};

async function CurrentUser() {
  const actor = await getActor();
  return (
    <span className="text-sm text-muted-fg">
      {actor.name} · <span className="font-mono text-xs">{actor.role}</span>
    </span>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="id" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-border bg-surface">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
            <Link href="/projects" className="font-semibold tracking-tight">
              DG <span className="text-accent">Projects</span>
            </Link>
            <Suspense fallback={<span className="text-sm text-muted-fg">…</span>}>
              <CurrentUser />
            </Suspense>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
