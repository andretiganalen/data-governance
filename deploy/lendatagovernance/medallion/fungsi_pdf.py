#!/usr/bin/env python3
"""PDF "Glosarium Fungsi Generik" otomatis tiap ada perubahan istilah Fungsi (Version Control).

Dipanggil dari glossary_app.main (timer 10 menit). Membandingkan isi istilah Fungsi Generik (nama, definisi, Data Owner) dengan
snapshot terakhir (data/medallion/fungsi_pdf_state.json). Bila berbeda: membuat PDF baru berisi daftar Fungsi + definisi + Riwayat
Revisi (apa yang berubah, siapa, kapan), lalu mendaftarkannya ke data/referensi lewat scripts/referensi-tambah.py
("YYMMDD CC Glosarium Fungsi Generik Rev NN.pdf"; CC naik, berkas lama tidak pernah ditimpa). Berkas berisi definisi dari CLP-001
(dokumen internal), jadi hanya di data/referensi (di luar git), dilayani hanya untuk pengguna yang sudah masuk.
Sejak 2026-11-13 TIDAK terbit otomatis lagi (terlalu banyak PDF): revisi hanya terbit bila Admin Data Governance menekan tombol
"Terbitkan Revisi PDF" di Settings (layanan ldg-export menulis data/medallion/pdf_request/request.json; timer 10 menit mengambilnya)
atau lewat CLI --force. Timer tetap memperbarui status.json (apakah ada perubahan sejak revisi terakhir) untuk tombol itu.
  python fungsi_pdf.py          # hanya perbarui status; terbitkan bila ada permintaan dari tombol
  python fungsi_pdf.py --force  # terbitkan revisi baru sekarang"""
from __future__ import annotations

import hashlib
import html
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATE = ROOT / "data" / "medallion" / "fungsi_pdf_state.json"
FONTS = ROOT / "deploy" / "ui" / "leno-theme" / "fonts"
TAMBAH = ROOT / "deploy" / "lendatagovernance" / "scripts" / "referensi-tambah.py"
PLACEHOLDER = "Perlu input manual dari Data Governance"
WIB = timezone(timedelta(hours=7))
PARENT = "Fungsi Organisasi.FungsiGenerik"
REQ_DIR = ROOT / "data" / "medallion" / "pdf_request"
REQUEST, STATUS = REQ_DIR / "request.json", REQ_DIR / "status.json"


def snapshot(om) -> dict:
    out, after = {}, ""
    while True:
        r = om.get("/v1/glossaryTerms?limit=500&fields=owners,parent&glossary=OrganisasiFungsi".replace("&glossary=OrganisasiFungsi", "") + after)
        for t in r.get("data", []):
            if (t.get("fullyQualifiedName") or "").startswith(PARENT + ".") or t.get("fullyQualifiedName") == PARENT:
                out[t["fullyQualifiedName"]] = {
                    "nama": t.get("displayName") or t["name"], "definisi": (t.get("description") or "").strip(),
                    "owner": "; ".join(sorted(o.get("displayName") or o["name"] for o in t.get("owners", []))),
                    "versi": t.get("version"), "oleh": t.get("updatedBy")}
        if not r.get("paging", {}).get("after"):
            return out
        after = "&after=" + r["paging"]["after"]


def digest(s: dict) -> str:
    return hashlib.sha1(json.dumps({k: (v["nama"], v["definisi"], v["owner"]) for k, v in sorted(s.items())}, ensure_ascii=False).encode()).hexdigest()


def diff(old: dict, new: dict) -> list[dict]:
    ch = []
    for k, v in sorted(new.items()):
        o = old.get(k)
        if o is None:
            ch.append({"istilah": v["nama"], "jenis": "Baru", "oleh": v["oleh"]})
        elif (o["nama"], o["definisi"], o["owner"]) != (v["nama"], v["definisi"], v["owner"]):
            what = [n for n, a, b in (("nama", o["nama"], v["nama"]), ("definisi", o["definisi"], v["definisi"]), ("Data Owner", o["owner"], v["owner"])) if a != b]
            ch.append({"istilah": v["nama"], "jenis": "Diubah (" + ", ".join(what) + ")", "oleh": v["oleh"]})
    ch += [{"istilah": o["nama"], "jenis": "Dihapus", "oleh": "-"} for k, o in sorted(old.items()) if k not in new]
    return ch


