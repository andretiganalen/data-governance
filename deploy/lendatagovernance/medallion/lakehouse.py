#!/usr/bin/env python3
"""Loader lakehouse Len Data Governance → Trino lakekeeper.medallion_repository.

Alur (aturan proyek: semua data aplikasi tinggal di Trino lakehouse):
  BRONZE  setiap berkas unggahan (xlsx/csv) → staging + 1 baris per sheet di bronze_repository
          + baris mentah per sheet di bronze_<sumber>_<sheet> (semua varchar, apa adanya, append).
          Berkas dengan checksum yang sama tidak dimuat dua kali.
  SILVER  dari berkas terbaru tiap sumber yang dikenali → silver_dim_* / silver_fact_* bersih (full refresh).
  GOLD    gabungan siap pakai untuk dashboard → gold_* (full refresh; *_snapshot = riwayat harian).

Sumber yang dikenali: DG_WORKBOOK (workbook tata kelola ERM) dan EGRC (Sumber Data E-GRC).
Berkas lain → Bronze saja (source_system FILE) + header masuk bronze_meta_quarantine untuk ditinjau.

Perintah:
  lakehouse.py ingest <berkas>...      muat ke Bronze lalu bangun ulang Silver/Gold
  lakehouse.py inbox                   proses semua berkas di $DATA/medallion/inbox (dipakai timer)
  lakehouse.py retry                   lengkapi Bronze berstatus PARTIAL (tabel mentah yang tertunda)
  lakehouse.py rebuild                 bangun ulang Silver/Gold dari berkas terbaru di bronze_repository
  lakehouse.py status                  jumlah baris + snapshot terakhir setiap tabel (pembanding DBeaver)

Skema tabel: schema/medallion_repository.sql (sumber kebenaran). Kredensial: $DATA/secrets/trino.env.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "loader")]
import build_medallion as bm  # noqa: E402  silver(), gold() untuk workbook tata kelola
import egrc  # noqa: E402               Silver/Gold E-GRC (ditulis ke CSV sementara, lalu dipetakan)
import workbook as wbmod  # noqa: E402

DATA = Path(os.environ.get("LDG_DATA_DIR", "/srv/lendatagovernance"))
SCHEMA_FILE = HERE / "schema" / "medallion_repository.sql"
REF = HERE / "reference"
CONTRACT_VERSION = "v1.0"
HOLDING = "DEFEND ID"
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
LEVEL_ORDER = {"Low": 1, "Low to Moderate": 2, "Moderate": 3, "Moderate to High": 4, "High": 5}
LEVEL_COLOR = {"Low": "#1E7B34", "Low to Moderate": "#8BC34A", "Moderate": "#F2C200",
               "Moderate to High": "#F28C00", "High": "#DA0000"}
JT = 1_000_000  # nilai E-GRC dalam juta rupiah (asumsi GRC, lihat temuan mutu) → IDR


def log(*a):
    print(*a, flush=True)


# ============================================================== Trino
class Trino:
    def __init__(self):
        import trino
        env = dict(l.strip().split("=", 1) for l in (DATA / "secrets" / "trino.env").read_text().splitlines()
                   if "=" in l and not l.startswith("#"))
        self.catalog, self.schema = env["TRINO_CATALOG"], env["TRINO_SCHEMA"]
        self.conn = trino.dbapi.connect(
            host=env["TRINO_HOST"], port=int(env.get("TRINO_PORT", 443)), user=env["TRINO_USER"], http_scheme="https",
            auth=trino.auth.BasicAuthentication(env["TRINO_USER"], env["TRINO_PASSWORD"]),
            catalog=self.catalog, schema=self.schema, source="lendatagovernance-lakehouse")

    RETRYABLE = ("ICEBERG_COMMIT_ERROR", "ICEBERG_CATALOG_ERROR", "Error processing metadata for table", "Failed to open input stream")

    def q(self, sql: str, attempts: int = 8) -> list:
        """Galat commit/katalog/S3 Lakekeeper yang sementara dicoba ulang (jeda 30 s … 5 menit, total ±20 menit).
        Pernyataan yang gagal commit tidak meninggalkan perubahan, dan DELETE/INSERT loader aman diulang."""
        import time
        for i in range(attempts):
            try:
                cur = self.conn.cursor()
                cur.execute(sql)
                return cur.fetchall()
            except Exception as e:  # noqa: BLE001
                if i + 1 == attempts or not any(k in str(e) for k in self.RETRYABLE):
                    raise
                wait = min(300, 30 * 2 ** i if i < 2 else 60 * i)
                log(f"    … Lakekeeper: {str(e)[:90]} — percobaan {i + 2}/{attempts} dalam {wait} detik")
                time.sleep(wait)

    def fq(self, table: str) -> str:
        return f"{self.catalog}.{self.schema}.{table}"

    def columns(self, table: str) -> list[tuple[str, str]]:
        return [(r[0], r[1]) for r in self.q(
            f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = '{self.schema}' "
            f"AND table_name = '{table}' ORDER BY ordinal_position")]

    def tables(self) -> list[str]:
        return [r[0] for r in self.q(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{self.schema}'")]


def sq(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def lit(v, t: str) -> str:
    t = t.lower().replace(" ", "")
    if v is None or (isinstance(v, str) and v.strip() == "") or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "NULL"
    if t.startswith("varchar"):
        return sq(v)
    if t in ("integer", "bigint"):
        return str(int(round(float(v))))
    if t == "double":
        return repr(float(v))
    if t.startswith("decimal"):
        return f"CAST({sq(v)} AS {t})"
    if t == "boolean":
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        return "TRUE" if str(v).strip().lower() in ("ya", "y", "yes", "true", "1", "t") else "FALSE"
    if t == "date":
        return f"DATE {sq(v.isoformat() if isinstance(v, date) else str(v)[:10])}"
    if t.startswith("timestamp"):
        if isinstance(v, datetime):
            v = v.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f") + " UTC"
        return f"TIMESTAMP {sq(v)}"
    raise ValueError(f"tipe tidak dikenal: {t}")


# ============================================================== skema (berkas SQL = sumber kebenaran)
def load_schema() -> dict[str, dict]:
    out = {}
    for m in re.finditer(r"CREATE TABLE (\w+) \(\n(.*?)\n\)(?:\nCOMMENT '((?:[^']|'')*)')?;", SCHEMA_FILE.read_text(), re.S):
        cols = []
        for line in m.group(2).split("\n"):
            mm = re.match(r"\s+(\w+) (.+?)(?: COMMENT '((?:[^']|'')*)')?,?$", line)
            cols.append((mm.group(1), mm.group(2), (mm.group(3) or "").replace("''", "'")))
        out[m.group(1)] = {"cols": cols, "comment": (m.group(3) or "").replace("''", "'")}
    return out


def norm_type(t: str) -> str:
    return t.lower().replace(" ", "")


def ensure_table(tq: Trino, name: str, spec: dict, live: set[str], managed: bool) -> str:
    want = [(c, norm_type(t)) for c, t, _ in spec["cols"]]
    if name in live:
        have = [(c, norm_type(t)) for c, t in tq.columns(name)]
        if have == want:
            return "sama"
        if not managed and tq.q(f"SELECT count(*) FROM {tq.fq(name)}")[0][0] > 0:
            log(f"  ! {name}: skema berbeda tetapi tabel berisi data dan tidak dikelola loader — dibiarkan")
            return "dibiarkan"
    cols = ",\n".join(f"  {c} {t}" + (f" COMMENT {sq(cm)}" if cm else "") for c, t, cm in spec["cols"])
    tq.q(f"CREATE OR REPLACE TABLE {tq.fq(name)} (\n{cols}\n)" + (f"\nCOMMENT {sq(spec['comment'])}" if spec["comment"] else "")
         + "\nWITH (format = 'PARQUET', format_version = 2)")
    return "direvisi" if name in live else "dibuat"


def insert(tq: Trino, name: str, cols: list[tuple[str, str]], rows: list[dict], max_bytes: int = 600_000) -> None:
    if not rows:
        return
    names = ", ".join(c for c, _ in cols)
    head = f"INSERT INTO {tq.fq(name)} ({names}) VALUES "
    batch, size = [], len(head)
    for r in rows:
        v = "(" + ", ".join(lit(r.get(c), t) for c, t in cols) + ")"
        if batch and (size + len(v) > max_bytes or len(batch) >= 1000):
            tq.q(head + ",\n".join(batch))
            batch, size = [], len(head)
        batch.append(v)
        size += len(v) + 2
    tq.q(head + ",\n".join(batch))


def replace_rows(tq: Trino, name: str, spec: dict, rows: list[dict], where: str | None = None) -> None:
    cols = [(c, t) for c, t, _ in spec["cols"]]
    tq.q(f"DELETE FROM {tq.fq(name)}" + (f" WHERE {where}" if where else ""))
    insert(tq, name, cols, rows)


# ============================================================== BRONZE
def snake(s: str, maxlen: int = 60) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s[:maxlen].strip("_")


def cell_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    return s or None


def read_sheets(path: Path) -> dict[str, tuple[list[str], list[tuple[int, list]]]]:
    """→ {sheet: (header asli, [(no_baris_sumber, [nilai str…])])}. Header = baris pertama (≤10) yang cukup terisi."""
    grids: dict[str, list[list]] = {}
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            grids[ws.title] = [[cell_str(c) for c in r] for r in ws.iter_rows(values_only=True)]
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|") if sample else csv.excel
            grids[path.stem] = [[cell_str(c) for c in r] for r in csv.reader(f, dialect)]
    else:
        raise SystemExit(f"Format tidak didukung: {path.name} (pakai .xlsx atau .csv)")
    out = {}
    for sheet, g in grids.items():
        g = [r for r in g]
        filled = [sum(1 for c in r if c) for r in g[:10]]
        if not filled or max(filled) == 0:
            out[sheet] = ([], [])
            continue
        need = max(2, math.ceil(max(filled) * 0.5))
        h = next(i for i, n in enumerate(filled) if n >= need)
        header = [c or "" for c in g[h]]
        width = max(len(header), max((len(r) for r in g), default=0))
        header += [""] * (width - len(header))
        rows = [(i + 1, (r + [None] * width)[:width]) for i, r in enumerate(g[h + 1:], h + 1) if any(r)]
        out[sheet] = (header, rows)
    return out


def column_names(header: list[str]) -> list[str]:
    out, seen = [], Counter()
    for i, h in enumerate(header, 1):
        n = snake(h) or f"c{i:02d}"
        if n[0].isdigit() or n.startswith("_"):
            n = "c_" + n.lstrip("_")
        seen[n] += 1
        out.append(n if seen[n] == 1 else f"{n}_{seen[n]}")
    return out


def detect_source(sheets: dict) -> str:
    names = set(sheets)
    if {"Data_Element_Attribute", "Data_Flow_Lineage", "Master_Organization"} <= names:
        return "DG_WORKBOOK"
    if {"R_Risk Register", "R_Risk Strategy Matrix"} <= names:
        return "EGRC"
    return "FILE"


def baseline_headers(schema: dict) -> set[str]:
    hs = set()
    for spec in schema.values():
        for _, _, cm in spec["cols"]:
            m = re.match(r"baseline header '(.+)'", cm)
            if m:
                hs.add(m.group(1).strip().upper())
    return hs


CREATE_BROKEN: list[str] = []  # katalog menolak tabel baru di batch ini → sheet berikutnya langsung ditunda


def ingest(tq: Trino, path: Path, schema: dict, batch_id: str, now: datetime, name: str | None = None) -> dict | None:
    name = name or path.name
    raw = path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    file_id = checksum[:16]
    prev = dict(tq.q(f"SELECT source_object, max(ingestion_status) FROM {tq.fq('bronze_repository')} "
                     f"WHERE file_checksum = {sq(checksum)} GROUP BY 1"))
    sheets = read_sheets(path)
    todo = [sh for sh, (h, _) in sheets.items() if h and prev.get(sh) != "SUCCESS"]
    if not todo:
        log(f"  = {name}: sudah pernah dimuat (file_id {file_id}) — Bronze dilewati")
        return None
    if prev:
        log(f"  … {name}: melanjutkan — {len(prev) - sum(1 for s in prev if s in todo)} sheet sudah ada, {len(todo)} sheet tersisa")
        undone = ", ".join(sq(s) for s in todo)
        tq.q(f"DELETE FROM {tq.fq('bronze_repository')} WHERE file_checksum = {sq(checksum)} AND source_object IN ({undone})")
        tq.q(f"DELETE FROM {tq.fq('bronze_meta_quarantine')} WHERE file_id = {sq(file_id)} AND source_object IN ({undone})")
    source = detect_source(sheets)
    staging = DATA / "medallion" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    staged = staging / f"{file_id}__{name}"
    if not staged.exists():
        shutil.copy2(path, staged)
    known = baseline_headers(schema) if source == "DG_WORKBOOK" else None
    fields = []
    if source == "FILE":
        fields = tq.q(f"SELECT field_id, column_name, business_term FROM {tq.fq('silver_dim_meta_field')}")
    prefix = {"DG_WORKBOOK": "bronze_dg_workbook", "EGRC": "bronze_egrc"}.get(source) or f"bronze_file_{snake(path.stem, 30)}"
    live = set(tq.tables())
    for sheet, (header, rows) in sheets.items():
        if sheet not in todo:
            continue
        table = f"{prefix}_{snake(sheet, 40)}"[:100]
        names = column_names(header)
        cols = [("_row_no", "integer")] + [(n, "varchar") for n in names] + [
            ("_file_id", "varchar"), ("_batch_id", "varchar"), ("_source_file", "varchar"),
            ("_ingested_at", "timestamp(6) with time zone")]
        raw_ok = True
        if table not in live:
            spec = ",\n".join(f"  {c} {t}" + (f" COMMENT {sq('header asli: ' + h)}" if h else "")
                              for (c, t), h in zip(cols, [""] + header + ["", "", "", ""]))
            if CREATE_BROKEN:
                raw_ok = False
            else:
                try:
                    tq.q(f"CREATE TABLE {tq.fq(table)} (\n{spec}\n) COMMENT {sq(f'Bronze mentah: {source} / {sheet}')}"
                         f"\nWITH (format = 'PARQUET', format_version = 2)")
                except Exception as e:  # noqa: BLE001  — katalog (Lakekeeper) menolak tabel baru
                    CREATE_BROKEN.append(str(e)[:200])
                    raw_ok = False
                    log(f"  ! {table}: tabel baru gagal dibuat ({str(e)[:120]}) — sheet ini dan berikutnya ditunda (PARTIAL)")
        else:
            have = {c for c, _ in tq.columns(table)}
            for c, t in cols:
                if c not in have:
                    tq.q(f"ALTER TABLE {tq.fq(table)} ADD COLUMN {c} {t}")
            # pemuatan sebelumnya yang terputus (belum tercatat di bronze_repository) → buang sisanya dulu
            tq.q(f"DELETE FROM {tq.fq(table)} WHERE _file_id = {sq(file_id)}")
        recs = [{"_row_no": no, **dict(zip(names, vals)), "_file_id": file_id, "_batch_id": batch_id,
                 "_source_file": name, "_ingested_at": now} for no, vals in rows]
        if raw_ok:
            insert(tq, table, cols, recs)
        q_here = []
        for h, n, i in zip(header, names, range(len(names))):
            if not h:
                continue
            if known is not None and h.strip().upper() in known:
                continue
            if source == "EGRC":
                continue  # header E-GRC dipetakan oleh egrc.py (kode X0xx di kerangka)
            sug, score = None, 0.0
            for fid, col, term in fields:
                for cand in (col, term):
                    if cand:
                        s = SequenceMatcher(None, snake(h), snake(cand)).ratio()
                        if s > score:
                            sug, score = fid, s
            samples = [v[i] for _, v in rows if i < len(v) and v[i]][:5]
            q_here.append({"file_id": file_id, "batch_id": batch_id, "source_system": source, "source_object": sheet,
                           "source_locator": f"{sheet}!kolom {i + 1}", "source_header": h, "normalized_header": n,
                           "suggested_field_id": sug if score >= 0.6 else None, "suggestion_score": round(score, 2),
                           "sample_values": " | ".join(samples)[:500], "review_status": "OPEN", "ingested_at": now})
        insert(tq, "bronze_meta_quarantine", [(c, t) for c, t, _ in schema["bronze_meta_quarantine"]["cols"]], q_here)
        insert(tq, "bronze_repository", [(c, t) for c, t, _ in schema["bronze_repository"]["cols"]], [{
            "file_id": file_id, "batch_id": batch_id, "source_system": source, "source_object": sheet,
            "source_format": path.suffix.lower().lstrip("."), "file_name": name, "file_path": str(staged),
            "file_size_bytes": len(raw), "file_checksum": checksum, "row_count": len(rows),
            "header_mapped_count": sum(1 for h in header if h) - len(q_here), "header_quarantined_count": len(q_here),
            "target_bronze_table": table, "ingestion_status": "SUCCESS" if raw_ok else "PARTIAL", "is_processed_to_silver": source != "FILE",
            "contract_version": CONTRACT_VERSION, "ingested_at": now}])  # dicatat per sheet → bisa dilanjutkan
        log(f"  {'+' if raw_ok else '~'} {table}: {len(rows)} baris" + ("" if raw_ok else " (ditunda: PARTIAL)")
            + (f", {len(q_here)} header dikarantina" if q_here else ""))
    return {"source": source, "file_id": file_id, "staged": staged}


def latest_sources(tq: Trino) -> dict[str, dict]:
    rows = tq.q(f"SELECT source_system, file_id, file_path, file_name, max(ingested_at) FROM {tq.fq('bronze_repository')} "
                f"WHERE source_system IN ('DG_WORKBOOK', 'EGRC') AND ingestion_status IN ('SUCCESS', 'PARTIAL') "
                f"GROUP BY 1, 2, 3, 4 ORDER BY 5 DESC")
    out = {}
    for src, fid, fpath, fname, _ in rows:
        if src not in out and Path(fpath).exists():
            out[src] = {"file_id": fid, "path": Path(fpath), "name": fname}
    return out


# ============================================================== helpers
def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def ival(v):
    n = num(v)
    return None if n is None else int(round(n))


def money(v):
    n = num(v)
    return None if n is None else n * JT


def per_date(periode_key: str | None, year: int):
    if periode_key:
        y, m = int(periode_key[:4]), int(periode_key[4:6])
        return date(y, m, 1), m
    return date(year, 1, 1), None


def time_cols(d: date, month: int | None) -> dict:
    return {"period_date": d, "date_key": int(d.strftime("%Y%m%d")), "period_month": month,
            "month_name": BULAN[month - 1] if month else None, "quarter_label": f"TW{(month - 1) // 3 + 1}" if month else None}


def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as f:
        return [{k: (v if v != "" else None) for k, v in r.items()} for r in csv.DictReader(f)]


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def slug(s):
    return snake(s or "", 40) or None


# ============================================================== SILVER + GOLD: workbook tata kelola
DQ_DIMENSION = {"Not Null": "Completeness", "Lookup": "Consistency", "Lookup/Cross Validation": "Consistency",
                "≥ Tanggal Mulai": "Consistency", "Auto Calculated": "Accuracy"}
DQ_DIMENSIONS = [
    ("DQ01", "Completeness", "Kelengkapan", "Data wajib terisi.", "Nilai kosong/NULL pada kolom wajib"),
    ("DQ02", "Uniqueness", "Keunikan", "Tidak ada duplikat pada kunci.", "Duplikat pada kolom kunci"),
    ("DQ03", "Validity", "Keabsahan", "Nilai sesuai format, tipe, dan rentang.", "Format, rentang, daftar nilai"),
    ("DQ04", "Consistency", "Konsistensi", "Nilai konsisten antar tabel/sistem.", "Referensi (lookup) dan aturan lintas kolom"),
    ("DQ05", "Accuracy", "Akurasi", "Nilai sesuai kenyataan/sumber resmi.", "Perbandingan dengan sumber resmi, hasil hitung"),
    ("DQ06", "Timeliness", "Ketepatan waktu", "Data tersedia tepat waktu.", "Umur data dibanding periode lapor"),
]


def build_meta(path: Path, file_id: str, L: dict, snap: date) -> dict[str, list[dict]]:
    raw = wbmod.read_xlsx(str(path))
    s = bm.silver(raw)
    g = bm.gold(s)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    T: dict[str, list[dict]] = {}

    dea = s["Data_Element_Attribute"]
    tables = {t["TABLE_ID"]: t for t in s["Database_Object"]}
    datasets = {d["DATASET_ID"]: d for d in s["Business_Dataset"]}
    gloss = {x["FIELD_ID"]: x for x in s["Business_Glossary"]}
    rank = wbmod.SENSITIVITY_RANK
    cls = {}
    for a in s["Data_Security_Access"]:
        c = a["CLASSIFICATION"]
        if c in rank and rank[c] >= rank.get(cls.get(a["FIELD_ID"]), -1):
            cls[a["FIELD_ID"]] = c
    roles = defaultdict(lambda: defaultdict(list))
    for a in s["Data_Governance_Assignment"]:
        u = " ".join(x for x in (a["ORG_ID"], a["UNIT KERJA"]) if x)
        if u not in roles[a["FIELD_ID"]][a["ROLE"]]:
            roles[a["FIELD_ID"]][a["ROLE"]].append(u)

    def sys_of_table(tid):
        d = datasets.get((tables.get(tid) or {}).get("DATASET_ID"), {})
        return d.get("SYSTEM_NAME") or None

    T["silver_dim_meta_system"] = [{"system_id": r["SYSTEM_ID"], "system_name": r["SYSTEM_NAME"], "description": r["DESCRIPTION"], **L}
                                   for r in s["Master_System"]]
    T["silver_dim_meta_dataset"] = [{"dataset_id": r["DATASET_ID"], "dataset_name": r["BUSINESS_DATASET"], "business_dataset": r["BUSINESS_DATASET"],
                                     "business_domain": r["BUSINESS_DOMAIN"], "system_id": r["SYSTEM_ID"], "system_name": r["SYSTEM_NAME"],
                                     "data_domain_id": "DOM-" + (slug(r["BUSINESS_DOMAIN"]) or "na").upper(), "data_domain": r["BUSINESS_DOMAIN"],
                                     "data_asset_status": "Aktif", **L} for r in s["Business_Dataset"]]
    T["silver_dim_meta_table"] = [{"table_id": r["TABLE_ID"], "dataset_id": r["DATASET_ID"], "dataset_name": r["DATASET_NAME"],
                                   "table_name": r["TABLE_NAME"], "object_type": r["OBJECT_TYPE"], "database_name": "ERM",
                                   "sensitive_data_flag": any(rank.get(cls.get(f["FIELD_ID"]), 0) >= 2 for f in dea if f["TABLE_ID"] == r["TABLE_ID"]),
                                   "source_system": sys_of_table(r["TABLE_ID"]), **L} for r in s["Database_Object"]]
    T["silver_dim_meta_field"] = [{"field_id": r["FIELD_ID"], "table_id": r["TABLE_ID"], "table_name": r["TABLE_NAME"] or (tables.get(r["TABLE_ID"]) or {}).get("TABLE_NAME"),
                                   "column_name": r["COLUMN_NAME"], "data_dictionary_description": (gloss.get(r["FIELD_ID"]) or {}).get("DEFINISI"),
                                   "business_term": r["BUSINESS_TERM"], "data_type": r["DATA_TYPE"],
                                   "sensitive_flag": rank.get(cls.get(r["FIELD_ID"]), 0) >= 2 if r["FIELD_ID"] in cls else None,
                                   "metadata_status": "Perlu dilengkapi" if r["catatan_mutu"] else "Lengkap",
                                   "source_system": sys_of_table(r["TABLE_ID"]), **L} for r in dea]
    T["silver_dim_meta_glossary"] = [{"field_id": r["FIELD_ID"], "business_term": r["BUSINESS_TERM"], "definisi": r["DEFINISI"],
                                      "owner": "; ".join(roles[r["FIELD_ID"]].get("Data Owner", [])) or None,
                                      "steward": "; ".join(roles[r["FIELD_ID"]].get("Data Steward", [])) or None,
                                      "status": "Tersedia" if r["DEFINISI"] else "Belum ada",
                                      "source_reference": path.name, **L} for r in s["Business_Glossary"]]
    T["silver_dim_meta_governance_assignment"] = [{"field_id": r["FIELD_ID"], "field_name": r["FIELD_NAME"], "business_term": r["BUSINESS_TERM"],
                                                   "role": r["ROLE"], "org_id": r["ORG_ID"], "unit_kerja": r["UNIT KERJA"],
                                                   "role_status": "Aktif", **L} for r in s["Data_Governance_Assignment"]]
    by_field = {f["FIELD_ID"]: f for f in dea}
    T["silver_dim_meta_dq_rule"] = [{"field_id": r["FIELD_ID"], "field_name": r["FIELD_NAME"], "business_term": r["BUSINESS_TERM"],
                                     "rule": r["RULE"], "validation": r["VALIDATION"], "dq_rule_id": f"DQR{i:03d}",
                                     "dq_dimension": DQ_DIMENSION.get(r["VALIDATION"], "Validity"),
                                     "target_table": (by_field.get(r["FIELD_ID"]) or {}).get("TABLE_NAME"),
                                     "target_column": (by_field.get(r["FIELD_ID"]) or {}).get("COLUMN_NAME"),
                                     "rule_type": "Otomatis" if wbmod.dq_test(r["VALIDATION"] or "") else "Manual",
                                     "remediation_status": "Belum dijalankan", **L}
                                    for i, r in enumerate(s["Data_Quality_Rules"], 1)]
    T["silver_dim_meta_lineage"] = [{"lineage_id": r["LINEAGE_ID"], "system_id": r["SYSTEM_ID"], "system_name": r["SYSTEM_NAME"],
                                     "table_id": r["TABLE_ID"], "table_name": r["TABLE_NAME"], "field_id": r["FIELD_ID"],
                                     "field_name": r["FIELD_NAME"], "target_asset": r["TARGET_ASSET"], "target_label": r["TARGET_LABEL"],
                                     "asset_type": r["ASSET_TYPE"], "source_system": r["SYSTEM_NAME"], "source_database": "ERM",
                                     "source_table": r["TABLE_NAME"], "source_column": r["FIELD_NAME"], "lineage_type": "Kolom → Layar",
                                     "target_system": "LenO", "target_table": r["TARGET_ASSET"], "target_column": r["TARGET_LABEL"],
                                     "status": "Aktif", **L} for r in s["Data_Flow_Lineage"]]
    T["silver_dim_meta_access"] = [{"access_id": r["ACCESS_ID"], "lineage_id": r["LINEAGE_ID"], "target_asset": r["TARGET_ASSET"],
                                    "target_label": r["TARGET_LABEL"], "field_id": r["FIELD_ID"], "field_name": r["FIELD_NAME"],
                                    "org_id": r["ORG_ID"], "unit_kerja": r["UNIT_KERJA"], "classification": r["CLASSIFICATION"],
                                    "permission_category": r["PERMISSION_CATEGORY"], "permission_type": r["PERMISSION_TYPE"], **L}
                                   for r in s["Data_Security_Access"]]
    lib = []
    for r in raw.get("Library", []):
        for grp in ("Data Type", "Role", "Object", "Asset Type", "Classification", "Permission Category", "Permission Type"):
            item = bm.clean(r.get(grp))
            if item and not any(x["library_group"] == grp and x["item"] == item for x in lib):
                lib.append({"library_group": grp, "item": item, "deskripsi": bm.clean(r.get("Deskripsi")) if grp == "Data Type" else None,
                            "permission_category": bm.clean(r.get("Permission Category")) if grp == "Permission Type" else None, **L})
    T["silver_dim_meta_library"] = lib
    T["silver_dim_organization"] = [{"org_id": r["ORG_ID"], "fungsi": r["FUNGSI"], "unit_kerja": r["UNIT_KERJA"],
                                     "divisi_id": slug(r["DIVISI"]), "divisi": r["DIVISI"], "direktorat_id": slug(r["DIREKTORAT"]),
                                     "direktorat": r["DIREKTORAT"], "company_id": "COMP-LEN-001",
                                     "valid_from": snap, "valid_to": date(9999, 12, 31), "is_current": True, **L}
                                    for r in s["Master_Organization"]]
    rules_by_field = Counter(r["FIELD_ID"] for r in s["Data_Quality_Rules"])
    dom = []
    for d in sorted({x["BUSINESS_DOMAIN"] for x in s["Business_Dataset"] if x["BUSINESS_DOMAIN"]}):
        ds = [x for x in s["Business_Dataset"] if x["BUSINESS_DOMAIN"] == d]
        tids = {t["TABLE_ID"] for t in s["Database_Object"] if t["DATASET_ID"] in {x["DATASET_ID"] for x in ds}}
        fs = [f["FIELD_ID"] for f in dea if f["TABLE_ID"] in tids]
        dom.append({"data_domain_id": "DOM-" + slug(d).upper(), "data_domain": d,
                    "system_count": len({x["SYSTEM_ID"] for x in ds if x["SYSTEM_ID"]}), "dataset_count": len(ds),
                    "table_count": len(tids), "field_count": len(fs), "dq_rule_count": sum(rules_by_field[f] for f in fs),
                    "dq_coverage": pct(sum(1 for f in fs if rules_by_field[f]), len(fs)), "domain_status": "Aktif", **L})
    T["silver_dim_meta_data_domain"] = dom
    T["silver_dim_meta_dq_dimension"] = [{"dq_id": a, "dimension": b, "sub_dimension": c, "definition": d, "what_to_check": e, **L}
                                         for a, b, c, d, e in DQ_DIMENSIONS]
    T["silver_dim_meta_kpi"] = [{"kpi_id": f"KPI{i:02d}", "kpi_name": k["indikator"], "category": k["kategori"], "definition": k["indikator"],
                                 "target": None, "frequency": "Setiap muat", "data_source": "Workbook tata kelola (DG_WORKBOOK)",
                                 "owner": "Staf DG (UV-1)", "status": "Aktif", **L} for i, k in enumerate(g["gold_kpi_tata_kelola"], 1)]
    corr, n = [], 0
    for sheet, rows in s.items():
        for r in rows:
            if r.get("catatan_mutu"):
                n += 1
                key = next((f"{k}={v}" for k, v in r.items() if k.endswith("_ID") and v), None)
                corr.append({"correction_id": f"BC{n:04d}", "baseline_file": path.name, "baseline_sha256": sha, "sheet_name": sheet,
                             "cell_range": key, "issue_type": r["catatan_mutu"], "decision": "OPEN", "decision_role": "Staf DG (UV-1)",
                             "note": "Perbaiki di workbook sumber lalu unggah ulang.", **L})
    T["silver_fact_meta_baseline_correction"] = corr

    # ---- Gold metadata (dari build_medallion.gold, nama kolom distandarkan)
    def ren(rows, m, extra=None):
        out = []
        for r in rows:
            o = {new: r.get(old) for old, new in m.items()}
            if extra:
                o.update(extra(o))
            out.append({**o, "_batch_id": L["_batch_id"], "_loaded_at": L["_loaded_at"]})
        return out
    yn = lambda v: None if v is None else v == "Ya"  # noqa: E731
    T["gold_meta_data_dictionary"] = ren(g["gold_kamus_data"], {
        "field_id": "field_id", "sistem": "system_name", "domain_bisnis": "business_domain", "dataset": "dataset_name", "tabel": "table_name",
        "kolom": "column_name", "istilah_bisnis": "business_term", "definisi": "definition", "tipe_data": "data_type", "sensitivitas": "classification",
        "unit_pemilik": "owner_unit", "unit_steward": "steward_unit", "unit_pengguna": "user_units", "jumlah_aturan_mutu": "dq_rule_count",
        "aturan_mutu": "dq_rules", "jumlah_layar_hilir": "downstream_screen_count", "ada_tabel": "has_table", "ada_definisi": "has_definition",
        "ada_klasifikasi": "has_classification", "ada_pemilik": "has_owner"},
        lambda o: {**{k: yn(o[k]) for k in ("has_table", "has_definition", "has_classification", "has_owner")},
                   "completeness_pct": 25.0 * sum(1 for k in ("has_table", "has_definition", "has_classification", "has_owner") if o[k] == "Ya")})
    T["gold_meta_table_summary"] = ren(g["gold_ringkasan_tabel"], {
        "tabel": "table_name", "table_id": "table_id", "dataset": "dataset_name", "domain_bisnis": "business_domain", "sistem": "system_name",
        "jumlah_kolom": "column_count", "kolom_confidential": "confidential_column_count", "sensitivitas_tertinggi": "highest_classification",
        "unit_pemilik": "owner_unit", "jumlah_layar_hilir": "downstream_screen_count", "pct_definisi": "definition_pct", "jumlah_aturan_mutu": "dq_rule_count"})
    T["gold_meta_screen_summary"] = ren(g["gold_ringkasan_layar"], {
        "modul": "module", "layar": "screen", "jumlah_field": "field_count", "tabel_sumber": "source_tables", "jumlah_tabel_sumber": "source_table_count",
        "dataset_sumber": "source_datasets", "sensitivitas_tertinggi": "highest_classification", "jumlah_unit_boleh_lihat": "units_can_view",
        "jumlah_unit_boleh_ubah": "units_can_edit", "unit_pemilik": "owner_unit"})
    T["gold_meta_lineage"] = ren(g["gold_lineage"], {
        "lineage_id": "lineage_id", "sistem": "system_name", "domain_bisnis": "business_domain", "dataset": "dataset_name", "tabel": "table_name",
        "kolom": "column_name", "field_id": "field_id", "istilah_bisnis": "business_term", "modul": "module", "layar_tujuan": "target_screen",
        "label_di_layar": "target_label", "jenis_aset": "asset_type", "sensitivitas": "classification"})
    T["gold_meta_access_matrix"] = ren(g["gold_hak_akses"], {
        "access_id": "access_id", "layar": "screen", "label_di_layar": "screen_label", "field_id": "field_id", "kolom": "column_name",
        "org_id": "org_id", "unit_kerja": "unit_kerja", "divisi": "divisi", "direktorat": "direktorat", "sensitivitas": "classification",
        "kategori_izin": "permission_category", "jenis_izin": "permission_type"})
    T["gold_meta_glossary"] = ren(g["gold_glosarium"], {
        "field_id": "field_id", "istilah_bisnis": "business_term", "definisi": "definition", "status_definisi": "definition_status",
        "unit_pemilik": "owner_unit", "unit_steward": "steward_unit", "unit_pengguna": "user_units", "jumlah_kolom": "column_count",
        "jumlah_layar": "screen_count", "sensitivitas": "classification"})
    T["gold_meta_dq_rule"] = ren(g["gold_aturan_mutu"], {
        "field_id": "field_id", "kolom": "column_name", "istilah_bisnis": "business_term", "aturan": "rule", "validasi": "validation",
        "jenis_uji": "test_type", "status_eksekusi": "execution_status"})
    T["gold_meta_governance_kpi_snapshot"] = [{"snapshot_date": snap, "kpi_category": k["kategori"], "kpi_name": k["indikator"],
                                               "kpi_value": num(k["nilai"]), "unit": k["satuan"], "_batch_id": L["_batch_id"],
                                               "_loaded_at": L["_loaded_at"]} for k in g["gold_kpi_tata_kelola"]]
    notes = Counter((c["sheet_name"], c["issue_type"]) for c in corr)
    T["_dq_findings"] = [{"snapshot_date": snap, "source_system": "DG_WORKBOOK", "finding_code": f"DGW-Q{i:02d}", "finding_category": "Kelengkapan",
                          "severity": "Sedang", "sheet_name": sh, "affected_rows": cnt, "description": note, "example": None,
                          "etl_action": "Dimuat apa adanya, ditandai di silver_fact_meta_baseline_correction.",
                          "follow_up_owner": "Staf DG (UV-1)", "_batch_id": L["_batch_id"], "_loaded_at": L["_loaded_at"]}
                         for i, ((sh, note), cnt) in enumerate(sorted(notes.items()), 1)]
    return T


# ============================================================== SILVER + GOLD: E-GRC
def build_erm(tq: Trino, path: Path, L: dict, snap: date) -> dict[str, list[dict]]:
    with tempfile.TemporaryDirectory() as tmp:
        work, gdir = Path(tmp) / "work", Path(tmp) / "gold"
        egrc.run(str(path), snap.strftime("%y%m%d") + " LH", work, gdir)
        S = {p.stem: read_csv(p) for p in (work / "silver" / "egrc").glob("*.csv")}
        temuan = read_csv(gdir / "gold_grc_temuan_mutu.csv")

    ent = {e["entitas_key"]: e for e in csv.DictReader((REF / "entitas.csv").open(encoding="utf-8"))}
    master = {r[0]: (r[1], r[2]) for r in tq.q(   # dimensi perusahaan bersama (kerangka SDM/korporasi, sdm.py)
        f"SELECT company_id, company_name, company_acronym FROM {tq.fq('silver_dim_company_information')} "
        "WHERE company_id LIKE 'COMP-%'")} if "silver_dim_company_information" in set(tq.tables()) else {}

    def comp(ek: str | None, year: int | None) -> dict:
        e = ent.get(ek or "DID", {})
        cid = e.get("company_id") or f"EGRC-{ek}"
        name, acr = master.get(cid, (e.get("entitas_nama"), ek))
        return {"fiscal_year": year, "company_id": cid, "company_name": name, "company_acronym": acr, "holding_name": HOLDING}

    T: dict[str, list[dict]] = {}
    tail = {"_batch_id": L["_batch_id"], "_loaded_at": L["_loaded_at"]}
    scd = {"valid_from": snap, "valid_to": date(9999, 12, 31), "is_current": True}
    tax = {t["taksonomi_key"]: t["taksonomi_nama"] for t in csv.DictReader((REF / "grc_taksonomi.csv").open(encoding="utf-8"))}
    risks = S["silver_dim_grc_risiko"]
    rk = {r["risiko_key"]: r for r in risks}
    sas = {x["sasaran_key"]: x for x in S["silver_dim_grc_sasaran_strategis"]}
    cid_of = {r["risiko_key"]: comp(r["entitas_key"], ival(r["rkap_tahun"]))["company_id"] for r in risks}

    # ---- Silver
    d0 = date(2024, 1, 1)
    days = []
    for i in range((date(2027, 12, 31) - d0).days + 1):
        d = d0 + timedelta(days=i)
        nxt = d + timedelta(days=1)
        days.append({"date_key": int(d.strftime("%Y%m%d")), "full_date": d, "period_year": d.year, "period_quarter": (d.month - 1) // 3 + 1,
                     "period_semester": (d.month - 1) // 6 + 1, "period_month": d.month,
                     "month_name_id": ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
                                       "Oktober", "November", "Desember"][d.month - 1], "month_short_id": BULAN[d.month - 1],
                     "year_month": d.strftime("%Y-%m"), "quarter_label": f"TW{(d.month - 1) // 3 + 1}", "day_of_month": d.day,
                     "day_of_week": d.isoweekday(), "day_name_id": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][d.weekday()],
                     "week_of_year": d.isocalendar()[1], "is_month_start": d.day == 1, "is_month_end": nxt.month != d.month,
                     "is_weekend": d.weekday() >= 5, "is_holiday_id": None, "fiscal_year": d.year, "rkap_label": f"RKAP {d.year}"})
    T["silver_dim_date"] = days
    T["silver_dim_fx_rate"] = [{"currency_code": "IDR", "rate_date": date(2024, 1, 1), "fx_rate_to_idr": 1.0,
                                "rate_source": "Konstanta (sumber E-GRC dalam IDR)", **L}]
    T["silver_dim_erm_risk_taxonomy"] = [{"risk_taxonomy_id": k, "main_category": v, **scd, **L} for k, v in tax.items()]
    T["silver_dim_erm_risk_matrix"] = [{"risk_matrix_id": m["matriks_key"], "skor_dampak": ival(m["dampak_skor"]),
                                        "skor_kemungkinan": ival(m["kemungkinan_skor"]), "tingkat_risiko": ival(m["skala_risiko_nilai"]),
                                        "kategori_tingkat_risiko": m["level_risiko_kategori"],
                                        "kategori_tingkat_risiko_color_hex": LEVEL_COLOR.get(m["level_risiko_kategori"]), **scd, **L}
                                       for m in S["silver_dim_grc_matriks_risiko"]]
    first_risk = {}
    for r in risks:
        first_risk.setdefault(r["sasaran_key"], r)
    T["silver_dim_erm_objective"] = [{"objective_id": k, "company_id": cid_of[first_risk[k]["risiko_key"]] if k in first_risk else None,
                                      "fiscal_year": ival(first_risk[k]["rkap_tahun"]) if k in first_risk else None,
                                      "nama_sasaran": x["sasaran_tema_nama"], "keterangan_sasaran": x["sasaran_uraian"], **scd, **L}
                                     for k, x in sas.items()]
    T["silver_dim_erm_objective_basis"] = [{"objective_basis_id": "OB-" + slug(t).upper(), "nama_sasaran": t, **scd, **L}
                                           for t in sorted({x["sasaran_tema_nama"] for x in sas.values() if x["sasaran_tema_nama"]})]
    T["silver_dim_erm_risk"] = [{"risk_id": r["risiko_kode"], "company_id": cid_of[r["risiko_key"]], "objective_id": r["sasaran_key"],
                                 "fiscal_year": ival(r["rkap_tahun"]), "main_category": tax.get(r["taksonomi_key"]),
                                 "keterangan_sasaran": (sas.get(r["sasaran_key"]) or {}).get("sasaran_uraian"),
                                 "peristiwa_risiko": r["risiko_nama"], "asumsi_dampak": r["dampak_asumsi_uraian"],
                                 "deskripsi_dampak": r["dampak_uraian"], **scd, **L} for r in risks]
    causes = S["silver_dim_grc_penyebab"]
    T["silver_dim_erm_risk_cause"] = [{"risk_cause_id": c["penyebab_key"], "risk_id": rk[c["risiko_key"]]["risiko_kode"],
                                       "cause_seq": ival(c["penyebab_kode"]), "penyebab": c["penyebab_uraian"], **scd, **L}
                                      for c in causes if c["risiko_key"] in rk]
    T["silver_fact_erm_risk_appetite"] = [{"company_id": comp(a["entitas_key"], None)["company_id"], "period_year": ival(a["rkap_tahun"]),
                                           "date_key": ival(a["rkap_tahun"]) * 10000 + 101 if a["rkap_tahun"] else None,
                                           "plan_label": f"RKAP {a['rkap_tahun']}" if a["rkap_tahun"] else None,
                                           "nilai_kapasitas_risiko": money(a["kapasitas_risiko_jt_idr"]), "nilai_selera_risiko": money(a["selera_risiko_jt_idr"]),
                                           "nilai_toleransi_risiko": money(a["toleransi_risiko_jt_idr"]), "nilai_batasan_risiko": money(a["limit_risiko_jt_idr"]),
                                           "currency_code": "IDR", "fx_rate_to_idr": 1.0, "amount_unit": "IDR", **L}
                                          for a in S["silver_fact_grc_ambang_risiko_tahunan"] if a["entitas_key"]]
    jenis = {"INHEREN": "INHEREN", "TARGET": "TARGET_RESIDUAL", "REALISASI": "REALISASI"}
    asm = []
    for p in S["silver_fact_grc_penilaian_risiko"]:
        r = rk.get(p["risiko_key"])
        if not r:
            continue
        y = ival(r["rkap_tahun"])
        d, m = per_date(p["periode_key"], y)
        asm.append({"risk_id": r["risiko_kode"], "company_id": cid_of[r["risiko_key"]], "assessment_type": jenis.get(p["penilaian_jenis_kategori"], p["penilaian_jenis_kategori"]),
                    "period_year": d.year, "period_month": m, "date_key": int(d.strftime("%Y%m%d")),
                    "skor_dampak": ival(p["dampak_skor"]), "skor_kemungkinan": ival(p["kemungkinan_skor"]),
                    "tingkat_risiko": ival(p["skala_risiko_nilai"]), "kategori_tingkat_risiko": p["level_risiko_kategori"],
                    "deskripsi_dampak": p["dampak_teks"], "dampak_finansial": money(p["dampak_jt_idr"]) if p["penilaian_jenis_kategori"] == "REALISASI" else None,
                    "currency_code": "IDR", "fx_rate_to_idr": 1.0, "nilai_dampak": money(p["dampak_jt_idr"]),
                    "dampak_terhadap_limit": num(p["dampak_thd_limit_rasio"]), "exposure_risiko": money(p["eksposur_jt_idr"]),
                    "kemungkinan_pct": num(p["kemungkinan_prob"]), "biaya_pengendalian": money(p["biaya_pengendalian_jt_idr"]), **L})
    T["silver_fact_erm_risk_assessment"] = asm
    params = {x["parameter_key"]: x for x in S["silver_dim_grc_parameter_risiko"]}
    kri = []
    for f in S["silver_fact_grc_profil_risiko_bulanan"]:
        p = params.get(f["parameter_key"])
        if not p:
            continue
        d, m = per_date(f["periode_key"], ival(p["rkap_tahun"]))
        kri.append({"kri_id": p["parameter_kode"], "company_id": comp(p["entitas_key"], None)["company_id"], "company_id_is_assumed": not p["entitas_key"],
                    "period_year": d.year, "period_month": m, "date_key": int(d.strftime("%Y%m%d")), "main_category": tax.get(p["taksonomi_key"]),
                    "parameter_kri": p["parameter_nama"], "target_formula_kri": p["parameter_rumus_uraian"],
                    "risk_limit_kri": num(p["ambang_limit_nilai"]), "risk_appetite_range_kri": p["ambang_selera_teks"],
                    "risk_tolerance_kri": num(p["ambang_toleransi_nilai"]), "actual_value_kri": num(f["aktual_nilai"]),
                    "actual_text_kri": f["aktual_teks"], "status_kri": f["profil_status_kategori"], "arah_kri": p["parameter_arah_kategori"], **L})
    T["silver_fact_erm_kri_monthly"] = kri
    plans = S["silver_dim_grc_rencana_pengendalian"]
    T["silver_fact_erm_mitigation_plan_monthly"] = [{"mitigation_plan_id": p["rencana_key"], "risk_id": rk[p["risiko_key"]]["risiko_kode"],
                                                     "risk_cause_id": p["penyebab_key"], "company_id": cid_of[p["risiko_key"]],
                                                     "period_year": ival(rk[p["risiko_key"]]["rkap_tahun"]), "rencana_penanganan": p["rencana_uraian"],
                                                     "currency_code": "IDR", **L} for p in plans if p["risiko_key"] in rk]
    pk = {p["rencana_key"]: p for p in plans}
    prog = []
    for g_ in S["silver_fact_grc_progres_pengendalian_bulanan"]:
        p = pk.get(g_["rencana_key"])
        if not p or p["risiko_key"] not in rk:
            continue
        d, m = per_date(g_["periode_key"], ival(rk[p["risiko_key"]]["rkap_tahun"]))
        prog.append({"mitigation_plan_id": p["rencana_key"], "risk_id": rk[p["risiko_key"]]["risiko_kode"], "company_id": cid_of[p["risiko_key"]],
                     "period_year": d.year, "period_month": m, "date_key": int(d.strftime("%Y%m%d")),
                     "realisasi_penanganan": g_["progres_realisasi_uraian"], "persentase_realisasi": num(g_["progres_rasio"]),
                     "currency_code": "IDR", "pic_fungsi": p["pic_uraian"], **L})
    T["silver_fact_erm_mitigation_realization"] = prog

    # ---- Gold
    risk_info = {}
    for r in risks:
        y = ival(r["rkap_tahun"])
        risk_info[r["risiko_kode"]] = {"c": comp(r["entitas_key"], y), "peristiwa_risiko": r["risiko_nama"],
                                       "main_category": tax.get(r["taksonomi_key"]), "year": y, "key": r["risiko_key"]}
    appetite = {(a["company_id"], a["period_year"]): a for a in T["silver_fact_erm_risk_appetite"]}

    G_asm = []
    for a in asm:
        ri = risk_info[a["risk_id"]]
        d = date(a["period_year"], a["period_month"] or 1, 1)
        G_asm.append({**ri["c"], **time_cols(d, a["period_month"]), "risk_id": a["risk_id"], "peristiwa_risiko": ri["peristiwa_risiko"],
                      "main_category": ri["main_category"], "assessment_type": a["assessment_type"], "skor_dampak": a["skor_dampak"],
                      "skor_kemungkinan": a["skor_kemungkinan"], "kemungkinan_pct": a["kemungkinan_pct"], "tingkat_risiko": a["tingkat_risiko"],
                      "kategori_tingkat_risiko": a["kategori_tingkat_risiko"], "urutan_tingkat": LEVEL_ORDER.get(a["kategori_tingkat_risiko"]),
                      "nilai_dampak": a["nilai_dampak"], "dampak_terhadap_limit": a["dampak_terhadap_limit"],
                      "exposure_risiko": a["exposure_risiko"], **tail})
    T["gold_erm_risk_assessment_monthly"] = G_asm

    cells = defaultdict(list)
    for a in G_asm:
        if a["skor_dampak"] and a["skor_kemungkinan"]:
            cells[(a["company_id"], a["period_date"], a["assessment_type"], a["skor_dampak"], a["skor_kemungkinan"])].append(a)
    T["gold_erm_risk_heatmap_monthly"] = [{**{k: xs[0][k] for k in ("fiscal_year", "company_id", "company_name", "company_acronym", "holding_name",
                                                                    "period_date", "date_key", "period_month", "month_name", "quarter_label")},
                                           "assessment_type": t, "skor_dampak": sd, "skor_kemungkinan": sk, "tingkat_risiko": xs[0]["tingkat_risiko"],
                                           "kategori_tingkat_risiko": xs[0]["kategori_tingkat_risiko"], "urutan_tingkat": xs[0]["urutan_tingkat"],
                                           "warna_hex": LEVEL_COLOR.get(xs[0]["kategori_tingkat_risiko"]), "jumlah_risiko": len(xs),
                                           "daftar_risk_id": ", ".join(sorted(x["risk_id"] for x in xs)),
                                           "total_exposure_risiko": sum(x["exposure_risiko"] or 0 for x in xs), **tail}
                                          for (cid, d, t, sd, sk), xs in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3], kv[0][4]))]

    by_risk = defaultdict(list)
    for a in G_asm:
        by_risk[a["risk_id"]].append(a)
    causes_by = Counter(c["risk_id"] for c in T["silver_dim_erm_risk_cause"])
    plans_by = Counter(p["risk_id"] for p in T["silver_fact_erm_mitigation_plan_monthly"])
    last_prog = {}
    for p in sorted(prog, key=lambda x: x["date_key"]):
        last_prog[p["mitigation_plan_id"]] = p
    prog_by_risk = defaultdict(list)
    for p in last_prog.values():
        prog_by_risk[p["risk_id"]].append(p["persentase_realisasi"])
    reg = []
    for r in risks:
        code = r["risiko_kode"]
        ri = risk_info[code]
        inh = next((a for a in by_risk[code] if a["assessment_type"] == "INHEREN"), {})
        real = [a for a in by_risk[code] if a["assessment_type"] == "REALISASI" and (a["nilai_dampak"] is not None or a["skor_dampak"])]
        last = max(real, key=lambda a: a["period_date"]) if real else {}
        inh_src = next((x for x in asm if x["risk_id"] == code and x["assessment_type"] == "INHEREN"), {})
        sx = sas.get(r["sasaran_key"]) or {}
        reg.append({**ri["c"], "risk_id": code, "objective_id": r["sasaran_key"], "nama_sasaran": sx.get("sasaran_tema_nama"),
                    "keterangan_sasaran": sx.get("sasaran_uraian"), "main_category": ri["main_category"], "peristiwa_risiko": r["risiko_nama"],
                    "deskripsi_dampak": r["dampak_uraian"], "asumsi_dampak": r["dampak_asumsi_uraian"],
                    "skor_dampak_inheren": inh.get("skor_dampak"), "skor_kemungkinan_inheren": inh.get("skor_kemungkinan"),
                    "kemungkinan_pct_inheren": inh.get("kemungkinan_pct"), "tingkat_risiko_inheren": inh.get("tingkat_risiko"),
                    "kategori_tingkat_risiko_inheren": inh.get("kategori_tingkat_risiko"), "urutan_tingkat_inheren": inh.get("urutan_tingkat"),
                    "nilai_dampak_inheren": inh.get("nilai_dampak"), "dampak_terhadap_limit_inheren": inh.get("dampak_terhadap_limit"),
                    "exposure_risiko_inheren": inh.get("exposure_risiko"), "biaya_pengendalian": inh_src.get("biaya_pengendalian"),
                    "periode_realisasi_terakhir": last.get("period_date"), "skor_dampak_realisasi": last.get("skor_dampak"),
                    "skor_kemungkinan_realisasi": last.get("skor_kemungkinan"), "tingkat_risiko_realisasi": last.get("tingkat_risiko"),
                    "kategori_tingkat_risiko_realisasi": last.get("kategori_tingkat_risiko"), "nilai_dampak_realisasi": last.get("nilai_dampak"),
                    "exposure_risiko_realisasi": last.get("exposure_risiko"), "jumlah_penyebab": causes_by[code],
                    "jumlah_rencana_penanganan": plans_by[code], "progres_penanganan_rata2": avg(prog_by_risk[code]),
                    "status_aktif": "Aktif", **tail})
    T["gold_erm_risk_register"] = reg

    months = lambda y: [date(y, m, 1) for m in range(1, 13)]  # noqa: E731
    comps = {(x["company_id"], x["fiscal_year"]): x for x in (ri["c"] for ri in risk_info.values())}
    ent_years = sorted({a["period_year"] for a in T["silver_fact_erm_risk_appetite"] if a["period_year"]})
    util = []
    for a in T["silver_fact_erm_risk_appetite"]:
        y = a["period_year"]
        if not y:
            continue
        c = comps.get((a["company_id"], y)) or {**comp(next((k for k, e in ent.items() if e.get("company_id") == a["company_id"]), None), y)}
        inh_tot = sum(x["exposure_risiko"] or 0 for x in G_asm if x["company_id"] == a["company_id"] and x["fiscal_year"] == y
                      and x["assessment_type"] == "INHEREN") or None
        for d in months(y):
            rows_m = [x for x in G_asm if x["company_id"] == a["company_id"] and x["period_date"] == d]
            tgt = [x["exposure_risiko"] for x in rows_m if x["assessment_type"] == "TARGET_RESIDUAL" and x["exposure_risiko"] is not None]
            rel = [x for x in rows_m if x["assessment_type"] == "REALISASI" and x["exposure_risiko"] is not None]
            e_rel = sum(x["exposure_risiko"] for x in rel) if rel else None
            lim, sel, tol, kap = a["nilai_batasan_risiko"], a["nilai_selera_risiko"], a["nilai_toleransi_risiko"], a["nilai_kapasitas_risiko"]
            if e_rel is None:
                st = "Belum dilaporkan"
            elif lim is not None and e_rel <= lim:
                st = "Dalam batasan"
            elif sel is not None and e_rel <= sel:
                st = "Dalam selera"
            elif tol is not None and e_rel <= tol:
                st = "Dalam toleransi"
            elif kap is not None and e_rel <= kap:
                st = "Melebihi toleransi"
            else:
                st = "Melebihi kapasitas"
            util.append({**c, "fiscal_year": y, **time_cols(d, d.month), "nilai_kapasitas_risiko": kap, "nilai_selera_risiko": sel,
                         "nilai_toleransi_risiko": tol, "nilai_batasan_risiko": lim, "exposure_inheren_total": inh_tot,
                         "exposure_target_total": sum(tgt) if tgt else None, "exposure_realisasi_total": e_rel,
                         "nilai_dampak_realisasi_total": sum(x["nilai_dampak"] or 0 for x in rel) if rel else None,
                         "rasio_realisasi_terhadap_batasan": e_rel / lim if e_rel is not None and lim else None,
                         "rasio_realisasi_terhadap_selera": e_rel / sel if e_rel is not None and sel else None,
                         "rasio_inheren_terhadap_batasan": inh_tot / lim if inh_tot and lim else None,
                         "status_utilisasi": st, "jumlah_risiko_dilaporkan": len({x["risk_id"] for x in rel}), **tail})
    T["gold_erm_risk_appetite_utilization"] = util

    G_kri = []
    for k in kri:
        c = comp(None if k["company_id_is_assumed"] else next((e for e, v in ent.items() if v.get("company_id") == k["company_id"]), None), k["period_year"])
        d = date(k["period_year"], k["period_month"] or 1, 1)
        G_kri.append({**c, "company_is_assumed": k["company_id_is_assumed"], **time_cols(d, k["period_month"]),
                      **{x: k[x] for x in ("kri_id", "main_category", "parameter_kri", "target_formula_kri", "arah_kri", "risk_limit_kri",
                                            "risk_appetite_range_kri", "risk_tolerance_kri", "actual_value_kri", "actual_text_kri", "status_kri")},
                      "is_bahaya": k["status_kri"] == "Bahaya", "is_dinilai": k["status_kri"] not in (None, "Tidak dapat dinilai"), **tail})
    T["gold_erm_kri_monitoring_monthly"] = G_kri

    cause_txt = {c["risk_cause_id"]: c["penyebab"] for c in T["silver_dim_erm_risk_cause"]}
    prog_at = {(p["mitigation_plan_id"], p["date_key"]): p for p in prog}
    G_mit = []
    for p in T["silver_fact_erm_mitigation_plan_monthly"]:
        ri = risk_info[p["risk_id"]]
        for d in months(p["period_year"]):
            g_ = prog_at.get((p["mitigation_plan_id"], int(d.strftime("%Y%m%d"))))
            v = g_["persentase_realisasi"] if g_ else None
            st = "Belum dilaporkan" if not g_ else ("Belum mulai" if not v else ("Selesai" if v >= 1 else "Berjalan"))
            G_mit.append({**ri["c"], **time_cols(d, d.month), "risk_id": p["risk_id"], "peristiwa_risiko": ri["peristiwa_risiko"],
                          "main_category": ri["main_category"], "mitigation_plan_id": p["mitigation_plan_id"], "risk_cause_id": p["risk_cause_id"],
                          "penyebab": cause_txt.get(p["risk_cause_id"]), "rencana_penanganan": p["rencana_penanganan"],
                          "pic_fungsi": pk[p["mitigation_plan_id"]]["pic_uraian"], "persentase_realisasi": v,
                          "realisasi_penanganan": g_["realisasi_penanganan"] if g_ else None, "is_dilaporkan": bool(g_),
                          "status_progres": st, **tail})
    T["gold_erm_mitigation_progress_monthly"] = G_mit

    exe = []
    for (cid, y), c in sorted(comps.items()):
        rids = [code for code, ri in risk_info.items() if ri["c"]["company_id"] == cid and ri["year"] == y]
        ap = appetite.get((cid, y), {})
        for d in months(y):
            rows_m = [x for x in G_asm if x["company_id"] == cid and x["period_date"] == d]
            rel = [x for x in rows_m if x["assessment_type"] == "REALISASI" and x["kategori_tingkat_risiko"]]
            lv = Counter(x["kategori_tingkat_risiko"] for x in rel)
            e_rel = [x["exposure_risiko"] for x in rows_m if x["assessment_type"] == "REALISASI" and x["exposure_risiko"] is not None]
            tgt = [x["exposure_risiko"] for x in rows_m if x["assessment_type"] == "TARGET_RESIDUAL" and x["exposure_risiko"] is not None]
            k_m = [k for k in G_kri if k["company_id"] == cid and k["period_date"] == d]
            p_m = [p["persentase_realisasi"] for p in G_mit if p["company_id"] == cid and p["period_date"] == d and p["is_dilaporkan"]]
            lim = ap.get("nilai_batasan_risiko")
            exe.append({**c, **time_cols(d, d.month), "jumlah_risiko": len(rids), "jumlah_risiko_dilaporkan": len({x["risk_id"] for x in rel}),
                        "jumlah_low": lv["Low"], "jumlah_low_to_moderate": lv["Low to Moderate"], "jumlah_moderate": lv["Moderate"],
                        "jumlah_moderate_to_high": lv["Moderate to High"], "jumlah_high": lv["High"],
                        "exposure_target_total": sum(tgt) if tgt else None, "exposure_realisasi_total": sum(e_rel) if e_rel else None,
                        "nilai_batasan_risiko": lim, "rasio_realisasi_terhadap_batasan": sum(e_rel) / lim if e_rel and lim else None,
                        "jumlah_kri": len(k_m) if k_m else None, "jumlah_kri_bahaya": sum(1 for k in k_m if k["is_bahaya"]) if k_m else None,
                        "progres_penanganan_rata2": avg(p_m), **tail})
    T["gold_erm_executive_summary_monthly"] = exe

    bench, compl = [], []
    for (cid, y), c in sorted(comps.items()):
        rr = [x for x in reg if x["company_id"] == cid and x["fiscal_year"] == y]
        n = len(rr)
        lim = appetite.get((cid, y), {}).get("nilai_batasan_risiko")
        inh_tot = sum(x["exposure_risiko_inheren"] or 0 for x in rr)
        pl = [p for p in T["silver_fact_erm_mitigation_plan_monthly"] if p["company_id"] == cid and p["period_year"] == y]
        pl_prog = sum(1 for p in pl if p["mitigation_plan_id"] in last_prog)
        bench.append({**c, "jumlah_risiko": n, "jumlah_risiko_high_inheren": sum(1 for x in rr if x["kategori_tingkat_risiko_inheren"] == "High"),
                      "persen_risiko_high_inheren": pct(sum(1 for x in rr if x["kategori_tingkat_risiko_inheren"] == "High"), n),
                      "tingkat_risiko_inheren_rata2": avg([x["tingkat_risiko_inheren"] for x in rr]),
                      "tingkat_risiko_realisasi_terakhir_rata2": avg([x["tingkat_risiko_realisasi"] for x in rr]),
                      "exposure_inheren_total": inh_tot, "nilai_batasan_risiko": lim,
                      "rasio_inheren_terhadap_batasan": inh_tot / lim if lim else None,
                      "biaya_pengendalian_total": sum(x["biaya_pengendalian"] or 0 for x in rr),
                      "jumlah_rencana_penanganan": len(pl), "persen_rencana_ada_progres": pct(pl_prog, len(pl)), **tail})
        tgt_r = {x["risk_id"] for x in G_asm if x["company_id"] == cid and x["assessment_type"] == "TARGET_RESIDUAL"
                 and (x["nilai_dampak"] is not None or x["skor_dampak"])}
        parts = [pct(sum(1 for x in rr if x["jumlah_penyebab"]), n), pct(sum(1 for x in rr if x["jumlah_rencana_penanganan"]), n),
                 pct(pl_prog, len(pl)), pct(sum(1 for x in rr if x["risk_id"] in tgt_r), n),
                 pct(sum(1 for x in rr if x["periode_realisasi_terakhir"]), n)]
        compl.append({**c, "jumlah_risiko": n, "persen_risiko_ada_penyebab": parts[0], "persen_risiko_ada_rencana": parts[1],
                      "persen_rencana_ada_progres": parts[2], "persen_risiko_ada_target_residual": parts[3],
                      "persen_risiko_ada_realisasi": parts[4], "skor_kepatuhan": avg(parts), **tail})
    for i, b in enumerate(sorted(bench, key=lambda x: -(x["exposure_inheren_total"] or 0)), 1):
        b["peringkat_exposure"] = i
    T["gold_erm_company_benchmark"] = bench
    T["gold_erm_governance_compliance"] = compl
    for empty in ("gold_erm_risk_loss_event", "gold_erm_audit_finding_linkage", "gold_erm_swot_matrix"):
        T[empty] = []
    T["_dq_findings"] = [{"snapshot_date": snap, "source_system": "EGRC", "finding_code": t["temuan_kode"], "finding_category": t["temuan_kategori"],
                          "severity": t["tingkat_kategori"], "sheet_name": t["sheet_nama"], "affected_rows": ival(t["baris_jml"]),
                          "description": t["temuan_uraian"], "example": t["contoh_uraian"], "etl_action": t["tindakan_etl_uraian"],
                          "follow_up_owner": t["tindak_lanjut_pemilik_nama"], **tail} for t in temuan]
    return T


# ============================================================== orkestrasi
SNAPSHOT_TABLES = {"gold_meta_governance_kpi_snapshot", "gold_meta_dq_finding_snapshot"}


def rebuild(tq: Trino, schema: dict, batch_id: str, now: datetime) -> None:
    """Urutan: SDM/korporasi (dimensi perusahaan bersama) → berkas DG_WORKBOOK/EGRC → Aplikasi ERM LenO (lenodb).
    Tabel ber-kolom _source_system menampung beberapa sumber; tiap sumber hanya mengganti barisnya sendiri."""
    import leno_erm  # Aplikasi ERM LenO dari katalog Trino lenodb (SQL di Trino)
    import sdm  # kerangka SDM + korporasi (SQL di Trino), dari Bronze bronze_sdm_* / bronze_corp_*
    sdm.build(tq, schema, batch_id, now)
    rebuild_files(tq, schema, batch_id, now)
    leno_erm.build(tq, schema, batch_id, now)


def rebuild_files(tq: Trino, schema: dict, batch_id: str, now: datetime) -> None:
    srcs = latest_sources(tq)
    if not srcs:
        log("Belum ada berkas DG_WORKBOOK/EGRC di bronze_repository. Jalankan: lakehouse.py ingest <berkas>")
        return
    snap = now.astimezone(timezone(timedelta(hours=7))).date()
    out: dict[str, list[dict]] = {}
    findings = []
    for src, info in srcs.items():
        L = {"_file_id": info["file_id"], "_batch_id": batch_id, "_source_system": src, "_source_file": info["name"], "_loaded_at": now}
        log(f"Silver/Gold dari {src}: {info['name']} (file_id {info['file_id']})")
        T = build_meta(info["path"], info["file_id"], L, snap) if src == "DG_WORKBOOK" else build_erm(tq, info["path"], L, snap)
        findings += T.pop("_dq_findings")
        for rows in T.values():          # Gold tanpa lineage per baris: tandai sumbernya
            for r in rows:
                r.setdefault("_source_system", src)
        out.update(T)
    if "DG_WORKBOOK" in srcs and "EGRC" in srcs:
        out["gold_meta_dq_finding_snapshot"] = findings
    elif findings:
        out["gold_meta_dq_finding_snapshot"] = findings  # hanya sumber yang ada; snapshot hari ini diganti
    live = set(tq.tables())
    for name in sorted(out):
        spec = schema[name]
        st = ensure_table(tq, name, spec, live, managed=True)
        rows = out[name]
        if name in SNAPSHOT_TABLES:
            replace_rows(tq, name, spec, rows, where=f"snapshot_date = DATE '{snap.isoformat()}'")
        elif any(c == "_source_system" for c, _, _ in spec["cols"]):
            replace_rows(tq, name, spec, rows, where="_source_system IS DISTINCT FROM 'LENO_ERM'")   # baris LenO dikelola leno_erm.py
        else:
            replace_rows(tq, name, spec, rows)
        log(f"  {name:45s} {len(rows):6d} baris" + ("" if st == "sama" else f"  [{st}]"))
    tq.q(f"UPDATE {tq.fq('bronze_repository')} SET is_processed_to_silver = TRUE WHERE source_system IN "
         f"({', '.join(sq(s) for s in srcs)}) AND file_id IN ({', '.join(sq(i['file_id']) for i in srcs.values())})")


def ensure_base(tq: Trino, schema: dict) -> None:
    """Revisi tabel kerangka agar cocok dengan berkas skema. Tabel berisi data yang bukan milik loader tidak disentuh."""
    live = set(tq.tables())
    changed = []
    for name, spec in schema.items():
        st = ensure_table(tq, name, spec, live, managed=False)
        if st not in ("sama", "dibiarkan"):
            changed.append(f"{name} [{st}]")
    if changed:
        log("Skema disesuaikan: " + ", ".join(changed))


def status(tq: Trino) -> None:
    """Per tabel, tanpa coba ulang: tabel yang sesaat tak terbaca oleh Lakekeeper ditandai, sisanya tetap tampil."""
    log(f"{'tabel':55s} {'baris':>9s}  snapshot terakhir (WIB)")
    for t in sorted(tq.tables()):
        try:
            n = f"{tq.q(f'SELECT count(*) FROM {tq.fq(t)}', attempts=1)[0][0]:9d}"
            last = tq.q(f'SELECT max(committed_at) FROM {tq.catalog}.{tq.schema}."{t}$snapshots"', attempts=1)[0][0]
            when = last.astimezone(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M") if last else "-"
        except Exception as e:  # noqa: BLE001
            n, when = "    galat", f"tak terbaca: {str(e)[:70]}"
        log(f"{t:55s} {n}  {when}")


def sync_catalog() -> None:
    """Katalog :8585 ikut diperbarui (tabel, kolom, jumlah baris). Gagal sinkron tidak membatalkan pemuatan."""
    try:
        import catalog_trino
        catalog_trino.main()
    except (Exception, SystemExit) as e:  # noqa: BLE001 — token kedaluwarsa/katalog mati: cukup diberi tahu
        log(f"  ! sinkron katalog dilewati: {str(e)[:200]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("files", nargs="+")
    p.add_argument("--no-rebuild", action="store_true")
    sub.add_parser("inbox")
    sub.add_parser("retry", help="lengkapi berkas berstatus PARTIAL dari staging")
    sub.add_parser("rebuild")
    sub.add_parser("status")
    a = ap.parse_args()
    tq = Trino()
    if a.cmd == "status":
        return status(tq)
    import fcntl
    (DATA / "medallion").mkdir(parents=True, exist_ok=True)
    lock = (DATA / "medallion" / ".lakehouse.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("Loader lain sedang berjalan — dilewati.")
        return
    schema = load_schema()
    now = datetime.now(timezone.utc)
    batch_id = str(uuid.uuid4())
    names: dict[Path, str] = {}
    inbox = DATA / "medallion" / "inbox"
    if a.cmd == "inbox" and not any(f.is_file() and f.suffix.lower() in (".xlsx", ".xlsm", ".csv") for f in inbox.glob("*")):
        return                                   # timer tiap 10 menit: inbox kosong → Trino tidak disentuh sama sekali
    ensure_base(tq, schema)
    files: list[Path] = []
    if a.cmd == "ingest":
        files = [Path(f) for f in a.files]
    elif a.cmd == "retry":
        rows = tq.q(f"SELECT DISTINCT file_path, file_name FROM {tq.fq('bronze_repository')} WHERE ingestion_status = 'PARTIAL'")
        files = [Path(p) for p, _ in rows if Path(p).exists()]
        names = {Path(p): n for p, n in rows}
        if not files:
            log("Tidak ada berkas PARTIAL.")
            return
    elif a.cmd == "inbox":
        inbox = DATA / "medallion" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        files = sorted(f for f in inbox.iterdir() if f.is_file() and f.suffix.lower() in (".xlsx", ".xlsm", ".csv")
                       and not f.name.startswith(("~$", ".")))
        if not files:
            return
    log(f"batch {batch_id}")
    new = False
    for f in files:
        log(f"Bronze: {f.name}")
        r = ingest(tq, f, schema, batch_id, now, name=names.get(f) if a.cmd == "retry" else None)
        new = new or bool(r and r["source"] != "FILE")
        if a.cmd == "inbox":
            done = DATA / "medallion" / "inbox" / "selesai"
            done.mkdir(exist_ok=True)
            shutil.move(str(f), done / f"{now.strftime('%Y%m%d-%H%M%S')}__{f.name}")
    if a.cmd == "rebuild" or (new and not getattr(a, "no_rebuild", False)):
        rebuild(tq, schema, batch_id, now)
        sync_catalog()
    elif files:
        log("Tidak ada berkas baru dari sumber yang dikenali — Silver/Gold tidak diubah.")


if __name__ == "__main__":
    main()
