/* Len Data Governance — bahasa untuk teks buatan kita (menu Explore/Visualisasi, Tempat Sampah, dialog hapus).
 * Mengikuti pilihan bahasa aplikasi (cookie i18next): "id-ID" → Bahasa Indonesia formal, selain itu → English.
 * Satu bahasa per tampilan: tidak ada campuran. Dipakai lewat window.LDG_I18N.t(kunci, {var}). */
(function () {
  "use strict";
  var D = {
    id: {
      explore: "Jelajahi", viz: "Visualisasi", viz_hint: "Visualisasi data Gold (lakehouse Trino)", viz_frame: "Visualisasi data Gold",
      tab_risiko: "Risiko ERM", tab_tata: "Tata Kelola Data", tab_sdm: "SDM", tab_kesegaran: "Kesegaran Data",
      tab_dashboard: "Semua dasbor", tab_grafik: "Grafik", tab_sql: "SQL Lab",
      trash: "Tempat Sampah", trash_card: "Data yang dihapus disimpan {d} hari dan dapat dipulihkan.", back_settings: "← Kembali ke Pengaturan",
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
      explore: "Explore", viz: "Visualization", viz_hint: "Gold data visualization (Trino lakehouse)", viz_frame: "Gold data visualization",
      tab_risiko: "ERM Risk", tab_tata: "Data Governance", tab_sdm: "HR", tab_kesegaran: "Data Freshness",
      tab_dashboard: "All dashboards", tab_grafik: "Charts", tab_sql: "SQL Lab",
      trash: "Trash", trash_card: "Deleted items are kept for {d} days and can be restored.", back_settings: "← Back to Settings",
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
    var v = m ? decodeURIComponent(m[1]) : "";
    return /^id\b/i.test(v) ? "id" : "en";
  }
  function t(k, v) {
    var s = (D[lang()][k] != null ? D[lang()][k] : D.en[k]) || k;
    if (v) Object.keys(v).forEach(function (n) { s = s.split("{" + n + "}").join(v[n]); });
    return s;
  }
  window.LDG_I18N = { lang: lang, t: t };
})();
