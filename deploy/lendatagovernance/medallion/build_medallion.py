"""Workbook Governance → Medallion (Bronze → Silver → Gold) + panel unduh "Data Siap Pakai".

Usage:
  python3 build_medallion.py --release "261106 01" --workbook <file.xlsx> [--egrc <E-GRC.xlsx>]
                             [--root /srv/lendatagovernance/medallion] [--manifest-out <path.json>]

Layout under --root:
  work/<rid>/bronze/*.csv     sheet workbook apa adanya (hanya di server)
  work/<rid>/silver/*.csv     dibersihkan + kolom catatan_mutu (hanya di server)
  panel/rilis/<rid>/          GOLD metadata: *.csv + "<YYMMDD CC> Data Siap Pakai (Gold).xlsx" + manifest.json
  panel/rilis/<rid>/grc/      GOLD E-GRC (egrc.py) — Confidential, login terpisah (unduh-grc.htpasswd)
  work/<rid>/{bronze,silver}/egrc/  Bronze/Silver E-GRC (hanya di server)
  panel/index.html            panel unduh (disajikan gateway di /unduh/, dengan login)
<rid> = release with the space replaced by "-" (e.g. 261106-01).

Isi Gold = metadata tata kelola (kamus data, lineage, hak akses, glosarium, aturan mutu, ...),
bukan isi transaksi aplikasi ERM: belum ada koneksi ke basis data ERM.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "loader"))
import workbook as wbmod  # noqa: E402  (read_xlsx, dq_test, SENSITIVITY_RANK)

RANK = wbmod.SENSITIVITY_RANK
MISSING = {"", "0", "not found", "-", "n/a"}


def clean(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v.lower() in MISSING else " ".join(v.split())


def write_csv(path: Path, rows: list[dict], cols: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = cols or (list(rows[0].keys()) if rows else [])
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # BOM → Excel membuka UTF-8 dengan benar
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ------------------------------------------------------------------ Silver
def silver(wb: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Trim, normalise placeholders ('0', 'Not Found') to empty, drop exact duplicates, flag broken references."""
    out: dict[str, list[dict]] = {}
    for sheet, rows in wb.items():
        if sheet == "Library":
            continue
        seen, keep = set(), []
        for r in rows:
            c = {k: clean(v) for k, v in r.items()}
            key = tuple(sorted(c.items()))
            if key in seen:
                continue
            seen.add(key)
            c["catatan_mutu"] = ""
            keep.append(c)
        out[sheet] = keep
    tables = {t["TABLE_ID"] for t in out["Database_Object"]}
    glossary = {g["FIELD_ID"]: g for g in out["Business_Glossary"]}
    orgs = {o["ORG_ID"] for o in out["Master_Organization"]}

    def flag(row, note):
        row["catatan_mutu"] = "; ".join(x for x in (row["catatan_mutu"], note) if x)

    for f in out["Data_Element_Attribute"]:
        if f["TABLE_ID"] not in tables:
            flag(f, "tabel belum terdaftar di Database_Object")
        if not glossary.get(f["FIELD_ID"], {}).get("DEFINISI"):
            flag(f, "definisi belum ada")
    for a in out["Data_Governance_Assignment"] + out["Data_Security_Access"]:
        if a["ORG_ID"] and a["ORG_ID"].lower() != "all" and a["ORG_ID"] not in orgs:
            flag(a, "ORG_ID tidak dikenal")
    for d in out["Business_Dataset"]:
        if not d["SYSTEM_ID"]:
            flag(d, "sistem sumber belum ditentukan")
    return out


