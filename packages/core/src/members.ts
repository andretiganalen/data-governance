import { prisma } from "@dg/db";
import { authorize, type ActorContext } from "./context";

export async function listMembers(ctx: ActorContext) {
  authorize(ctx, "project:read");
  const rows = await prisma.membership.findMany({
    where: { organizationId: ctx.organizationId, user: { isActive: true } },
    include: { user: { select: { id: true, name: true, email: true } } },
    orderBy: { user: { name: "asc" } },
  });
  return rows.map((m) => ({ ...m.user, role: m.role }));
}
