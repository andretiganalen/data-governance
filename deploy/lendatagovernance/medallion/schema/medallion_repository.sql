-- Skema lakekeeper.medallion_repository (sumber kebenaran). Dipakai oleh medallion/lakehouse.py:
-- tabel yang dikelola loader direvisi (CREATE OR REPLACE) bila kolom/tipe di Trino berbeda dari berkas ini.
-- Tabel bronze_<sumber>_<sheet> (baris mentah) dibuat dinamis oleh loader dan tidak dicantumkan di sini.

CREATE TABLE bronze_meta_quarantine (
   file_id varchar COMMENT 'relasi ke bronze_repository',
   batch_id varchar COMMENT 'uuid batch ingestion',
   source_system varchar COMMENT 'sumber data',
   source_object varchar COMMENT 'objek sumber',
   source_locator varchar COMMENT 'sheet/halaman/rentang tabel',
   source_header varchar COMMENT 'nama header asli dari dokumen sumber',
   normalized_header varchar COMMENT 'header setelah proses normalisasi',
   suggested_field_id varchar COMMENT 'rekomendasi kode FIELD_ID terdekat',
   suggestion_score double COMMENT 'skor kecocokan Levenshtein/Jaro (0.00 - 1.00)',
   sample_values varchar COMMENT 'sampel maksimal 5 nilai data mentah',
   review_status varchar COMMENT 'OPEN | APPROVED | REJECTED',
   ingested_at timestamp(6) with time zone COMMENT 'waktu karantina'
);

CREATE TABLE bronze_repository (
   file_id varchar COMMENT 'sha256[:16] pengenal unik file',
   batch_id varchar COMMENT 'uuid batch ingestion run',
   source_system varchar COMMENT 'DG_WORKBOOK | LENO_ERM | EGRC | SAP | FILE',
   source_object varchar COMMENT 'nama entitas/tabel asal',
   source_format varchar COMMENT 'db|xlsx|csv|gsheet|docx|pdf|pdf_ocr|json',
   file_name varchar COMMENT 'nama berkas fisik/ekspor',
   file_path varchar COMMENT 'lokasi penyimpanan staging',
   file_size_bytes bigint COMMENT 'ukuran berkas dalam bytes',
   file_checksum varchar COMMENT 'sha256 utuh integritas data',
   row_count bigint COMMENT 'jumlah baris diekstrak',
   header_mapped_count integer COMMENT 'jumlah header cocok kontrak',
   header_quarantined_count integer COMMENT 'jumlah header masuk karantina',
   target_bronze_table varchar COMMENT 'tabel tujuan di layer bronze',
   ingestion_status varchar COMMENT 'SUCCESS | PARTIAL | FAILED',
   is_processed_to_silver boolean COMMENT 'flag siap diproses ETL Silver',
   contract_version varchar COMMENT 'versi kontrak aktif mis. v0.2',
   ingested_at timestamp(6) with time zone COMMENT 'waktu pencatatan UTC'
);

