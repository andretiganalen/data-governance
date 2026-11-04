# Data Governance

Main development workspace for the data governance initiative, including **DG Projects**,
the project-management web app.

```
data-governance/
├── apps/
│   └── web/            Next.js app (UI, routes, server actions)       → http://localhost:3000
├── packages/
│   ├── core/           Domain logic: validation, RBAC, audit, services (@dg/core)
│   └── db/             Prisma schema, migrations, seed, client       (@dg/db)
├── plan/               Deployment / implementation plans (OpenMetadata, …)
├── docs/adr/           Architecture decision records
├── templates/          Reusable templates
├── docker-compose.yml  Local PostgreSQL (127.0.0.1:5433)
└── .github/workflows/  CI
```

## Quick start

```bash
cp .env.example .env          # first time only
pnpm install
pnpm db:up                    # start Postgres in Docker
pnpm db:deploy && pnpm db:seed
pnpm dev                      # http://localhost:3000
```

## Common commands

| Command | What it does |
|---|---|
| `pnpm dev` | Run all apps in dev mode |
| `pnpm build` / `lint` / `typecheck` / `test` | Turborepo pipeline across workspaces |
| `pnpm db:migrate` | Create + apply a migration after editing `packages/db/prisma/schema.prisma` |
| `pnpm db:studio` | Browse data in Prisma Studio |
| `pnpm db:down` | Stop Postgres (data kept in volume `dg-pgdata`) |

See [docs/adr/pm-0001-application-stack.md](docs/adr/pm-0001-application-stack.md) for stack and architecture rules.

## Git remotes
`git pull` ← GitHub · `git push` → GitHub **and** GitLab (`gitlab.len.co.id/devops/data-governance`).
