/* Kerangka halaman Data Governance (sidebar + header), sesuai desain "Data Governance Portal – Iterasi 2".
   Dimuat oleh halaman baca-saja di /beranda/, /organisasi/, /sistem/, /dataset/, /objek/, /glosarium/.
   Item yang belum dibangun ditampilkan redup dan tidak bisa diklik. */
(function () {
  var NAV = [
    { title: null, items: [{ label: 'Beranda', href: '/' }] },
    { title: 'Master data', items: [
      { label: 'Fungsi', href: '/fungsi/' },
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
  top.innerHTML = '<span>Data Governance › ' + esc(document.title.split('·')[0].trim()) + '</span><span class="dg-user" id="dg-user"></span>';

  var body = document.body;
  var kids = Array.prototype.slice.call(body.childNodes);
  kids.forEach(function (n) { if (n.tagName !== 'SCRIPT' && n.tagName !== 'STYLE') main.appendChild(n); });
  main.insertBefore(top, main.firstChild);
  body.appendChild(side); body.appendChild(main);

  fetch('/_export/whoami', { credentials: 'same-origin' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) {
      if (!j || !j.nama) return;
      document.getElementById('dg-user').innerHTML = '<span class="dg-name">' + esc(j.nama) + '</span><span class="dg-av">' + esc(initials(j.nama)) + '</span>';
    })
    .catch(function () {});
})();
