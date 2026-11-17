#!/usr/bin/env python3
"""Definisi Business Glossary dari aplikasi (isi / ubah / hapus definisi). Tabel app_glosarium (Trino), append-only.
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


# Cek kualitas definisi (sama dengan artifact "Business Glossary"): 2 syarat Wajib, 4 Saran.
MIN_LEN, MAX_LEN, HARD_MAX = 10, 500, 4000
STARTERS = ("kategori yang menunjukkan", "pilihan yang menentukan", "uraian mengenai", "keterangan yang menjelaskan",
            "nilai angka yang menunjukkan", "nilai dalam rupiah yang menunjukkan", "persentase yang menunjukkan",
            "tanggal saat", "waktu saat", "penanda apakah", "dokumen pendukung yang", "nilai yang menunjukkan")


def template_only(d: str) -> bool:
    low = d.strip().lower()
    return any(low.startswith(st) and len(low) - len(st) < 10 for st in STARTERS)


def validate(field_id: str | None, definisi: str | None, current: set[str], aksi: str = "isi") -> tuple[str, str]:
    """Hanya syarat Wajib yang menolak simpan; Saran tidak menghalangi."""
    fid = (field_id or "").strip()
    if not FID_RE.match(fid) or fid not in current:
        return fid, "FIELD_ID tidak dikenal."
    if aksi == "hapus":
        return fid, ""
    d = (definisi or "").strip()
    if not d:
        return fid, "Isi definisi terlebih dahulu."
    if template_only(d):
        return fid, "Lengkapi kalimat setelah awalan template."
    if len(d) < MIN_LEN:
        return fid, "Ditulis dalam kalimat lengkap, minimal 10 karakter."
    if len(d) > HARD_MAX:   # > 500 hanya peringatan (oranye) di layar; batas keras untuk melindungi tabel
        return fid, "Definisi terlalu panjang (maksimal 4000 karakter)."
    return fid, ""


def append(tq, field_id: str, definisi: str | None, oleh: str, alasan: str | None, aksi: str = "isi") -> dict:
    """aksi isi = isi/ubah definisi; aksi hapus = definisi dikosongkan (FIELD_ID tetap ada di Data Element)."""
    ensure(tq)
    row = {"_id": uuid.uuid4().hex, "field_id": field_id, "definisi": None if aksi == "hapus" else (definisi or "").strip(), "aksi": aksi,
           "oleh": oleh, "diubah_pada": _now(), "alasan": (alasan or "").strip()[:500] or None}
    cols = ["_id", "field_id", "definisi", "aksi", "oleh", "diubah_pada", "alasan"]
    tq.q(f"INSERT INTO {tq.fq(TABLE)} ({', '.join(cols)}) VALUES ({', '.join(_sq(row[c]) for c in cols)})")
    return row
