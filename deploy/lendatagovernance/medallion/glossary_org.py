#!/usr/bin/env python3
"""Glosarium "Organisasi dan Fungsi": Fungsi Generik (CLP-001), Struktur Organisasi Saat Ini, Struktur Organisasi Kadaluarsa.

- Satu istilah per Fungsi (tim FN_* di aplikasi) di bawah istilah induk "Fungsi Generik". Definisi dibaca saat dijalankan dari
  CLP-001 di data/referensi (dokumen internal, tidak di git). Definisi yang tidak ditemukan atau terpotong (pergantian halaman PDF)
  ditulis "Perlu input manual dari Data Governance" dan terhitung di Gold gold_meta_glossary_status.
- Struktur Organisasi Saat Ini / Kadaluarsa: dari silver_dim_organization (SCD2: is_current, valid_to).
- Hanya MEMBUAT istilah yang belum ada; istilah yang sudah ada (diubah admin Data Governance) tidak pernah ditimpa.
- Dipanggil dari glossary_app.main (timer 10 menit): Fungsi baru di aplikasi otomatis mendapat istilah dengan penanda manual."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "loader")]
import lakehouse as L  # noqa: E402

PLACEHOLDER = "Perlu input manual dari Data Governance"
GLOSSARY = "Fungsi Organisasi"   # diganti nama oleh admin di aplikasi 2026-11-13 (tampil "Fungsi")
GLOSSARY_OWNER = "FN_Tata_Kelola"
ROOT = Path(__file__).resolve().parents[3]
TABLE_PREFIX = "len_lakehouse_trino.lakekeeper.medallion_repository."


def norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s or "")
    s = re.sub(r"^\s*fungsi\s+", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def clp001_items() -> dict[str, tuple[str, str]]:
    """{nama Fungsi ternormalisasi: (nama asli, definisi)}. Hanya butir utuh; butir yang terpotong pergantian halaman dilewati."""
    files = sorted((ROOT / "data" / "referensi").glob("* CLP-001 *.pdf"))
    if not files:
        return {}
    try:
        txt = subprocess.run(["pdftotext", "-layout", str(files[-1]), "-"], capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        return {}
    lines = txt.splitlines()
    starts = [i for i, ln in enumerate(lines) if re.match(r"^\s*\d{1,2}\s+Fungsi\s", ln)]
    out: dict[str, str] = {}
    for a, b in zip(starts, starts[1:] + [len(lines)]):
        seg = lines[a:b]
        mark = re.compile(r"Dokumen\s+tidak\s+terkontrol|CLP-001|\d{1,2}\s+OKT\s+\d{4}|Unit Generik|Definisi")
        cut = next((k for k, ln in enumerate(seg) if mark.search(ln)), None)
        if cut is not None:
            # footer di akhir butir: potong. Teks lain sesudah footer = pergantian halaman bercampur: butir tidak dipercaya.
            if cut == 0 or any(ln.strip() and not mark.search(ln) for ln in seg[cut:]):
                continue
            seg = seg[:cut]
        m = re.search(r"Fungsi (yang|bertanggung)", seg[0])
        if not m:
            continue
        col = m.start()
        name = re.sub(r"^\s*\d{1,2}\s+", "", seg[0][:col]).strip()
        defn = [seg[0][col:].strip()]
        for ln in seg[1:]:
            if not ln.strip():
                continue
            left, right = ln[:col].strip(), ln[col:].strip()
            if left:
                name += " " + left
            if right:
                defn.append(right)
        d = re.sub(r"\s+", " ", " ".join(defn)).strip()
        if name and len(d) > 25:
            out[norm(name)] = (re.sub(r"\s+", " ", name).strip(), d)
    return out


def clp001_definitions() -> dict[str, str]:
    """{nama Fungsi ternormalisasi: definisi}."""
    return {k: v[1] for k, v in clp001_items().items()}


def team_ref(om, name: str):
    t = om.find(f"/v1/teams/name/{quote(name, safe='')}")
    return {"id": t["id"], "type": "team"} if t else None


def org_counts(tq: L.Trino) -> dict:
    # Jangan campur count(DISTINCT IF(...)) dengan agregat lain dalam satu query: Trino menghabiskan 500 dtk di
    # OptimizeMixedDistinctAggregations (OPTIMIZER_TIMEOUT) dan timer glosarium macet. Query sederhana, masing-masing cepat.
    t = tq.fq("silver_dim_organization")
    a = tq.q(f"SELECT count_if(is_current), count_if(NOT is_current), max(IF(NOT is_current, valid_to)) FROM {t}")[0]
    d = tq.q(f"SELECT count(DISTINCT divisi), count(DISTINCT direktorat), count(DISTINCT unit_kerja) FROM {t} WHERE is_current")[0]
    return {"aktif": a[0], "kadaluarsa": a[1], "divisi": d[0], "direktorat": d[1], "unit": d[2], "terakhir_kadaluarsa": a[2]}


def seed(om, tq: L.Trino) -> dict:
    owner = team_ref(om, GLOSSARY_OWNER)
    glos = {"name": GLOSSARY, "displayName": "Organisasi dan Fungsi", "mutuallyExclusive": False,
            "description": "Glosarium struktur organisasi Len: Fungsi Generik (CLP-001) sebagai Data Owner, serta struktur organisasi "
                           "saat ini dan kadaluarsa. Bagian yang bertuliskan \"" + PLACEHOLDER + "\" perlu dilengkapi admin Data Governance."}
    if owner:
        glos["owners"] = [owner]
    if not om.find(f"/v1/glossaries/name/{quote(GLOSSARY, safe='')}"):
        om.put("/v1/glossaries", glos)
    made = 0

    def ensure(name: str, body: dict) -> None:
        nonlocal made
        # FQN istilah turunan memuat induknya: Glosarium.Induk.Nama (tanpa ini istilah selalu dianggap belum ada dan ditimpa)
        fqn = (body["parent"] + "." if body.get("parent") else GLOSSARY + ".") + name
        if om.find(f"/v1/glossaryTerms/name/{quote(fqn, safe='')}") is None:
            om.put("/v1/glossaryTerms", {"glossary": GLOSSARY, "name": name, **body})
            made += 1

    ensure("FungsiGenerik", {
        "displayName": "Fungsi Generik",
        "description": "Unit generik pelaksana kegiatan perusahaan menurut CLP-001 Nomenklatur Fungsi Generik. Setiap Fungsi menjadi Data Owner "
                       "di Len Data Governance (satu tim FN_* per Fungsi, di bawah Divisinya)."})
    c = org_counts(tq)
    ensure("StrukturOrganisasiSaatIni", {
        "displayName": "Struktur Organisasi Saat Ini",
        "description": f"Susunan Direktorat, Divisi (Eselon 1), unit kerja (Eselon 2), dan Fungsi yang berlaku saat ini (is_current = true, "
                       f"valid_to 9999-12-31). Saat dicatat: {c['aktif']} baris aktif ({c['direktorat']} Direktorat, {c['divisi']} Divisi, "
                       f"{c['unit']} unit kerja). Sumber: tabel silver_dim_organization. Data Owner: {PLACEHOLDER}."})
    ensure("StrukturOrganisasiKadaluarsa", {
        "displayName": "Struktur Organisasi Kadaluarsa",
        "description": f"Versi susunan organisasi yang sudah tidak berlaku (is_current = false, valid_to sebelum 9999-12-31). Saat dicatat: "
                       f"{c['kadaluarsa']} baris kadaluarsa. Sumber: tabel silver_dim_organization (riwayat SCD2). "
                       f"Aturan penentuan kadaluarsa dan Data Owner: {PLACEHOLDER}."})
    defs = clp001_definitions()
    after = ""
    teams = []
    while True:
        r = om.get("/v1/teams?limit=200" + after)
        teams += [t for t in r.get("data", []) if t["name"].startswith("FN_")]
        if not r.get("paging", {}).get("after"):
            break
        after = "&after=" + r["paging"]["after"]
    for t in teams:
        ref = {"id": t["id"], "type": "team"}
        d = defs.get(norm(t.get("displayName") or t["name"]))
        ensure(t["name"][3:], {
            "displayName": t.get("displayName") or t["name"][3:], "parent": f"{GLOSSARY}.FungsiGenerik", "owners": [ref],
            "description": d or PLACEHOLDER})
    return {"istilah_baru": made, "fungsi": len(teams), "definisi_clp001": len(defs)}


def tag_columns(om) -> int:
    """Tautkan kolom ke istilah (source Glossary) bila belum: is_current / valid_to / fungsi."""
    plan = [("silver_dim_organization", "is_current", "StrukturOrganisasiSaatIni"),
            ("silver_dim_organization", "valid_to", "StrukturOrganisasiKadaluarsa"),
            ("silver_dim_organization", "fungsi", "FungsiGenerik"), ("gold_meta_fungsi", "fungsi", "FungsiGenerik")]
    n = 0
    for tbl, col, term in plan:
        t = om.find(f"/v1/tables/name/{quote(TABLE_PREFIX + tbl, safe='')}?fields=columns,tags")
        if not t:
            continue
        i = next((k for k, c in enumerate(t["columns"]) if c["name"] == col), None)
        if i is None:
            continue
        fqn = f"{GLOSSARY}.{term}"
        tags = [{k: g[k] for k in ("tagFQN", "source", "labelType", "state") if k in g} for g in t["columns"][i].get("tags", [])]
        if any(g["tagFQN"] == fqn for g in tags):
            continue
        tags.append({"tagFQN": fqn, "source": "Glossary", "labelType": "Manual", "state": "Confirmed"})
        om.call("PATCH", f"/v1/tables/{t['id']}", [{"op": "add", "path": f"/columns/{i}/tags", "value": tags}],
                "application/json-patch+json")
        n += 1
    return n


def main() -> None:
    from catalog_loader import Catalog
    om = Catalog(dry=False)
    tq = L.Trino()
    L.log(f"glossary_org: {seed(om, tq)}; kolom tertaut baru: {tag_columns(om)}")


if __name__ == "__main__":
    main()
