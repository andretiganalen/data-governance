#!/usr/bin/env python3
"""Lima tingkat akses Len Data Governance (disetujui 2026-11-11), sisi katalog. Idempoten.

  1 Super Admin          isAdmin: hanya SUPER_ADMINS
  2 Admin Data Governance  tim UV-1 + peran AdminDataGovernance (kelola Fungsi dan Glosarium)
  3 Edit                 Owner (tim Fungsi FN_*) lewat Owner-Rule, dan peran DataSteward
  4 Unduh                anggota UV-1, tim "Pengunduh", atau tim Fungsi FN_* (ditegakkan di Visualisasi: superset/dg_sso.py)
  5 Lihat saja           semua anggota Organization lainnya: peran LihatSaja (lihat + ajukan permintaan, tanpa hak edit)

Akun admin lain (bukan SUPER_ADMINS) dipindah ke tingkat 2: masuk tim UV-1 lalu isAdmin dicabut (bisa dibalik kapan saja).
Pemetaan akun ke unit kerja dan Fungsi menunggu daftar HR/IDS (P3-3); sampai itu akun hanya berada di tim Organization.

  python access_levels.py            # terapkan
  python access_levels.py --dry      # hanya tampilkan rencana"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
import catalog_loader as C  # noqa: E402

SUPER_ADMINS = {"admin", "andre.tigana"}
STAFF_TEAM = "UV-1"
DOWNLOAD_TEAM = "Pengunduh"


def main() -> None:
    dry = "--dry" in sys.argv
    om = C.Catalog(dry=False)

    def put(path, body):
        if dry:
            print("  [dry] PUT", path, body.get("name"))
            return {"id": "dry", "fullyQualifiedName": body.get("name"), "name": body.get("name")}
        return om.put(path, body)

    # 5 Lihat saja: kebijakan + peran, menggantikan DataConsumer sebagai peran bawaan Organization
    pol = put("/v1/policies", {
        "name": "LihatSajaPolicy", "displayName": "Lihat saja",
        "description": "Melihat semua keterangan data dan mengajukan permintaan perbaikan; tanpa hak mengubah.",
        "rules": [{"name": "LihatSemua", "effect": "allow", "resources": ["All"], "operations": ["ViewAll"]},
                  {"name": "AjukanPermintaan", "effect": "allow", "resources": ["task"], "operations": ["Create"]},
                  {"name": "TanggapiPermintaan", "effect": "allow", "resources": ["All"], "operations": ["CreateTask", "EditTask"]}]})
    role = put("/v1/roles", {"name": "LihatSaja", "displayName": "Lihat saja",
                             "description": "Tingkat 5: lihat dan ajukan permintaan, tanpa hak edit.",
                             "policies": ["LihatSajaPolicy", "TaskAuthorPolicy"]})
    org = om.get("/v1/teams/name/Organization?fields=defaultRoles")
    cur = [r["name"] for r in org.get("defaultRoles", [])]
    print("Organization defaultRoles:", cur, "->", ["LihatSaja"])
    if not dry and cur != ["LihatSaja"]:
        om.patch(f"/v1/teams/{org['id']}", [{"op": "replace", "path": "/defaultRoles", "value": [{"id": role["id"], "type": "role"}]}])

    # 4 Unduh: tim Pengunduh (Group) di bawah Organization
    if not om.find(f"/v1/teams/name/{DOWNLOAD_TEAM}"):
        print("buat tim", DOWNLOAD_TEAM)
        put("/v1/teams", {"name": DOWNLOAD_TEAM, "displayName": "Pengunduh data", "teamType": "Group", "parents": [org["id"]],
                          "description": "Anggota boleh mengunduh data (CSV/Excel) dari menu Visualisasi. UV-1 dan semua tim Fungsi FN_* otomatis boleh."})

    # 1/2 admin: pindahkan selain SUPER_ADMINS ke Admin Data Governance
    staff = om.get(f"/v1/teams/name/{STAFF_TEAM}")
    after, users = "", []
    while True:
        r = om.get("/v1/users?limit=200&fields=teams,isAdmin" + after)
        users += r["data"]
        if not r.get("paging", {}).get("after"):
            break
        after = "&after=" + r["paging"]["after"]
    for u in users:
        if u.get("isBot") or not u.get("isAdmin") or u["name"] in SUPER_ADMINS:
            continue
        in_staff = any(t["id"] == staff["id"] for t in u.get("teams", []))
        print(f"turunkan {u['name']}: admin -> Admin Data Governance (UV-1{' sudah anggota' if in_staff else ''})")
        if dry:
            continue
        if not in_staff:
            om.patch(f"/v1/users/{u['id']}", [{"op": "add", "path": "/teams/-", "value": {"id": staff["id"], "type": "team"}}])
        om.patch(f"/v1/users/{u['id']}", [{"op": "replace", "path": "/isAdmin", "value": False}])
    print("selesai" + (" (dry)" if dry else ""))


if __name__ == "__main__":
    main()
