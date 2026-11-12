#!/usr/bin/env python3
"""Ekspor hasil Data Governance (Gold di Trino) ke Excel bergaya Workbook ERM, dengan sel kosong berwarna.

Sumber = hanya Gold `gold_meta_*` (angka yang sah). Satu berkas, sheet:
  Ringkasan, Data_Dictionary, Business_Glossary, Data_Quality_Rules, Data_Flow_Lineage, Data_Security_Access,
  Library (tersembunyi; daftar pilihan dropdown).
Warna sel (nilai statis, tampil sama di Excel/LibreOffice):
  MERAH  = kolom WAJIB masih kosong (atau tertulis "Belum ada" / "Perlu input manual dari Data Governance")
  KUNING = kolom yang seharusnya terisi tetapi masih kosong / belum lengkap
  tanpa warna = lengkap. Kosong tetap NULL (tidak ada isi yang dikarang).
Cakupan: --filter "<teks>" hanya mengambil elemen data yang pemilik/steward/penggunanya memuat teks itu (mis. nama unit/Fungsi);
tanpa --filter = semua (hanya admin). Pemanggil dari aplikasi wajib mengisi --filter sesuai hak akses pengguna.
Pakai:  data/medallion/.venv/bin/python medallion/export_xlsx.py [--filter TEKS] [--out berkas.xlsx]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
import lakehouse as L  # noqa: E402

WIB = timezone(timedelta(hours=7))
PLACEHOLDERS = {"belum ada", "perlu input manual dari data governance", "tidak ada", ""}
RED, YELLOW, HEAD = "F8C9C9", "FFF3B0", "AE2524"

# sheet -> (tabel Gold, kolom, wajib=merah, seharusnya=kuning)
SHEETS = {
    "Data_Dictionary": ("gold_meta_data_dictionary",
                        ["field_id", "system_name", "business_domain", "dataset_name", "table_name", "column_name", "business_term",
                         "definition", "data_type", "classification", "owner_unit", "steward_unit", "user_units", "dq_rule_count",
                         "dq_rules", "completeness_pct"],
                        {"field_id", "column_name", "business_term", "definition", "classification", "owner_unit"},
                        {"system_name", "business_domain", "dataset_name", "table_name", "data_type", "steward_unit", "user_units",
                         "dq_rules"}),
    "Business_Glossary": ("gold_meta_glossary",
                          ["field_id", "business_term", "definition", "definition_status", "owner_unit", "steward_unit", "user_units",
                           "classification"],
                          {"field_id", "business_term", "definition", "owner_unit"}, {"steward_unit", "user_units", "classification"}),
    "Data_Quality_Rules": ("gold_meta_dq_rule",
                           ["field_id", "column_name", "business_term", "rule", "validation", "test_type", "execution_status"],
                           {"field_id", "rule", "validation"}, {"column_name", "business_term", "test_type", "execution_status"}),
    "Data_Flow_Lineage": ("gold_meta_lineage",
                          ["lineage_id", "system_name", "business_domain", "dataset_name", "table_name", "column_name", "field_id",
                           "business_term", "target_screen", "target_label", "asset_type", "classification"],
                          {"lineage_id", "field_id", "target_screen", "asset_type"},
                          {"table_name", "column_name", "business_term", "target_label", "classification"}),
    "Data_Security_Access": ("gold_meta_access_matrix",
                             ["access_id", "screen", "screen_label", "field_id", "column_name", "org_id", "unit_kerja", "classification",
                              "permission_category", "permission_type"],
                             {"access_id", "field_id", "org_id", "classification", "permission_type"},
                             {"screen_label", "column_name", "unit_kerja", "permission_category"}),
}
UNIT_COLS = ("owner_unit", "steward_unit", "user_units")


def blank(v) -> bool:
    return v is None or str(v).strip().lower() in PLACEHOLDERS


def fetch(tq, table: str, cols: list[str]) -> list[tuple]:
    return tq.q(f"SELECT {', '.join(cols)} FROM {tq.fq(table)} ORDER BY 1")


def build(out: Path, filt: str | None = None) -> dict:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    tq = L.Trino()
    now = datetime.now(WIB)
    data = {n: fetch(tq, t, c) for n, (t, c, _, _) in SHEETS.items()}
    keep = None
    if filt:
        f = filt.lower()
        dc = SHEETS["Data_Dictionary"][1]
        idx = [dc.index(c) for c in UNIT_COLS]
        keep = {r[0] for r in data["Data_Dictionary"] if any(f in str(r[i] or "").lower() for i in idx)}
        for n, rows in data.items():
            fi = SHEETS[n][1].index("field_id")
            data[n] = [r for r in rows if r[fi] in keep]

    font = "Poppins"
    thin = Side(style="thin", color="D9D9D9")
    wb = Workbook()
    summ = wb.active
    summ.title = "Ringkasan"
    stats = {}
    for name, (_, cols, req, should) in SHEETS.items():
        ws = wb.create_sheet(name)
        ws.append([c.upper() for c in cols])
        for c in ws[1]:
            c.font, c.alignment = Font(name=font, bold=True, color="FFFFFF"), Alignment(vertical="center")
            c.fill = PatternFill("solid", fgColor=HEAD)
        ws.row_dimensions[1].height = 24
        red = yel = 0
        for r in data[name]:
            ws.append(list(r))
            for j, (col, v) in enumerate(zip(cols, r), 1):
                cell = ws.cell(row=ws.max_row, column=j)
                cell.font, cell.border = Font(name=font, size=10), Border(bottom=thin)
                if blank(v) and col in req:
                    cell.fill, red = PatternFill("solid", fgColor=RED), red + 1
                elif blank(v) and col in should:
                    cell.fill, yel = PatternFill("solid", fgColor=YELLOW), yel + 1
        for j, col in enumerate(cols, 1):
            w = max([len(col)] + [len(str(r[j - 1])) for r in data[name][:200] if r[j - 1] is not None])
            ws.column_dimensions[get_column_letter(j)].width = min(60, max(12, w + 2))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        stats[name] = {"baris": len(data[name]), "merah": red, "kuning": yel}

    lib = wb.create_sheet("Library")
    cls = ["Public", "Restricted", "Confidential", "Strictly Confidential"]
    lib.append(["Classification"])
    for c in cls:
        lib.append([c])
    lib.sheet_state = "hidden"
    for name in ("Data_Dictionary", "Business_Glossary", "Data_Flow_Lineage", "Data_Security_Access"):
        ws = wb[name]
        col = get_column_letter(SHEETS[name][1].index("classification") + 1)
        dv = DataValidation(type="list", formula1="=Library!$A$2:$A$5", allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{max(2, ws.max_row)}")

    summ["A1"], summ["A1"].font = "Hasil Data Governance — Len Data Governance", Font(name=font, size=16, bold=True, color=HEAD)
    info = [("Dibuat", now.strftime("%d-%m-%Y %H:%M WIB")), ("Sumber", "Gold di Trino (lakekeeper.medallion_repository), gold_meta_*"),
            ("Cakupan", f"Pemilik/steward/pengguna memuat \"{filt}\"" if filt else "Semua (tanpa filter)"),
            ("Merah", "Kolom wajib masih kosong / belum ada"), ("Kuning", "Kolom yang seharusnya terisi, masih kosong")]
    for i, (k, v) in enumerate(info, 3):
        summ.cell(i, 1, k).font, summ.cell(i, 2, v).font = Font(name=font, bold=True), Font(name=font)
    summ["A4"].fill = PatternFill("solid", fgColor="F5F5F5")
    summ["A6"].fill, summ["A7"].fill = PatternFill("solid", fgColor=RED), PatternFill("solid", fgColor=YELLOW)
    summ.append([])
    summ.append(["Sheet", "Baris", "Sel merah", "Sel kuning"])
    for c in summ[summ.max_row]:
        c.font, c.fill = Font(name=font, bold=True, color="FFFFFF"), PatternFill("solid", fgColor=HEAD)
    for n, s in stats.items():
        summ.append([n, s["baris"], s["merah"], s["kuning"]])
    summ.column_dimensions["A"].width, summ.column_dimensions["B"].width = 26, 60
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter")
    ap.add_argument("--out", default=str(L.DATA / "exports" / f"{datetime.now(WIB):%y%m%d} Data Governance Export.xlsx"))
    a = ap.parse_args()
    s = build(Path(a.out), a.filter)
    print(a.out)
    for n, v in s.items():
        print(f"  {n}: {v['baris']} baris, merah {v['merah']}, kuning {v['kuning']}")
