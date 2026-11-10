# DG-0002 — Standar Medallion: penamaan tabel, kolom, kunci, dan field_id

- Status: Diterima (2026-11-06). Berlaku untuk semua dataset Medallion baru, mulai dari E-GRC.
- Masa pakai: dirancang untuk 10 tahun (2026–2036). Perubahan hanya lewat ADR baru yang menggantikan bagian tertentu.
- Penegakan: `deploy/lendatagovernance/medallion/egrc.py` → `load_registry()` dan validasi keluaran. Build **gagal** bila standar dilanggar.

> **Pembaruan 2026-11-09 — lakehouse Trino.** Sistem rekam data kini `lakekeeper.medallion_repository` (Trino, Iceberg),
> bukan berkas CSV/XLSX di `/srv`. Atas keputusan pemilik (2026-11-09), tabel di lakehouse **mengikuti kerangka yang
> sudah ada di skema itu**: nama tabel `bronze_* / silver_dim_* / silver_fact_* / gold_*` berbahasa Inggris, kolom
> seperti `risk_id`, `company_id`, `fiscal_year`, kolom lineage `_file_id, _batch_id, _source_system, _source_file, _loaded_at`,
> dan kode elemen `F0xx`/`X0xx` dari workbook di komentar kolom. Aturan bagian 2–4 di bawah (akhiran kelas, `field_id`
> `<DOMAIN>-F<4 digit>`) tetap berlaku untuk keluaran berkas `egrc.py` dan `field_registry.csv`, tetapi **tidak** untuk
> tabel lakehouse. Definisi tabel lakehouse: `deploy/lendatagovernance/medallion/schema/medallion_repository.sql`;
> pemuat: `medallion/lakehouse.py`. ADR pengganti yang menyatukan keduanya perlu ditulis.
>
> **Pembaruan 2026-11-10.** Rilis berkas CSV/XLSX dan panel `/unduh/` dihentikan: tabel Lapisan di bawah dan §8
> (lokasi `work/`/`panel/`, akun panel) **tidak berlaku lagi**. Bronze/Silver/Gold hanya di `lakekeeper.medallion_repository`;
> berkas sumber hanya masukan Bronze (inbox) sebelum ETL. Akses data lewat Trino (menu Visualisasi, DBeaver); tabel
> buatan pengguna hanya di schema `lakekeeper.workspace`.

## Konteks
Data akan datang dari banyak sistem (ERM, E-GRC, SDM, keuangan, …) selama bertahun-tahun, dikerjakan oleh orang yang berganti-ganti.
Tanpa aturan tetap, kolom yang sama akan bernama berbeda, kode akan bertabrakan, dan dashboard rusak setiap kali sumber berubah.
Workbook ERM memakai `F001…F105` per workbook. Pola itu hanya muat 999 elemen dan tidak membedakan sistem.

## 1. Lapisan
| Lapisan | Isi | Lokasi | Akses |
| :-- | :-- | :-- | :-- |
| Bronze | Berkas sumber apa adanya + CSV per sheet (nomor baris asli) + SHA-256 | `/srv/lendatagovernance/medallion/work/<rid>/bronze/<sistem>/` | server saja |
| Silver | Data bersih: dim, fact, bridge. Satu fakta satu tempat. Nilai sumber tidak diubah diam-diam. | `…/work/<rid>/silver/<sistem>/` | server saja |
| Gold | Tabel datar siap dashboard + kamus data + temuan mutu | `…/panel/rilis/<rid>/[<domain>/]` (dihentikan 2026-11-10) | panel `/unduh/` (ditutup 2026-11-10) |

`<rid>` = nomor rilis `YYMMDD-CC`. Rilis tidak pernah ditimpa.

## 2. Nama tabel
```
silver_<dim|fact|bridge>[_<domain>]_<subjek>[_<grain>]
gold_<domain>_<subjek>[_<grain>]
```
- `<domain>` = kode domain huruf kecil (`grc`, `erm`, …). Dimensi **bersama** (dipakai lintas domain) tanpa domain: `silver_dim_periode`, `silver_dim_entitas`.
- `<grain>` wajib untuk fakta berwaktu: `_bulanan`, `_tahunan`, `_harian`.
- Contoh: `silver_fact_grc_penilaian_risiko`, `silver_bridge_grc_risiko_taksonomi`, `gold_grc_kinerja_risiko_bulanan`.
- Setiap domain Gold wajib punya `gold_<domain>_kamus_data` dan `gold_<domain>_temuan_mutu`.

