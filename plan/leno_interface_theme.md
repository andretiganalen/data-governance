---
title: LenO Interface — Ekstraksi Tema dari LPMS-III (dev-lpms.len.co.id)
tags: [ui, theme, leno, openmetadata]
dibuat: 2026-11-04
sumber: https://dev-lpms.len.co.id (LPMS-III · Dashboard), dibaca read-only lewat browser
---

# LenO Interface — Ekstraksi Tema

> [!important] Cakupan pemakaian di OpenMetadata
> **Dipakai:** §1 token warna & tipografi, §2 gaya header, §3 gaya sidebar (ukuran, warna, item aktif/hover), §5 gaya kartu. Diterapkan lewat `deploy/ui/leno-theme/leno.css`.
> **Tidak dipakai:** susunan/grup menu LPMS (Overview, Portofolio, Administrasi) dan pola User Access §4 (menu terkunci dengan catatan peran). Menu dan hak akses tetap milik OpenMetadata.

Acuan tampilan "LenO Interface" diambil dari aplikasi LPMS-III (Project Monitoring). Teknologinya Blazor + Ant Design Blazor + Bootstrap, dengan stylesheet `app.css` dan `Len.Apps.UI.LPMS.styles.css`.

## 1. Design tokens (CSS variables `:root`)

| Token | Nilai | Pemakaian |
| :-- | :-- | :-- |
| `--lpms-red` | `#a51c20` | Warna utama: header, aksen menu aktif |
| `--lpms-red-deep` | `#7f1417` | Garis bawah header, bayangan |
| `--lpms-red-ink` | `#a51c20` | Teks menu aktif |
| `--lpms-red-soft` | `#fdecec` | Latar menu aktif |
| `--lpms-red-warn` | `#dc2626` | Peringatan |
| `--lpms-blue` | `#1f6feb` | Aksen info (kartu biru) |
| `--lpms-green` | `#16a34a` | Sukses / "Lancar" |
| `--lpms-amber` | `#f59e0b` | Peringatan ringan |
| `--lpms-bg` | `#fafafa` | Latar halaman |
| `--lpms-surface` | `#ffffff` | Kartu, sidebar |
| `--lpms-border` | `#e5e7eb` | Garis pemisah |
| `--lpms-ink` | `#1f1f1f` | Teks utama |
| `--lpms-ink-soft` | `#6b7280` | Teks sekunder |
| `--lpms-ink-mute` | `#9ca3af` | Teks/menu terkunci |

**Tipografi:** `Poppins, "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif`. Ukuran dasar 15px; judul header 17px/600; label menu 14px.

**Ikon:** Ant Design Icons (`anticon-*`) untuk navigasi; Font Awesome 6.5.2 tersedia.

**Logo:** `/images/leno-logo.png` (99×32) dengan alt "LenO". Ada versi penuh (`lpms-logo-full`) dan mark (`lpms-logo-mark`) untuk sidebar terlipat. Footer sidebar memuat logo Len dan DEFEND ID, plus teks "Len Industri Persero © 2026".

## 2. Header (`header.lpms-header`)

- Latar `#a51c20`, teks putih, tinggi 61px, padding `12px 24px`.
- Garis bawah `1px solid #7f1417`, bayangan `0 2px 6px rgba(127,20,23,.18)`.
- **Kiri:** tombol toggle sidebar 36×36 (latar `rgba(255,255,255,.15)`, radius 6px, ikon `menu-fold`), lalu judul halaman `h1.lpms-header-title`.
- **Kanan:**
  - Dua tombol bulat 34px (latar `rgba(255,255,255,.12)`): Daftar Kerja (`check-square`) dan Notifikasi (`bell`). Badge hitungan merah `#ff4d4f`.
  - Avatar inisial bulat 36px (latar putih, teks merah) + username (`/me/profile`).
  - Tautan "Logout" (`/logout`, putih 70%).

## 3. Sidebar (`aside.lpms-sidebar`)

- **Ukuran:** lebar 248px terbuka; 72px terlipat (`lpms-sidebar--collapsed`, hanya ikon). Latar putih, garis kanan `1px solid #e5e7eb`.
- **Brand (`.lpms-brand`):** logo + judul aplikasi (14px/700, mis. "LPMS-III") + subjudul (11px, abu-abu, mis. "Project Monitoring"), padding `18px 20px`, garis bawah.
- **Grup menu** berlabel huruf kapital kecil: *Overview* (Dashboard, Daftar Kerja, Daftar Proyek), *Portofolio* (Statistik, Project Membership), *Administrasi* (User Management, Org Structure, Settings).
- **Item menu (`.lpms-nav-link`):** tinggi 42px, padding `10px 12px`, gap 12px, radius 8px, ikon + label 14px. Badge hitungan merah di kanan (mis. Daftar Kerja 3).
  - Hover: latar `#f3f4f6`.
  - Aktif: latar `#fdecec`, teks `#a51c20` 600, ditambah garis vertikal kiri 3px `#a51c20` (`::before`).
- **Footer:** logo mitra + hak cipta; disembunyikan saat sidebar terlipat.

## 4. Pola User Access

- **Semua menu tetap ditampilkan.** Menu yang tidak boleh diakses diberi status *terkunci* (`.lpms-nav-link--locked`):
  - teks `#9ca3af`, ikon opasitas 0.4, kursor `not-allowed`, tanpa efek hover, tanpa `href`;
  - catatan peran di bawah label (`.lpms-nav-locked-note`), mis. "Hanya Developer.", "Hanya Admin Bagian Proyek (FP).";
  - tooltip `"<Menu> — <syarat peran>"`.
- Saat sidebar terlipat, catatan disembunyikan; syarat peran tetap tampil lewat tooltip.
- Menu administrasi pengguna (User Management, Org Structure, Settings) terkunci untuk peran non-Developer. Halaman di dalamnya tidak dapat dibuka dengan akun yang dipakai saat ekstraksi.

## 5. Kartu & konten

- **Kartu statistik:** latar putih, radius 10px, border `#f0f0f0`, bayangan `0 2px 8px rgba(0,0,0,.06)`, garis atas berwarna per kategori (biru/hijau/amber/ungu).
- **Kartu proyek:** garis atas merah, chip kode proyek, progress bar, status hijau "Lancar / On Track", tautan "Detail →" merah.
