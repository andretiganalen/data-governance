"use server";

import { refresh } from "next/cache";
import { z } from "zod";
import { createProject, createTask, DomainError, updateTaskStatus } from "@dg/core";
import { getActor } from "./session";

export type ActionState = {
  ok: boolean;
  message?: string;
  fieldErrors?: Record<string, string[] | undefined>;
};

async function run(fn: () => Promise<unknown>, success: string): Promise<ActionState> {
  try {
    await fn();
    refresh();
    return { ok: true, message: success };
  } catch (e) {
    if (e instanceof z.ZodError) {
      return {
        ok: false,
        message: "Please fix the highlighted fields.",
        fieldErrors: z.flattenError(e).fieldErrors,
      };
    }
    if (e instanceof DomainError) return { ok: false, message: e.message };
    console.error(e);
    return { ok: false, message: "Unexpected error. Please try again." };
  }
}

const str = (fd: FormData, k: string) => {
  const v = fd.get(k);
  return typeof v === "string" && v.trim() !== "" ? v : undefined;
};

export async function createProjectAction(_: ActionState, fd: FormData): Promise<ActionState> {
  const actor = await getActor();
  return run(
    () =>
      createProject(actor, {
        key: str(fd, "key") ?? "",
        name: str(fd, "name") ?? "",
        description: str(fd, "description"),
        startDate: str(fd, "startDate"),
        dueDate: str(fd, "dueDate"),
      }),
    "Project created",
  );
}

export async function createTaskAction(_: ActionState, fd: FormData): Promise<ActionState> {
  const actor = await getActor();
  return run(
    () =>
      createTask(actor, {
        projectId: str(fd, "projectId") ?? "",
        title: str(fd, "title") ?? "",
        priority: (str(fd, "priority") as "MEDIUM") ?? "MEDIUM",
        dueDate: str(fd, "dueDate"),
        assigneeId: str(fd, "assigneeId"),
      }),
    "Task created",
  );
}

export async function updateTaskStatusAction(taskId: string, status: string): Promise<ActionState> {
  const actor = await getActor();
  return run(() => updateTaskStatus(actor, { taskId, status: status as "TODO" }), "Status updated");
}
