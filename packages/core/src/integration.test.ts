import path from "node:path";
import { config } from "dotenv";
import { afterAll, describe, expect, it } from "vitest";

config({ path: path.resolve(import.meta.dirname, "../../../.env") });
const { prisma } = await import("@dg/db");
const { createProject, createTask, updateTaskStatus } = await import("./index");

const hasDb = !!process.env.DATABASE_URL;

describe.skipIf(!hasDb)("project/task services (integration)", async () => {
  const user = await prisma.user.upsert({
    where: { email: "it-test@example.local" },
    update: {},
    create: { email: "it-test@example.local", name: "IT Test" },
  });
  const org = await prisma.organization.create({
    data: { slug: `it-${Date.now()}`, name: "IT Org" },
  });
  await prisma.membership.create({
    data: { organizationId: org.id, userId: user.id, role: "ADMIN" },
  });
  const admin = { userId: user.id, organizationId: org.id, role: "ADMIN" as const };
  const viewer = { ...admin, role: "VIEWER" as const };

  afterAll(async () => {
    await prisma.organization.delete({ where: { id: org.id } });
    await prisma.user.delete({ where: { id: user.id } });
    await prisma.$disconnect();
  });

  it("creates project, numbers tasks sequentially under concurrency, audits", async () => {
    const p = await createProject(admin, { key: "it", name: "Integration" });
    expect(p.key).toBe("IT");
    const tasks = await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        createTask(admin, { projectId: p.id, title: `Task ${i}` }),
      ),
    );
    expect(tasks.map((t) => t.number).sort()).toEqual([1, 2, 3, 4, 5]);
    await updateTaskStatus(admin, { taskId: tasks[0].id, status: "DONE" });
    const logs = await prisma.auditLog.count({ where: { organizationId: org.id } });
    expect(logs).toBe(1 + 5 + 1);
  });

  it("rejects duplicate project key", async () => {
    await expect(createProject(admin, { key: "IT", name: "Dup" })).rejects.toThrow(
      /already in use/,
    );
  });

  it("viewer cannot create tasks", async () => {
    const p = await prisma.project.findFirstOrThrow({ where: { organizationId: org.id } });
    await expect(createTask(viewer, { projectId: p.id, title: "Nope" })).rejects.toThrow(
      /permission/,
    );
  });
});
