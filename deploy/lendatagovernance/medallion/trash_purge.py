#!/usr/bin/env python3
"""Tempat Sampah: hapus PERMANEN entitas katalog yang sudah di Tempat Sampah (soft delete) lebih dari RETENTION_DAYS hari.

Aturan (2026-11-11, keputusan pemilik): data yang dihapus pengguna disimpan 20 hari di Tempat Sampah dan bisa dipulihkan
(gateway mengubah hardDelete=true dari klien jaringan menjadi soft delete). Skrip ini jalan di server (timer harian) dan
satu-satunya yang boleh menghapus permanen. Usia dihitung dari updatedAt entitas terhapus (waktu dihapus).

  python trash_purge.py --dry     # hanya tampilkan yang akan dihapus permanen
  python trash_purge.py           # hapus permanen
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "loader")]
import catalog_loader as C  # noqa: E402

RETENTION_DAYS = 20
# Urutan: anak sebelum induk agar hapus rekursif tidak menghapus anak yang masih ditunggu.
TYPES = ["glossaryTerms", "glossaries", "tables", "databaseSchemas", "databases", "dashboards", "charts", "pipelines", "topics",
         "containers", "mlmodels", "storedProcedures", "searchIndexes", "dataProducts", "domains", "tags", "classifications", "teams"]


def call(method: str, path: str, token: str):
    req = urllib.request.Request(C.API_URL + path, method=method, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--days", type=int, default=RETENTION_DAYS)
    a = ap.parse_args()
    token = C.load_token()
    cutoff = (time.time() - a.days * 86400) * 1000
    purged = kept = errors = 0
    for typ in TYPES:
        after = ""
        while True:
            code, r = call("GET", f"/v1/{typ}?include=deleted&limit=200&fields=deleted{after}", token)
            if code != 200:
                break  # jenis tidak tersedia di versi ini
            for e in r.get("data", []):
                if not e.get("deleted"):
                    continue
                name = e.get("fullyQualifiedName") or e["name"]
                age = (time.time() * 1000 - (e.get("updatedAt") or 0)) / 86400000
                if e.get("updatedAt", 0) > cutoff:
                    kept += 1
                    continue
                if a.dry:
                    print(f"[dry] {typ}: {name} ({age:.0f} hari di Tempat Sampah) -> hapus permanen")
                    purged += 1
                    continue
                c, _ = call("DELETE", f"/v1/{typ}/{e['id']}?hardDelete=true&recursive=true", token)
                if c in (200, 204):
                    print(f"dihapus permanen: {typ}: {name} ({age:.0f} hari)")
                    purged += 1
                else:
                    print(f"GAGAL ({c}): {typ}: {name}")
                    errors += 1
            nxt = r.get("paging", {}).get("after")
            if not nxt:
                break
            after = "&after=" + nxt
    print(f"Tempat Sampah: {purged} {'akan ' if a.dry else ''}dihapus permanen (> {a.days} hari), {kept} masih disimpan, {errors} gagal")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
