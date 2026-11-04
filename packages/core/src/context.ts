import type { OrgRole } from "@dg/db";
import { forbidden } from "./errors";
import { can, type Permission } from "./permissions";

/** Who is acting, in which tenant. Built once per request by the auth layer. */
export interface ActorContext {
  userId: string;
  organizationId: string;
  role: OrgRole;
}

export function authorize(ctx: ActorContext, permission: Permission): void {
  if (!can(ctx.role, permission)) throw forbidden();
}