# ------------------------------------------------------------------ Gold
GOLD_INFO = {
    "gold_kamus_data": ("Kamus Data",
        "Satu baris per elemen data/kolom: tabel, istilah bisnis, definisi, tipe, sensitivitas, unit pemilik/steward/pengguna, aturan mutu, jumlah layar hilir, status kelengkapan.",
        "Apa arti data ini? Siapa pemiliknya? Kolom mana yang sensitif?"),
    "gold_ringkasan_tabel": ("Ringkasan Tabel",
        "Satu baris per tabel: dataset, domain, jumlah kolom, sensitivitas tertinggi, unit pemilik, jumlah layar hilir, % definisi lengkap.",
        "Data apa yang ada dan seberapa lengkap tata kelolanya?"),
    "gold_ringkasan_layar": ("Ringkasan Layar/Dashboard LenO",
        "Satu baris per layar aplikasi ERM di LenO: modul, jumlah field, tabel sumber, sensitivitas tertinggi, jumlah unit yang boleh melihat.",
        "Dataset mana yang mengisi layar/dashboard ini?"),
    "gold_lineage": ("Lineage Kolom → Layar",
        "Satu baris per aliran data: sistem, dataset, tabel, kolom, istilah bisnis → layar & label tujuan.",
        "Dari mana data berasal dan ke mana mengalir? Apa yang terdampak bila kolom berubah?"),
    "gold_hak_akses": ("Matriks Hak Akses",
        "Satu baris per kombinasi layar × field × unit kerja × izin, lengkap dengan divisi, direktorat, dan sensitivitas.",
        "Siapa memakai data ini dan dengan izin apa?"),
    "gold_glosarium": ("Glosarium Bisnis",
        "Satu baris per istilah bisnis: definisi, status definisi, unit pemilik, steward, pengguna, jumlah kolom & layar terkait.",
        "Istilah bisnis apa yang berlaku dan apa artinya?"),
    "gold_aturan_mutu": ("Aturan Mutu Data",
        "Satu baris per aturan mutu: elemen data, aturan, validasi, jenis uji (otomatis/deskriptif), status eksekusi.",
        "Aturan kualitas apa yang berlaku pada data ini?"),
    "gold_organisasi": ("Struktur Organisasi",
        "Satu baris per unit kerja: fungsi, divisi, direktorat — untuk filter dan pengelompokan di dashboard.",
        "Unit kerja mana berada di divisi/direktorat mana?"),
    "gold_kpi_tata_kelola": ("Indikator Tata Kelola",
        "Indikator siap tampil: jumlah aset, % kelengkapan definisi/klasifikasi/pemilik, cakupan lineage & aturan mutu.",
        "Seberapa matang tata kelola data saat ini?"),
}


