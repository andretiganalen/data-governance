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
