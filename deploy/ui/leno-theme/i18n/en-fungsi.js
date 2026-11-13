// Keputusan 2026-11-13: di Len istilah "Domain" dikenal sebagai "Fungsi" (merujuk ke Fungsi Organisasi). Dipakai gateway untuk membungkus
// loader en-US: teks berkunci "domain" diganti saat dimuat. Placeholder {{x}} dan tag <0> tidak disentuh.
const swap = (t) => String(t).split(/(\{\{.*?\}\}|<\/?\d+>)/).map((p) => /^(\{\{|<\/?\d)/.test(p) ? p :
  p.replace(/\bSubdomains?\b/g, "Sub-Fungsi").replace(/\bsubdomains?\b/g, "sub-fungsi").replace(/\bDomains?\b/g, "Fungsi").replace(/\bdomains?\b/g, "fungsi")).join("");
const patch = (o) => Object.fromEntries(Object.entries(o || {}).map(([k, v]) => [k, /domain/i.test(k) && typeof v === "string" ? swap(v) : v]));
export function apply(m) {
  const d = m.default || m;
  const n = { label: patch(d.label), message: patch(d.message), server: d.server };
  return { ...m, default: n, label: n.label, message: n.message, server: n.server };
}
