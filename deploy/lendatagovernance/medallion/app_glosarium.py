#!/usr/bin/env python3
"""Definisi Business Glossary dari aplikasi (isi / ubah definisi). Tabel app_glosarium (Trino), append-only.
Daftar = gold_meta_glossary_app + definisi terbaru dari aplikasi (perubahan menang untuk FIELD_ID yang sama)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

TABLE = "app_glosarium"
_ready = False
FID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def _sq(v) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def ensure(tq) -> None:
    global _ready
    if _ready:
        return
    tq.q(f"""CREATE TABLE IF NOT EXISTS {tq.fq(TABLE)} (
  _id varchar, field_id varchar, definisi varchar, aksi varchar, oleh varchar, diubah_pada varchar, alasan varchar)
  WITH (format = 'PARQUET', format_version = 2)""")
    _ready = True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def latest_app(tq) -> dict[str, dict]:
    ensure(tq)
    cols = ["_id", "field_id", "definisi", "aksi", "oleh", "diubah_pada", "alasan"]
    sql = (f"SELECT {', '.join(cols)} FROM (SELECT *, row_number() OVER (PARTITION BY field_id ORDER BY diubah_pada DESC, _id DESC) rn "
           f"FROM {tq.fq(TABLE)}) WHERE rn = 1")
    return {r[1]: dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def validate(field_id: str | None, definisi: str | None, current: set[str]) -> tuple[str, str]:
    fid = (field_id or "").strip()
    if not FID_RE.match(fid) or fid not in current:
        return fid, "FIELD_ID tidak dikenal."
    d = (definisi or "").strip()
    if len(d) < 10:
        return fid, "Definisi terlalu pendek. Tulis minimal satu kalimat yang jelas."
    if len(d) > 2000:
        return fid, "Definisi terlalu panjang (maksimal 2000 karakter)."
    return fid, ""


def append(tq, field_id: str, definisi: str, oleh: str, alasan: str | None) -> dict:
    ensure(tq)
    row = {"_id": uuid.uuid4().hex, "field_id": field_id, "definisi": definisi.strip(), "aksi": "isi",
           "oleh": oleh, "diubah_pada": _now(), "alasan": (alasan or "").strip()[:500] or None}
    cols = ["_id", "field_id", "definisi", "aksi", "oleh", "diubah_pada", "alasan"]
    tq.q(f"INSERT INTO {tq.fq(TABLE)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row
