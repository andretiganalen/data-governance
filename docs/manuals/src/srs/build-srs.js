// SRS Len Data Governance → .docx  (node docs/manuals/src/srs/build-srs.js "<keluaran.docx>")
// Struktur mengikuti ISO/IEC/IEEE 29148 (SRS). Use case: usecases.js.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
  HeadingLevel, LevelFormat, PageBreak, Header, Footer, PageNumber, TableOfContents, BorderStyle, ImageRun,
} = require("docx");
const { UC, AKTOR } = require("./usecases");

const OUT = process.argv[2] || "SRS Len Data Governance.docx";
const REL = process.argv[3] || "261110 02";
const NAVY = "194A80", RED = "CF0000", GREY = "F2F4F7", LINE = "C9CED6", FONT = "Arial";
const W = 9638; // lebar isi A4 dengan margin 1134 DXA (2 cm)

// ---------------------------------------------------------------- helper
const t = (s, o = {}) => new TextRun({ text: s, font: FONT, size: o.size || 20, bold: o.bold, italics: o.italics, color: o.color });
const P = (s, o = {}) => new Paragraph({ children: Array.isArray(s) ? s : [t(s, o)], spacing: { after: o.after ?? 100, line: 276 }, alignment: o.align, keepNext: o.keepNext });
const H1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(s)], pageBreakBefore: true });
const H2 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(s)] });
const H3 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [t(s)] });
const B = (s, lvl = 0) => new Paragraph({ numbering: { reference: "bullet", level: lvl }, children: Array.isArray(s) ? s : [t(s)], spacing: { after: 60 } });
const N = (s, ref) => new Paragraph({ numbering: { reference: ref, level: 0 }, children: [t(s)], spacing: { after: 60 } });
const rich = (s) => s.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((x) => x.startsWith("**") ? t(x.slice(2, -2), { bold: true }) : t(x));

function cell(content, width, o = {}) {
  const paras = (Array.isArray(content) ? content : [content]).map((c) =>
    c instanceof Paragraph ? c : new Paragraph({ children: rich(String(c)).map((r) => r), spacing: { after: 40 } }));
  if (o.head) paras.forEach((p) => p.root.forEach?.(() => {}));
  return new TableCell({
    width: { size: width, type: WidthType.DXA }, children: paras,
    shading: o.fill ? { type: ShadingType.CLEAR, color: "auto", fill: o.fill } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
  });
}
function table(head, rows, widths) {
  const sum = widths.reduce((a, b) => a + b, 0);
  const ws = widths.map((x) => Math.round((x * W) / sum));
  ws[ws.length - 1] += W - ws.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: LINE };
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: ws,
    borders: { top: border, bottom: border, left: border, right: border, insideHorizontal: border, insideVertical: border },
    rows: [
      new TableRow({ tableHeader: true, children: head.map((h, i) => new TableCell({
        width: { size: ws[i], type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, color: "auto", fill: NAVY },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: [t(h, { bold: true, color: "FFFFFF", size: 19 })] })] })) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, ws[i], { fill: ri % 2 ? GREY : undefined })) })),
    ],
  });
}
const gap = () => new Paragraph({ children: [], spacing: { after: 120 } });

