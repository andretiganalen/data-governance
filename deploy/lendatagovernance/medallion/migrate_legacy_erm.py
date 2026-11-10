#!/usr/bin/env python3
"""Pindahkan data ERM lama di Trino ke lakekeeper.medallion_repository, lalu hapus schema lamanya.

Sumber (pipeline ERM sebelum Len Data Governance, 2025-01 … 2026-10):
  lakekeeper.erm          iro (701 baris) + 2 view hitung (event_agg, orders_by_date)
  lakekeeper.erm_bronze   E-GRC mentah (8 tabel)
  lakekeeper.erm_silver   E-GRC bersih (7 tabel)
Tujuan: nama skeleton Inggris di medallion_repository (lihat MOVES). Data disalin apa adanya (CTAS), jumlah baris
dicocokkan, komentar tabel mencatat asal; baru setelah SEMUA cocok, tabel/view/schema lama di-DROP.

Aman diulang: tabel tujuan yang sudah ada dan jumlah barisnya sama tidak disalin lagi; schema yang sudah
hilang dilewati.  Pemakaian:  migrate_legacy_erm.py [--dry-run] [--keep-source]
"""
from __future__ import annotations

import sys
from datetime import date

import lakehouse as L

MOVES = {  # sumber → tabel tujuan di medallion_repository
    "erm.iro": "bronze_erm_iro",
    "erm_bronze.ingest_file_registry": "bronze_erm_ingest_file_registry",
    "erm_bronze.pengendalian_risiko": "bronze_erm_risk_control",
    "erm_bronze.risk_profile": "bronze_erm_risk_profile",
    "erm_bronze.risk_register": "bronze_erm_risk_register",
    "erm_bronze.risk_strategy_matrix": "bronze_erm_risk_strategy_matrix",
    "erm_bronze.trigger_matriks_level": "bronze_erm_trigger_level_matrix",
    "erm_bronze.trigger_matriks_skor": "bronze_erm_trigger_score_matrix",
    "erm_bronze.trigger_skala_level": "bronze_erm_trigger_scale_level",
    "erm_silver.matriks_level": "silver_dim_erm_risk_level_matrix",
    "erm_silver.matriks_skor": "silver_dim_erm_risk_score_matrix",
    "erm_silver.risk_level_reference": "silver_dim_erm_risk_level_reference",
    "erm_silver.pengendalian_risiko": "silver_fact_erm_risk_control_monthly",
    "erm_silver.risk_profile": "silver_fact_erm_risk_profile_monthly",
    "erm_silver.risk_register": "silver_fact_erm_risk_register_monthly",
    "erm_silver.risk_strategy_matrix": "silver_fact_erm_risk_strategy_matrix",
}
# View lama (definisinya tidak bisa dibaca pengguna loader; keduanya = count(*) dari erm.iro, diverifikasi sama)
VIEWS = {
    "erm.event_agg": ("gold_erm_iro_event_count", "event_count"),
    "erm.orders_by_date": ("gold_erm_iro_row_count", "count_iro"),
}
SCHEMAS = ["erm", "erm_bronze", "erm_silver"]


def main() -> None:
    dry, keep = "--dry-run" in sys.argv, "--keep-source" in sys.argv
    tq = L.Trino()
    cat, dst = tq.catalog, tq.schema
    have = {r[0] for r in tq.q(f"SHOW SCHEMAS FROM {cat}")}
    todo = {s: d for s, d in MOVES.items() if s.split(".")[0] in have}
    if not todo:
        L.log("Schema erm/erm_bronze/erm_silver sudah tidak ada — tidak ada yang dipindah.")
        return
    live = set(tq.tables())
    ok = True
    for src, d in todo.items():
        n_src = tq.q(f"SELECT count(*) FROM {cat}.{src}")[0][0]
        if d in live and tq.q(f"SELECT count(*) FROM {tq.fq(d)}")[0][0] == n_src:
            L.log(f"  = {src:40s} → {d:42s} {n_src:6d} baris (sudah ada)")
            continue
        L.log(f"  + {src:40s} → {d:42s} {n_src:6d} baris" + (" [dry-run]" if dry else ""))
        if dry:
            continue
        if d in live:
            tq.q(f"DROP TABLE {tq.fq(d)}")
        tq.q(f"CREATE TABLE {tq.fq(d)} WITH (format = 'PARQUET', format_version = 2) AS SELECT * FROM {cat}.{src}")
        tq.q(f"COMMENT ON TABLE {tq.fq(d)} IS "
             + L.sq(f"Data ERM lama, dipindah dari {cat}.{src} pada {date.today().isoformat()} (apa adanya)."))
        n_dst = tq.q(f"SELECT count(*) FROM {tq.fq(d)}")[0][0]
        if n_dst != n_src:
            ok = False
            L.log(f"    ! jumlah baris beda: {n_src} → {n_dst}")
    for src, (d, col) in VIEWS.items():
        if src.split(".")[0] not in have:
            continue
        L.log(f"  + view {src:35s} → {d}" + (" [dry-run]" if dry else ""))
        if not dry:
            tq.q(f"CREATE OR REPLACE VIEW {tq.fq(d)} COMMENT "
                 + L.sq(f"Pengganti view {cat}.{src}: jumlah baris bronze_erm_iro.")
                 + f" AS SELECT count(*) AS {col} FROM {tq.fq('bronze_erm_iro')}")
            if tq.q(f"SELECT {col} FROM {tq.fq(d)}")[0][0] != tq.q(f"SELECT * FROM {cat}.{src}")[0][0]:
                ok = False
                L.log(f"    ! nilai view beda dengan {src}")
    if dry or keep or not ok:
        L.log("Sumber TIDAK dihapus" + (" (ada selisih)" if not ok else "") + ".")
        return
    for src in VIEWS:
        if src.split(".")[0] in have:
            tq.q(f"DROP VIEW IF EXISTS {cat}.{src}")
    for src in todo:
        tq.q(f"DROP TABLE IF EXISTS {cat}.{src}")
    for s in SCHEMAS:
        if s in have:
            left = tq.q(f"SHOW TABLES FROM {cat}.{s}")
            if left:
                L.log(f"  ! {cat}.{s} masih berisi {[r[0] for r in left]} — schema tidak dihapus")
            else:
                tq.q(f"DROP SCHEMA {cat}.{s}")
                L.log(f"  - schema {cat}.{s} dihapus")


if __name__ == "__main__":
    main()
