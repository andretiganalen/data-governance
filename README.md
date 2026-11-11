# Data Governance

Main workspace for the data governance initiative.

```
data-governance/
├── deploy/
│   ├── lendatagovernance/  Len Data Governance stack (mirrored live at /home/ubuntu/data-governance/deploy/lendatagovernance)
│   └── ui/                 Len theme + Visualisasi menu injected by the gateway
├── plan/               Deployment plans and UI standard (Len classic)
├── docs/adr/           Architecture decision records
└── templates/          Reusable templates
```

All business data lives in the Trino lakehouse `lakekeeper.medallion_repository` (Trino `datahub.len.co.id:443`).
Raw CSV/XLSX files are Bronze input only; users read and create tables through Trino (menu Visualisasi).

> The former **DG Projects** web app (Next.js on :3000, Postgres on :5433) was retired on
> 2026-11-05. Its code is in git history before that date; see `docs/adr/pm-0001-application-stack.md`.

## Git remotes
`git pull` ← GitHub · `git push` → GitHub **and** GitLab (`gitlab.len.co.id/devops/data-governance`).
