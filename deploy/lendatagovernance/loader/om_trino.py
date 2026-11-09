#!/usr/bin/env python3
"""Sinkron katalog OpenMetadata dengan Trino lakehouse (lakekeeper.medallion_repository).

OpenMetadata di stack ini tidak punya komponen ingestion (Airflow), jadi metadata didorong lewat API:
  layanan "Len Lakehouse (Trino)" › database lakekeeper › schema medallion_repository › semua tabel,
  dengan kolom + tipe + komentar dari Trino, dan jumlah baris (profil tabel) per waktu sinkron.
Tabel yang sudah tidak ada di Trino dihapus (soft delete) dari katalog.

Tujuan: admin bisa mencocokkan :8585 dengan DBeaver — daftar tabel, kolom, dan jumlah baris harus sama.
Dipanggil otomatis di akhir lakehouse.py (bila token ada); bisa juga manual:
  /srv/lendatagovernance/medallion/.venv/bin/python loader/om_trino.py
Butuh: OM_TOKEN admin di /srv/lendatagovernance/secrets/loader.env, kredensial Trino di secrets/trino.env.
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "medallion")]
from om_loader import OM, q  # noqa: E402

SERVICE = "len_lakehouse_trino"
WIB = timezone(timedelta(hours=7))


def om_type(t: str) -> dict:
    t = t.lower()
    m = re.match(r"decimal\((\d+),\s*(\d+)\)", t)
    if m:
        return {"dataType": "DECIMAL", "precision": int(m.group(1)), "scale": int(m.group(2)), "dataTypeDisplay": t}
    base = {"varchar": "STRING", "integer": "INT", "bigint": "BIGINT", "double": "DOUBLE", "real": "FLOAT", "boolean": "BOOLEAN",
            "date": "DATE", "smallint": "SMALLINT", "tinyint": "TINYINT"}
    if t.startswith("timestamp"):
        return {"dataType": "TIMESTAMPZ" if "time zone" in t else "TIMESTAMP", "dataTypeDisplay": t}
    if t.startswith("varchar"):
        return {"dataType": "STRING", "dataTypeDisplay": t}
    return {"dataType": base.get(t, "UNKNOWN"), "dataTypeDisplay": t}


def layer(name: str) -> str:
    return next((x for x in ("bronze", "silver", "gold") if name.startswith(x + "_")), "lain")


def main() -> None:
    from lakehouse import Trino  # kredensial & koneksi yang sama dengan loader
    tq = Trino()
    om = OM(dry=False)
    now = datetime.now(timezone.utc)
    stamp = now.astimezone(WIB).strftime("%Y-%m-%d %H:%M WIB")

    om.put("/v1/services/databaseServices", {
        "name": SERVICE, "displayName": "Len Lakehouse (Trino)", "serviceType": "Trino",
        "description": "Trino lakehouse Len (Iceberg/Lakekeeper) — sistem rekam data aplikasi Data Governance. "
                       "Metadata disinkronkan oleh loader/om_trino.py (bukan ingestion OpenMetadata).",
        "connection": {"config": {"type": "Trino", "hostPort": f"{tq.conn.host}:{tq.conn.port}", "username": tq.conn.user,
                                  "catalog": tq.catalog}}})
    db = om.put("/v1/databases", {"name": tq.catalog, "service": SERVICE, "displayName": tq.catalog,
                                  "description": "Katalog Iceberg Lakekeeper di Trino datahub.len.co.id."})
    sch = om.put("/v1/databaseSchemas", {"name": tq.schema, "database": db["fullyQualifiedName"],
                                         "description": "Medallion Len Data Governance: bronze_* (mentah), silver_dim_*/silver_fact_* (bersih), "
                                                        "gold_* (siap dashboard). Definisi: deploy/lendatagovernance/medallion/schema/medallion_repository.sql"})
    cols = defaultdict_list()
    for t, c, dt, cm, pos in tq.q(
            f"SELECT c.table_name, c.column_name, c.data_type, c.comment, c.ordinal_position FROM information_schema.columns c "
            f"WHERE c.table_schema = '{tq.schema}' ORDER BY c.table_name, c.ordinal_position"):
        cols[t].append((c, dt, cm))
    tcomment = dict(tq.q(f"SELECT table_name, comment FROM system.metadata.table_comments "
                         f"WHERE catalog_name = '{tq.catalog}' AND schema_name = '{tq.schema}'"))
    names = sorted(cols)
    counts: dict[str, int | None] = {}
    for t in names:  # per tabel: satu tabel yang metadatanya rusak di Lakekeeper tidak menggagalkan semuanya
        try:
            counts[t] = tq.q(f"SELECT count(*) FROM {tq.fq(t)}", attempts=1)[0][0]
        except Exception as e:  # noqa: BLE001
            counts[t] = None
            print(f"  ! {t}: jumlah baris tidak terbaca ({str(e)[:100]})")
    for t in names:
        desc = (tcomment.get(t) or "").strip()
        n = f"**{counts[t]:,}**" if counts[t] is not None else "**tidak terbaca** (Lakekeeper gagal membaca metadata)"
        desc = (desc + "\n\n" if desc else "") + f"Lapisan **{layer(t)}**. Jumlah baris di Trino: {n} (sinkron {stamp})."
        body = {"name": t, "databaseSchema": sch["fullyQualifiedName"], "tableType": "Iceberg", "description": desc,
                "columns": [{"name": c, **om_type(dt), **({"description": cm} if cm else {})} for c, dt, cm in cols[t]]}
        tb = om.put("/v1/tables", body)
        if counts[t] is not None:
            om.call("PUT", f"/v1/tables/{tb['id']}/tableProfile", {
                "tableProfile": {"timestamp": int(now.timestamp() * 1000), "rowCount": counts[t], "columnCount": len(cols[t])}})
    # tabel yang sudah hilang dari Trino → soft delete
    existing = om.get(f"/v1/tables?databaseSchema={q(sch['fullyQualifiedName'])}&limit=1000").get("data", [])
    gone = [x for x in existing if x["name"] not in cols]
    for x in gone:
        om.call("DELETE", f"/v1/tables/{x['id']}")
    print(f"OpenMetadata ↔ Trino: {len(names)} tabel disinkron, {len(gone)} dihapus, {sum(v for v in counts.values() if v):,} baris, {sum(1 for v in counts.values() if v is None)} tak terbaca ({stamp})")


def defaultdict_list():
    from collections import defaultdict
    return defaultdict(list)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"selesai dalam {time.time() - t0:.0f} detik")
