---
title: Interface & Menu — Standar Tema Web-based Apps Len (default)
tags: [ui, theme, design-system, standard, len]
dibuat: 2026-11-04
status: Default v1.1 — wajib untuk aplikasi web baru
sumber: https://www.len.co.id/ (dibaca read-only: Elementor global kit post-5.css, header post-77.css, konten post-36.css, footer post-63.css)
menggantikan_warna_dari: "[[leno_interface_theme.md]]"
---

# Interface & Menu — Standar Tema

> [!important] Cakupan
> Dokumen ini adalah **default** untuk tema semua aplikasi web-based baru (internal maupun portal).
> Gaya: **classic korporat** — header putih berbayang tipis, navy sebagai warna utama, merah hanya sebagai
> aksen penanda, sudut tegas, garis tipis. Isi, susunan menu, dan hak akses tetap milik masing-masing aplikasi.
> `leno_interface_theme.md` tetap acuan **posisi** (header atas, sidebar kiri, kartu); **warna & font** mengikuti dokumen ini.

Nilai bertanda **(Len)** diambil langsung dari len.co.id. Nilai bertanda *(turunan)* adalah turunan yang
konsisten dengan palet Len untuk kebutuhan aplikasi (status, latar, garis) yang tidak ada di situs.

## 1. Warna (CSS variables `:root`)

| Token | Nilai | Asal | Pemakaian |
| :-- | :-- | :-- | :-- |
| `--len-navy` | `#194A80` | (Len) global color | **Warna utama**: tombol utama, menu aktif, judul, tautan navigasi |
| `--len-navy-700` | `#12375F` | *(turunan)* | Hover/pressed tombol navy |
| `--len-navy-50` | `#EEF3F9` | *(turunan)* | Latar item menu aktif, baris terpilih |
| `--len-red` | `#DA0000` | (Len) global color | **Aksen**: penanda menu aktif, badge, tombol sekunder |
| `--len-red-700` | `#CF0000` | (Len) garis pointer menu | Garis bawah/kiri menu aktif |
| `--len-red-hover` | `#FF2121` | (Len) hover dropdown | Hover item dropdown (teks putih) |
| `--len-blue` | `#0562C9` | (Len) global color | Tautan dalam teks, info |
| `--len-ink` | `#3B3B3B` | (Len) primary | Judul & teks utama |
| `--len-text` | `#515151` | (Len) text | Teks isi, label menu |
| `--len-text-2` | `#54595F` | (Len) secondary | Teks sekunder |
| `--len-muted` | `#838282` | (Len) | Teks bantu, placeholder (hanya ≥ 14px) |
| `--len-line` | `#C4C4C4` | (Len) pemisah dropdown | Garis pemisah menu, border input |
| `--len-line-soft` | `#E6E6E6` | *(turunan)* | Border kartu, tabel |
| `--len-bg` | `#F5F6F8` | *(turunan)* | Latar halaman aplikasi |
| `--len-surface` | `#FFFFFF` | (Len) | Header, kartu, sidebar, dropdown |
| `--len-footer` | `#000000` | (Len) footer | Footer, teks putih |
| `--len-success` | `#1E7B34` | *(turunan)* | Sukses / "Lancar" |
| `--len-warning` | `#B26A00` | *(turunan)* | Peringatan |
| `--len-danger` | `#DA0000` | = `--len-red` | Error, hapus |

**Aturan warna**
- Navy = aksi utama & navigasi. Merah **tidak** dipakai sebagai latar area besar; hanya penanda (garis 3px, badge, ikon peringatan) dan tombol sekunder.
- Kontras minimum WCAG AA: `#515151` / `#3B3B3B` / `#194A80` / `#DA0000` di atas putih lulus untuk teks normal. `#838282` hanya untuk teks ≥ 14px atau non-esensial.
- Satu aksi utama (navy) per layar/form.

## 2. Tipografi

| Peran | Font | Ukuran / berat | Asal |
| :-- | :-- | :-- | :-- |
| Judul halaman (H1) | Montserrat | 24px / 700, letter-spacing −0.3px | (Len) Montserrat 700; ukuran disesuaikan untuk aplikasi |
| Judul hero (landing saja) | Montserrat | 38px / 900, letter-spacing −1.6px | (Len) typography 24e5958 |
| Sub-judul / judul kartu | Montserrat | 17px / 700 | (Len) typography 86efe63 |
| Teks isi | Montserrat | 14–15px / 400–500 | (Len) global text: Montserrat 500, 15px/400 |
| Label menu (header & sidebar) | Open Sans | 14–15px / 500 | (Len) menu Open Sans 500 |
| Tombol | Montserrat | 14px / 600 | (Len) accent Montserrat 500, dinaikkan ke 600 |
| Angka/kode | `ui-monospace, Consolas` | 13px | *(turunan)* |

Stack: `Montserrat, "Segoe UI", Arial, sans-serif` (judul **dan isi**) · `"Open Sans", "Segoe UI", Arial, sans-serif` (**menu saja**).
Koreksi 2026-11-04: v1.0 keliru menaruh Open Sans untuk isi; len.co.id memakai Montserrat untuk isi.
Muat dari Google Fonts dengan `display=swap`; tanpa internet tetap jatuh ke Segoe UI/Arial.

## 3. Batas, sudut, bayangan

