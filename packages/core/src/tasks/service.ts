import { prisma } from "@dg/db";
import { audit } from "../audit";
import { authorize, type ActorContext } from "../context";
import { notFound } from "../errors";
import {
  CreateTaskSchema,
  UpdateTaskStatusSchema,
  type CreateTaskInput,
  type UpdateTaskStatusInput,
} from "./schemas";

export async function listTasks(ctx: ActorContext, projectId: string) {
  authorize(ctx, "task:read");
  return prisma.task.findMany({
    where: { projectId, deletedAt: null, project: { organizationId: ctx.organizationId } },
    orderBy: [{ status: "asc" }, { sortOrder: "asc" }, { number: "asc" }],
    include: { assignee: { select: { id: true, name: true } } },
  });
}

export async function createTask(ctx: ActorContext, input: CreateTaskInput) {
  authorize(ctx, "task:create");
  const data = CreateTaskSchema.parse(input);
  return prisma.$transaction(async (tx) => {
    // Atomic per-project counter → stable human keys (DG-1, DG-2, …), safe under concurrency.
    const project = await tx.project
      .update({
        where: { id: data.projectId, organizationId: ctx.organizationId, deletedAt: null },
        data: { taskSeq: { increment: 1 } },
        select: { id: true, key: true, taskSeq: true },
      })
      .catch(() => {
        throw notFound("Project");
      });
    if (data.assigneeId) {
      const member = await tx.membership.findUnique({
        where: {
          organizationId_userId: { organizationId: ctx.organizationId, userId: data.assigneeId },
        },
      });
      if (!member) throw notFound("Assignee");
    }
    const task = await tx.task.create({
      data: {
        ...data,
        number: project.taskSeq,
        reporterId: ctx.userId,
        sortOrder: project.taskSeq,
      },
    });
    await audit(tx, ctx, "task.created", "task", task.id, {
      key: `${project.key}-${task.number}`,
      title: task.title,
    });
    return task;
  });
}

export async function updateTaskStatus(ctx: ActorContext, input: UpdateTaskStatusInput) {
  authorize(ctx, "task:update");
  const { taskId, status } = UpdateTaskStatusSchema.parse(input);
  return prisma.$transaction(async (tx) => {
    const existing = await tx.task.findFirst({
      where: { id: taskId, deletedAt: null, project: { organizationId: ctx.organizationId } },
      select: { status: true },
    });
    if (!existing) throw notFound("Task");
    const task = await tx.task.update({ where: { id: taskId }, data: { status } });
    await audit(tx, ctx, "task.status_changed", "task", taskId, {
      from: existing.status,
      to: status,
    });
    return task;
  });
}
