"use client";

import { useTransition } from "react";
import { updateTaskStatusAction } from "@/lib/actions";
import { TASK_STATUSES, TASK_STATUS_LABEL } from "@/lib/labels";

export function TaskStatusSelect({ taskId, status }: { taskId: string; status: string }) {
  const [pending, start] = useTransition();
  return (
    <select
      aria-label="Change status"
      defaultValue={status}
      disabled={pending}
      onChange={(e) => {
        const next = e.target.value;
        start(async () => {
          const r = await updateTaskStatusAction(taskId, next);
          if (!r.ok) alert(r.message);
        });
      }}
      className="rounded border border-border bg-surface px-1.5 py-0.5 text-xs text-muted-fg disabled:opacity-50"
    >
      {TASK_STATUSES.map((s) => (
        <option key={s} value={s}>
          {TASK_STATUS_LABEL[s]}
        </option>
      ))}
    </select>
  );
}
