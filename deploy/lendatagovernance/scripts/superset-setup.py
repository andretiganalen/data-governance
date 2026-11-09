#!/usr/bin/env python3
"""Isi awal Superset (modul Visualisasi Gold):
  1. koneksi "Len Lakehouse (Trino)" ke lakekeeper (hanya baca: allow_dml mati),
  2. dataset untuk setiap tabel gold_* + dimensi pendukung di lakekeeper.medallion_repository,
  3. dua dashboard awal — Risiko ERM dan Tata Kelola Data — dengan contoh grafik
     (tren waktu, batang bertumpuk, donut, histogram, heatmap, angka besar, tabel).

Aman diulang: koneksi diperbarui, dataset yang sudah ada dilewati, dashboard hanya dibuat bila belum ada
(pakai --force untuk membuat ulang dashboard awal; dashboard buatan admin lain tidak disentuh).

Pemakaian (di server):  /srv/lendatagovernance/medallion/.venv/bin/python scripts/superset-setup.py [--force]
  Akun: admin awal dari secrets/superset.env, atau akun Admin Superset Anda sendiri:
  SUPERSET_USER=<username> SUPERSET_PASSWORD=<sandi> …/python scripts/superset-setup.py
Kredensial: $DATA/secrets/superset.env dan $DATA/secrets/trino.env (tidak pernah di git).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

import requests

DATA = Path(os.environ.get("OM_DATA_DIR", "/srv/lendatagovernance"))
BASE = os.environ.get("SUPERSET_URL", "http://127.0.0.1:8585/visualisasi")
DB_NAME = "Len Lakehouse (Trino)"
SCHEMA = "medallion_repository"
EXTRA_DATASETS = ["silver_dim_date", "silver_dim_organization", "silver_dim_erm_risk_matrix", "bronze_repository"]


def env(name: str) -> dict[str, str]:
    return dict(l.strip().split("=", 1) for l in (DATA / "secrets" / name).read_text().splitlines()
                if "=" in l and not l.startswith("#"))


class API:
    def __init__(self):
        e = env("superset.env")
        self.s = requests.Session()
        r = self.s.post(f"{BASE}/api/v1/security/login", json={
            "username": os.environ.get("SUPERSET_USER") or e.get("SUPERSET_ADMIN_USER", "admin"),
            "password": os.environ.get("SUPERSET_PASSWORD") or e["SUPERSET_ADMIN_PASSWORD"],
            "provider": "db", "refresh": True})
        r.raise_for_status()
        self.s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        self.s.headers["X-CSRFToken"] = self.s.get(f"{BASE}/api/v1/security/csrf_token/").json()["result"]
        self.s.headers["Referer"] = BASE

    def call(self, method: str, path: str, **kw):
        r = self.s.request(method, f"{BASE}{path}", **kw)
        if r.status_code >= 400:
            raise SystemExit(f"{method} {path} → {r.status_code}: {r.text[:500]}")
        return r.json() if r.text else {}

    def find(self, kind: str, col: str, value) -> dict | None:
        q = {"filters": [{"col": col, "opr": "eq", "value": value}], "page_size": 100}
        res = self.call("GET", f"/api/v1/{kind}/?q={quote(json.dumps(q))}")["result"]
        return res[0] if res else None


def setup_database(api: API) -> int:
    t = env("trino.env")
    uri = (f"trino://{quote(t['TRINO_USER'], safe='')}:{quote(t['TRINO_PASSWORD'], safe='')}"
           f"@{t['TRINO_HOST']}:{t.get('TRINO_PORT', '443')}/{t['TRINO_CATALOG']}")
    body = {"database_name": DB_NAME, "sqlalchemy_uri": uri, "expose_in_sqllab": True, "allow_dml": False,
            "allow_ctas": False, "allow_cvas": False, "allow_run_async": False, "allow_file_upload": False,
            "extra": json.dumps({"engine_params": {"connect_args": {"http_scheme": "https", "source": "lendatagovernance-superset"}},
                                 "metadata_params": {}, "schemas_allowed_for_file_upload": [],
                                 "metadata_cache_timeout": {"schema_cache_timeout": 600, "table_cache_timeout": 600}})}
    db = api.find("database", "database_name", DB_NAME)
    if db:
        api.call("PUT", f"/api/v1/database/{db['id']}", json=body)
        print(f"koneksi diperbarui: {DB_NAME} (id {db['id']})")
        return db["id"]
    r = api.call("POST", "/api/v1/database/", json=body)
    print(f"koneksi dibuat: {DB_NAME} (id {r['id']})")
    return r["id"]


def setup_datasets(api: API, db_id: int) -> dict[str, int]:
    tables = api.call("GET", f"/api/v1/database/{db_id}/tables/?q={quote(json.dumps({'schema_name': SCHEMA, 'force': True}))}")["result"]
    names = sorted(t["value"] for t in tables if t["value"].startswith("gold_")) + EXTRA_DATASETS
    ids = {}
    for name in names:
        q = {"filters": [{"col": "table_name", "opr": "eq", "value": name}, {"col": "schema", "opr": "eq", "value": SCHEMA}]}
        found = api.call("GET", f"/api/v1/dataset/?q={quote(json.dumps(q))}")["result"]
        if found:
            ids[name] = found[0]["id"]
            api.call("PUT", f"/api/v1/dataset/{ids[name]}/refresh")
            continue
        r = api.call("POST", "/api/v1/dataset/", json={"database": db_id, "schema": SCHEMA, "table_name": name})
        ids[name] = r["id"]
        print(f"dataset dibuat: {name} (id {ids[name]})")
    for name, i in ids.items():  # kolom waktu utama → filter waktu & sumbu waktu bawaan
        d = api.call("GET", f"/api/v1/dataset/{i}")["result"]
        cols = [c["column_name"] for c in d.get("columns", [])]
        dttm = next((c for c in ("period_date", "snapshot_date", "full_date", "ingested_at") if c in cols), None)
        if dttm and d.get("main_dttm_col") != dttm:
            api.call("PUT", f"/api/v1/dataset/{i}", json={"main_dttm_col": dttm})
    print(f"{len(ids)} dataset siap")
    return ids


# --------------------------------------------------------------- grafik
def m(col: str, agg: str = "SUM", label: str | None = None) -> dict:
    return {"expressionType": "SIMPLE", "column": {"column_name": col}, "aggregate": agg, "label": label or f"{agg}({col})"}


def f_eq(col: str, val) -> dict:
    return {"expressionType": "SIMPLE", "subject": col, "operator": "==", "comparator": val, "clause": "WHERE"}


COMMON = {"time_range": "No filter", "adhoc_filters": [], "color_scheme": "lenDataGovernance", "row_limit": 10000}


def ts(kind: str, x: str, metrics: list, groupby=None, **kw) -> dict:
    return {"viz_type": kind, "x_axis": x, "time_grain_sqla": "P1M", "metrics": metrics, "groupby": groupby or [],
            "show_legend": True, "legendOrientation": "top", "rich_tooltip": True, "y_axis_format": "SMART_NUMBER",
            "x_axis_time_format": "%b %Y", "truncate_metric": True, **kw}


def charts_erm() -> list[tuple]:
    """(judul, dataset, form_data, lebar 1–12, tinggi)"""
    return [
        ("Jumlah risiko terdaftar", "gold_erm_risk_register",
         {"viz_type": "big_number_total", "metric": "count", "subheader": "risiko (register E-GRC)", "y_axis_format": "SMART_NUMBER"}, 3, 30),
        ("Eksposur inheren total (IDR)", "gold_erm_risk_register",
         {"viz_type": "big_number_total", "metric": m("exposure_risiko_inheren", "SUM", "Eksposur inheren"), "subheader": "IDR",
          "y_axis_format": "SMART_NUMBER"}, 3, 30),
        ("KRI berstatus Bahaya", "gold_erm_kri_monitoring_monthly",
         {"viz_type": "big_number_total", "metric": m("kri_id", "COUNT_DISTINCT", "KRI bahaya"), "subheader": "KRI (seluruh periode)",
          "adhoc_filters": [f_eq("is_bahaya", True)], "y_axis_format": "SMART_NUMBER"}, 3, 30),
        ("Progres penanganan rata-rata", "gold_erm_mitigation_progress_monthly",
         {"viz_type": "big_number_total", "metric": m("persentase_realisasi", "AVG", "Progres rata-rata"), "subheader": "dari laporan yang ada",
          "y_axis_format": ".0%"}, 3, 30),
        ("Sebaran level risiko inheren (donut)", "gold_erm_risk_register",
         {"viz_type": "pie", "groupby": ["kategori_tingkat_risiko_inheren"], "metric": "count", "donut": True, "show_labels": True,
          "label_type": "key_percent", "labels_outside": True, "innerRadius": 40, "outerRadius": 75, "sort_by_metric": True}, 4, 55),
        ("Eksposur realisasi vs batasan per bulan (tren)", "gold_erm_risk_appetite_utilization",
         ts("echarts_timeseries_line", "period_date",
            [m("exposure_realisasi_total", "SUM", "Eksposur realisasi"), m("exposure_target_total", "SUM", "Eksposur target"),
             m("nilai_batasan_risiko", "SUM", "Batasan risiko")], markerEnabled=True), 8, 55),
        ("Histogram tingkat risiko inheren (1–25)", "gold_erm_risk_register",
         {"viz_type": "histogram_v2", "column": "tingkat_risiko_inheren", "groupby": [], "bins": 5, "normalize": False,
          "x_axis_title": "Tingkat risiko inheren", "y_axis_title": "Jumlah risiko", "show_value": True}, 4, 55),
        ("Peta risiko inheren 5×5 (heatmap)", "gold_erm_risk_heatmap_monthly",
         {"viz_type": "heatmap_v2", "x_axis": "skor_dampak", "groupby": "skor_kemungkinan", "metric": m("jumlah_risiko", "SUM", "Jumlah risiko"),
          "adhoc_filters": [f_eq("assessment_type", "INHEREN")], "linear_color_scheme": "lenRiskLevel", "show_values": True,
          "normalize_across": "heatmap", "sort_x_axis": "alpha_asc", "sort_y_axis": "alpha_desc", "xscale_interval": -1,
          "yscale_interval": -1, "left_margin": "auto", "bottom_margin": "auto", "value_bounds": [None, None], "y_axis_format": "SMART_NUMBER"}, 4, 55),
        ("Status KRI per bulan (batang bertumpuk)", "gold_erm_kri_monitoring_monthly",
         ts("echarts_timeseries_bar", "period_date", ["count"], ["status_kri"], stack="Stack"), 4, 55),
        ("Sebaran level realisasi per bulan", "gold_erm_risk_assessment_monthly",
         ts("echarts_timeseries_bar", "period_date", ["count"], ["kategori_tingkat_risiko"], stack="Stack",
            adhoc_filters=[f_eq("assessment_type", "REALISASI")]), 6, 55),
        ("Progres penanganan rata-rata per bulan", "gold_erm_mitigation_progress_monthly",
         ts("echarts_timeseries_line", "period_date", [m("persentase_realisasi", "AVG", "Progres rata-rata")], ["company_acronym"],
            y_axis_format=".0%", markerEnabled=True), 6, 55),
        ("Register risiko (tabel)", "gold_erm_risk_register",
         {"viz_type": "table", "query_mode": "raw", "all_columns": [
             "company_acronym", "risk_id", "main_category", "peristiwa_risiko", "kategori_tingkat_risiko_inheren", "tingkat_risiko_inheren",
             "exposure_risiko_inheren", "kategori_tingkat_risiko_realisasi", "periode_realisasi_terakhir", "jumlah_rencana_penanganan",
             "progres_penanganan_rata2"], "order_by_cols": [json.dumps(["tingkat_risiko_inheren", False])], "row_limit": 1000,
          "include_search": True, "server_pagination": False, "table_timestamp_format": "%Y-%m"}, 12, 70),
    ]


def charts_meta() -> list[tuple]:
    return [
        ("Elemen data (kolom)", "gold_meta_data_dictionary", {"viz_type": "big_number_total", "metric": "count", "subheader": "FIELD_ID terdaftar"}, 3, 30),
        ("Kelengkapan metadata rata-rata", "gold_meta_data_dictionary",
         {"viz_type": "big_number_total", "metric": m("completeness_pct", "AVG", "Kelengkapan"), "subheader": "% (tabel, definisi, klasifikasi, pemilik)",
          "y_axis_format": ",.1f"}, 3, 30),
        ("Istilah glosarium tanpa definisi", "gold_meta_glossary",
         {"viz_type": "big_number_total", "metric": "count", "subheader": "istilah", "adhoc_filters": [f_eq("definition_status", "Belum ada")]}, 3, 30),
        ("Temuan mutu data hari ini", "gold_meta_dq_finding_snapshot",
         {"viz_type": "big_number_total", "metric": "count", "subheader": "temuan (snapshot terakhir)",
          "time_range": "Last day"}, 3, 30),
        ("Sebaran klasifikasi sensitivitas (donut)", "gold_meta_data_dictionary",
         {"viz_type": "pie", "groupby": ["classification"], "metric": "count", "donut": True, "show_labels": True,
          "label_type": "key_percent", "innerRadius": 40, "outerRadius": 75}, 4, 55),
        ("Tren KPI kelengkapan (%)", "gold_meta_governance_kpi_snapshot",
         {**ts("echarts_timeseries_line", "snapshot_date", [m("kpi_value", "MAX", "Nilai")], ["kpi_name"],
               adhoc_filters=[f_eq("kpi_category", "Kelengkapan")], markerEnabled=True), "time_grain_sqla": "P1D",
          "x_axis_time_format": "%d %b"}, 8, 55),
        ("% definisi per tabel", "gold_meta_table_summary",
         {"viz_type": "echarts_timeseries_bar", "x_axis": "table_name", "metrics": [m("definition_pct", "MAX", "% definisi")], "groupby": [],
          "orientation": "horizontal", "show_legend": False, "y_axis_format": ",.0f", "x_axis_sort": "% definisi", "x_axis_sort_asc": True,
          "truncate_metric": True}, 6, 60),
        ("Temuan mutu per sumber & kategori", "gold_meta_dq_finding_snapshot",
         {"viz_type": "echarts_timeseries_bar", "x_axis": "finding_category", "metrics": [m("affected_rows", "SUM", "Baris terdampak")],
          "groupby": ["source_system"], "stack": "Stack", "show_legend": True, "y_axis_format": "SMART_NUMBER", "time_range": "Last day"}, 6, 60),
        ("Hak akses per unit kerja & jenis izin", "gold_meta_access_matrix",
         {"viz_type": "echarts_timeseries_bar", "x_axis": "unit_kerja", "metrics": ["count"], "groupby": ["permission_category"],
          "stack": "Stack", "orientation": "horizontal", "show_legend": True, "y_axis_format": "SMART_NUMBER", "row_limit": 100}, 12, 70),
        ("Kamus data (tabel)", "gold_meta_data_dictionary",
         {"viz_type": "table", "query_mode": "raw", "all_columns": [
             "field_id", "table_name", "column_name", "business_term", "classification", "owner_unit", "dq_rule_count",
             "downstream_screen_count", "completeness_pct"], "row_limit": 1000, "include_search": True}, 12, 70),
    ]


DASHBOARDS = [
    ("risiko-erm", "Risiko ERM — Ringkasan (Gold)", charts_erm),
    ("tata-kelola-data", "Tata Kelola Data — Metadata (Gold)", charts_meta),
]


def layout(chart_rows: list[list[tuple[int, str, int, int]]]) -> dict:
    pos = {"DASHBOARD_VERSION_KEY": "v2", "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
           "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]}}
    for row in chart_rows:
        rid = f"ROW-{uuid.uuid4().hex[:10]}"
        pos["GRID_ID"]["children"].append(rid)
        pos[rid] = {"type": "ROW", "id": rid, "children": [], "parents": ["ROOT_ID", "GRID_ID"], "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        for cid, name, w, h in row:
            k = f"CHART-{uuid.uuid4().hex[:10]}"
            pos[rid]["children"].append(k)
            pos[k] = {"type": "CHART", "id": k, "children": [], "parents": ["ROOT_ID", "GRID_ID", rid],
                      "meta": {"chartId": cid, "sliceName": name, "width": w, "height": h}}
    return pos


def setup_dashboards(api: API, ds: dict[str, int], force: bool) -> None:
    for slug, title, spec in DASHBOARDS:
        old = api.find("dashboard", "slug", slug)
        if old and not force:
            print(f"dashboard sudah ada: {title} → /superset/dashboard/{slug}/ (pakai --force untuk membuat ulang)")
            continue
        if old:
            for c in api.call("GET", f"/api/v1/dashboard/{old['id']}/charts")["result"]:
                api.call("DELETE", f"/api/v1/chart/{c['id']}")
            api.call("DELETE", f"/api/v1/dashboard/{old['id']}")
        d = api.call("POST", "/api/v1/dashboard/", json={"dashboard_title": title, "slug": slug, "published": True,
                                                          "json_metadata": json.dumps({"color_scheme": "lenDataGovernance",
                                                                                       "refresh_frequency": 0, "cross_filters_enabled": True})})
        rows, cur, width = [], [], 0
        for name, table, form, w, h in spec():
            if table not in ds:
                print(f"  ! dataset {table} belum ada — grafik '{name}' dilewati")
                continue
            fd = {**COMMON, **form, "datasource": f"{ds[table]}__table"}
            c = api.call("POST", "/api/v1/chart/", json={"slice_name": name, "viz_type": fd["viz_type"], "datasource_id": ds[table],
                                                         "datasource_type": "table", "params": json.dumps(fd), "dashboards": [d["id"]]})
            if width + w > 12:
                rows.append(cur)
                cur, width = [], 0
            cur.append((c["id"], name, w, h))
            width += w
        if cur:
            rows.append(cur)
        api.call("PUT", f"/api/v1/dashboard/{d['id']}", json={"position_json": json.dumps(layout(rows))})
        print(f"dashboard dibuat: {title} → {BASE}/superset/dashboard/{slug}/ ({sum(len(r) for r in rows)} grafik)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="buat ulang dashboard awal")
    a = ap.parse_args()
    api = API()
    db_id = setup_database(api)
    ds = setup_datasets(api, db_id)
    setup_dashboards(api, ds, a.force)


if __name__ == "__main__":
    sys.exit(main())
