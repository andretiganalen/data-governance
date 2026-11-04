import type { OrgRole } from "@dg/db";

/** Fine-grained permissions. Roles are bundles of these — extend here, not in UI code. */
export type Permission =
  | "project:read"
  | "project:create"
  | "project:update"
  | "project:delete"
  | "task:read"
  | "task:create"
  | "task:update"
  | "task:delete"
  | "member:manage"
  | "audit:read";

const READ: Permission[] = ["project:read", "task:read"];
const WRITE: Permission[] = [...READ, "task:create", "task:update"];
const MANAGE: Permission[] = [
  ...WRITE,
  "project:create",
  "project:update",
  "project:delete",
  "task:delete",
  "audit:read",
];

export const ROLE_PERMISSIONS: Record<OrgRole, ReadonlySet<Permission>> = {
  VIEWER: new Set(READ),
  MEMBER: new Set(WRITE),
  ADMIN: new Set([...MANAGE, "member:manage"]),
  OWNER: new Set([...MANAGE, "member:manage"]),
};

export function can(role: OrgRole, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role].has(permission);
}