// ---------------------------------------------------------------- kebutuhan fungsional
const FR = [
  ["FR-01", "Autentikasi", "Sistem harus mewajibkan login sebelum akses katalog, API, dan Visualisasi."],
  ["FR-02", "Autentikasi", "Sistem harus mendukung SSO OIDC dengan IDS Len (confidential client) pada fase 2."],
  ["FR-03", "Autentikasi", "Sistem harus menerbitkan token sesi bertanda tangan (JWT, kunci RSA per server)."],
  ["FR-04", "Autentikasi", "Logout atau token berganti harus mengakhiri sesi Visualisasi pada permintaan berikutnya."],
  ["FR-05", "Otorisasi", "Admin harus dapat membuat Access Token bermasa berlaku untuk otomasi."],
  ["FR-06", "Otorisasi", "Sistem harus memodelkan organisasi Direktorat › Divisi › Unit Kerja sebagai tim."],
  ["FR-07", "Otorisasi", "Hak DG-* dari workbook harus ditegakkan sebagai policy + role default tim."],
  ["FR-10", "Katalog", "Sistem harus menyediakan pencarian teks lintas tabel, kolom, glosarium, dan dashboard."],
  ["FR-11", "Katalog", "Sistem harus menampilkan hierarki layanan › database › schema › tabel lakehouse."],
  ["FR-12", "Katalog", "Halaman tabel harus menampilkan kolom, tipe Trino, komentar, tag, pemilik, dan jumlah baris."],
  ["FR-13", "Glosarium", "Sistem harus menyediakan glosarium ERM satu istilah per Elemen Data dengan definisi."],
  ["FR-14", "Glosarium", "Perubahan istilah harus melalui reviewer (Data Steward bisnis)."],
  ["FR-15", "Kepemilikan", "Setiap aset harus dapat diberi pemilik tim unit kerja."],
  ["FR-16", "Klasifikasi", "Kolom harus dapat diberi tepat satu tag Sensitivitas (Public…Strictly Confidential)."],
  ["FR-17", "Lineage", "Sistem harus menampilkan lineage kolom tabel Trino → model data layar → layar LenO."],
  ["FR-18", "Mutu data", "Sistem harus menyimpan definisi uji mutu per kolom Trino."],
  ["FR-19", "Referensi", "Hak akses layar LenO harus tercatat sebagai properti referensi pada dashboard layar."],
  ["FR-20", "Kolaborasi", "Pengguna harus dapat mengikuti aset, berdiskusi, dan mengajukan tugas perubahan."],
  ["FR-21", "Katalog", "Metadata Workbook ERM (blok deskripsi, tag, pemilik) harus bertahan saat sinkron ulang dari Trino."],
  ["FR-22", "Katalog ERM", "Tabel ERM LenO harus direpresentasikan oleh tabel Trino padanannya (TABLE_MAP, kode F0xx); tidak ada layanan database terpisah."],
  ["FR-23", "Pemuat", "Pemuat workbook harus idempoten dan menghasilkan laporan cacat di luar repo."],
  ["FR-30", "Lakehouse", "Berkas sumber (.xlsx/.xlsm/.csv) hanya masukan Bronze melalui inbox atau ingest."],
  ["FR-31", "Lakehouse", "Bronze harus menyimpan baris mentah per sheet, checksum, dan status per berkas; berkas sama tidak dimuat dua kali."],
  ["FR-32", "Lakehouse", "Silver (dim/fact bertipe + kolom lineage) dan Gold (siap dashboard, snapshot harian) dibangun dari berkas terbaru tiap sumber."],
  ["FR-33", "Lakehouse", "Pemrosesan inbox harus otomatis setiap 10 menit dan tidak menyentuh Trino bila inbox kosong."],
  ["FR-34", "Lakehouse", "Pemuatan yang gagal sebagian harus dapat dilanjutkan per sheet (PARTIAL → retry)."],
  ["FR-35", "Lakehouse", "Sistem harus melaporkan jumlah baris dan snapshot terakhir per tabel."],
  ["FR-36", "Lakehouse", "Sumber dikenali otomatis (DG_WORKBOOK, EGRC, FILE); header asing dikarantina."],
  ["FR-37", "Lakehouse", "Skema Trino harus mengikuti medallion_repository.sql sebagai sumber kebenaran."],
  ["FR-38", "Katalog", "Katalog harus disinkronkan dengan Trino setelah setiap pemuatan (tabel, kolom, jumlah baris; hapus lunak tabel hilang)."],
  ["FR-39", "Lakehouse", "Data ERM lama di schema lain harus dapat dipindahkan ke medallion_repository dengan verifikasi jumlah baris."],
  ["FR-40", "Visualisasi", "Visualisasi harus tampil di dalam aplikasi utama (:8585/visualisasi/), tanpa port atau kredensial terpisah."],
  ["FR-41", "Visualisasi", "Peran Visualisasi mengikuti peran aplikasi utama (Admin → Admin; lainnya → Gamma + sql_lab)."],
  ["FR-42", "Visualisasi", "Dashboard Risiko ERM dan Tata Kelola Data harus membaca Gold langsung dari Trino, dengan filter dan drill-down."],
  ["FR-43", "Visualisasi", "Pengguna harus dapat membuat grafik dan dashboard sendiri."],
  ["FR-44", "Visualisasi", "SQL Lab harus tersedia untuk query baca dengan batas waktu dan baris."],
  ["FR-45", "Visualisasi", "Semua pengguna boleh membuat tabel dan mengunggah CSV/XLSX hanya di lakekeeper.workspace."],
  ["FR-46", "Aturan data", "Pernyataan tulis ke selain lakekeeper.workspace harus ditolak sebelum dikirim ke Trino."],
  ["FR-47", "Aturan data", "Hanya koneksi database Trino yang boleh dibuat, diubah, atau diuji."],
  ["FR-48", "Visualisasi", "Koneksi, dataset Gold, dan dashboard awal harus dapat disiapkan ulang dengan satu skrip."],
  ["FR-50", "Operasi", "Basis data internal harus dibackup harian (retensi 14 hari) dan dapat dipulihkan."],
  ["FR-51", "Operasi", "Status layanan harus dapat diperiksa dengan satu perintah."],
  ["FR-52", "Operasi", "Upgrade komponen dan pembangunan ulang indeks pencarian harus terdokumentasi dan dapat diulang."],
  ["FR-53", "Dokumentasi", "Manual pengguna, staf, dan pengembang harus dapat diterbitkan ulang dari data terkini."],
  ["FR-54", "Keamanan", "Rahasia harus disimpan hanya di /srv/lendatagovernance/secrets, tidak di repo."],
  ["FR-55", "Antarmuka", "Seluruh antarmuka memakai tema Len classic dan nama Len Data Governance."],
];

