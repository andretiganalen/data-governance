# Sumber manual Len Data Governance

Satu perintah membuat satu rilis: tiga manual PDF bernomor `YYMMDD CC`, dengan angka diambil langsung dari sumbernya.

```bash
PY=/srv/lendatagovernance/medallion/.venv/bin/python   # venv medallion: trino + openpyxl
$PY docs/manuals/src/rilis.py --dry-run          # nomor rilis berikutnya
$PY docs/manuals/src/rilis.py                    # rilis baru (tidak menimpa rilis lama)
$PY docs/manuals/src/rilis.py --preview <dir>    # cetak ulang PDF dari build/data.js terakhir, untuk memeriksa tata letak
```

| Berkas | Audiens | Batas isi |
| :-- | :-- | :-- |
| `pengembang.html` | Pengembang / Admin (UV-3) | status rinci, akses, tindak lanjut, arah, operasi |
| `staf.html` | Staf DG (UV-1), Pemilik, Pimpinan | hanya Sudah bisa / Belum bisa; tanpa status aplikasi |
| `pengguna.html` | Pengguna | cara pakai + Tersedia / Belum ada / Belum bisa; tanpa detail aplikasi atau port |

Angka diisi otomatis dari `build/data.js` (dibuat saat rilis):

- `R.gold` — lapisan Gold di Trino `lakekeeper.medallion_repository` (hanya SELECT/SHOW): daftar tabel `gold_*` (`tabel`),
  KPI tata kelola terbaru (`kpi`), istilah tanpa definisi, catatan mutu Silver, berkas sumber terakhir, jumlah objek per lapisan.
  Data dibangun oleh `deploy/lendatagovernance/medallion/lakehouse.py`, bukan oleh `rilis.py`.
- `R.dataset` — ringkasan per dataset bisnis (dari `silver_dim_meta_dataset`, `gold_meta_data_dictionary`, `gold_meta_lineage`).
- `R.live` — status langsung katalog (project compose `lendatagovernance`, basis data `lendatagovernance_db`).

Butuh: venv di atas + `/srv/lendatagovernance/secrets/trino.env`, node 22, google-chrome, dan `sudo docker` untuk membaca status katalog.

## SRS (Software Requirements Specification)
Sumber: `srs/usecases.js` (60 use case) dan `srs/build-srs.js` (bab, kebutuhan fungsional/non-fungsional, keterlacakan, isu).
Butuh paket npm `docx` (v9); bila belum terpasang global, pasang di folder sementara lalu arahkan `NODE_PATH`:
```bash
npm install --prefix /tmp/docxjs docx@9
NODE_PATH=/tmp/docxjs/node_modules node docs/manuals/src/srs/build-srs.js "docs/manuals/<YYMMDD CC> SRS Len Data Governance.docx" "<YYMMDD CC>"
```
Perbarui `usecases.js`/`build-srs.js` setiap kali fitur, aturan data, atau isu terbuka berubah.
