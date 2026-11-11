---
title: Interface & Menu — Standar Tema Web-based Apps Len (UIx)
tags: [ui, theme, design-system, standard, len, uix]
dibuat: 2026-11-04
diperbarui: 2026-11-11
status: Default v2.0 (UIx) — wajib untuk aplikasi web baru dan yang sudah ada
sumber: Artifak design system "UIx" (claude.ai/artifact/FqPxtXaKBbuxoBowzYE9vn) — tokens.json + README
---

# Interface & Menu — Standar Tema (UIx)

> [!important] Keputusan 2026-11-11 (Andre Tigana)
> Tampilan semua aplikasi web Len mengikuti **UIx** saja. Tidak ada tema lain dan tidak ada jalan kembali.
> UIx = library komponen aplikasi internal Len (Audit, KPI, SKI): padat, tenang; abu-abu bekerja, merah korporat
> hanya untuk hal yang ditindaklanjuti pembaca; warna status hanya bicara soal status.
> Posisi: header atas, sidebar kiri, kartu (bagian 4). Isi, susunan menu, dan hak akses milik aplikasi.
> Sumber nilai: `project/tokens.json` artifak UIx (nilai oklch dikonversi ke hex, tema terang saja).

## 1. Warna (CSS variables `--uix-*`, `:root` di `deploy/ui/leno-theme/leno.css`)

| Token | Nilai | Pemakaian |
| :-- | :-- | :-- |
| `--uix-primary` | `#ae2524` | Aksi utama (tombol Primary solid), tautan, tab aktif, ikon menu terpilih |
| `--uix-primary-strong` | `#8e1e1d` | Hover/pressed |
| `--uix-on-primary` | `#ffffff` | Teks di atas merah |
| `--uix-text-head` / `-body` / `-secondary` / `-muted` | `#101828` / `#364153` / `#6a7282` / `#99a1af` | Judul / isi / bantu / placeholder (muted hanya placeholder, nonaktif, kosong) |
| `--uix-surface-page` / `--uix-surface` / `-subtle` / `-muted` | `#f9fafb` / `#ffffff` / `#f9fafb` / `#f3f4f6` | Halaman / panel (kartu, modal, sidebar) / cekungan / strip & hover |
| `--uix-border` / `-subtle` / `-strong` | `#e5e7eb` / `#f3f4f6` / `#d1d5dc` | Komponen / pemisah baris / tepi tegas |
| `--uix-field-border` | `#99a1af` | Batas kolom input (isi `--uix-input-wash` `rgba(0,0,0,.04)`) |
| `--uix-success` / `-warning-text` / `-danger` / `-info` | `#008236` / `#bb4d00` / `#e7000b` / `#155dfc` | Status saja, selalu dengan kata atau ikon |
| `--uix-focus-border` / `-ring` | `#6a7282` / `rgba(106,114,130,.4)` | Fokus: satu cincin netral 3px |

**Aturan**
- Merah bukan untuk fokus dan bukan untuk "invalid" (itu terbaca bahaya). Hanya Primary, Danger, dan Default boleh solid.
- Warna tidak pernah satu-satunya penanda: status pakai kata/ikon; opsi terpilih pakai centang dan bobot 500.
- Grafik: seri `uix-chart-1…6` berurutan, tidak diacak (lihat tokens.json); legenda bila ≥ 3 seri.

## 2. Tipografi

- **Satu huruf: Poppins** 400 / 500 / 600 (tanpa 700), dideklarasikan `"UIx Poppins"`. Berkas di `deploy/ui/leno-theme/fonts/`,
  dilayani gateway di `/_leno/fonts/` (tanpa Google Fonts). Stack: `"UIx Poppins", "Segoe UI", Arial, sans-serif`.
- Isi 13px (menu, tabel, input). Judul kartu 16/600, judul bagian 18, judul halaman & modal 20. Kode tetap monospace.
- Huruf kecil gaya kalimat untuk judul, tombol, label. Tanpa emoji.

## 3. Bentuk, jarak, bayangan

| Elemen | Aturan |
| :-- | :-- |
| Radius | Kontrol & tombol **8px** · kartu, modal, panel **12px** · chip, badge, baris menu **6px** · pil hanya untuk pil/switch |
| Tinggi kontrol | 30 / **34** / 38 px (sm / md / lg) |
| Kartu | Garis `--uix-border` + `--uix-shadow-xs`, radius 12 |
| Bayangan | `xs` kartu & tombol · `md` dropdown/popover · `lg` drawer · `xl` modal (nilai di leno.css) |
| Fokus | `:focus-visible` outline 3px `--uix-focus-ring`; batas jadi `--uix-focus-border` |
| Nonaktif | Opasitas 0.5 (kolom input: readonly, teks muted) |

## 4. Menu

- **Sidebar kiri:** putih, garis kanan `--uix-border`; baris 6px, margin 2px 4px, teks 13px; hover latar `#f3f4f6`;
  **terpilih** = latar `#f3f4f6`, bobot 500, ikon merah, penanda 3px merah di kiri (tidak ada latar merah).
- **Dropdown/menu daftar:** panel menjorok 4px, baris 32px, radius 6px, hover abu-abu; terpilih = centang merah + bobot 500, tidak ada baris bertint merah.
- **Tab:** tinta 2px merah di bawah tab aktif, label tab aktif merah bobot 500.
- **Tabel:** kepala `#f9fafb`, teks 12px/600 `--uix-text-secondary` (tanpa huruf kapital semua), baris dipisah `--uix-border-subtle`, hover `#f9fafb`.
- **Panel Visualisasi** (`leno-menu.js`) memakai gaya yang sama; Superset (`leno-superset.css`) dan Referensi (`referensi.html`) ikut.

## 5. Penerapan di repo

| Berkas | Isi |
| :-- | :-- |
| `deploy/ui/leno-theme/leno.css` | Tema katalog (dimasukkan gateway ke setiap halaman) |
| `deploy/ui/leno-theme/leno-menu.js` | Panel Visualisasi (gaya inline mengikuti UIx) |
| `deploy/ui/leno-theme/leno-superset.css` | Tema Superset 6 |
| `deploy/ui/leno-theme/referensi.html` | Halaman `/referensi/` |
| `deploy/ui/leno-theme/fonts/` | Poppins 400/500/600 (woff2, dari artifak UIx) |
| Settings › Preferences › Theme | `primaryColor #ae2524`, `selectedColor #8e1e1d` |

Catatan: UI katalog hanya punya tema terang; token tema gelap UIx belum dipakai.
