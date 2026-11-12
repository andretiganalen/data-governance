/* Len Data Governance — Context Center > Documents.
 *  1. Folder: urutan manual (FOLDER_ORDER), sisanya menurut abjad. Dokumen: menurun (terbaru dahulu) menurut tanggal dibuat.
 *  2. Baris kecil di bawah nama dokumen: "Dibuat YYMMDD" (tanggal dari awal nama berkas standar "YYMMDD CC Nama" atau "YY.MM.DD …";
 *     updatedAt tidak dipakai karena ikut berubah saat berkas dipindah/diproses).
 * Pengurutan dilakukan pada respons API (XHR) agar tidak mengganggu render React; teks baris kecil diganti idempoten di DOM. */
(function () {
  "use strict";
  var FOLDER_ORDER = ["ERM", "Reference"];
  var T = function (k, v) { return window.LDG_I18N ? window.LDG_I18N.t(k, v) : k; };
  var RE_FILES = /\/api\/v1\/contextCenter\/drive\/files(\?|$)/, RE_FOLDERS = /\/api\/v1\/contextCenter\/drive\/folders(\?|$)/;

  function created(name) {   // "261016 Rev…" / "26.11.21 Timeline…" → "261016" / "261121"
    var m = /^\s*(\d{2})[.\-]?(\d{2})[.\-]?(\d{2})(?!\d)/.exec(name || "");
    return m ? m[1] + m[2] + m[3] : "";
  }
  function cc(name) { var m = /^\s*[\d.\-]{6,8}\s+(\d{2})\s/.exec(name || ""); return m ? m[1] : "00"; }
  function fileKey(f) { var n = f.displayName || f.name || ""; return (created(n) || "000000") + cc(n) + n; }
  function sortFiles(a) { return a.slice().sort(function (x, y) { var p = fileKey(x), q = fileKey(y); return p < q ? 1 : p > q ? -1 : 0; }); }
  function sortFolders(a) {
    return a.slice().sort(function (x, y) {
      var i = FOLDER_ORDER.indexOf(x.name), j = FOLDER_ORDER.indexOf(y.name);
      if (i < 0) i = 1e6; if (j < 0) j = 1e6;
      return i !== j ? i - j : String(x.name).localeCompare(String(y.name));
    });
  }

  /* ---------- pengurutan pada respons API ---------- */
  var open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    var u = String(url);
    if (/^get$/i.test(method) && RE_FILES.test(u)) {
      this._ldg = "files";
      if (/[?&]limit=(\d+)/.test(u) && !/[?&]limit=0(&|$)/.test(u)) arguments[1] = u.replace(/([?&]limit=)\d+/, "$1100");   // satu halaman cukup agar urutan menyeluruh
    } else if (/^get$/i.test(method) && RE_FOLDERS.test(u)) this._ldg = "folders";
    return open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    var x = this;
    if (x._ldg) x.addEventListener("readystatechange", function () {
      if (x.readyState !== 4 || x.status !== 200) return;
      try {
        var j = JSON.parse(x.responseText);
        if (!j || !Array.isArray(j.data)) return;
        j.data = x._ldg === "files" ? sortFiles(j.data) : sortFolders(j.data);
        var txt = JSON.stringify(j);
        Object.defineProperty(x, "responseText", { value: txt, configurable: true });
        Object.defineProperty(x, "response", { value: txt, configurable: true });
      } catch (e) { /* biarkan respons asli */ }
    });
    return send.apply(this, arguments);
  };

  /* ---------- teks baris kecil ---------- */
  function setText(n, s) { if (n && n.textContent !== s) n.textContent = s; }
  function decorate() {
    if (!/^\/context-center\/documents/.test(location.pathname)) return;
    document.querySelectorAll('[data-testid^="document-row-"]').forEach(function (row) {
      var nm = row.querySelector('[data-testid="document-name"]'), at = row.querySelector('[data-testid="document-updated-at"]');
      var d = nm ? created(nm.textContent) : "";
      if (at && d) setText(at, T("docs_created", { d: d }));
    });
    document.querySelectorAll("span").forEach(function (s) {
      if (s.children.length === 0 && /^(Sorted by|Diurutkan|Urutan)\b/.test(s.textContent.trim())) setText(s, T("docs_sorted"));
    });
  }
  var pending = false;
  new MutationObserver(function () {
    if (pending) return; pending = true;
    (window.requestAnimationFrame || setTimeout)(function () { pending = false; decorate(); });
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
})();
