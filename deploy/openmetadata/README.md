# OpenMetadata — dev-data.len.co.id

Deploys OpenMetadata 2.0.7 on server jitsi (192.168.125.14). Follows `plan/openmetadata_deployment_plan.md`.

| URL | What |
|---|---|
| http://dev-data.len.co.id | Landing page → "Masuk dengan IDS" → OpenMetadata (via gateway :80) |
| http://192.168.125.14:8585 | OpenMetadata direct |
| http://127.0.0.1:8586/healthcheck | Admin/health (server-local only) |

| Path | Content |
|---|---|
| `compose.yaml` | postgresql 15, opensearch 3.2.0, migrate, openmetadata-server, gateway (nginx) |
| `openmetadata.base.env` | Non-secret settings (git) |
| `/srv/openmetadata/secrets/` | DB passwords, Fernet key, JWT keys, IDS client (NOT in git — back up to vault) |
| `/srv/openmetadata/{postgres,opensearch,backup}` | Data |

## Operate
```bash
cd ~/data-governance/deploy/openmetadata
./scripts/secrets-init.sh            # once
docker compose up -d                 # start / apply changes
./scripts/verify.sh                  # status
docker compose logs -f openmetadata-server
./scripts/backup.sh                  # manual backup (timer runs 01:30 daily)
docker compose down                  # stop (data kept)
```

## Switch login to IDS (phase 2)
1. Ask IDS team for a **confidential** client: redirect `http://dev-data.len.co.id/callback`,
   post-logout `http://dev-data.len.co.id/`, scopes `openid email profile`, claims `email name preferred_username`.
2. `./scripts/enable-ids.sh <client_id> <client_secret>`

## DNS
`dev-data.len.co.id` needs an internal A record → `192.168.125.14` (network team).
Until then, on each Windows PC add to `C:\Windows\System32\drivers\etc\hosts`:
`192.168.125.14  dev-data.len.co.id`

## Phase 3 loader (`loader/`, Python stdlib only)
Needs an **admin** Personal Access Token (creates teams, roles, policies, custom properties):
OpenMetadata → profile (top right) › **Access Token** › Generate. Then on the server:
```bash
echo 'OM_TOKEN=<paste token>' > /srv/openmetadata/secrets/loader.env && chmod 600 /srv/openmetadata/secrets/loader.env
```
```bash
cd /opt/openmetadata/deploy/loader
WB="/home/ubuntu/data-governance/templates/261016 Rev.0.1_Data Governance_ERM.xlsx"
./om_loader.py workbook "$WB" --dry-run   # preview, no writes
./om_loader.py workbook "$WB"             # load everything (idempotent, safe to re-run)
```
Loads: teams Direktorat › Divisi › Unit Kerja, classification Sensitivitas, glossary ERM (1 term per Elemen Data,
reviewers = Data Steward, owner = Data Owner, property Data User), service LenO ERM › ERM › erm › 18 tables
(column tags: sensitivity + glossary term), 19 LenO screens (dashboard + data model, property *Hak Akses LenO*),
column lineage table → screen, DQ test-case definitions (not executed), DG-* → policy/role for the team.
Defect report → `/srv/openmetadata/reports/workbook-defects-<date>.md` (outside git — repo is public).

After UG-1/UV-1 fix the workbook: `scripts/reload-workbook.sh [file.xlsx]` reloads and lists closed/new defects.
