#!/usr/bin/env python3
"""Glosarium di aplikasi -> Trino (gold_meta_glossary). Searah: aplikasi adalah sumber setelah admin Data Governance
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
        r = om.get("/v1/glossaryTerms?limit=500&fields=owners,reviewers,extension,glossary" + after)
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
    name = "gold_meta_glossary"
    L.ensure_table(tq, name, schema[name], set(tq.tables()), managed=True)
    L.replace_rows(tq, name, schema[name], rows)
    return len(rows)


def main() -> None:
    import uuid
    tq = L.Trino()
    n = build(tq, L.load_schema(), uuid.uuid4().hex[:12])
    L.log(f"gold_meta_glossary: {n} istilah dicatat dari aplikasi")


if __name__ == "__main__":
    main()