const NFR = [
  ["NFR-01", "Keamanan", "Akses UI/API hanya lewat gateway :80/:8585; port admin 8586 dan Superset 8088 tidak dibuka ke luar."],
  ["NFR-02", "Keamanan", "Rahasia tidak pernah masuk git (remote GitHub publik); setiap push didahului pemindaian rahasia."],
  ["NFR-03", "Keamanan", "Kredensial Trino hanya di secrets/trino.env; Visualisasi memakai satu koneksi Trino bersama dengan penjaga SQL."],
  ["NFR-04", "Keamanan", "Sesi Visualisasi berlaku maks. 8 jam dan terikat hash token aplikasi utama."],
  ["NFR-05", "Kinerja", "Halaman katalog terbuka ≤ 3 detik pada jaringan kantor; query SQL Lab dibatasi 300 detik dan 100.000 baris."],
  ["NFR-06", "Kinerja", "Pemuatan inbox mendeteksi berkas baru dalam ≤ 10 menit."],
  ["NFR-07", "Keandalan", "Galat sementara Lakekeeper/S3 dicoba ulang hingga 8 kali (30 detik … 5 menit) tanpa duplikasi data."],
  ["NFR-08", "Keandalan", "Hanya satu loader lakehouse berjalan pada satu waktu (kunci berkas)."],
  ["NFR-09", "Ketersediaan", "Layanan memakai restart unless-stopped dan healthcheck; gateway menampilkan halaman tunggu saat server mulai."],
  ["NFR-10", "Pemulihan", "RPO ≤ 24 jam (backup 01:30), RTO ≤ 2 jam (restore + reindex)."],
  ["NFR-11", "Kepatuhan data", "Semua data bisnis aplikasi tinggal di Trino lakehouse; pengecualian hanya penyimpanan internal platform (Postgres, OpenSearch)."],
  ["NFR-12", "Penamaan", "Tabel lakehouse mengikuti kerangka Inggris bronze_/silver_dim_/silver_fact_/gold_; kolom membawa kode F0xx/X0xx di komentar (ADR DG-0002)."],
  ["NFR-13", "Penamaan", "Tidak ada nama produk upstream pada komponen milik proyek; hanya nama yang ditetapkan upstream (image, path di dalam image, kunci env, path URL)."],
  ["NFR-14", "Pemeliharaan", "Semua konfigurasi di repo deploy/lendatagovernance; salinan live /opt/lendatagovernance/deploy; data /srv/lendatagovernance."],
  ["NFR-15", "Kegunaan", "Antarmuka berbahasa Indonesia dengan tema LenO (Montserrat/Open Sans, navy #194A80, merah #CF0000)."],
  ["NFR-16", "Lisensi", "Komponen open-source berlisensi permisif (Apache-2.0, PostgreSQL); tanpa Elasticsearch ELv2/AGPL atau MySQL GPL."],
  ["NFR-17", "Kompatibilitas", "OpenSearch harus ≥ 3.4.0 untuk server katalog 2.0.x (bug Lucene 10 script_score pada 3.2–3.3)."],
];

const GRUP = { A: "Akses dan identitas", B: "Katalog dan tata kelola metadata", C: "Lakehouse dan pemuat data", D: "Visualisasi dan analitik", E: "Operasi dan pemeliharaan" };

