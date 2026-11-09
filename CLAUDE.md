# DG workspace — notes for coding agents

- OpenMetadata deploy lives in `deploy/lendatagovernance` (live copy: `/opt/lendatagovernance/deploy`, data: `/srv/lendatagovernance`). Plan: `plan/openmetadata_deployment_plan.md`.
- UI default for every web app: `plan/interface-menu.md` (Len classic: colours, fonts, borders, menu from len.co.id). Positions: `plan/leno_interface_theme.md`.
- The DG Projects app (apps/web, packages/*) was removed on 2026-11-05; recover it from git history if ever needed.
- Data rule (2026-11-09, Andre Tigana): every database/dataset used by an app must live in the Trino lakehouse. Apps read and write their business data through Trino; no separate app databases, local files or CSV/XLSX stores as the system of record. Exception: a platform's own internal store that Trino cannot host (e.g. OpenMetadata's and Superset's Postgres, OpenSearch).
- Lakehouse: `lakekeeper.medallion_repository` on Trino `datahub.len.co.id:443`; table definitions in `deploy/lendatagovernance/medallion/schema/medallion_repository.sql` (source of truth, English skeleton naming), loader `medallion/lakehouse.py` (ingest/inbox/retry/rebuild/status). Credentials only in `/srv/lendatagovernance/secrets/trino.env` — never commit them (GitHub remote is public). Remaining gap: the old `/unduh/` panel still serves CSV/XLSX files from `build_medallion.py`.
- Superset (Gold dashboards) at `:8088` via the gateway; setup `scripts/superset-setup.py`. Reply to the user in Bahasa Indonesia.