CREATE TABLE gold_erm_audit_finding_linkage (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   finding_date date,
   date_key integer,
   audit_finding_id varchar,
   sumber_audit varchar COMMENT 'SPI | KAP | BPK | …',
   risk_id varchar,
   peristiwa_risiko varchar,
   main_category varchar,
   uraian_temuan varchar,
   tingkat_temuan varchar,
   status_tindak_lanjut varchar,
   target_selesai date,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Temuan audit yang dikaitkan ke risiko. Menunggu sumber data.';

CREATE TABLE gold_erm_company_benchmark (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   jumlah_risiko integer,
   jumlah_risiko_high_inheren integer,
   persen_risiko_high_inheren double COMMENT '0–100',
   tingkat_risiko_inheren_rata2 double,
   tingkat_risiko_realisasi_terakhir_rata2 double,
   exposure_inheren_total double COMMENT 'IDR',
   nilai_batasan_risiko double COMMENT 'IDR',
   rasio_inheren_terhadap_batasan double,
   biaya_pengendalian_total double COMMENT 'IDR',
   jumlah_rencana_penanganan integer,
   persen_rencana_ada_progres double COMMENT '0–100',
   peringkat_exposure integer COMMENT '1 = eksposur inheren terbesar',
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Perbandingan antar perusahaan per tahun.';

CREATE TABLE gold_erm_executive_summary_monthly (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   period_date date COMMENT 'Tanggal pertama bulan periode (sumbu waktu grafik)',
   date_key integer COMMENT 'yyyymmdd, FK silver_dim_date',
   period_month integer COMMENT '1–12',
   month_name varchar COMMENT 'Jan…Des',
   quarter_label varchar COMMENT 'TW1…TW4',
   jumlah_risiko integer,
   jumlah_risiko_dilaporkan integer COMMENT 'risiko dengan realisasi bulan ini',
   jumlah_low integer,
   jumlah_low_to_moderate integer,
   jumlah_moderate integer,
   jumlah_moderate_to_high integer,
   jumlah_high integer,
   exposure_target_total double COMMENT 'IDR',
   exposure_realisasi_total double COMMENT 'IDR',
   nilai_batasan_risiko double COMMENT 'IDR',
   rasio_realisasi_terhadap_batasan double,
   jumlah_kri integer,
   jumlah_kri_bahaya integer,
   progres_penanganan_rata2 double COMMENT '0–1',
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Ringkasan eksekutif bulanan per perusahaan: sebaran level, eksposur vs batasan, KRI, progres.';

CREATE TABLE gold_erm_governance_compliance (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   jumlah_risiko integer,
   persen_risiko_ada_penyebab double,
   persen_risiko_ada_rencana double,
   persen_rencana_ada_progres double,
   persen_risiko_ada_target_residual double,
   persen_risiko_ada_realisasi double,
   skor_kepatuhan double COMMENT 'rata-rata lima persentase',
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Kepatuhan pengisian register risiko per perusahaan & tahun (kelengkapan, 0–100).';

CREATE TABLE gold_erm_kri_monitoring_monthly (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   period_date date COMMENT 'Tanggal pertama bulan periode (sumbu waktu grafik)',
   date_key integer COMMENT 'yyyymmdd, FK silver_dim_date',
   period_month integer COMMENT '1–12',
   month_name varchar COMMENT 'Jan…Des',
   quarter_label varchar COMMENT 'TW1…TW4',
   company_is_assumed boolean COMMENT 'TRUE bila sumber tidak mencantumkan entitas (dianggap DEFEND ID)',
   kri_id varchar COMMENT 'RP01…',
   main_category varchar,
   parameter_kri varchar,
   target_formula_kri varchar,
   arah_kri varchar,
   risk_limit_kri double,
   risk_appetite_range_kri varchar,
   risk_tolerance_kri double,
   actual_value_kri double,
   actual_text_kri varchar,
   status_kri varchar COMMENT 'Aman | Hati-hati | Bahaya | Tidak dapat dinilai',
   is_bahaya boolean,
   is_dinilai boolean,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Pemantauan Key Risk Indicator bulanan: nilai aktual vs limit, selera, toleransi.';

CREATE TABLE gold_erm_mitigation_progress_monthly (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   period_date date COMMENT 'Tanggal pertama bulan periode (sumbu waktu grafik)',
   date_key integer COMMENT 'yyyymmdd, FK silver_dim_date',
   period_month integer COMMENT '1–12',
   month_name varchar COMMENT 'Jan…Des',
   quarter_label varchar COMMENT 'TW1…TW4',
   risk_id varchar,
   peristiwa_risiko varchar,
   main_category varchar,
   mitigation_plan_id varchar,
   risk_cause_id varchar,
   penyebab varchar,
   rencana_penanganan varchar,
   pic_fungsi varchar,
   persentase_realisasi double COMMENT '0–1',
   realisasi_penanganan varchar,
   is_dilaporkan boolean,
   status_progres varchar COMMENT 'Belum dilaporkan | Belum mulai | Berjalan | Selesai',
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)',
   _source_system varchar COMMENT 'lineage: EGRC | LENO_ERM (risiko korporat E-GRC vs risiko operasional Aplikasi ERM LenO)'
)
COMMENT 'Progres rencana penanganan risiko per bulan (12 bulan per rencana; is_dilaporkan = ada laporan).';

CREATE TABLE gold_erm_risk_appetite_utilization (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   period_date date COMMENT 'Tanggal pertama bulan periode (sumbu waktu grafik)',
   date_key integer COMMENT 'yyyymmdd, FK silver_dim_date',
   period_month integer COMMENT '1–12',
   month_name varchar COMMENT 'Jan…Des',
   quarter_label varchar COMMENT 'TW1…TW4',
   nilai_kapasitas_risiko double COMMENT 'IDR',
   nilai_selera_risiko double COMMENT 'IDR',
   nilai_toleransi_risiko double COMMENT 'IDR',
   nilai_batasan_risiko double COMMENT 'IDR (limit)',
   exposure_inheren_total double COMMENT 'IDR',
   exposure_target_total double COMMENT 'IDR',
   exposure_realisasi_total double COMMENT 'IDR',
   nilai_dampak_realisasi_total double COMMENT 'IDR',
   rasio_realisasi_terhadap_batasan double,
   rasio_realisasi_terhadap_selera double,
   rasio_inheren_terhadap_batasan double,
   status_utilisasi varchar COMMENT 'Dalam batasan | Dalam selera | Dalam toleransi | Melebihi toleransi | Melebihi kapasitas | Belum dilaporkan',
   jumlah_risiko_dilaporkan integer,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Pemakaian selera risiko bulanan: eksposur dibanding batasan, selera, toleransi, kapasitas.';

CREATE TABLE gold_erm_risk_assessment_monthly (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   period_date date COMMENT 'Tanggal pertama bulan periode (sumbu waktu grafik)',
   date_key integer COMMENT 'yyyymmdd, FK silver_dim_date',
   period_month integer COMMENT '1–12',
   month_name varchar COMMENT 'Jan…Des',
   quarter_label varchar COMMENT 'TW1…TW4',
   risk_id varchar,
   peristiwa_risiko varchar,
   main_category varchar,
   assessment_type varchar COMMENT 'INHEREN | TARGET_RESIDUAL | REALISASI',
   skor_dampak integer,
   skor_kemungkinan integer,
   kemungkinan_pct double COMMENT '0–1',
   tingkat_risiko integer COMMENT '1–25',
   kategori_tingkat_risiko varchar COMMENT 'Low … High',
   urutan_tingkat integer COMMENT '1=Low … 5=High (untuk urutan grafik)',
   nilai_dampak double COMMENT 'IDR',
   dampak_terhadap_limit double COMMENT 'rasio',
   exposure_risiko double COMMENT 'IDR',
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)',
   _source_system varchar COMMENT 'lineage: EGRC | LENO_ERM (risiko korporat E-GRC vs risiko operasional Aplikasi ERM LenO)'
)
COMMENT 'Penilaian risiko bulanan (INHEREN, TARGET_RESIDUAL, REALISASI) per risiko — untuk tren waktu.';

CREATE TABLE gold_erm_risk_heatmap_monthly (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   period_date date COMMENT 'Tanggal pertama bulan periode (sumbu waktu grafik)',
   date_key integer COMMENT 'yyyymmdd, FK silver_dim_date',
   period_month integer COMMENT '1–12',
   month_name varchar COMMENT 'Jan…Des',
   quarter_label varchar COMMENT 'TW1…TW4',
   assessment_type varchar,
   skor_dampak integer COMMENT 'sumbu X',
   skor_kemungkinan integer COMMENT 'sumbu Y',
   tingkat_risiko integer,
   kategori_tingkat_risiko varchar COMMENT 'Low … High',
   urutan_tingkat integer COMMENT '1=Low … 5=High (untuk urutan grafik)',
   warna_hex varchar COMMENT 'warna standar level',
   jumlah_risiko integer,
   daftar_risk_id varchar COMMENT 'dipisah koma',
   total_exposure_risiko double COMMENT 'IDR',
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)',
   _source_system varchar COMMENT 'lineage: EGRC | LENO_ERM (risiko korporat E-GRC vs risiko operasional Aplikasi ERM LenO)'
)
COMMENT 'Peta risiko 5×5 per perusahaan, bulan, dan jenis penilaian: jumlah risiko per sel.';

CREATE TABLE gold_erm_risk_loss_event (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   event_date date,
   date_key integer,
   loss_event_id varchar,
   risk_id varchar,
   peristiwa_risiko varchar,
   main_category varchar,
   deskripsi_kejadian varchar,
   nilai_kerugian double COMMENT 'IDR',
   nilai_pemulihan double COMMENT 'IDR',
   nilai_kerugian_bersih double COMMENT 'IDR',
   status_kejadian varchar,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Kejadian kerugian (loss event) terkait risiko. Menunggu sumber data.';

CREATE TABLE gold_erm_risk_register (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   risk_id varchar COMMENT 'Kode risiko E-GRC (RDF…/RLC…/RLN…)',
   objective_id varchar COMMENT 'FK silver_dim_erm_objective',
   nama_sasaran varchar COMMENT 'Tema sasaran strategis',
   keterangan_sasaran varchar COMMENT 'Uraian sasaran',
   main_category varchar COMMENT 'Taksonomi risiko',
   peristiwa_risiko varchar COMMENT 'Uraian peristiwa risiko',
   deskripsi_dampak varchar,
   asumsi_dampak varchar,
   skor_dampak_inheren integer COMMENT '1–5',
   skor_kemungkinan_inheren integer COMMENT '1–5',
   kemungkinan_pct_inheren double COMMENT 'probabilitas 0–1',
   tingkat_risiko_inheren integer COMMENT 'skor dampak × kemungkinan (1–25)',
   kategori_tingkat_risiko_inheren varchar COMMENT 'Low … High',
   urutan_tingkat_inheren integer COMMENT '1–5',
   nilai_dampak_inheren double COMMENT 'IDR',
   dampak_terhadap_limit_inheren double COMMENT 'rasio',
   exposure_risiko_inheren double COMMENT 'IDR',
   biaya_pengendalian double COMMENT 'IDR',
   periode_realisasi_terakhir date COMMENT 'bulan realisasi terakhir yang dilaporkan',
   skor_dampak_realisasi integer,
   skor_kemungkinan_realisasi integer,
   tingkat_risiko_realisasi integer,
   kategori_tingkat_risiko_realisasi varchar,
   nilai_dampak_realisasi double COMMENT 'IDR',
   exposure_risiko_realisasi double COMMENT 'IDR',
   jumlah_penyebab integer,
   jumlah_rencana_penanganan integer,
   progres_penanganan_rata2 double COMMENT 'rata-rata progres terakhir, 0–1',
   status_aktif varchar COMMENT 'Aktif',
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)',
   _source_system varchar COMMENT 'lineage: EGRC | LENO_ERM (risiko korporat E-GRC vs risiko operasional Aplikasi ERM LenO)'
)
COMMENT 'Register risiko per perusahaan & tahun: inheren, realisasi terakhir, penyebab, penanganan. Satu baris per risiko.';

CREATE TABLE gold_erm_swot_matrix (
   fiscal_year integer COMMENT 'Tahun fiskal RKAP',
   company_id varchar COMMENT 'FK lakekeeper.medallion.silver_dim_company_information',
   company_name varchar COMMENT 'Nama perusahaan',
   company_acronym varchar COMMENT 'Singkatan (LEN, PINDAD, PAL, PTDI, DAHANA, …)',
   holding_name varchar COMMENT 'DEFEND ID',
   objective_id varchar,
   nama_sasaran varchar,
   swot_kuadran varchar COMMENT 'Kekuatan | Kelemahan | Peluang | Ancaman',
   uraian varchar,
   urutan integer,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Matriks SWOT per sasaran. Menunggu sumber data (LenO ERM erm_analisaswot).';

CREATE TABLE gold_meta_access_matrix (
   access_id varchar,
   screen varchar,
   screen_label varchar,
   field_id varchar,
   column_name varchar,
   org_id varchar,
   unit_kerja varchar,
   divisi varchar,
   direktorat varchar,
   classification varchar,
   permission_category varchar,
   permission_type varchar,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Matriks hak akses per layar, kolom, dan unit kerja.';

CREATE TABLE gold_meta_data_dictionary (
   field_id varchar,
   system_name varchar,
   business_domain varchar,
   dataset_name varchar,
   table_name varchar,
   column_name varchar,
   business_term varchar,
   definition varchar,
   data_type varchar,
   classification varchar,
   owner_unit varchar,
   steward_unit varchar,
   user_units varchar,
   dq_rule_count integer,
   dq_rules varchar,
   downstream_screen_count integer,
   has_table boolean,
   has_definition boolean,
   has_classification boolean,
   has_owner boolean,
   completeness_pct double COMMENT '0–100, rata-rata 4 flag',
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Kamus data: satu baris per elemen data (FIELD_ID) dengan kelengkapan tata kelola.';

CREATE TABLE gold_meta_dq_finding_snapshot (
   snapshot_date date,
   source_system varchar COMMENT 'DG_WORKBOOK | EGRC',
   finding_code varchar,
   finding_category varchar,
   severity varchar,
   sheet_name varchar,
   affected_rows integer,
   description varchar,
   example varchar,
   etl_action varchar,
   follow_up_owner varchar,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Temuan mutu data sumber per tanggal muat (riwayat). Satu snapshot per hari.';

CREATE TABLE gold_meta_dq_rule (
   field_id varchar,
   column_name varchar,
   business_term varchar,
   rule varchar,
   validation varchar,
   test_type varchar,
   execution_status varchar,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Aturan mutu data per elemen data dan status eksekusinya.';

CREATE TABLE gold_meta_glossary (
   field_id varchar,
   business_term varchar,
   definition varchar,
   definition_status varchar COMMENT 'Tersedia | Belum ada',
   owner_unit varchar,
   steward_unit varchar,
   user_units varchar,
   column_count integer,
   screen_count integer,
   classification varchar,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Glosarium bisnis dengan status definisi dan pemakaian.';

CREATE TABLE gold_meta_governance_kpi_snapshot (
   snapshot_date date,
   kpi_category varchar,
   kpi_name varchar,
   kpi_value double,
   unit varchar,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'KPI tata kelola per tanggal muat (riwayat, untuk tren). Satu snapshot per hari.';

CREATE TABLE gold_meta_lineage (
   lineage_id varchar,
   system_name varchar,
   business_domain varchar,
   dataset_name varchar,
   table_name varchar,
   column_name varchar,
   field_id varchar,
   business_term varchar,
   module varchar,
   target_screen varchar,
   target_label varchar,
   asset_type varchar,
   classification varchar,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Lineage kolom → layar.';

CREATE TABLE gold_meta_screen_summary (
   module varchar,
   screen varchar,
   field_count integer,
   source_tables varchar,
   source_table_count integer,
   source_datasets varchar,
   highest_classification varchar,
   units_can_view integer,
   units_can_edit integer,
   owner_unit varchar,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Ringkasan per layar/dashboard LenO.';

CREATE TABLE gold_meta_table_summary (
   table_name varchar,
   table_id varchar,
   dataset_name varchar,
   business_domain varchar,
   system_name varchar,
   column_count integer,
   confidential_column_count integer,
   highest_classification varchar,
   owner_unit varchar,
   downstream_screen_count integer,
   definition_pct double COMMENT '0–100',
   dq_rule_count integer,
   _batch_id varchar COMMENT 'lineage: batch loader',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage: waktu muat (UTC)'
)
COMMENT 'Ringkasan per tabel sumber: kolom, sensitivitas, pemilik, layar hilir, % definisi.';

CREATE TABLE silver_dim_company_hierarchy (
   hierarchy_type varchar COMMENT 'REPORTING | LEGAL',
   ancestor_company_id varchar,
   descendant_company_id varchar,
   depth integer,
   is_direct_parent boolean,
   relation_label varchar,
   path_company_ids varchar,
   relation_to_len varchar,
   valid_from date,
   valid_to date,
   is_current boolean,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_date (
   date_key integer COMMENT 'PK yyyymmdd',
   full_date date,
   period_year integer,
   period_quarter integer,
   period_semester integer,
   period_month integer,
   month_name_id varchar COMMENT 'Januari…Desember',
   month_short_id varchar COMMENT 'Jan…Des',
   year_month varchar COMMENT 'yyyy-mm',
   quarter_label varchar COMMENT 'TW1…TW4',
   day_of_month integer,
   day_of_week integer COMMENT '1=Senin',
   day_name_id varchar,
   week_of_year integer,
   is_month_start boolean,
   is_month_end boolean,
   is_weekend boolean,
   is_holiday_id boolean COMMENT 'libur nasional/cuti bersama',
   fiscal_year integer,
   rkap_label varchar COMMENT 'RKAP yyyy'
);

CREATE TABLE silver_dim_erm_control_adequacy (
   control_adequacy_id varchar COMMENT 'PK turunan',
   parameter_kecukupan varchar COMMENT 'F030 – COLUMN_NAME ''Parameter'' konteks kecukupan kontrol',
   urutan_kecukupan integer COMMENT 'turunan untuk sortir',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_control_effectiveness (
   control_effectiveness_id varchar COMMENT 'PK turunan',
   parameter_efektivitas varchar COMMENT 'F029 – COLUMN_NAME ''Parameter'' konteks efektivitas kontrol',
   urutan_efektivitas integer COMMENT 'turunan untuk sortir',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_impact_criteria_qualitative (
   impact_criteria_qualitative_id varchar COMMENT 'PK turunan',
   skor_dampak integer COMMENT 'F009 – rentang 1–5',
   kategori_operasional_proyek varchar COMMENT 'F013 – COLUMN_NAME ''Kategori'' — konteks Operasional/Proyek',
   kriteria_dampak_kualitatif varchar COMMENT 'F023 – COLUMN_NAME ''KriteriaDampak'' konteks kualitatif (konfirmasi K-14)',
   tipe_risiko varchar COMMENT 'F024',
   parameter_dampak_kualitatif varchar COMMENT 'F025 – COLUMN_NAME ''Parameter'' konteks dampak kualitatif',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_impact_criteria_quantitative (
   impact_criteria_quantitative_id varchar COMMENT 'PK turunan',
   skor_dampak integer COMMENT 'F009 – rentang 1–5',
   kriteria_dampak_kuantitatif varchar COMMENT 'F019 – COLUMN_NAME ''KriteriaDampak'' konteks kuantitatif',
   min_dampak bigint COMMENT 'F020 – baseline Integer; BIGINT agar aman untuk nilai rupiah',
   max_dampak bigint COMMENT 'F021 – idem F020',
   deskripsi_dampak varchar COMMENT 'F022',
   currency_code varchar COMMENT 'default IDR',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_likelihood_criteria (
   likelihood_criteria_id varchar COMMENT 'PK turunan',
   kategori_operasional_proyek varchar COMMENT 'F013 – COLUMN_NAME ''Kategori'' — konteks Operasional/Proyek',
   parameter_kemungkinan varchar COMMENT 'F026 – COLUMN_NAME ''Parameter'' konteks kemungkinan',
   kriteria_kemungkinan varchar COMMENT 'F027 – COLUMN_NAME ''Kriteria'' konteks kemungkinan',
   kriteria_dampak_kemungkinan varchar COMMENT 'F028 – COLUMN_NAME ''KriteriaDampak'' konteks kemungkinan (konfirmasi K-14)',
   skor_kemungkinan integer COMMENT 'turunan bila tersedia di sumber',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_objective (
   objective_id varchar COMMENT 'PK',
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   fiscal_year integer,
   nama_sasaran varchar COMMENT 'F014',
   keterangan_sasaran varchar COMMENT 'F031',
   proses_bisnis varchar COMMENT 'F032',
   input_proses varchar COMMENT 'F033',
   output_proses varchar COMMENT 'F034',
   stakeholders_terkait varchar COMMENT 'F035',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_objective_basis (
   objective_basis_id varchar COMMENT 'PK turunan',
   nama_sasaran varchar COMMENT 'F014',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_risk (
   risk_id varchar COMMENT 'PK bisnis (LenO ID / E-GRC RDF…/RLC…/RLN…)',
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   divisi_id varchar COMMENT 'F003 – FK silver_dim_organization (level Divisi)',
   org_id varchar COMMENT 'F004 – FK silver_dim_organization (Bagian = UNIT_KERJA / ORG_ID)',
   objective_id varchar COMMENT 'FK silver_dim_erm_objective',
   fiscal_year integer,
   kategori_operasional_proyek varchar COMMENT 'F013 – konstanta per dataset sumber: erm_riskregister ∈ DS004 Operational Risk Register → ''Operasional''; ''Proyek'' hanya bila tabel DS005 Project Risk Register ditambahkan (konfirmasi K-14)',
   main_category varchar COMMENT 'F006 – Master = teks; transaksi = lookup ke risk_taxonomy',
   sub_category varchar COMMENT 'F007 – idem F006',
   kriteria_dampak_kualitatif varchar COMMENT 'F023 – COLUMN_NAME ''KriteriaDampak'' konteks kualitatif (konfirmasi K-14)',
   keterangan_sasaran varchar COMMENT 'F031',
   peristiwa_risiko varchar COMMENT 'F036',
   peluang_terjadi varchar COMMENT 'F037 – COLUMN_NAME ''Peluang'' = Kemungkinan terjadi (bukan SWOT)',
   asumsi_dampak varchar COMMENT 'X004 – E-GRC: Asumsi Dampak',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   deskripsi_dampak varchar COMMENT 'F022 – E-GRC: Deskripsi Dampak',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_risk_cause (
   risk_cause_id varchar COMMENT 'PK',
   risk_id varchar COMMENT 'FK',
   divisi_id varchar COMMENT 'F003 – FK silver_dim_organization (level Divisi)',
   cause_seq integer COMMENT 'urutan penyebab',
   penyebab varchar COMMENT 'F038',
   dampak varchar COMMENT 'F039',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_risk_matrix (
   risk_matrix_id varchar COMMENT 'PK turunan',
   kategori_operasional_proyek varchar COMMENT 'F013 – COLUMN_NAME ''Kategori'' — konteks Operasional/Proyek',
   skor_dampak integer COMMENT 'F009 – rentang 1–5',
   skor_kemungkinan integer COMMENT 'F010 – rentang 1–5',
   tingkat_risiko integer COMMENT 'F011 – = skor_dampak × skor_kemungkinan (auto calculated)',
   kategori_tingkat_risiko varchar COMMENT 'F012 – lookup matriks (Low … High)',
   kategori_tingkat_risiko_color_hex varchar COMMENT 'turunan: warna standar level',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_erm_risk_taxonomy (
   risk_taxonomy_id varchar COMMENT 'PK turunan',
   main_category varchar COMMENT 'F006 – Master = teks; transaksi = lookup ke risk_taxonomy',
   sub_category varchar COMMENT 'F007 – idem F006',
   definisi_kategori varchar COMMENT 'F008 – COLUMN_NAME ''Definisi'' konteks uraian kategori/taksonomi risiko',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_fx_rate (
   currency_code varchar COMMENT 'ISO 4217',
   rate_date date,
   fx_rate_to_idr double COMMENT '1 untuk IDR',
   rate_source varchar COMMENT 'sumber kurs',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_access (
   access_id varchar COMMENT 'baseline header ''ACCESS_ID''',
   lineage_id varchar COMMENT 'baseline header ''LINEAGE_ID''',
   target_asset varchar COMMENT 'baseline header ''TARGET_ASSET''',
   target_label varchar COMMENT 'baseline header ''TARGET_LABEL''',
   field_id varchar COMMENT 'baseline header ''FIELD_ID''',
   field_name varchar COMMENT 'baseline header ''FIELD_NAME''',
   org_id varchar COMMENT 'baseline header ''ORG_ID''',
   unit_kerja varchar COMMENT 'baseline header ''UNIT_KERJA''',
   classification varchar COMMENT 'baseline header ''CLASSIFICATION''',
   permission_category varchar COMMENT 'baseline header ''PERMISSION_CATEGORY''',
   permission_type varchar COMMENT 'baseline header ''PERMISSION_TYPE''',
   role_name varchar COMMENT 'baseline header ''ROLE_NAME''',
   access_purpose varchar COMMENT 'baseline header ''ACCESS_PURPOSE''',
   approval_status varchar COMMENT 'baseline header ''APPROVAL_STATUS''',
   approver varchar COMMENT 'baseline header ''APPROVER''',
   grant_date date COMMENT 'baseline header ''GRANT_DATE''',
   review_date date COMMENT 'baseline header ''REVIEW_DATE''',
   last_review_result varchar COMMENT 'baseline header ''LAST_REVIEW_RESULT''',
   evidence varchar COMMENT 'baseline header ''EVIDENCE''',
   exception_flag boolean COMMENT 'baseline header ''EXCEPTION_FLAG''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_data_domain (
   data_domain_id varchar COMMENT 'baseline header ''DATA_DOMAIN_ID''',
   data_domain varchar COMMENT 'baseline header ''DATA_DOMAIN''',
   description varchar COMMENT 'baseline header ''DESCRIPTION''',
   business_owner varchar COMMENT 'baseline header ''BUSINESS_OWNER''',
   data_steward varchar COMMENT 'baseline header ''DATA_STEWARD''',
   criticality varchar COMMENT 'baseline header ''CRITICALITY''',
   classification varchar COMMENT 'baseline header ''CLASSIFICATION''',
   system_count bigint COMMENT 'baseline header ''SYSTEM_COUNT''',
   dataset_count bigint COMMENT 'baseline header ''DATASET_COUNT''',
   table_count bigint COMMENT 'baseline header ''TABLE_COUNT''',
   field_count bigint COMMENT 'baseline header ''FIELD_COUNT''',
   dq_rule_count bigint COMMENT 'baseline header ''DQ_RULE_COUNT''',
   dq_coverage double COMMENT 'baseline header ''DQ_COVERAGE''',
   domain_status varchar COMMENT 'baseline header ''DOMAIN_STATUS''',
   evidence varchar COMMENT 'baseline header ''EVIDENCE''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_dataset (
   dataset_id varchar COMMENT 'baseline header ''DATASET_ID''',
   dataset_name varchar COMMENT 'baseline header ''DATASET_NAME''',
   business_dataset varchar COMMENT 'baseline header ''BUSINESS_DATASET''',
   business_domain varchar COMMENT 'baseline header ''BUSINESS_DOMAIN''',
   system_id varchar COMMENT 'baseline header ''SYSTEM_ID''',
   system_name varchar COMMENT 'baseline header ''SYSTEM_NAME''',
   data_domain_id varchar COMMENT 'baseline header ''DATA_DOMAIN_ID''',
   data_domain varchar COMMENT 'baseline header ''DATA_DOMAIN''',
   subdomain varchar COMMENT 'baseline header ''SUBDOMAIN''',
   data_owner varchar COMMENT 'baseline header ''DATA_OWNER''',
   data_steward varchar COMMENT 'baseline header ''DATA_STEWARD''',
   criticality varchar COMMENT 'baseline header ''CRITICALITY''',
   classification varchar COMMENT 'baseline header ''CLASSIFICATION''',
   record_count bigint COMMENT 'baseline header ''RECORD_COUNT''',
   data_asset_status varchar COMMENT 'baseline header ''DATA_ASSET_STATUS''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_dq_dimension (
   dq_id varchar COMMENT 'baseline header ''DQ_ID''',
   dimension varchar COMMENT 'baseline header ''DIMENSION''',
   sub_dimension varchar COMMENT 'baseline header ''SUB_DIMENSION''',
   definition varchar COMMENT 'baseline header ''DEFINITION''',
   what_to_check varchar COMMENT 'baseline header ''WHAT_TO_CHECK''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_dq_rule (
   field_id varchar COMMENT 'baseline header ''FIELD_ID''',
   field_name varchar COMMENT 'baseline header ''FIELD_NAME''',
   business_term varchar COMMENT 'baseline header ''BUSINESS_TERM''',
   rule varchar COMMENT 'baseline header ''RULE''',
   validation varchar COMMENT 'baseline header ''VALIDATION''',
   dq_rule_id varchar COMMENT 'baseline header ''DQ_RULE_ID''',
   dq_dimension varchar COMMENT 'baseline header ''DQ_DIMENSION''',
   sub_dimension varchar COMMENT 'baseline header ''SUB_DIMENSION''',
   target_table varchar COMMENT 'baseline header ''TARGET_TABLE''',
   target_column varchar COMMENT 'baseline header ''TARGET_COLUMN''',
   rule_type varchar COMMENT 'baseline header ''RULE_TYPE''',
   threshold double COMMENT 'baseline header ''THRESHOLD''',
   measurement_method varchar COMMENT 'baseline header ''MEASUREMENT_METHOD''',
   result_value double COMMENT 'baseline header ''RESULT_VALUE''',
   pass_fail varchar COMMENT 'baseline header ''PASS_FAIL''',
   check_date date COMMENT 'baseline header ''CHECK_DATE''',
   check_frequency varchar COMMENT 'baseline header ''CHECK_FREQUENCY''',
   severity varchar COMMENT 'baseline header ''SEVERITY''',
   evidence varchar COMMENT 'baseline header ''EVIDENCE''',
   remediation_status varchar COMMENT 'baseline header ''REMEDIATION_STATUS''',
   remediation_owner varchar COMMENT 'baseline header ''REMEDIATION_OWNER''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_field (
   field_id varchar COMMENT 'baseline header ''FIELD_ID''',
   table_id varchar COMMENT 'baseline header ''TABLE_ID''',
   table_name varchar COMMENT 'baseline header ''TABLE_NAME''',
   column_name varchar COMMENT 'baseline header ''COLUMN_NAME''',
   data_dictionary_description varchar COMMENT 'baseline header ''DATA_DICTIONARY_DESCRIPTION''',
   business_term varchar COMMENT 'baseline header ''BUSINESS_TERM''',
   data_type varchar COMMENT 'baseline header ''DATA_TYPE''',
   sensitive_flag boolean COMMENT 'baseline header ''SENSITIVE_FLAG''',
   critical_data_element boolean COMMENT 'baseline header ''CRITICAL_DATA_ELEMENT''',
   nullable_flag boolean COMMENT 'baseline header ''NULLABLE_FLAG''',
   pk_flag boolean COMMENT 'baseline header ''PK_FLAG''',
   fk_flag boolean COMMENT 'baseline header ''FK_FLAG''',
   unique_flag boolean COMMENT 'baseline header ''UNIQUE_FLAG''',
   length_bytes integer COMMENT 'baseline header ''LENGTH_BYTES''',
   length integer COMMENT 'baseline header ''LENGTH''',
   precision integer COMMENT 'baseline header ''PRECISION''',
   scale integer COMMENT 'baseline header ''SCALE''',
   default_value varchar COMMENT 'baseline header ''DEFAULT_VALUE''',
   dq_dimension_primary varchar COMMENT 'baseline header ''DQ_DIMENSION_PRIMARY''',
   dq_score double COMMENT 'baseline header ''DQ_SCORE''',
   dq_status varchar COMMENT 'baseline header ''DQ_STATUS''',
   metadata_status varchar COMMENT 'baseline header ''METADATA_STATUS''',
   source_system varchar COMMENT 'baseline header ''SOURCE_SYSTEM''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_field_alias (
   alias_id varchar COMMENT 'baseline header ''ALIAS_ID''',
   field_id varchar COMMENT 'baseline header ''FIELD_ID''',
   source_system varchar COMMENT 'baseline header ''SOURCE_SYSTEM''',
   source_object varchar COMMENT 'baseline header ''SOURCE_OBJECT''',
   source_header varchar COMMENT 'baseline header ''SOURCE_HEADER''',
   normalized_header varchar COMMENT 'baseline header ''NORMALIZED_HEADER''',
   match_rule varchar COMMENT 'baseline header ''MATCH_RULE''',
   transform_rule varchar COMMENT 'baseline header ''TRANSFORM_RULE''',
   alias_status varchar COMMENT 'baseline header ''ALIAS_STATUS''',
   approved_by_role varchar COMMENT 'baseline header ''APPROVED_BY_ROLE''',
   contract_version varchar COMMENT 'baseline header ''CONTRACT_VERSION''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_glossary (
   field_id varchar COMMENT 'baseline header ''FIELD_ID''',
   business_term varchar COMMENT 'baseline header ''BUSINESS_TERM''',
   definisi varchar COMMENT 'baseline header ''DEFINISI''',
   domain varchar COMMENT 'baseline header ''DOMAIN''',
   subdomain varchar COMMENT 'baseline header ''SUBDOMAIN''',
   owner varchar COMMENT 'baseline header ''OWNER''',
   steward varchar COMMENT 'baseline header ''STEWARD''',
   status varchar COMMENT 'baseline header ''STATUS''',
   approval_date date COMMENT 'baseline header ''APPROVAL_DATE''',
   source_reference varchar COMMENT 'baseline header ''SOURCE_REFERENCE''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_governance_assignment (
   field_id varchar COMMENT 'baseline header ''FIELD_ID''',
   field_name varchar COMMENT 'baseline header ''FIELD_NAME''',
   business_term varchar COMMENT 'baseline header ''BUSINESS_TERM''',
   role varchar COMMENT 'baseline header ''ROLE''',
   org_id varchar COMMENT 'baseline header ''ORG_ID''',
   unit_kerja varchar COMMENT 'baseline header ''UNIT KERJA''',
   dataset_id varchar COMMENT 'baseline header ''DATASET_ID''',
   data_domain varchar COMMENT 'baseline header ''DATA_DOMAIN''',
   subdomain varchar COMMENT 'baseline header ''SUBDOMAIN''',
   role_status varchar COMMENT 'baseline header ''ROLE_STATUS''',
   assignment_date date COMMENT 'baseline header ''ASSIGNMENT_DATE''',
   review_date date COMMENT 'baseline header ''REVIEW_DATE''',
   evidence varchar COMMENT 'baseline header ''EVIDENCE''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_kpi (
   kpi_id varchar COMMENT 'baseline header ''KPI_ID''',
   kpi_name varchar COMMENT 'baseline header ''KPI_NAME''',
   category varchar COMMENT 'baseline header ''CATEGORY''',
   definition varchar COMMENT 'baseline header ''DEFINITION''',
   formula varchar COMMENT 'baseline header ''FORMULA''',
   target varchar COMMENT 'baseline header ''TARGET''',
   frequency varchar COMMENT 'baseline header ''FREQUENCY''',
   data_source varchar COMMENT 'baseline header ''DATA_SOURCE''',
   owner varchar COMMENT 'baseline header ''OWNER''',
   evidence varchar COMMENT 'baseline header ''EVIDENCE''',
   status varchar COMMENT 'baseline header ''STATUS''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_library (
   library_group varchar COMMENT 'baseline header ''LIBRARY_GROUP''',
   item varchar COMMENT 'baseline header ''ITEM''',
   deskripsi varchar COMMENT 'baseline header ''DESKRIPSI''',
   permission_category varchar COMMENT 'baseline header ''PERMISSION_CATEGORY''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_lineage (
   lineage_id varchar COMMENT 'baseline header ''LINEAGE_ID''',
   system_id varchar COMMENT 'baseline header ''SYSTEM_ID''',
   system_name varchar COMMENT 'baseline header ''SYSTEM_NAME''',
   table_id varchar COMMENT 'baseline header ''TABLE_ID''',
   table_name varchar COMMENT 'baseline header ''TABLE_NAME''',
   field_id varchar COMMENT 'baseline header ''FIELD_ID''',
   field_name varchar COMMENT 'baseline header ''FIELD_NAME''',
   target_asset varchar COMMENT 'baseline header ''TARGET_ASSET''',
   target_label varchar COMMENT 'baseline header ''TARGET_LABEL''',
   asset_type varchar COMMENT 'baseline header ''ASSET_TYPE''',
   source_system varchar COMMENT 'baseline header ''SOURCE_SYSTEM''',
   source_database varchar COMMENT 'baseline header ''SOURCE_DATABASE''',
   source_schema varchar COMMENT 'baseline header ''SOURCE_SCHEMA''',
   source_table varchar COMMENT 'baseline header ''SOURCE_TABLE''',
   source_column varchar COMMENT 'baseline header ''SOURCE_COLUMN''',
   transformation_logic varchar COMMENT 'baseline header ''TRANSFORMATION_LOGIC''',
   lineage_type varchar COMMENT 'baseline header ''LINEAGE_TYPE''',
   target_system varchar COMMENT 'baseline header ''TARGET_SYSTEM''',
   target_database varchar COMMENT 'baseline header ''TARGET_DATABASE''',
   target_schema varchar COMMENT 'baseline header ''TARGET_SCHEMA''',
   target_table varchar COMMENT 'baseline header ''TARGET_TABLE''',
   target_column varchar COMMENT 'baseline header ''TARGET_COLUMN''',
   confidence varchar COMMENT 'baseline header ''CONFIDENCE''',
   evidence varchar COMMENT 'baseline header ''EVIDENCE''',
   status varchar COMMENT 'baseline header ''STATUS''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_system (
   system_id varchar COMMENT 'baseline header ''SYSTEM_ID''',
   system_name varchar COMMENT 'baseline header ''SYSTEM_NAME''',
   description varchar COMMENT 'baseline header ''DESCRIPTION''',
   application_type varchar COMMENT 'baseline header ''APPLICATION_TYPE''',
   lifecycle_status varchar COMMENT 'baseline header ''LIFECYCLE_STATUS''',
   criticality varchar COMMENT 'baseline header ''CRITICALITY''',
   business_owner varchar COMMENT 'baseline header ''BUSINESS_OWNER''',
   data_owner varchar COMMENT 'baseline header ''DATA_OWNER''',
   data_steward varchar COMMENT 'baseline header ''DATA_STEWARD''',
   technical_owner varchar COMMENT 'baseline header ''TECHNICAL_OWNER''',
   database_platform varchar COMMENT 'baseline header ''DATABASE_PLATFORM''',
   data_classification varchar COMMENT 'baseline header ''DATA_CLASSIFICATION''',
   dm_assessment_status varchar COMMENT 'baseline header ''DM_ASSESSMENT_STATUS''',
   last_review_date date COMMENT 'baseline header ''LAST_REVIEW_DATE''',
   evidence_source varchar COMMENT 'baseline header ''EVIDENCE_SOURCE''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_meta_table (
   table_id varchar COMMENT 'baseline header ''TABLE_ID''',
   dataset_id varchar COMMENT 'baseline header ''DATASET_ID''',
   dataset_name varchar COMMENT 'baseline header ''DATASET_NAME''',
   table_name varchar COMMENT 'baseline header ''TABLE_NAME''',
   object_type varchar COMMENT 'baseline header ''OBJECT_TYPE''',
   database_name varchar COMMENT 'baseline header ''DATABASE_NAME''',
   object_owner varchar COMMENT 'baseline header ''OBJECT_OWNER''',
   row_count bigint COMMENT 'baseline header ''ROW_COUNT''',
   sensitive_data_flag boolean COMMENT 'baseline header ''SENSITIVE_DATA_FLAG''',
   critical_data_flag boolean COMMENT 'baseline header ''CRITICAL_DATA_FLAG''',
   last_profile_date date COMMENT 'baseline header ''LAST_PROFILE_DATE''',
   business_form_procedure varchar COMMENT 'baseline header ''BUSINESS_ FORM_PROCEDURE''',
   source_system varchar COMMENT 'baseline header ''SOURCE_SYSTEM''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_dim_organization (
   org_id varchar COMMENT 'ORG_ID (PK bisnis)',
   fungsi varchar COMMENT 'FUNGSI',
   unit_kerja varchar COMMENT 'UNIT_KERJA = Bagian',
   divisi_id varchar COMMENT 'turunan slug DIVISI',
   divisi varchar COMMENT 'DIVISI',
   direktorat_id varchar COMMENT 'turunan slug DIREKTORAT',
   direktorat varchar COMMENT 'DIREKTORAT',
   company_id varchar COMMENT 'default PT Len Industri (Persero)',
   valid_from date COMMENT 'SCD2',
   valid_to date COMMENT 'SCD2 (9999-12-31 = aktif)',
   is_current boolean COMMENT 'SCD2',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_erm_existing_control (
   existing_control_id varchar COMMENT 'PK',
   risk_id varchar COMMENT 'FK',
   risk_cause_id varchar COMMENT 'FK',
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   period_year integer,
   existing_control varchar COMMENT 'F045 – COLUMN_NAME ''Existing''',
   parameter_efektivitas varchar COMMENT 'F029 – COLUMN_NAME ''Parameter'' konteks efektivitas kontrol',
   parameter_kecukupan varchar COMMENT 'F030 – COLUMN_NAME ''Parameter'' konteks kecukupan kontrol',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_erm_kri_monthly (
   kri_id varchar COMMENT 'RP01…',
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   company_id_is_assumed boolean COMMENT 'sheet tanpa Entity → DEFEND ID',
   risk_id varchar COMMENT 'FK – pemetaan KRI → risiko (tabel pemetaan disetujui Risk Management)',
   org_id varchar COMMENT 'FK – unit pemilik KRI bila tersedia',
   period_year integer,
   period_month integer COMMENT '1–12',
   date_key integer COMMENT 'yyyymmdd hari pertama bulan',
   main_category varchar COMMENT 'F006 – Master = teks; transaksi = lookup ke risk_taxonomy',
   parameter_kri varchar COMMENT 'X006 – E-GRC Risk Profile: Risk Parameter (KRI)',
   target_formula_kri varchar COMMENT 'X007 – E-GRC Risk Profile: Target',
   risk_limit_kri double COMMENT 'X008 – E-GRC Risk Profile: Risk Limit',
   risk_appetite_range_kri varchar COMMENT 'X009 – E-GRC Risk Profile: Risk Appetite',
   risk_tolerance_kri double COMMENT 'X010 – E-GRC Risk Profile: Risk Tolerance',
   actual_value_kri double COMMENT 'X011 – E-GRC Risk Profile: Aktual <bulan>',
   status_kri varchar COMMENT 'X012 – E-GRC Risk Profile: Status (Bahaya/Aman)',
   actual_text_kri varchar COMMENT 'X011 – nilai aktual berupa teks bila bukan angka',
   arah_kri varchar COMMENT 'E-GRC: arah parameter (makin tinggi makin buruk / makin baik)',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_erm_mitigation_plan_monthly (
   mitigation_plan_id varchar COMMENT 'PK rencana',
   risk_id varchar COMMENT 'FK',
   risk_cause_id varchar COMMENT 'FK bila ada',
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   period_year integer,
   period_month integer COMMENT '1–12',
   date_key integer COMMENT 'yyyymmdd hari pertama bulan',
   rencana_penanganan varchar COMMENT 'F046',
   target_waktu_penyelesaian date COMMENT 'F047 – ≥ tanggal mulai',
   anggaran_penanganan decimal(20, 2) COMMENT 'F048 – + currency_code',
   currency_code varchar,
   fx_rate_to_idr double COMMENT 'dari silver_dim_fx_rate',
   is_rencana_bulan boolean COMMENT 'F049–F060 – Bulan1…Bulan12 di-unpivot: 1 baris per bulan, period_month = N (Bulan1 = Januari)',
   source_month_column varchar COMMENT 'Bulan1…Bulan12 (jejak header asli)',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_erm_mitigation_realization (
   mitigation_plan_id varchar COMMENT 'FK',
   risk_id varchar COMMENT 'FK',
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   period_year integer,
   period_month integer COMMENT '1–12',
   date_key integer COMMENT 'yyyymmdd hari pertama bulan',
   realisasi_penanganan varchar COMMENT 'F061',
   persentase_realisasi decimal(9, 6) COMMENT 'F062 – disimpan fraksi 0–1',
   penggunaan_anggaran decimal(20, 2) COMMENT 'F063 – + currency_code',
   currency_code varchar,
   fx_rate_to_idr double COMMENT 'dari silver_dim_fx_rate',
   status_penanganan_risiko varchar COMMENT 'F064 – lookup',
   dokumen_path varchar COMMENT 'F065 – BLOB → path evidence + dokumen_sha256',
   dokumen_sha256 varchar COMMENT 'checksum dokumen',
   alasan_tidak_direalisasikan varchar COMMENT 'F066',
   persentase_biaya_pengendalian decimal(9, 6) COMMENT 'X005 – E-GRC: Realisasi % Biaya Pengendalian',
   pic_fungsi varchar COMMENT 'X013 – E-GRC Pengendalian: PIC/Fungsi (kode fungsi, mis. MSC, BDGP)',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_erm_risk_appetite (
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   period_year integer,
   date_key integer COMMENT 'yyyy0101',
   plan_label varchar COMMENT 'RKAP yyyy',
   nilai_kapasitas_risiko decimal(20, 2) COMMENT 'F015 – + currency_code',
   nilai_selera_risiko decimal(20, 2) COMMENT 'F016 – + currency_code',
   nilai_toleransi_risiko decimal(20, 2) COMMENT 'F017 – + currency_code',
   nilai_batasan_risiko decimal(20, 2) COMMENT 'F018 – + currency_code',
   currency_code varchar COMMENT 'IDR/USD',
   fx_rate_to_idr double COMMENT '1 untuk IDR',
   amount_unit varchar COMMENT 'IDR | IDR_THOUSAND',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_erm_risk_assessment (
   risk_id varchar COMMENT 'FK',
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   assessment_type varchar COMMENT 'INHEREN | RESIDUAL | TARGET_RESIDUAL | REALISASI',
   period_year integer,
   period_month integer COMMENT '1–12',
   date_key integer COMMENT 'yyyymmdd hari pertama bulan',
   skor_dampak integer COMMENT 'F009 – rentang 1–5',
   skor_kemungkinan integer COMMENT 'F010 – rentang 1–5',
   tingkat_risiko integer COMMENT 'F011 – = skor_dampak × skor_kemungkinan (auto calculated)',
   kategori_tingkat_risiko varchar COMMENT 'F012 – lookup matriks (Low … High)',
   kriteria_dampak_kuantitatif varchar COMMENT 'F019 – COLUMN_NAME ''KriteriaDampak'' konteks kuantitatif',
   min_dampak bigint COMMENT 'F020 – baseline Integer; BIGINT agar aman untuk nilai rupiah',
   max_dampak bigint COMMENT 'F021 – idem F020',
   deskripsi_dampak varchar COMMENT 'F022',
   kriteria_dampak_kualitatif varchar COMMENT 'F023 – COLUMN_NAME ''KriteriaDampak'' konteks kualitatif (konfirmasi K-14)',
   parameter_dampak_kualitatif varchar COMMENT 'F025 – COLUMN_NAME ''Parameter'' konteks dampak kualitatif',
   parameter_kemungkinan varchar COMMENT 'F026 – COLUMN_NAME ''Parameter'' konteks kemungkinan',
   kriteria_kemungkinan varchar COMMENT 'F027 – COLUMN_NAME ''Kriteria'' konteks kemungkinan',
   kriteria_dampak_kemungkinan varchar COMMENT 'F028 – COLUMN_NAME ''KriteriaDampak'' konteks kemungkinan (konfirmasi K-14)',
   tipe_risiko varchar COMMENT 'F024 – dari kriteria dampak kualitatif terpilih',
   dampak_finansial decimal(20, 2) COMMENT 'F040 – + currency_code (residual)',
   currency_code varchar,
   fx_rate_to_idr double COMMENT 'dari silver_dim_fx_rate',
   nilai_dampak decimal(20, 2) COMMENT 'X001 – E-GRC: Dampak Inheren / Target Dampak Residual / Realisasi Nilai Dampak',
   dampak_terhadap_limit decimal(9, 6) COMMENT 'X002 – E-GRC: Dampak terhadap Limit (fraksi)',
   exposure_risiko decimal(20, 2) COMMENT 'X003 – E-GRC: Exposure Risiko',
   kemungkinan_pct decimal(9, 6) COMMENT 'X014 – E-GRC: Kemungkinan (probabilitas, fraksi 0–1)',
   biaya_pengendalian decimal(20, 2) COMMENT 'E-GRC: Biaya Pengendalian (IDR, hanya baris INHEREN)',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_erm_swot_analysis (
   swot_id varchar COMMENT 'PK',
   company_id varchar COMMENT 'F001 – FK silver_dim_company_information (label ''Perusahaan'')',
   objective_id varchar COMMENT 'FK bila ada',
   period_year integer,
   swot_kekuatan varchar COMMENT 'F041 – COLUMN_NAME ''Kekuatan'' konteks SWOT',
   swot_kelemahan varchar COMMENT 'F042 – konteks SWOT',
   swot_peluang varchar COMMENT 'F043 – COLUMN_NAME ''Peluang'' konteks SWOT (opportunity)',
   swot_ancaman varchar COMMENT 'F044 – konteks SWOT',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_meta_baseline_correction (
   correction_id varchar COMMENT 'baseline header ''CORRECTION_ID''',
   baseline_file varchar COMMENT 'baseline header ''BASELINE_FILE''',
   baseline_sha256 varchar COMMENT 'baseline header ''BASELINE_SHA256''',
   sheet_name varchar COMMENT 'baseline header ''SHEET_NAME''',
   cell_range varchar COMMENT 'baseline header ''CELL_RANGE''',
   issue_type varchar COMMENT 'baseline header ''ISSUE_TYPE''',
   original_formula varchar COMMENT 'baseline header ''ORIGINAL_FORMULA''',
   original_value varchar COMMENT 'baseline header ''ORIGINAL_VALUE''',
   proposed_formula varchar COMMENT 'baseline header ''PROPOSED_FORMULA''',
   proposed_value varchar COMMENT 'baseline header ''PROPOSED_VALUE''',
   rule_id varchar COMMENT 'baseline header ''RULE_ID''',
   decision varchar COMMENT 'baseline header ''DECISION''',
   decision_role varchar COMMENT 'baseline header ''DECISION_ROLE''',
   derived_file varchar COMMENT 'baseline header ''DERIVED_FILE''',
   note varchar COMMENT 'baseline header ''NOTE''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

CREATE TABLE silver_fact_meta_dq_result (
   dq_assessment_id varchar COMMENT 'baseline header ''DQ_ASSESSMENT_ID''',
   data_domain varchar COMMENT 'baseline header ''DATA_DOMAIN''',
   system_id varchar COMMENT 'baseline header ''SYSTEM_ID''',
   table_id varchar COMMENT 'baseline header ''TABLE_ID''',
   field_id varchar COMMENT 'baseline header ''FIELD_ID''',
   table_name varchar COMMENT 'baseline header ''TABLE_NAME''',
   field_name varchar COMMENT 'baseline header ''FIELD_NAME''',
   dq_dimension varchar COMMENT 'baseline header ''DQ_DIMENSION''',
   dq_sub_dimension varchar COMMENT 'baseline header ''DQ_SUB_DIMENSION''',
   rule_id varchar COMMENT 'baseline header ''RULE_ID''',
   total_records bigint COMMENT 'baseline header ''TOTAL_RECORDS''',
   failed_records bigint COMMENT 'baseline header ''FAILED_RECORDS''',
   pass_rate double COMMENT 'baseline header ''PASS_RATE''',
   threshold double COMMENT 'baseline header ''THRESHOLD''',
   status varchar COMMENT 'baseline header ''STATUS''',
   severity varchar COMMENT 'baseline header ''SEVERITY''',
   check_date date COMMENT 'baseline header ''CHECK_DATE''',
   evidence varchar COMMENT 'baseline header ''EVIDENCE''',
   remediation_owner varchar COMMENT 'baseline header ''REMEDIATION_OWNER''',
   remediation_status varchar COMMENT 'baseline header ''REMEDIATION_STATUS''',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_ERM | EGRC | FILE',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
);

-- ==== Data ERM lama (pipeline sebelum Len Data Governance), dipindah 2026-11-10 dari lakekeeper.erm/erm_bronze/erm_silver
-- oleh medallion/migrate_legacy_erm.py. Isi apa adanya; tidak dikelola loader (tidak pernah ditimpa).

CREATE TABLE bronze_erm_iro (
   kategori varchar,
   divisi varchar,
   unit_kerja varchar,
   target varchar,
   risiko varchar,
   penyebab varchar,
   uraian_dampak varchar,
   kontrol_eksisting varchar,
   efektifitas_kontrol varchar,
   nilai_dampak varchar,
   skor_dampak bigint,
   skor_kemungkinan bigint,
   tingkat_risiko bigint,
   kategori_tingkat_risiko varchar,
   rencana_penanganan varchar,
   anggaran varchar,
   unit_kerja_terkait varchar,
   target_penyelesaian date,
   peluang varchar,
   realisasi_penanganan double,
   realisasi1 double,
   realisasi2 double,
   realisasi3 double,
   realisasi4 double,
   realisasi5 double,
   realisasi6 double,
   realisasi7 double,
   realisasi8 double,
   realisasi9 double,
   realisasi10 double,
   realisasi11 double,
   realisasi12 double,
   realisasi_sd double,
   skor_dampak_residual bigint,
   skor_kemungkinan_residual bigint,
   tingkat_risiko_residual bigint,
   kategori_tingkat_risiko_residual varchar,
   status varchar,
   tahun bigint
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm.iro pada 2026-11-10 (apa adanya).';

CREATE TABLE bronze_erm_ingest_file_registry (
   source_file_name varchar,
   file_modified_at timestamp(6) with time zone,
   snapshot_date date,
   tahun bigint,
   registered_at timestamp(6) with time zone
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_bronze.ingest_file_registry pada 2026-11-10 (apa adanya).';

CREATE TABLE bronze_erm_risk_control (
   id_risiko varchar,
   risiko varchar,
   id_penyebab bigint,
   penyebab varchar,
   id_rencana_pengendalian double,
   rencana_pengendalian varchar,
   pic_fungsi varchar,
   realisasi_jan varchar,
   percent_progress_jan double,
   realisasi_feb varchar,
   percent_progress_feb varchar,
   realisasi_mar varchar,
   percent_progress_mar varchar,
   realisasi_apr varchar,
   percent_progress_apr varchar,
   realisasi_mei varchar,
   percent_progress_mei varchar,
   realisasi_jun varchar,
   percent_progress_jun varchar,
   realisasi_jul varchar,
   percent_progress_jul varchar,
   realisasi_agu varchar,
   percent_progress_agu varchar,
   realisasi_sep varchar,
   percent_progress_sep varchar,
   realisasi_okt varchar,
   percent_progress_okt varchar,
   realisasi_nov varchar,
   percent_progress_nov varchar,
   realisasi_des varchar,
   percent_progress_des varchar,
   source_file_name varchar,
   snapshot_date date,
   file_modified_at timestamp(6) with time zone,
   ingestion_timestamp timestamp(6) with time zone,
   tahun bigint
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_bronze.pengendalian_risiko pada 2026-11-10 (apa adanya).';

CREATE TABLE bronze_erm_risk_profile (
   id_risk_profile varchar,
   taksonomi varchar,
   risk_parameter varchar,
   target varchar,
   risk_limit varchar,
   risk_appetite varchar,
   risk_tolerance varchar,
   aktual_jan varchar,
   aktual_feb varchar,
   aktual_mar varchar,
   aktual_apr varchar,
   aktual_mei varchar,
   aktual_jun varchar,
   aktual_jul varchar,
   aktual_agu varchar,
   aktual_sep varchar,
   aktual_okt varchar,
   aktual_nov varchar,
   aktual_des varchar,
   status varchar,
   penyebab_risiko varchar,
   rencana_pengendalian varchar,
   source_file_name varchar,
   snapshot_date date,
   file_modified_at timestamp(6) with time zone,
   ingestion_timestamp timestamp(6) with time zone,
   tahun bigint
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_bronze.risk_profile pada 2026-11-10 (apa adanya).';

CREATE TABLE bronze_erm_risk_register (
   risk_id varchar,
   entity varchar,
   strategic_objective varchar,
   taksonomi varchar,
   risk_register varchar,
   penyebab varchar,
   deskripsi_dampak varchar,
   asumsi_dampak varchar,
   dampak_inheren varchar,
   dampak_terhadap_limit varchar,
   skor_dampak bigint,
   kemungkinan double,
   skor_kemungkinan bigint,
   level_risiko varchar,
   exposure_risiko bigint,
   biaya_pengendalian bigint,
   target_dampak_residual_januari varchar,
   target_dampak_residual_februari varchar,
   target_dampak_residual_maret varchar,
   target_dampak_residual_april varchar,
   target_dampak_residual_mei varchar,
   target_dampak_residual_juni varchar,
   target_dampak_residual_juli varchar,
   target_dampak_residual_agustus varchar,
   target_dampak_residual_september varchar,
   target_dampak_residual_oktober varchar,
   target_dampak_residual_november varchar,
   target_dampak_residual_desember varchar,
   target_residual_dampak_terhadap_limit_januari varchar,
   target_residual_dampak_terhadap_limit_februari varchar,
   target_residual_dampak_terhadap_limit_maret varchar,
   target_residual_dampak_terhadap_limit_april varchar,
   target_residual_dampak_terhadap_limit_mei varchar,
   target_residual_dampak_terhadap_limit_juni varchar,
   target_residual_dampak_terhadap_limit_juli varchar,
   target_residual_dampak_terhadap_limit_agustus varchar,
   target_residual_dampak_terhadap_limit_september varchar,
   target_residual_dampak_terhadap_limit_oktober varchar,
   target_residual_dampak_terhadap_limit_november varchar,
   target_residual_dampak_terhadap_limit_desember varchar,
   target_skor_dampak_januari bigint,
   target_skor_dampak_februari bigint,
   target_skor_dampak_maret bigint,
   target_skor_dampak_april bigint,
   target_skor_dampak_mei bigint,
   target_skor_dampak_juni bigint,
   target_skor_dampak_juli bigint,
   target_skor_dampak_agustus bigint,
   target_skor_dampak_september bigint,
   target_skor_dampak_oktober bigint,
   target_skor_dampak_november bigint,
   target_skor_dampak_desember bigint,
   target_kemungkinan_januari double,
   target_kemungkinan_februari double,
   target_kemungkinan_maret double,
   target_kemungkinan_april double,
   target_kemungkinan_mei double,
   target_kemungkinan_juni double,
   target_kemungkinan_juli double,
   target_kemungkinan_agustus double,
   target_kemungkinan_september double,
   target_kemungkinan_oktober double,
   target_kemungkinan_november double,
   target_kemungkinan_desember double,
   target_skor_kemungkinan_januari bigint,
   target_skor_kemungkinan_februari bigint,
   target_skor_kemungkinan_maret bigint,
   target_skor_kemungkinan_april bigint,
   target_skor_kemungkinan_mei bigint,
   target_skor_kemungkinan_juni bigint,
   target_skor_kemungkinan_juli bigint,
   target_skor_kemungkinan_agustus bigint,
   target_skor_kemungkinan_september bigint,
   target_skor_kemungkinan_oktober bigint,
   target_skor_kemungkinan_november bigint,
   target_skor_kemungkinan_desember bigint,
   target_exposure_risiko_januari double,
   target_exposure_risiko_februari double,
   target_exposure_risiko_maret double,
   target_exposure_risiko_april double,
   target_exposure_risiko_mei double,
   target_exposure_risiko_juni double,
   target_exposure_risiko_juli double,
   target_exposure_risiko_agustus double,
   target_exposure_risiko_september double,
   target_exposure_risiko_oktober double,
   target_exposure_risiko_november double,
   target_exposure_risiko_desember double,
   target_level_risiko_januari varchar,
   target_level_risiko_februari varchar,
   target_level_risiko_maret varchar,
   target_level_risiko_april varchar,
   target_level_risiko_mei varchar,
   target_level_risiko_juni varchar,
   target_level_risiko_juli varchar,
   target_level_risiko_agustus varchar,
   target_level_risiko_september varchar,
   target_level_risiko_oktober varchar,
   target_level_risiko_november varchar,
   target_level_risiko_desember varchar,
   realisasi_biaya_pengendalian_januari bigint,
   realisasi_percent_biaya_pengendalian_januari double,
   realisasi_nilai_dampak_januari varchar,
   realiasi_dampak_terhadap_limit_januari double,
   realisasi_skor_dampak_januari bigint,
   realisasi_kemungkinan_januari double,
   realisasi_skor_kemungkinan_januari bigint,
   realisasi_exposure_risiko_januari double,
   realisasi_level_risiko_januari varchar,
   realisasi_biaya_pengendalian_februari bigint,
   realisasi_percent_biaya_pengendalian_februari double,
   realisasi_nilai_dampak_februari varchar,
   realiasi_dampak_terhadap_limit_februari double,
   realisasi_skor_dampak_februari bigint,
   realisasi_kemungkinan_februari double,
   realisasi_skor_kemungkinan_februari bigint,
   realisasi_exposure_risiko_februari double,
   realisasi_level_risiko_februari varchar,
   realisasi_biaya_pengendalian_maret bigint,
   realisasi_percent_biaya_pengendalian_maret double,
   realisasi_nilai_dampak_maret varchar,
   realiasi_dampak_terhadap_limit_maret double,
   realisasi_skor_dampak_maret bigint,
   realisasi_kemungkinan_maret varchar,
   realisasi_skor_kemungkinan_maret bigint,
   realisasi_exposure_risiko_maret double,
   realisasi_level_risiko_maret varchar,
   realisasi_biaya_pengendalian_april bigint,
   realisasi_percent_biaya_pengendalian_april double,
   realisasi_nilai_dampak_april varchar,
   realiasi_dampak_terhadap_limit_april double,
   realisasi_skor_dampak_april bigint,
   realisasi_kemungkinan_april double,
   realisasi_skor_kemungkinan_april bigint,
   realisasi_exposure_risiko_april double,
   realisasi_level_risiko_april varchar,
   realisasi_biaya_pengendalian_mei bigint,
   realisasi_percent_biaya_pengendalian_mei double,
   realisasi_nilai_dampak_mei varchar,
   realiasi_dampak_terhadap_limit_mei double,
   realisasi_skor_dampak_mei bigint,
   realisasi_kemungkinan_mei double,
   realisasi_skor_kemungkinan_mei bigint,
   realisasi_exposure_risiko_mei double,
   realisasi_level_risiko_mei varchar,
   realisasi_biaya_pengendalian_juni bigint,
   realisasi_percent_biaya_pengendalian_juni double,
   realisasi_nilai_dampak_juni varchar,
   realiasi_dampak_terhadap_limit_juni double,
   realisasi_skor_dampak_juni bigint,
   realisasi_kemungkinan_juni double,
   realisasi_skor_kemungkinan_juni bigint,
   realisasi_exposure_risiko_juni bigint,
   realisasi_level_risiko_juni varchar,
   realisasi_biaya_pengendalian_juli bigint,
   realisasi_percent_biaya_pengendalian_juli double,
   realisasi_nilai_dampak_juli varchar,
   realiasi_dampak_terhadap_limit_juli double,
   realisasi_skor_dampak_juli bigint,
   realisasi_kemungkinan_juli double,
   realisasi_skor_kemungkinan_juli bigint,
   realisasi_exposure_risiko_juli double,
   realisasi_level_risiko_juli varchar,
   realisasi_biaya_pengendalian_agustus bigint,
   realisasi_percent_biaya_pengendalian_agustus double,
   realisasi_nilai_dampak_agustus varchar,
   realiasi_dampak_terhadap_limit_agustus double,
   realisasi_skor_dampak_agustus bigint,
   realisasi_kemungkinan_agustus double,
   realisasi_skor_kemungkinan_agustus bigint,
   realisasi_exposure_risiko_agustus double,
   realisasi_level_risiko_agustus varchar,
   realisasi_biaya_pengendalian_september varchar,
   realisasi_percent_biaya_pengendalian_september varchar,
   realisasi_nilai_dampak_september varchar,
   realiasi_dampak_terhadap_limit_september varchar,
   realisasi_skor_dampak_september varchar,
   realisasi_kemungkinan_september varchar,
   realisasi_skor_kemungkinan_september varchar,
   realisasi_exposure_risiko_september varchar,
   realisasi_level_risiko_september varchar,
   realisasi_biaya_pengendalian_oktober varchar,
   realisasi_percent_biaya_pengendalian_oktober varchar,
   realisasi_nilai_dampak_oktober varchar,
   realiasi_dampak_terhadap_limit_oktober varchar,
   realisasi_skor_dampak_oktober varchar,
   realisasi_kemungkinan_oktober varchar,
   realisasi_skor_kemungkinan_oktober varchar,
   realisasi_exposure_risiko_oktober varchar,
   realisasi_level_risiko_oktober varchar,
   realisasi_biaya_pengendalian_november varchar,
   realisasi_percent_biaya_pengendalian_november varchar,
   realisasi_nilai_dampak_november varchar,
   realiasi_dampak_terhadap_limit_november varchar,
   realisasi_skor_dampak_november varchar,
   realisasi_kemungkinan_november varchar,
   realisasi_skor_kemungkinan_november varchar,
   realisasi_exposure_risiko_november varchar,
   realisasi_level_risiko_november varchar,
   realisasi_biaya_pengendalian_desember varchar,
   realisasi_percent_biaya_pengendalian_desember varchar,
   realisasi_nilai_dampak_desember varchar,
   realiasi_dampak_terhadap_limit_desember varchar,
   realisasi_skor_dampak_desember varchar,
   realisasi_kemungkinan_desember varchar,
   realisasi_skor_kemungkinan_desember varchar,
   realisasi_exposure_risiko_desember varchar,
   realisasi_level_risiko_desember varchar,
   source_file_name varchar,
   snapshot_date date,
   file_modified_at timestamp(6) with time zone,
   ingestion_timestamp timestamp(6) with time zone,
   tahun bigint
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_bronze.risk_register pada 2026-11-10 (apa adanya).';

CREATE TABLE bronze_erm_risk_strategy_matrix (
   rsmatrix_id varchar,
   entity varchar,
   periode varchar,
   risk_capacity double,
   risk_appetite double,
   risk_tolerance double,
   risk_limit double,
   source_file_name varchar,
   snapshot_date date,
   file_modified_at timestamp(6) with time zone,
   ingestion_timestamp timestamp(6) with time zone,
   tahun bigint
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_bronze.risk_strategy_matrix pada 2026-11-10 (apa adanya).';

CREATE TABLE bronze_erm_trigger_level_matrix (
   skor_kemungkinan bigint,
   dampak_1 varchar,
   dampak_2 varchar,
   dampak_3 varchar,
   dampak_4 varchar,
   dampak_5 varchar,
   source_file_name varchar,
   snapshot_date date,
   file_modified_at timestamp(6) with time zone,
   ingestion_timestamp timestamp(6) with time zone,
   tahun bigint
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_bronze.trigger_matriks_level pada 2026-11-10 (apa adanya).';

CREATE TABLE bronze_erm_trigger_score_matrix (
   skor_kemungkinan bigint,
   dampak_1 varchar,
   dampak_2 varchar,
   dampak_3 bigint,
   dampak_4 bigint,
   dampak_5 bigint,
   source_file_name varchar,
   snapshot_date date,
   file_modified_at timestamp(6) with time zone,
   ingestion_timestamp timestamp(6) with time zone,
   tahun bigint
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_bronze.trigger_matriks_skor pada 2026-11-10 (apa adanya).';

CREATE TABLE bronze_erm_trigger_scale_level (
   skala_risiko varchar,
   level_risiko varchar,
   source_file_name varchar,
   snapshot_date date,
   file_modified_at timestamp(6) with time zone,
   ingestion_timestamp timestamp(6) with time zone,
   tahun bigint
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_bronze.trigger_skala_level pada 2026-11-10 (apa adanya).';

CREATE TABLE silver_dim_erm_risk_level_matrix (
   tahun bigint,
   skor_kemungkinan bigint,
   skor_dampak bigint,
   level_skor bigint,
   level_label varchar,
   snapshot_date date,
   source_file_name varchar,
   file_modified_at timestamp(6) with time zone,
   silver_processed_at timestamp(6) with time zone
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_silver.matriks_level pada 2026-11-10 (apa adanya).';

CREATE TABLE silver_dim_erm_risk_score_matrix (
   tahun bigint,
   skor_kemungkinan bigint,
   skor_dampak bigint,
   skor bigint,
   snapshot_date date,
   source_file_name varchar,
   file_modified_at timestamp(6) with time zone,
   silver_processed_at timestamp(6) with time zone
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_silver.matriks_skor pada 2026-11-10 (apa adanya).';

CREATE TABLE silver_dim_erm_risk_level_reference (
   skor_min bigint,
   skor_max bigint,
   label varchar,
   snapshot_date date,
   source_file_name varchar,
   silver_processed_at timestamp(6) with time zone
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_silver.risk_level_reference pada 2026-11-10 (apa adanya).';

CREATE TABLE silver_fact_erm_risk_control_monthly (
   tahun bigint,
   risk_id varchar,
   id_penyebab varchar,
   id_rencana_pengendalian varchar,
   bulan bigint,
   penyebab varchar,
   rencana_pengendalian varchar,
   pic_fungsi varchar,
   realisasi varchar,
   percent_progress double,
   snapshot_date date,
   source_file_name varchar,
   file_modified_at timestamp(6) with time zone,
   silver_processed_at timestamp(6) with time zone
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_silver.pengendalian_risiko pada 2026-11-10 (apa adanya).';

CREATE TABLE silver_fact_erm_risk_profile_monthly (
   tahun bigint,
   risk_profile_id varchar,
   bulan bigint,
   taksonomi varchar,
   risk_parameter varchar,
   target_formula varchar,
   risk_limit double,
   risk_limit_uraian varchar,
   risk_appetite_range varchar,
   risk_tolerance double,
   risk_tolerance_uraian varchar,
   aktual double,
   aktual_uraian varchar,
   status varchar,
   penyebab_risiko varchar,
   rencana_pengendalian varchar,
   snapshot_date date,
   source_file_name varchar,
   file_modified_at timestamp(6) with time zone,
   silver_processed_at timestamp(6) with time zone
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_silver.risk_profile pada 2026-11-10 (apa adanya).';

CREATE TABLE silver_fact_erm_risk_register_monthly (
   tahun bigint,
   risk_id varchar,
   bulan bigint,
   entity varchar,
   company_id varchar,
   strategic_objective varchar,
   taksonomi varchar,
   risk_register varchar,
   penyebab varchar,
   deskripsi_dampak varchar,
   asumsi_dampak varchar,
   dampak_inheren decimal(27,11),
   dampak_inheren_uraian varchar,
   dampak_terhadap_limit double,
   skor_dampak bigint,
   kemungkinan double,
   skor_kemungkinan bigint,
   level_risiko bigint,
   level_risiko_text varchar,
   exposure_risiko decimal(27,11),
   biaya_pengendalian decimal(27,11),
   target_dampak_residual decimal(27,11),
   target_dampak_residual_uraian varchar,
   target_residual_dampak_terhadap_limit double,
   target_skor_dampak bigint,
   target_kemungkinan double,
   target_skor_kemungkinan bigint,
   target_exposure_risiko decimal(27,11),
   target_level_risiko bigint,
   target_level_risiko_text varchar,
   realisasi_biaya_pengendalian decimal(27,11),
   realisasi_percent_biaya_pengendalian double,
   realisasi_nilai_dampak decimal(27,11),
   realisasi_nilai_dampak_uraian varchar,
   realisasi_dampak_terhadap_limit double,
   realisasi_skor_dampak bigint,
   realisasi_kemungkinan double,
   realisasi_skor_kemungkinan bigint,
   realisasi_exposure_risiko decimal(27,11),
   realisasi_level_risiko bigint,
   realisasi_level_risiko_text varchar,
   snapshot_date date,
   source_file_name varchar,
   file_modified_at timestamp(6) with time zone,
   silver_processed_at timestamp(6) with time zone
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_silver.risk_register pada 2026-11-10 (apa adanya).';

CREATE TABLE silver_fact_erm_risk_strategy_matrix (
   tahun bigint,
   rsmatrix_id varchar,
   entity varchar,
   company_id varchar,
   periode_text varchar,
   risk_capacity decimal(27,11),
   risk_appetite decimal(27,11),
   risk_tolerance decimal(27,11),
   risk_limit decimal(27,11),
   snapshot_date date,
   source_file_name varchar,
   file_modified_at timestamp(6) with time zone,
   silver_processed_at timestamp(6) with time zone
)
COMMENT 'Data ERM lama, dipindah dari lakekeeper.erm_silver.risk_strategy_matrix pada 2026-11-10 (apa adanya).';

-- ==== Kerangka SDM (Sumber Daya Manusia) + data korporasi, 2026-11-10. Sumber: Bronze bronze_sdm_* / bronze_corp_*
-- (dipindah dari prototipe lakekeeper.medallion oleh medallion/migrate_legacy_medallion.py). Dibangun medallion/sdm.py.
-- Kolom data pribadi ditandai "Sensitivitas: <level>" di komentar → tag Sensitivitas di katalog (catalog_trino.py).

CREATE TABLE silver_dim_company_information (
   company_id varchar COMMENT 'PK perusahaan/entitas (dirujuk kolom company_id ERM, label ''Perusahaan'')',
   company_name varchar,
   company_name_formatted varchar,
   company_aliases varchar,
   company_acronym varchar,
   entity_classification varchar,
   domicile_status varchar,
   company_group varchar,
   company_level varchar,
   relation_to_main varchar,
   is_central_company boolean,
   company_address varchar,
   city varchar,
   province varchar,
   country varchar,
   postal_code varchar,
   phone_number varchar,
   email varchar,
   website varchar,
   tax_id_npwp varchar COMMENT 'NPWP badan — Sensitivitas: Restricted',
   industry_sector varchar,
   business_category varchar,
   vendor_category_finance varchar,
   vendor_category_scm varchar,
   contact_person varchar COMMENT 'Nama narahubung — Sensitivitas: Confidential',
   contact_phone varchar COMMENT 'Telepon narahubung — Sensitivitas: Confidential',
   notes varchar,
   is_active boolean,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: CORP',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Dimensi bersama perusahaan/entitas Len (holding DEFEND ID, anak, afiliasi, mitra). Sumber: bronze_corp_company_information.';

CREATE TABLE silver_dim_sdm_employee (
   employee_id varchar COMMENT 'PK pegawai',
   nik_npp varchar COMMENT 'Nomor induk pegawai — Sensitivitas: Confidential',
   full_name varchar COMMENT 'Nama lengkap — Sensitivitas: Confidential',
   origin_name varchar COMMENT 'Nama asal di berkas sumber — Sensitivitas: Confidential',
   company_id varchar COMMENT 'FK silver_dim_company_information (dicocokkan dari company_name; NULL = tidak cocok, lihat gold_sdm_dq_finding)',
   company_name varchar,
   company_scope varchar,
   directorate varchar,
   division varchar,
   unit varchar,
   job_title varchar,
   job_title_detail varchar,
   job_level varchar,
   job_stream varchar,
   sub_job_stream varchar,
   employment_status varchar COMMENT 'PKWTT | PKWT | Maganghub',
   special_program_assignment varchar,
   gender varchar COMMENT 'Baku: Laki-laki | Perempuan; NULL bila sumber bukan jenis kelamin — Sensitivitas: Restricted',
   gender_source varchar COMMENT 'Nilai jenis kelamin apa adanya dari sumber — Sensitivitas: Restricted',
   age integer COMMENT 'Sensitivitas: Restricted',
   birth_date date COMMENT 'Tanggal lahir (untuk umur per periode) — Sensitivitas: Restricted',
   age_group varchar,
   generation varchar,
   religion varchar COMMENT 'Sensitivitas: Strictly Confidential',
   education_level varchar,
   major varchar,
   institution varchar,
   years_of_service double,
   years_of_service_group varchar,
   physical_condition varchar COMMENT 'Kondisi fisik/kesehatan — Sensitivitas: Strictly Confidential',
   is_certified boolean,
   certification_summary varchar,
   project_management_qualification varchar,
   dq_note varchar COMMENT 'Catatan mutu baris (nilai sumber tidak diubah diam-diam)',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: SDM | LENO_SDM',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Dimensi pegawai (kerangka SDM). Satu baris per pegawai per sumber: SDM (prototipe, bronze_sdm_employee_information) | LENO_SDM (Aplikasi LenO ps_karyawan).';

CREATE TABLE silver_fact_sdm_certification (
   certification_id varchar COMMENT 'PK',
   employee_id varchar COMMENT 'FK silver_dim_sdm_employee (nama/NIK tidak diduplikasi di sini)',
   company_id varchar COMMENT 'FK silver_dim_company_information',
   company_name varchar,
   certification_name varchar,
   certification_category varchar,
   training_type varchar,
   validity_status varchar,
   period_start_year integer COMMENT 'Tahun awal dari sumber ''YYYY'' atau ''YYYY-YYYY''; NULL bila format lain',
   period_end_year integer COMMENT 'Tahun akhir (= awal bila sumber satu tahun)',
   training_year_source varchar COMMENT 'Nilai tahun/rentang apa adanya dari sumber',
   dq_note varchar,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: SDM',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Fakta sertifikasi/pelatihan pegawai (kerangka SDM). Sumber: bronze_sdm_employee_certification.';

CREATE TABLE silver_fact_corp_investment_monthly (
   fact_id varchar COMMENT 'PK',
   company_id varchar COMMENT 'FK silver_dim_company_information',
   company_name varchar,
   company_group varchar,
   company_level varchar,
   period_year integer,
   period_month integer COMMENT '1–12',
   date_key integer COMMENT 'yyyymmdd hari pertama bulan',
   category_code varchar,
   category_name varchar,
   item_name varchar,
   annual_budget double COMMENT 'Anggaran tahunan',
   monthly_budget double,
   monthly_realization double,
   ytd_budget double COMMENT 'Anggaran s.d. bulan',
   ytd_realization double COMMENT 'Realisasi s.d. bulan',
   ytd_realization_pct double COMMENT 'Persen realisasi s.d. anggaran (apa adanya dari sumber)',
   remaining_annual_budget double,
   mom_growth_nominal double,
   mom_growth_pct double,
   notes varchar,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: CORP',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Fakta investasi bulanan per perusahaan. Sumber: bronze_corp_company_investment.';

CREATE TABLE silver_fact_corp_tax_monthly (
   fact_id varchar COMMENT 'PK',
   company_id varchar COMMENT 'FK silver_dim_company_information',
   company_name varchar,
   company_group varchar,
   company_level varchar,
   period_year integer,
   period_month integer COMMENT '1–12',
   date_key integer COMMENT 'yyyymmdd hari pertama bulan',
   tax_jurisdiction varchar,
   tax_group varchar,
   tax_item_code varchar,
   tax_item_name varchar,
   monthly_realization double,
   ytd_realization double,
   mom_growth_nominal double,
   mom_growth_pct double,
   notes varchar,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: CORP',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Fakta pajak bulanan per perusahaan. Sumber: bronze_corp_company_tax.';

CREATE TABLE gold_sdm_workforce_profile (
   company_id varchar,
   company_name varchar,
   directorate varchar,
   division varchar,
   employment_status varchar,
   gender varchar,
   age_group varchar,
   generation varchar,
   education_level varchar,
   years_of_service_group varchar,
   job_level varchar,
   headcount bigint,
   certified_count bigint,
   avg_age double,
   avg_years_of_service double,
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold SDM: profil tenaga kerja teragregasi (tanpa data pribadi) untuk dashboard demografi.';

CREATE TABLE gold_sdm_company_summary (
   company_id varchar,
   company_name varchar,
   company_group varchar,
   headcount bigint,
   pkwtt_count bigint,
   pkwt_count bigint,
   intern_count bigint,
   female_count bigint,
   female_ratio double COMMENT 'Perempuan / (Laki-laki + Perempuan); pegawai tanpa jenis kelamin baku tidak dihitung',
   avg_age double,
   certified_count bigint,
   certified_ratio double,
   certification_count bigint,
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold SDM: ringkasan tenaga kerja per perusahaan.';

CREATE TABLE gold_sdm_certification_summary (
   company_name varchar,
   certification_category varchar,
   training_type varchar,
   validity_status varchar,
   period_start_year integer,
   period_end_year integer,
   certification_count bigint,
   employee_count bigint,
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold SDM: ringkasan sertifikasi per perusahaan, kategori, jenis, status, periode.';

CREATE TABLE gold_sdm_dq_finding (
   table_name varchar,
   column_name varchar,
   rule_name varchar,
   finding varchar,
   affected_rows bigint,
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold SDM: temuan mutu data SDM/korporasi (nilai sumber tidak diubah; tindak lanjut ke pemilik data HC).';

-- ==== Program Task Force Asta Cita (domain astacita), 2026-11-10. Sumber: berkas Nextcloud DBASTACITA (nextcloud_sync.py →
-- inbox → Bronze bronze_file_dbastacita_*). Berkas utama: DBASTACITA/DBASTACITA.xlsx (versi terbaru di Bronze). Dibangun medallion/astacita.py.
-- Kunci penghubung = tema bidang (theme_code), bukan nomor "Asta Cita N" (penomoran beda antar sheet; lihat gold_astacita_dq_finding).

CREATE TABLE silver_dim_astacita_theme (
   theme_code varchar COMMENT 'PK tema bidang baku (SEMICON, EO_SENSOR, AI, CYBER, SATELLITE, RADAR_EW, UAS, C2)',
   astacita_no integer COMMENT 'Nomor Asta Cita menurut sheet Profile berkas utama',
   astacita_label varchar COMMENT 'Asta Cita <no>',
   theme_name varchar COMMENT 'Nama tema menurut sheet Profile',
   theme_synonyms varchar COMMENT 'Ejaan lain di sheet/berkas lain (dipisah |)',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: ASTACITA',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Dimensi tema/bidang program Task Force Asta Cita.';

CREATE TABLE silver_dim_astacita_program (
   program_id varchar COMMENT 'PK: <theme_code>-<urutan baris profil>',
   theme_code varchar COMMENT 'FK silver_dim_astacita_theme',
   profile_code varchar COMMENT 'Kode di sheet Profile (P1…)',
   program_no varchar,
   program_name varchar,
   budget_idr double COMMENT 'Anggaran (Rp); NULL bila sumber bukan angka',
   budget_source varchar COMMENT 'Nilai anggaran apa adanya',
   budget_status varchar,
   co_lead varchar COMMENT 'Sensitivitas: Restricted',
   program_lead varchar COMMENT 'Sensitivitas: Restricted',
   description varchar,
   output_description varchar,
   operating_concept varchar,
   period_label varchar,
   stage_label varchar,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: ASTACITA',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Dimensi program Asta Cita (sheet Profile).';

CREATE TABLE silver_fact_astacita_scurve_weekly (
   theme_code varchar COMMENT 'FK silver_dim_astacita_theme',
   period_year integer,
   period_month integer,
   week_no integer COMMENT 'Minggu ke- dalam bulan (w1…w5)',
   date_key integer COMMENT 'yyyymmdd hari pertama bulan',
   plan_monthly_ratio double COMMENT 'Rencana bulanan (fraksi 0–1)',
   plan_cumulative_ratio double COMMENT 'Akumulasi rencana (fraksi 0–1)',
   actual_monthly_ratio double COMMENT 'Realisasi bulanan (fraksi 0–1)',
   actual_cumulative_ratio double COMMENT 'Akumulasi realisasi (fraksi 0–1)',
   deviation_cumulative_ratio double COMMENT 'Deviasi akumulasi (realisasi − rencana, apa adanya dari sumber)',
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: ASTACITA',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Fakta kurva S mingguan per tema (sheet Kurva S).';

CREATE TABLE silver_fact_astacita_output (
   theme_code varchar,
   output_no integer,
   output_name varchar,
   output_summary varchar,
   status varchar COMMENT 'Baku: Completed | In Progress | Not Started (nilai lain apa adanya)',
   status_source varchar,
   progress_ratio double COMMENT 'Fraksi 0–1',
   reporting_period_label varchar,
   notes varchar,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: ASTACITA',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Fakta output/deliverable per tema (sheet Output).';

CREATE TABLE silver_fact_astacita_issue (
   theme_code varchar,
   period_year integer,
   period_month integer,
   date_key integer,
   program_name varchar,
   issue varchar,
   issue_description varchar,
   issue_summary varchar,
   strategy varchar,
   strategy_summary varchar,
   support_needed varchar,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: ASTACITA',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Fakta kendala dan strategi per tema per bulan (sheet Kendala dan strategi).';

CREATE TABLE silver_fact_astacita_activity_monthly (
   theme_code varchar,
   period_year integer,
   period_month integer,
   date_key integer,
   activity_category varchar,
   activity_title varchar,
   baseline_ratio double,
   actual_ratio double,
   deviation_cause varchar,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: ASTACITA',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Fakta kegiatan bulanan (baseline vs realisasi) per tema (sheet 8 Asta Cita).';

CREATE TABLE silver_fact_astacita_priority_score (
   theme_code varchar,
   survey_code varchar COMMENT 'Kode di sheet Hasil Kompilasi (P1…; penomoran survei)',
   survey_label varchar COMMENT 'Label Asta Cita menurut survei',
   avg_impact double,
   avg_business double,
   avg_resource double,
   avg_risk double,
   risk_score_used double,
   consensus_score double,
   aip_final_score double,
   aip_rank integer,
   function_balanced_score double,
   balanced_rank integer,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: ASTACITA',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Fakta skor prioritas AHP/AIP per tema (sheet Hasil Kompilasi, survei 13 responden).';

CREATE TABLE silver_dim_astacita_manpower (
   theme_code varchar,
   person_name varchar COMMENT 'Nama personel — Sensitivitas: Confidential',
   role_status varchar,
   program_name varchar,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: ASTACITA',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Personel per tema (sheet Manpower).';

CREATE TABLE gold_astacita_program_summary (
   theme_code varchar,
   astacita_no integer,
   astacita_label varchar,
   theme_name varchar,
   program_count bigint,
   total_budget_idr double,
   last_scurve_date_key integer,
   plan_cumulative_ratio double,
   actual_cumulative_ratio double,
   deviation_cumulative_ratio double,
   schedule_status varchar COMMENT 'Sesuai/Lebih cepat (deviasi ≥ 0) | Terlambat (deviasi < 0) | Belum ada realisasi',
   output_count bigint,
   output_completed bigint,
   output_progress_avg double,
   issue_count bigint,
   aip_final_score double,
   aip_rank integer,
   manpower_count bigint,
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold Asta Cita: ringkasan per tema (program, anggaran, kurva S terakhir, output, kendala, prioritas, manpower).';

CREATE TABLE gold_astacita_scurve_weekly (
   theme_code varchar,
   astacita_label varchar,
   theme_name varchar,
   period_date date,
   date_key integer,
   week_no integer,
   week_label varchar,
   plan_cumulative_ratio double,
   actual_cumulative_ratio double,
   deviation_cumulative_ratio double,
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold Asta Cita: kurva S mingguan siap grafik.';

CREATE TABLE gold_astacita_output_status (
   theme_code varchar,
   astacita_label varchar,
   theme_name varchar,
   status varchar,
   output_count bigint,
   progress_avg double,
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold Asta Cita: jumlah output per status per tema.';

CREATE TABLE gold_astacita_dq_finding (
   table_name varchar,
   column_name varchar,
   rule_name varchar,
   finding varchar,
   affected_rows bigint,
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold Asta Cita: temuan mutu data sumber DBASTACITA.';

-- ==== SDM dari Aplikasi LenO (lenodb.silver: ps_karyawan, ps_statusbarukaryawan, ps_ukkaryawan), 2026-11-10. Dibangun medallion/leno_sdm.py.
-- Baris pegawai LenO masuk silver_dim_sdm_employee dengan _source_system = LENO_SDM (berdampingan dengan prototipe SDM).
-- Kelompok status: reference/sdm_status_kepegawaian.csv (dapat dikoreksi Unit HC).

CREATE TABLE silver_fact_sdm_employment_status (
   status_id varchar COMMENT 'PK',
   employee_id varchar COMMENT 'FK silver_dim_sdm_employee',
   company_id varchar COMMENT 'FK silver_dim_company_information',
   status_name varchar COMMENT 'Status kepegawaian sumber (Karyawan Tetap, Kontrak Pemborongan, …)',
   employment_class varchar COMMENT 'TETAP | KONTRAK | NON_KARYAWAN | TIDAK_AKTIF | TIDAK_DIKENAL (reference/sdm_status_kepegawaian.csv)',
   contract_flag varchar COMMENT 'Kontrak | Non Kontrak | Alih Daya | Organ Perusahaan',
   is_employee boolean,
   is_active boolean COMMENT 'FALSE untuk status tidak aktif bekerja (mis. Cuti Tanpa Tanggungan)',
   job_category varchar COMMENT 'Jenis karyawan sumber (Staff, Penunjang Produksi & Operasi, …)',
   valid_from date COMMENT 'TMT status',
   valid_to date COMMENT 'Akhir berlaku: paling awal dari tanggal berakhir, TMT berhenti, dan (bila pegawai tidak aktif) absensi terakhir / perubahan data terakhir; 9999-12-31 = masih berlaku',
   end_date_basis varchar COMMENT 'Dasar valid_to: tanggal berakhir | TMT berhenti | absensi terakhir (perkiraan) | perubahan data terakhir (perkiraan) | terbuka',
   is_current boolean,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_SDM',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Riwayat status kepegawaian per pegawai (rentang berlaku). Sumber: Aplikasi LenO ps_statusbarukaryawan.';

CREATE TABLE silver_fact_sdm_unit_assignment (
   assignment_id varchar COMMENT 'PK',
   employee_id varchar COMMENT 'FK silver_dim_sdm_employee',
   org_id varchar COMMENT 'Kode unit kerja (hr_unitkerja.kodeuk = ORG_ID workbook)',
   unit_name varchar,
   valid_from date,
   valid_to date COMMENT '9999-12-31 = masih berlaku',
   is_current boolean,
   _file_id varchar COMMENT 'lineage',
   _batch_id varchar COMMENT 'lineage',
   _source_system varchar COMMENT 'lineage: LENO_SDM',
   _source_file varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Riwayat penempatan unit kerja per pegawai. Sumber: Aplikasi LenO ps_ukkaryawan + hr_unitkerja.';

CREATE TABLE gold_sdm_headcount_monthly (
   period_year integer,
   period_month integer,
   period_date date COMMENT 'Hari pertama bulan',
   date_key integer,
   company_id varchar,
   company_name varchar,
   org_id varchar COMMENT 'Unit kerja pada akhir bulan (NULL bila tidak tercatat)',
   unit_name varchar,
   gender varchar COMMENT 'Laki-laki | Perempuan',
   employment_class varchar COMMENT 'TETAP | KONTRAK | NON_KARYAWAN | TIDAK_AKTIF | TIDAK_DIKENAL',
   contract_flag varchar COMMENT 'Kontrak | Non Kontrak | Alih Daya | Organ Perusahaan',
   employment_status varchar COMMENT 'Status kepegawaian sumber',
   is_employee boolean,
   is_active boolean COMMENT 'Aktif bekerja (bukan cuti tanpa tanggungan)',
   age_group varchar COMMENT '<25 | 25-34 | 35-44 | 45-54 | 55+ (umur pada akhir bulan)',
   headcount bigint COMMENT 'Jumlah orang pada posisi akhir bulan',
   age_min integer,
   age_max integer,
   age_avg double,
   _source_system varchar COMMENT 'lineage: LENO_SDM',
   _batch_id varchar COMMENT 'lineage',
   _loaded_at timestamp(6) with time zone COMMENT 'lineage'
)
COMMENT 'Gold SDM: jumlah karyawan per bulan (posisi akhir bulan) menurut perusahaan, unit, gender, kontrak/non kontrak, status, kelompok umur — dengan umur min/maks/rata-rata. Tanpa data pribadi.';
