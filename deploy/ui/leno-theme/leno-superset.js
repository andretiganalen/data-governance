/* Len Data Governance — Superset (Visualisasi) di dalam kerangka aplikasi utama.
 *  1. Tanda "dg-embedded" saat ditampilkan dalam iframe (CSS menyembunyikan chrome Superset).
 *  2. Bahasa Indonesia: paket bahasa resmi (translations/id, dibangun di image) menerjemahkan sebagian besar teks; komponen Superset 6
 *     tertentu (mis. label filter daftar, placeholder "Choose…") tidak membacanya. Untuk itu teks chrome yang PERSIS sama dengan kunci
 *     kamus (/_leno/i18n/superset-id.json) diganti di DOM. Isi data (judul dasbor/grafik, nama kolom, SQL, tabel hasil) tidak disentuh.
 *     Aktif hanya saat cookie i18next = id-*. */
(function () {
  "use strict";
  if (window.top !== window.self) document.documentElement.classList.add("dg-embedded");
  var m = /(?:^|;\s*)i18next=([^;]+)/.exec(document.cookie);
  var lang = m ? decodeURIComponent(m[1]) : (navigator.language || "");
  if (!/^id\b/i.test(lang)) return;

  var SKIP = "script,style,textarea,input,pre,code,svg,canvas,.ace_editor,[contenteditable=true],.ReactVirtualized__Table," +
    ".ant-table-tbody a,.dashboard-content,.dashboard-grid,.chart-container,.slice_container,.header-title,.editable-title,.ant-card-meta-title,.ant-breadcrumb a";
  var ATTRS = ["placeholder", "title", "aria-label"];
  var dict = null;

  function tr(s) {
    var k = s.trim();
    if (!k || k.length > 400) return null;
    var v = dict[k];
    return v && v !== k ? s.replace(k, v) : null;
  }
  function walk(root) {
    if (!dict || !root) return;
    var base = root.nodeType === 1 ? root : root.parentElement;
    if (!base || base.closest(SKIP)) return;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n;
    while ((n = w.nextNode())) {
      var p = n.parentElement;
      if (!p || p.closest(SKIP)) continue;
      var t = tr(n.nodeValue); if (t != null) n.nodeValue = t;
    }
    if (root.querySelectorAll) root.querySelectorAll("[placeholder],[title],[aria-label]").forEach(function (e) {
      if (e.closest(SKIP) && e.tagName !== "INPUT") return;
      ATTRS.forEach(function (a) { var v = e.getAttribute(a); if (v) { var t = tr(v); if (t != null) e.setAttribute(a, t); } });
    });
  }
  var pending = false, queue = [];
  function flush() { pending = false; var q = queue; queue = []; q.forEach(walk); }
  function start() {
    walk(document.body);
    new MutationObserver(function (list) {
      list.forEach(function (r) {
        if (r.type === "characterData") queue.push(r.target.parentElement);
        else r.addedNodes.forEach(function (n) { if (n.nodeType === 1 || n.nodeType === 3) queue.push(n); });
      });
      if (!pending) { pending = true; (window.requestAnimationFrame || setTimeout)(flush); }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  fetch("/_leno/i18n/superset-id.json", { credentials: "omit" }).then(function (r) { return r.json(); })
    .then(function (d) { dict = d; if (document.body) start(); else document.addEventListener("DOMContentLoaded", start); })
    .catch(function () { /* tanpa kamus: tetap berjalan dengan paket bahasa bawaan */ });
})();