def gold(s: dict[str, list[dict]]) -> dict[str, list[dict]]:
    org = {o["ORG_ID"]: o for o in s["Master_Organization"]}
    tables = {t["TABLE_ID"]: t for t in s["Database_Object"]}
    datasets = {d["DATASET_ID"]: d for d in s["Business_Dataset"]}
    glossary = {g["FIELD_ID"]: g for g in s["Business_Glossary"]}
    fields = s["Data_Element_Attribute"]

    def unit(oid: str) -> str:
        if oid.lower() == "all":
            return "Seluruh Unit Kerja"
        o = org.get(oid)
        return f"{oid} {o['UNIT_KERJA']}" if o else oid

    assign = defaultdict(lambda: defaultdict(set))
    for a in s["Data_Governance_Assignment"]:
        assign[a["FIELD_ID"]][a["ROLE"]].add(unit(a["ORG_ID"]))
    cls = defaultdict(set)
    for a in s["Data_Security_Access"]:
        if a["CLASSIFICATION"]:
            cls[a["FIELD_ID"]].add(a["CLASSIFICATION"])

    def sens(fid):
        c = cls.get(fid)
        return max(c, key=lambda x: RANK.get(x, -1)) if c else ""

    rules = defaultdict(list)
    for r in s["Data_Quality_Rules"]:
        rules[r["FIELD_ID"]].append(r)
    lin_by_field = defaultdict(set)
    for l in s["Data_Flow_Lineage"]:
        lin_by_field[l["FIELD_ID"]].add(l["TARGET_ASSET"])
    j = lambda xs: "; ".join(sorted(xs))  # noqa: E731
    yn = lambda b: "Ya" if b else "Tidak"  # noqa: E731

    # Kamus data
    kamus = []
    for f in fields:
        fid, t = f["FIELD_ID"], tables.get(f["TABLE_ID"])
        ds = datasets.get(t["DATASET_ID"], {}) if t else {}
        g = glossary.get(fid, {})
        a = assign.get(fid, {})
        kamus.append({
            "field_id": fid, "sistem": ds.get("SYSTEM_NAME", ""), "domain_bisnis": ds.get("BUSINESS_DOMAIN", ""),
            "dataset": ds.get("BUSINESS_DATASET", ""), "tabel": t["TABLE_NAME"] if t else "",
            "kolom": f["COLUMN_NAME"], "istilah_bisnis": f["BUSINESS_TERM"] or g.get("BUSINESS_TERM", ""),
            "definisi": g.get("DEFINISI", ""), "tipe_data": f["DATA_TYPE"], "sensitivitas": sens(fid),
            "unit_pemilik": j(a.get("Data Owner", ())), "unit_steward": j(a.get("Data Steward", ())),
            "unit_pengguna": j(a.get("Data User", ())),
            "jumlah_aturan_mutu": len(rules.get(fid, ())),
            "aturan_mutu": "; ".join(f"{r['RULE']} ({r['VALIDATION']})" for r in rules.get(fid, ())),
            "jumlah_layar_hilir": len(lin_by_field.get(fid, ())),
            "ada_tabel": yn(bool(t)), "ada_definisi": yn(bool(g.get("DEFINISI"))),
            "ada_klasifikasi": yn(bool(sens(fid))), "ada_pemilik": yn(bool(a.get("Data Owner"))),
        })

    # Ringkasan tabel
    rt = []
    for tid, t in sorted(tables.items(), key=lambda kv: kv[1]["TABLE_NAME"]):
        ds = datasets.get(t["DATASET_ID"], {})
        ks = [k for k, f in zip(kamus, fields) if f["TABLE_ID"] == tid]
        sv = [k["sensitivitas"] for k in ks if k["sensitivitas"]]
        screens = set().union(*[lin_by_field.get(k["field_id"], set()) for k in ks]) if ks else set()
        rt.append({
            "tabel": t["TABLE_NAME"], "table_id": tid, "dataset": ds.get("BUSINESS_DATASET", t["DATASET_NAME"]),
            "domain_bisnis": ds.get("BUSINESS_DOMAIN", ""), "sistem": ds.get("SYSTEM_NAME", ""),
            "jumlah_kolom": len(ks), "kolom_confidential": sum(1 for x in sv if RANK.get(x, 0) >= 2),
            "sensitivitas_tertinggi": max(sv, key=lambda x: RANK.get(x, -1)) if sv else "",
            "unit_pemilik": j({u for k in ks for u in k["unit_pemilik"].split("; ") if u}),
            "jumlah_layar_hilir": len(screens),
            "pct_definisi": round(100 * sum(k["ada_definisi"] == "Ya" for k in ks) / len(ks)) if ks else 0,
            "jumlah_aturan_mutu": sum(k["jumlah_aturan_mutu"] for k in ks),
        })

    # Lineage
    tname = {tid: t["TABLE_NAME"] for tid, t in tables.items()}
    lin = []
    for l in s["Data_Flow_Lineage"]:
        t = tables.get(l["TABLE_ID"], {})
        ds = datasets.get(t.get("DATASET_ID", ""), {})
        scr = l["TARGET_ASSET"]
        lin.append({
            "lineage_id": l["LINEAGE_ID"], "sistem": l["SYSTEM_NAME"], "domain_bisnis": ds.get("BUSINESS_DOMAIN", ""),
            "dataset": ds.get("BUSINESS_DATASET", ""), "tabel": tname.get(l["TABLE_ID"], l["TABLE_NAME"]),
            "kolom": l["FIELD_NAME"], "field_id": l["FIELD_ID"],
            "istilah_bisnis": glossary.get(l["FIELD_ID"], {}).get("BUSINESS_TERM", ""),
            "modul": scr.split(" - ")[0] if " - " in scr else scr, "layar_tujuan": scr,
            "label_di_layar": l["TARGET_LABEL"], "jenis_aset": l["ASSET_TYPE"], "sensitivitas": sens(l["FIELD_ID"]),
        })

    # Ringkasan layar
    access_by_screen = defaultdict(list)
    for a in s["Data_Security_Access"]:
        access_by_screen[a["TARGET_ASSET"]].append(a)
    rl = []
    by_screen = defaultdict(list)
    for x in lin:
        by_screen[x["layar_tujuan"]].append(x)
    for scr, xs in sorted(by_screen.items()):
        sv = [x["sensitivitas"] for x in xs if x["sensitivitas"]]
        acc = access_by_screen.get(scr, [])
        rl.append({
            "modul": xs[0]["modul"], "layar": scr, "jumlah_field": len({x["label_di_layar"] for x in xs}),
            "tabel_sumber": j({x["tabel"] for x in xs}), "jumlah_tabel_sumber": len({x["tabel"] for x in xs}),
            "dataset_sumber": j({x["dataset"] for x in xs if x["dataset"]}),
            "sensitivitas_tertinggi": max(sv, key=lambda v: RANK.get(v, -1)) if sv else "",
            "jumlah_unit_boleh_lihat": len({a["ORG_ID"] for a in acc if a["PERMISSION_TYPE"] == "DA-View"}),
            "jumlah_unit_boleh_ubah": len({a["ORG_ID"] for a in acc if a["PERMISSION_TYPE"] == "DM-Update"}),
            "unit_pemilik": j({u for x in xs for u in assign.get(x["field_id"], {}).get("Data Owner", ())}),
        })

    # Hak akses
    ha = []
    for a in s["Data_Security_Access"]:
        o = org.get(a["ORG_ID"], {})
        ha.append({
            "access_id": a["ACCESS_ID"], "layar": a["TARGET_ASSET"], "label_di_layar": a["TARGET_LABEL"],
            "field_id": a["FIELD_ID"], "kolom": a["FIELD_NAME"], "org_id": a["ORG_ID"],
            "unit_kerja": a["UNIT_KERJA"] or o.get("UNIT_KERJA", ""), "divisi": o.get("DIVISI", ""),
            "direktorat": o.get("DIREKTORAT", ""), "sensitivitas": a["CLASSIFICATION"],
            "kategori_izin": a["PERMISSION_CATEGORY"], "jenis_izin": a["PERMISSION_TYPE"],
        })

    # Glosarium
    cols_by_field = Counter(f["FIELD_ID"] for f in fields)
    gl = []
    for fid in sorted(set(glossary) | set(cols_by_field)):
        g = glossary.get(fid, {})
        a = assign.get(fid, {})
        term = g.get("BUSINESS_TERM") or next((f["BUSINESS_TERM"] for f in fields if f["FIELD_ID"] == fid), "")
        gl.append({
            "field_id": fid, "istilah_bisnis": term, "definisi": g.get("DEFINISI", ""),
            "status_definisi": "Tersedia" if g.get("DEFINISI") else "Belum ada",
            "unit_pemilik": j(a.get("Data Owner", ())), "unit_steward": j(a.get("Data Steward", ())),
            "unit_pengguna": j(a.get("Data User", ())), "jumlah_kolom": cols_by_field.get(fid, 0),
            "jumlah_layar": len(lin_by_field.get(fid, ())), "sensitivitas": sens(fid),
        })

    # Aturan mutu
    am = []
    for r in s["Data_Quality_Rules"]:
        td = wbmod.dq_test(r["VALIDATION"])
        am.append({
            "field_id": r["FIELD_ID"], "kolom": r["FIELD_NAME"], "istilah_bisnis": r["BUSINESS_TERM"],
            "aturan": r["RULE"], "validasi": r["VALIDATION"],
            "jenis_uji": f"Otomatis ({td[0]})" if td else "Deskriptif (diperiksa manual)",
            "status_eksekusi": "Belum dijalankan",
        })

    og = [{"org_id": o["ORG_ID"], "unit_kerja": o["UNIT_KERJA"], "fungsi": o["FUNGSI"], "divisi": o["DIVISI"],
           "direktorat": o["DIREKTORAT"]} for o in s["Master_Organization"]]

    n = len(kamus) or 1
    pct = lambda key: round(100 * sum(k[key] == "Ya" for k in kamus) / n, 1)  # noqa: E731
    kpi = [
        ("Inventaris", "Sistem sumber", len({d["SYSTEM_NAME"] for d in datasets.values() if d["SYSTEM_NAME"]}), "sistem"),
        ("Inventaris", "Dataset bisnis", len(datasets), "dataset"),
        ("Inventaris", "Tabel", len(tables), "tabel"),
        ("Inventaris", "Elemen data (kolom)", len(kamus), "kolom"),
        ("Inventaris", "Layar/dashboard LenO", len(rl), "layar"),
        ("Inventaris", "Istilah glosarium", len(glossary), "istilah"),
        ("Inventaris", "Unit kerja", len(og), "unit"),
        ("Kelengkapan", "Kolom dengan definisi", pct("ada_definisi"), "%"),
        ("Kelengkapan", "Kolom dengan klasifikasi sensitivitas", pct("ada_klasifikasi"), "%"),
        ("Kelengkapan", "Kolom dengan unit pemilik", pct("ada_pemilik"), "%"),
        ("Kelengkapan", "Kolom yang tabelnya terdaftar", pct("ada_tabel"), "%"),
        ("Sensitivitas", "Kolom Confidential atau lebih tinggi",
         sum(1 for k in kamus if RANK.get(k["sensitivitas"], 0) >= 2), "kolom"),
        ("Sensitivitas", "Kolom Restricted", sum(1 for k in kamus if k["sensitivitas"] == "Restricted"), "kolom"),
        ("Lineage", "Aliran kolom → layar", len(lin), "aliran"),
        ("Lineage", "Kolom yang dipakai di layar", round(100 * sum(1 for k in kamus if k["jumlah_layar_hilir"]) / n, 1), "%"),
        ("Mutu", "Aturan mutu", len(am), "aturan"),
        ("Mutu", "Aturan yang bisa diuji otomatis", sum(1 for r in am if r["jenis_uji"].startswith("Otomatis")), "aturan"),
        ("Mutu", "Aturan yang sudah dijalankan", 0, "aturan"),
        ("Akses", "Baris matriks hak akses", len(ha), "baris"),
    ]
    kpi = [{"kategori": a, "indikator": b, "nilai": c, "satuan": d} for a, b, c, d in kpi]

    return {"gold_kamus_data": kamus, "gold_ringkasan_tabel": rt, "gold_ringkasan_layar": rl,
            "gold_lineage": lin, "gold_hak_akses": ha, "gold_glosarium": gl, "gold_aturan_mutu": am,
            "gold_organisasi": og, "gold_kpi_tata_kelola": kpi}


