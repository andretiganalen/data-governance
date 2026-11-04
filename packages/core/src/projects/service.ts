import { prisma, Prisma } from "@dg/db";
import { audit } from "../audit";
import { authorize, type ActorContext } from "../context";
import { conflict, notFound } from "../errors";
import { CreateProjectSchema, type CreateProjectInput } from "./schemas";

export async function listProjects(ctx: ActorContext) {
  authorize(ctx, "project:read");
  const projects = await prisma.project.findMany({
    where: { organizationId: ctx.organizationId, deletedAt: null },
    orderBy: { createdAt: "desc" },
    include: {
      owner: { select: { id: true, name: true } },
      _count: { select: { tasks: { where: { deletedAt: null } } } },
    },
  });
  const done = await prisma.task.groupBy({
    by: ["projectId"],
    where: { project: { organizationId: ctx.organizationId }, deletedAt: null, status: "DONE" },
    _count: true,
  });
  const doneBy = new Map(done.map((d) => [d.projectId, d._count]));
  return projects.map((p) => ({ ...p, doneCount: doneBy.get(p.id) ?? 0 }));
}

export async function getProjectByKey(ctx: ActorContext, key: string) {
  authorize(ctx, "project:read");
  const project = await prisma.project.findFirst({
    where: { organizationId: ctx.organizationId, key: key.toUpperCase(), deletedAt: null },
    include: { owner: { select: { id: true, name: true } } },
  });
  if (!project) throw notFound("Project");
  return project;
}

export async function createProject(ctx: ActorContext, input: CreateProjectInput) {
  authorize(ctx, "project:create");
  const data = CreateProjectSchema.parse(input);
  try {
    return await prisma.$transaction(async (tx) => {
      const project = await tx.project.create({
        data: { ...data, organizationId: ctx.organizationId, ownerId: ctx.userId },
      });
      await audit(tx, ctx, "project.created", "project", project.id, {
        key: project.key,
        name: project.name,
      });
      return project;
    });
  } catch (e) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2002") {
      throw conflict(`Project key "${data.key}" is already in use`);
    }
    throw e;
  }
}
