#!/usr/bin/env python3
"""Data Element (kolom) dari aplikasi: tambah. Tabel app_elemen (Trino), append-only.
FIELD_ID dibuat otomatis: nomor F berikutnya dari semua sumber (silver_dim_meta_field, app_elemen, glosarium)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

TABLE = "app_elemen"
FIELDS = ["table_id", "column_name", "business_term", "data_type"]
_ready = False
FID_RE = re.compile(r"^F(\d{3,})$")


def _sq(v) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def ensure(tq) -> None:
    global _ready
    if _ready:
        return
    tq.q(f"""CREATE TABLE IF NOT EXISTS {tq.fq(TABLE)} (
  _id varchar, field_id varchar, table_id varchar, column_name varchar, business_term varchar, data_type varchar,
  aksi varchar, oleh varchar, diubah_pada varchar, alasan varchar)
  WITH (format = 'PARQUET', format_version = 2)""")
    _ready = True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def next_field_id(tq) -> str:
    ensure(tq)
    ids = set()
    for sql in (f"SELECT field_id FROM {tq.fq('silver_dim_meta_field')}",
                f"SELECT field_id FROM {tq.fq(TABLE)}",
                f"SELECT field_id FROM {tq.fq('gold_meta_glossary_app')}"):
        for (v,) in tq.q(sql):
            m = FID_RE.match(str(v or ""))
            if m:
                ids.add(int(m.group(1)))
    return f"F{(max(ids) if ids else 0) + 1:03d}"


def validate(tq, data: dict, tables: set[str], terms: set[str]) -> str:
    """Pesan galat kosong bila valid."""
    tid = (data.get("table_id") or "").strip()
    if tid not in tables:
        return "Pilih TABLE_ID yang sudah ada (dari Database Object)."
    if not (data.get("column_name") or "").strip():
        return "Nama kolom wajib diisi."
    bt = (data.get("business_term") or "").strip()
    if bt and bt not in terms:
        return "Business term harus dipilih dari Glosarium."
    if not (data.get("data_type") or "").strip():
        return "Tipe data wajib diisi."
    for k in ("column_name", "data_type"):
        if len(data.get(k) or "") > 200:
            return "Isian terlalu panjang."
    return ""


def append(tq, data: dict, oleh: str, alasan: str | None) -> dict:
    ensure(tq)
    fid = next_field_id(tq)
    row = {"_id": uuid.uuid4().hex, "field_id": fid, "table_id": data["table_id"].strip(),
           "column_name": data["column_name"].strip(), "business_term": (data.get("business_term") or "").strip() or None,
           "data_type": data["data_type"].strip(), "aksi": "tambah", "oleh": oleh, "diubah_pada": _now(),
           "alasan": (alasan or "").strip()[:500] or None}
    cols = ["_id", "field_id", "table_id", "column_name", "business_term", "data_type", "aksi", "oleh", "diubah_pada", "alasan"]
    tq.q(f"INSERT INTO {tq.fq(TABLE)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row


def added(tq) -> list[dict]:
    ensure(tq)
    cols = ["field_id", "table_id", "column_name", "business_term", "data_type", "oleh", "diubah_pada"]
    return [dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(
        f"SELECT {', '.join(cols)} FROM {tq.fq(TABLE)} WHERE aksi = 'tambah' ORDER BY diubah_pada")]
