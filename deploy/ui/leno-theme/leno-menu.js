/* Len Data Governance — aplikasi utama: modul Visualisasi + nama merek di seluruh antarmuka.
 * Disisipkan gateway (nginx sub_filter) bersama leno.css.
 *  1. Menu "Visualisasi" di sidebar kiri (disalin dari item bawaan agar gaya sama).
 *  2. Klik → dashboard Gold tampil DI DALAM kerangka Len Data Governance (header & sidebar tetap), dengan tab.
 *     Isi dari Superset 6 di /visualisasi/ (origin sama, tanpa menu Superset — lihat leno-superset.css).
 *  3. Tanpa kredensial baru: token sesi Len Data Governance (Bearer yang dipakai UI) diteruskan lewat cookie
 *     `dg_token` (path /visualisasi) dan diverifikasi server Visualisasi ke API Len Data Governance. Logout → cookie dihapus.
 *  4. Nama merek: teks bawaan aplikasi dasar yang masih menyebut nama produk upstream (label, judul, tooltip,
 *     placeholder) ditampilkan sebagai "Len Data Governance". Isi yang sedang diedit pengguna tidak disentuh.
 */
(function () {
  "use strict";
  var ITEM_ID = "len-menu-visualisasi", PANEL_ID = "len-visualisasi", COOKIE = "dg_token";
  var TABS = [
    ["risiko", "Risiko ERM", "/visualisasi/superset/dashboard/risiko-erm/?standalone=1"],
    ["tata-kelola", "Tata Kelola Data", "/visualisasi/superset/dashboard/tata-kelola-data/?standalone=1"],
    ["sdm", "SDM", "/visualisasi/superset/dashboard/sdm-headcount/?standalone=1"],
    ["kesegaran", "Kesegaran Data", "/visualisasi/superset/dashboard/kesegaran-data/?standalone=1"],
    ["dashboard", "Semua dashboard", "/visualisasi/dashboard/list/"],
    ["grafik", "Grafik", "/visualisasi/chart/list/"],
    ["sql", "SQL Lab", "/visualisasi/sqllab/"]
  ];
  var ICON = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" ' +
    'aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>';

  /* ---------- 3. sesi: teruskan token Len Data Governance ke modul Visualisasi ---------- */
  function setToken(t) {
    if (t && document.cookie.indexOf(COOKIE + "=" + t) === -1)
      document.cookie = COOKIE + "=" + t + "; path=/visualisasi; SameSite=Strict";
  }
  function clearToken() { document.cookie = COOKIE + "=; path=/visualisasi; Max-Age=0; SameSite=Strict"; }
  function bearer(v) { var m = /^Bearer\s+(\S+)$/i.exec(v || ""); return m && m[1].split(".").length === 3 ? m[1] : null; }
  var setHdr = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.setRequestHeader = function (k, v) {
    if (String(k).toLowerCase() === "authorization") setToken(bearer(v));
    return setHdr.apply(this, arguments);
  };
  var xopen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, url) {
    if (/\/users\/logout/.test(String(url))) clearToken();
    return xopen.apply(this, arguments);
  };
  if (window.fetch) {
    var f = window.fetch;
    window.fetch = function (input, init) {
      try {
        var h = init && init.headers;
        var v = h && (typeof h.get === "function" ? h.get("Authorization") : (h.Authorization || h.authorization));
        setToken(bearer(v));
        if (/\/users\/logout/.test(String(input && input.url || input))) clearToken();
      } catch (e) { /* abaikan */ }
      return f.apply(this, arguments);
    };
  }
  if (/^\/(signin|signup|logout)/.test(location.pathname)) clearToken();

  /* ---------- 2. panel Visualisasi di area konten ---------- */
  function css() {
    if (document.getElementById(PANEL_ID + "-css")) return;
    var s = document.createElement("style");
    s.id = PANEL_ID + "-css";
    s.textContent =
      "#" + PANEL_ID + "{position:fixed;z-index:400;background:#F5F6F8;display:flex;flex-direction:column}" +
      "#" + PANEL_ID + " .lv-bar{display:flex;align-items:flex-end;gap:4px;padding:12px 20px 0;background:#fff;border-bottom:1px solid #E6E6E6}" +
      "#" + PANEL_ID + " .lv-title{font:700 18px Montserrat,Arial,sans-serif;color:#3B3B3B;margin:0 20px 10px 0}" +
      "#" + PANEL_ID + " .lv-tab{font:500 14px 'Open Sans',Arial,sans-serif;color:#515151;background:none;border:0;" +
      "border-bottom:3px solid transparent;padding:8px 12px 9px;cursor:pointer}" +
      "#" + PANEL_ID + " .lv-tab:hover{color:#194A80}" +
      "#" + PANEL_ID + " .lv-tab[aria-selected=true]{color:#194A80;font-weight:600;border-bottom-color:#CF0000}" +
      "#" + PANEL_ID + " iframe{flex:1;width:100%;border:0;background:#F5F6F8}" +
      "html.dg-vis-open .left-sidebar-menu .ant-menu-item-selected:not(#" + ITEM_ID + "){background:transparent!important}" +
      "html.dg-vis-open .left-sidebar-menu .ant-menu-item-selected:not(#" + ITEM_ID + ")::after{display:none!important}" +
      "html.dg-vis-open #" + ITEM_ID + "{background:var(--len-navy-50,#EEF3F9)!important}";
    document.head.appendChild(s);
  }
  function place(panel) {
    var side = document.querySelector(".left-sidebar-layout, .ant-layout-sider");
    var nav = document.querySelector(".navbar-container, .ant-layout-header");
    panel.style.left = (side ? Math.round(side.getBoundingClientRect().right) : 0) + "px";
    panel.style.top = (nav ? Math.round(nav.getBoundingClientRect().bottom) : 0) + "px";
    panel.style.right = "0"; panel.style.bottom = "0";
  }
  function show(key) {
    css();
    var tab = TABS.filter(function (t) { return t[0] === key; })[0] || TABS[0];
    var panel = document.getElementById(PANEL_ID);
    if (!panel) {
      panel = document.createElement("section");
      panel.id = PANEL_ID;
      panel.setAttribute("aria-label", "Visualisasi");
      var bar = document.createElement("div");
      bar.className = "lv-bar";
      bar.innerHTML = '<h2 class="lv-title">Visualisasi</h2>';
      TABS.forEach(function (t) {
        var b = document.createElement("button");
        b.className = "lv-tab"; b.type = "button"; b.dataset.key = t[0]; b.textContent = t[1];
        b.addEventListener("click", function () { show(t[0]); });
        bar.appendChild(b);
      });
      var frame = document.createElement("iframe");
      frame.title = "Visualisasi data Gold";
      panel.appendChild(bar); panel.appendChild(frame);
      document.body.appendChild(panel);
      window.addEventListener("resize", function () { place(panel); });
      var side = document.querySelector(".left-sidebar-layout, .ant-layout-sider");
      if (side && window.ResizeObserver) new ResizeObserver(function () { place(panel); }).observe(side);
    }
    place(panel);
    panel.querySelectorAll(".lv-tab").forEach(function (b) { b.setAttribute("aria-selected", String(b.dataset.key === tab[0])); });
    var frame = panel.querySelector("iframe");
    var src = "/visualisasi/login/?next=" + encodeURIComponent(tab[2]);   // sesi diperbarui dari token Len DG
    if (frame.dataset.key !== tab[0]) { frame.dataset.key = tab[0]; frame.src = src; }
    document.documentElement.classList.add("dg-vis-open");
    if (location.hash !== "#visualisasi=" + tab[0]) history.replaceState(history.state, "", location.pathname + location.search + "#visualisasi=" + tab[0]);
  }
  function hide() {
    var panel = document.getElementById(PANEL_ID);
    if (panel) panel.remove();
    document.documentElement.classList.remove("dg-vis-open");
    if (/^#visualisasi/.test(location.hash)) history.replaceState(history.state, "", location.pathname + location.search);
  }

  /* ---------- 1. item menu di sidebar ---------- */
  function build(menu) {
    var tpl = menu.querySelector("li.ant-menu-item");
    if (!tpl) return null;
    var li = tpl.cloneNode(true);               // salinan tanpa handler React
    li.id = ITEM_ID;
    li.classList.remove("ant-menu-item-selected", "ant-menu-item-active");
    li.removeAttribute("data-menu-id");
    li.setAttribute("data-testid", "app-bar-item-visualisasi");
    li.setAttribute("title", "Visualisasi data Gold (Trino lakehouse)");
    var icon = li.querySelector(".ant-menu-item-icon, .anticon, svg");
    if (icon) {
      var span = document.createElement("span");
      span.className = "ant-menu-item-icon anticon";
      span.setAttribute("role", "img");
      span.innerHTML = ICON;
      icon.replaceWith(span);
    }
    var label = li.querySelector(".ant-menu-title-content");
    if (label) label.textContent = "Visualisasi";
    li.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); show(TABS[0][0]); }, true);
    return li;
  }
  function ensure() {
    if (document.getElementById(ITEM_ID)) return;
    var menu = document.querySelector(".left-sidebar-menu.ant-menu, .left-sidebar-layout ul.ant-menu");
    if (!menu) return;
    var li = build(menu);
    if (!li) return;
    menu.appendChild(li);
    // menu lain → tutup Visualisasi
    menu.addEventListener("click", function (e) { if (!e.target.closest("#" + ITEM_ID)) hide(); });
    var m = /^#visualisasi(?:=([\w-]+))?/.exec(location.hash);
    if (m) show(m[1] || TABS[0][0]);
  }
  ["pushState", "replaceState"].forEach(function (k) {   // navigasi aplikasi ke halaman lain → tutup panel
    var orig = history[k];
    history[k] = function (s, t, url) {
      var r = orig.apply(this, arguments);
      if (url && !/#visualisasi/.test(String(url)) && document.getElementById(PANEL_ID)) hide();
      return r;
    };
  });
  window.addEventListener("popstate", function () { if (!/^#visualisasi/.test(location.hash)) hide(); });
  // ---- nama merek
  var UPSTREAM = new RegExp(["Open", "Metadata"].join(""), "g"), BRAND = "Len Data Governance";
  var SKIP = "script,style,textarea,input,code,pre,[contenteditable=true],[contenteditable=''],.ProseMirror,.ql-editor";
  var ATTRS = ["title", "placeholder", "alt", "aria-label", "data-tooltip"];
  function rebrand(root) {
    if (!root || !document.body) return;
    if (UPSTREAM.test(document.title)) document.title = document.title.replace(UPSTREAM, BRAND);
    UPSTREAM.lastIndex = 0;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n;
    while ((n = w.nextNode())) {
      if (n.nodeValue.indexOf("Metadata") < 0 || !UPSTREAM.test(n.nodeValue)) { UPSTREAM.lastIndex = 0; continue; }
      UPSTREAM.lastIndex = 0;
      var el = n.parentElement;
      if (el && !el.closest(SKIP)) n.nodeValue = n.nodeValue.replace(UPSTREAM, BRAND);
    }
    if (root.querySelectorAll) root.querySelectorAll("[" + ATTRS.join("],[") + "]").forEach(function (el) {
      if (el.closest(SKIP) && el.tagName !== "INPUT" && el.tagName !== "TEXTAREA") return;
      ATTRS.forEach(function (a) {
        var v = el.getAttribute(a);
        if (v && v.indexOf("Metadata") >= 0) el.setAttribute(a, v.replace(UPSTREAM, BRAND));
      });
    });
  }
  var pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    (window.requestAnimationFrame || setTimeout)(function () { pending = false; rebrand(document.body); });
  }
  new MutationObserver(function () { ensure(); schedule(); })
    .observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  document.addEventListener("DOMContentLoaded", function () { ensure(); schedule(); });
})();