def render(snap: dict, revisions: list[dict]) -> str:
    e = html.escape
    rev = revisions[-1]
    rows = []
    items = sorted((v for k, v in snap.items() if k != PARENT), key=lambda v: v["nama"].lower())
    for i, v in enumerate(items, 1):
        d = v["definisi"] or PLACEHOLDER
        cls = ' class="manual"' if PLACEHOLDER.lower() in d.lower() else ""
        rows.append(f"<tr><td>{i}</td><td><b>{e(v['nama'])}</b></td><td{cls}>{e(d)}</td><td>{e(v['owner'] or '-')}</td><td>{v['versi'] or '-'}</td></tr>")
    hist = "".join(
        f"<tr><td>{r['rev']:02d}</td><td>{e(r['tanggal'])}</td><td>{e(r['ringkasan'])}</td></tr>" for r in reversed(revisions))
    det = "".join(f"<tr><td>{e(c['istilah'])}</td><td>{e(c['jenis'])}</td><td>{e(c.get('oleh') or '-')}</td></tr>" for c in rev["perubahan"][:80])
    fonts = "".join(
        f'@font-face{{font-family:"UIx Poppins";font-weight:{w};src:url("file://{FONTS}/poppins-latin-{w}-normal.woff2") format("woff2")}}' for w in (400, 500, 600))
    manual = sum(1 for v in items if PLACEHOLDER.lower() in (v["definisi"] or PLACEHOLDER).lower())
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8"><style>{fonts}
@page{{size:A4;margin:18mm 16mm}}
body{{font:400 9.5pt/1.5 "UIx Poppins",Arial,sans-serif;color:#364153;margin:0}}
h1{{font:600 22pt "UIx Poppins";color:#101828;margin:0 0 2mm}} h2{{font:600 13pt "UIx Poppins";color:#101828;margin:8mm 0 3mm;break-after:avoid}}
.meta{{color:#6a7282;font-size:9pt}} .cover{{padding:6mm 0 4mm;border-bottom:1px solid #e5e7eb}}
.kv{{display:grid;grid-template-columns:34mm 1fr;gap:1mm 4mm;margin-top:5mm;font-size:9pt}} .kv b{{color:#101828;font-weight:500}}
table{{width:100%;border-collapse:collapse;font-size:8.6pt}} th{{background:#f9fafb;color:#6a7282;text-align:left;font-weight:600;padding:2mm 2.5mm;border-bottom:1px solid #e5e7eb}}
td{{padding:2mm 2.5mm;border-bottom:1px solid #f3f4f6;vertical-align:top}} tr{{break-inside:avoid}} td b{{color:#101828;font-weight:600}}
.manual{{background:#f3f4f6;color:#101828;font-weight:500}} .note{{margin-top:5mm;padding:3mm 4mm;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;font-size:8.6pt}}
</style></head><body>
<div class="cover"><div class="meta">PT Len Industri (Persero) · Len Data Governance</div><h1>Glosarium Fungsi Generik</h1>
<div class="meta">Tugas tiap Fungsi pada skala Enterprise; Fungsi adalah Data Owner di Len Data Governance (tanpa awalan &ldquo;Fungsi&rdquo;).</div>
<div class="kv"><b>Revisi</b><span>{rev['rev']:02d}</span><b>Tanggal terbit</b><span>{e(rev['tanggal'])}</span>
<b>Jumlah Fungsi</b><span>{len(items)}</span><b>Perlu input manual</b><span>{manual} Fungsi (ditandai abu-abu pada tabel)</span>
<b>Sumber</b><span>Glosarium &ldquo;Organisasi dan Fungsi&rdquo; di aplikasi; definisi awal dari CLP-001 Nomenklatur Fungsi Generik</span></div>
<div class="note">Dokumen tidak terkontrol. Versi terbaru ada di aplikasi (Glosarium &rsaquo; Organisasi dan Fungsi). Revisi baru terbit otomatis setiap ada perubahan istilah Fungsi.</div></div>
<h2>Daftar Fungsi dan definisinya</h2>
<table><thead><tr><th style="width:8mm">No.</th><th style="width:38mm">Fungsi</th><th>Definisi</th><th style="width:30mm">Data Owner</th><th style="width:12mm">Versi istilah</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Riwayat revisi</h2>
<table><thead><tr><th style="width:12mm">Rev.</th><th style="width:38mm">Tanggal</th><th>Ringkasan</th></tr></thead><tbody>{hist}</tbody></table>
<h2>Perubahan pada revisi {rev['rev']:02d}</h2>
<table><thead><tr><th>Istilah</th><th>Jenis perubahan</th><th>Oleh</th></tr></thead><tbody>{det or '<tr><td colspan="3">Penerbitan awal.</td></tr>'}</tbody></table>
</body></html>"""


def publish(snap: dict, revisions: list[dict]) -> str:
    with tempfile.TemporaryDirectory() as td:
        h, p = Path(td) / "doc.html", Path(td) / "doc.pdf"
        h.write_text(render(snap, revisions), encoding="utf-8")
        subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={td}/prof", f"--print-to-pdf={p}", f"file://{h}"], check=True, capture_output=True, timeout=120)
        name = f"Glosarium Fungsi Generik Rev {revisions[-1]['rev']:02d}"
        out = subprocess.run([sys.executable, str(TAMBAH), f"{p}={name}"], check=True, capture_output=True, text=True).stdout.strip()
    return out


def write_status(st: dict, snap: dict, pending: bool = False) -> None:
    """Status tanpa isi definisi, dibaca layanan ldg-export untuk tombol di UI."""
    last = (st.get("revisions") or [{}])[-1]
    REQ_DIR.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({
        "rev": last.get("rev"), "tanggal": last.get("tanggal"), "berkas": last.get("berkas"),
        "ada_perubahan": st.get("digest") != digest(snap) if snap else False, "menunggu": pending,
        "diperiksa": datetime.now(WIB).strftime("%d %b %Y %H:%M WIB")}, ensure_ascii=False))


def run(om, force: bool = False) -> str | None:
    """Terbitkan revisi hanya bila force atau ada permintaan tombol (request.json); selain itu hanya perbarui status."""
    snap = snapshot(om)
    if len(snap) < 2:
        return None
    st = json.loads(STATE.read_text()) if STATE.exists() else {"digest": None, "snapshot": {}, "revisions": []}
    req = REQUEST.exists()
    if not (force or req):
        write_status(st, snap)
        return None
    by = ""
    if req:
        try:
            by = json.loads(REQUEST.read_text()).get("oleh", "")
        except ValueError:
            pass
    ch = diff(st["snapshot"], snap) if st["revisions"] else []
    ts = datetime.now(WIB).strftime("%d %b %Y %H:%M WIB")
    st["revisions"].append({"rev": len(st["revisions"]) + 1, "tanggal": ts, "perubahan": ch, "diminta_oleh": by,
                            "ringkasan": f"{len(ch)} istilah berubah" if ch else
                            (f"Penerbitan awal ({len(snap) - 1} Fungsi)" if len(st["revisions"]) == 0 else "Diterbitkan manual, tanpa perubahan istilah")})
    fn = publish(snap, st["revisions"])
    st["revisions"][-1]["berkas"] = fn
    st.update({"digest": digest(snap), "snapshot": snap})
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))
    REQUEST.unlink(missing_ok=True)
    write_status(st, snap)
    return fn


def main() -> None:
    sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "loader")]
    from catalog_loader import Catalog
    fn = run(Catalog(dry=False), force="--force" in sys.argv)
    print(f"fungsi_pdf: {fn or 'tidak ada permintaan (status diperbarui)'}")


if __name__ == "__main__":
    main()
