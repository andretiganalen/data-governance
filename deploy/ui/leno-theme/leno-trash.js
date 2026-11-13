/* Len Data Governance — Tempat Sampah.
 *  1. Dialog hapus berbahasa Indonesia: menjelaskan akibat dan risiko dengan nada tenang. Penghapusan = pindah ke Tempat Sampah
 *     (gateway mengubah hardDelete=true dari klien jaringan menjadi soft delete; pilihan "hapus permanen" disembunyikan).
 *  2. Kartu "Tempat Sampah" di Settings: daftar data yang dihapus, sisa hari (20 hari), tombol Pulihkan.
 * Token sesi: cookie dg_token (diisi leno-menu.js dari sesi aplikasi). Gaya mengikuti UIx (plan/interface-menu.md). */
(function () {
  "use strict";
  var T = function (k, v) { return window.LDG_I18N ? window.LDG_I18N.t(k, v) : k; };
  var DAYS = 20, ITEM_ID = "len-menu-trash", PANEL_ID = "len-trash", EXPORT_ID = "len-menu-export", PDF_ID = "len-menu-pdf";
  var TYPES = [["glossaryTerms"], ["glossaries"], ["tables"], ["databaseSchemas"], ["databases"], ["dashboards"], ["charts"],
    ["dataProducts"], ["domains"], ["tags"], ["classifications"], ["teams"]];

  function token() { var m = /(?:^|;\s*)dg_token=([^;]+)/.exec(document.cookie); return m ? m[1] : ""; }
  function api(method, path, body) {
    return fetch("/api/v1" + path, {
      method: method, credentials: "same-origin",
      headers: { "Authorization": "Bearer " + token(), "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined
    });
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  /* ---------- gaya ---------- */
  function css() {
    if (document.getElementById("len-trash-css")) return;
    var s = document.createElement("style");
    s.id = "len-trash-css";
    s.textContent =
      ".ld-info{margin:12px 0 0;padding:12px 14px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;font:400 13px/1.55 'UIx Poppins',Arial,sans-serif;color:#364153;text-align:left}" +
      ".ld-info p{margin:0 0 6px}.ld-info .ld-lead{font-weight:500;color:#101828}.ld-info .ld-h{margin:10px 0 4px;font-weight:600;color:#101828;font-size:12px}" +
      ".ld-info ul{margin:0;padding-left:18px;list-style:disc}.ld-info li{margin:0 0 3px}.ld-info .ld-foot{margin:10px 0 0;color:#6a7282;font-size:12px}" +
      "#" + PANEL_ID + "{position:fixed;z-index:400;background:var(--uix-page,#f9fafb);overflow:auto;padding:16px}" +
      "#" + PANEL_ID + " .lt-gap{margin-top:16px}" +
      "#" + PANEL_ID + " td.ant-table-cell{vertical-align:middle}" +
      "#" + PANEL_ID + " .lt-name{font-weight:500;word-break:break-all}" +
      "#" + PANEL_ID + " .lt-fqn{margin-top:2px;font-size:12px;opacity:.7;word-break:break-all}" +
      "#" + PANEL_ID + " .lt-empty{padding:40px 16px;text-align:center;opacity:.7}" +
      "#" + PANEL_ID + " .lt-msg{margin-top:16px}" +
      /* dialog hapus: tenang, bukan alarm (ikon abu-abu, tombol merah UIx biasa, bukan merah menyala) */
      ".ld-dlg [data-featured-icon]{background:#f3f4f6!important;color:#6a7282!important}" +
      ".ld-dlg [data-testid=confirm-button]{background:#ae2524!important;color:#fff!important;white-space:nowrap}" +
      ".ld-dlg [data-testid=confirm-button]:hover{background:#8e1e1d!important}";
    document.head.appendChild(s);
  }

  /* ---------- 1. dialog hapus ---------- */
  var INFO_CLASS = "ld-info";
  function infoBlock(name) {
    var d = el("div", INFO_CLASS);
    var lead = el("p", "ld-lead"); lead.textContent = T("dlg_lead", { n: name });
    d.appendChild(lead);
    function sec(title, items) {
      d.appendChild(el("p", "ld-h", title));
      var ul = el("ul"); items.forEach(function (t) { ul.appendChild(el("li", null, t)); }); d.appendChild(ul);
    }
    sec(T("dlg_h1"), [T("dlg_1a"), T("dlg_1b", { d: DAYS }), T("dlg_1c", { d: DAYS })]);
    sec(T("dlg_h2"), [T("dlg_2a"), T("dlg_2b")]);
    d.appendChild(el("p", "ld-foot", T("dlg_foot")));
    return d;
  }
  function setText(node, text) { if (node && node.textContent !== text) node.textContent = text; }
  function fixDialog(d) {
    var confirm = d.querySelector('[data-testid="confirm-button"]');
    var head = d.querySelector('[data-testid="modal-header"]');
    if (!confirm || !head) return;
    var hs = head.querySelector("span, .prose span") || head;
    if (!d.dataset.lenName) {
      var t = (hs.textContent || "").trim();
      if (!/^(Delete|Hapus)\b/i.test(t)) return;                        // bukan dialog hapus
      var q = /"([^"]+)"/.exec(t);
      d.dataset.lenName = q ? q[1] : t.replace(/^(Delete|Hapus)\s+/i, "");
    }
    var name = d.dataset.lenName;
    css(); d.classList.add("ld-dlg");
    [hs, hs.parentElement].forEach(function (x) { if (x) { x.style.whiteSpace = "normal"; x.style.overflow = "visible"; x.style.textOverflow = "clip"; } });
    setText(hs, T("dlg_title", { n: name }));
    var group = d.querySelector('[role="radiogroup"]');         // jenis A: pilihan lunak/permanen
    if (group) {
      group.style.display = "none";
      var soft = d.querySelector('[data-testid="soft-delete"] input'); if (soft && !soft.checked) soft.click();
    }
    var p = head.querySelector("p");                            // jenis B: kalimat "Are you sure..."
    if (p && !p.classList.contains(INFO_CLASS)) p.style.display = "none";
    if (!d.querySelector("." + INFO_CLASS)) {
      var host = group ? group.parentElement : head.parentElement;
      host.insertBefore(infoBlock(name), group ? group : head.nextSibling);
    }
    var cancel = d.querySelector('[data-testid="cancel-button"], [data-testid="discard-button"]');
    setText(cancel && (cancel.querySelector("[data-text]") || cancel), T("cancel"));
    setText(confirm.querySelector("[data-text]") || confirm, T("confirm"));
  }
  function scanDialogs() { document.querySelectorAll('[role="dialog"]').forEach(fixDialog); }

  /* ---------- 2. menu & panel Tempat Sampah ---------- */
  var panelOpen = false;
  function place(panel) {   // persis menempel pada area konten utama (di kanan sidebar, di bawah bilah atas)
    var main = document.querySelector("main.ant-layout-content");
    var r = main ? main.getBoundingClientRect() : null;
    if (!r || !r.height) {
      var side = document.querySelector(".left-sidebar-layout, .ant-layout-sider");
      var nav = document.querySelector("header.ant-layout-header:not(.pricing-banner)");
      r = { left: side ? side.getBoundingClientRect().right : 0, top: nav ? nav.getBoundingClientRect().bottom : 0 };
    }
    panel.style.left = Math.round(r.left) + "px"; panel.style.top = Math.round(r.top) + "px";
    panel.style.right = "0"; panel.style.bottom = "0";
  }
  function daysLeft(ts) { return Math.max(0, DAYS - Math.floor((Date.now() - ts) / 86400000)); }
  function fmt(ts) { try { return new Date(ts).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }); } catch (e) { return new Date(ts).toISOString(); } }

  function load(panel) {
    var body = panel.querySelector(".lt-body"); body.textContent = T("loading");
    var jobs = TYPES.map(function (t) {
      return api("GET", "/" + t[0] + "?include=deleted&limit=200&fields=deleted").then(function (r) { return r.ok ? r.json() : { data: [] }; })
        .then(function (j) { return (j.data || []).filter(function (e) { return e.deleted; }).map(function (e) { return { t: t, e: e }; }); })
        .catch(function () { return []; });
    });
    Promise.all(jobs).then(function (parts) {
      var rows = [].concat.apply([], parts).sort(function (a, b) { return (b.e.updatedAt || 0) - (a.e.updatedAt || 0); });
      body.textContent = "";
      var card = el("div", "ant-card ant-card-bordered lt-gap"), cb = el("div", "ant-card-body");
      card.appendChild(cb); body.appendChild(card);
      if (!rows.length) { cb.appendChild(el("div", "lt-empty", T("empty"))); return; }
      var wrap = el("div", "ant-table-wrapper"), tbl = el("div", "ant-table"), cont = el("div", "ant-table-container");
      var tb = el("table"), th = el("thead", "ant-table-thead"), hr = el("tr");
      [T("h_name"), T("h_type"), T("h_by"), T("h_at"), T("h_left"), ""].forEach(function (h) { hr.appendChild(el("th", "ant-table-cell", h)); });
      th.appendChild(hr); tb.appendChild(th);
      var tbody = el("tbody", "ant-table-tbody");
      rows.forEach(function (x) {
        var tr = el("tr", "ant-table-row"), n = x.e.displayName || x.e.name;
        var nc = el("td", "ant-table-cell"); nc.appendChild(el("div", "lt-name", n));
        if (x.e.fullyQualifiedName && x.e.fullyQualifiedName !== n) nc.appendChild(el("div", "lt-fqn", x.e.fullyQualifiedName));
        tr.appendChild(nc);
        var c1 = el("td", "ant-table-cell"); c1.appendChild(el("span", "ant-tag", T("t_" + x.t[0]))); tr.appendChild(c1);
        tr.appendChild(el("td", "ant-table-cell", x.e.updatedBy || "-"));
        tr.appendChild(el("td", "ant-table-cell", x.e.updatedAt ? fmt(x.e.updatedAt) : "-"));
        var left = x.e.updatedAt ? daysLeft(x.e.updatedAt) : 0;
        tr.appendChild(el("td", "ant-table-cell", left > 0 ? T("left", { n: left }) : T("soon")));
        var act = el("td", "ant-table-cell"), b = el("button", "ant-btn ant-btn-default ant-btn-sm"); b.type = "button";
        b.appendChild(el("span", null, T("restore")));
        b.addEventListener("click", function () { restore(panel, x, tr, b, n); });
        act.appendChild(b); tr.appendChild(act); tbody.appendChild(tr);
      });
      tb.appendChild(tbody); cont.appendChild(tb); tbl.appendChild(cont); wrap.appendChild(tbl); cb.appendChild(wrap);
    });
  }
  function msg(panel, text) {
    var m = panel.querySelector(".lt-msg"); if (m) m.remove();
    m = el("div", "ant-alert ant-alert-info lt-msg"); m.appendChild(el("div", "ant-alert-message", text));
    panel.querySelector(".lt-head").after(m);
    setTimeout(function () { if (m.parentNode) m.remove(); }, 8000);
  }
  function setBtn(btn, text) { var s = btn.querySelector("span"); if (s) s.textContent = text; }
  function restore(panel, x, tr, btn, name) {
    btn.disabled = true; setBtn(btn, T("restoring"));
    api("PUT", "/" + x.t[0] + "/restore", { id: x.e.id }).then(function (r) {
      if (r.ok) { tr.remove(); msg(panel, T("restored", { n: name })); return; }
      btn.disabled = false; setBtn(btn, T("restore"));
      msg(panel, T("restore_fail", { n: name }));
    }).catch(function () { btn.disabled = false; setBtn(btn, T("restore")); msg(panel, T("offline")); });
  }
  function showPanel() {
    css();
    var panel = document.getElementById(PANEL_ID);
    if (!panel) {
      panel = el("div"); panel.id = PANEL_ID;
      // kepala halaman: struktur sama dengan halaman bawaan (kartu + page-header-container + heading/sub-heading)
      var head = el("div", "ant-card ant-card-bordered lt-head"), hb = el("div", "ant-card-body"), row = el("div", "ant-row");
      var c1 = el("div", "ant-col ant-col-16"), ph = el("div", "page-header-container");
      var h = el("h5", "ant-typography heading m-b-0", T("trash")); h.setAttribute("data-testid", "heading");
      var sp = el("div", "ant-space ant-space-horizontal ant-space-align-center"), si = el("div", "ant-space-item");
      si.appendChild(h); sp.appendChild(si); ph.appendChild(sp);
      var sub = el("div", "ant-typography sub-heading", T("trash_sub", { d: DAYS })); sub.setAttribute("data-testid", "sub-heading");
      ph.appendChild(sub); c1.appendChild(ph);
      var c2 = el("div", "ant-col ant-col-8 d-flex justify-end");
      var back = el("button", "ant-btn ant-btn-default"); back.type = "button"; back.appendChild(el("span", null, T("back_settings")));
      back.addEventListener("click", hidePanel); c2.appendChild(back);
      row.appendChild(c1); row.appendChild(c2); hb.appendChild(row); head.appendChild(hb); panel.appendChild(head);
      panel.appendChild(el("div", "lt-body"));
      document.body.appendChild(panel);
      window.addEventListener("resize", function () { place(panel); });
    }
    place(panel); panel.style.display = "block"; panelOpen = true;
    document.documentElement.classList.add("dg-trash-open");
    load(panel);
  }
  function hidePanel() {
    var p = document.getElementById(PANEL_ID); if (p) p.style.display = "none";
    panelOpen = false; document.documentElement.classList.remove("dg-trash-open");
  }
  /* Ikon kartu Settings: struktur sama dengan ikon bawaan (svg 89x89, kotak rx 28 berwarna pucat + gambar garis di tengah, ukuran 1em). */
  var BOX = '<path d="M0 28C0 12.536 12.536 0 28 0H61C76.464 0 89 12.536 89 28V61C89 76.464 76.464 89 61 89H28C12.536 89 0 76.464 0 61V28Z" fill="';
  function cardSvg(fill, glyph) {
    return '<svg viewBox="0 0 89 89" fill="none" xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" aria-hidden="true" focusable="false">' +
      BOX + fill + '"/><g transform="translate(24.5 24.5) scale(.8333)">' + glyph + "</g></svg>";
  }
  var TRASH = cardSvg("#F2F4F7",
    '<g stroke="#4a5565" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M6 12h36M18 12V8a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v4M10 12l2.4 28a3 3 0 0 0 3 2.8h16.4a3 3 0 0 0 3-2.8L37 12"/>' +
    '<g stroke-width="2"><path d="M21.2 24.6 24 20l2.2 3.4M25.6 30.2h-3.5a1.6 1.6 0 0 1-1.4-2.4l.5-.8M29.2 26.4l1.4 2.4a1.6 1.6 0 0 1-1.4 2.4M22.6 33l-2-2.8 2.8-.6M27 33.2l3-1.6-2.6-1.4M29.2 26.4 26.6 25l.7 2.6"/></g></g>');
  var EXCEL = cardSvg("#F2F4F7",
    '<g stroke="#4a5565" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M28 5H13a3 3 0 0 0-3 3v32a3 3 0 0 0 3 3h22a3 3 0 0 0 3-3V15z"/><path d="M28 5v10h10"/>' +
    '<path d="M24 22v13M18.5 30l5.5 5.5 5.5-5.5"/></g>');
  var PDF = cardSvg("#F2F4F7",
    '<g stroke="#4a5565" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M28 5H13a3 3 0 0 0-3 3v32a3 3 0 0 0 3 3h22a3 3 0 0 0 3-3V15z"/><path d="M28 5v10h10"/>' +
    '<path d="M16 30h16M16 36h10M16 24h8"/></g>');
  var THEME = cardSvg("#FEF3F2",
    '<g stroke="#ae2524" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M24 5C13.5 5 5 13 5 23.5S13.2 42 21 42c3 0 4-1.8 4-3.6 0-3.4 2-4.4 4.6-4.4H36c4 0 7-2.8 7-7C43 14 34.5 5 24 5z"/>' +
    '<circle cx="15" cy="23" r="2.4"/><circle cx="20" cy="14.5" r="2.4"/><circle cx="30" cy="14.5" r="2.4"/><circle cx="35" cy="23" r="2.4"/></g>');
  function tile(ic, svg) {   // hanya mengganti isi ikon; ukuran/kotak ikut gaya kartu bawaan
    ic.innerHTML = '<span role="img" class="anticon">' + svg + "</span>";
    ic.setAttribute("data-ldg-icon", "1");
  }
  function decorateCards() {   // kartu "Preferences" → ikon tema (outline merah UIx)
    document.querySelectorAll(".setting-card-item").forEach(function (card) {
      var t = card.querySelector(".setting-card-content .font-semibold");
      var ic = card.querySelector(".setting-card-icon");
      if (!t || !ic || ic.getAttribute("data-ldg-icon")) return;
      if (/^(preferences|preferensi|appearance|tampilan)$/i.test(t.textContent.trim())) tile(ic, THEME);
    });
  }
  function ensureCard() {
    if (/^\/settings(\/|$)/.test(location.pathname)) decorateCards();
    ensureTrashCard();
    ensureExportCard();
    ensurePdfCard();
  }
  function ensureTrashCard() {   // kartu "Tempat Sampah" di halaman Settings (di samping Services, Notifications, ...)
    if (!/^\/settings\/?$/.test(location.pathname) || document.getElementById(ITEM_ID)) return;
    var box = document.querySelector(".setting-items-container"); if (!box || !box.firstElementChild) return;
    var col = box.firstElementChild.cloneNode(true);
    col.id = ITEM_ID;
    var card = col.querySelector(".ant-card"); if (!card) return;
    card.setAttribute("data-testid", "tempat-sampah"); card.style.cursor = "pointer"; card.style.flex = "1"; card.style.alignSelf = "stretch"; col.style.padding = "0 10px"; col.style.display = "flex"; col.style.alignItems = "stretch";
    var ic = card.querySelector(".setting-card-icon"); if (ic) tile(ic, TRASH);
    var t = card.querySelector(".setting-card-content .font-semibold"); if (t) t.textContent = T("trash");
    var d = card.querySelector(".setting-card-content div"); if (d) { d.textContent = T("trash_card", { d: DAYS }); d.removeAttribute("title"); }
    card.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); showPanel(); }, true);
    box.appendChild(col);
  }
  /* Unduh Excel hasil Data Governance: layanan ldg-export (gateway /_export/) menentukan hak dan cakupan dari token sesi. */
  var exportBusy = false;
  function setExportText(card, key, v) { var d = card.querySelector(".setting-card-content div"); if (d) { d.textContent = T(key, v); d.removeAttribute("title"); } }
  function runExport(card) {
    if (exportBusy) return; exportBusy = true; setExportText(card, "export_busy");
    var H = { "Authorization": "Bearer " + token() }, back = function (k) { setTimeout(function () { setExportText(card, "export_card"); }, 6000); if (k) setExportText(card, k); exportBusy = false; };
    fetch("/_export/governance.xlsx", { headers: H, credentials: "same-origin" }).then(function (r) {
      if (r.status === 403) return back("export_denied");
      if (r.status === 401) return back("export_login");
      if (!r.ok) return back("export_error");
      var name = (/filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "") || [])[1] || "Data Governance.xlsx";
      return r.blob().then(function (b) {
        var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; document.body.appendChild(a); a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
        back("export_done");
      });
    }).catch(function () { back("export_error"); });
  }
  function ensureExportCard() {   // kartu "Unduh Excel" di Settings, sebelah Tempat Sampah; struktur disalin dari kartu bawaan
    if (!/^\/settings\/?$/.test(location.pathname) || document.getElementById(EXPORT_ID)) return;
    var box = document.querySelector(".setting-items-container"); if (!box || !box.firstElementChild) return;
    var col = box.firstElementChild.cloneNode(true);
    col.id = EXPORT_ID;
    var card = col.querySelector(".ant-card"); if (!card) return;
    card.setAttribute("data-testid", "unduh-excel"); card.style.cursor = "pointer"; card.style.flex = "1"; card.style.alignSelf = "stretch"; col.style.padding = "0 10px"; col.style.display = "flex"; col.style.alignItems = "stretch";
    var ic = card.querySelector(".setting-card-icon"); if (ic) tile(ic, EXCEL);
    var t = card.querySelector(".setting-card-content .font-semibold"); if (t) t.textContent = T("export");
    setExportText(card, "export_card");
    card.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); runExport(card); }, true);
    box.appendChild(col);
  }
  /* Terbitkan Revisi PDF (Glosarium Fungsi Generik): hanya tampil untuk Admin Data Governance; ldg-export mencatat permintaan,
     timer glosarium 10 menit menerbitkannya ke Dokumen › Reference. */
  var pdfAllowed = null, pdfBusy = false;
  function pdfStatus(card) {
    fetch("/_export/fungsi-pdf", { headers: { "Authorization": "Bearer " + token() }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
        if (!s) return;
        setExportText(card, s.menunggu ? "pdf_pending" : (s.rev ? "pdf_rev" : "pdf_none"),
          { r: String(s.rev || 0).padStart(2, "0"), t: s.tanggal || "", c: s.ada_perubahan ? T("pdf_changed") : "" });
      }).catch(function () {});
  }
  function runPdf(card) {
    if (pdfBusy) return; pdfBusy = true; setExportText(card, "pdf_busy");
    fetch("/_export/fungsi-pdf", { method: "POST", headers: { "Authorization": "Bearer " + token() }, credentials: "same-origin" })
      .then(function (r) { setExportText(card, r.status === 403 ? "pdf_denied" : r.ok ? "pdf_wait" : "export_error"); })
      .catch(function () { setExportText(card, "export_error"); })
      .then(function () { pdfBusy = false; });
  }
  function ensurePdfCard() {
    if (!/^\/settings\/?$/.test(location.pathname) || document.getElementById(PDF_ID)) return;
    if (pdfAllowed === null) {
      pdfAllowed = false;
      fetch("/_export/me", { headers: { "Authorization": "Bearer " + token() }, credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : {}; }).then(function (m) { pdfAllowed = !!m.pdf; ensurePdfCard(); }).catch(function () { pdfAllowed = null; });
      return;
    }
    if (!pdfAllowed) return;
    var box = document.querySelector(".setting-items-container"); if (!box || !box.firstElementChild) return;
    var col = box.firstElementChild.cloneNode(true);
    col.id = PDF_ID;
    var card = col.querySelector(".ant-card"); if (!card) return;
    card.setAttribute("data-testid", "terbitkan-revisi-pdf"); card.style.cursor = "pointer"; card.style.flex = "1"; card.style.alignSelf = "stretch"; col.style.padding = "0 10px"; col.style.display = "flex"; col.style.alignItems = "stretch";
    var ic = card.querySelector(".setting-card-icon"); if (ic) tile(ic, PDF);
    var t = card.querySelector(".setting-card-content .font-semibold"); if (t) t.textContent = T("pdf");
    setExportText(card, "pdf_card");
    card.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); runPdf(card); }, true);
    box.appendChild(col); pdfStatus(card);
  }
  var lastLang = "";
  function ensure() {
    var lg = window.LDG_I18N ? window.LDG_I18N.lang() : "";
    if (lg !== lastLang) {   // bahasa berganti → bangun ulang teks panel & kartu
      lastLang = lg;
      ["len-trash", ITEM_ID, EXPORT_ID, PDF_ID].forEach(function (id) { var n = document.getElementById(id); if (n) n.remove(); });
      panelOpen = false; document.documentElement.classList.remove("dg-trash-open");
    }
    ensureCard();
    if (panelOpen && !/^\/settings\/?$/.test(location.pathname)) hidePanel();
  }
  ["pushState", "replaceState"].forEach(function (k) {
    var orig = history[k];
    history[k] = function () { var r = orig.apply(this, arguments); if (panelOpen) hidePanel(); return r; };
  });
  window.addEventListener("popstate", hidePanel);

  var pending = false;
  if (document.head) css(); else document.addEventListener("DOMContentLoaded", css);
  new MutationObserver(function () {
    if (pending) return; pending = true;
    (window.requestAnimationFrame || setTimeout)(function () { pending = false; ensure(); scanDialogs(); });
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
