#!/usr/bin/env python3
"""Pindahkan schema lama lakekeeper.medallion (prototipe 2026-11-02: SDM + korporasi) ke medallion_repository.

Semua 16 tabel lama menjadi tabel Bronze apa adanya (CTAS) di medallion_repository; Silver/Gold SDM dan korporasi
lalu dibangun ulang oleh medallion/sdm.py dari Bronze ini (kerangka SDM). Jumlah baris dicocokkan; baru setelah
SEMUA cocok, tabel dan schema lama di-DROP.

Aman diulang. Pemakaian:  migrate_legacy_medallion.py [--dry-run] [--keep-source]
"""
from __future__ import annotations

import sys
from datetime import date

import lakehouse as L

SRC_SCHEMA = "medallion"
MOVES = {  # tabel lama → Bronze di medallion_repository
    "bronze_dashboard_demografi_karyawan": "bronze_sdm_dashboard_demografi_karyawan",
    "bronze_251112_dashboard_demografi_karyawan": "bronze_sdm_dashboard_demografi_karyawan_251112",
    "bronze_261002_dashboard_demografi_karyawan": "bronze_sdm_dashboard_demografi_karyawan_261002",
    "bronze_demografi_karyawan": "bronze_sdm_demografi_karyawan",
    "silver_dim_employee_information": "bronze_sdm_employee_information",
    "silver_dim_employee_certification_information": "bronze_sdm_employee_certification",
    "bronze_dashboard_lainnya": "bronze_corp_dashboard_lainnya",
    "bronze_dashboard_performa_korporasi_defend": "bronze_corp_dashboard_performa_korporasi_defend",
    "bronze_dashboard_performa_korporasi_len_inc": "bronze_corp_dashboard_performa_korporasi_len_inc",
    "bronze_data_realisasi_len_inc": "bronze_corp_data_realisasi_len_inc",
    "bronze_data_roic": "bronze_corp_data_roic",
    "bronze_data_utang": "bronze_corp_data_utang",
    "silver_dim_company_information": "bronze_corp_company_information",
    "silver_fact_company_investasi": "bronze_corp_company_investment",
    "silver_fact_company_pajak": "bronze_corp_company_tax",
    "bronze_repository": "bronze_legacy_medallion_repository",
}


def main() -> None:
    dry, keep = "--dry-run" in sys.argv, "--keep-source" in sys.argv
    tq = L.Trino()
    cat = tq.catalog
    if SRC_SCHEMA not in {r[0] for r in tq.q(f"SHOW SCHEMAS FROM {cat}")}:
        L.log(f"Schema {cat}.{SRC_SCHEMA} sudah tidak ada — tidak ada yang dipindah.")
        return
    have = {r[0] for r in tq.q(f"SHOW TABLES FROM {cat}.{SRC_SCHEMA}")}
    unknown = have - set(MOVES)
    if unknown:
        raise SystemExit(f"Tabel tak terpetakan di {cat}.{SRC_SCHEMA}: {sorted(unknown)} — perbarui MOVES dulu.")
    live, ok = set(tq.tables()), True
    for src, d in MOVES.items():
        if src not in have:
            continue
        n_src = tq.q(f"SELECT count(*) FROM {cat}.{SRC_SCHEMA}.{src}")[0][0]
        if d in live and tq.q(f"SELECT count(*) FROM {tq.fq(d)}")[0][0] == n_src:
            L.log(f"  = {src:48s} → {d:50s} {n_src:6d} baris (sudah ada)")
            continue
        L.log(f"  + {src:48s} → {d:50s} {n_src:6d} baris" + (" [dry-run]" if dry else ""))
        if dry:
            continue
        if d in live:
            tq.q(f"DROP TABLE {tq.fq(d)}")
        # nama kolom lama bisa tak baku (mis. "unnamed:_1", "2026_01_01_00_00_00") → dikutip apa adanya
        tq.q(f'CREATE TABLE {tq.fq(d)} WITH (format = \'PARQUET\', format_version = 2) AS SELECT * FROM {cat}."{SRC_SCHEMA}"."{src}"')
        tq.q(f"COMMENT ON TABLE {tq.fq(d)} IS " + L.sq(
            f"Bronze apa adanya dari {cat}.{SRC_SCHEMA}.{src} (prototipe medallion 2026-11-02), dipindah {date.today().isoformat()}."))
        n_dst = tq.q(f"SELECT count(*) FROM {tq.fq(d)}")[0][0]
        if n_dst != n_src:
            ok = False
            L.log(f"    ! jumlah baris beda: {n_src} → {n_dst}")
    if dry or keep or not ok:
        L.log("Sumber TIDAK dihapus" + (" (ada selisih)" if not ok else "") + ".")
        return
    for src in have:
        tq.q(f'DROP TABLE IF EXISTS {cat}."{SRC_SCHEMA}"."{src}"')
    try:
        tq.q(f"DROP SCHEMA {cat}.{SRC_SCHEMA}", attempts=1)
        L.log(f"  - schema {cat}.{SRC_SCHEMA} dihapus")
    except Exception as e:  # noqa: BLE001
        if "protected" not in str(e):
            raise
        L.log(f"  ! {cat}.{SRC_SCHEMA} kosong tetapi diproteksi di Lakekeeper — minta admin Lakekeeper melepas proteksi")


if __name__ == "__main__":
    main()
