# Len Data Governance — dev-data.len.co.id

Compose project `lendatagovernance` (live: `/opt/lendatagovernance/deploy`, data: `/srv/lendatagovernance`). Deploys Len Data Governance on server jitsi (192.168.125.14). Follows `plan/lendatagovernance_deployment_plan.md`.

**Data rule:** every dataset the app uses lives only in the Trino lakehouse `lakekeeper.medallion_repository`.
Raw CSV/XLSX files are Bronze input (inbox) before ETL, never a store users read from. Postgres/OpenSearch below hold
only the platform's own internal state. The catalog server runs the upstream open-source image
`docker.getcollate.io/openmetadata/server:2.0.7`; that image name, its in-image paths and env-variable keys are fixed
upstream — everything else carries the Len Data Governance name.

| URL | What |
|---|---|
| http://dev-data.len.co.id | Landing page → "Masuk dengan IDS" → Len Data Governance (via gateway :80) |
| http://192.168.125.14:8585 | Len Data Governance via the same gateway (LenO theme applied) |
| http://127.0.0.1:8586/healthcheck | Admin/health (server-local only) |
| http://192.168.125.14:8585 › menu **Visualisasi** | Dashboard Gold di dalam aplikasi utama (tab Risiko ERM · Tata Kelola Data · Semua dashboard · Grafik · SQL Lab); login = sesi Len Data Governance |

| Path | Content |
|---|---|
| `compose.yaml` | postgresql 15 (`lendatagovernance_db`, `superset`), opensearch 3.4.0, ldg-migrate, ldg-server, superset 6.0.0 (internal), gateway (nginx :80, :8585) |
| `lendatagovernance.base.env` | Non-secret settings (git); secrets in `/srv/lendatagovernance/secrets/lendatagovernance.env` |
| `/srv/lendatagovernance/secrets/` | DB passwords, Fernet key, JWT keys, IDS client (NOT in git — back up to vault) |
| `/srv/lendatagovernance/{postgres,opensearch,backup}` | Data |

