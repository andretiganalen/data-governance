---
name: uix-len-web-apps
description: Standar antarmuka UIx untuk aplikasi web internal Len (warna merah korporat #ae2524, font Poppins, abu-abu bekerja, radius 8/12, sidebar kiri + header atas + kartu). Pakai saat membuat atau mengubah halaman, menu, kartu, tabel, dialog, atau teks UI di aplikasi Len, termasuk yang disuntikkan ke aplikasi pihak ketiga lewat gateway.
---

# UIx — standar antarmuka web Len

UIx adalah satu-satunya tema. Tidak ada tema lain, tidak ada jalan kembali ke gaya lama. Gaya: padat dan tenang. Abu-abu yang bekerja, merah korporat hanya untuk hal yang perlu ditindaklanjuti pembaca, warna status hanya bicara soal status. Hanya tema terang (token tema gelap belum dipakai).

Balas pengguna dalam Bahasa Indonesia formal.

## 1. Aturan emas (urutan prioritas)

1. **Pakai struktur bawaan aplikasi.** Kartu, menu, halaman, tabel, tombol baru dibuat dari kelas dan struktur aplikasi itu sendiri (mis. `ant-card`, `page-header-container`, `ant-table`, `ant-btn`, item sidebar sebagai `<a class="left-panel-item…">`, ikon kartu gaya bawaan 89px), diletakkan di `main.ant-layout-content`. Jangan membuat tiruan bergaya manual.
2. **Samakan dengan saudaranya.** Sebelum dikirim, bandingkan elemen baru dengan elemen sejenis di menu yang sama: tinggi, jarak, posisi vertikal, ikon, font. Selisih beberapa piksel dianggap cacat.
3. **Satu bahasa per tampilan.** Bahasa Indonesia formal atau English, tidak pernah dicampur dalam satu tampilan.
4. **Tidak ada nilai warna, font, atau radius yang ditulis langsung** di komponen. Selalu lewat token `--uix-*`.

## 2. Token warna (`:root`)

| Token | Nilai | Pemakaian |
| :-- | :-- | :-- |
| `--uix-primary` | `#ae2524` | Aksi utama (tombol Primary solid), tautan, tab aktif, ikon menu terpilih |
| `--uix-primary-strong` | `#8e1e1d` | Hover/pressed |
| `--uix-primary-soft` | `rgba(174,37,36,.10)` | Latar lembut merah (jarang) |
| `--uix-on-primary` | `#ffffff` | Teks di atas merah |
| `--uix-text-head` / `-body` / `-secondary` / `-muted` | `#101828` / `#364153` / `#6a7282` / `#99a1af` | Judul / isi / bantu / placeholder (muted hanya placeholder, nonaktif, kosong) |
| `--uix-surface-page` / `--uix-surface` / `-subtle` / `-muted` | `#f9fafb` / `#ffffff` / `#f9fafb` / `#f3f4f6` | Halaman / panel / cekungan / strip & hover |
| `--uix-border` / `-subtle` / `-strong` | `#e5e7eb` / `#f3f4f6` / `#d1d5dc` | Komponen / pemisah baris / tepi tegas |
| `--uix-field-border` | `#99a1af` | Batas kolom input (isi `--uix-input-wash` `rgba(0,0,0,.04)`) |
| `--uix-success` / `-warning-text` / `-danger` / `-info` | `#008236` / `#bb4d00` / `#e7000b` / `#155dfc` | Status saja, selalu dengan kata atau ikon |
| `--uix-focus-border` / `-ring` | `#6a7282` / `rgba(106,114,130,.4)` | Fokus: satu cincin netral 3px |

Aturan warna:
- Merah bukan untuk fokus dan bukan untuk "invalid" (terbaca bahaya). Hanya Primary, Danger, dan Default yang boleh solid.
- Warna tidak pernah satu-satunya penanda: status pakai kata atau ikon, opsi terpilih pakai centang dan bobot 500.
- Grafik: seri `uix-chart-1…6` berurutan, tidak diacak; legenda bila ≥ 3 seri.
- Ikon biru bawaan pihak ketiga (`#1677FF`) diwarnai ulang ke `--uix-primary` lewat aturan CSS, bukan diedit satu per satu.

## 3. Tipografi

- Satu keluarga: **Poppins** 400 / 500 / 600 (tanpa 700), dideklarasikan sebagai `"UIx Poppins"`, berkas woff2 dilayani dari server sendiri (tanpa Google Fonts). Stack: `"UIx Poppins", "Segoe UI", Arial, sans-serif`.
- Isi 13px (menu, tabel, input). Judul kartu 16/600, judul bagian 18, judul halaman dan modal 20. Kode tetap monospace.
- Huruf kecil gaya kalimat untuk judul, tombol, label. Tanpa emoji di antarmuka.

## 4. Bentuk, jarak, bayangan

| Elemen | Aturan |
| :-- | :-- |
| Radius | Kontrol dan tombol **8px** · kartu, modal, panel **12px** · chip, badge, baris menu **6px** · pil hanya untuk pil dan switch |
| Tinggi kontrol | 30 / **34** / 38 px (sm / md / lg) |
| Kartu | Garis `--uix-border` + `--uix-shadow-xs`, radius 12 |
| Bayangan | `xs` kartu dan tombol · `md` dropdown/popover · `lg` drawer · `xl` modal |
| Fokus | `:focus-visible` outline 3px `--uix-focus-ring`; batas jadi `--uix-focus-border` |
| Nonaktif | Opasitas 0.5 (kolom input: readonly, teks muted) |

## 5. Menu dan susunan halaman

Susunan: header atas, sidebar kiri, isi berupa kartu.

- **Sidebar:** putih, garis kanan `--uix-border`; baris radius 6px, margin 2px 4px, teks 13px; hover latar `#f3f4f6`; **terpilih** = latar `#f3f4f6`, bobot 500, ikon merah, penanda 3px merah di kiri (tidak ada latar merah).
- **Dropdown/menu daftar:** panel menjorok 4px, baris 32px, radius 6px, hover abu-abu; terpilih = centang merah + bobot 500, tanpa baris bertint merah.
- **Tab:** tinta 2px merah di bawah tab aktif, label tab aktif merah bobot 500.
- **Tabel:** kepala `#f9fafb`, teks 12px/600 `--uix-text-secondary` (tanpa huruf kapital semua), baris dipisah `--uix-border-subtle`, hover `#f9fafb`.
- **Kartu pengaturan:** tinggi sama dengan kartu bawaan; kolom induk memakai `display` yang sama dengan saudaranya (selisih `flex` vs `block` pernah menggeser kartu 10px).
- **Menu dengan anak** (mis. Explore: Explore, Visualisasi) berupa dropdown; anak sidebar memakai `<a class="left-panel-item…">` dengan tinggi 40px, bobot 500, ikon 16px.
- **Panel tertanam** (aplikasi lain di dalam aplikasi): dihitung dari `getBoundingClientRect()` milik `main.ant-layout-content`, bukan angka tetap, supaya tidak menutupi header.

## 6. Dialog dan pesan

- Nada tenang: tanpa warna alarm, tanpa kapital berteriak. Jelaskan apa yang terjadi, dampaknya, dan cara memulihkan.
- Hapus = pindah ke Tempat Sampah (dapat dipulihkan); opsi hapus permanen disembunyikan dari antarmuka.
- Teks kosong dan "belum ada data" ditulis apa adanya. **Jangan memunculkan `null`**: tulis "Eksisting" bila tidak ada pembaruan, atau biarkan kolom data NULL tanpa dikarang.

## 7. Bahasa (i18n)

- Pilihan bahasa di menu aplikasi: "Bahasa Indonesia - ID" dan English. Ikuti cookie bahasa aplikasi.
- Setiap teks kustom baru masuk ke kamus dua bahasa (ID dan EN) di satu berkas (`leno-i18n.js`). Tidak ada teks satu bahasa yang ditulis langsung di komponen.
- Istilah mengikuti glosarium (`i18n/glosarium.md`). Ubah terjemahan di sumber JSON lalu jalankan skrip build; jangan edit hasil build.
- Isi data (nama tabel, kolom, judul dasbor, SQL) tidak diterjemahkan.

## 8. Merek

- Logo dan favicon ditanam permanen dari satu folder (`brand/`) dan diganti hanya dengan menimpa berkas di sana. Konfigurasi tema dilayani gateway dari `brand/theme.json` bila endpoint bawaan mengembalikan nilai kosong.
- Nama produk: pakai nama milik kita. Nama upstream hanya muncul bila tidak bisa diubah (jalur, kunci env, nama image); teks UI diganti oleh gateway.

## 9. Cara menerapkan ke aplikasi pihak ketiga (pola)

1. Satu berkas CSS tema (`:root` token + override) dan JS kecil per fitur, dilayani gateway dan disuntikkan lewat `sub_filter` ke setiap halaman.
2. Edit konfigurasi gateway **di tempat** (bukan ganti berkas): bind-mount file menyimpan inode lama. Atau buat ulang container gateway setelah edit.
3. Jangan membuka port atau kredensial terpisah untuk aplikasi tertanam; login lewat sesi aplikasi induk (SSO).
4. Setelah perubahan UI: ambil tangkapan layar halaman dan bandingkan dengan saudara di menu yang sama (aturan emas no. 2).

## 10. Daftar periksa sebelum menyatakan selesai

- [ ] Hanya token `--uix-*`; tidak ada hex, font, atau radius liar.
- [ ] Poppins 400/500/600 termuat dari server sendiri.
- [ ] Merah hanya untuk aksi utama, tautan, dan penanda terpilih.
- [ ] Elemen baru memakai kelas bawaan dan sejajar dengan saudaranya (tinggi, jarak, posisi).
- [ ] Fokus: cincin netral 3px; status selalu dengan kata atau ikon.
- [ ] Semua teks baru ada di kamus ID dan EN; tampilan tidak bercampur bahasa.
- [ ] Tidak ada `null` yang tampil ke pengguna.
- [ ] Tidak ada rahasia, nama host internal, atau data pribadi di berkas yang di-commit.

## Batas yang diketahui

- Hanya tema terang. Token tema gelap UIx belum dipakai.
- Superset (Visualisasi) mengikuti tema lewat CSS tersendiri; komponen Superset 6 tertentu mengabaikan paket bahasa dan diterjemahkan lewat DOM.