// ---------------------------------------------------------------- isi
const kids = [];
// Sampul
const logo = path.join(__dirname, "..", "img", "len-logo.png");
if (fs.existsSync(logo)) kids.push(new Paragraph({ children: [new ImageRun({ type: "png", data: fs.readFileSync(logo), transformation: { width: 150, height: 54 } })], spacing: { after: 1600 } }));
kids.push(
  new Paragraph({ children: [t("SOFTWARE REQUIREMENTS SPECIFICATION", { size: 24, bold: true, color: RED })], spacing: { after: 200 } }),
  new Paragraph({ children: [t("Len Data Governance", { size: 56, bold: true, color: NAVY })], spacing: { after: 200 } }),
  new Paragraph({ children: [t("Katalog metadata, Trino lakehouse Medallion, dan Visualisasi — tata kelola data ERM", { size: 26 })], spacing: { after: 1200 } }),
  table(["Atribut", "Nilai"], [
    ["Nomor dokumen", `SRS-LDG ${REL}`], ["Versi", "1.0"], ["Tanggal", "10 November 2026"],
    ["Sistem", "Len Data Governance — server dev jitsi (192.168.125.14), dev-data.len.co.id"],
    ["Pemilik", "Data Governance (UV-1) · Administrator (UV-3)"], ["Klasifikasi", "Internal"],
    ["Acuan struktur", "ISO/IEC/IEEE 29148:2018 — Software Requirements Specification"],
  ], [30, 70]),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ children: [t("Riwayat revisi", { size: 26, bold: true, color: NAVY })], spacing: { after: 120 } }),
  table(["Versi", "Tanggal", "Perubahan", "Oleh"], [
    ["1.0", "10-11-2026", `Rilis awal: ${FR.length} kebutuhan fungsional, ${NFR.length} non-fungsional, ${UC.length} use case, sesuai sistem yang berjalan (data hanya di Trino, katalog ERM pada tabel Trino, Visualisasi terintegrasi, penamaan Len Data Governance).`, "Tim Data Governance"],
  ], [10, 15, 55, 20]),
  gap(),
  new Paragraph({ children: [t("Daftar isi", { size: 26, bold: true, color: NAVY })], spacing: { after: 120 } }),
  new TableOfContents("Daftar isi", { hyperlink: true, headingStyleRange: "1-2" }),
  P("(Perbarui daftar isi di Word: klik kanan › Update Field.)", { italics: true, size: 18 }),
);

// 1. Pendahuluan
kids.push(H1("1. Pendahuluan"),
  H2("1.1 Tujuan"),
  P("Dokumen ini menetapkan kebutuhan perangkat lunak Len Data Governance: apa yang harus dilakukan sistem, untuk siapa, dengan batasan apa, dan bagaimana kebutuhan diverifikasi. Dokumen menjadi acuan bersama bagi Staf Data Governance, Data Owner, Administrator, pengembang, dan Pimpinan untuk pengembangan, pengujian penerimaan, dan audit."),
  H2("1.2 Ruang lingkup"),
  P("Len Data Governance adalah satu aplikasi web untuk tata kelola data ERM Len (holding DEFEND ID). Cakupannya:"),
  B("Katalog metadata: glosarium bisnis, klasifikasi sensitivitas, kepemilikan, lineage, definisi mutu data, hak tata kelola."),
  B("Trino lakehouse lakekeeper.medallion_repository (Iceberg/Lakekeeper di datahub.len.co.id:443) sebagai satu-satunya sistem rekam data bisnis, berlapis Bronze → Silver → Gold."),
  B("Modul Visualisasi (Superset 6) di dalam aplikasi utama untuk dashboard, grafik, SQL Lab, dan tabel kerja pengguna di lakekeeper.workspace."),
  B("Operasi: backup, pemulihan, upgrade, rilis manual."),
  P("Di luar cakupan: aplikasi transaksi ERM LenO itu sendiri (layarnya hanya direpresentasikan sebagai referensi lineage dan hak akses), dan sistem sumber E-GRC."),
  H2("1.3 Definisi dan singkatan"),
  table(["Istilah", "Arti"], [
    ["Bronze / Silver / Gold", "Lapisan Medallion: mentah apa adanya / bersih bertipe (dim, fact) / siap dashboard."],
    ["Trino lakehouse", "Mesin SQL Trino atas katalog Iceberg lakekeeper; schema medallion_repository (data resmi) dan workspace (tabel kerja pengguna)."],
    ["Workbook Governance", "Berkas Excel Rev.0.1 Data Governance ERM: organisasi, glosarium, elemen data, objek database, lineage, mutu, hak akses."],
    ["E-GRC", "Sumber Data E-GRC (Excel): risk register, profil risiko, pengendalian, matriks."],
    ["Elemen Data (F0xx)", "Kode elemen data workbook; dicantumkan di komentar kolom Trino untuk keterlacakan."],
    ["LenO ERM", "Aplikasi ERM di platform LenO; 18 tabel dan 19 layarnya menjadi referensi metadata."],
    ["UG-1, UV-1, UV-3", "Unit kerja: Data Owner bisnis (UG-1), Data Governance (UV-1), Administrator TI (UV-3)."],
    ["SSO", "Single sign-on: Visualisasi memakai sesi aplikasi utama; fase 2 memakai IDS Len."],
    ["DG-*", "Hak tata kelola (Assign Owner, Classify Data, Edit Glossary, Edit Lineage, Edit DQ Rule, …)."],
    ["Server katalog", "Komponen ldg-server (image open-source upstream versi 2.0.7) yang menyediakan UI dan API katalog."],
  ], [28, 72]),
  H2("1.4 Referensi"),
  B("plan/lendatagovernance_deployment_plan.md — rencana deployment dan fase."),
  B("docs/adr/pm-0001-application-stack.md; docs/adr/dg-0002-medallion-penamaan-field-id.md — keputusan arsitektur dan penamaan."),
  B("deploy/lendatagovernance/medallion/schema/medallion_repository.sql — definisi tabel lakehouse (sumber kebenaran)."),
  B("plan/interface-menu.md, plan/leno_interface_theme.md — standar antarmuka Len classic."),
  B("Manual Pengembang, Manual Staf Data Governance dan Pimpinan, Manual Pengguna (docs/manuals)."),
  H2("1.5 Ikhtisar dokumen"),
  P("Bab 2 menjelaskan konteks dan arsitektur. Bab 3 dan 4 memuat kebutuhan fungsional dan non-fungsional. Bab 5 memuat kebutuhan data. Bab 6 merinci 60 use case. Bab 7 memuat matriks keterlacakan, Bab 8 kriteria penerimaan, dan Bab 9 isu terbuka."),
);

