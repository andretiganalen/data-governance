"use client";

import { useActionState, useEffect, useRef } from "react";
import { createProjectAction, createTaskAction, type ActionState } from "@/lib/actions";

const initial: ActionState = { ok: false };
const input =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20";
const label = "block text-xs font-medium text-muted-fg mb-1";

function FieldError({ errors }: { errors?: string[] }) {
  return errors?.length ? <p className="mt-1 text-xs text-danger">{errors[0]}</p> : null;
}

function Status({ state }: { state: ActionState }) {
  if (!state.message) return null;
  return <p className={`text-sm ${state.ok ? "text-success" : "text-danger"}`}>{state.message}</p>;
}

function useResetOnSuccess(state: ActionState) {
  const ref = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (state.ok) ref.current?.reset();
  }, [state]);
  return ref;
}

export function NewProjectForm() {
  const [state, action, pending] = useActionState(createProjectAction, initial);
  const ref = useResetOnSuccess(state);
  const fe = state.fieldErrors ?? {};
  return (
    <form ref={ref} action={action} className="grid gap-3 sm:grid-cols-6">
      <div className="sm:col-span-1">
        <label className={label} htmlFor="key">
          Key
        </label>
        <input
          id="key"
          name="key"
          placeholder="DG"
          className={`${input} uppercase`}
          required
          maxLength={10}
        />
        <FieldError errors={fe.key} />
      </div>
      <div className="sm:col-span-3">
        <label className={label} htmlFor="name">
          Project name
        </label>
        <input id="name" name="name" placeholder="Data Governance ERM" className={input} required />
        <FieldError errors={fe.name} />
      </div>
      <div className="sm:col-span-1">
        <label className={label} htmlFor="startDate">
          Start
        </label>
        <input id="startDate" name="startDate" type="date" className={input} />
      </div>
      <div className="sm:col-span-1">
        <label className={label} htmlFor="dueDate">
          Due
        </label>
        <input id="dueDate" name="dueDate" type="date" className={input} />
        <FieldError errors={fe.dueDate} />
      </div>
      <div className="sm:col-span-6">
        <label className={label} htmlFor="description">
          Description
        </label>
        <textarea id="description" name="description" rows={2} className={input} />
      </div>
      <div className="flex items-center gap-3 sm:col-span-6">
        <button
          disabled={pending}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
        >
          {pending ? "Creating…" : "Create project"}
        </button>
        <Status state={state} />
      </div>
    </form>
  );
}

export function NewTaskForm({
  projectId,
  members,
}: {
  projectId: string;
  members: { id: string; name: string }[];
}) {
  const [state, action, pending] = useActionState(createTaskAction, initial);
  const ref = useResetOnSuccess(state);
  const fe = state.fieldErrors ?? {};
  return (
    <form ref={ref} action={action} className="grid gap-3 sm:grid-cols-12">
      <input type="hidden" name="projectId" value={projectId} />
      <div className="sm:col-span-5">
        <label className={label} htmlFor="title">
          Task
        </label>
        <input
          id="title"
          name="title"
          placeholder="What needs to be done?"
          className={input}
          required
        />
        <FieldError errors={fe.title} />
      </div>
      <div className="sm:col-span-2">
        <label className={label} htmlFor="priority">
          Priority
        </label>
        <select id="priority" name="priority" defaultValue="MEDIUM" className={input}>
          <option value="LOW">Low</option>
          <option value="MEDIUM">Medium</option>
          <option value="HIGH">High</option>
          <option value="URGENT">Urgent</option>
        </select>
      </div>
      <div className="sm:col-span-2">
        <label className={label} htmlFor="assigneeId">
          Assignee
        </label>
        <select id="assigneeId" name="assigneeId" className={input} defaultValue="">
          <option value="">Unassigned</option>
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-2">
        <label className={label} htmlFor="tdue">
          Due
        </label>
        <input id="tdue" name="dueDate" type="date" className={input} />
      </div>
      <div className="flex items-end sm:col-span-1">
        <button
          disabled={pending}
          className="w-full rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
        >
          {pending ? "…" : "Add"}
        </button>
      </div>
      {!state.ok && state.message ? (
        <div className="sm:col-span-12">
          <Status state={state} />
        </div>
      ) : null}
    </form>
  );
}
