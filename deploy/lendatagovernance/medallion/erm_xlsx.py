#!/usr/bin/env python3
"""Ekspor Excel dengan layout berkas dasar ERM (Rev.0.1_Data Governance_ERM.xlsx) dari data Trino yang berlaku.

- Header tiap sheet dan sheet Library diambil dari templat (data/medallion/templates/erm_template.xlsx, di luar git).
- Isi tiap sheet dibaca dari Trino (silver/gold), ditambah perubahan aplikasi (app_organisasi, app_sistem).
- Kolom yang tidak ada di sumber dibiarkan kosong (tidak diisi nilai buatan).
"""
from __future__ import annotations

import io
from pathlib import Path

import app_organisasi as AO
import app_sistem as AS
import export_xlsx as X

TEMPLATE = X.DATA / "medallion" / "templates" / "erm_template.xlsx"


def _rows(tq, sql: str) -> list[tuple]:
    return tq.q(sql)


def _sheet_rows(tq) -> dict[str, list[list]]:
    """Nama sheet templat → baris data (urutan kolom mengikuti header templat)."""
    out: dict[str, list[list]] = {}
    org = AO.merged(tq)
    out["Master_Organization"] = [[r["org_id"], r["fungsi"], r["unit_kerja"], r["divisi"], r["direktorat"]] for r in org]
    sis = AS.merged(tq)
    out["Master_System"] = [[r["system_id"], r["system_name"], r["description"]] for r in sis]
    out["Business_Dataset"] = _rows(tq, f"SELECT dataset_id, business_dataset, business_domain, system_id, system_name "
                                        f"FROM {tq.fq('silver_dim_meta_dataset')} ORDER BY dataset_id")
    out["Database_Object"] = _rows(tq, f"SELECT table_id, dataset_id, dataset_name, table_name, object_type "
                                       f"FROM {tq.fq('silver_dim_meta_table')} ORDER BY table_id")
    out["Data_Element_Attribute"] = _rows(tq, f"SELECT field_id, table_id, table_name, column_name, business_term, data_type "
                                              f"FROM {tq.fq('silver_dim_meta_field')} ORDER BY field_id")
    out["Business_Glossary"] = _rows(tq, f"SELECT field_id, business_term, definisi FROM {tq.fq('gold_meta_glossary_app')} ORDER BY field_id")
    out["Data_Governance_Assignment"] = _rows(tq, f"SELECT field_id, field_name, business_term, role, org_id, unit_kerja "
                                                  f"FROM {tq.fq('silver_dim_meta_governance_assignment')}")
    out["Data_Quality_Rules"] = _rows(tq, f"SELECT field_id, field_name, business_term, rule, validation "
                                          f"FROM {tq.fq('silver_dim_meta_dq_rule')}")
    # Data_Flow_Lineage: SYSTEM_ID dan TABLE_ID tidak ada di gold_meta_lineage → kosong
    out["Data_Flow_Lineage"] = [[l, None, sn, None, tn, fid, cn, ta, tl, at] for (l, sn, tn, cn, fid, ta, tl, at) in _rows(
        tq, f"SELECT lineage_id, system_name, table_name, column_name, field_id, target_screen, target_label, asset_type "
            f"FROM {tq.fq('gold_meta_lineage')} ORDER BY lineage_id")]
    # Data_Security_Access: LINEAGE_ID tidak ada di gold_meta_access_matrix → kosong
    out["Data_Security_Access"] = [[a, None, sc, sl, fid, cn, org, uk, cl, pc, pt] for (a, sc, sl, fid, cn, org, uk, cl, pc, pt) in _rows(
        tq, f"SELECT access_id, screen, screen_label, field_id, column_name, org_id, unit_kerja, classification, "
            f"permission_category, permission_type FROM {tq.fq('gold_meta_access_matrix')} ORDER BY access_id")]
    return out


def build(tq, buf: io.BytesIO) -> dict[str, int]:
    """Tulis berkas Excel ke buf. Mengembalikan jumlah baris per sheet data."""
    from openpyxl import load_workbook
    tpl = load_workbook(TEMPLATE)                       # buka templat agar Library dan header ikut terbawa
    data = _sheet_rows(tq)
    counts: dict[str, int] = {}
    for name, rows in data.items():
        ws = tpl[name]
        # hapus isi lama (baris ≥ 2), pertahankan header
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row)
        ncol = len([c for c in next(ws.iter_rows(max_row=1, values_only=True)) if c is not None])
        for r in rows:
            ws.append(list(r)[:ncol] + [None] * max(0, ncol - len(r)))
        counts[name] = len(rows)
    tpl.save(buf)
    buf.seek(0)
    return counts
