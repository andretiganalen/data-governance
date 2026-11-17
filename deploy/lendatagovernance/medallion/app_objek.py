#!/usr/bin/env python3
"""Perubahan Database Object dari aplikasi (tambah / ubah / hapus). Tabel app_objek (Trino), append-only.
Daftar = silver_dim_meta_table + perubahan aplikasi (perubahan menang untuk TABLE_ID yang sama)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

TABLE = "app_objek"
FIELDS = ["dataset_id", "table_name", "object_type", "database_name"]
BASE_COLS = ["table_id", "dataset_id", "dataset_name", "table_name", "object_type", "database_name"]
ID_RE = re.compile(r"^TB\d{3}$")
AKSI = ("tambah", "ubah", "hapus")
OBJECT_TYPES = ("Table", "View")
_ready = False


def _sq(v) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def ensure(tq) -> None:
    global _ready
    if _ready:
        return
    tq.q(f"""CREATE TABLE IF NOT EXISTS {tq.fq(TABLE)} (
  _id varchar, table_id varchar, dataset_id varchar, table_name varchar, object_type varchar,
  database_name varchar, aksi varchar, oleh varchar, diubah_pada varchar, alasan varchar)
  WITH (format = 'PARQUET', format_version = 2)""")
    _ready = True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def latest_app(tq) -> dict[str, dict]:
    ensure(tq)
    cols = ["_id", "table_id", "dataset_id", "table_name", "object_type", "database_name", "aksi", "oleh", "diubah_pada", "alasan"]
    sql = (f"SELECT {', '.join(cols)} FROM (SELECT *, row_number() OVER (PARTITION BY table_id ORDER BY diubah_pada DESC, _id DESC) rn "
           f"FROM {tq.fq(TABLE)}) WHERE rn = 1")
    return {r[1]: dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def base(tq) -> dict[str, dict]:
    sql = (f"SELECT table_id, dataset_id, dataset_name, table_name, object_type, database_name "
           f"FROM {tq.fq('silver_dim_meta_table')}")
    return {r[0]: dict(zip(BASE_COLS, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def merged(tq) -> list[dict]:
    out = {k: {**r, "sumber": "Database"} for k, r in base(tq).items()}
    for k, a in latest_app(tq).items():
        if a["aksi"] == "hapus":
            out.pop(k, None)
            continue
        cur = out.get(k, {c: None for c in BASE_COLS})
        out[k] = {**cur, "table_id": k, **{f: a[f] for f in FIELDS}, "sumber": "Aplikasi",
                  "diubah_oleh": a["oleh"], "diubah_pada": a["diubah_pada"]}
    return sorted(out.values(), key=lambda r: r["table_id"])


def validate(tq, aksi: str, table_id: str | None, data: dict, current: dict[str, dict], datasets: set[str]) -> tuple[str, str]:
    if aksi not in AKSI:
        return "", "Aksi tidak dikenal."
    tid = (table_id or "").strip().upper()
    if not ID_RE.match(tid):
        return tid, "TABLE_ID harus berbentuk seperti TB019."
    if aksi == "tambah" and tid in current:
        return tid, f"TABLE_ID {tid} sudah ada."
    if aksi in ("ubah", "hapus") and tid not in current:
        return tid, f"TABLE_ID {tid} tidak ditemukan."
    if aksi == "hapus":
        return tid, ""
    did = (data.get("dataset_id") or "").strip().upper()
    if did not in datasets:
        return tid, "DATASET_ID tidak dikenal. Pilih dataset yang ada."
    if not (data.get("table_name") or "").strip():
        return tid, "Nama tabel wajib diisi."
    if (data.get("object_type") or "Table") not in OBJECT_TYPES:
        return tid, "Jenis objek harus Table atau View."
    if len((data.get("table_name") or "")) > 200:
        return tid, "Nama tabel terlalu panjang."
    return tid, ""


def append(tq, aksi: str, table_id: str, data: dict, oleh: str, alasan: str | None) -> dict:
    ensure(tq)
    if aksi == "hapus":
        cur = latest_app(tq).get(table_id) or base(tq).get(table_id) or {}
        data = {f: cur.get(f) for f in FIELDS}
    row = {"_id": uuid.uuid4().hex, "table_id": table_id,
           "dataset_id": (data.get("dataset_id") or "").strip().upper() or None,
           "table_name": (data.get("table_name") or "").strip() or None,
           "object_type": (data.get("object_type") or "Table").strip() or "Table",
           "database_name": (data.get("database_name") or "").strip() or None,
           "aksi": aksi, "oleh": oleh, "diubah_pada": _now(), "alasan": (alasan or "").strip()[:500] or None}
    cols = ["_id", "table_id", "dataset_id", "table_name", "object_type", "database_name", "aksi", "oleh", "diubah_pada", "alasan"]
    tq.q(f"INSERT INTO {tq.fq(TABLE)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row
