#!/usr/bin/env python3
"""Perubahan Business Dataset dari aplikasi (tambah / ubah). Tabel app_dataset (Trino), append-only.
Daftar = silver_dim_meta_dataset + perubahan aplikasi (perubahan menang untuk DATASET_ID yang sama)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

TABLE = "app_dataset"
FIELDS = ["dataset_name", "business_domain", "system_id"]
BASE_COLS = ["dataset_id", "dataset_name", "business_domain", "system_id", "system_name", "data_owner", "data_asset_status"]
ID_RE = re.compile(r"^DS\d{3}$")
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
  aksi varchar, oleh varchar, diubah_pada varchar, alasan varchar)
  WITH (format = 'PARQUET', format_version = 2)""")
    _ready = True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def latest_app(tq) -> dict[str, dict]:
    ensure(tq)
    cols = ["_id", "dataset_id", "dataset_name", "business_domain", "system_id", "aksi", "oleh", "diubah_pada", "alasan"]
    sql = (f"SELECT {', '.join(cols)} FROM (SELECT *, row_number() OVER (PARTITION BY dataset_id ORDER BY diubah_pada DESC, _id DESC) rn "
           f"FROM {tq.fq(TABLE)}) WHERE rn = 1")
    return {r[1]: dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def base(tq) -> dict[str, dict]:
    sql = (f"SELECT d.dataset_id, d.dataset_name, d.business_domain, d.system_id, d.system_name, d.data_owner, d.data_asset_status "
           f"FROM {tq.fq('silver_dim_meta_dataset')} d")
    return {r[0]: dict(zip(BASE_COLS, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def merged(tq) -> list[dict]:
    out = {k: {**r, "sumber": "Database"} for k, r in base(tq).items()}
    for k, a in latest_app(tq).items():
        if a["aksi"] == "hapus":          # soft delete: tidak tampil, riwayat tetap ada
            out.pop(k, None)
            continue
        cur = out.get(k, {c: None for c in BASE_COLS})
        out[k] = {**cur, "dataset_id": k, **{f: a[f] for f in FIELDS}, "sumber": "Aplikasi",
                  "diubah_oleh": a["oleh"], "diubah_pada": a["diubah_pada"]}
    return sorted(out.values(), key=lambda r: r["dataset_id"])


def validate(aksi: str, dataset_id: str | None, data: dict, current: dict[str, dict]) -> tuple[str, str]:
    if aksi not in AKSI:
        return "", "Aksi tidak dikenal."
    did = (dataset_id or "").strip().upper()
    if not ID_RE.match(did):
        return did, "DATASET_ID harus berbentuk seperti DS006."
    if aksi == "tambah" and did in current:
        return did, f"DATASET_ID {did} sudah ada."
    if aksi in ("ubah", "hapus") and did not in current:
        return did, f"DATASET_ID {did} tidak ditemukan."
    if aksi == "hapus":
        return did, ""
    if not (data.get("dataset_name") or "").strip():
        return did, "Nama dataset wajib diisi."
    if len((data.get("dataset_name") or "")) > 200 or len((data.get("business_domain") or "")) > 200:
        return did, "Isian terlalu panjang."
    return did, ""


def append(tq, aksi: str, dataset_id: str, data: dict, oleh: str, alasan: str | None) -> dict:
    ensure(tq)
    if aksi == "hapus":   # hapus = baris penanda; isi terakhir disalin agar riwayat tetap lengkap
        cur = latest_app(tq).get(dataset_id) or {}
        data = {"dataset_name": cur.get("dataset_name"), "business_domain": cur.get("business_domain"), "system_id": cur.get("system_id")}
        if not cur:
            b = base(tq).get(dataset_id) or {}
            data = {"dataset_name": b.get("dataset_name"), "business_domain": b.get("business_domain"), "system_id": b.get("system_id")}
    row = {"_id": uuid.uuid4().hex, "dataset_id": dataset_id, "dataset_name": (data.get("dataset_name") or "").strip() or None,
           "business_domain": (data.get("business_domain") or "").strip() or None,
           "system_id": (data.get("system_id") or "").strip().upper() or None,
           "aksi": aksi, "oleh": oleh, "diubah_pada": _now(), "alasan": (alasan or "").strip()[:500] or None}
    cols = ["_id", "dataset_id", "dataset_name", "business_domain", "system_id", "aksi", "oleh", "diubah_pada", "alasan"]
    tq.q(f"INSERT INTO {tq.fq(TABLE)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row
