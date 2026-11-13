#!/usr/bin/env python3
"""Master Organisasi (2026-11-13, keputusan pemilik): Fungsi Generik terhadap unit aktual, bertingkat versi.

- Baseline  = CLP-001 rev.01 (tanggal dokumen 2024-02-28): daftar Fungsi Generik lama + definisi, tanpa pemetaan unit.
- Terbaru   = Nota 021/N/UQ/VIII/2026 (tanggal dokumen 2026-08-24): Fungsi Generik baru per Direktorat/Divisi/Bagian + tupoksi.
  Diekstrak dari PDF oleh nota_extract.py ke data/medallion/master_organisasi/nota_021.json (di luar git).
- Tanggal Dokumen menjadi tanggal pembaruan Master Organisasi: baseline berlaku sampai 2026-08-24, Nota 021 berlaku mulai 2026-08-24.
- Gold: gold_meta_master_organisasi (dibuat ulang hanya bila dokumen berubah). Glosarium "Fungsi Organisasi": istilah induk
  "Master Organisasi" + satu istilah per Fungsi Generik baru (tanpa awalan "Fungsi"), dibuat bila belum ada, tidak pernah menimpa
  suntingan admin. Penyesuaian pemetaan = admin Data Governance mengedit istilah di aplikasi (Edit), menulis dasar dokumennya; riwayat versi
  istilah dan gold_meta_glossary_app mencatatnya.
  python master_org.py [--force]"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "loader")]
import glossary_org as G  # noqa: E402
import lakehouse as L  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "data" / "medallion" / "master_organisasi"
NOTA, STATE = DIR / "nota_021.json", DIR / "gold_state.json"
TABLE = "gold_meta_master_organisasi"
PARENT = "MasterOrganisasi"
BASELINE = {"versi": "Baseline CLP-001", "dokumen": "CLP-001 Nomenklatur Unit Generik rev.01_20240228", "tanggal": date(2024, 2, 28)}
TERBARU = {"versi": "Nota 021", "dokumen": "Nota 021/N/UQ/VIII/2026 Pembaruan Pemetaan Fungsi Generik Terhadap Unit Aktual", "tanggal": date(2026, 8, 24)}
BINTANG = {1: "Fungsi di luar Struktur Organisasi, ditetapkan lewat Keputusan Direksi No. 058/SKEP.HC/DU/VI/2026 tentang Tim Produksi",
           2: "Fungsi di luar Struktur Organisasi, ditetapkan lewat Surat Tugas Direktur Utama No. 028/STU/DU/I/2026 tentang Tim Perencanaan dan Pelaksanaan PMN Tahun 2026"}
TGL = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def tgl(d: date) -> str:
    return f"{d.day} {TGL[d.month]} {d.year}"


def bare(name: str) -> str:
    return re.sub(r"^\s*fungsi\s+", "", name or "", flags=re.I).strip()


def load_nota() -> list[dict]:
    return json.loads(NOTA.read_text()) if NOTA.exists() else []


def rows_all() -> list[dict]:
    now = datetime.now(timezone.utc)
    nota = load_nota()
    out = []

    def add(ver, **kw):
        base = {"versi": ver["versi"], "dokumen": ver["dokumen"], "tanggal_dokumen": ver["tanggal"], "berlaku_mulai": ver["tanggal"],
                "direktorat": None, "divisi": None, "bagian": None, "tingkat_unit": None, "fungsi_lama": None, "catatan": None,
                "halaman": None, "sumber_perubahan": "Dokumen", "_loaded_at": now}
        base.update(kw)
        base["master_id"] = hashlib.sha1("|".join(str(base.get(k)) for k in ("versi", "direktorat", "divisi", "bagian", "fungsi_lama", "fungsi_generik_dokumen")).encode()).hexdigest()[:16]
        out.append(base)

    have = G.clp001_items()
    names = {k: v for k, v in have.items()}
    for r in nota:   # butir CLP-001 yang terpotong pergantian halaman tetap tercatat (nama dari Nota), definisinya perlu input manual
        if r["fungsi_lama"] not in ("", "-") and G.norm(r["fungsi_lama"]) not in names:
            names[G.norm(r["fungsi_lama"])] = (r["fungsi_lama"], G.PLACEHOLDER)
    for k, (nm, d) in names.items():
        add(BASELINE, berlaku_sampai=TERBARU["tanggal"], is_current=False, fungsi_lama=nm, fungsi_generik=bare(nm), fungsi_generik_dokumen=nm, tupoksi=d)
    for r in nota:
        add(TERBARU, berlaku_sampai=None, is_current=True, direktorat=r["direktorat"], divisi=r["divisi"], bagian=r["bagian"],
            tingkat_unit=r["tingkat_unit"], fungsi_lama=r["fungsi_lama"], fungsi_generik=bare(r["fungsi_baru"]),
            fungsi_generik_dokumen=r["fungsi_baru"], tupoksi=r["tupoksi"], catatan=BINTANG.get(r.get("fungsi_baru_bintang", 0)), halaman=r["halaman"])
    return out


def build_gold(tq: L.Trino, schema: dict, force: bool = False) -> str:
    rows = rows_all()
    fp = hashlib.sha1(json.dumps([{k: str(v) for k, v in r.items() if k != "_loaded_at"} for r in rows], sort_keys=True).encode()).hexdigest()
    live = set(tq.tables())
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if not force and TABLE in live and st.get("fp") == fp:
        return f"{TABLE}: tidak berubah ({len(rows)} baris)"
    batch = fp[:12]
    for r in rows:
        r["_batch_id"] = batch
    L.ensure_table(tq, TABLE, schema[TABLE], live, managed=True)
    L.replace_rows(tq, TABLE, schema[TABLE], rows)
    DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"fp": fp, "baris": len(rows)}))
    return f"{TABLE}: {len(rows)} baris dicatat"


def term_name(display: str) -> str:
    return re.sub(r"[^\w]+", "_", display, flags=re.U).strip("_")


def describe(display: str, rows: list[dict]) -> str:
    tup = list(dict.fromkeys(r["tupoksi"] for r in rows if r["tupoksi"]))
    lines = [tup[0] if len(tup) == 1 else "Tupoksi berbeda per unit pelaksana (lihat daftar di bawah).", ""]
    lines.append("**Unit pelaksana (Nota 021):**")
    for r in rows:
        unit = " › ".join(x for x in (r["direktorat"], r["divisi"], r["bagian"] if r["bagian"] != r["divisi"] else "") if x)
        lines.append(f"- {unit}" + (f". {r['tupoksi']}" if len(tup) > 1 else ""))
    lama = list(dict.fromkeys(r["fungsi_lama"] for r in rows if r["fungsi_lama"] not in ("", "-")))
    lines += ["", "**Fungsi Generik Lama (CLP-001):** " + (", ".join(bare(x) for x in lama) if lama else "tidak ada padanan (Fungsi baru)")]
    cat = list(dict.fromkeys(BINTANG[r["fungsi_baru_bintang"]] for r in rows if r.get("fungsi_baru_bintang")))
    if cat:
        lines.append("**Catatan:** " + "; ".join(cat) + ".")
    lines += ["", f"**Dasar:** {TERBARU['dokumen']}, tanggal dokumen {tgl(TERBARU['tanggal'])}.",
              "Penyesuaian pemetaan oleh Admin Data Governance: ubah deskripsi ini lewat Edit dan tulis dasar dokumennya (nomor dan tanggal) di baris Dasar."]
    return "\n".join(lines)


def seed(om) -> dict:
    nota = load_nota()
    if not nota:
        return {"istilah_baru": 0, "catatan": "nota_021.json belum ada (jalankan nota_extract.py)"}
    made = 0

    def ensure(name: str, body: dict) -> None:
        nonlocal made
        fqn = (body["parent"] + "." if body.get("parent") else G.GLOSSARY + ".") + name
        if om.find(f"/v1/glossaryTerms/name/{quote(fqn, safe='')}") is None:
            om.put("/v1/glossaryTerms", {"glossary": G.GLOSSARY, "name": name, **body})
            made += 1

    n_baru = len({bare(r["fungsi_baru"]) for r in nota})
    ensure(PARENT, {"displayName": "Master Organisasi", "description": (
        "Master Organisasi Len: Fungsi Generik terhadap unit aktual (Direktorat, Divisi, Bagian). Tanggal Dokumen menjadi tanggal pembaruan.\n\n"
        f"**Baseline:** {BASELINE['dokumen']}, tanggal dokumen {tgl(BASELINE['tanggal'])}: daftar Fungsi Generik lama dan definisinya, "
        "tanpa pemetaan unit (istilah di bawah \"Fungsi Generik\").\n\n"
        f"**Terbaru:** {TERBARU['dokumen']}, tanggal dokumen {tgl(TERBARU['tanggal'])}: {len(nota)} baris pemetaan, {n_baru} Fungsi Generik baru "
        "(istilah di bawah ini, nama tanpa awalan \"Fungsi\"). Versi sebelumnya berlaku sampai tanggal dokumen penggantinya.\n\n"
        "Data lengkap per versi: tabel Gold gold_meta_master_organisasi.")})
    owners = {}
    after = ""
    while True:   # tim FN_* → pemilik istilah bila namanya sama
        r = om.get("/v1/teams?limit=200" + after)
        for t in r.get("data", []):
            if t["name"].startswith("FN_"):
                owners[G.norm(t.get("displayName") or t["name"])] = {"id": t["id"], "type": "team"}
        if not r.get("paging", {}).get("after"):
            break
        after = "&after=" + r["paging"]["after"]
    groups: dict[str, list[dict]] = {}
    for r in nota:
        groups.setdefault(bare(r["fungsi_baru"]), []).append(r)
    for display, rows in groups.items():
        body = {"displayName": display, "parent": f"{G.GLOSSARY}.{PARENT}", "description": describe(display, rows)}
        if G.norm(display) in owners:
            body["owners"] = [owners[G.norm(display)]]
        ensure(term_name(display), body)
    return {"istilah_baru": made, "fungsi_generik_baru": len(groups), "dengan_pemilik": sum(1 for d in groups if G.norm(d) in owners)}


def main() -> None:
    from catalog_loader import Catalog
    L.log(f"master_org: {build_gold(L.Trino(), L.load_schema(), '--force' in sys.argv)}")
    L.log(f"master_org: {seed(Catalog(dry=False))}")


if __name__ == "__main__":
    main()
