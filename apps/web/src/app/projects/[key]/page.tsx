import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { can, DomainError, getProjectByKey, listMembers, listTasks } from "@dg/core";
import { NewTaskForm } from "@/components/forms";
import { TaskStatusSelect } from "@/components/task-status-select";
import { getActor } from "@/lib/session";
import {
  fmtDate,
  PRIORITY_STYLE,
  PROJECT_STATUS_LABEL,
  TASK_STATUSES,
  TASK_STATUS_LABEL,
} from "@/lib/labels";

async function Board({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const actor = await getActor();
  const project = await getProjectByKey(actor, key).catch((e) => {
    if (e instanceof DomainError && e.code === "NOT_FOUND") notFound();
    throw e;
  });
  const [tasks, members] = await Promise.all([listTasks(actor, project.id), listMembers(actor)]);
  const canEdit = can(actor.role, "task:update");

  return (
    <>
      <div className="mb-6">
        <Link href="/projects" className="text-sm text-muted-fg hover:text-fg">
          ← Projects
        </Link>
        <div className="mt-2 flex flex-wrap items-baseline gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
          <span className="font-mono text-sm text-muted-fg">{project.key}</span>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs">
            {PROJECT_STATUS_LABEL[project.status]}
          </span>
        </div>
        {project.description && <p className="mt-1 text-muted-fg">{project.description}</p>}
        <p className="mt-1 text-xs text-muted-fg">
          Owner {project.owner?.name ?? "—"} · {fmtDate(project.startDate)} →{" "}
          {fmtDate(project.dueDate)}
        </p>
      </div>

      {can(actor.role, "task:create") && (
        <section className="mb-6 rounded-lg border border-border bg-surface p-4">
          <NewTaskForm projectId={project.id} members={members} />
        </section>
      )}

      <div className="grid gap-4 md:grid-cols-5">
        {TASK_STATUSES.map((status) => {
          const col = tasks.filter((t) => t.status === status);
          return (
            <section key={status} className="rounded-lg bg-muted/60 p-3">
              <h2 className="mb-3 flex justify-between text-xs font-semibold uppercase tracking-wide text-muted-fg">
                {TASK_STATUS_LABEL[status]} <span>{col.length}</span>
              </h2>
              <ul className="space-y-2">
                {col.map((t) => (
                  <li
                    key={t.id}
                    className="rounded-md border border-border bg-surface p-3 shadow-sm"
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <span className="font-mono text-xs text-muted-fg">
                        {project.key}-{t.number}
                      </span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${PRIORITY_STYLE[t.priority]}`}
                      >
                        {t.priority}
                      </span>
                    </div>
                    <p className="text-sm">{t.title}</p>
                    <div className="mt-2 flex items-center justify-between gap-2 text-xs text-muted-fg">
                      <span className="truncate">{t.assignee?.name ?? "Unassigned"}</span>
                      {canEdit ? <TaskStatusSelect taskId={t.id} status={t.status} /> : null}
                    </div>
                    {t.dueDate && (
                      <p className="mt-1 text-xs text-muted-fg">Due {fmtDate(t.dueDate)}</p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </>
  );
}

export default function ProjectPage({ params }: PageProps<"/projects/[key]">) {
  return (
    <Suspense fallback={<p className="text-muted-fg">Loading board…</p>}>
      <Board params={params} />
    </Suspense>
  );
}
