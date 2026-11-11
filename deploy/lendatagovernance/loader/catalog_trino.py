#!/usr/bin/env python3
"""Sinkron katalog Len Data Governance dengan Trino lakehouse (lakekeeper.medallion_repository).

Katalog di stack ini tidak punya komponen ingestion (Airflow), jadi metadata didorong lewat API:
  layanan "Len Lakehouse (Trino)" › database lakekeeper › schema medallion_repository › semua tabel,
  dengan kolom + tipe + komentar dari Trino, dan jumlah baris (profil tabel) per waktu sinkron.
Tabel yang sudah tidak ada di Trino dihapus (soft delete) dari katalog. Metadata Workbook ERM yang dipasang
catalog_loader.py (blok deskripsi "Workbook ERM", tag Sensitivitas/glosarium, pemilik) dipertahankan.

Tujuan: admin bisa mencocokkan :8585 dengan DBeaver — daftar tabel, kolom, dan jumlah baris harus sama.
Dipanggil otomatis di akhir lakehouse.py (bila token ada); bisa juga manual:
  /home/ubuntu/data-governance/data/medallion/.venv/bin/python loader/catalog_trino.py
Butuh: LDG_TOKEN admin di /home/ubuntu/data-governance/data/secrets/loader.env, kredensial Trino di secrets/trino.env.
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "medallion")]
import workbook as W  # noqa: E402
from catalog_loader import Catalog, q  # noqa: E402

SERVICE = "len_lakehouse_trino"
WIB = timezone(timedelta(hours=7))


def catalog_type(t: str) -> dict:
    t = t.lower()
    m = re.match(r"decimal\((\d+),\s*(\d+)\)", t)
    if m:
        return {"dataType": "DECIMAL", "precision": int(m.group(1)), "scale": int(m.group(2)), "dataTypeDisplay": t}
    base = {"varchar": "STRING", "integer": "INT", "bigint": "BIGINT", "double": "DOUBLE", "real": "FLOAT", "boolean": "BOOLEAN",
            "date": "DATE", "smallint": "SMALLINT", "tinyint": "TINYINT"}
    if t.startswith("timestamp"):
        return {"dataType": "TIMESTAMPZ" if "time zone" in t else "TIMESTAMP", "dataTypeDisplay": t}
    if t.startswith("varchar"):
        return {"dataType": "STRING", "dataTypeDisplay": t}
    return {"dataType": base.get(t, "UNKNOWN"), "dataTypeDisplay": t}


def layer(name: str) -> str:
    return next((x for x in ("bronze", "silver", "gold") if name.startswith(x + "_")), "lain")


def main() -> None:
    from lakehouse import Trino  # kredensial & koneksi yang sama dengan loader
    tq = Trino()
    om = Catalog(dry=False)
    now = datetime.now(timezone.utc)
    stamp = now.astimezone(WIB).strftime("%Y-%m-%d %H:%M WIB")

    om.put("/v1/services/databaseServices", {
        "name": SERVICE, "displayName": "Len Lakehouse (Trino)", "serviceType": "Trino",
        "description": "Trino lakehouse Len (Iceberg/Lakekeeper) — sistem rekam data aplikasi Data Governance. "
                       "Metadata disinkronkan oleh loader/catalog_trino.py (tanpa komponen ingestion).",
        "connection": {"config": {"type": "Trino", "hostPort": f"{tq.conn.host}:{tq.conn.port}", "username": tq.conn.user,
                                  "catalog": tq.catalog}}})
    db = om.put("/v1/databases", {"name": tq.catalog, "service": SERVICE, "displayName": tq.catalog,
                                  "description": "Katalog Iceberg Lakekeeper di Trino datahub.len.co.id."})
    sch = om.put("/v1/databaseSchemas", {"name": tq.schema, "database": db["fullyQualifiedName"],
                                         "description": "Medallion Len Data Governance: bronze_* (mentah), silver_dim_*/silver_fact_* (bersih), "
                                                        "gold_* (siap dashboard). Definisi: deploy/lendatagovernance/medallion/schema/medallion_repository.sql"})
    cols = defaultdict_list()
    for t, c, dt, cm, pos in tq.q(
            f"SELECT c.table_name, c.column_name, c.data_type, c.comment, c.ordinal_position FROM information_schema.columns c "
            f"WHERE c.table_schema = '{tq.schema}' ORDER BY c.table_name, c.ordinal_position"):
        cols[t].append((c, dt, cm))
    tcomment = dict(tq.q(f"SELECT table_name, comment FROM system.metadata.table_comments "
                         f"WHERE catalog_name = '{tq.catalog}' AND schema_name = '{tq.schema}'"))
    names = sorted(cols)
    counts: dict[str, int | None] = {}
    for t in names:  # per tabel: satu tabel yang metadatanya rusak di Lakekeeper tidak menggagalkan semuanya
        try:
            counts[t] = tq.q(f"SELECT count(*) FROM {tq.fq(t)}", attempts=1)[0][0]
        except Exception as e:  # noqa: BLE001
            counts[t] = None
            print(f"  ! {t}: jumlah baris tidak terbaca ({str(e)[:100]})")
    for t in names:
        desc = (tcomment.get(t) or "").strip()
        n = f"**{counts[t]:,}**" if counts[t] is not None else "**tidak terbaca** (Lakekeeper gagal membaca metadata)"
        desc = (desc + "\n\n" if desc else "") + f"Lapisan **{layer(t)}**. Jumlah baris di Trino: {n} (sinkron {stamp})."
        cur = om.find(f"/v1/tables/name/{q(sch['fullyQualifiedName'] + '.' + t)}?fields=columns,tags,owners") or {}
        keep = {c["name"]: c for c in cur.get("columns", [])}   # pengayaan Workbook ERM (catalog_loader.py)

        def enrich(c: str, base: str | None) -> dict:
            k = keep.get(c, {})
            extra = (k.get("description") or "").partition(W.WORKBOOK_MARK)
            d = (base or "") + (extra[1] + extra[2] if extra[1] else "")
            tags = [{x: g[x] for x in ("tagFQN", "source", "labelType", "state") if x in g} for g in k.get("tags", [])]
            return {**({"description": d} if d else {}), **({"tags": tags} if tags else {})}

        wb = (cur.get("description") or "").partition(W.WORKBOOK_MARK)
        body = {"name": t, "databaseSchema": sch["fullyQualifiedName"], "tableType": "Iceberg",
                "description": desc + (wb[1] + wb[2] if wb[1] else ""),
                "columns": [{"name": c, **catalog_type(dt), **enrich(c, cm)} for c, dt, cm in cols[t]]}
        if cur.get("owners"):
            body["owners"] = [{"id": o["id"], "type": o["type"]} for o in cur["owners"]]
        tb = om.put("/v1/tables", body)
        sensitivity_tags(om, tb, cols[t])
        if counts[t] is not None:
            om.call("PUT", f"/v1/tables/{tb['id']}/tableProfile", {
                "tableProfile": {"timestamp": int(now.timestamp() * 1000), "rowCount": counts[t], "columnCount": len(cols[t])}})
    layer_governance(om, sch["fullyQualifiedName"], names)
    # tabel yang sudah hilang dari Trino → soft delete
    existing = om.get(f"/v1/tables?databaseSchema={q(sch['fullyQualifiedName'])}&limit=1000").get("data", [])
    gone = [x for x in existing if x["name"] not in cols]
    for x in gone:
        om.call("DELETE", f"/v1/tables/{x['id']}")
    print(f"Katalog ↔ Trino: {len(names)} tabel disinkron, {len(gone)} dihapus, {sum(v for v in counts.values() if v):,} baris, {sum(1 for v in counts.values() if v is None)} tak terbaca ({stamp})")


SENS = {"public": "Public", "restricted": "Restricted", "confidential": "Confidential", "strictly confidential": "StrictlyConfidential"}


def sensitivity_tags(om, tb: dict, tcols: list) -> None:
    """Komentar kolom "Sensitivitas: <level>" (skema medallion_repository.sql) → tag Sensitivitas.<level> di katalog.
    Tag Sensitivitas lain pada kolom itu diganti (klasifikasi saling eksklusif); tag lain (glosarium) dipertahankan."""
    want = {}
    for c, _, cm in tcols:
        m = re.search(r"Sensitivitas:\s*(Strictly Confidential|Confidential|Restricted|Public)", cm or "", re.I)
        if m:
            want[c] = f"{W.CLASSIFICATION}.{SENS[m.group(1).lower()]}"
    if not want:
        return
    cur = om.get(f"/v1/tables/{tb['id']}?fields=columns,tags")
    ops = []
    for i, c in enumerate(cur.get("columns", [])):
        if c["name"] not in want:
            continue
        tags = c.get("tags", [])
        if any(g["tagFQN"] == want[c["name"]] for g in tags):
            continue
        keep = [{k: g[k] for k in ("tagFQN", "source", "labelType", "state") if k in g}
                for g in tags if not g["tagFQN"].startswith(W.CLASSIFICATION + ".")]
        ops.append({"op": "add", "path": f"/columns/{i}/tags", "value": keep + [
            {"tagFQN": want[c["name"]], "source": "Classification", "labelType": "Manual", "state": "Confirmed"}]})
    if ops:
        om.patch(f"/v1/tables/{tb['id']}", ops)


LAYER_CLASS = "LapisanData"
LAYER_TAGS = [("Bronze", "Bronze (mentah)", "Salinan mentah berkas sumber. Hanya untuk pipeline dan Staf Data Governance."),
              ("Silver", "Silver (bersih)", "Data terstandar antar-lapisan. Hanya untuk pipeline dan Staf Data Governance."),
              ("Gold", "Gold (siap pakai)", "Data siap pakai untuk dashboard dan pengguna.")]
HIDE_POLICY, HIDE_ROLE = "SembunyikanLapisanMentah", "LapisanMentahTertutup"
STAFF_TEAM = "UV-1"   # Staf Data Governance — boleh melihat Bronze/Silver (selain admin & loader)


def layer_governance(om, sch_fqn: str, names: list) -> None:
    """Tag LapisanData.<Bronze|Silver|Gold> per tabel + kebijakan tolak-lihat Bronze/Silver bagi semua kecuali Staf DG.
    Admin melewati kebijakan, jadi loader (token admin) tidak terpengaruh. Kebijakan dipasang di tim Organization."""
    om.put("/v1/classifications", {"name": LAYER_CLASS, "displayName": "Lapisan Data", "mutuallyExclusive": True,
                                   "description": "Lapisan medallion tabel: Bronze, Silver, atau Gold."})
    for n, d, desc in LAYER_TAGS:
        om.put("/v1/tags", {"classification": LAYER_CLASS, "name": n, "displayName": d, "description": desc})
    for t in names:
        want = f"{LAYER_CLASS}.{layer(t).capitalize()}"
        if layer(t) == "lain":
            continue
        cur = om.get(f"/v1/tables/name/{q(sch_fqn + '.' + t)}?fields=tags")
        if any(g["tagFQN"] == want for g in cur.get("tags", [])):
            continue
        keep = [{k: g[k] for k in ("tagFQN", "source", "labelType", "state") if k in g}
                for g in cur.get("tags", []) if not g["tagFQN"].startswith(LAYER_CLASS + ".")]
        om.patch(f"/v1/tables/{cur['id']}", [{"op": "add", "path": "/tags", "value": keep + [
            {"tagFQN": want, "source": "Classification", "labelType": "Manual", "state": "Confirmed"}]}])
    pol = om.put("/v1/policies", {
        "name": HIDE_POLICY, "displayName": "Sembunyikan Bronze dan Silver",
        "description": "Pengguna biasa hanya melihat tabel Gold. Bronze dan Silver terlihat oleh admin dan anggota "
                       f"{STAFF_TEAM} (Staf Data Governance).",
        "rules": [{"name": "TolakLihatLapisanMentah", "effect": "deny", "resources": ["table"], "operations": ["All"],
                   "condition": f"matchAnyTag('{LAYER_CLASS}.Bronze','{LAYER_CLASS}.Silver') && !inAnyTeam('{STAFF_TEAM}')"}]})
    org = om.get("/v1/teams/name/Organization?fields=policies")
    if not any(x["id"] == pol["id"] for x in org.get("policies", [])):
        om.patch(f"/v1/teams/{org['id']}", [{"op": "add", "path": "/policies/-",
                                              "value": {"id": pol["id"], "type": "policy"}}])


def defaultdict_list():
    from collections import defaultdict
    return defaultdict(list)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"selesai dalam {time.time() - t0:.0f} detik")
