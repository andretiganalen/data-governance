// Mengisi angka dari build/data.js (window.R) ke elemen [data-v="path"]; kesalahan → window.__err (build gagal).
window.onerror = (m) => { window.__err = String(m); };
const get = (o, p) => p.split('.').reduce((a, k) => (a == null ? a : a[k]), o);
const fmt = (v) => (typeof v === 'number' ? v.toLocaleString('id-ID') : v);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const kpi = (name) => { const k = R.gold.kpi.find((x) => x.indikator === name); if (!k) throw new Error('kpi ' + name); return k.nilai; };
const chip = (st) => `<span class="chip ${{ 'Tersedia': 'ok', 'Sudah bisa': 'ok', 'Berjalan': 'ok', 'Selesai': 'ok', 'Belum ada': 'no', 'Dimuat, ada cacat': 'no', 'Belum bisa': 'na', 'Belum mulai': 'na', 'Terblokir': 'bad' }[st] || 'info'}">${esc(st)}</span>`;
document.addEventListener('DOMContentLoaded', () => {
  try {
    if (!window.R) throw new Error('build/data.js belum dibuat — jalankan rilis.py');
    if (window.render) window.render(R);
    document.querySelectorAll('[data-v]').forEach((el) => {
      const v = get(R, el.dataset.v);
      if (v === undefined) throw new Error('data tidak ada: ' + el.dataset.v);
      el.textContent = fmt(v);
    });
    document.querySelectorAll('[data-kpi]').forEach((el) => { el.textContent = fmt(kpi(el.dataset.kpi)); });
  } catch (e) { window.__err = e.message; throw e; }
});

// Lampiran Master Organisasi di setiap manual (mulai rilis 14 Nov 2026; rilis.py mengisi R.master, sebelum itu null → tidak tampil).
document.addEventListener('DOMContentLoaded', () => {
  try {
    const M = window.R && window.R.master;
    if (!M || !M.baris.length) return;
    const sec = document.createElement('section');
    sec.className = 'pb';
    const ver = M.versi.map((v) => `<li><b>${esc(v.versi)}</b>${v.berlaku ? ' (berlaku)' : ' (versi sebelumnya)'}: ${esc(v.dokumen)}, tanggal dokumen ${esc(v.tanggal)}, ${fmt(v.baris)} baris.</li>`).join('');
    let h = `<h2>Lampiran: Master Organisasi</h2><p>Fungsi Generik terhadap unit aktual, dibaca dari tabel Gold <b>gold_meta_master_organisasi</b> pada saat rilis. Tanggal dokumen menjadi tanggal pembaruan Master Organisasi.</p><ul>${ver}</ul><p>Versi yang berlaku memuat <b>${fmt(M.fungsi)}</b> Fungsi Generik pada <b>${fmt(M.baris.length)}</b> baris pemetaan.</p>`;
    let dir = null, rows = '';
    const flush = () => { if (dir !== null) h += `<h3>${esc(dir)}</h3><table class="t"><tr><th>Divisi</th><th>Bagian</th><th>Fungsi Generik</th><th>Fungsi lama</th></tr>${rows}</table>`; rows = ''; };
    M.baris.forEach((r) => {
      if (r.direktorat !== dir) { flush(); dir = r.direktorat; }
      rows += `<tr><td>${esc(r.divisi)}</td><td>${esc(r.bagian === r.divisi ? '(langsung pada Divisi)' : r.bagian)}</td><td>${esc(r.fungsi)}${r.catatan ? ' <small>*</small>' : ''}</td><td>${esc(r.lama)}</td></tr>`;
    });
    flush();
    const cat = [...new Set(M.baris.map((r) => r.catatan).filter(Boolean))];
    if (cat.length) h += `<p style="font-size:8.5pt"><small>*</small> ${cat.map(esc).join('; ')}.</p>`;
    sec.innerHTML = h;
    const secs = document.querySelectorAll('section');
    secs[secs.length - 1].after(sec);
  } catch (e) { window.__err = e.message; throw e; }
});
