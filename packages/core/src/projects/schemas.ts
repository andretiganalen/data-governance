import { z } from "zod";

export const ProjectStatusSchema = z.enum([
  "PLANNED",
  "ACTIVE",
  "ON_HOLD",
  "COMPLETED",
  "ARCHIVED",
]);

const optionalDate = z.preprocess(
  (v) => (v === "" || v == null ? undefined : v),
  z.coerce.date().optional(),
);

export const CreateProjectSchema = z
  .object({
    key: z
      .string()
      .trim()
      .toUpperCase()
      .regex(/^[A-Z][A-Z0-9]{1,9}$/, "2–10 chars, letters/digits, starting with a letter"),
    name: z.string().trim().min(3).max(120),
    description: z.string().trim().max(5000).optional(),
    status: ProjectStatusSchema.default("PLANNED"),
    startDate: optionalDate,
    dueDate: optionalDate,
  })
  .refine((p) => !p.startDate || !p.dueDate || p.dueDate >= p.startDate, {
    message: "Due date must be on or after start date",
    path: ["dueDate"],
  });

export type CreateProjectInput = z.input<typeof CreateProjectSchema>;
