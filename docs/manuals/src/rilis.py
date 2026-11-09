#!/usr/bin/env python3
"""Satu perintah rilis: data Gold + 3 manual PDF dengan nomor versi "YYMMDD CC".

  python3 docs/manuals/src/rilis.py [--workbook <xlsx>] [--dry-run]

- CC = nomor iterasi global (01, 02, …): nilai CC tertinggi dari PDF di docs/manuals/ dan rilis di panel, + 1.
  Rilis lama tidak pernah ditimpa.
- Langkah: medallion (Bronze→Silver→Gold, panel /unduh/) → status langsung dari server → data.js → PDF (Chrome).
- Butuh: python3 + openpyxl, node 22, google-chrome, sudo docker (untuk membaca status katalog).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parent
OUT = SRC.parent                                   # docs/manuals
REPO = SRC.parents[2]
DEPLOY = REPO / "deploy/openmetadata"
LIVE = Path("/opt/openmetadata/deploy")
DATA = Path("/srv/openmetadata")
MEDALLION = DATA / "medallion"
WORKBOOK = REPO / "templates/261016 Rev.0.1_Data Governance_ERM.xlsx"
DOCS = [  # (source html, nama dokumen)
    ("pengembang.html", "Manual Pengembang"),
    ("staf.html", "Manual Staf Data Governance dan Pimpinan"),
    ("pengguna.html", "Manual Pengguna"),
]


def next_release() -> str:
    cc = [int(m.group(1)) for p in OUT.glob("*.pdf") if (m := re.match(r"^\d{6} (\d{2}) ", p.name))]
    cc += [int(m.group(1)) for p in (MEDALLION / "panel/rilis").glob("*") if (m := re.match(r"^\d{6}-(\d{2})$", p.name))]
    return f"{datetime.now():%y%m%d} {max(cc, default=0) + 1:02d}"


def sh(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout.strip()


def psql(sql: str) -> str:
    return sh(f"cd {LIVE} && sudo -n docker compose -p openmetadata exec -T postgresql "
              f"psql -U postgres -d openmetadata_db -At -F '|' -c \"{sql}\"")


def count(table: str) -> int:
    v = psql(f"select count(*) from {table}")
    return int(v) if v.isdigit() else -1


def live_status() -> dict:
    s: dict = {"diambil": f"{datetime.now():%Y-%m-%d %H:%M}"}
    s["layanan"] = [dict(zip(("nama", "status"), l.split("\t")))
                    for l in sh(f"cd {LIVE} && sudo -n docker compose -p openmetadata ps --format '{{{{.Service}}}}\t{{{{.Status}}}}'").splitlines()]
    m = re.search(r"openmetadata/server:([\w.]+)", (LIVE / "compose.yaml").read_text())
    s["versi_om"] = m.group(1) if m else "?"
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
    for f in (DATA / "secrets/openmetadata.env",):
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
                   if l.startswith("OM_TOKEN="))
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
    b = sorted((DATA / "backup").glob("*.dump"))
    s["backup_terakhir"] = b[-1].name if b else "-"
    s["jumlah_backup"] = len(b)
    rep = sorted((DATA / "reports").glob("workbook-defects-*.md"))
    s["cacat"] = {}
    if rep:
        for line in rep[-1].read_text().splitlines():
            if m := re.match(r"^### (.+) \((\d+)\)", line):
                s["cacat"][m.group(1)] = int(m.group(2))
        s["laporan_cacat"] = rep[-1].name
    s["panel_akun"] = sum(1 for l in (DATA / "secrets/unduh.htpasswd").read_text().splitlines() if ":" in l) \
        if (DATA / "secrets/unduh.htpasswd").exists() else 0
    return s


def dataset_view(rel_dir: Path) -> list[dict]:
    """Ringkasan per dataset bisnis untuk pengguna: ada/belum, dipakai di layar mana, oleh unit mana."""
    import csv
    rd = lambda n: list(csv.DictReader((rel_dir / f"{n}.csv").open(encoding="utf-8-sig")))  # noqa: E731
    kamus, lin = rd("gold_kamus_data"), rd("gold_lineage")
    bronze = MEDALLION / "work" / rel_dir.name / "silver" / "Business_Dataset.csv"
    out = []
    for d in csv.DictReader(bronze.open(encoding="utf-8-sig")):
        ks = [k for k in kamus if k["dataset"] == d["BUSINESS_DATASET"]]
        tabel = sorted({k["tabel"] for k in ks if k["tabel"]})
        layar = sorted({l["layar_tujuan"] for l in lin if l["dataset"] == d["BUSINESS_DATASET"]})
        pengguna = sorted({u for k in ks for u in k["unit_pengguna"].split("; ") if u})
        pemilik = sorted({u for k in ks for u in k["unit_pemilik"].split("; ") if u})
        out.append({"dataset": d["BUSINESS_DATASET"], "domain": d["BUSINESS_DOMAIN"], "sistem": d["SYSTEM_NAME"],
                    "status": "Tersedia" if tabel else "Belum ada", "tabel": tabel, "layar": layar,
                    "pemilik": pemilik, "pengguna": pengguna})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", default=str(WORKBOOK))
    ap.add_argument("--dry-run", action="store_true", help="tampilkan nomor rilis berikutnya saja")
    ap.add_argument("--preview", metavar="DIR", help="cetak ulang PDF dari build/data.js terakhir ke DIR (tanpa rilis baru)")
    a = ap.parse_args()
    if a.preview:
        rel = json.loads((SRC / "build/manifest.json").read_text())["release"]
        jobs = [{"src": s, "out": f"PREVIEW {rel} {name}.pdf", "title": name} for s, name in DOCS]
        Path(a.preview).mkdir(parents=True, exist_ok=True)
        subprocess.run(["node", str(SRC / "build-pdf.mjs"), a.preview, json.dumps(jobs)], check=True)
        return
    release = next_release()
    print(f"Rilis: {release}")
    if a.dry_run:
        return
    rid = release.replace(" ", "-")
    build = SRC / "build"
    build.mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(DEPLOY / "medallion/build_medallion.py"), "--release", release,
                    "--workbook", a.workbook, "--root", str(MEDALLION),
                    "--manifest-out", str(build / "manifest.json")], check=True)
    data = {
        "rilis": release, "tanggal": f"{datetime.now():%d %B %Y}", "tanggal_iso": f"{datetime.now():%Y-%m-%d}",
        "gold": json.loads((build / "manifest.json").read_text()),
        "live": live_status(),
        "dataset": dataset_view(MEDALLION / "panel/rilis" / rid),
        "alamat": "http://192.168.125.14", "panel": "http://192.168.125.14/unduh/",
    }
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
             "November", "Desember"]
    now = datetime.now()
    data["tanggal"] = f"{now.day} {bulan[now.month - 1]} {now.year}"
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
        "Rilis baru: `python3 docs/manuals/src/rilis.py` (lihat `src/README.md`).\n\n"
        "| Rilis | Dokumen | Ukuran |\n| :-- | :-- | --: |\n" + "\n".join(rows) + "\n")
    print(f"Indeks: {OUT / 'README.md'}")


if __name__ == "__main__":
    main()