# ------------------------------------------------------------------ XLSX
def write_xlsx(path: Path, g: dict[str, list[dict]], release: str, source: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    info = wb.active
    info.title = "Info"
    head = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="194A80")
    info.append(["Len Data Governance — Data Siap Pakai (Gold)"])
    info["A1"].font = Font(bold=True, size=14, color="194A80")
    info.append([f"Rilis {release}", f"Sumber: {source}"])
    info.append(["Isi: metadata tata kelola data ERM (bukan isi transaksi aplikasi)."])
    info.append([])
    info.append(["Sheet", "Nama", "Isi", "Menjawab", "Baris"])
    for c in info[5]:
        c.font, c.fill = head, fill
    for key, rows in g.items():
        name, desc, ans = GOLD_INFO[key]
        info.append([key.removeprefix("gold_")[:31], name, desc, ans, len(rows)])
    for col, w in zip("ABCDE", (24, 28, 90, 60, 8)):
        info.column_dimensions[col].width = w
    for key, rows in g.items():
        ws = wb.create_sheet(key.removeprefix("gold_")[:31])
        cols = list(rows[0].keys()) if rows else []
        ws.append(cols)
        for c in ws[1]:
            c.font, c.fill = head, fill
            c.alignment = Alignment(vertical="center")
        for r in rows:
            ws.append([r[c] for c in cols])
        ws.freeze_panes = "A2"
        if cols:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(rows) + 1}"
        for i, c in enumerate(cols, 1):
            width = max([len(str(c))] + [len(str(r[c])) for r in rows[:300]])
            ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
    wb.save(path)


