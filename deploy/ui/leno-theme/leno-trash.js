/* Len Data Governance — Tempat Sampah.
 *  1. Dialog hapus berbahasa Indonesia: menjelaskan akibat dan risiko dengan nada tenang. Penghapusan = pindah ke Tempat Sampah
 *     (gateway mengubah hardDelete=true dari klien jaringan menjadi soft delete; pilihan "hapus permanen" disembunyikan).
 *  2. Kartu "Tempat Sampah" di Settings: daftar data yang dihapus, sisa hari (20 hari), tombol Pulihkan.
 * Token sesi: cookie dg_token (diisi leno-menu.js dari sesi aplikasi). Gaya mengikuti UIx (plan/interface-menu.md). */
(function () {
  "use strict";
  var DAYS = 20, ITEM_ID = "len-menu-trash", PANEL_ID = "len-trash";
  var TYPES = [["glossaryTerms", "Istilah Glosarium"], ["glossaries", "Glosarium"], ["tables", "Tabel"],
    ["databaseSchemas", "Skema"], ["databases", "Database"], ["dashboards", "Dashboard"], ["charts", "Grafik"],
    ["dataProducts", "Data Product"], ["domains", "Domain"], ["tags", "Tag"], ["classifications", "Klasifikasi"], ["teams", "Tim / Fungsi"]];

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
      "#" + PANEL_ID + "{position:fixed;z-index:400;background:#f9fafb;overflow:auto;padding:20px 24px;font:400 13px/1.5 'UIx Poppins',Arial,sans-serif;color:#364153}" +
      "#" + PANEL_ID + " h2{margin:0 0 4px;font:600 18px 'UIx Poppins',Arial,sans-serif;color:#101828}" +
      "#" + PANEL_ID + " .lt-sub{margin:0 0 16px;color:#6a7282}" +
      "#" + PANEL_ID + " .lt-card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 0 0 1px rgba(16,24,40,.04),0 1px 2px rgba(16,24,40,.06);overflow:hidden}" +
      "#" + PANEL_ID + " table{width:100%;border-collapse:collapse}" +
      "#" + PANEL_ID + " th{text-align:left;padding:10px 14px;background:#f9fafb;border-bottom:1px solid #e5e7eb;font-weight:600;font-size:12px;color:#6a7282}" +
      "#" + PANEL_ID + " td{padding:10px 14px;border-bottom:1px solid #f3f4f6;vertical-align:middle}" +
      "#" + PANEL_ID + " tr:last-child td{border-bottom:0}" +
      "#" + PANEL_ID + " .lt-name{font-weight:500;color:#101828;word-break:break-all}" +
      "#" + PANEL_ID + " .lt-fqn{margin-top:2px;font-size:11px;color:#6a7282;word-break:break-all}" +
      "#" + PANEL_ID + " .lt-chip{display:inline-block;padding:2px 8px;border-radius:6px;background:#f3f4f6;font-size:12px}" +
      "#" + PANEL_ID + " .lt-left{white-space:nowrap}" +
      "#" + PANEL_ID + " button.lt-btn{height:30px;padding:0 12px;border:1px solid #d1d5dc;border-radius:8px;background:#fff;color:#364153;font:500 13px 'UIx Poppins',Arial,sans-serif;cursor:pointer;box-shadow:0 0 0 1px rgba(16,24,40,.04),0 1px 2px rgba(16,24,40,.06)}" +
      "#" + PANEL_ID + " button.lt-btn:hover{background:#f3f4f6;color:#101828}" +
      "#" + PANEL_ID + " button.lt-btn[disabled]{opacity:.5;cursor:default}" +
      "#" + PANEL_ID + " .lt-empty{padding:40px 16px;text-align:center;color:#6a7282}" +
      "#" + PANEL_ID + " .lt-msg{margin:0 0 12px;padding:10px 14px;border-radius:8px;background:#f3f4f6;color:#101828}" +
      "#" + PANEL_ID + " .lt-back{background:none;border:0;padding:0 0 8px;color:#6a7282;font:400 13px 'UIx Poppins',Arial,sans-serif;cursor:pointer}" +
      "#" + PANEL_ID + " .lt-back:hover{color:#101828}" +
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
    var lead = el("p", "ld-lead"); lead.textContent = "“" + name + "” akan disimpan di Tempat Sampah, bukan langsung dihapus.";
    d.appendChild(lead);
    function sec(title, items) {
      d.appendChild(el("p", "ld-h", title));
      var ul = el("ul"); items.forEach(function (t) { ul.appendChild(el("li", null, t)); }); d.appendChild(ul);
    }
    sec("Yang akan terjadi", [
      "Data tidak lagi tampil di pencarian, daftar, dan dashboard.",
      "Selama " + DAYS + " hari, Anda atau admin bisa memulihkannya lewat Settings › Tempat Sampah.",
      "Setelah " + DAYS + " hari, data dihapus permanen secara otomatis dan tidak bisa dipulihkan."]);
    sec("Perlu diperhatikan", [
      "Tautan ke data ini (istilah, kolom, pemilik, dashboard) ikut tidak aktif sementara, dan kembali normal saat dipulihkan.",
      "Yang dipindahkan hanya catatan di Len Data Governance; data sumber di Trino tidak berubah."]);
    d.appendChild(el("p", "ld-foot", "Ragu? Pilih Batal, tidak ada yang berubah."));
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
      if (!/^Delete\b/i.test(t)) return;                        // bukan dialog hapus
      var q = /"([^"]+)"/.exec(t);
      d.dataset.lenName = q ? q[1] : t.replace(/^Delete\s+/i, "");
    }
    var name = d.dataset.lenName;
    css(); d.classList.add("ld-dlg");
    [hs, hs.parentElement].forEach(function (x) { if (x) { x.style.whiteSpace = "normal"; x.style.overflow = "visible"; x.style.textOverflow = "clip"; } });
    setText(hs, "Pindahkan “" + name + "” ke Tempat Sampah?");
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
    setText(cancel && (cancel.querySelector("[data-text]") || cancel), "Batal");
    setText(confirm.querySelector("[data-text]") || confirm, "Ya, pindahkan");
  }
  function scanDialogs() { document.querySelectorAll('[role="dialog"]').forEach(fixDialog); }

  /* ---------- 2. menu & panel Tempat Sampah ---------- */
  var panelOpen = false;
  function place(panel) {
    var side = document.querySelector(".left-sidebar-layout, .ant-layout-sider");
    var nav = document.querySelector(".navbar-container, .ant-layout-header");
    panel.style.left = (side ? Math.round(side.getBoundingClientRect().right) : 0) + "px";
    panel.style.top = (nav ? Math.round(nav.getBoundingClientRect().bottom) : 0) + "px";
    panel.style.right = "0"; panel.style.bottom = "0";
  }
  function daysLeft(ts) { return Math.max(0, DAYS - Math.floor((Date.now() - ts) / 86400000)); }
  function fmt(ts) { try { return new Date(ts).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }); } catch (e) { return new Date(ts).toISOString(); } }

  function load(panel) {
    var body = panel.querySelector(".lt-body"); body.textContent = "Memuat…";
    var jobs = TYPES.map(function (t) {
      return api("GET", "/" + t[0] + "?include=deleted&limit=200&fields=deleted").then(function (r) { return r.ok ? r.json() : { data: [] }; })
        .then(function (j) { return (j.data || []).filter(function (e) { return e.deleted; }).map(function (e) { return { t: t, e: e }; }); })
        .catch(function () { return []; });
    });
    Promise.all(jobs).then(function (parts) {
      var rows = [].concat.apply([], parts).sort(function (a, b) { return (b.e.updatedAt || 0) - (a.e.updatedAt || 0); });
      body.textContent = "";
      if (!rows.length) { body.appendChild(el("div", "lt-empty", "Tempat Sampah kosong. Tidak ada data yang menunggu dihapus.")); return; }
      var card = el("div", "lt-card"), tb = el("table"), th = el("thead"), hr = el("tr");
      ["Nama", "Jenis", "Dihapus oleh", "Dihapus pada", "Sisa waktu", ""].forEach(function (h) { hr.appendChild(el("th", null, h)); });
      th.appendChild(hr); tb.appendChild(th);
      var tbody = el("tbody");
      rows.forEach(function (x) {
        var tr = el("tr"), n = x.e.displayName || x.e.name;
        var nc = el("td"); nc.appendChild(el("div", "lt-name", x.e.displayName || x.e.name));
        if (x.e.fullyQualifiedName && x.e.fullyQualifiedName !== (x.e.displayName || x.e.name)) nc.appendChild(el("div", "lt-fqn", x.e.fullyQualifiedName));
        tr.appendChild(nc);
        var c1 = el("td"); c1.appendChild(el("span", "lt-chip", x.t[1])); tr.appendChild(c1);
        tr.appendChild(el("td", null, x.e.updatedBy || "-"));
        tr.appendChild(el("td", null, x.e.updatedAt ? fmt(x.e.updatedAt) : "-"));
        var left = x.e.updatedAt ? daysLeft(x.e.updatedAt) : 0;
        tr.appendChild(el("td", "lt-left", left > 0 ? left + " hari lagi bisa dipulihkan" : "Segera dihapus permanen"));
        var act = el("td"), b = el("button", "lt-btn", "Pulihkan"); b.type = "button";
        b.addEventListener("click", function () { restore(panel, x, tr, b, n); });
        act.appendChild(b); tr.appendChild(act); tbody.appendChild(tr);
      });
      tb.appendChild(tbody); card.appendChild(tb); body.appendChild(card);
    });
  }
  function msg(panel, text) {
    var m = panel.querySelector(".lt-msg"); if (m) m.remove();
    m = el("div", "lt-msg", text); panel.querySelector(".lt-sub").after(m);
    setTimeout(function () { if (m.parentNode) m.remove(); }, 8000);
  }
  function restore(panel, x, tr, btn, name) {
    btn.disabled = true; btn.textContent = "Memulihkan…";
    api("PUT", "/" + x.t[0] + "/restore", { id: x.e.id }).then(function (r) {
      if (r.ok) { tr.remove(); msg(panel, "“" + name + "” sudah dipulihkan dan tampil kembali."); return; }
      btn.disabled = false; btn.textContent = "Pulihkan";
      msg(panel, "Belum bisa memulihkan “" + name + "”. Kemungkinan nama yang sama sudah dipakai atau Anda belum punya hak memulihkannya. Hubungi admin Data Governance bila perlu.");
    }).catch(function () { btn.disabled = false; btn.textContent = "Pulihkan"; msg(panel, "Koneksi terputus. Coba lagi sebentar lagi."); });
  }
  function showPanel() {
    css();
    var panel = document.getElementById(PANEL_ID);
    if (!panel) {
      panel = el("div"); panel.id = PANEL_ID;
      var back = el("button", "lt-back", "← Kembali ke Settings"); back.type = "button";
      back.addEventListener("click", hidePanel); panel.appendChild(back);
      panel.appendChild(el("h2", null, "Tempat Sampah"));
      panel.appendChild(el("p", "lt-sub", "Data yang dihapus disimpan di sini selama " + DAYS + " hari, lalu dihapus permanen otomatis. Pilih Pulihkan untuk mengembalikannya."));
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
  /* Ikon kartu Settings (hardcoded, satu keluarga dengan ikon kartu bawaan: kotak 90px, garis/outline). */
  var TRASH = '<svg viewBox="0 0 48 48" width="52" height="52" fill="none" stroke="#4a5565" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M6 12h36M18 12V8a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v4M10 12l2.4 28a3 3 0 0 0 3 2.8h16.4a3 3 0 0 0 3-2.8L37 12"/>' +
    '<g stroke-width="1.9"><path d="M21.2 24.6 24 20l2.2 3.4M25.6 30.2h-3.5a1.6 1.6 0 0 1-1.4-2.4l.5-.8M29.2 26.4l1.4 2.4a1.6 1.6 0 0 1-1.4 2.4M22.6 33l-2-2.8 2.8-.6M27 33.2l3-1.6-2.6-1.4M29.2 26.4 26.6 25l.7 2.6"/></g></svg>';
  var THEME = '<svg viewBox="0 0 48 48" width="52" height="52" fill="none" stroke="#ae2524" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M24 5C13.5 5 5 13 5 23.5S13.2 42 21 42c3 0 4-1.8 4-3.6 0-3.4 2-4.4 4.6-4.4H36c4 0 7-2.8 7-7C43 14 34.5 5 24 5z"/>' +
    '<circle cx="15" cy="23" r="2.4"/><circle cx="20" cy="14.5" r="2.4"/><circle cx="30" cy="14.5" r="2.4"/><circle cx="35" cy="23" r="2.4"/></svg>';
  var TILE = "width:90px;height:90px;display:flex;align-items:center;justify-content:center;border-radius:12px;";
  function tile(ic, svg, bg) {
    ic.innerHTML = '<span role="img" class="anticon">' + svg + "</span>";
    ic.style.cssText = TILE + "background:" + bg;
    ic.setAttribute("data-ldg-icon", "1");
  }
  function decorateCards() {   // kartu "Preferences" → ikon tema (outline merah UIx)
    document.querySelectorAll(".setting-card-item").forEach(function (card) {
      var t = card.querySelector(".setting-card-content .font-semibold");
      var ic = card.querySelector(".setting-card-icon");
      if (!t || !ic || ic.getAttribute("data-ldg-icon")) return;
      if (/^(preferences|preferensi|appearance|tampilan)$/i.test(t.textContent.trim())) tile(ic, THEME, "#fdf2f2");
    });
  }
  function ensureCard() {
    if (/^\/settings(\/|$)/.test(location.pathname)) decorateCards();
    ensureTrashCard();
  }
  function ensureTrashCard() {   // kartu "Tempat Sampah" di halaman Settings (di samping Services, Notifications, ...)
    if (!/^\/settings\/?$/.test(location.pathname) || document.getElementById(ITEM_ID)) return;
    var box = document.querySelector(".setting-items-container"); if (!box || !box.firstElementChild) return;
    var col = box.firstElementChild.cloneNode(true);
    col.id = ITEM_ID;
    var card = col.querySelector(".ant-card"); if (!card) return;
    card.setAttribute("data-testid", "tempat-sampah"); card.style.cursor = "pointer";
    var ic = card.querySelector(".setting-card-icon"); if (ic) tile(ic, TRASH, "#f3f4f6");
    var t = card.querySelector(".setting-card-content .font-semibold"); if (t) t.textContent = "Tempat Sampah";
    var d = card.querySelector(".setting-card-content div"); if (d) { d.textContent = "Data yang dihapus disimpan " + DAYS + " hari dan bisa dipulihkan."; d.removeAttribute("title"); }
    card.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); showPanel(); }, true);
    box.appendChild(col);
  }
  function ensure() {
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
