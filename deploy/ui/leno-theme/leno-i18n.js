/* Len Data Governance — bahasa untuk teks buatan kita (menu Explore/Visualisasi, Tempat Sampah, dialog hapus).
 * Mengikuti pilihan bahasa aplikasi (cookie i18next): "id-ID" → Bahasa Indonesia formal, selain itu → English.
 * Satu bahasa per tampilan: tidak ada campuran. Dipakai lewat window.LDG_I18N.t(kunci, {var}). */
(function () {
  "use strict";
  var D = {
    id: {
      land_viz: "Visualisasi", land_chip: "Katalog Metadata ERM", land_title: "Tata kelola data dalam satu tempat",
      land_desc: "Temukan aset data, glosarium bisnis, klasifikasi sensitivitas, dan pemilik data.",
      land_login_ids: "Masuk dengan IDS", land_login: "Masuk",
      land_pending: "Login IDS sedang diaktivasi. Untuk sementara, gunakan akun lokal dari admin UV-3.",
      land_b1: "Single sign-on dengan akun IDS (email kantor)", land_b2: "Akses sesuai peran: Pemilik Data, Steward Data, Pengguna Data",
      land_b3: "Hanya dapat diakses dari jaringan internal",
      land_footer: "dev-data.len.co.id · lingkungan pengembangan · Len Industri Persero © 2026",
      st_title: "Len Data Governance sedang dimulai…", st_text: "Halaman ini dimuat ulang otomatis setiap 15 detik.", st_back: "Kembali ke beranda",
      ref_back: "← Kembali", ref_back_aria: "Kembali ke halaman sebelumnya", ref_head: "Len Data Governance · Referensi", ref_h2: "Dokumen referensi",
      ref_note: "Urutan: terbaru di atas. Nama berkas apa adanya: <b>YYMMDD CC Nama File.ext</b> (tanggal unggah, nomor unggah, nama). Versi lama tetap tersedia. Dokumen internal Len, tidak terkontrol: versi terbaru ada di aplikasi LenO.",
      ref_name: "Nama berkas", ref_size: "Ukuran", ref_loading: "Memuat…", ref_none: "Belum ada berkas.",
      ref_login: "Silakan masuk ke aplikasi terlebih dahulu. Dokumen referensi kini berada di Pusat Konteks › Dokumen › Reference.",
      explore: "Jelajahi", viz: "Visualisasi", viz_hint: "Visualisasi data Gold (lakehouse Trino)", viz_frame: "Visualisasi data Gold",
      tab_risiko: "Risiko ERM", tab_tata: "Tata Kelola Data", tab_sdm: "SDM", tab_kesegaran: "Kesegaran Data",
      tab_dashboard: "Semua dasbor", tab_grafik: "Grafik", tab_sql: "SQL Lab",
      trash: "Tempat Sampah", trash_card: "Data yang dihapus disimpan {d} hari dan dapat dipulihkan.", back_settings: "← Kembali ke Pengaturan",
      docs_created: "Dibuat {d}", docs_sorted: "Urutan: Tanggal dibuat (terbaru dahulu)",
      restored: "“{n}” telah dipulihkan dan tampil kembali.", trash_sub: "Data yang dihapus disimpan di sini selama {d} hari, kemudian dihapus permanen secara otomatis. Pilih Pulihkan untuk mengembalikannya.",
      loading: "Memuat…", empty: "Tempat Sampah kosong. Tidak ada data yang menunggu penghapusan.",
      h_name: "Nama", h_type: "Jenis", h_by: "Dihapus oleh", h_at: "Dihapus pada", h_left: "Sisa waktu",
      left: "{n} hari lagi dapat dipulihkan", soon: "Segera dihapus permanen", restore: "Pulihkan", restoring: "Memulihkan…",
      restore_fail: "“{n}” belum dapat dipulihkan. Kemungkinan nama yang sama sudah digunakan atau Anda belum memiliki hak untuk memulihkannya. Silakan hubungi admin Data Governance bila diperlukan.",
      offline: "Koneksi terputus. Silakan coba lagi beberapa saat lagi.",
      t_glossaryTerms: "Istilah Glosarium", t_glossaries: "Glosarium", t_tables: "Tabel", t_databaseSchemas: "Skema", t_databases: "Basis Data",
      t_dashboards: "Dasbor", t_charts: "Grafik", t_dataProducts: "Produk Data", t_domains: "Domain", t_tags: "Label", t_classifications: "Klasifikasi", t_teams: "Tim / Fungsi",
      dlg_title: "Pindahkan “{n}” ke Tempat Sampah?", dlg_lead: "“{n}” akan disimpan di Tempat Sampah, tidak langsung dihapus.",
      dlg_h1: "Yang akan terjadi",
      dlg_1a: "Data tidak lagi tampil pada pencarian, daftar, dan dasbor.",
      dlg_1b: "Selama {d} hari, Anda atau admin dapat memulihkannya melalui Pengaturan › Tempat Sampah.",
      dlg_1c: "Setelah {d} hari, data dihapus permanen secara otomatis dan tidak dapat dipulihkan.",
      dlg_h2: "Perlu diperhatikan",
      dlg_2a: "Tautan ke data ini (istilah, kolom, pemilik, dasbor) sementara tidak aktif, dan kembali normal setelah data dipulihkan.",
      dlg_2b: "Yang dipindahkan hanya catatan di Len Data Governance; data sumber di Trino tidak berubah.",
      dlg_foot: "Ragu? Pilih Batal, tidak ada yang berubah.", cancel: "Batal", confirm: "Ya, pindahkan"
    },
    en: {
      land_viz: "Visualization", land_chip: "ERM Metadata Catalog", land_title: "Data governance in one place",
      land_desc: "Find data assets, the business glossary, sensitivity classifications, and data owners.",
      land_login_ids: "Sign in with IDS", land_login: "Sign in",
      land_pending: "IDS sign-in is being activated. For now, use a local account from the UV-3 admin.",
      land_b1: "Single sign-on with your IDS account (work email)", land_b2: "Role-based access: Data Owner, Data Steward, Data User",
      land_b3: "Accessible only from the internal network",
      land_footer: "dev-data.len.co.id · development environment · Len Industri Persero © 2026",
      st_title: "Len Data Governance is starting…", st_text: "This page reloads automatically every 15 seconds.", st_back: "Back to home",
      ref_back: "← Back", ref_back_aria: "Back to the previous page", ref_head: "Len Data Governance · Reference", ref_h2: "Reference documents",
      ref_note: "Order: newest first. File names as-is: <b>YYMMDD CC File Name.ext</b> (upload date, upload number, name). Older versions remain available. Internal Len documents, uncontrolled: the latest version is in the LenO app.",
      ref_name: "File name", ref_size: "Size", ref_loading: "Loading…", ref_none: "No files yet.",
      ref_login: "Please sign in to the app first. Reference documents are now in Context Center › Documents › Reference.",
      explore: "Explore", viz: "Visualization", viz_hint: "Gold data visualization (Trino lakehouse)", viz_frame: "Gold data visualization",
      tab_risiko: "ERM Risk", tab_tata: "Data Governance", tab_sdm: "HR", tab_kesegaran: "Data Freshness",
      tab_dashboard: "All dashboards", tab_grafik: "Charts", tab_sql: "SQL Lab",
      trash: "Trash", trash_card: "Deleted items are kept for {d} days and can be restored.", back_settings: "← Back to Settings",
      docs_created: "Created {d}", docs_sorted: "Sorted by: Created date (newest first)",
      restored: "“{n}” has been restored and is visible again.",
      trash_sub: "Deleted items are kept here for {d} days, then permanently deleted automatically. Choose Restore to bring an item back.",
      loading: "Loading…", empty: "The Trash is empty. Nothing is waiting to be deleted.",
      h_name: "Name", h_type: "Type", h_by: "Deleted by", h_at: "Deleted on", h_left: "Time left",
      left: "{n} days left to restore", soon: "Permanent deletion soon", restore: "Restore", restoring: "Restoring…",
      restore_fail: "“{n}” could not be restored. The same name may already be in use, or you may not have permission to restore it. Please contact the Data Governance admin if needed.",
      offline: "Connection lost. Please try again in a moment.",
      t_glossaryTerms: "Glossary Term", t_glossaries: "Glossary", t_tables: "Table", t_databaseSchemas: "Schema", t_databases: "Database",
      t_dashboards: "Dashboard", t_charts: "Chart", t_dataProducts: "Data Product", t_domains: "Domain", t_tags: "Tag", t_classifications: "Classification", t_teams: "Team / Function",
      dlg_title: "Move “{n}” to Trash?", dlg_lead: "“{n}” will be kept in the Trash, not deleted right away.",
      dlg_h1: "What will happen",
      dlg_1a: "The item will no longer appear in search, lists, and dashboards.",
      dlg_1b: "For {d} days, you or an admin can restore it from Settings › Trash.",
      dlg_1c: "After {d} days, it is permanently deleted automatically and cannot be restored.",
      dlg_h2: "Please note",
      dlg_2a: "Links to this item (terms, columns, owners, dashboards) are temporarily inactive and return to normal once it is restored.",
      dlg_2b: "Only the record in Len Data Governance is moved; the source data in Trino is unchanged.",
      dlg_foot: "Not sure? Choose Cancel and nothing changes.", cancel: "Cancel", confirm: "Yes, move to Trash"
    }
  };
  function lang() {
    var m = /(?:^|;\s*)i18next=([^;]+)/.exec(document.cookie);
    var v = m ? decodeURIComponent(m[1]) : (navigator.language || "");
    return /^id\b/i.test(v) ? "id" : "en";
  }
  function t(k, v) {
    var s = (D[lang()][k] != null ? D[lang()][k] : D.en[k]) || k;
    if (v) Object.keys(v).forEach(function (n) { s = s.split("{" + n + "}").join(v[n]); });
    return s;
  }
  function apply(root) {   // halaman statis: data-i18n (teks), data-i18n-html (HTML sederhana), data-i18n-aria
    root = root || document;
    root.querySelectorAll("[data-i18n]").forEach(function (e) { e.textContent = t(e.getAttribute("data-i18n")); });
    root.querySelectorAll("[data-i18n-html]").forEach(function (e) { e.innerHTML = t(e.getAttribute("data-i18n-html")); });
    root.querySelectorAll("[data-i18n-aria]").forEach(function (e) { e.setAttribute("aria-label", t(e.getAttribute("data-i18n-aria"))); });
    document.documentElement.setAttribute("lang", lang());
  }
  function setLang(l) {   // pengalih bahasa halaman statis: tulis cookie yang sama dengan aplikasi (i18next)
    document.cookie = "i18next=" + (l === "id" ? "id-ID" : "en-US") + "; path=/; max-age=31536000; SameSite=Lax";
    apply(document);
    document.dispatchEvent(new CustomEvent("ldg-lang"));
  }
  window.LDG_I18N = { lang: lang, t: t, apply: apply, setLang: setLang };
  if (document.querySelector("[data-i18n],[data-i18n-html],[data-i18n-aria]")) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { apply(document); });
    else apply(document);
  }
})();
