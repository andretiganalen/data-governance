import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { can, listProjects } from "@dg/core";
import { NewProjectForm } from "@/components/forms";
import { getActor } from "@/lib/session";
import { fmtDate, PROJECT_STATUS_LABEL } from "@/lib/labels";

export const metadata: Metadata = { title: "Projects" };

async function ProjectList() {
  const actor = await getActor();
  const projects = await listProjects(actor);
  return (
    <>
      {can(actor.role, "project:create") && (
        <section className="mb-8 rounded-lg border border-border bg-surface p-5">
          <h2 className="mb-4 text-sm font-semibold">New project</h2>
          <NewProjectForm />
        </section>
      )}
      {projects.length === 0 ? (
        <p className="text-muted-fg">No projects yet.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => {
            const total = p._count.tasks;
            const pct = total ? Math.round((p.doneCount / total) * 100) : 0;
            return (
              <li key={p.id}>
                <Link
                  href={`/projects/${p.key}`}
                  className="block rounded-lg border border-border bg-surface p-5 transition hover:border-accent"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="font-mono text-xs text-muted-fg">{p.key}</span>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs">
                      {PROJECT_STATUS_LABEL[p.status]}
                    </span>
                  </div>
                  <h3 className="font-medium">{p.name}</h3>
                  {p.description && (
                    <p className="mt-1 line-clamp-2 text-sm text-muted-fg">{p.description}</p>
                  )}
                  <div className="mt-4 h-1.5 rounded-full bg-muted">
                    <div className="h-1.5 rounded-full bg-success" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-muted-fg">
                    <span>
                      {p.doneCount}/{total} done
                    </span>
                    <span>Due {fmtDate(p.dueDate)}</span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

export default function ProjectsPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Projects</h1>
      <Suspense fallback={<p className="text-muted-fg">Loading projects…</p>}>
        <ProjectList />
      </Suspense>
    </>
  );
}
