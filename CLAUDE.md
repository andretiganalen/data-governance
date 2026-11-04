# DG workspace — notes for coding agents

- Monorepo: pnpm + Turborepo. Run commands from repo root (`pnpm dev|build|lint|typecheck|test`).
- Next.js here is v16 with Cache Components — read `apps/web/AGENTS.md` and `apps/web/node_modules/next/dist/docs/` before writing Next code. Request-time data (DB, cookies) must sit inside `<Suspense>`.
- Writes go through `@dg/core` services (RBAC + audit in one transaction). Never call Prisma for writes from `apps/web`.
- Schema change: edit `packages/db/prisma/schema.prisma` → `pnpm db:migrate` → commit the migration folder.
- Env lives in repo-root `.env` (copy from `.env.example`). Postgres: `pnpm db:up` (port 5433).
- Architecture rules: `docs/adr/pm-0001-application-stack.md`.
- UI default for every web app: `plan/interface-menu.md` (Len classic: colours, fonts, borders, menu from len.co.id). Positions: `plan/leno_interface_theme.md`.
