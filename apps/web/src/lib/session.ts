import "server-only";
import { cookies } from "next/headers";
import { prisma } from "@dg/db";
import type { ActorContext } from "@dg/core";

/**
 * Resolves the acting user + tenant for this request.
 *
 * Phase 1 (now): local dev identity from DEV_USER_EMAIL.
 * Phase 2: replace the body with Auth.js / OIDC (IDS) session lookup —
 *          callers keep using getActor() unchanged.
 */
export async function getActor(): Promise<ActorContext & { name: string; email: string }> {
  const jar = await cookies(); // request-time: keeps every caller dynamic (Cache Components)
  const email = jar.get("dg_dev_user")?.value ?? process.env.DEV_USER_EMAIL;
  if (!email || process.env.NODE_ENV === "production") {
    throw new Error("No authenticated user. Configure SSO before running in production.");
  }
  const user = await prisma.user.findUnique({
    where: { email },
    include: { memberships: { take: 1, orderBy: { createdAt: "asc" } } },
  });
  const membership = user?.memberships[0];
  if (!user || !membership)
    throw new Error(`Dev user ${email} has no organization membership. Run: pnpm db:seed`);
  return {
    userId: user.id,
    organizationId: membership.organizationId,
    role: membership.role,
    name: user.name,
    email: user.email,
  };
}
