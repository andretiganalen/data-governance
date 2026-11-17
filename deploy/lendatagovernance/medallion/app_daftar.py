#!/usr/bin/env python3
"""Tambah untuk layar Tata kelola dan Akses (append-only, satu tabel app_<kunci> per layar).
ID otomatis: prefiks + nomor berikutnya dari tabel aplikasi dan sumber dasar."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

SPEC = {
    "assignment": {"table": "app_assignment", "id": None, "base": None, "req": ["field_id", "role", "org_id"],
                   "cols": ["field_id", "role", "org_id"]},
    "kualitas": {"table": "app_kualitas", "id": ("dq_rule_id", "DQR"), "base": ("silver_dim_meta_dq_rule", "dq_rule_id"),
                 "req": ["field_id", "rule", "validation"], "cols": ["field_id", "rule", "validation"]},
    "lineage": {"table": "app_lineage", "id": ("lineage_id", "L"), "base": ("gold_meta_lineage", "lineage_id"),
                "req": ["field_id", "target_label", "asset_type"], "cols": ["field_id", "target_label", "asset_type"]},
    "akses": {"table": "app_akses", "id": ("access_id", "A"), "base": ("gold_meta_access_matrix", "access_id"),
              "req": ["field_id", "org_id", "classification", "permission_category", "permission_type"],
              "cols": ["field_id", "org_id", "classification", "permission_category", "permission_type"]},
}
ROLES = ("Data Owner", "Data Steward", "Data User")
_ready: set[str] = set()


def _sq(v) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def ensure(tq, key: str) -> str:
    sp = SPEC[key]
    if key not in _ready:
        idc = [sp["id"][0]] if sp["id"] else []
        cols = ["_id"] + idc + sp["cols"] + ["aksi", "oleh", "diubah_pada", "alasan"]
        tq.q(f"CREATE TABLE IF NOT EXISTS {tq.fq(sp['table'])} ({', '.join(c + ' varchar' for c in cols)}) WITH (format = 'PARQUET', format_version = 2)")
        _ready.add(key)
    return sp["table"]


def next_id(tq, key: str) -> str | None:
    sp = SPEC[key]
    if not sp["id"]:
        return None
    col, pre = sp["id"]
    nums = []
    for tbl, c in ([(sp["table"], col)] + ([sp["base"]] if sp["base"] else [])):
        for (v,) in tq.q(f"SELECT {c} FROM {tq.fq(tbl)}"):
            m = re.search(r"(\d+)$", str(v or ""))
            if m:
                nums.append(int(m.group(1)))
    return f"{pre}{(max(nums) if nums else 0) + 1:03d}"


def validate(key: str, data: dict, options: dict[str, set[str]]) -> str:
    sp = SPEC[key]
    for f in sp["req"]:
        if not str(data.get(f) or "").strip():
            return f"Isian {f.replace('_', ' ')} wajib diisi."
        if len(str(data.get(f))) > 200:
            return "Isian terlalu panjang."
    for f, allowed in options.items():
        if data.get(f) not in allowed:
            return f"Pilihan {f.replace('_', ' ')} tidak dikenal."
    if key == "assignment" and data.get("role") not in ROLES:
        return "Peran tidak dikenal."
    return ""


def append(tq, key: str, data: dict, oleh: str, alasan: str | None) -> dict:
    tbl = ensure(tq, key)
    sp = SPEC[key]
    row = {"_id": uuid.uuid4().hex}
    if sp["id"]:
        row[sp["id"][0]] = next_id(tq, key)
    for c in sp["cols"]:
        row[c] = str(data.get(c) or "").strip() or None
    row.update({"aksi": "tambah", "oleh": oleh, "diubah_pada": _now(), "alasan": (alasan or "").strip()[:500] or None})
    cols = list(row.keys())
    tq.q(f"INSERT INTO {tq.fq(tbl)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row


def added(tq, key: str) -> list[dict]:
    tbl = ensure(tq, key)
    sp = SPEC[key]
    cols = ([sp["id"][0]] if sp["id"] else []) + sp["cols"] + ["oleh", "diubah_pada"]
    return [dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(
        f"SELECT {', '.join(cols)} FROM {tq.fq(tbl)} WHERE aksi = 'tambah' ORDER BY diubah_pada")]
