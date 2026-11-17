#!/usr/bin/env python3
"""Business Dataset dari aplikasi (tambah / ubah / hapus). Tabel app_dataset (Trino), append-only.
DATASET_ID otomatis (DS###). Daftar = silver_dim_meta_dataset + perubahan aplikasi (perubahan menang)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

TABLE = "app_dataset"
FIELDS = ["dataset_name", "business_domain", "system_id", "database_name"]
BASE_COLS = ["dataset_id", "dataset_name", "business_domain", "system_id", "system_name", "data_owner", "data_asset_status"]
AKSI = ("tambah", "ubah", "hapus")
_ready = False


def _sq(v) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def ensure(tq) -> None:
    global _ready
    if _ready:
        return
    tq.q(f"""CREATE TABLE IF NOT EXISTS {tq.fq(TABLE)} (
  _id varchar, dataset_id varchar, dataset_name varchar, business_domain varchar, system_id varchar,
  database_name varchar, aksi varchar, oleh varchar, diubah_pada varchar, alasan varchar)
  WITH (format = 'PARQUET', format_version = 2)""")
    tq.q(f"ALTER TABLE {tq.fq(TABLE)} ADD COLUMN IF NOT EXISTS database_name varchar")
    _ready = True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def latest_app(tq) -> dict[str, dict]:
    ensure(tq)
    cols = ["_id", "dataset_id", "dataset_name", "business_domain", "system_id", "database_name", "aksi", "oleh", "diubah_pada", "alasan"]
    sql = (f"SELECT {', '.join(cols)} FROM (SELECT *, row_number() OVER (PARTITION BY dataset_id ORDER BY diubah_pada DESC, _id DESC) rn "
           f"FROM {tq.fq(TABLE)}) WHERE rn = 1")
    return {r[1]: dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def base(tq) -> dict[str, dict]:
    sql = (f"SELECT d.dataset_id, d.dataset_name, d.business_domain, d.system_id, d.system_name, d.data_owner, d.data_asset_status "
           f"FROM {tq.fq('silver_dim_meta_dataset')} d")
    return {r[0]: dict(zip(BASE_COLS, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def merged(tq) -> list[dict]:
    out = {k: {**r, "sumber": "Database", "database_name": None} for k, r in base(tq).items()}
    for k, a in latest_app(tq).items():
        if a["aksi"] == "hapus":
            out.pop(k, None)
            continue
        cur = out.get(k, {c: None for c in BASE_COLS})
        out[k] = {**cur, "dataset_id": k, **{f: a[f] for f in FIELDS}, "sumber": "Aplikasi",
                  "diubah_oleh": a["oleh"], "diubah_pada": a["diubah_pada"]}
    return sorted(out.values(), key=lambda r: r["dataset_id"])


def next_id(tq) -> str:
    nums = []
    for k in list(base(tq).keys()) + list(latest_app(tq).keys()):
        m = re.search(r"(\d+)$", k)
        if m:
            nums.append(int(m.group(1)))
    return f"DS{(max(nums) if nums else 0) + 1:03d}"


def validate(aksi: str, dataset_id: str | None, data: dict, current: dict[str, dict], systems: set[str], dbs: set[str]) -> tuple[str, str]:
    if aksi not in AKSI:
        return "", "Aksi tidak dikenal."
    did = (dataset_id or "").strip().upper()
    if aksi in ("ubah", "hapus") and did not in current:
        return did, f"DATASET_ID {did} tidak ditemukan."
    if aksi == "hapus":
        return did, ""
    if aksi == "tambah":
        did = "PENDING"   # ID dibuat di append()
    if not (data.get("dataset_name") or "").strip():
        return did, "Business dataset wajib diisi."
    if not (data.get("business_domain") or "").strip():
        return did, "Business domain wajib diisi."
    sid = (data.get("system_id") or "").strip().upper()
    if sid and sid not in systems:
        return did, "SYSTEM_ID tidak dikenal. Pilih dari Master System."
    if (data.get("database_name") or "").strip() and data["database_name"].strip() not in dbs:
        return did, "Nama database tidak dikenal."
    if len(data.get("dataset_name") or "") > 200 or len(data.get("business_domain") or "") > 200:
        return did, "Isian terlalu panjang."
    return did, ""


def append(tq, aksi: str, dataset_id: str, data: dict, oleh: str, alasan: str | None) -> dict:
    ensure(tq)
    if aksi == "tambah":
        dataset_id = next_id(tq)
    if aksi == "hapus":
        cur = latest_app(tq).get(dataset_id) or base(tq).get(dataset_id) or {}
        data = {f: cur.get(f) for f in FIELDS}
    sid = (data.get("system_id") or "").strip().upper() or None
    row = {"_id": uuid.uuid4().hex, "dataset_id": dataset_id, "dataset_name": (data.get("dataset_name") or "").strip() or None,
           "business_domain": (data.get("business_domain") or "").strip() or None, "system_id": sid,
           "database_name": (data.get("database_name") or "").strip() or None,
           "aksi": aksi, "oleh": oleh, "diubah_pada": _now(), "alasan": (alasan or "").strip()[:500] or None}
    cols = ["_id", "dataset_id", "dataset_name", "business_domain", "system_id", "database_name", "aksi", "oleh", "diubah_pada", "alasan"]
    tq.q(f"INSERT INTO {tq.fq(TABLE)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row
