// SRS Len Data Governance → PDF (HTML bergaya Len → Chrome headless lewat ../build-pdf.mjs; tanpa dependensi npm).
// Pemakaian: node docs/manuals/src/srs/build-srs-pdf.js "<YYMMDD CC>" [folder keluaran]
// 50 use case: 25 Dasar (pemakaian harian lewat antarmuka) + 25 Lanjutan (administrasi, otomasi, integrasi, operasi).
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { UC, AKTOR } = require("./usecases");
const { FR, NFR } = require("./requirements");

const REL = process.argv[2] || "261110 03";
const OUTDIR = path.resolve(process.argv[3] || path.join(__dirname, "..", ".."));
const SRC = path.join(__dirname, "..");

// ---- pemilihan dan pengelompokan 50 use case (id lama dari usecases.js → id baru)
const DASAR = ["UC-01", "UC-02", "UC-03", "UC-07", "UC-08", "UC-09", "UC-10", "UC-11", "UC-12", "UC-13", "UC-14", "UC-15", "UC-16",
  "UC-18", "UC-19", "UC-23", "UC-24", "UC-38", "UC-39", "UC-40", "UC-41", "UC-42", "UC-43", "UC-44", "UC-45"];
const LANJUT = ["UC-04", "UC-05", "UC-06", "UC-17", "UC-25", "UC-26", "UC-28", "UC-29", "UC-32", "UC-33", "UC-34", "UC-36", "UC-46",
  "UC-47", "UC-48", "UC-50", "UC-51", "UC-52", "UC-53", "UC-54", "UC-55", "UC-56", "UC-57", "UC-58", "UC-60"];
// use case yang dilebur ke use case lain (isi alurnya masuk ke sana)
const LEBUR = {
  "UC-20": ["UC-16", "Hak akses layar LenO (properti referensi Unit Kerja × Kategori × Izin) terlihat pada dashboard layar."],
  "UC-21": ["UC-09", "Pengguna dapat memilih Follow agar perubahan aset muncul di activity feed."],
  "UC-22": ["UC-23", "Pengguna juga dapat berdiskusi langsung di aset dan menyebut (@) unit terkait."],
  "UC-27": ["UC-25", "Bronze berstatus PARTIAL dilengkapi per sheet dengan lakehouse.py retry."],
  "UC-30": ["UC-25", "Sumber dikenali otomatis (DG_WORKBOOK, EGRC, FILE); header asing masuk bronze_meta_quarantine."],
  "UC-31": ["UC-25", "Berkas dengan checksum yang sama tidak dimuat dua kali."],
  "UC-35": ["UC-60", "scripts/reload-workbook.sh memuat ulang dan menampilkan cacat yang tertutup dan yang baru."],
  "UC-37": ["UC-28", "Tabel *_snapshot menyimpan riwayat harian (baris hari ini diganti, hari sebelumnya dipertahankan)."],
  "UC-49": ["UC-44", "Hasil query/grafik dapat diunduh sebagai CSV untuk keperluan sesaat; sistem rekam tetap Trino."],
  "UC-59": ["UC-55", "Tema LenO (leno.css, leno-superset.css, leno-menu.js) diperiksa setelah upgrade; teks merek upstream diganti di peramban."],
};
const byId = Object.fromEntries(UC.map((u) => [u.id, u]));
const map = {};
DASAR.forEach((o, i) => (map[o] = `UC-D${String(i + 1).padStart(2, "0")}`));
LANJUT.forEach((o, i) => (map[o] = `UC-L${String(i + 1).padStart(2, "0")}`));
const fix = (s) => s.replace(/UC-\d\d/g, (m) => map[m] || (LEBUR[m] ? map[LEBUR[m][0]] : m));
const sel = [...DASAR, ...LANJUT].map((o) => {
  const u = byId[o];
  const merged = Object.entries(LEBUR).filter(([, [to]]) => to === o);
  const extra = merged.map(([, [, txt]]) => txt);
  const fr = [...new Set([...u.fr, ...merged.flatMap(([from]) => byId[from].fr)])].sort();
  return { ...u, id: map[o], level: DASAR.includes(o) ? "Dasar" : "Lanjutan", asal: o,
    utama: u.utama.map(fix), alt: [...u.alt.map(fix), ...extra.map((x) => "Termasuk: " + x)], pemicu: fix(u.pemicu), pra: u.pra.map(fix), pasca: fix(u.pasca), fr };
});
if (sel.length !== 50 || new Set(sel.map((u) => u.asal)).size !== 50) throw new Error("harus tepat 50 use case unik");

