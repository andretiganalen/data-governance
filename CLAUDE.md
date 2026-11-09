# DG workspace — notes for coding agents

- OpenMetadata deploy lives in `deploy/lendatagovernance` (live copy: `/opt/lendatagovernance/deploy`, data: `/srv/lendatagovernance`). Plan: `plan/openmetadata_deployment_plan.md`.
- UI default for every web app: `plan/interface-menu.md` (Len classic: colours, fonts, borders, menu from len.co.id). Positions: `plan/leno_interface_theme.md`.
- The DG Projects app (apps/web, packages/*) was removed on 2026-11-05; recover it from git history if ever needed.
- Data rule (2026-11-09, Andre Tigana): every database/dataset used by an app must live in the Trino lakehouse. Apps read and write their business data through Trino; no separate app databases, local files or CSV/XLSX stores as the system of record. Exception: a platform's own internal store that Trino cannot host (e.g. OpenMetadata's Postgres and OpenSearch). Gap: medallion bronze/silver/gold still writes CSV/XLSX files under `/srv/lendatagovernance/medallion`.