# ------------------------------------------------------------------ Panel
PANEL_CSS = """
@font-face{font-family:Montserrat;font-weight:400;src:url(_aset/montserrat-400.woff2) format('woff2')}
@font-face{font-family:Montserrat;font-weight:600;src:url(_aset/montserrat-600.woff2) format('woff2')}
@font-face{font-family:Montserrat;font-weight:700;src:url(_aset/montserrat-700.woff2) format('woff2')}
@font-face{font-family:'Open Sans';font-weight:600;src:url(_aset/opensans-600.woff2) format('woff2')}
:root{--navy:#194A80;--navy7:#12375F;--navy50:#EEF3F9;--red:#DA0000;--blue:#0562C9;--ink:#3B3B3B;--text:#515151;
--muted:#838282;--line:#E6E6E6;--bg:#F5F6F8;--ok:#1E7B34}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:400 14px/1.55 Montserrat,Arial,sans-serif}
header{background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08);display:flex;align-items:center;gap:14px;padding:12px 28px}
header img{height:34px}header .brand{font:600 15px 'Open Sans',Arial;color:var(--ink)}header .brand b{color:var(--navy)}
header nav{margin-left:auto;font:600 14px 'Open Sans',Arial}header nav a{color:var(--navy);text-decoration:none}
main{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
h1{color:var(--ink);font:700 24px/1.25 Montserrat;margin:0 0 4px;letter-spacing:-.3px}
.sub{color:var(--muted);margin:0 0 22px}
.rel{background:#fff;border:1px solid var(--line);border-left:3px solid var(--red);padding:18px 22px;display:flex;
flex-wrap:wrap;gap:18px;align-items:center;margin-bottom:22px}
.rel .id{font:700 22px Montserrat;color:var(--navy)}.rel .meta{color:var(--muted);font-size:13px}
.btn{display:inline-block;background:var(--navy);color:#fff;font:600 14px Montserrat;padding:9px 16px;text-decoration:none;
border:0}.btn:hover{background:var(--navy7)}.btn.sec{background:#fff;color:var(--navy);border:1px solid var(--navy)}
.rel .btn{margin-left:auto}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line)}
th{background:var(--navy);color:#fff;text-align:left;font:600 13px 'Open Sans',Arial;padding:9px 12px}
td{border-top:1px solid var(--line);padding:10px 12px;vertical-align:top}
td .n{font-weight:700;color:var(--ink)}td .q{color:var(--blue);font-size:13px}td.num{text-align:right;white-space:nowrap}
td a{color:var(--navy);font-weight:600}
.note{margin-top:18px;padding:12px 16px;background:var(--navy50);border:1px solid #d6e2ef;font-size:13px}
h2{color:var(--ink);font:700 17px Montserrat;margin:34px 0 10px}
.conf{font:700 11px 'Open Sans',Arial;color:#fff;background:var(--red);padding:2px 8px;vertical-align:middle;margin-left:6px}
footer{background:#000;color:#fff;font-size:12px;padding:14px 28px}
@media(max-width:720px){header{padding:10px 16px}main{padding:20px 16px}.rel .btn{margin-left:0}
table,thead,tbody,tr,td{display:block}thead{display:none}tr{border-top:1px solid var(--line)}td{border:0}}
"""


