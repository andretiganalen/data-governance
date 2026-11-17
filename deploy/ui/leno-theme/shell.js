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
    '@media (max-width:820px){.dg-side{display:none;}}',
    /* ===== Standar tombol, menu Aksi, chip, dan isian otomatis (artifact "Data Governance Portal – Iterasi 2").
       Satu sumber untuk semua halaman; menimpa gaya lokal halaman dan antd. ===== */
    /* Tombol dasar: tinggi 40, radius 8, Poppins 600 */
    '.dg-main .ant-btn,.dg-main .dg-btn{display:inline-flex !important;align-items:center;justify-content:center;gap:8px;height:40px !important;min-height:40px;padding:0 18px !important;border-radius:8px !important;font-family:var(--uix-font) !important;font-size:14px !important;font-weight:600 !important;line-height:1 !important;cursor:pointer;text-decoration:none;box-sizing:border-box;transition:background .15s,border-color .15s,box-shadow .15s;white-space:nowrap;}',
    '.dg-main .ant-btn>span{display:inline-flex;align-items:center;gap:8px;}',
    /* Utama: merah UIx bergradasi */
    '.dg-main .ant-btn-primary,.dg-main .dg-btn{background:linear-gradient(180deg,#c0302e,#ae2524) !important;color:#fff !important;border:0 !important;box-shadow:0 2px 6px rgba(174,37,36,.25) !important;}',
    '.dg-main .ant-btn-primary:hover,.dg-main .dg-btn:hover{background:linear-gradient(180deg,#ae2524,#8e1418) !important;color:#fff !important;}',
    /* Netral (Batal, Tutup): putih, garis abu */
    '.dg-main .ant-btn-default,.dg-main .dg-btn.ghost{background:#fff !important;color:#16202E !important;border:1px solid #C9CFDA !important;box-shadow:none !important;font-weight:500 !important;}',
    '.dg-main .ant-btn-default:hover,.dg-main .dg-btn.ghost:hover{background:#F4F5F7 !important;border-color:#AEB6C4 !important;color:#16202E !important;}',
    /* Sekunder (Simpan & tambah lagi): garis merah */
    '.dg-main .dg-btn-sec{background:#fff !important;color:#ae2524 !important;border:1px solid #ae2524 !important;font-weight:600 !important;}',
    '.dg-main .dg-btn-sec:hover{background:#FCE8E9 !important;color:#8e1418 !important;border-color:#8e1418 !important;}',
    /* Hapus (konfirmasi): kuning tua, tenang, bukan merah alarm */
    '.dg-main .dg-btn-hapus,.dg-main .ant-btn-dangerous{background:#B45309 !important;color:#fff !important;border:0 !important;box-shadow:none !important;}',
    '.dg-main .dg-btn-hapus:hover,.dg-main .ant-btn-dangerous:hover{background:#92400E !important;color:#fff !important;}',
    /* Kecil (Aksi ▾, Pilih): tinggi 32 */
    '.dg-main .ant-btn-sm,.dg-main td .dg-btn{height:32px !important;min-height:32px;padding:0 12px !important;font-size:13px !important;}',
    '.dg-main .ant-btn[disabled],.dg-main .ant-btn:disabled{opacity:.5;cursor:not-allowed;box-shadow:none !important;}',
    '.dg-main .ant-btn:focus-visible,.dg-main .dg-btn:focus-visible,.dg-main .dg-menu-list button:focus-visible{outline:2px solid #ae2524;outline-offset:2px;}',
    '.dg-main .dg-plus{width:16px;height:16px;flex:0 0 16px;}',
    /* Urutan tombol form: Batal · Simpan & tambah lagi · Simpan, rata kanan */
    '.dg-main form footer,.dg-main .dg-dialog footer{display:flex;justify-content:flex-end;align-items:center;gap:8px;flex-wrap:wrap;}',
    /* Menu Aksi: satu tampilan untuk semua tabel */
    '.dg-main .dg-menu{position:relative;display:inline-block;}',
    '.dg-main .dg-menu-list{position:absolute !important;right:0 !important;top:36px !important;min-width:168px !important;background:#fff !important;border:1px solid #E3E6EB !important;border-radius:8px !important;box-shadow:0 12px 24px rgba(16,24,40,.12) !important;padding:4px !important;z-index:40 !important;text-align:left !important;}',
    '.dg-main .dg-menu-list[hidden]{display:none !important;}',
    '.dg-main .dg-menu-list button{display:flex !important;align-items:center;width:100% !important;min-height:36px;text-align:left !important;background:none !important;border:0 !important;padding:0 12px !important;font-family:var(--uix-font) !important;font-size:13px !important;font-weight:500 !important;color:#16202E !important;border-radius:6px !important;cursor:pointer;}',
    '.dg-main .dg-menu-list button:hover{background:#F4F5F7 !important;}',
    '.dg-main .dg-menu-list [data-ubah],.dg-main .dg-menu-list [data-lengkapi],.dg-main .dg-menu-list [data-isi]{color:#ae2524 !important;}',
    '.dg-main .dg-menu-list [data-hapus]{color:#9A4A06 !important;border-top:1px solid #EEF0F3 !important;border-radius:0 0 6px 6px !important;margin-top:4px;}',
    '.dg-main .dg-menu-list [data-hapus]:hover{background:#FDF1E3 !important;}',
    /* Chip sumber isian: Otomatis / Otomatis dari DB / Dari master = abu, Manual = merah muda */
    '.dg-main .dg-chip,.dg-main .dg-ch{display:inline-flex;align-items:center;gap:4px;padding:1px 8px;border-radius:999px;background:#EDF0F4;color:#3A4658;font-size:11px;font-weight:600;line-height:18px;white-space:nowrap;vertical-align:middle;}',
    '.dg-main .dg-chip.mn,.dg-main .dg-chip.manual,.dg-main .dg-ch.mn,.dg-main .dg-ch.manual{background:#FCE8E9;color:#8E1418;}',
    '.dg-main .dg-chip.ok{background:#E7F6EC;color:#0E6B33;}',
    /* Label isian: nama di kiri, chip di kanan (seperti artifact) */
    '.dg-main .dg-field>label,.dg-main .dg-form .f>label,.dg-main .dg-add .f>label{display:flex !important;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:4px 8px;font-size:13px !important;font-weight:600 !important;color:#16202E !important;margin-bottom:6px !important;}',
    '.dg-main .dg-field>label .dg-chip,.dg-main .dg-field>label .dg-ch,.dg-main .f>label .dg-chip,.dg-main .f>label .dg-ch{margin-left:auto;white-space:normal;max-width:100%;text-align:left;}',
    /* Isian otomatis: garis putus-putus, latar abu, ikon gembok, tidak bisa diketik */
    '.dg-main .dg-auto,.dg-main form input[readonly],.dg-main form input:disabled,.dg-main form select:disabled{border:1px dashed #AEB6C4 !important;background-color:#F5F6F8 !important;color:#3A4658 !important;cursor:not-allowed;' +
      'padding-left:32px !important;background-repeat:no-repeat !important;background-position:10px center !important;background-size:14px 14px !important;' +
      'background-image:url("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27%236A7282%27 stroke-width=%272.4%27 stroke-linecap=%27round%27 stroke-linejoin=%27round%27%3E%3Crect x=%275%27 y=%2711%27 width=%2714%27 height=%279%27 rx=%272%27/%3E%3Cpath d=%27M8 11V8a4 4 0 0 1 8 0v3%27/%3E%3C/svg%3E") !important;}',
    /* Isian form dan pencarian: tinggi 40 agar sejajar dengan tombol */
    '.dg-main form input:not([type=checkbox]):not([type=radio]),.dg-main form select,.dg-main .dg-toolbar-top input,.dg-main .dg-toolbar-top select,.dg-main .dg-toolbar input,.dg-main .dg-toolbar select{height:40px !important;border-radius:8px !important;box-sizing:border-box;}'
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
      if (tr.children.length === 0) return;
      /* baris rincian (satu sel melebar) bukan baris data: tidak diberi Aksi */
      if (tr.classList.contains('detail') || (tr.children.length === 1 && tr.children[0].colSpan > 1)) {
        var stray = tr.querySelector('td.dg-aksi-td'); if (stray) stray.remove();
        return;
      }
      var list = tr.querySelector('.dg-menu-list');
      if (list) {   // baris yang sudah punya menu (Ubah, Hapus, Lengkapi): pastikan Detail ada di dalamnya
        if (!list.querySelector('[data-dg-detail]')) {
          list.insertAdjacentHTML('afterbegin', '<button type="button" role="menuitem" data-dg-detail="1">Detail</button>');
        }
        return;
      }
      if (tr.querySelector('td.dg-aksi-td')) return;
      var td = document.createElement('td'); td.className = 'ant-table-cell act dg-aksi-td'; td.style.textAlign = 'right';
      td.innerHTML = '<div class="dg-menu" style="position:relative;display:inline-block"><button class="ant-btn ant-btn-default ant-btn-sm" type="button" data-dg-menu="1"><span>Aksi ▾</span></button>' +
        '<div class="dg-menu-list" role="menu" hidden style="position:absolute;right:0;top:32px;min-width:140px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;box-shadow:0 12px 24px rgba(16,24,40,.12);padding:4px;z-index:30;text-align:left">' +
        '<button type="button" role="menuitem" data-dg-detail="1" style="display:block;width:100%;text-align:left;background:none;border:0;padding:8px 10px;font:inherit;font-size:13px;cursor:pointer">Detail</button></div></div>';
      tr.appendChild(td);
    });
  }
  /* Menu Aksi seragam: satu tombol Aksi ▾ per baris. Buka/tutup di sini; Detail membuka popup. */
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-dg-menu]');
    if (b) {
      e.stopPropagation();
      var list = b.parentNode.querySelector('.dg-menu-list');
      var open = list.hidden;
      document.querySelectorAll('.dg-menu-list').forEach(function (m) { m.hidden = true; });
      list.hidden = !open;
      return;
    }
    if (!(e.target.closest && e.target.closest('.dg-menu'))) {
      document.querySelectorAll('.dg-menu-list').forEach(function (m) { m.hidden = true; });
    }
  }, true);
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
    document.querySelectorAll('.dg-menu-list').forEach(function (m) { m.hidden = true; });
    var tr = b.closest('tr'); if (tr) openRowDetail(tr);
  }, true);
  /* Seragamkan tombol dan menu yang dibuat halaman masing-masing (peran ditentukan id/atribut, bukan teks). */
  var PLUS = '<svg class="dg-plus" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>';
  var ORDER = ['data-dg-detail', 'data-ubah', 'data-lengkapi', 'data-isi', 'data-hapus'];
  function rank(b) { for (var i = 0; i < ORDER.length; i++) if (b.hasAttribute(ORDER[i])) return i; return 2; }
  function standardize() {
    var t = document.getElementById('btn-tambah');
    if (t && !t.querySelector('.dg-plus')) t.insertAdjacentHTML('afterbegin', PLUS);
    document.querySelectorAll('#f-save-new,#a-again').forEach(function (b) { b.classList.remove('ant-btn-default'); b.classList.add('ant-btn', 'dg-btn-sec'); });
    document.querySelectorAll('#h-ok').forEach(function (b) {
      b.classList.remove('ant-btn-primary', 'ant-btn-dangerous'); b.classList.add('ant-btn', 'dg-btn-hapus'); b.style.background = '';
    });
    document.querySelectorAll('.dg-menu > [data-menu],.dg-menu > [data-dg-menu]').forEach(function (b) {
      b.classList.add('ant-btn', 'ant-btn-default', 'ant-btn-sm');
      b.setAttribute('aria-haspopup', 'menu');
    });
    document.querySelectorAll('.dg-menu-list').forEach(function (list) {
      list.setAttribute('role', 'menu');
      var items = Array.prototype.slice.call(list.children).filter(function (c) { return c.tagName === 'BUTTON'; });
      items.forEach(function (b) { b.setAttribute('role', 'menuitem'); b.removeAttribute('style'); });
      var sorted = items.slice().sort(function (a, b) { return rank(a) - rank(b); });
      if (sorted.some(function (b, i) { return b !== items[i]; })) sorted.forEach(function (b) { list.appendChild(b); });
    });
  }
  /* Setelah memilih item menu, semua menu Aksi ditutup. */
  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('.dg-menu-list button')) {
      setTimeout(function () { document.querySelectorAll('.dg-menu-list').forEach(function (m) { m.hidden = true; }); }, 0);
    }
  });
  function tick() { watchTables(); document.querySelectorAll('table').forEach(ensureActions); standardize(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tick); else tick();
  new MutationObserver(function () { standardize(); }).observe(document.body, { childList: true, subtree: true });
  setInterval(tick, 1500);

  fetch('/_export/whoami', { credentials: 'same-origin' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) {
      if (!j || !j.nama) return;
      document.getElementById('dg-user').innerHTML = '<span class="dg-name">' + esc(j.nama) + '</span><span class="dg-av">' + esc(initials(j.nama)) + '</span>';
    })
    .catch(function () {});
})();
