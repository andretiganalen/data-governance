# Len Data Governance — dev-data.len.co.id

Compose project `lendatagovernance` (live: `/opt/lendatagovernance/deploy`, data: `/srv/lendatagovernance`). Deploys OpenMetadata 2.0.7 on server jitsi (192.168.125.14). Follows `plan/openmetadata_deployment_plan.md`.

| URL | What |
|---|---|
| http://dev-data.len.co.id | Landing page → "Masuk dengan IDS" → OpenMetadata (via gateway :80) |
| http://192.168.125.14:8585 | OpenMetadata via the same gateway (LenO theme applied) |
| http://127.0.0.1:8586/healthcheck | Admin/health (server-local only) |
| http://192.168.125.14:8585/visualisasi/ | Visualisasi Gold — Apache Superset 6, menu *Visualisasi* di sidebar OpenMetadata (tidak ada port terpisah) |

| Path | Content |
|---|---|
| `compose.yaml` | postgresql 15, opensearch 3.2.0, migrate, openmetadata-server, superset 6.0.0 (internal), gateway (nginx :80, :8585) |
| `openmetadata.base.env` | Non-secret settings (git) |
| `/srv/lendatagovernance/secrets/` | DB passwords, Fernet key, JWT keys, IDS client (NOT in git — back up to vault) |
| `/srv/lendatagovernance/{postgres,opensearch,backup}` | Data |

## Operate
```bash
cd ~/data-governance/deploy/lendatagovernance
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
echo 'OM_TOKEN=<paste token>' > /srv/lendatagovernance/secrets/loader.env && chmod 600 /srv/lendatagovernance/secrets/loader.env
```
```bash
cd /opt/lendatagovernance/deploy/loader
WB="/home/ubuntu/data-governance/templates/261016 Rev.0.1_Data Governance_ERM.xlsx"
./om_loader.py workbook "$WB" --dry-run   # preview, no writes
./om_loader.py workbook "$WB"             # load everything (idempotent, safe to re-run)
```
Loads: teams Direktorat › Divisi › Unit Kerja, classification Sensitivitas, glossary ERM (1 term per Elemen Data,
reviewers = Data Steward, owner = Data Owner, property Data User), service LenO ERM › ERM › erm › 18 tables
(column tags: sensitivity + glossary term), 19 LenO screens (dashboard + data model, property *Hak Akses LenO*),
column lineage table → screen, DQ test-case definitions (not executed), DG-* → policy/role for the team.
Defect report → `/srv/lendatagovernance/reports/workbook-defects-<date>.md` (outside git — repo is public).

After UG-1/UV-1 fix the workbook: `scripts/reload-workbook.sh [file.xlsx]` reloads and lists closed/new defects.

## Lakehouse Trino — Bronze → Silver → Gold (`medallion/lakehouse.py`)
Aturan proyek: semua data aplikasi tinggal di Trino lakehouse `lakekeeper.medallion_repository`
(`jdbc:trino://datahub.len.co.id:443`). Kredensial hanya di `/srv/lendatagovernance/secrets/trino.env`:
`TRINO_HOST, TRINO_PORT, TRINO_USER, TRINO_PASSWORD, TRINO_CATALOG=lakekeeper, TRINO_SCHEMA=medallion_repository`.

| Lapisan | Tabel | Cara isi |
|---|---|---|
| Bronze | `bronze_repository` (1 baris per sheet per berkas), `bronze_<sumber>_<sheet>` (baris mentah, varchar), `bronze_meta_quarantine` (header tak dikenal) | append; berkas dengan checksum sama dilewati |
| Silver | `silver_dim_*`, `silver_fact_*` (bersih, bertipe, kolom lineage `_file_id … _loaded_at`) | dibangun ulang dari berkas terbaru tiap sumber |
| Gold | `gold_erm_*` (risiko), `gold_meta_*` (tata kelola), `*_snapshot` = riwayat harian | dibangun ulang; snapshot per hari |

Skema = `medallion/schema/medallion_repository.sql` (sumber kebenaran; kerangka asli 2026-11-02 di `schema/skeleton_20261102.sql`).
Sumber dikenali otomatis: workbook tata kelola (`DG_WORKBOOK`) dan Sumber Data E-GRC (`EGRC`); berkas lain → Bronze saja (`FILE`).

```bash
python3 -m venv /srv/lendatagovernance/medallion/.venv && /srv/lendatagovernance/medallion/.venv/bin/pip install trino openpyxl  # sekali
PY=/srv/lendatagovernance/medallion/.venv/bin/python; LH=/opt/lendatagovernance/deploy/medallion/lakehouse.py
$PY $LH ingest "<berkas.xlsx>"     # unggah → Bronze → Silver → Gold
$PY $LH retry                      # lengkapi Bronze berstatus PARTIAL (tabel mentah yang tertunda)
$PY $LH rebuild                    # bangun ulang Silver/Gold dari berkas terbaru
$PY $LH status                     # jumlah baris + snapshot terakhir tiap tabel (pembanding DBeaver)
```
Inbox otomatis: letakkan berkas di `/srv/lendatagovernance/medallion/inbox/`; timer
`host/systemd/lendatagovernance-lakehouse-inbox.timer` (tiap 10 menit) memuatnya lalu memindahkan ke `inbox/selesai/`.
Pasang: `sudo cp host/systemd/lendatagovernance-lakehouse-inbox.* /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now lendatagovernance-lakehouse-inbox.timer`.
Penyuntingan langsung di tabel `silver_*`/`gold_*` akan tertimpa pada pemuatan berikutnya — perbaiki di sumber lalu unggah ulang.

## Visualisasi Gold — Apache Superset (`superset/`)
Image `lendatagovernance/superset:6.0.0-dg1` (driver Trino + Postgres, tema & palet Len), berjalan di subpath `/visualisasi` (`SUPERSET_APP_ROOT`) di belakang gateway :8585 — port 8088 tidak dibuka. Menu *Visualisasi* di sidebar OpenMetadata disisipkan oleh `ui/leno-theme/leno-menu.js`. Metadata Superset (pengguna, grafik,
dashboard) di database `superset` pada Postgres stack ini; **data** dibaca dari Trino (koneksi hanya baca, `allow_dml` mati).
Rahasia: `/srv/lendatagovernance/secrets/superset.env` (`SUPERSET_SECRET_KEY`, `SUPERSET_DB_PASSWORD`, `SUPERSET_ADMIN_*`).
```bash
docker compose build superset && docker compose up -d superset && docker compose up -d --force-recreate gateway   # nginx.conf adalah bind-mount berkas: rsync → gateway harus dibuat ulang
/srv/lendatagovernance/medallion/.venv/bin/python scripts/superset-setup.py           # koneksi + dataset + 2 dashboard awal
/srv/lendatagovernance/medallion/.venv/bin/python scripts/superset-setup.py --force   # buat ulang dashboard awal
```
Dashboard awal: `:8585/visualisasi/superset/dashboard/risiko-erm/` dan `:8585/visualisasi/superset/dashboard/tata-kelola-data/`. Skrip setup memakai admin awal atau akun Anda: `SUPERSET_USER=… SUPERSET_PASSWORD=…`. Admin membuat grafik sendiri lewat
**Charts › + Chart** (tren waktu, histogram, donut, heatmap, dll.) atau **SQL Lab**.
