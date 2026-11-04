import { connection } from "next/server";
import { prisma } from "@dg/db";

/** Liveness/readiness probe for load balancers & monitoring. */
export async function GET() {
  await connection();
  try {
    await prisma.$queryRaw`SELECT 1`;
    return Response.json({ status: "ok", db: "up", time: new Date().toISOString() });
  } catch {
    return Response.json({ status: "degraded", db: "down" }, { status: 503 });
  }
}
