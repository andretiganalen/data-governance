# Data Governance

Main workspace for the data governance initiative.

```
data-governance/
├── deploy/
│   ├── openmetadata/   OpenMetadata 2.0.7 stack (mirrored live at /opt/lendatagovernance/deploy)
│   └── ui/             Len theme for the OpenMetadata gateway
├── plan/               Deployment plans and UI standard (Len classic)
├── docs/adr/           Architecture decision records
└── templates/          Reusable templates
```

> The former **DG Projects** web app (Next.js on :3000, Postgres on :5433) was retired on
> 2026-11-05. Its code is in git history before that date; see `docs/adr/pm-0001-application-stack.md`.

## Git remotes
`git pull` ← GitHub · `git push` → GitHub **and** GitLab (`gitlab.len.co.id/devops/data-governance`).
