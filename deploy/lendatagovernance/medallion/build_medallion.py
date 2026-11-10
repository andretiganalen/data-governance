"""Workbook Governance → Silver/Gold (fungsi murni, dipakai medallion/lakehouse.py).

  silver(wb)  sheet workbook (wbmod.read_xlsx) → baris bersih per sheet + kolom catatan mutu
  gold(s)     Silver → tabel metadata siap pakai (kamus data, lineage, hak akses, glosarium, aturan mutu, ...)

Tidak menulis berkas: hasilnya dimuat lakehouse.py ke Trino lakekeeper.medallion_repository (satu-satunya
sistem rekam data). Rilis CSV/XLSX + panel /unduh/ lama dihentikan 2026-11-10.

Isi Gold = metadata tata kelola, bukan isi transaksi aplikasi ERM.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "loader"))
import workbook as wbmod  # noqa: E402  (read_xlsx, dq_test, SENSITIVITY_RANK)

RANK = wbmod.SENSITIVITY_RANK
MISSING = {"", "0", "not found", "-", "n/a"}


def clean(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v.lower() in MISSING else " ".join(v.split())


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
