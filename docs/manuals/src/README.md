# Sumber manual Len Data Governance

Satu perintah membuat satu rilis: data Gold (panel `/unduh/`) + tiga manual PDF bernomor `YYMMDD CC`.

```bash
python3 docs/manuals/src/rilis.py --dry-run          # nomor rilis berikutnya
python3 docs/manuals/src/rilis.py                    # rilis baru (tidak menimpa rilis lama)
python3 docs/manuals/src/rilis.py --preview <dir>    # cetak ulang PDF dari data rilis terakhir, untuk memeriksa tata letak
```

| Berkas | Audiens | Batas isi |
| :-- | :-- | :-- |
| `pengembang.html` | Pengembang / Admin (UV-3) | status rinci, akses, tindak lanjut, arah, operasi |
| `staf.html` | Staf DG (UV-1), Pemilik, Pimpinan | hanya Sudah bisa / Belum bisa; tanpa status aplikasi |
| `pengguna.html` | Pengguna | cara pakai + Tersedia / Belum ada / Belum bisa; tanpa detail aplikasi atau port |

Angka diisi otomatis dari `build/data.js` (manifest Gold + status langsung server). Butuh python3 + openpyxl, node 22,
google-chrome, dan `sudo docker` untuk membaca status katalog. Pipeline data: `deploy/openmetadata/medallion/`.
