/* Kerangka halaman Data Governance (sidebar + header), sesuai desain "Data Governance Portal – Iterasi 2".
   Dimuat oleh halaman baca-saja di /beranda/, /organisasi/, /sistem/, /dataset/, /objek/, /glosarium/.
   Item yang belum dibangun ditampilkan redup dan tidak bisa diklik. */
(function () {
  var NAV = [
    { title: null, items: [{ label: 'Beranda', href: '/' }] },
    { title: 'Master data', items: [
      { label: 'Organisasi', href: '/organisasi/' },
      { label: 'Sistem', href: '/sistem/' }] },
    { title: 'Katalog data', items: [
      { label: 'Business Dataset', href: '/dataset/' },
      { label: 'Database Object', href: '/objek/' },
      { label: 'Data Element', href: '/elemen/' },
      { label: 'Business Glossary', href: '/glosarium/' }] },
    { title: 'Tata kelola', items: [
      { label: 'Governance Assignment', href: '/assignment/' },
      { label: 'Data Quality Rules', href: '/kualitas/' },
      { label: 'Data Flow Lineage', href: '/lineage/' },
      { label: 'Security Access', href: '/akses/' }] }
  ];
  /* Menu aplikasi lama (sidebar bawah) tetap dilampirkan: item yang tidak ada di desain. */
  var NAV_BAWAH = { title: 'Lainnya', items: [
    { label: 'Explore', href: '/explore' },
    { label: 'Visualisasi', href: '/explore' },
    { label: 'Glosarium (aplikasi lama)', href: '/glossary' },
    { label: 'Documents', href: '/docs' },
    ] };
  /* Pengaturan berdiri sendiri, di bawah grup Lainnya. */
  var PENGATURAN = { title: null, items: [{ label: 'Pengaturan', href: '/settings' }] };
  var CSS = [
    'body{display:flex;min-height:100vh;}',
    '.dg-side{width:248px;flex:0 0 248px;background:var(--uix-surface);border-right:1px solid var(--uix-border);padding:16px 12px;box-sizing:border-box;position:sticky;top:0;height:100vh;overflow:auto;font-family:var(--uix-font);}',
    '.dg-side .dg-brand{display:flex;align-items:center;gap:10px;padding:4px 8px 16px;font-weight:600;color:var(--uix-text-head);font-size:15px;}',
    '.dg-side .dg-brand img{height:28px;}',
    '.dg-side h4{margin:16px 8px 6px;font-size:12px;font-weight:600;color:var(--uix-text-muted);text-transform:none;}',
    '.dg-side a,.dg-side span.dg-off{display:block;padding:7px 10px;border-radius:var(--uix-radius);font-size:14px;color:var(--uix-text-body);text-decoration:none;}',
    '.dg-side a:hover{background:var(--uix-surface-muted);}',
    '.dg-side a[aria-current="page"]{background:var(--uix-primary-soft);color:var(--uix-primary);font-weight:600;}',
    '.dg-side span.dg-off{color:var(--uix-text-muted);cursor:default;}',
    '.dg-side .dg-fold{display:flex;align-items:center;justify-content:space-between;width:100%;margin:8px 0 0;padding:7px 10px;border-radius:var(--uix-radius);background:none;border:0;font:inherit;font-size:14px;color:var(--uix-text-body);cursor:pointer;text-align:left;}',
    '.dg-side .dg-fold:hover{background:var(--uix-surface-muted);}',
    '.dg-side .dg-grp a{padding-left:24px;}',
    '.dg-side .dg-fold .dg-car{transition:transform .15s;display:inline-block;}',
    '.dg-side .dg-fold[aria-expanded="false"] .dg-car{transform:rotate(-90deg);}',
    '.dg-side .dg-grp[hidden]{display:none;}',
    '.dg-main{flex:1;min-width:0;}',
    '.dg-top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 24px;background:var(--uix-surface);border-bottom:1px solid var(--uix-border);font-family:var(--uix-font);font-size:14px;color:var(--uix-text-body);}',
    '.dg-top .dg-user{display:flex;align-items:center;gap:10px;}',
    '.dg-top .dg-av{width:32px;height:32px;border-radius:999px;background:var(--uix-primary);color:var(--uix-on-primary);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;}',
    '.dg-top .dg-name{font-weight:600;color:var(--uix-text-head);}',
    '.ant-table-content{overflow-x:auto;}',
    '.ant-table-cell{white-space:normal;}',
    '.ant-table-wrapper .ant-table-cell{padding:10px 8px !important;}',
    '.dg-chip{white-space:normal;}',
    '.ant-table-wrapper table{width:100%;}',
    '@media (max-width:820px){.dg-side{display:none;}}'
  ].join('');

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function initials(n) { return n.split(/\s+/).filter(Boolean).slice(0, 2).map(function (w) { return w[0].toUpperCase(); }).join(''); }

  var style = document.createElement('style'); style.textContent = CSS; document.head.appendChild(style);
  /* Gaya UIx asli aplikasi (antd): dimuat dari berkas yang dipakai ldg-server, agar kelas ant-* tampil sama. */
  fetch('/_export/uicss', { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : { css: [] }; }).then(function (j) {
    (j.css || []).forEach(function (href) {
      if (document.querySelector('link[href="' + href + '"]')) return;
      var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; document.head.appendChild(l);
    });
  }).catch(function () {});

  var path = location.pathname.replace(/index\.html$/, '');
  var side = document.createElement('aside'); side.className = 'dg-side'; side.setAttribute('aria-label', 'Navigasi');
  var html = '<div class="dg-brand"><img src="/brand/len-logo.png" alt="" onerror="this.remove()">Data Governance</div>';
  NAV.concat([NAV_BAWAH, PENGATURAN]).forEach(function (g, gi) {
    var fold = g === NAV_BAWAH;
    if (fold) html += '<button type="button" class="dg-fold" aria-expanded="false" aria-controls="dg-grp-' + gi + '">' + esc(g.title) + '<span class="dg-car" aria-hidden="true">▾</span></button><div class="dg-grp" id="dg-grp-' + gi + '" hidden>';
    else if (g.title) html += '<h4>' + esc(g.title) + '</h4>';
    g.items.forEach(function (it) {
      if (!it.href) { html += '<span class="dg-off" title="Belum tersedia">' + esc(it.label) + '</span>'; return; }
      var cur = it.href === '/' ? path === '/' : path.indexOf(it.href) === 0;
      html += '<a href="' + it.href + '" target="_self"' + (cur ? ' aria-current="page"' : '') + '>' + esc(it.label) + '</a>';
    });
    if (fold) html += '</div>';
  });
  side.innerHTML = html;
  /* Grup "Lainnya" dibuka/ditutup di tempat (tanpa tab baru). */
  side.addEventListener('click', function (e) {
    var f = e.target.closest('.dg-fold'); if (!f) return;
    var open = f.getAttribute('aria-expanded') !== 'true';
    f.setAttribute('aria-expanded', String(open));
    var box = document.getElementById(f.getAttribute('aria-controls'));
    if (box) box.hidden = !open;
  });

  var main = document.createElement('div'); main.className = 'dg-main';
  var top = document.createElement('header'); top.className = 'dg-top';
  top.innerHTML = '<span id="dg-top-title">Data Governance</span><span class="dg-user" id="dg-user"></span>';
  function setTopTitle() {
    var h = document.querySelector('h1');
    var name = h && h.textContent.trim() ? h.textContent.trim() : document.title.split('·')[0].trim();
    var el = document.getElementById('dg-top-title'); if (el) el.textContent = 'Data Governance › ' + name;
  }
  setTimeout(setTopTitle, 400); window.addEventListener('load', setTopTitle);

  var body = document.body;
  var kids = Array.prototype.slice.call(body.childNodes);
  kids.forEach(function (n) { if (n.tagName !== 'SCRIPT' && n.tagName !== 'STYLE') main.appendChild(n); });
  /* Alur koneksi (artifact "Beranda · Alur pengisian"): 10 langkah berurutan dan kebutuhan datanya. */
  var FLOW = [
    { n: 1, label: 'Organisasi', href: '/organisasi/', deps: [] },
    { n: 2, label: 'Sistem', href: '/sistem/', deps: [] },
    { n: 3, label: 'Business Dataset', href: '/dataset/', deps: ['Sistem'] },
    { n: 4, label: 'Database Object', href: '/objek/', deps: ['Business Dataset'] },
    { n: 5, label: 'Data Element', href: '/elemen/', deps: ['Database Object'] },
    { n: 6, label: 'Business Glossary', href: '/glosarium/', deps: ['Data Element'] },
    { n: 7, label: 'Governance Assignment', href: '/assignment/', deps: ['Data Element', 'Organisasi'] },
    { n: 8, label: 'Data Quality Rules', href: '/kualitas/', deps: ['Data Element'] },
    { n: 9, label: 'Data Flow Lineage', href: '/lineage/', deps: ['Data Element', 'Sistem'] },
    { n: 10, label: 'Security Access', href: '/akses/', deps: ['Data Flow Lineage', 'Organisasi'] }
  ];
  function renderFlow() {
    var cur = FLOW.findIndex(function (x) { return location.pathname.replace(/\/$/, '') === x.href.replace(/\/$/, ''); });
    if (cur < 0) return;
    var item = FLOW[cur];
    var hrefOf = function (name) { var f = FLOW.find(function (x) { return x.label === name; }); return f ? f.href : '/'; };
    var chain = FLOW.map(function (x, i) {
      var on = i === cur;
      return '<a href="' + x.href + '" target="_self" style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;font-size:12px;text-decoration:none;white-space:nowrap;' +
        (on ? 'background:#ae2524;color:#fff;font-weight:600' : 'background:#EDF0F4;color:#3A4658') + '"><span>' + x.n + '</span>' + esc(x.label) + '</a>';
    }).join('<span style="color:#99a1af;font-size:12px">›</span>');
    var needs = item.deps.length
      ? 'Butuh data: ' + item.deps.map(function (d) { return '<a href="' + hrefOf(d) + '" target="_self" style="color:#ae2524">' + esc(d) + '</a>'; }).join(', ')
      : 'Langkah awal, tidak membutuhkan data dari langkah lain.';
    var next = FLOW[cur + 1];
    var nxt = next ? '<a href="' + next.href + '" target="_self" style="color:#ae2524;margin-left:auto">Lanjut: ' + esc(next.label) + ' →</a>' : '';
    var bar = document.createElement('div');
    bar.id = 'dg-flow';
    bar.style.cssText = 'margin:0 0 12px;padding:10px 12px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;font-family:var(--uix-font)';
    bar.innerHTML = '<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;overflow-x:auto">' + chain + '</div>' +
      '<div style="display:flex;gap:12px;align-items:center;margin-top:8px;font-size:12px;color:#6a7282;flex-wrap:wrap"><span>' + needs + '</span>' + nxt + '</div>';
    var crumb = document.querySelector('.dg-crumb');
    if (crumb && crumb.parentNode) crumb.parentNode.insertBefore(bar, crumb.nextSibling);
    else main.insertBefore(bar, top.nextSibling);
  }
  setTimeout(renderFlow, 0);
  main.insertBefore(top, main.firstChild);
  body.appendChild(side); body.appendChild(main);

  /* Kolom Aksi paling kanan di setiap tabel. Baris yang sudah punya menu Aksi (admin) tidak diubah;
     baris lain mendapat tombol Detail yang membuka popup berisi isi baris. */
  function ensureActions(table) {
    var head = table.querySelector('thead tr');
    if (head) {
      var th = head.querySelector('#th-aksi');
      if (th) { th.hidden = false; }
      else if (!head.querySelector('.dg-aksi-th')) {
        var h = document.createElement('th'); h.className = 'ant-table-cell dg-aksi-th'; h.style.textAlign = 'right'; h.textContent = 'Aksi';
        head.appendChild(h);
      }
    }
    table.querySelectorAll('tbody tr').forEach(function (tr) {
      if (tr.querySelector('td.act, td.dg-aksi-td')) return;
      if (tr.children.length === 0) return;
      var td = document.createElement('td'); td.className = 'ant-table-cell act dg-aksi-td'; td.style.textAlign = 'right';
      td.innerHTML = '<button class="ant-btn ant-btn-default ant-btn-sm" type="button" data-dg-detail="1"><span>Detail</span></button>';
      tr.appendChild(td);
    });
  }
  function watchTables() {
    document.querySelectorAll('table').forEach(function (table) {
      if (table.dataset.dgWatch) return;
      table.dataset.dgWatch = '1';
      var obs = new MutationObserver(function () { ensureActions(table); });
      obs.observe(table, { childList: true, subtree: true });
      ensureActions(table);
    });
  }
  function openRowDetail(tr) {
    var table = tr.closest('table'); if (!table) return;
    var heads = Array.prototype.map.call(table.querySelectorAll('thead th'), function (th) { return th.textContent.trim(); });
    var cells = Array.prototype.slice.call(tr.children).filter(function (td) { return !td.classList.contains('dg-aksi-td') && !td.classList.contains('act'); });
    var box = document.getElementById('dg-detail');
    if (!box) {
      box = document.createElement('div'); box.id = 'dg-detail';
      box.style.cssText = 'position:fixed;inset:0;background:rgba(16,24,40,.45);display:flex;align-items:center;justify-content:center;padding:16px;z-index:200;';
      box.innerHTML = '<div style="background:#fff;border-radius:12px;box-shadow:0 12px 24px rgba(16,24,40,.2);width:100%;max-width:560px;max-height:90vh;overflow:auto;font-family:var(--uix-font)">' +
        '<div style="padding:16px 20px;border-bottom:1px solid #e5e7eb;font-weight:600;color:#101828" id="dg-detail-title">Detail</div>' +
        '<div style="padding:16px 20px;font-size:13px;line-height:1.8" id="dg-detail-body"></div>' +
        '<div style="padding:12px 20px;border-top:1px solid #e5e7eb;text-align:right"><button class="ant-btn ant-btn-default" type="button" id="dg-detail-close"><span>Tutup</span></button></div></div>';
      document.body.appendChild(box);
      box.addEventListener('click', function (e) { if (e.target === box || e.target.id === 'dg-detail-close' || e.target.closest('#dg-detail-close')) box.style.display = 'none'; });
    }
    var first = cells[0] ? cells[0].textContent.trim() : '';
    document.getElementById('dg-detail-title').textContent = 'Detail · ' + first;
    document.getElementById('dg-detail-body').innerHTML = cells.map(function (td, i) {
      var v = td.textContent.trim();
      return '<div><b>' + (heads[i] || '') + ':</b> ' + (v ? v.replace(/[&<>]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]; }) : '<span style="color:#8E1418">Perlu input manual</span>') + '</div>';
    }).join('');
    box.style.display = 'flex';
  }
  /* di fase capture: tombol Detail tidak ikut memicu aksi baris lain */
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-dg-detail]');
    if (!b) return;
    e.stopPropagation(); e.preventDefault();
    var tr = b.closest('tr'); if (tr) openRowDetail(tr);
  }, true);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchTables); else watchTables();
  setInterval(function () { watchTables(); document.querySelectorAll("table").forEach(ensureActions); }, 1500);

  fetch('/_export/whoami', { credentials: 'same-origin' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) {
      if (!j || !j.nama) return;
      document.getElementById('dg-user').innerHTML = '<span class="dg-name">' + esc(j.nama) + '</span><span class="dg-av">' + esc(initials(j.nama)) + '</span>';
    })
    .catch(function () {});
})();
