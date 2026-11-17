#!/usr/bin/env python3
"""Perubahan Master Organisasi dari aplikasi (tambah / ubah / hapus).

Tabel: <katalog>.<skema>.app_organisasi (Trino, dimiliki aplikasi; loader workbook tidak menyentuhnya).
Model append-only: setiap perubahan menjadi baris baru (aksi, oleh, diubah_pada, alasan). Keadaan terkini per ORG_ID
= baris terakhir; aksi = 'hapus' berarti unit tidak tampil (soft delete, riwayat tetap ada).
Daftar yang tampil = silver_dim_organization (versi berlaku, sumber Excel ERM) + perubahan aplikasi (perubahan menang).

Hanya Admin Data Governance (isAdmin atau tim UV-1) yang boleh menulis; validasi dilakukan di export_server.py.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

TABLE = "app_organisasi"
FIELDS = ["fungsi", "unit_kerja", "divisi", "direktorat"]
BASE_COLS = ["org_id", "fungsi", "unit_kerja", "divisi", "direktorat", "company_id"]
ORG_RE = re.compile(r"^[A-Z]{2}-\d+$")
AKSI = ("tambah", "ubah", "hapus")

_ready = False


def _sq(v) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def ensure(tq) -> None:
    global _ready
    if _ready:
        return
    tq.q(f"""CREATE TABLE IF NOT EXISTS {tq.fq(TABLE)} (
  _id varchar, org_id varchar, fungsi varchar, unit_kerja varchar, divisi varchar, direktorat varchar,
  company_id varchar, aksi varchar, oleh varchar, diubah_pada varchar, alasan varchar)
  WITH (format = 'PARQUET', format_version = 2)""")
    _ready = True


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def latest_app(tq) -> dict[str, dict]:
    """ORG_ID → baris terakhir dari perubahan aplikasi."""
    ensure(tq)
    cols = ["_id", "org_id", "fungsi", "unit_kerja", "divisi", "direktorat", "company_id", "aksi", "oleh", "diubah_pada", "alasan"]
    sql = (f"SELECT {', '.join(cols)} FROM (SELECT *, row_number() OVER (PARTITION BY org_id ORDER BY diubah_pada DESC, _id DESC) rn "
           f"FROM {tq.fq(TABLE)}) WHERE rn = 1")
    return {r[1]: dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def base(tq) -> dict[str, dict]:
    cols = BASE_COLS
    sql = f"SELECT {', '.join(cols)} FROM {tq.fq('silver_dim_organization')} WHERE is_current"
    return {r[0]: dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(sql)}


def merged(tq) -> list[dict]:
    b = base(tq)
    app = latest_app(tq)
    out = {}
    for k, r in b.items():
        out[k] = {**r, "sumber": "Database"}
    for k, a in app.items():
        if a["aksi"] == "hapus":
            out.pop(k, None)
            continue
        cur = out.get(k, {"org_id": k, "company_id": None})
        out[k] = {**cur, **{f: a[f] for f in FIELDS}, "sumber": "Aplikasi", "diubah_oleh": a["oleh"], "diubah_pada": a["diubah_pada"]}
    return sorted(out.values(), key=lambda r: ((r.get("direktorat") or ""), (r.get("divisi") or ""), r["org_id"]))


def validate(aksi: str, org_id: str | None, data: dict, current: dict[str, dict]) -> tuple[str, str]:
    """→ (org_id ternormalisasi, pesan galat kosong bila valid)."""
    if aksi not in AKSI:
        return "", "Aksi tidak dikenal."
    oid = (org_id or "").strip().upper()
    if not ORG_RE.match(oid):
        return oid, "ORG_ID harus berbentuk seperti UD-1."
    if aksi == "tambah" and oid in current:
        return oid, f"ORG_ID {oid} sudah ada."
    if aksi in ("ubah", "hapus") and oid not in current:
        return oid, f"ORG_ID {oid} tidak ditemukan."
    if aksi in ("tambah", "ubah"):
        for f in FIELDS:
            v = (data.get(f) or "").strip()
            if not v:
                return oid, f"Kolom {f.replace('_', ' ')} wajib diisi."
            if len(v) > 200:
                return oid, f"Kolom {f.replace('_', ' ')} terlalu panjang."
    return oid, ""


def append(tq, aksi: str, org_id: str, data: dict, oleh: str, alasan: str | None, current: dict[str, dict]) -> dict:
    ensure(tq)
    prev = current.get(org_id) or {}
    vals = {f: ((data.get(f) or "").strip() or None) if aksi != "hapus" else prev.get(f) for f in FIELDS}
    row = {"_id": uuid.uuid4().hex, "org_id": org_id, **vals, "company_id": prev.get("company_id"),
           "aksi": aksi, "oleh": oleh, "diubah_pada": _now(), "alasan": (alasan or "").strip()[:500] or None}
    cols = ["_id", "org_id", "fungsi", "unit_kerja", "divisi", "direktorat", "company_id", "aksi", "oleh", "diubah_pada", "alasan"]
    tq.q(f"INSERT INTO {tq.fq(TABLE)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row
