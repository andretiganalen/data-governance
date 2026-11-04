import type { Prisma } from "@dg/db";
import type { ActorContext } from "./context";

type Tx = Prisma.TransactionClient;

export function audit(
  tx: Tx,
  ctx: ActorContext,
  action: string,
  entityType: string,
  entityId: string,
  data?: Prisma.InputJsonValue,
) {
  return tx.auditLog.create({
    data: {
      organizationId: ctx.organizationId,
      actorId: ctx.userId,
      action,
      entityType,
      entityId,
      data,
    },
  });
}