| Elemen | Aturan |
| :-- | :-- |
| Garis umum | `1px solid var(--len-line-soft)`; pemisah menu/dropdown `1px solid var(--len-line)` (Len) |
| Sudut | Input, tombol aplikasi, tag: **4px** · Kartu, panel, modal: **6px** · Menu & tabel: **0** (Len: menu tanpa radius) |
| Tombol pill (`100px`) | **Hanya** CTA di landing/portal (Len), tidak di form aplikasi |
| Bayangan header | `0 2px 6px rgba(0,0,0,.18)` (Len) |
| Bayangan kartu | `0 1px 2px rgba(0,0,0,.06)` — tipis, classic *(turunan)* |
| Fokus keyboard | `outline: 2px solid var(--len-blue); outline-offset: 2px` |
| Penanda aktif | Garis **3px** `var(--len-red-700)` — bawah (menu atas) atau kiri (sidebar) |

## 4. Menu

### 4.1 Header & menu atas (pola len.co.id)
- Header **putih**, tinggi 64px, padding `0 24px`, bayangan header (§3). Logo kiri (tinggi 32px), menu di tengah/kanan, aksi pengguna paling kanan.
- Item menu: Open Sans 500 15px (`--len-font-menu`), warna `--len-text`, padding `15px` (Len), tanpa latar.
- Hover: teks `--len-navy` + garis bawah 3px `--len-red-700`. Aktif: sama, permanen.
- Dropdown: latar putih, lebar min. 240px, item padding `12px 16px`, pemisah `1px solid --len-line` (Len);
  hover item **latar `--len-red-hover`, teks putih** (Len). Judul grup (item `href="#"`) Montserrat 600 12px kapital, abu.
- Bertingkat maksimal 2 level; level ke-2 menjorok 20px (Len: `+20px`).

### 4.2 Sidebar aplikasi (posisi dari `leno_interface_theme.md` §3)
- Lebar 248px (terlipat 72px), latar putih, garis kanan `1px solid --len-line-soft`.
- Item: tinggi 40px, padding `10px 16px`, gap ikon–label 12px, Open Sans 500 14px `--len-text`, radius 0.
- Hover: latar `#F3F4F6`, teks `--len-ink`.
- Aktif: latar `--len-navy-50`, teks `--len-navy` 600, **garis kiri 3px `--len-red-700`**.
- Label grup: Montserrat 600 11px kapital, `--len-muted`, padding `16px 16px 6px`.

### 4.3 Aksi pengguna (kanan header)
- Tombol ikon 36px, latar transparan, ikon `--len-text`; hover latar `--len-navy-50`.
- Badge hitungan: latar `--len-red`, teks putih, 18px.
- Avatar inisial 34px: latar `--len-navy`, teks putih.

## 5. Komponen dasar

| Komponen | Aturan |
| :-- | :-- |
| Tombol utama | Latar `--len-navy`, teks putih, radius 4px, padding `10px 18px`; hover `--len-navy-700` |
| Tombol sekunder | Garis 1px `--len-navy`, teks navy, latar putih; hover latar `--len-navy-50` |
| Tombol bahaya | Latar `--len-red`, teks putih |
| Input | Tinggi 38px, garis `1px solid --len-line`, radius 4px; fokus garis `--len-navy` + outline fokus |
| Kartu | Putih, garis `--len-line-soft`, radius 6px, bayangan kartu; judul Montserrat 700 17px; **garis atas 3px `--len-navy`** untuk kartu ringkasan |
| Tabel | Header latar `#F7F8FA`, teks Montserrat 600 12px kapital `--len-text-2`; baris garis bawah `--len-line-soft`; hover baris `#FAFBFC` |
| Chip/tag | Radius 4px, latar `--len-navy-50`, teks `--len-navy`, 12px/600 |
| Footer | Latar `--len-footer`, teks putih 80%, 12–13px (Len) |

## 6. Template token

```css
:root {
  --len-navy:#194A80; --len-navy-700:#12375F; --len-navy-50:#EEF3F9;
  --len-red:#DA0000; --len-red-700:#CF0000; --len-red-hover:#FF2121; --len-blue:#0562C9;
  --len-ink:#3B3B3B; --len-text:#515151; --len-text-2:#54595F; --len-muted:#838282;
  --len-line:#C4C4C4; --len-line-soft:#E6E6E6; --len-bg:#F5F6F8; --len-surface:#FFFFFF; --len-footer:#000000;
  --len-success:#1E7B34; --len-warning:#B26A00; --len-danger:#DA0000;
  --len-font-head: Montserrat, "Segoe UI", Arial, sans-serif;
  --len-font-body: Montserrat, "Segoe UI", Arial, sans-serif;   /* isi = Montserrat (Len) */
  --len-font-menu: "Open Sans", "Segoe UI", Arial, sans-serif;  /* menu saja */
  --len-radius-control:4px; --len-radius-card:6px;
  --len-shadow-header:0 2px 6px rgba(0,0,0,.18); --len-shadow-card:0 1px 2px rgba(0,0,0,.06);
}
```

## 7. Penerapan

| Aplikasi | File |
| :-- | :-- |
| Len Data Governance (dev-data) | `deploy/ui/leno-theme/leno.css` (disisipkan gateway) + Settings › Preferences › Theme: Primary `#194A80`, Info `#0562C9`, Success `#1E7B34`, Warning `#B26A00`, Error `#DA0000` |
| Landing dev-data | `deploy/lendatagovernance/gateway/html/index.html` |
| Aplikasi baru | Salin §6 ke stylesheet global; ikuti §4–§5 |

**Tidak diatur di sini:** isi/urutan menu, hak akses, dan teks — tetap milik masing-masing aplikasi.