## 3. Nama kolom
1. `snake_case`, huruf kecil ASCII, maksimal 60 karakter, bahasa Indonesia baku.
2. Pola: `[tahap_][subjek_]atribut[_kualifier]_<kata kelas>`. **Kata kelas wajib di akhir** dan menentukan tipe serta satuan:

| Kata kelas | Arti | Tipe | Contoh |
| :-- | :-- | :-- | :-- |
| `key` | kunci penghubung antar tabel | TEXT/INT | `risiko_key`, `periode_key` |
| `id` | identitas registry | TEXT | `field_id` |
| `kode` | kode bisnis dari sumber | TEXT | `risiko_kode`, `rencana_kode` |
| `nama` | label pendek | TEXT | `entitas_nama` |
| `label` | teks tampilan turunan | TEXT | `periode_label` |
| `uraian` | teks panjang | TEXT | `rencana_uraian` |
| `teks` | nilai kualitatif pengganti angka | TEXT | `dampak_teks` |
| `kategori` | nilai dari daftar tertutup | TEXT | `level_risiko_kategori` |
| `no` | nomor urut / bilangan kecil | INT | `bulan_no` |
| `tahun` | tahun 4 digit | INT | `rkap_tahun` |
| `tgl` | tanggal ISO | DATE | `berlaku_sejak_tgl` |
| `jt_idr` | uang, **juta rupiah** | DECIMAL | `eksposur_jt_idr` |
| `rasio` | pecahan desimal (0,25 = 25%) | DECIMAL | `progres_rasio` |
| `prob` | peluang 0–1 | DECIMAL | `kemungkinan_prob` |
| `skor` | skala bulat 1–5 | INT | `dampak_skor` |
| `nilai` | angka lain (satuan di kamus) | DECIMAL | `skala_risiko_nilai` |
| `jml` | hitungan | INT | `risiko_jml` |
| `flag` | benar/salah | BOOLEAN | `ambang_urutan_valid_flag` |

3. Satuan uang lain menambah kata kelas baru lewat ADR (mis. `_idr`, `_usd`). Satuan tidak boleh disimpulkan dari isi.
4. Singkatan baku saja: `jml`, `no`, `tgl`, `thd` (terhadap), `jt`, `idr`, `pic`, `rkap`, `prob`, `key`. Singkatan lain ditulis lengkap.
5. Tahap/periode menjadi awalan: `inheren_`, `target_`, `realisasi_`, `target_akhir_`, `realisasi_akhir_`.
6. Kolom audit Silver/Gold memakai awalan `meta_`: `meta_sumber_sheet_nama`, `meta_sumber_baris_no`, `meta_rilis_kode`, `meta_catatan_mutu_uraian`.
7. Dilarang: spasi, huruf besar, tanda baca, angka di awal, nama bulan di nama kolom (pakai baris + `periode_key`), kata "baru/lama/v2".

## 4. field_id
Format: `<DOMAIN>-F<NNNN>`, contoh `GRC-F0012`, `CMN-F0013`. Regex: `^[A-Z]{3,4}-F\d{4}$`.

1. **Satu nama kolom = satu field_id = satu arti**, di semua tabel dan lapisan. Kolom yang sama di Silver dan Gold berbagi field_id.
2. field_id mengidentifikasi **elemen data bisnis**, bukan posisi fisik. Ganti nama kolom tidak mengubah field_id. Registry mencatat nama baru dan nama lama ditandai Usang.
3. **Permanen dan tidak dipakai ulang.** Elemen yang tidak dipakai lagi diberi `field_status_kategori = Usang`, bukan dihapus.
4. Nomor urut **tanpa makna** (tidak ada rentang khusus). Arti ada di registry, bukan di angka.
5. Turunan (tahap, agregat, rasio) mendapat field_id sendiri dan menunjuk elemen dasar lewat `turunan_dari_field_id`.
6. Arti berubah berarti field_id baru. Contoh: satuan berubah dari juta ke ribu rupiah = elemen baru.
7. Kode domain terdaftar:

| Domain | Isi | Status |
| :-- | :-- | :-- |
| `CMN` | Elemen bersama lintas domain (periode, entitas, kolom audit, kamus, temuan) | aktif |
| `GRC` | E-GRC: manajemen risiko korporat | aktif |
| `ERM` | Aplikasi ERM di LenO (workbook governance, `F001…F105`) | migrasi: `F001` → `ERM-F0001` sebagai alias, berlaku pada versi loader berikutnya |
| `META` | Dataset metadata tata kelola (`gold_kamus_data`, …) | direncanakan: dimigrasi ke `gold_meta_*` + kolom berkata kelas |

8. Kapasitas: 9.999 elemen per domain. Bila habis, ADR baru menambah digit. Kode domain baru ditambahkan lewat ADR.

## 5. Kunci
- Kunci dibentuk **deterministik dari kode bisnis** sehingga stabil antar rilis: `risiko_key = '2026-RDF001'`, `parameter_key = '2026-RP01'`,
  `penyebab_key = '2026-RDF001-P01'`, `rencana_key = '2026-RDF002-R03.1'`, `matriks_key = 'K4-D5'`, `periode_key = 202601`.
- Bila sumber tidak punya kode: `<prefiks>-` + 8 hex SHA-1 teks yang dinormalisasi (mis. `sasaran_key = 'SS-1a2b3c4d'`).
- Dilarang memakai nomor urut hasil load sebagai kunci (berubah setiap rilis).
- Kode bertingkat (`3.1`, `3.2`) **selalu teks**, tidak boleh angka desimal (1.10 akan menjadi 1.1).
- Kode entitas grup dikelola di `medallion/reference/entitas.csv`, dengan status `Usulan` sampai disetujui pemilik data.

## 6. Registry dan penegakan
- Registry tunggal: `deploy/lendatagovernance/medallion/registry/field_registry.csv`, berisi metadata saja (tanpa nilai), aman untuk repo.
- Menambah kolom: tambahkan baris registry (field_id berikutnya di domainnya, definisi, satuan, sensitivitas, turunan), lalu pakai di ETL.
- Build menolak: format field_id salah, field_id/kolom ganda, kata kelas tidak cocok, nama tabel tidak standar, kolom keluaran tidak terdaftar.
- `gold_<domain>_kamus_data` dibuat otomatis dari registry + tabel pemakai, dan menjadi jawaban "apa arti kolom ini".

## 7. Mutu dan kejujuran data
- Nilai sumber disimpan. Hasil hitung ulang ETL ditaruh di kolom terpisah (`dampak_thd_limit_rasio` di samping `dampak_thd_limit_sumber_rasio`).
- Setiap koreksi, asumsi, atau keanehan dicatat di `meta_catatan_mutu_uraian` (baris) dan `gold_<domain>_temuan_mutu` (ringkasan).
- Asumsi (mis. satuan juta rupiah) dicatat sebagai temuan sampai dikonfirmasi pemilik data.

## 8. Sensitivitas dan akses
- `sensitivitas_kategori` per kolom di registry. Dataset dengan kolom Confidential disajikan di folder domain dengan login tersendiri (`/unduh/rilis/<rid>/grc/`, akun panel E-GRC) — **dihentikan 2026-11-10**; sensitivitas kini ditegakkan lewat tag Sensitivitas di katalog.
- Berkas sumber dan hasil Silver/Gold tidak pernah masuk repo (repo publik; `*.xlsx` dan `/srv` di luar git).

## Konsekuensi
- Dashboard bisa bergantung pada nama kolom Gold dalam jangka panjang. Perubahan arti selalu terlihat sebagai field_id baru.
- Dataset metadata ERM (`gold_kamus_data`, dst.) belum mengikuti pola kolom ini dan dimigrasi bertahap (status META di atas).
- Sumber baru cukup menambah: referensi, baris registry, dan modul ETL `<sistem>.py` dengan pola Bronze → Silver → Gold yang sama.