def grc_section(m: dict) -> str:
    g = m.get("grc")
    if not g:
        return ""
    e, rid = html.escape, m["rid"]
    rows = "".join(
        f"<tr><td><div class='n'>{e(d['nama'])}</div>{e(d['isi'])}<div class='q'>Menjawab: {e(d['menjawab'])}</div></td>"
        f"<td class='num'>{d['baris']:,}".replace(",", ".") +
        f"</td><td class='num'><a href='rilis/{rid}/grc/{d['file']}' download='{e(m['release'])} {d['file']}'>CSV</a></td></tr>"
        for d in g["gold"])
    return f"""<h2>E-GRC: Manajemen Risiko Korporat <span class="conf">CONFIDENTIAL</span></h2>
<p class="sub" style="margin-bottom:12px">Sumber: {e(g['sumber'])}. Unduhan meminta <b>akun E-GRC</b> tersendiri (diberikan atas persetujuan pemilik data Risk Management).
Nilai uang dalam juta rupiah. Arti setiap kolom ada di <i>Kamus Data E-GRC</i>.</p>
<div class="rel"><div><div class="meta">E-GRC rilis</div><div class="id">{e(m['release'])}</div></div>
<div class="meta">{g['ringkas']['risiko']} risiko · {g['ringkas']['parameter']} parameter profil · {len(g['temuan'])} temuan mutu sumber</div>
<a class="btn" href="rilis/{rid}/grc/{e(g['xlsx'])}" download>Unduh E-GRC (XLSX)</a></div>
<table><thead><tr><th>Dataset</th><th style="width:90px;text-align:right">Baris</th><th style="width:80px;text-align:right">Unduh</th></tr></thead>
<tbody>{rows}</tbody></table>"""