// 2. Deskripsi umum
kids.push(H1("2. Deskripsi umum"),
  H2("2.1 Perspektif produk"),
  P("Len Data Governance menggantikan pengelolaan metadata ERM berbasis berkas dengan satu pintu masuk web. Semua data bisnis berada di Trino lakehouse; aplikasi hanya menyimpan status internal platform (metadata katalog dan Superset di PostgreSQL, indeks pencarian di OpenSearch)."),
  H2("2.2 Arsitektur"),
  table(["Komponen", "Teknologi", "Peran"], [
    ["gateway", "nginx 1.27 (:80, :8585)", "Satu pintu masuk; landing page; menyisipkan tema LenO dan menu Visualisasi; meneruskan /visualisasi/ ke Superset."],
    ["ldg-server", "Server katalog 2.0.7 (Java)", "UI + API katalog, autentikasi, otorisasi, glosarium, lineage, mutu."],
    ["ldg-migrate", "Image yang sama", "Migrasi skema basis data internal saat start."],
    ["postgresql", "PostgreSQL 15", "lendatagovernance_db (metadata katalog), superset (metadata Visualisasi)."],
    ["opensearch", "OpenSearch (cluster ldg-cluster)", "Indeks pencarian katalog (data turunan, dapat dibangun ulang)."],
    ["superset", "Apache Superset 6.0.0-dg2", "Modul Visualisasi di /visualisasi; SSO dg_sso.py; penjaga SQL."],
    ["Trino lakehouse", "Trino + Iceberg/Lakekeeper (datahub.len.co.id:443)", "Sistem rekam data: medallion_repository, workspace."],
    ["lakehouse.py + timer", "Python 3.12, systemd", "Pemuat Bronze → Silver → Gold; inbox tiap 10 menit."],
    ["catalog_loader.py / catalog_trino.py", "Python", "Memuat workbook ke katalog; sinkron katalog ↔ Trino."],
  ], [22, 28, 50]),
  gap(),
  P("Alur data: berkas sumber → inbox → Bronze (Trino) → Silver → Gold → Visualisasi/SQL Lab; katalog disinkronkan dari Trino dan diperkaya metadata workbook."),
  H2("2.3 Fungsi utama"),
  B("Menemukan dan memahami data (pencarian, hierarki, detail tabel, glosarium, lineage)."),
  B("Mengelola tata kelola (pemilik, klasifikasi, istilah, uji mutu, hak DG-*)."),
  B("Memuat dan mentransformasi data ke Trino secara otomatis dan dapat diulang."),
  B("Menyajikan data siap pakai di dashboard dan memberi ruang kerja SQL yang aman."),
  B("Mengoperasikan sistem dengan aman (backup, upgrade, rahasia, rilis manual)."),
  H2("2.4 Aktor dan karakteristik pengguna"),
  table(["Aktor", "Karakteristik", "Kebutuhan utama"], [
    [AKTOR.PU, "Pegawai unit kerja; non-teknis sampai analis.", "Mencari data, membaca definisi, melihat dashboard, query/analisis di workspace."],
    [AKTOR.DO, "Pemilik bisnis data ERM.", "Menetapkan pemilik, klasifikasi, memperbaiki workbook."],
    [AKTOR.DS, "Pengurus istilah dan mutu.", "Menyunting dan menyetujui glosarium, aturan mutu."],
    [AKTOR.ST, "Pengelola program tata kelola.", "Memantau KPI, memuat ulang workbook, menindaklanjuti cacat."],
    [AKTOR.AD, "TI, akses server dan admin aplikasi.", "Instalasi, token, pemuatan, backup, upgrade, keamanan."],
    [AKTOR.PI, "Manajemen.", "Ringkasan risiko dan kinerja tata kelola."],
    [AKTOR.SYS, "Proses otomatis.", "Inbox, backup, sinkron katalog, snapshot."],
    [AKTOR.IDS, "Penyedia identitas Len.", "SSO OIDC (fase 2)."],
    [AKTOR.TR, "Sistem eksternal.", "Menyimpan dan mengeksekusi data lakehouse."],
  ], [24, 32, 44]),
  H2("2.5 Batasan"),
  B("Data bisnis wajib di Trino lakehouse (aturan proyek 2026-11-09); berkas CSV/XLSX hanya masukan Bronze."),
  B("Tidak ada port atau kredensial terpisah untuk Visualisasi; semua lewat :8585."),
  B("Repo GitHub publik: rahasia hanya di /srv/lendatagovernance/secrets."),
  B("Server katalog memakai image upstream; nama image, path di dalam image, kunci env, dan path URL tidak dapat diganti."),
  B("Lingkungan: satu server dev (jitsi) dengan Docker Compose; jaringan ldg-internal (tanpa rute keluar) dan ldg-egress."),
  H2("2.6 Asumsi dan ketergantungan"),
  B("Trino datahub.len.co.id dan penyimpanan Lakekeeper/S3 tersedia; galat sementara ditangani dengan coba ulang."),
  B("Tim IDS menerbitkan client OIDC dan tim jaringan membuat DNS dev-data.len.co.id (fase 2)."),
  B("Workbook Governance dan E-GRC dipelihara pemilik data."),
);