const ucByFr = {};
sel.forEach((u) => u.fr.forEach((f) => (ucByFr[f] = (ucByFr[f] || []).concat(u.id))));
const e = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const tbl = (head, rows, cls = "") => `<table class="${cls}"><thead><tr>${head.map((h) => `<th>${e(h)}</th>`).join("")}</tr></thead><tbody>${
  rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
const ul = (a) => (a.length ? `<ul>${a.map((x) => `<li>${e(x)}</li>`).join("")}</ul>` : "—");
const ol = (a) => `<ol>${a.map((x) => `<li>${e(x)}</li>`).join("")}</ol>`;
const chip = (l) => `<span class="chip ${l === "Dasar" ? "ok" : "info"}">${l}</span>`;
const st = (s) => `<span class="chip ${s === "Tersedia" ? "ok" : "no"}">${s}</span>`;

const GRUP = { A: "Akses dan identitas", B: "Katalog dan tata kelola metadata", C: "Lakehouse dan pemuat data", D: "Visualisasi dan analitik", E: "Operasi dan pemeliharaan" };

function ucCard(u) {
  return `<div class="uc keep"><div class="uh"><b>${u.id}</b> ${e(u.nama)} ${chip(u.level)} ${st(u.status)}</div>
  <table class="kv"><tbody>
  <tr><th>Aktor</th><td>${e(u.aktor.join("; "))}</td></tr>
  <tr><th>Tujuan</th><td>${e(u.tujuan)}</td></tr>
  <tr><th>Prioritas · Kelompok</th><td>${u.prioritas} · ${GRUP[u.grup]}</td></tr>
  <tr><th>Prasyarat</th><td>${ul(u.pra)}</td></tr>
  <tr><th>Pemicu</th><td>${e(u.pemicu)}</td></tr>
  <tr><th>Alur utama</th><td>${ol(u.utama)}</td></tr>
  <tr><th>Alur alternatif / eksepsi</th><td>${ul(u.alt)}</td></tr>
  <tr><th>Pascakondisi</th><td>${e(u.pasca)}</td></tr>
  <tr><th>Kebutuhan</th><td>${u.fr.join(", ")}</td></tr>
  </tbody></table></div>`;
}

const D = sel.filter((u) => u.level === "Dasar"), L = sel.filter((u) => u.level === "Lanjutan");
const comp = { Autentikasi: "ldg-server, gateway, dg_sso.py", Otorisasi: "ldg-server, catalog_loader.py", Katalog: "ldg-server, catalog_trino.py", Glosarium: "ldg-server", Kepemilikan: "ldg-server", Klasifikasi: "ldg-server", Lineage: "ldg-server, catalog_loader.py", "Mutu data": "ldg-server", Referensi: "ldg-server", Kolaborasi: "ldg-server", "Katalog ERM": "workbook.py, catalog_loader.py", Pemuat: "catalog_loader.py", Lakehouse: "lakehouse.py, Trino", Visualisasi: "superset, leno-menu.js", "Aturan data": "dg_sso.py", Operasi: "scripts/*, systemd", Dokumentasi: "rilis.py, srs/", Keamanan: "secrets-init.sh", Antarmuka: "leno-theme, gateway" };
const ver = { Lakehouse: "lakehouse.py status vs DBeaver", "Aturan data": "Uji SQL Lab / uji koneksi (HTTP 422)", Visualisasi: "Uji UI :8585/visualisasi/", Operasi: "verify.sh, restore uji" };

const logo = "img/len-logo.png";
const html = `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>SRS Len Data Governance ${REL}</title>
<link rel="stylesheet" href="base.css"><style>
.cover{background:#fff}.cover .band{position:absolute;inset:0 0 auto 0;height:118mm;background:var(--navy)}
.cover img{position:absolute;left:20mm;top:18mm;height:15mm;background:#fff;padding:2mm 3mm}
.cover .t{position:absolute;left:20mm;right:20mm;top:56mm;color:#fff}.cover .t .k{font:600 11pt 'Open Sans';letter-spacing:.5px;opacity:.85}
.cover .t h1{color:#fff;font-size:32pt;margin:4mm 0 3mm;letter-spacing:-.6px}.cover .t p{font-size:12.5pt;margin:0;max-width:160mm;opacity:.95}
.cover .qs{position:absolute;left:20mm;right:20mm;top:132mm;display:grid;grid-template-columns:1fr 1fr;gap:5mm 8mm}
.cover .qs div{border-left:3px solid var(--red);padding:1mm 0 1mm 4mm;font-size:10.5pt;color:var(--ink)}.cover .qs b{display:block;font-size:20pt;color:var(--navy)}
.cover .meta{position:absolute;left:20mm;right:20mm;bottom:18mm;font-size:9pt;color:var(--muted)}
h1{font-size:18pt;color:var(--navy);border-bottom:2px solid var(--red);padding-bottom:2mm;margin:0 0 4mm}
h2{font-size:12.5pt;color:var(--navy);margin:6mm 0 2mm}h3{font-size:10.5pt;margin:4mm 0 2mm}
table{font-size:8.6pt;margin:2mm 0 4mm}th,td{border:1px solid var(--soft);padding:1.4mm 2mm;vertical-align:top;text-align:left}
thead th{background:var(--navy);color:#fff;font-weight:600}td:first-child{white-space:nowrap}.uc table.kv td:first-child{white-space:normal}tbody tr:nth-child(even) td{background:#f7f9fc}
td ul,td ol{margin:0;padding-left:4.5mm}td li{margin:0 0 .6mm}
.uc{border:1px solid var(--line);border-top:3px solid var(--navy);margin:0 0 5mm}.uc .uh{background:var(--navy50);padding:2mm 3mm;font-weight:600;color:var(--ink);font-size:10pt}
.uc .uh b{color:var(--red);margin-right:1.5mm}.uc .uh .chip{margin-left:1mm;font-size:7pt}
.uc table.kv{margin:0}.uc table.kv th{width:36mm;background:#fafbfd;color:var(--ink);font-weight:600}.uc table.kv td,.uc table.kv th{border:0;border-top:1px solid var(--soft)}
.toc{columns:2;column-gap:10mm;font-size:9.5pt}.toc div{break-inside:avoid;margin:0 0 1.2mm}.toc a{color:var(--ink);text-decoration:none}.toc .s{padding-left:5mm;color:var(--text2)}
.note{background:var(--navy50);border-left:3px solid var(--navy);padding:2.5mm 4mm;margin:3mm 0;font-size:9.3pt}
.lv{display:grid;grid-template-columns:1fr 1fr;gap:5mm;margin:3mm 0}.lv div{border:1px solid var(--line);padding:3mm 4mm}.lv h3{margin-top:0}
</style></head><body>
<section class="cover"><div class="band"></div><img src="${logo}" alt="Len">
<div class="t"><div class="k">SOFTWARE REQUIREMENTS SPECIFICATION · ${REL}</div><h1>Len Data Governance</h1>
<p>Katalog metadata, Trino lakehouse Medallion, dan Visualisasi untuk tata kelola data ERM Len (holding DEFEND ID)</p></div>
<div class="qs"><div><b>50</b>use case — 25 Dasar, 25 Lanjutan</div><div><b>${FR.length}</b>kebutuhan fungsional</div>
<div><b>${NFR.length}</b>kebutuhan non-fungsional</div><div><b>1</b>sistem rekam data: Trino lakehouse</div></div>
<div class="meta">Nomor SRS-LDG ${REL} · Versi 1.1 · 10 November 2026 · Klasifikasi: Internal · Acuan struktur ISO/IEC/IEEE 29148:2018<br>
Pemilik: Data Governance (UV-1) · Administrator (UV-3) · Server dev jitsi 192.168.125.14 / dev-data.len.co.id</div></section>

<h1>Daftar isi</h1><div class="toc">
${["1|Pendahuluan", "2|Deskripsi umum", "3|Kebutuhan fungsional", "4|Kebutuhan non-fungsional dan antarmuka", "5|Kebutuhan data", "6|Use case — ringkasan",
  "7|Use case Dasar (UC-D01 … UC-D25)", "8|Use case Lanjutan (UC-L01 … UC-L25)", "9|Matriks keterlacakan", "10|Kriteria penerimaan", "11|Isu terbuka dan risiko", "A|Lampiran: aktor × use case", "B|Lampiran: riwayat revisi"]
  .map((x) => { const [n, t] = x.split("|"); return `<div><a href="#s${n}"><b>${n}.</b> ${t}</a></div>`; }).join("")}</div>
<div class="note">Dokumen ini menggantikan versi .docx 261110 02 (60 use case). Use case kini dikelompokkan menjadi <b>Dasar</b> (pemakaian harian lewat antarmuka oleh pengguna bisnis) dan <b>Lanjutan</b> (administrasi, otomasi, integrasi, dan operasi). Sepuluh use case yang tumpang tindih dilebur ke use case terkait (ditandai "Termasuk:" pada alur alternatif).</div>

<h1 id="s1" class="pb">1. Pendahuluan</h1>
<h2>1.1 Tujuan</h2><p>Dokumen ini menetapkan kebutuhan perangkat lunak Len Data Governance: apa yang harus dilakukan sistem, untuk siapa, dengan batasan apa, dan cara memverifikasinya. Dokumen menjadi acuan bersama Staf Data Governance, Data Owner, Administrator, pengembang, dan Pimpinan untuk pengembangan, pengujian penerimaan, dan audit.</p>
<h2>1.2 Ruang lingkup</h2><ul>
<li><b>Katalog metadata</b>: glosarium bisnis, klasifikasi sensitivitas, kepemilikan, lineage, definisi mutu data, hak tata kelola.</li>
<li><b>Trino lakehouse</b> <code>lakekeeper.medallion_repository</code> (Iceberg/Lakekeeper, datahub.len.co.id:443): satu-satunya sistem rekam data bisnis, berlapis Bronze → Silver → Gold.</li>
<li><b>Visualisasi</b> (Superset 6) di dalam aplikasi: dashboard, grafik, SQL Lab, tabel kerja pengguna di <code>lakekeeper.workspace</code>.</li>
<li><b>Operasi</b>: backup, pemulihan, upgrade, indeks pencarian, rilis dokumen.</li></ul>
<p>Di luar cakupan: aplikasi transaksi ERM LenO (layarnya hanya direpresentasikan sebagai referensi lineage dan hak akses) dan sistem sumber E-GRC.</p>
<h2>1.3 Definisi dan singkatan</h2>${tbl(["Istilah", "Arti"], [
  ["Bronze / Silver / Gold", "Lapisan Medallion: mentah apa adanya / bersih bertipe (dim, fact) / siap dashboard."],
  ["Trino lakehouse", "Mesin SQL Trino atas katalog Iceberg lakekeeper; schema medallion_repository (data resmi) dan workspace (tabel kerja pengguna)."],
  ["Workbook Governance", "Excel Rev.0.1 Data Governance ERM: organisasi, glosarium, elemen data, objek database, lineage, mutu, hak akses."],
  ["E-GRC", "Sumber Data E-GRC (Excel): risk register, profil risiko, pengendalian, matriks."],
  ["Elemen Data (F0xx)", "Kode elemen data workbook; dicantumkan di komentar kolom Trino untuk keterlacakan."],
  ["LenO ERM", "Aplikasi ERM di platform LenO; 18 tabel dan 19 layarnya menjadi referensi metadata."],
  ["UG-1, UV-1, UV-3", "Unit kerja: Data Owner bisnis, Data Governance, Administrator TI."],
  ["Use case Dasar", "Pemakaian harian lewat antarmuka oleh pengguna bisnis; tidak perlu akses server."],
  ["Use case Lanjutan", "Administrasi, otomasi, integrasi, dan operasi; umumnya oleh Admin/Staf atau proses sistem."],
  ["Server katalog", "Komponen ldg-server (image open-source upstream 2.0.7) yang menyediakan UI dan API katalog."],
].map((r) => r.map(e)))}
<h2>1.4 Referensi</h2><ul><li>plan/lendatagovernance_deployment_plan.md — rencana deployment dan fase.</li>
<li>docs/adr/pm-0001-application-stack.md, docs/adr/dg-0002-medallion-penamaan-field-id.md.</li>
<li>deploy/lendatagovernance/medallion/schema/medallion_repository.sql — definisi tabel lakehouse.</li>
<li>plan/interface-menu.md, plan/leno_interface_theme.md — standar antarmuka Len classic.</li>
<li>Manual Pengembang, Manual Staf Data Governance dan Pimpinan, Manual Pengguna (docs/manuals).</li></ul>

<h1 id="s2" class="pb">2. Deskripsi umum</h1>
<h2>2.1 Perspektif produk</h2><p>Len Data Governance menggantikan pengelolaan metadata ERM berbasis berkas dengan satu pintu masuk web. Semua data bisnis berada di Trino lakehouse; aplikasi hanya menyimpan status internal platform (metadata katalog dan Superset di PostgreSQL, indeks pencarian di OpenSearch).</p>
<h2>2.2 Arsitektur</h2>${tbl(["Komponen", "Teknologi", "Peran"], [
  ["gateway", "nginx 1.27 (:80, :8585)", "Satu pintu masuk; landing page; tema LenO dan menu Visualisasi; meneruskan /visualisasi/."],
  ["ldg-server / ldg-migrate", "Server katalog 2.0.7", "UI + API katalog, autentikasi, otorisasi, glosarium, lineage, mutu; migrasi skema saat start."],
  ["postgresql", "PostgreSQL 15", "lendatagovernance_db (metadata katalog), superset (metadata Visualisasi)."],
  ["opensearch", "OpenSearch 3.4.0 (ldg-cluster)", "Indeks pencarian (data turunan; dapat dibangun ulang)."],
  ["superset", "Apache Superset 6.0.0-dg2", "Visualisasi di /visualisasi; SSO dg_sso.py; penjaga SQL."],
  ["Trino lakehouse", "Trino + Iceberg/Lakekeeper", "Sistem rekam: medallion_repository, workspace."],
  ["lakehouse.py + timer", "Python 3.12, systemd", "Pemuat Bronze → Silver → Gold; inbox tiap 10 menit."],
  ["catalog_loader.py / catalog_trino.py", "Python", "Memuat workbook ke katalog; sinkron katalog ↔ Trino."],
].map((r) => r.map(e)))}
<p>Alur data: berkas sumber → inbox → Bronze (Trino) → Silver → Gold → Visualisasi/SQL Lab; katalog disinkronkan dari Trino dan diperkaya metadata workbook.</p>
<h2>2.3 Aktor</h2>${tbl(["Aktor", "Karakteristik", "Kebutuhan utama"], [
  [AKTOR.PU, "Pegawai unit kerja; non-teknis sampai analis.", "Mencari data, membaca definisi, dashboard, analisis di workspace."],
  [AKTOR.DO, "Pemilik bisnis data ERM.", "Pemilik aset, klasifikasi, perbaikan workbook."],
  [AKTOR.DS, "Pengurus istilah dan mutu.", "Menyunting dan menyetujui glosarium, aturan mutu."],
  [AKTOR.ST, "Pengelola program tata kelola.", "KPI, pemuatan ulang workbook, tindak lanjut cacat."],
  [AKTOR.AD, "TI, akses server dan admin aplikasi.", "Instalasi, token, pemuatan, backup, upgrade, keamanan."],
  [AKTOR.PI, "Manajemen.", "Ringkasan risiko dan kinerja tata kelola."],
  [AKTOR.SYS, "Proses otomatis.", "Inbox, backup, sinkron katalog, snapshot."],
  [AKTOR.IDS, "Penyedia identitas Len.", "SSO OIDC (fase 2)."],
  [AKTOR.TR, "Sistem eksternal.", "Menyimpan dan mengeksekusi data lakehouse."],
].map((r) => r.map(e)))}
<h2>2.4 Batasan</h2><ul><li>Data bisnis wajib di Trino lakehouse; berkas CSV/XLSX hanya masukan Bronze.</li>
<li>Tidak ada port atau kredensial terpisah untuk Visualisasi; semua lewat :8585.</li>
<li>Repo GitHub publik: rahasia hanya di /srv/lendatagovernance/secrets.</li>
<li>Server katalog memakai image upstream; nama image, path di dalam image, kunci env, dan path URL tidak dapat diganti.</li>
<li>Satu server dev (jitsi), Docker Compose, jaringan ldg-internal (tanpa rute keluar) dan ldg-egress.</li></ul>
<h2>2.5 Asumsi dan ketergantungan</h2><ul><li>Trino dan penyimpanan Lakekeeper/S3 tersedia; galat sementara ditangani dengan coba ulang.</li>
<li>Tim IDS menerbitkan client OIDC dan tim jaringan membuat DNS dev-data.len.co.id (fase 2).</li>
<li>Workbook Governance dan E-GRC dipelihara pemilik data.</li></ul>

<h1 id="s3" class="pb">3. Kebutuhan fungsional</h1>
<p>Setiap kebutuhan bersifat wajib ("harus"). Kolom Use case menunjuk use case yang memenuhinya.</p>
${tbl(["ID", "Area", "Kebutuhan", "Use case"], FR.map(([id, a, k]) => [id, e(a), e(k), (ucByFr[id] || []).join(", ") || "—"]))}

<h1 id="s4" class="pb">4. Kebutuhan non-fungsional dan antarmuka</h1>
${tbl(["ID", "Kategori", "Kebutuhan"], NFR.map((r) => r.map(e)))}
<h2>4.1 Antarmuka eksternal</h2>${tbl(["Antarmuka", "Arah", "Spesifikasi"], [
  ["Peramban pengguna", "Masuk", "HTTP :80/:8585 via gateway; tema LenO; Bahasa Indonesia."],
  ["API katalog", "Masuk", "REST /api/v1 dengan Bearer token (LDG_TOKEN untuk otomasi)."],
  ["Trino", "Keluar", "HTTPS :443, catalog lakekeeper, schema medallion_repository / workspace."],
  ["IDS Len", "Keluar", "OIDC discovery/JWKS ids.len.co.id (fase 2)."],
  ["DBeaver (admin)", "Ke Trino", "JDBC jdbc:trino://datahub.len.co.id:443 untuk verifikasi."],
].map((r) => r.map(e)))}

<h1 id="s5" class="pb">5. Kebutuhan data</h1>
<p>Sistem rekam: <code>lakekeeper.medallion_repository</code>. Definisi tabel di medallion_repository.sql; tabel Silver/Gold memuat kolom lineage <code>_file_id, _batch_id, _source_system, _source_file, _loaded_at</code>.</p>
${tbl(["Lapisan", "Tabel", "Isi", "Cara isi"], [
  ["Bronze", "bronze_repository, bronze_&lt;sumber&gt;_&lt;sheet&gt;, bronze_meta_quarantine, bronze_erm_* (data lama)", "Baris mentah per sheet, status per berkas, header asing.", "Append; checksum mencegah duplikasi."],
  ["Silver", "silver_dim_* (organisasi, tanggal, risiko, taksonomi, kriteria, glosarium, field …), silver_fact_* (penilaian risiko, KRI, mitigasi, appetite …)", "Bersih, bertipe, kode F0xx di komentar.", "Full refresh dari berkas terbaru tiap sumber."],
  ["Gold", "gold_erm_* (risk register, heatmap, KRI, mitigasi, ringkasan eksekutif …), gold_meta_* (kamus data, lineage, glosarium, KPI, temuan mutu …)", "Siap dashboard; *_snapshot = riwayat harian.", "Full refresh; snapshot per hari."],
  ["Workspace", "lakekeeper.workspace.*", "Tabel kerja pengguna (SQL Lab, unggahan).", "Dibuat pengguna; tidak dikelola loader."],
])}
<h2>5.1 Tabel ERM LenO → tabel Trino</h2>${tbl(["Tabel LenO (Database_Object)", "Tabel Trino di medallion_repository"], [
  ["erm_masterrisk", "silver_dim_erm_risk_taxonomy"], ["erm_heatmap", "silver_dim_erm_risk_matrix"],
  ["erm_dasarsasaran / erm_sasaran", "silver_dim_erm_objective_basis / silver_dim_erm_objective"],
  ["erm_penerimaanrisiko", "silver_fact_erm_risk_appetite"],
  ["erm_kriteriadampakkuantitatif / …kualitatif", "silver_dim_erm_impact_criteria_quantitative / …_qualitative"],
  ["erm_kriteriakemungkinan", "silver_dim_erm_likelihood_criteria"],
  ["erm_efektivitas / erm_kecukupan", "silver_dim_erm_control_effectiveness / …_adequacy"],
  ["erm_riskregister / erm_penyebabrisiko", "silver_dim_erm_risk / silver_dim_erm_risk_cause"],
  ["erm_riskinherent + erm_riskresidual", "silver_fact_erm_risk_assessment"],
  ["erm_analisaswot / erm_existingcontrol", "silver_fact_erm_swot_analysis / silver_fact_erm_existing_control"],
  ["erm_rencanamitigasi / erm_realisasimitigasi", "silver_fact_erm_mitigation_plan_monthly / silver_fact_erm_mitigation_realization"],
].map((r) => r.map(e)))}
<h2>5.2 Retensi dan kualitas</h2><ul><li>Backup basis data internal 14 hari; snapshot Gold harian dipertahankan.</li>
<li>ETL tidak mengubah isi bisnis diam-diam: nilai sumber disimpan, koreksi dicatat (silver_fact_meta_baseline_correction, gold_meta_dq_finding_snapshot).</li>
<li>Cacat workbook dilaporkan ke /srv/lendatagovernance/reports (di luar repo).</li></ul>

<h1 id="s6" class="pb">6. Use case — ringkasan</h1>
<div class="lv"><div><h3>${chip("Dasar")} 25 use case</h3><p>Pemakaian harian lewat antarmuka: masuk, mencari dan memahami data, glosarium, kepemilikan, klasifikasi, lineage, mutu, dashboard, grafik, SQL Lab, tabel kerja.</p></div>
<div><h3>${chip("Lanjutan")} 25 use case</h3><p>Administrasi dan otomasi: token, pengguna, hak DG-*, pemuatan lakehouse, sinkron katalog, aturan data Trino-only, backup/restore, IDS, upgrade, indeks pencarian, rahasia.</p></div></div>
${tbl(["ID", "Nama", "Tingkat", "Aktor utama", "Prioritas", "Status"], sel.map((u) => [`<b>${u.id}</b>`, e(u.nama), chip(u.level), e(u.aktor[0]), u.prioritas, st(u.status)]))}

<h1 id="s7" class="pb">7. Use case Dasar</h1>
<p>Dua puluh lima use case untuk pengguna bisnis. Semua dijalankan lewat peramban di :8585, tanpa akses server.</p>
${D.map(ucCard).join("")}

<h1 id="s8" class="pb">8. Use case Lanjutan</h1>
<p>Dua puluh lima use case untuk administrasi, otomasi, integrasi, dan operasi. Sebagian dijalankan Administrator di server (skrip di deploy/lendatagovernance), sebagian berjalan otomatis.</p>
${L.map(ucCard).join("")}

<h1 id="s9" class="pb">9. Matriks keterlacakan</h1>
${tbl(["Kebutuhan", "Use case", "Komponen", "Verifikasi"], FR.map(([id, area]) => [id, (ucByFr[id] || []).join(", ") || "—", e(comp[area] || "-"), e(ver[area] || "Uji fungsional UI/API")]))}

<h1 id="s10" class="pb">10. Kriteria penerimaan</h1><ol>
<li>Semua use case berstatus Tersedia lulus uji alur utama dan alternatif di server dev.</li>
<li>lakehouse.py status menunjukkan jumlah baris yang sama dengan katalog dan DBeaver untuk seluruh tabel medallion_repository.</li>
<li>CREATE TABLE workspace.&lt;nama&gt; berhasil; penulisan ke schema lain dan koneksi non-Trino ditolak.</li>
<li>Pencarian kata kunci pada semua jenis aset tanpa galat dan tanpa shard gagal (terverifikasi 10-11-2026: 1.056 uji).</li>
<li>Tidak ada nama produk upstream pada teks antarmuka, kecuali yang ditetapkan upstream.</li>
<li>Backup harian ada dan restore uji berhasil.</li>
<li>Fase 2: login IDS berhasil dan akun basic sementara dinonaktifkan.</li></ol>

<h1 id="s11" class="pb">11. Isu terbuka dan risiko</h1>
${tbl(["ID", "Isu", "Dampak", "Tindak lanjut", "Pemilik"], [
  ["ISU-01", "<b>Selesai 10-11-2026.</b> Pencarian galat 500 pada OpenSearch 3.2 (bug Lucene 10: script_score di dalam dis_max pada segmen tanpa kecocokan).", "—", "OpenSearch 3.4.0 + reindex penuh; 1.056 uji lulus (NFR-17).", "UV-3"],
  ["ISU-02", "Client IDS dan DNS dev-data.len.co.id belum tersedia.", "Login masih basic auth.", "P2-1, P2-2, lalu UC-L20.", "Tim IDS, Jaringan"],
  ["ISU-03", "Workspace memakai satu kredensial Trino bersama.", "Pengguna dapat menimpa tabel kerja pengguna lain.", "Kredensial Trino per pengguna atau impersonation.", "UV-3"],
  ["ISU-04", "Namespace lakekeeper.erm (kosong) diproteksi di Lakekeeper.", "Schema kosong tersisa.", "Admin Lakekeeper melepas proteksi, lalu migrate_legacy_erm.py.", "Admin Lakekeeper"],
  ["ISU-05", "23 cacat workbook (glosarium kosong, tabel Not Found, klasifikasi, kolom kembar).", "Metadata belum lengkap.", "UC-L25.", "UG-1 / UV-1"],
  ["ISU-06", "Uji mutu baru definisi; Domain, Data Product, Data Contract belum ada.", "Mutu tidak terukur otomatis.", "P4-1.", "UV-1"],
  ["ISU-07", "Hardening akses (self-signup, policy konsumen, jumlah admin).", "Risiko hak berlebih.", "SEC-1 (Manual Pengembang §2.3).", "UV-3"],
])}

<h1 id="sA" class="pb">Lampiran A. Aktor × use case</h1>
${tbl(["Aktor", "Dasar", "Lanjutan"], Object.values(AKTOR).map((a) => [e(a), D.filter((u) => u.aktor.includes(a)).map((u) => u.id).join(", ") || "—", L.filter((u) => u.aktor.includes(a)).map((u) => u.id).join(", ") || "—"]))}
<h1 id="sB">Lampiran B. Riwayat revisi</h1>
${tbl(["Versi", "Tanggal", "Perubahan"], [
  ["1.0", "10-11-2026", "Versi .docx (60 use case)."],
  ["1.1", "10-11-2026", `Format PDF; 50 use case (25 Dasar, 25 Lanjutan; 10 dilebur); ${FR.length} FR, ${NFR.length} NFR; ISU-01 selesai.`],
])}
</body></html>`;

const htmlFile = path.join(SRC, "srs.html");
fs.writeFileSync(htmlFile, html);
const out = `${REL} SRS Len Data Governance.pdf`;
execFileSync("node", [path.join(SRC, "build-pdf.mjs"), OUTDIR, JSON.stringify([{ src: "srs.html", out, title: `SRS ${REL}` }])], { stdio: "inherit" });
fs.unlinkSync(htmlFile);
console.log(`${sel.length} use case (${D.length} Dasar, ${L.length} Lanjutan) → ${path.join(OUTDIR, out)}`);