def panel_index(panel: Path, releases: list[dict]) -> str:
    latest = releases[0]
    rid = latest["rid"]
    e = html.escape
    rows = "".join(
        f"<tr><td><div class='n'>{e(d['nama'])}</div>{e(d['isi'])}<div class='q'>Menjawab: {e(d['menjawab'])}</div></td>"
        f"<td class='num'>{d['baris']:,}".replace(",", ".") +
        f"</td><td class='num'><a href='rilis/{rid}/{d['file']}' download='{e(latest['release'])} {d['file']}'>CSV</a></td></tr>"
        for d in latest["gold"])
    hist = "".join(
        f"<tr><td>{e(r['release'])}</td><td>{e(r['dibuat'])}</td><td>{e(r['sumber'])}</td>"
        f"<td class='num'><a href='rilis/{r['rid']}/{e(r['xlsx'])}' download>XLSX</a></td></tr>" for r in releases)
    return f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Data Siap Pakai — Len Data Governance</title>
<style>{PANEL_CSS}</style></head><body>
<header><img src="_aset/len-logo.png" alt="Len"><div class="brand"><b>Len</b> Data Governance · Data Siap Pakai</div>
<nav><a href="/">Ke katalog data</a></nav></header>
<main>
<h1>Data Siap Pakai (Gold)</h1>
<p class="sub">Data bersih dan terstruktur untuk dashboard (Power BI, Excel, Looker Studio). Hanya rilis resmi yang ditampilkan.</p>
<div class="rel"><div><div class="meta">Rilis terbaru</div><div class="id">{e(latest['release'])}</div></div>
<div class="meta">Dibuat {e(latest['dibuat'])}<br>Sumber: {e(latest['sumber'])}</div>
<a class="btn" href="rilis/{rid}/{e(latest['xlsx'])}" download>Unduh semua (XLSX)</a></div>
<table><thead><tr><th>Dataset</th><th style="width:90px;text-align:right">Baris</th><th style="width:80px;text-align:right">Unduh</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="note"><b>Catatan isi.</b> Rilis ini berisi <b>metadata tata kelola</b> aplikasi ERM: kamus data, alur data,
hak akses, glosarium, aturan mutu, dan indikator. Isi transaksi aplikasi ERM di LenO belum tersedia.
CSV memakai UTF-8 dan pemisah koma. Pertanyaan tentang isi data: Staf Data Governance (UV-1).</div>
{grc_section(latest)}
<h2>Riwayat rilis</h2>
<table><thead><tr><th>Rilis</th><th>Dibuat</th><th>Sumber</th><th style="width:80px;text-align:right">Unduh</th></tr></thead>
<tbody>{hist}</tbody></table>
</main><footer>© PT Len Industri (Persero) · Len Data Governance</footer></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", required=True, help='"YYMMDD CC"')
    ap.add_argument("--workbook", required=True)
    ap.add_argument("--root", default="/srv/lendatagovernance/medallion")
    ap.add_argument("--assets", default=str(HERE / "panel-assets"), help="fonts + logo for the panel")
    ap.add_argument("--egrc", help="Bronze E-GRC (.xlsx) → Silver/Gold E-GRC (egrc.py)")
    ap.add_argument("--manifest-out")
    a = ap.parse_args()
    release, root, src = a.release, Path(a.root), Path(a.workbook)
    rid = release.replace(" ", "-")
    work, rel_dir = root / "work" / rid, root / "panel" / "rilis" / rid
    if rel_dir.exists():
        sys.exit(f"Rilis {release} sudah ada: {rel_dir} — rilis tidak ditimpa, gunakan nomor CC berikutnya.")

    raw = wbmod.read_xlsx(str(src))
    for sheet, rows in raw.items():
        write_csv(work / "bronze" / f"{sheet}.csv", rows)
    s = silver(raw)
    for sheet, rows in s.items():
        write_csv(work / "silver" / f"{sheet}.csv", rows)
    g = gold(s)

    rel_dir.mkdir(parents=True)
    xlsx = f"{release} Data Siap Pakai (Gold).xlsx"
    gold_meta = []
    for key, rows in g.items():
        write_csv(rel_dir / f"{key}.csv", rows)
        name, desc, ans = GOLD_INFO[key]
        gold_meta.append({"key": key, "file": f"{key}.csv", "nama": name, "isi": desc, "menjawab": ans,
                          "baris": len(rows), "kolom": list(rows[0].keys()) if rows else [],
                          "sha256": hashlib.sha256((rel_dir / f"{key}.csv").read_bytes()).hexdigest()[:16]})
    write_xlsx(rel_dir / xlsx, g, release, src.name)
    silver_notes = {k: sum(1 for r in v if r["catatan_mutu"]) for k, v in s.items()}
    manifest = {
        "release": release, "rid": rid, "dibuat": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sumber": src.name, "xlsx": xlsx, "gold": gold_meta,
        "bronze": {k: len(v) for k, v in raw.items()}, "silver": {k: len(v) for k, v in s.items()},
        "silver_catatan_mutu": silver_notes,
        "kpi": g["gold_kpi_tata_kelola"],
        "glosarium_belum_ada": [x["field_id"] + " " + x["istilah_bisnis"] for x in g["gold_glosarium"]
                                if x["status_definisi"] == "Belum ada"],
    }
    if a.egrc:
        import egrc
        manifest["grc"] = egrc.run(a.egrc, release, work, rel_dir / "grc")
    (rel_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))

    panel = root / "panel"
    (panel / "_aset").mkdir(exist_ok=True)
    for f in Path(a.assets).glob("*"):
        shutil.copy2(f, panel / "_aset" / f.name)
    releases = []
    for m in sorted((panel / "rilis").glob("*/manifest.json"), reverse=True):
        releases.append(json.loads(m.read_text()))
    (panel / "index.html").write_text(panel_index(panel, releases))
    if a.manifest_out:
        Path(a.manifest_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.manifest_out).write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"Rilis {release}: gold → {rel_dir} ({sum(d['baris'] for d in gold_meta)} baris, {len(gold_meta)} dataset)")


if __name__ == "__main__":
    main()
