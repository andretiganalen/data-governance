#!/usr/bin/env python3
"""Glosarium di aplikasi -> Trino (gold_meta_glossary_app). Searah: aplikasi adalah sumber setelah admin Data Governance
mengubahnya; tabel ini mencatat keadaan terkini (tiap 10 menit lewat timer, dan di akhir rebuild).
sumber_perubahan = "Aplikasi" bila definisi/nama berbeda dari Workbook (silver_dim_meta_glossary) atau istilah tidak ada di Workbook."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "loader")]
import lakehouse as L  # noqa: E402


def fetch_terms() -> list[dict]:
    from catalog_loader import Catalog
    om = Catalog(dry=False)
    out, after = [], ""
    while True:
        r = om.get("/v1/glossaryTerms?limit=500&fields=owners,reviewers,extension,glossary,parent,usageCount" + after)
        out += r.get("data", [])
        if not r.get("paging", {}).get("after"):
            return out
        after = "&after=" + r["paging"]["after"]


def names(refs) -> str | None:
    return "; ".join(sorted(x.get("displayName") or x["name"] for x in (refs or []))) or None


def build(tq: L.Trino, schema: dict, batch_id: str) -> int:
    wb = {r[0]: (r[1], r[2]) for r in tq.q(
        "SELECT field_id, business_term, definisi FROM " + tq.fq("silver_dim_meta_glossary") + " WHERE _source_system = 'DG_WORKBOOK'")}
    now = datetime.now(timezone.utc)
    rows = []
    for t in fetch_terms():
        fid = t["name"]
        ext = t.get("extension") or {}
        base = wb.get(fid)
        same = base is not None and (base[0] or "") == (t.get("displayName") or "") and (base[1] or "").strip() == (t.get("description") or "").strip()
        rows.append({"field_id": fid, "business_term": t.get("displayName") or fid, "definisi": t.get("description"),
                     "glosarium": (t.get("glossary") or {}).get("displayName") or (t.get("glossary") or {}).get("name"),
                     "data_owner": names(t.get("owners")), "data_steward": names(ext.get("dataSteward")),
                     "data_user": names(ext.get("dataUser")), "reviewer": names(t.get("reviewers")),
                     "versi": t.get("version"),
                     "diubah_oleh": t.get("updatedBy"),
                     "diubah_pada": datetime.fromtimestamp(t["updatedAt"] / 1000, timezone.utc) if t.get("updatedAt") else None,
                     "sumber_perubahan": "Workbook" if same else "Aplikasi", "_batch_id": batch_id, "_loaded_at": now})
    name = "gold_meta_glossary_app"
    L.ensure_table(tq, name, schema[name], set(tq.tables()), managed=True)
    L.replace_rows(tq, name, schema[name], rows)
    return len(rows)


def fetch_fungsi() -> list[dict]:
    from catalog_loader import Catalog
    om = Catalog(dry=False)
    out, after = [], ""
    while True:
        r = om.get("/v1/teams?limit=200&fields=parents,owns" + after)
        out += [t for t in r.get("data", []) if t["name"].startswith("FN_")]
        if not r.get("paging", {}).get("after"):
            return out
        after = "&after=" + r["paging"]["after"]


def build_fungsi(tq: L.Trino, schema: dict, batch_id: str) -> int:
    import workbook as W
    plan = W.to_lakehouse(W.build(W.read_xlsx(str(Path(__file__).resolve().parents[3] / "templates" / "261016 Rev.0.1_Data Governance_ERM.xlsx"))))
    wb = {t["name"]: (t["displayName"], t["description"]) for t in plan.teams if t["name"].startswith("FN_")}
    now = datetime.now(timezone.utc)
    rows = []
    for t in fetch_fungsi():
        owns = t.get("owns") or []
        par = (t.get("parents") or [{}])[0]
        rows.append({"team_name": t["name"], "fungsi": t.get("displayName") or t["name"],
                     "eselon1": par.get("displayName") or par.get("name"), "deskripsi": t.get("description"),
                     "jumlah_tabel_dimiliki": sum(1 for o in owns if o.get("type") == "table"),
                     "jumlah_istilah_dimiliki": sum(1 for o in owns if o.get("type") == "glossaryTerm"),
                     "versi": t.get("version"), "diubah_oleh": t.get("updatedBy"),
                     "diubah_pada": datetime.fromtimestamp(t["updatedAt"] / 1000, timezone.utc) if t.get("updatedAt") else None,
                     "sumber_perubahan": "Workbook" if wb.get(t["name"]) == (t.get("displayName"), t.get("description")) else "Aplikasi",
                     "_batch_id": batch_id, "_loaded_at": now})
    name = "gold_meta_fungsi"
    L.ensure_table(tq, name, schema[name], set(tq.tables()), managed=True)
    L.replace_rows(tq, name, schema[name], rows)
    return len(rows)


def build_status(tq: L.Trino, schema: dict, batch_id: str) -> int:
    """Kelengkapan tiap istilah + ringkasan per glosarium (gold_meta_glossary_status / _ringkasan)."""
    from glossary_org import PLACEHOLDER
    now = datetime.now(timezone.utc)
    rows = []
    for t in fetch_terms():
        desc = (t.get("description") or "").strip()
        manual = PLACEHOLDER.lower() in desc.lower()
        ada_def, ada_own, ada_rev = bool(desc) and not manual, bool(t.get("owners")), bool(t.get("reviewers"))
        tertaut = int(t.get("usageCount") or 0)
        gap = [k for k, ok in (("definisi", ada_def), ("Data Owner", ada_own), ("peninjau", ada_rev), ("tautan kolom", tertaut > 0)) if not ok]
        if manual and "definisi" not in gap:
            gap.append("definisi")
        yn = lambda b: "Ya" if b else "Tidak"  # noqa: E731
        rows.append({"field_id": t["name"], "business_term": t.get("displayName") or t["name"],
                     "glosarium": (t.get("glossary") or {}).get("displayName") or (t.get("glossary") or {}).get("name"),
                     "induk": (t.get("parent") or {}).get("displayName") or (t.get("parent") or {}).get("name"),
                     "ada_definisi": yn(ada_def), "ada_owner": yn(ada_own), "ada_reviewer": yn(ada_rev), "kolom_tertaut": tertaut,
                     "butuh_input_manual": yn(manual), "kekurangan": "; ".join(gap) or None,
                     "status": "Lengkap" if not gap else "Belum tuntas", "_batch_id": batch_id, "_loaded_at": now})
    summ = []
    for g in sorted({r["glosarium"] for r in rows}) + ["SEMUA"]:
        rs = [r for r in rows if g == "SEMUA" or r["glosarium"] == g]
        n, ok = len(rs), sum(r["status"] == "Lengkap" for r in rs)
        summ.append({"glosarium": g, "jumlah_istilah": n, "lengkap": ok, "belum_tuntas": n - ok,
                     "persen_lengkap": round(100.0 * ok / n, 1) if n else None,
                     "butuh_input_manual": sum(r["butuh_input_manual"] == "Ya" for r in rs),
                     "tanpa_owner": sum(r["ada_owner"] == "Tidak" for r in rs),
                     "tanpa_reviewer": sum(r["ada_reviewer"] == "Tidak" for r in rs),
                     "tanpa_tautan_kolom": sum(r["kolom_tertaut"] == 0 for r in rs), "_batch_id": batch_id, "_loaded_at": now})
    for name, data in (("gold_meta_glossary_status", rows), ("gold_meta_glossary_ringkasan", summ)):
        L.ensure_table(tq, name, schema[name], set(tq.tables()), managed=True)
        L.replace_rows(tq, name, schema[name], data)
    return len(rows)


def main() -> None:
    import uuid
    tq = L.Trino()
    try:  # istilah Organisasi dan Fungsi (dibuat bila belum ada); gagal tidak menghentikan pencatatan
        import glossary_org
        from catalog_loader import Catalog
        L.log(f"glossary_org: {glossary_org.seed(Catalog(dry=False), tq)}; kolom tertaut baru: {glossary_org.tag_columns(Catalog(dry=False))}")
    except (Exception, SystemExit) as e:  # noqa: BLE001
        L.log(f"glossary_org dilewati: {str(e)[:200]}")
    n = build(tq, L.load_schema(), uuid.uuid4().hex[:12])
    L.log(f"gold_meta_glossary_app: {n} istilah dicatat dari aplikasi")
    L.log(f"gold_meta_fungsi: {build_fungsi(tq, L.load_schema(), 'fungsi')} Fungsi dicatat dari aplikasi")
    L.log(f"gold_meta_glossary_status: {build_status(tq, L.load_schema(), 'status')} istilah dinilai kelengkapannya")


if __name__ == "__main__":
    main()
