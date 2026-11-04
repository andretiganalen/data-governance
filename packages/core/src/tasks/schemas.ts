import { z } from "zod";

export const TaskStatusSchema = z.enum(["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE", "CANCELLED"]);
export const TaskPrioritySchema = z.enum(["LOW", "MEDIUM", "HIGH", "URGENT"]);

const emptyToUndef = (v: unknown) => (v === "" || v == null ? undefined : v);

export const CreateTaskSchema = z.object({
  projectId: z.uuid(),
  title: z.string().trim().min(3).max(200),
  description: z.string().trim().max(10000).optional(),
  priority: TaskPrioritySchema.default("MEDIUM"),
  assigneeId: z.preprocess(emptyToUndef, z.uuid().optional()),
  dueDate: z.preprocess(emptyToUndef, z.coerce.date().optional()),
});

export const UpdateTaskStatusSchema = z.object({
  taskId: z.uuid(),
  status: TaskStatusSchema,
});

export type CreateTaskInput = z.input<typeof CreateTaskSchema>;
export type UpdateTaskStatusInput = z.input<typeof UpdateTaskStatusSchema>;
