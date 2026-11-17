#!/usr/bin/env python3
"""Perubahan Master Sistem dari aplikasi (tambah / ubah). Tabel app_sistem (Trino), append-only seperti app_organisasi.
Daftar yang tampil = silver_dim_meta_system + perubahan aplikasi (perubahan menang untuk SYSTEM_ID yang sama)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

TABLE = "app_sistem"
FIELDS = ["system_name", "description"]
BASE_COLS = ["system_id", "system_name", "description", "data_owner", "business_owner", "database_platform", "dm_assessment_status"]
ID_RE = re.compile(r"^SYS\d{3}$")
AKSI = ("tambah", "ubah")
_ready = False


def _sq(v) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def ensure(tq) -> None:
    global _ready
    if _ready:
        return
    tq.q(f"""CREATE TABLE IF NOT EXISTS {tq.fq(TABLE)} (
  _id varchar, system_id varchar, system_name varchar, description varchar, aksi varchar,
  oleh varchar, diubah_pada varchar, alasan varchar)
  WITH (format = 'PARQUET', format_version = 2)""")
    _ready = True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def latest_app(tq) -> dict[str, dict]:
    ensure(tq)
    cols = ["_id", "system_id", "system_name", "description", "aksi", "oleh", "diubah_pada", "alasan"]
    sql = (f"SELECT {', '.join(cols)} FROM (SELECT *, row_number() OVER (PARTITION BY system_id ORDER BY diubah_pada DESC, _id DESC) rn "
           f"FROM {tq.fq(TABLE)}) WHERE rn = 1")
    return {r[1]: dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def base(tq) -> dict[str, dict]:
    sql = f"SELECT {', '.join(BASE_COLS)} FROM {tq.fq('silver_dim_meta_system')}"
    return {r[0]: dict(zip(BASE_COLS, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def merged(tq) -> list[dict]:
    out = {k: {**r, "sumber": "Database"} for k, r in base(tq).items()}
    for k, a in latest_app(tq).items():
        cur = out.get(k, {c: None for c in BASE_COLS})
        out[k] = {**cur, "system_id": k, **{f: a[f] for f in FIELDS}, "sumber": "Aplikasi",
                  "diubah_oleh": a["oleh"], "diubah_pada": a["diubah_pada"]}
    return sorted(out.values(), key=lambda r: r["system_id"])


def validate(aksi: str, system_id: str | None, data: dict, current: dict[str, dict]) -> tuple[str, str]:
    if aksi not in AKSI:
        return "", "Aksi tidak dikenal."
    sid = (system_id or "").strip().upper()
    if not ID_RE.match(sid):
        return sid, "SYSTEM_ID harus berbentuk seperti SYS002."
    if aksi == "tambah" and sid in current:
        return sid, f"SYSTEM_ID {sid} sudah ada."
    if aksi == "ubah" and sid not in current:
        return sid, f"SYSTEM_ID {sid} tidak ditemukan."
    name = (data.get("system_name") or "").strip()
    if not name:
        return sid, "Nama sistem wajib diisi."
    if len(name) > 200 or len((data.get("description") or "")) > 1000:
        return sid, "Isian terlalu panjang."
    return sid, ""


def append(tq, aksi: str, system_id: str, data: dict, oleh: str, alasan: str | None) -> dict:
    ensure(tq)
    row = {"_id": uuid.uuid4().hex, "system_id": system_id, "system_name": (data.get("system_name") or "").strip(),
           "description": (data.get("description") or "").strip() or None, "aksi": aksi, "oleh": oleh,
           "diubah_pada": _now(), "alasan": (alasan or "").strip()[:500] or None}
    cols = ["_id", "system_id", "system_name", "description", "aksi", "oleh", "diubah_pada", "alasan"]
    tq.q(f"INSERT INTO {tq.fq(TABLE)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row
