# Data Owner berdasarkan Fungsi (usulan pemetaan)

Status: **usulan, belum diterapkan** di katalog. Sumber: `Master_Organization` (kolom FUNGSI) pada Workbook Governance 261016 Rev.0.1, dibandingkan dengan CLP-001 Nomenklatur Fungsi Generik rev.01 (35 Fungsi).

## Aturan

- Nama Data Owner = nama Fungsi **tanpa awalan "Fungsi"** dan tanpa kode unit (contoh: `Manajemen Risiko`, bukan `UG-1 Risk Management`).
- Setiap Fungsi dipetakan ke **Eselon 1** (Divisi) dan **Eselon 2** (unit kerja, kode UX-n). Satu Fungsi bisa mencakup beberapa unit, dan satu Divisi bisa memuat beberapa Fungsi.
- Hak, peran, dan keanggotaan tetap mengikuti unit Eselon 2; Fungsi menjadi label kepemilikan aset.

## Pemetaan

| Data Owner (Fungsi) | Eselon 1 (Divisi) | Eselon 2 (unit) | Sesuai CLP-001 |
| :-- | :-- | :-- | :-: |
| Akuntansi | Accounting | UF-2 Accounting & Reporting | ya |
| Audit Internal | Internal Audit | UI-1 General Audit; UI-2 Specific Audit & Audit Quality | ya |
| K3L | QHSE & Process Excellence | UQ-3 Health, Safety & Environment | ya |
| Keuangan | Finance | UK-1 Corporate Finance; UK-2 Treasury | ya |
| Komunikasi Korporasi | Corporate Secretary | UC-3 Institutional Relation & Corporate Communication | ya |
| Legal | Legal | UY-1 Corporate Legal; UY-2 Litigation & Dispute Resolution | ya |
| Litbang | Engineering; Innovation Center | UE-2 Engineering 2; UM-1 Innovation Ecosystem; UM-2 Technology Innovation | ya |
| Manajemen Proses Bisnis | QHSE & Process Excellence | UQ-2 Business Process Management | ya |
| Manajemen Proyek | Project Deployment Center | UP-1 Project Operation 1; UP-2 Project Operation 2; UP-3 Project Operation 3 | ya |
| Manajemen Risiko | Governance, Risk Management & Compliance | UG-1 Risk Management | ya |
| Pajak | Accounting | UF-5 Tax Management | **tidak** |
| Pemasaran | Marketing & Sales Center | US-1 Marketing & Sales - Army; US-2 Marketing & Sales - Navy; US-3 Marketing & Sales - Air Force | ya |
| Pengadaan | Supply Chain Management | UJ-1 Procurement Policy; UJ-2 Procurement Operation | ya |
| Pengamanan | Corporate Secretary | UC-5 Corporate Security | ya |
| Pengawasan Pra Proyek | Project Management Office | UO-2 Bid & Resource Management | ya |
| Pengawasan Proyek | Project Management Office | UO-1 Operation Monitoring & Evaluation | ya |
| Pengembangan Bisnis | Business Development & Global Partnership | UD-1 Business Development; UD-3 Strategic Partnership | ya |
| Pengendali Anggaran | Accounting | UF-3 Budgeting, PMN & Cost Control | ya |
| Penjaminan Mutu | QHSE & Process Excellence | UQ-1 Quality Assurance | ya |
| Perencanaan Perusahaan | Corporate Strategic Planning | UW-1 Corporate Planning & Performance Management; UW-2 Corporate Program & Strategy Management | ya |
| Perencanaan Proyek | Marketing & Sales Center | US-5 Project & Supply Planning | ya |
| Portofolio | Portfolio Management | UL-1 Portfolio Optimization; UL-2 Subsidiaries Alignment & Support | ya |
| Rekayasa Sistem | Engineering | UE-1 Engineering 1 | ya |
| SDM | Human Capital & General Affairs | UH-1 Human Capital Policy & Strategy; UH-2 Human Capital Performance & Talent Management; UH-3 Human Capital Services | ya |
| TJSL | Corporate Secretary | UC-2 Corporate Social Responsibility | ya |
| Tata Kelola | Governance, Risk Management & Compliance | UG-2 Corporate Governance & Compliance | ya |
| Teknologi Informasi | Information System | UV-1 IT Governance & Data Management; UV-2 IT Operation & Cyber Security; UV-3 IT Development | **tidak** |
| Urusan Umum | Human Capital & General Affairs | UH-4 General Affairs | ya |

Total: 28 Fungsi dari 45 unit Eselon 2.

## Temuan untuk diputuskan

1. Nama di workbook yang tidak ada di CLP-001: `Pajak`, `Teknologi Informasi`. Saran: `Teknologi Informasi` dibakukan menjadi `Teknologi` (CLP-001 no. 20); `Pajak` tidak ada di CLP-001 (usul: digabung ke `Keuangan`, atau CLP-001 direvisi).
2. Fungsi CLP-001 yang belum punya unit di organisasi saat ini (9): Operasi Produksi, Pengelola Gudang, Pengelola Sistem Manajemen, Produksi, Purna Jual, Rekayasa Pra Produksi, Rendal Produksi, Sekretaris Perusahaan, Teknologi.
3. **Keterbatasan katalog:** hanya tim bertipe *Group* yang dapat memiliki aset, dan Group tidak dapat memuat Group lain. Dua cara agar kepemilikan terbaca di level Fungsi dan Eselon 1:
   - **A (disarankan):** buat satu tim Group per Fungsi (nama tanpa awalan) sebagai Data Owner, di bawah Divisinya (Eselon 1); unit Eselon 2 dicatat sebagai atribut pada tim itu.
   - **B:** pertahankan unit Eselon 2 sebagai pemilik, tetapi nama tampilan diganti menjadi nama Fungsi dan Divisi ditambahkan di deskripsi.
4. Setelah cara dipilih, kepemilikan aset yang ada (UG-1: 77 aset, UP-1: 2, UV-1: 3, UP-2: 1, UH-3: 1) dipindahkan otomatis oleh loader.
