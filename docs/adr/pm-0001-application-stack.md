# PM-0001 — Application stack for DG Projects

- Status: Accepted
- Date: 2026-11-04

## Context
We need an internal project-management application that will be developed and
maintained for ~10 years at enterprise scale: many teams, auditability, SSO with
the corporate identity provider (IDS / OIDC), and steady onboarding of new developers.

## Decision
| Concern | Choice | Why |
|---|---|---|
| Language | TypeScript (strict), end to end | One language for UI, API and domain; largest hiring pool |
| Repo | pnpm workspaces + Turborepo monorepo | Shared domain code, cached builds, add apps (worker, mobile API) later without re-platforming |
| Web | Next.js (App Router, Server Components, Server Actions) | Industry default React framework; server-first keeps DB credentials off the client |
| Database | PostgreSQL 16 | Proven, open source, JSON + full-text, partitioning for audit growth |
| ORM / migrations | Prisma 7 (driver adapter `pg`) | Typed client, versioned SQL migrations checked into git |
| Validation | Zod | Single schema for forms, actions and future public API |
| Styling | Tailwind CSS with design tokens | Themeable (light/dark, corporate brand) from one place |
| Tests | Vitest (unit + DB integration); Playwright to be added for E2E | |
| CI | GitHub Actions (lint, typecheck, test, build against real Postgres) | |

## Architecture rules
1. **Layering:** `apps/web` (UI, routing) → `packages/core` (business rules, RBAC, audit) → `packages/db` (schema, client).
   UI never queries Prisma directly for writes; all mutations go through `@dg/core`.
2. **Multi-tenant:** every business row is scoped by `organization_id`; services take an `ActorContext`.
3. **Authorization:** permissions (`project:create`, …) are mapped from roles in `core/permissions.ts`; check with `authorize()`.
4. **Audit:** every mutation writes `audit_logs` in the same transaction.
5. **Identity:** user key is office email; `users.external_id` stores the OIDC subject. Only `apps/web/src/lib/session.ts` knows how identity is resolved.
6. **IDs:** UUIDv7 (time-ordered, index-friendly, safe to expose).
7. **Soft delete:** `deleted_at` on projects, tasks, comments.

## Consequences
- Phase 2 SSO = replace `getActor()` with Auth.js + OIDC provider; no service changes.
- If a separate REST/GraphQL API or background worker is needed, add `apps/api` / `apps/worker` reusing `@dg/core`.