// 3. Kebutuhan fungsional
const ucByFr = {};
UC.forEach((u) => u.fr.forEach((f) => (ucByFr[f] = (ucByFr[f] || []).concat(u.id))));
kids.push(H1("3. Kebutuhan fungsional"),
  P("Setiap kebutuhan bersifat wajib (\"harus\") kecuali disebut lain. Kolom Use case menunjukkan use case yang memenuhinya (rinci di Bab 6)."),
  table(["ID", "Area", "Kebutuhan", "Use case"], FR.map(([id, a, k]) => [id, a, k, (ucByFr[id] || []).join(", ")]), [10, 15, 55, 20]));

// 4. Non-fungsional
kids.push(H1("4. Kebutuhan non-fungsional"),
  table(["ID", "Kategori", "Kebutuhan"], NFR, [11, 17, 72]),
  H2("4.1 Antarmuka eksternal"),
  table(["Antarmuka", "Arah", "Spesifikasi"], [
    ["Peramban pengguna", "Masuk", "HTTP :80/:8585 via gateway; tema LenO; Bahasa Indonesia."],
    ["API katalog", "Masuk", "REST /api/v1 dengan Bearer token (LDG_TOKEN untuk otomasi)."],
    ["Trino", "Keluar", "HTTPS :443, basic auth, catalog lakekeeper, schema medallion_repository / workspace."],
    ["IDS Len", "Keluar", "OIDC discovery/JWKS ids.len.co.id (fase 2)."],
    ["DBeaver (admin)", "Masuk ke Trino", "JDBC jdbc:trino://datahub.len.co.id:443 untuk verifikasi."],
  ], [22, 13, 65]),
);

