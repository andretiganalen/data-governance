#!/usr/bin/env python3
"""Satu perintah rilis: 3 manual PDF dengan nomor versi "YYMMDD CC", angka diambil langsung dari sumbernya.

  /home/ubuntu/data-governance/data/medallion/.venv/bin/python docs/manuals/src/rilis.py [--dry-run | --preview <dir>]

- CC = nomor iterasi global (01, 02, …): nilai CC tertinggi dari PDF di docs/manuals/, + 1. Rilis lama tidak ditimpa.
- Data Gold/dataset dibaca dari Trino lakehouse lakekeeper.medallion_repository (hanya SELECT/SHOW, tidak menulis);
  dibangun oleh deploy/lendatagovernance/medallion/lakehouse.py, bukan oleh skrip ini.
- Status katalog dibaca dari kontainer (project compose lendatagovernance) → build/data.js → PDF (Chrome).
- Butuh: venv medallion (trino + openpyxl), kredensial secrets/trino.env, node 22, google-chrome, sudo docker.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import socket
import subprocess
from datetime import date, datetime
from pathlib import Path

SRC = Path(__file__).resolve().parent
OUT = SRC.parent                                   # docs/manuals
REPO = SRC.parents[2]
DEPLOY = REPO / "deploy/lendatagovernance"
LIVE = Path("/home/ubuntu/data-governance/deploy/lendatagovernance")
DATA = Path("/home/ubuntu/data-governance/data")
PROJECT = "lendatagovernance"                      # nama project compose
DB = "lendatagovernance_db"                        # basis data katalog di Postgres
DOCS = [  # (source html, nama dokumen)
    ("pengembang.html", "Manual Pengembang"),
    ("staf.html", "Manual Staf Data Governance dan Pimpinan"),
    ("pengguna.html", "Manual Pengguna"),
]
# Tabel Gold metadata ↔ keterangan berbahasa Indonesia (GOLD_INFO di medallion/build_medallion.py).
GOLD_INFO_KEY = {
    "gold_meta_data_dictionary": "gold_kamus_data", "gold_meta_table_summary": "gold_ringkasan_tabel",
    "gold_meta_screen_summary": "gold_ringkasan_layar", "gold_meta_lineage": "gold_lineage",
    "gold_meta_access_matrix": "gold_hak_akses", "gold_meta_glossary": "gold_glosarium",
    "gold_meta_dq_rule": "gold_aturan_mutu", "gold_meta_governance_kpi_snapshot": "gold_kpi_tata_kelola",
}
# Nama tampilan + pertanyaan yang dijawab untuk tabel Gold lain (isi = komentar tabel di Trino).
GOLD_NAMA = {
    "gold_erm_risk_register": ("Register Risiko", "Risiko apa saja yang tercatat, berapa nilai inheren dan realisasinya?"),
    "gold_erm_risk_assessment_monthly": ("Penilaian Risiko Bulanan", "Bagaimana tren tingkat risiko dari bulan ke bulan?"),
    "gold_erm_risk_heatmap_monthly": ("Peta Risiko 5×5 Bulanan", "Di sel mana risiko perusahaan terkumpul?"),
    "gold_erm_executive_summary_monthly": ("Ringkasan Eksekutif Bulanan", "Bagaimana posisi risiko perusahaan bulan ini?"),
    "gold_erm_kri_monitoring_monthly": ("Pemantauan KRI Bulanan", "Indikator risiko mana yang melewati batas?"),
    "gold_erm_mitigation_progress_monthly": ("Progres Mitigasi Bulanan", "Sejauh mana rencana penanganan risiko berjalan?"),
    "gold_erm_risk_appetite_utilization": ("Pemakaian Selera Risiko", "Berapa eksposur dibanding selera dan toleransi risiko?"),
    "gold_erm_governance_compliance": ("Kepatuhan Pengisian Register", "Seberapa lengkap register risiko diisi?"),
    "gold_erm_company_benchmark": ("Perbandingan Antar Perusahaan", "Bagaimana posisi risiko antar perusahaan?"),
    "gold_erm_audit_finding_linkage": ("Temuan Audit terkait Risiko", ""),
    "gold_erm_risk_loss_event": ("Kejadian Kerugian", ""),
    "gold_erm_swot_matrix": ("Matriks SWOT", ""),
    "gold_erm_iro_event_count": ("Jumlah Kejadian IRO", ""),
    "gold_erm_iro_row_count": ("Jumlah Baris IRO", ""),
    "gold_meta_dq_finding_snapshot": ("Temuan Mutu Data Sumber", "Masalah mutu apa yang ditemukan saat data dimuat?"),
}


def next_release() -> str:
    cc = [int(m.group(1)) for p in OUT.glob("*.pdf") if (m := re.match(r"^\d{6} (\d{2}) ", p.name))]
    return f"{datetime.now():%y%m%d} {max(cc, default=0) + 1:02d}"


def sh(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout.strip()


def psql(sql: str) -> str:
    return sh(f"cd {LIVE} && sudo -n docker compose -p {PROJECT} exec -T postgresql "
              f"psql -U postgres -d {DB} -At -F '|' -c \"{sql}\"")


def count(table: str) -> int:
    v = psql(f"select count(*) from {table}")
    return int(v) if v.isdigit() else -1


def live_status() -> dict:
    s: dict = {"diambil": f"{datetime.now():%Y-%m-%d %H:%M}"}
    s["layanan"] = [dict(zip(("nama", "status"), l.split("\t")))
                    for l in sh(f"cd {LIVE} && sudo -n docker compose -p {PROJECT} ps --format '{{{{.Service}}}}\t{{{{.Status}}}}'").splitlines()]
    # versi server katalog = tag image upstream pada baris image layanan ldg-server
    m = re.search(r"image:\s*\S+/server:([\w.]+)", (LIVE / "compose.yaml").read_text())
    s["versi_katalog"] = m.group(1) if m else "?"
    s["entitas"] = {k: count(t) for k, t in {
        "tabel": "table_entity", "kolom_katalog": "(select jsonb_array_elements(json->'columns') from table_entity) c",
        "dashboard": "dashboard_entity", "istilah_glosarium": "glossary_term_entity", "tim": "team_entity",
        "test_case": "test_case", "hasil_uji": "data_quality_data_time_series", "kontrak_data": "data_contract_entity",
        "produk_data": "data_product_entity", "domain": "domain_entity", "pipeline": "pipeline_entity",
        "model_ml": "ml_model_entity", "metrik": "metric_entity", "pengumuman": "announcement_entity",
        "percakapan": "thread_entity_legacy"}.items()}
    s["entitas"]["lineage_edge"] = int(psql("select count(*) from entity_relationship where relation=13") or -1)
    s["tag"] = dict(l.split("|") for l in psql(
        "select tagfqn, count(*) from tag_usage where tagfqn not like 'ERM.%' group by 1 order by 1").splitlines())
    s["sertifikasi_terpasang"] = int(psql("select count(*) from tag_usage where tagfqn like 'Certification.%'") or 0)
    users = [l.split("|") for l in psql(
        "select name, json->>'isAdmin', coalesce(json->>'isBot','false') from user_entity").splitlines()]
    human = [u for u in users if u[2] != "true" and "bot" not in u[0]]
    s["akun"] = {"manusia": len(human), "admin": sum(u[1] == "true" for u in human),
                 "non_admin": sum(u[1] != "true" for u in human)}
    s["peran_tim"] = [l.split("|") for l in psql(
        "select t.name, r.name from entity_relationship e join team_entity t on t.id::text=e.fromid::text "
        "join role_entity r on r.id::text=e.toid::text where e.fromentity='team' and e.toentity='role'").splitlines()]
    s["anggota_uv1"] = int(psql(
        "select count(*) from entity_relationship e join team_entity t on t.id::text=e.fromid::text "
        "where t.name='UV-1' and e.toentity='user'") or 0)
    s["nonadmin_dengan_role_bot"] = int(psql(
        "select count(distinct u.name) from entity_relationship e join user_entity u on u.id::text=e.fromid::text "
        "join role_entity r on r.id::text=e.toid::text where e.toentity='role' and r.name like '%Bot%' "
        "and u.name not like '%bot%' and coalesce(u.json->>'isAdmin','false')='false'") or 0)
    s["kebijakan"] = {}
    for p in ("DataConsumerPolicy", "OrganizationPolicy", "DG_UV_1"):
        s["kebijakan"][p] = [dict(zip(("rule", "efek", "resource", "operasi", "kondisi"), l.split("|"))) for l in psql(
            "select r->>'name', r->>'effect', (select string_agg(x,',') from jsonb_array_elements_text(r->'resources') x), "
            "(select string_agg(x,', ') from jsonb_array_elements_text(r->'operations') x), coalesce(r->>'condition','') "
            f"from policy_entity, jsonb_array_elements(json->'rules') r where json->>'name'='{p}'").splitlines()]
    env = {}
    for f in (DATA / "secrets/lendatagovernance.env",):
        try:
            for line in f.read_text().splitlines():
                if line.startswith("AUTHENTICATION_") and "KEY" not in line:
                    k, _, v = line.partition("=")
                    env[k] = v
        except OSError:
            pass
    s["auth"] = {"provider": env.get("AUTHENTICATION_PROVIDER", "?"),
                 "self_signup": env.get("AUTHENTICATION_ENABLE_SELF_SIGNUP", "?")}
    exp = None
    try:  # only the expiry is read from the token; the token itself is never printed or stored
        tok = next(l.split("=", 1)[1] for l in (DATA / "secrets/loader.env").read_text().splitlines()
                   if l.startswith("LDG_TOKEN="))
        pl = tok.split(".")[1]
        exp = json.loads(base64.urlsafe_b64decode(pl + "=" * (-len(pl) % 4))).get("exp")
    except (OSError, StopIteration, IndexError, ValueError):
        pass
    s["token_loader_kedaluwarsa"] = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M") if exp else "tidak terbaca"
    s["token_loader_aktif"] = bool(exp and exp > datetime.now().timestamp())
    try:
        socket.gethostbyname("dev-data.len.co.id")
        s["dns"] = "ada"
    except OSError:
        s["dns"] = "NXDOMAIN"
    b = sorted((DATA / "backup").glob("lendatagovernance_db-*.dump"), key=lambda p: p.stat().st_mtime)
    s["backup_terakhir"] = b[-1].name if b else "-"
    s["jumlah_backup"] = len(b)
    rep = sorted((DATA / "reports").glob("workbook-defects-*.md"))
    s["cacat"] = {}
    if rep:
        for line in rep[-1].read_text().splitlines():
            if m := re.match(r"^### (.+) \((\d+)\)", line):
                s["cacat"][m.group(1)] = int(m.group(2))
        s["laporan_cacat"] = rep[-1].name
    return s


def trino():
    """Koneksi baca ke lakekeeper.medallion_repository memakai kelas Trino milik loader (kredensial secrets/trino.env)."""
    import sys
    sys.path.insert(0, str(DEPLOY / "medallion"))
    import lakehouse
    return lakehouse, lakehouse.Trino()


def num(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def gold_status(lh, tq) -> dict:
    """Ringkasan lapisan Gold di Trino: daftar tabel/view gold_*, baris, kolom, KPI tata kelola terbaru, glosarium kosong."""
    cat, sch = tq.catalog, tq.schema
    objs = tq.q(f"SELECT table_name, table_type FROM {cat}.information_schema.tables WHERE table_schema = '{sch}'")
    lapisan = {k: sum(1 for t, _ in objs if t.startswith(k + "_")) for k in ("bronze", "silver", "gold")}
    cols: dict[str, list[str]] = {}
    for t, c in tq.q(f"SELECT table_name, column_name FROM {cat}.information_schema.columns "
                     f"WHERE table_schema = '{sch}' AND table_name LIKE 'gold%' ORDER BY table_name, ordinal_position"):
        if t.startswith("gold_") and not c.startswith("_"):
            cols.setdefault(t, []).append(c)
    comment = dict(tq.q(f"SELECT table_name, comment FROM system.metadata.table_comments "
                        f"WHERE catalog_name = '{cat}' AND schema_name = '{sch}' AND table_name LIKE 'gold%'"))
    tabel = []
    for t, typ in sorted(o for o in objs if o[0].startswith("gold_")):
        try:
            n = tq.q(f"SELECT count(*) FROM {tq.fq(t)}", attempts=3)[0][0]
        except Exception:  # noqa: BLE001 — satu tabel tak terbaca tidak menggagalkan rilis
            n = -1
        nama, isi, menjawab = lh.bm.GOLD_INFO.get(GOLD_INFO_KEY.get(t, ""), (None, None, ""))
        if not nama:
            nama, menjawab = GOLD_NAMA.get(t, (t, ""))
        tabel.append({"tabel": t, "jenis": "view" if typ == "VIEW" else "tabel", "nama": nama or t,
                      "isi": isi or comment.get(t) or "", "menjawab": menjawab, "baris": n, "kolom": cols.get(t, [])})
    snap = tq.q("SELECT max(snapshot_date) FROM gold_meta_governance_kpi_snapshot")[0][0]
    kpi = [{"kategori": a, "indikator": b, "nilai": num(c), "satuan": d} for a, b, c, d in tq.q(
        "SELECT kpi_category, kpi_name, kpi_value, unit FROM gold_meta_governance_kpi_snapshot "
        f"WHERE snapshot_date = DATE '{snap}'")] if snap else []
    nodef = [f"{a} {b}" for a, b in tq.q(
        "SELECT field_id, business_term FROM gold_meta_glossary WHERE definition_status = 'Belum ada' ORDER BY field_id")]
    notes = {k: v for k, v in tq.q("SELECT sheet_name, count(*) FROM silver_fact_meta_baseline_correction GROUP BY 1 ORDER BY 1")}
    sumber = [{"sistem": a, "berkas": b, "dimuat": c.strftime("%Y-%m-%d %H:%M")} for a, b, c in tq.q(
        "SELECT source_system, max_by(file_name, ingested_at), max(ingested_at) FROM bronze_repository "
        "WHERE is_processed_to_silver GROUP BY 1 ORDER BY 1")]
    return {"katalog": f"{cat}.{sch}", "diambil": f"{datetime.now():%Y-%m-%d %H:%M}", "lapisan": lapisan,
            "tabel": tabel, "kpi": kpi, "kpi_tanggal": str(snap or "-"), "glosarium_belum_ada": nodef,
            "silver_catatan_mutu": notes, "sumber": sumber}


def dataset_view(tq) -> list[dict]:
    """Ringkasan per dataset bisnis untuk pengguna: ada/belum, dipakai di layar mana, oleh unit mana (dari Trino)."""
    split = lambda v: [u for u in (v or "").split("; ") if u]  # noqa: E731
    kamus = tq.q("SELECT dataset_name, table_name, owner_unit, user_units FROM gold_meta_data_dictionary")
    layar = tq.q("SELECT DISTINCT dataset_name, target_screen FROM gold_meta_lineage")
    out = []
    for ds, dom, sistem in tq.q("SELECT business_dataset, business_domain, system_name FROM silver_dim_meta_dataset "
                                "ORDER BY business_domain, business_dataset"):
        ks = [k for k in kamus if k[0] == ds]
        tabel = sorted({k[1] for k in ks if k[1]})
        out.append({"dataset": ds, "domain": dom or "", "sistem": sistem or "",
                    "status": "Tersedia" if tabel else "Belum ada", "tabel": tabel,
                    "layar": sorted({s for d, s in layar if d == ds and s}),
                    "pemilik": sorted({u for k in ks for u in split(k[2])}),
                    "pengguna": sorted({u for k in ks for u in split(k[3])})})
    return out


MASTER_FROM = date(2026, 11, 14)   # keputusan 2026-11-13: daftar Master Organisasi masuk setiap manual mulai rilis 14 November 2026


def master_view(tq) -> dict:
    """Master Organisasi (Gold gold_meta_master_organisasi): versi + daftar Fungsi Generik berlaku per unit, urutan sesuai dokumen."""
    ver = [{"versi": a, "dokumen": b, "tanggal": str(c), "baris": n, "berlaku": bool(cur)} for a, b, c, n, cur in tq.q(
        "SELECT versi, dokumen, tanggal_dokumen, count(*), max_by(is_current, tanggal_dokumen) FROM gold_meta_master_organisasi "
        "GROUP BY versi, dokumen, tanggal_dokumen ORDER BY tanggal_dokumen")]
    rows = [{"direktorat": a or "", "divisi": b or "", "bagian": c or "", "fungsi": d or "", "lama": e or "", "catatan": f or ""}
            for a, b, c, d, e, f in tq.q(
        "SELECT direktorat, divisi, bagian, fungsi_generik, fungsi_lama, catatan FROM gold_meta_master_organisasi "
        "WHERE is_current ORDER BY urutan")]
    return {"versi": ver, "baris": rows, "fungsi": len({r["fungsi"] for r in rows})}


def release_of_build() -> str:
    t = (SRC / "build/data.js").read_text()
    return json.loads(t[t.index("=") + 1:].strip().rstrip(";"))["rilis"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="tampilkan nomor rilis berikutnya saja")
    ap.add_argument("--preview", metavar="DIR", help="cetak ulang PDF dari build/data.js terakhir ke DIR (tanpa rilis baru)")
    a = ap.parse_args()
    if a.preview:
        rel = release_of_build()
        jobs = [{"src": s, "out": f"PREVIEW {rel} {name}.pdf", "title": name} for s, name in DOCS]
        Path(a.preview).mkdir(parents=True, exist_ok=True)
        subprocess.run(["node", str(SRC / "build-pdf.mjs"), a.preview, json.dumps(jobs)], check=True)
        return
    release = next_release()
    print(f"Rilis: {release}")
    if a.dry_run:
        return
    build = SRC / "build"
    build.mkdir(exist_ok=True)
    lh, tq = trino()
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
             "November", "Desember"]
    now = datetime.now()
    data = {
        "rilis": release, "tanggal": f"{now.day} {bulan[now.month - 1]} {now.year}", "tanggal_iso": f"{now:%Y-%m-%d}",
        "gold": gold_status(lh, tq),
        "live": live_status(),
        "dataset": dataset_view(tq),
        "master": master_view(tq) if now.date() >= MASTER_FROM else None,
        "alamat": "http://192.168.125.14",
        "visualisasi": "http://192.168.125.14:8585/visualisasi/",
    }
    (build / "data.js").write_text("window.R = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    jobs = [{"src": s, "out": f"{release} {name}.pdf", "title": name} for s, name in DOCS]
    subprocess.run(["node", str(SRC / "build-pdf.mjs"), str(OUT), json.dumps(jobs)], check=True)
    write_index(release)


def write_index(release: str) -> None:
    rows = []
    for p in sorted(OUT.glob("*.pdf"), reverse=True):
        if m := re.match(r"^(\d{6} \d{2}) (.+)\.pdf$", p.name):
            rows.append(f"| {m.group(1)} | [{m.group(2)}](<{p.name}>) | {p.stat().st_size // 1024} KB |")
    (OUT / "README.md").write_text(
        "# Manual Len Data Governance — daftar rilis\n\n"
        "Nama berkas: `YYMMDD CC [Nama Dokumen].pdf` — CC naik satu setiap rilis baru; rilis lama tidak ditimpa.\n"
        "Rilis baru: `/home/ubuntu/data-governance/data/medallion/.venv/bin/python docs/manuals/src/rilis.py` (lihat `src/README.md`).\n\n"
        "| Rilis | Dokumen | Ukuran |\n| :-- | :-- | --: |\n" + "\n".join(rows) + "\n")
    print(f"Indeks: {OUT / 'README.md'}")


if __name__ == "__main__":
    main()