## Operate
```bash
cd ~/data-governance/deploy/lendatagovernance
./scripts/secrets-init.sh            # once
docker compose up -d                 # start / apply changes
./scripts/verify.sh                  # status
docker compose logs -f ldg-server
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
Len Data Governance → profile (top right) › **Access Token** › Generate. Then on the server:
```bash
echo 'LDG_TOKEN=<paste token>' > /srv/lendatagovernance/secrets/loader.env && chmod 600 /srv/lendatagovernance/secrets/loader.env
```
```bash
cd /opt/lendatagovernance/deploy/loader
WB="/home/ubuntu/data-governance/templates/261016 Rev.0.1_Data Governance_ERM.xlsx"
PY=/srv/lendatagovernance/medallion/.venv/bin/python
$PY catalog_loader.py workbook "$WB" --dry-run   # preview, no writes
$PY catalog_loader.py workbook "$WB"             # load everything (idempotent, safe to re-run)
$PY catalog_trino.py                            # sync catalog ↔ Trino (also runs after every lakehouse load)
```
Loads: teams Direktorat › Divisi › Unit Kerja, classification Sensitivitas, glossary ERM (1 term per Elemen Data,
reviewers = Data Steward, owner = Data Owner, property Data User), the 18 LenO ERM tables (sheet Database_Object)
mapped onto their Trino tables in `len_lakehouse_trino › lakekeeper › medallion_repository` (`workbook.TABLE_MAP`,
columns matched by element code F0xx in the column comments: description, owners, column tags sensitivity + glossary
term), 19 LenO screens (dashboard service *LenO ERM*: dashboard + data model, property *Hak Akses LenO*), column
lineage Trino table → screen, DQ test-case definitions (not executed), DG-* → policy/role for the team.
`catalog_trino.py` keeps this workbook metadata when it re-syncs tables from Trino. The former separate
CustomDatabase service *LenO ERM* is removed by the loader.
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

Data ERM lama dari schema `lakekeeper.erm`, `erm_bronze`, `erm_silver` disalin ke `medallion_repository` (2026-11-10,
`medallion/migrate_legacy_erm.py`): `bronze_erm_*`, `silver_dim_erm_risk_{level,score}_matrix`, `silver_dim_erm_risk_level_reference`,
`silver_fact_erm_risk_{control,profile,register}_monthly`, `silver_fact_erm_risk_strategy_matrix`, view `gold_erm_iro_*`.
Schema lama dihapus dengan `migrate_legacy_erm.py` (tanpa `--keep-source`) setelah salinan diverifikasi.

Panel unduhan berkas `/unduh/` (rilis CSV/XLSX) ditutup 2026-11-10: data Gold dibaca dari Trino (menu Visualisasi, DBeaver).

**Sumber lain (rebuild, SQL di Trino):**
- `medallion/leno_erm.py` — Aplikasi ERM LenO dari katalog Trino `lenodb.silver` (replika CDC): snapshot Bronze `bronze_leno_*`,
  lalu Silver/Gold ERM dengan `_source_system = LENO_ERM` (perusahaan COMP-LEN-001; unit kerja `hr_unitkerja.kodeuk` = ORG_ID).
  Baris EGRC dan LENO_ERM hidup berdampingan; tiap sumber hanya mengganti barisnya sendiri.
- `medallion/sdm.py` — kerangka SDM + korporasi: Bronze `bronze_sdm_*`/`bronze_corp_*` (dipindah dari prototipe `lakekeeper.medallion`
  oleh `migrate_legacy_medallion.py`, schema lama dihapus 2026-11-10) → `silver_dim_company_information`, `silver_dim_sdm_employee`,
  `silver_fact_sdm_certification`, `silver_fact_corp_{investment,tax}_monthly` → `gold_sdm_*`. Kolom pribadi ditandai
  `Sensitivitas: …` di komentar; `catalog_trino.py` memasang tag Sensitivitas-nya.
- `medallion/nextcloud_sync.py` + `medallion/astacita.py` — program Task Force Asta Cita dari Nextcloud `sharedrive.len.co.id`
  folder `DBASTACITA` (WebDAV, app password dari Login Flow v2 di `secrets/nextcloud.env`): spreadsheet baru/berubah (ETag) →
  inbox → Bronze `bronze_file_dbastacita_*` → `silver_dim_astacita_{theme,program,manpower}`, `silver_fact_astacita_*`
  (kurva S, output, kendala, kegiatan, skor prioritas AHP) → `gold_astacita_*`. Berkas utama `DBASTACITA/DBASTACITA.xlsx`
  (versi terbaru di Bronze). Kunci = tema bidang (`astacita.THEMES`), bukan nomor "Asta Cita N" (beda antar sheet).
  Timer inbox menjalankan sinkron Nextcloud tiap 10 menit (`ExecStartPre`); berkas baru memicu rebuild.
- `medallion/leno_sdm.py` — kepegawaian Aplikasi LenO (`lenodb.silver.ps_karyawan`, `ps_statusbarukaryawan`, `ps_ukkaryawan`,
  ringkasan absensi terakhir): Bronze hanya kolom yang diperlukan (tanpa KTP/paspor/NPWP/PIN) → `silver_dim_sdm_employee`
  (`LENO_SDM`), `silver_fact_sdm_employment_status` (rentang berlaku + `end_date_basis`), `silver_fact_sdm_unit_assignment` →
  **`gold_sdm_headcount_monthly`** (posisi akhir bulan sejak Jan 2024: unit × gender × Kontrak/Non Kontrak × status × kelompok umur,
  jumlah orang + umur min/maks/rata-rata). Kelompok status: `reference/sdm_status_kepegawaian.csv` (koreksi oleh Unit HC).
  Pegawai `aktif = 0` yang statusnya tak pernah ditutup diakhiri pada absensi terakhir (perkiraan) atau perubahan data terakhir.
  Contoh: `SELECT contract_flag, sum(headcount), min(age_min), max(age_max) FROM gold_sdm_headcount_monthly WHERE period_year = 2026
  AND period_month = 10 AND gender = 'Perempuan' AND contract_flag IN ('Kontrak','Non Kontrak') AND is_active GROUP BY 1`.
- Urutan `lakehouse.py rebuild`: SDM/korporasi → berkas Workbook/E-GRC → ERM LenO → SDM LenO → Asta Cita → sinkron katalog.

## Visualisasi — di dalam aplikasi utama (`superset/`, `../ui/leno-theme/leno-menu.js`)
Pengguna hanya melihat Len Data Governance (:8585). Menu **Visualisasi** di sidebar membuka panel di area konten
(header & sidebar tetap) berisi dashboard Gold. Mesinnya Apache Superset 6 (`lendatagovernance/superset:6.0.0-dg2`,
`SUPERSET_APP_ROOT=/visualisasi`) di belakang gateway; tidak ada port terpisah. Satu-satunya koneksi: Trino lakehouse.

- **Tanpa kredensial baru (SSO):** `leno-menu.js` meneruskan token sesi Len Data Governance ke cookie `dg_token`
  (path `/visualisasi`); `superset/dg_sso.py` memverifikasinya ke API Len Data Governance (`/api/v1/users/loggedInUser`).
  Admin → Admin Visualisasi; pengguna lain → Gamma + sql_lab (lihat semua dataset, membuat grafik, SQL Lab, unggah
  berkas). Logout/token berganti → sesi Visualisasi berakhir. Login kata sandi Superset dimatikan.
- **Hanya Trino, semua pengguna bisa membuat tabel:** koneksi selain `trino://` ditolak (buat/ubah/uji). Pernyataan tulis
  (CREATE/CTAS/INSERT/UPDATE/DELETE/DROP/ALTER/MERGE) dan unggah CSV/XLSX hanya ke schema `lakekeeper.workspace`
  — tulis lengkap `workspace.<tabel>`; schema lain (termasuk `medallion_repository` milik loader) ditolak
  (`dg_sql_guard`, `SQL_QUERY_MUTATOR`).
- **Tema:** `leno-superset.css` (font Montserrat/Open Sans, navy/merah Len, kartu 4px) + `THEME_DEFAULT` Superset;
  menu atas Superset disembunyikan saat tampil di dalam aplikasi (`leno-superset.js`).
- Metadata Superset (grafik, dashboard) di database `superset` pada Postgres stack ini. Rahasia: `secrets/superset.env`
  (`SUPERSET_SECRET_KEY`, `SUPERSET_DB_PASSWORD`).
```bash
docker compose build superset && docker compose up -d superset && docker compose up -d --force-recreate gateway   # nginx.conf = bind-mount berkas
/srv/lendatagovernance/medallion/.venv/bin/python scripts/superset-setup.py           # koneksi + dataset + 2 dashboard (login SSO via LDG_TOKEN)
/srv/lendatagovernance/medallion/.venv/bin/python scripts/superset-setup.py --force   # buat ulang dashboard awal
```