// 5. Kebutuhan data
kids.push(H1("5. Kebutuhan data"),
  P("Sistem rekam: lakekeeper.medallion_repository. Definisi tabel di medallion_repository.sql; setiap tabel Silver/Gold memuat kolom lineage _file_id, _batch_id, _source_system, _source_file, _loaded_at."),
  table(["Lapisan", "Tabel", "Isi", "Cara isi"], [
    ["Bronze", "bronze_repository, bronze_<sumber>_<sheet>, bronze_meta_quarantine, bronze_erm_* (data lama)", "Baris mentah varchar per sheet, status per berkas, header asing.", "Append; checksum mencegah duplikasi."],
    ["Silver", "silver_dim_* (organisasi, tanggal, risiko, taksonomi, kriteria, glosarium, field, …), silver_fact_* (penilaian risiko, KRI, mitigasi, appetite, …)", "Bersih, bertipe, kode F0xx di komentar.", "Full refresh dari berkas terbaru tiap sumber."],
    ["Gold", "gold_erm_* (risk register, heatmap, KRI, mitigasi, ringkasan eksekutif, …), gold_meta_* (kamus data, lineage, glosarium, KPI, temuan mutu, …)", "Siap dashboard; *_snapshot = riwayat harian.", "Full refresh; snapshot per hari."],
    ["Workspace", "lakekeeper.workspace.*", "Tabel kerja pengguna (SQL Lab, unggahan).", "Dibuat pengguna; tidak dikelola loader."],
  ], [12, 38, 28, 22]),
  gap(),
  H2("5.1 Pemetaan tabel ERM LenO ke Trino"),
  table(["Tabel LenO (Database_Object)", "Tabel Trino"], [
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
  ], [45, 55]),
  gap(),
  H2("5.2 Retensi dan kualitas"),
  B("Backup basis data internal 14 hari; snapshot Gold harian dipertahankan."),
  B("ETL tidak mengubah isi bisnis diam-diam: nilai sumber disimpan, koreksi dicatat (silver_fact_meta_baseline_correction, gold_meta_dq_finding_snapshot)."),
  B("Cacat workbook dilaporkan ke /srv/lendatagovernance/reports (di luar repo)."),
);

// 6. Use case
kids.push(H1("6. Use case"),
  P(`Total ${UC.length} use case dalam ${Object.keys(GRUP).length} kelompok. Status: Tersedia = berjalan di server dev; Fase 2 = menunggu prasyarat eksternal.`),
  table(["ID", "Nama", "Aktor utama", "Prioritas", "Status"], UC.map((u) => [u.id, u.nama, u.aktor[0], u.prioritas, u.status]), [10, 42, 26, 11, 11]));
for (const [g, judul] of Object.entries(GRUP)) {
  kids.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(`6.${"ABCDE".indexOf(g) + 1} ${judul}`)], pageBreakBefore: true }));
  for (const u of UC.filter((x) => x.grup === g)) {
    kids.push(H3(`${u.id} — ${u.nama}`));
    const lst = (arr, num) => arr.length ? arr.map((s, i) => new Paragraph({ children: [t(num ? `${i + 1}. ${s}` : `• ${s}`)], spacing: { after: 30 } })) : [new Paragraph({ children: [t("—")] })];
    kids.push(table(["Elemen", "Uraian"], [
      ["Aktor", u.aktor.join("; ")],
      ["Tujuan", u.tujuan],
      ["Prioritas / status", `${u.prioritas} / ${u.status}`],
      ["Prasyarat", lst(u.pra, false)],
      ["Pemicu", u.pemicu],
      ["Alur utama", lst(u.utama, true)],
      ["Alur alternatif / eksepsi", lst(u.alt, false)],
      ["Pascakondisi", u.pasca],
      ["Kebutuhan", u.fr.join(", ")],
    ], [24, 76]), gap());
  }
}

// 7. Keterlacakan
kids.push(H1("7. Matriks keterlacakan"),
  P("Setiap kebutuhan fungsional ditelusuri ke use case, komponen, dan cara verifikasi."),
  table(["Kebutuhan", "Use case", "Komponen", "Verifikasi"], FR.map(([id, area]) => {
    const comp = { Autentikasi: "ldg-server, gateway, dg_sso.py", Otorisasi: "ldg-server, catalog_loader.py", Katalog: "ldg-server, catalog_trino.py", Glosarium: "ldg-server", Kepemilikan: "ldg-server", Klasifikasi: "ldg-server", Lineage: "ldg-server, catalog_loader.py", "Mutu data": "ldg-server", Referensi: "ldg-server", Kolaborasi: "ldg-server", "Katalog ERM": "workbook.py, catalog_loader.py", Pemuat: "catalog_loader.py", Lakehouse: "lakehouse.py, Trino", Visualisasi: "superset, leno-menu.js", "Aturan data": "dg_sso.py", Operasi: "scripts/*, systemd", Dokumentasi: "docs/manuals/src/rilis.py", Keamanan: "secrets-init.sh", Antarmuka: "leno-theme, gateway" }[area] || "-";
    const ver = { Lakehouse: "lakehouse.py status vs DBeaver", "Aturan data": "Uji SQL Lab / uji koneksi (HTTP 422)", Visualisasi: "Uji UI di :8585/visualisasi/", Operasi: "verify.sh, restore uji" }[area] || "Uji fungsional UI/API";
    return [id, (ucByFr[id] || []).join(", "), comp, ver];
  }), [15, 23, 33, 29]));

// 8. Penerimaan
kids.push(H1("8. Kriteria penerimaan"),
  N("Semua use case berstatus Tersedia lulus uji alur utama dan alternatif di server dev.", "num"),
  N("lakehouse.py status menunjukkan jumlah baris yang sama dengan katalog dan DBeaver untuk seluruh tabel medallion_repository.", "num"),
  N("CREATE TABLE workspace.<nama> berhasil; penulisan ke schema lain dan koneksi non-Trino ditolak.", "num"),
  N("Pencarian kata kunci (mis. \"risiko\", \"silver\") pada semua jenis aset tidak menghasilkan galat.", "num"),
  N("Tidak ada nama produk upstream pada teks antarmuka, kecuali yang ditetapkan upstream.", "num"),
  N("Backup harian ada dan restore uji berhasil.", "num"),
  N("Fase 2: login IDS berhasil dan akun basic sementara dinonaktifkan.", "num"));

// 9. Isu terbuka
kids.push(H1("9. Isu terbuka dan risiko"),
  table(["ID", "Isu", "Dampak", "Tindak lanjut", "Pemilik"], [
    ["ISU-01", "SELESAI 10-11-2026 — pencarian per jenis aset galat 500 pada OpenSearch 3.2 (bug Lucene 10: script_score di dalam dis_max pada segmen tanpa kecocokan).", "Sudah tidak ada.", "OpenSearch dinaikkan ke 3.4.0 (Lucene 10.3.2) + reindex penuh; 1.056 uji pencarian lulus tanpa shard gagal (NFR-17).", "UV-3"],
    ["ISU-02", "Client IDS dan DNS dev-data.len.co.id belum tersedia.", "Login masih basic auth.", "P2-1, P2-2, lalu UC-54.", "Tim IDS, Jaringan"],
    ["ISU-03", "Workspace memakai satu kredensial Trino bersama.", "Pengguna dapat menimpa tabel kerja pengguna lain.", "Kredensial Trino per pengguna atau impersonation.", "UV-3"],
    ["ISU-04", "Namespace lakekeeper.erm (kosong) diproteksi di Lakekeeper.", "Schema kosong tersisa.", "Admin Lakekeeper melepas proteksi, lalu migrate_legacy_erm.py.", "Admin Lakekeeper"],
    ["ISU-05", "23 cacat workbook (glosarium kosong, tabel Not Found, klasifikasi, kolom kembar).", "Metadata belum lengkap.", "UC-60, UC-35.", "UG-1 / UV-1"],
    ["ISU-06", "Uji mutu baru berupa definisi; belum dieksekusi. Domain, Data Product, Data Contract belum ada.", "Mutu tidak terukur otomatis.", "P4-1.", "UV-1"],
    ["ISU-07", "Hardening akses (self-signup, policy konsumen, jumlah admin).", "Risiko hak berlebih.", "SEC-1 (Manual Pengembang §2.3).", "UV-3"],
  ], [9, 33, 18, 28, 12]));

// lampiran
kids.push(H1("Lampiran A. Ringkasan aktor × use case"),
  table(["Aktor", "Use case"], Object.values(AKTOR).map((a) => [a, UC.filter((u) => u.aktor.includes(a)).map((u) => u.id).join(", ")]), [30, 70]));

// ---------------------------------------------------------------- dokumen
const doc = new Document({
  creator: "Tim Data Governance Len", title: "SRS Len Data Governance", description: "Software Requirements Specification",
  styles: {
    default: { document: { run: { font: FONT, size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 32, bold: true, color: NAVY }, paragraph: { spacing: { before: 240, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 26, bold: true, color: NAVY }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 22, bold: true, color: RED }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullet", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 260 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 300 } } } }] },
  ] },
  features: { updateFields: true },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [t(`SRS Len Data Governance · ${REL}`, { size: 16, color: "838282" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t("Halaman ", { size: 16, color: "838282" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "838282" }), t(" dari ", { size: 16, color: "838282" }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: "838282" })] })] }) },
    children: kids,
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(OUT, b); console.log(`wrote ${OUT} — ${UC.length} use case, ${FR.length} FR, ${NFR.length} NFR`); });
