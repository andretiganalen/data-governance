#!/usr/bin/env python3
"""Layanan unduh Excel (kontainer `ldg-export`, hanya jaringan internal; publik lewat gateway /_export/).

Aturan akses (sama dengan lima tingkat akses, loader/access_levels.py):
  boleh unduh = isAdmin | tim UV-1 (Admin Data Governance) | tim Pengunduh | tim Fungsi FN_*
  cakupan     = isAdmin / UV-1 → semua; selain itu hanya elemen data yang pemilik/steward/penggunanya memuat ORG_ID
                dari Fungsi (FN_*) pengguna atau dari tim unit (kode seperti UG-1) tempat pengguna berada.
  tingkat 5 (Lihat saja) tidak boleh mengunduh.
Identitas = token sesi pengguna yang dikirim browser (Authorization: Bearer ...) dan divalidasi ke ldg-server; tidak ada
akun/kata sandi lain. Mengunduh dicatat di log (siapa, cakupan, jumlah baris), tanpa isi data.

  GET /_export/me                → {"allowed", "level", "scope", "orgs"}  (untuk tombol di UI)
  GET /_export/governance.xlsx   → berkas Excel (sel merah/kuning, lihat export_xlsx.py)
  GET /_export/fungsi-pdf        → status revisi PDF Glosarium Fungsi (hanya isAdmin / UV-1)
  POST /_export/fungsi-pdf       → minta revisi PDF baru: menulis request.json; timer glosarium 10 menit menerbitkannya
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
import export_xlsx as X  # noqa: E402

UPSTREAM = os.environ.get("LDG_UPSTREAM", "http://ldg-server:8585")
STAFF, DOWNLOAD = "UV-1", "Pengunduh"
WIB = timezone(timedelta(hours=7))
REQ_DIR = Path(os.environ.get("LDG_DATA_DIR", "/data")) / "medallion" / "pdf_request"
ORG_RE = re.compile(r"^[A-Za-z]{2}-\d+$")


def log(*a):
    print(datetime.now(WIB).strftime("%H:%M:%S"), *a, flush=True)


def norm(s: str) -> str:
    s = re.sub(r"\(tidak ada\)", "", s or "", flags=re.I).replace("_", " ").strip().lower()
    return re.sub(r"^(fn|fungsi)\s+", "", s)


def whoami(auth: str) -> dict | None:
    req = urllib.request.Request(UPSTREAM + "/api/v1/users/loggedInUser?fields=teams,roles", headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except (urllib.error.URLError, ValueError):
        return None


def fungsi_orgs() -> dict[str, set[str]]:
    """nama Fungsi ternormalisasi → ORG_ID dari silver_dim_organization (baris berlaku saat ini)."""
    tq = X.Trino()
    out: dict[str, set[str]] = {}
    for org, fungsi in tq.q(f"SELECT org_id, fungsi FROM {tq.fq('silver_dim_organization')} WHERE is_current"):
        out.setdefault(norm(fungsi), set()).add(org)
    return out


def access(user: dict) -> dict:
    teams = user.get("teams") or []
    names = {t.get("name") for t in teams}
    fn = [t for t in teams if (t.get("name") or "").startswith("FN_")]
    if user.get("isAdmin") or STAFF in names:
        return {"allowed": True, "level": "Admin", "orgs": None, "scope": "Semua data"}
    if not (fn or DOWNLOAD in names):
        return {"allowed": False, "level": "Lihat saja", "orgs": set(), "scope": "Tidak ada hak unduh"}
    orgs = {n for n in names if n and ORG_RE.match(n)}
    if fn:
        m = fungsi_orgs()
        for t in fn:
            orgs |= m.get(norm(t.get("displayName") or t["name"]), set()) | m.get(norm(t["name"]), set())
    return {"allowed": True, "level": "Fungsi" if fn else "Pengunduh", "orgs": orgs,
            "scope": "Fungsi/unit Anda" if orgs else "Belum ada unit atau Fungsi yang terpetakan"}


def master_organisasi() -> list[dict]:
    """Unit kerja berlaku: silver_dim_organization + perubahan aplikasi (app_organisasi). Hanya dibaca dari Trino."""
    import app_organisasi as AO
    return AO.merged(X.Trino())


def glosarium() -> dict:
    """Business Glossary: gold_meta_glossary_app (+ definisi dari aplikasi) + jumlah pemakaian di Data Element. Hanya dibaca dari Trino."""
    import app_glosarium as AG
    tq = X.Trino()
    cols = ["field_id", "business_term", "definisi", "glosarium", "data_owner", "data_steward", "diubah_pada", "sumber_perubahan"]
    base = {r[0]: dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(
        f"SELECT field_id, business_term, definisi, glosarium, data_owner, data_steward, diubah_pada, sumber_perubahan "
        f"FROM {tq.fq('gold_meta_glossary_app')}")}
    status = {r[0]: str(r[1]) for r in tq.q(f"SELECT field_id, status FROM {tq.fq('gold_meta_glossary_status')}")}
    dipakai = {r[0]: int(r[1]) for r in tq.q(f"SELECT field_id, count(*) FROM {tq.fq('silver_dim_meta_field')} GROUP BY 1")}
    app = AG.latest_app(tq)
    rows = []
    for fid, r in base.items():
        a = app.get(fid)
        d = (a["definisi"] if a and a["aksi"] == "isi" else r["definisi"]) or None
        rows.append({"field_id": fid, "business_term": r["business_term"], "definisi": d, "glosarium": r["glosarium"],
                     "data_owner": r["data_owner"], "data_steward": r["data_steward"], "status": status.get(fid),
                     "dipakai": dipakai.get(fid, 0), "sumber_perubahan": "Aplikasi" if a else r["sumber_perubahan"],
                     "diubah_oleh": a["oleh"] if a else None, "diubah_pada": a["diubah_pada"] if a else r["diubah_pada"]})
    return {"rows": sorted(rows, key=lambda x: (x["glosarium"] or "", x["business_term"] or ""))}


_UI_CSS: dict = {"t": 0.0, "css": []}


def uicss() -> dict:
    """Berkas CSS aplikasi (UIx/antd) yang sedang dipakai ldg-server. Nama berkas berubah tiap build, jadi dibaca dari /signin (cache 10 menit)."""
    import time
    import re as _re
    if time.time() - _UI_CSS["t"] < 600 and _UI_CSS["css"]:
        return {"css": _UI_CSS["css"]}
    with urllib.request.urlopen(UPSTREAM + "/signin", timeout=15) as r:
        html = r.read().decode("utf-8", "replace")
    css = [h for h in _re.findall(r'href="(/assets/[^"]+\.css)"', html)]
    _UI_CSS.update({"t": time.time(), "css": css})
    return {"css": css}


def fungsi() -> dict:
    """Fungsi (gold_meta_fungsi). Dasar dokumen ditentukan per baris: Nota 021 bila deskripsi menyebutnya, selain itu CLP-001. Hanya dibaca dari Trino."""
    tq = X.Trino()
    rows = []
    for r in tq.q(f"SELECT team_name, fungsi, eselon1, deskripsi, jumlah_istilah_dimiliki, jumlah_tabel_dimiliki FROM {tq.fq('gold_meta_fungsi')} ORDER BY fungsi"):
        team, nama, eselon, desk, istilah, tabel = [None if v is None else str(v) for v in r]
        dasar = "Nota 021/N/UQ/VIII/2026 (24 Agustus 2026)" if desk and "Nota 021" in desk else "CLP-001 rev.01 (28 Februari 2024)"
        rows.append({"team_name": team, "fungsi": nama, "eselon1": eselon, "dasar": dasar, "jumlah_istilah": istilah, "jumlah_tabel": tabel})
    return {"rows": rows}


def sistem() -> dict:
    """Master Sistem: silver_dim_meta_system + perubahan aplikasi (app_sistem). Nilai kosong tetap kosong."""
    import app_sistem as AS
    return {"rows": AS.merged(X.Trino())}


def dataset() -> dict:
    """Business Dataset: silver_dim_meta_dataset + perubahan aplikasi (app_dataset). Nilai kosong tetap kosong."""
    import app_dataset as AD
    return {"rows": AD.merged(X.Trino())}


def objek() -> dict:
    """Database Object (silver_dim_meta_table + perubahan app_objek) + kolomnya (silver_dim_meta_field). Hanya dibaca dari Trino."""
    tq = X.Trino()
    tcols = ["table_id", "dataset_id", "dataset_name", "table_name", "object_type", "database_name", "object_owner", "row_count",
             "sensitive_data_flag", "critical_data_flag", "source_system"]
    fcols = ["field_id", "table_id", "column_name", "business_term", "data_type", "pk_flag", "fk_flag", "nullable_flag",
             "sensitive_flag", "metadata_status"]
    import app_objek as AO
    tables = AO.merged(tq)
    fields = [dict(zip(fcols, [None if v is None else str(v) for v in r]))
              for r in tq.q(f"SELECT {', '.join(fcols)} FROM {tq.fq('silver_dim_meta_field')} ORDER BY table_id, field_id")]
    return {"rows": tables, "fields": fields}


DAFTAR = {   # kunci → (sumber Trino, kolom)  — baca saja
    "elemen": ("silver_dim_meta_field", ["field_id", "table_name", "column_name", "business_term", "data_type", "pk_flag", "sensitive_flag", "metadata_status"]),
    "assignment": ("silver_dim_meta_governance_assignment", ["field_id", "field_name", "business_term", "role", "org_id", "unit_kerja", "role_status"]),
    "kualitas": ("silver_dim_meta_dq_rule", ["dq_rule_id", "field_id", "business_term", "rule", "validation", "dq_dimension", "pass_fail", "check_date"]),
    "lineage": ("gold_meta_lineage", ["lineage_id", "system_name", "dataset_name", "table_name", "column_name", "field_id", "business_term", "target_label", "asset_type"]),
    "akses": ("gold_meta_access_matrix", ["access_id", "screen_label", "column_name", "field_id", "org_id", "unit_kerja", "classification", "permission_category", "permission_type"]),
}


def daftar(key: str) -> dict:
    """Daftar baca saja untuk layar Katalog/Tata kelola. Nilai kosong tetap kosong. Hanya dibaca dari Trino."""
    tbl, cols = DAFTAR[key]
    tq = X.Trino()
    rows = [dict(zip(cols, [None if v is None else str(v) for v in r])) for r in tq.q(f"SELECT {', '.join(cols)} FROM {tq.fq(tbl)}")]
    if key == "elemen":   # tambahan dari aplikasi (app_elemen)
        import app_elemen as AE
        import app_objek as AO
        nama_tabel = {r["table_id"]: r.get("table_name") for r in AO.merged(tq)}
        for a in AE.added(tq):
            rows.append({"field_id": a["field_id"], "table_name": None, "column_name": a["column_name"], "business_term": a["business_term"],
                         "data_type": a["data_type"], "pk_flag": None, "sensitive_flag": None, "metadata_status": "Perlu dilengkapi"})
            rows[-1]["table_name"] = nama_tabel.get(a["table_id"]) or a["table_id"]
    return {"rows": rows, "kolom": cols}


def can_edit(user: dict) -> bool:
    """Tulis Master Organisasi: isAdmin atau tim UV-1 (Admin Data Governance)."""
    return bool(user.get("isAdmin")) or any(t.get("name") == STAFF for t in (user.get("teams") or []))


class H(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/healthz":
            return self._json(200, {"ok": True})
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):   # halaman HTML (Beranda, Organisasi) hanya membawa cookie sesi
            tok = next((c.split("=", 1)[1] for c in (self.headers.get("Cookie") or "").split(";") if c.strip().startswith("dg_token=")), "")
            auth = f"Bearer {tok}" if tok else ""
        user = whoami(auth) if auth.startswith("Bearer ") else None
        if not user:
            return self._json(401, {"error": "Silakan masuk terlebih dahulu."})
        try:
            if path == "/_export/erm.xlsx":   # Excel format ERM (templat Rev.0.1), data Trino yang berlaku; hanya admin / UV-1
                a = access(user)
                if a["orgs"] is not None or not a["allowed"]:
                    return self._json(403, {"error": "Hanya Admin Data Governance yang dapat mengunduh format ERM."})
                import erm_xlsx as EX
                buf = io.BytesIO()
                counts = EX.build(X.Trino(), buf)
                log("unduh erm.xlsx", user.get("name"), "baris=", counts)
                data = buf.getvalue()
                name = f"{datetime.now(WIB):%y%m%d} Data Governance ERM.xlsx"
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            if path == "/_export/whoami":   # nama untuk kerangka halaman (tanpa data lain)
                nama = user.get("displayName") or user.get("name") or ""
                return self._json(200, {"nama": nama, "bisa_ubah": can_edit(user)})
            if path == "/_export/fungsi":   # baca saja
                return self._json(200, fungsi())
            if path == "/_export/uicss":   # berkas CSS aplikasi untuk halaman kita (gaya UIx asli)
                return self._json(200, uicss())
            if path.startswith("/_export/daftar/"):   # baca saja
                key = path.rsplit("/", 1)[-1]
                if key not in DAFTAR:
                    return self._json(404, {"error": "tidak ditemukan"})
                return self._json(200, daftar(key))
            if path == "/_export/objek":   # baca saja
                return self._json(200, objek())
            if path == "/_export/dataset":   # baca saja
                return self._json(200, dataset())
            if path == "/_export/sistem":   # baca saja
                return self._json(200, sistem())
            if path == "/_export/glosarium":   # baca saja
                return self._json(200, glosarium())
            if path == "/_export/master-organisasi":   # baca saja: versi berlaku dari Gold gold_meta_master_organisasi
                return self._json(200, {"rows": master_organisasi(), "bisa_ubah": can_edit(user)})
            a = access(user)
            if path == "/_export/me":
                return self._json(200, {"allowed": a["allowed"], "level": a["level"], "scope": a["scope"], "pdf": a["orgs"] is None and a["allowed"],
                                        "orgs": None if a["orgs"] is None else sorted(a["orgs"])})
            if path == "/_export/fungsi-pdf":
                if not (a["allowed"] and a["orgs"] is None):
                    return self._json(403, {"error": "Hanya Admin Data Governance."})
                try:
                    st = json.loads((REQ_DIR / "status.json").read_text())
                except (OSError, ValueError):
                    st = {}
                st["menunggu"] = (REQ_DIR / "request.json").exists()
                return self._json(200, st)
            if path == "/_export/governance.xlsx":
                if not a["allowed"]:
                    return self._json(403, {"error": "Akun Anda belum memiliki hak unduh."})
                buf = io.BytesIO()
                st = X.build(buf, org_ids=a["orgs"])
                name = f"{datetime.now(WIB):%y%m%d} Data Governance.xlsx"
                log("unduh", user.get("name"), a["level"], "orgs=", "semua" if a["orgs"] is None else sorted(a["orgs"]),
                    "baris=", {k: v["baris"] for k, v in st.items()})
                data = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            self._json(404, {"error": "tidak ditemukan"})
        except Exception as e:  # noqa: BLE001
            log("galat", repr(e)[:200])
            self._json(500, {"error": "Berkas belum dapat dibuat. Coba lagi sebentar."})

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 65536:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return {}

    def _glosarium_write(self, user: dict):
        import app_glosarium as AG
        if not can_edit(user):
            return self._json(403, {"error": "Hanya Admin Data Governance yang dapat mengisi definisi glosarium."})
        body = self._body()
        try:
            tq = X.Trino()
            current = {r[0] for r in tq.q(f"SELECT field_id FROM {tq.fq('gold_meta_glossary_app')}")}
            fid, galat = AG.validate(body.get("field_id"), body.get("definisi"), current)
            if galat:
                return self._json(400, {"error": galat})
            row = AG.append(tq, fid, body.get("definisi"), user.get("name") or "pengguna", body.get("alasan"))
            log("glosarium-definisi", fid, "oleh", user.get("name"))
            self._json(200, {"ok": True, "field_id": fid, "diubah_pada": row["diubah_pada"]})
        except Exception as e:  # noqa: BLE001
            log("galat glosarium", repr(e)[:200])
            self._json(500, {"error": "Definisi belum dapat disimpan. Coba lagi sebentar."})

    def _elemen_write(self, user: dict):
        import app_elemen as AE
        if not can_edit(user):
            return self._json(403, {"error": "Hanya Admin Data Governance yang dapat menambah Data Element."})
        body = self._body()
        try:
            tq = X.Trino()
            import app_objek as AO
            tables = {r["table_id"] for r in AO.merged(tq)}
            terms = {r[0] for r in tq.q(f"SELECT business_term FROM {tq.fq('gold_meta_glossary_app')}")}
            galat = AE.validate(tq, body, tables, terms)
            if galat:
                return self._json(400, {"error": galat})
            row = AE.append(tq, body, user.get("name") or "pengguna", body.get("alasan"))
            log("data-element", row["field_id"], "oleh", user.get("name"))
            self._json(200, {"ok": True, "field_id": row["field_id"], "diubah_pada": row["diubah_pada"]})
        except Exception as e:  # noqa: BLE001
            log("galat data-element", repr(e)[:200])
            self._json(500, {"error": "Data Element belum dapat disimpan. Coba lagi sebentar."})

    def _objek_write(self, user: dict):
        import app_objek as AO
        import app_dataset as AD
        if not can_edit(user):
            return self._json(403, {"error": "Hanya Admin Data Governance yang dapat mengubah Database Object."})
        body = self._body()
        aksi = str(body.get("aksi") or "")
        try:
            tq = X.Trino()
            current = {r["table_id"]: r for r in AO.merged(tq)}
            datasets = {r["dataset_id"] for r in AD.merged(tq)}
            tid, galat = AO.validate(tq, aksi, body.get("table_id"), body, current, datasets)
            if galat:
                return self._json(400, {"error": galat})
            row = AO.append(tq, aksi, tid, body, user.get("name") or "pengguna", body.get("alasan"))
            log("database-object", aksi, tid, "oleh", user.get("name"))
            self._json(200, {"ok": True, "table_id": tid, "aksi": aksi, "diubah_pada": row["diubah_pada"]})
        except Exception as e:  # noqa: BLE001
            log("galat database-object", repr(e)[:200])
            self._json(500, {"error": "Perubahan belum dapat disimpan. Coba lagi sebentar."})

    def _dataset_write(self, user: dict):
        import app_dataset as AD
        if not can_edit(user):
            return self._json(403, {"error": "Hanya Admin Data Governance yang dapat mengubah Business Dataset."})
        body = self._body()
        aksi = str(body.get("aksi") or "")
        try:
            tq = X.Trino()
            current = {r["dataset_id"]: r for r in AD.merged(tq)}
            did, galat = AD.validate(aksi, body.get("dataset_id"), body, current)
            if galat:
                return self._json(400, {"error": galat})
            row = AD.append(tq, aksi, did, body, user.get("name") or "pengguna", body.get("alasan"))
            log("business-dataset", aksi, did, "oleh", user.get("name"))
            self._json(200, {"ok": True, "dataset_id": did, "aksi": aksi, "diubah_pada": row["diubah_pada"]})
        except Exception as e:  # noqa: BLE001
            log("galat business-dataset", repr(e)[:200])
            self._json(500, {"error": "Perubahan belum dapat disimpan. Coba lagi sebentar."})

    def _sistem_write(self, user: dict):
        import app_sistem as AS
        if not can_edit(user):
            return self._json(403, {"error": "Hanya Admin Data Governance yang dapat mengubah Master Sistem."})
        body = self._body()
        aksi = str(body.get("aksi") or "")
        try:
            tq = X.Trino()
            current = {r["system_id"]: r for r in AS.merged(tq)}
            sid, galat = AS.validate(aksi, body.get("system_id"), body, current)
            if galat:
                return self._json(400, {"error": galat})
            row = AS.append(tq, aksi, sid, body, user.get("name") or "pengguna", body.get("alasan"))
            log("master-sistem", aksi, sid, "oleh", user.get("name"))
            self._json(200, {"ok": True, "system_id": sid, "aksi": aksi, "diubah_pada": row["diubah_pada"]})
        except Exception as e:  # noqa: BLE001
            log("galat master-sistem", repr(e)[:200])
            self._json(500, {"error": "Perubahan belum dapat disimpan. Coba lagi sebentar."})

    def _master_write(self, user: dict):
        import app_organisasi as AO
        if not can_edit(user):
            return self._json(403, {"error": "Hanya Admin Data Governance yang dapat mengubah Master Organisasi."})
        body = self._body()
        aksi = str(body.get("aksi") or "")
        try:
            tq = X.Trino()
            current = {r["org_id"]: r for r in AO.merged(tq)}
            oid, galat = AO.validate(aksi, body.get("org_id"), body, current)
            if galat:
                return self._json(400, {"error": galat})
            row = AO.append(tq, aksi, oid, body, user.get("name") or user.get("displayName") or "pengguna", body.get("alasan"), current)
            log("master-organisasi", aksi, oid, "oleh", user.get("name"))
            self._json(200, {"ok": True, "org_id": oid, "aksi": aksi, "diubah_pada": row["diubah_pada"]})
        except Exception as e:  # noqa: BLE001
            log("galat master-organisasi", repr(e)[:200])
            self._json(500, {"error": "Perubahan belum dapat disimpan. Coba lagi sebentar."})

    def do_POST(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path not in ("/_export/fungsi-pdf", "/_export/master-organisasi", "/_export/sistem", "/_export/dataset", "/_export/objek", "/_export/glosarium", "/_export/elemen"):
            return self._json(404, {"error": "tidak ditemukan"})
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            tok = next((c.split("=", 1)[1] for c in (self.headers.get("Cookie") or "").split(";") if c.strip().startswith("dg_token=")), "")
            auth = f"Bearer {tok}" if tok else ""
        user = whoami(auth) if auth.startswith("Bearer ") else None
        if not user:
            return self._json(401, {"error": "Silakan masuk terlebih dahulu."})
        if path == "/_export/master-organisasi":
            return self._master_write(user)
        if path == "/_export/sistem":
            return self._sistem_write(user)
        if path == "/_export/dataset":
            return self._dataset_write(user)
        if path == "/_export/objek":
            return self._objek_write(user)
        if path == "/_export/elemen":
            return self._elemen_write(user)
        if path == "/_export/glosarium":
            return self._glosarium_write(user)
        try:
            a = access(user)
            if not (a["allowed"] and a["orgs"] is None):
                return self._json(403, {"error": "Hanya Admin Data Governance."})
            REQ_DIR.mkdir(parents=True, exist_ok=True)
            (REQ_DIR / "request.json").write_text(json.dumps({"oleh": user.get("name"), "pada": datetime.now(WIB).isoformat()}))
            log("minta revisi PDF Fungsi", user.get("name"))
            self._json(202, {"menunggu": True})
        except Exception as e:  # noqa: BLE001
            log("galat", repr(e)[:200])
            self._json(500, {"error": "Permintaan belum dapat dicatat."})

    def log_message(self, *a):  # log akses standar dimatikan (token tidak boleh tercetak)
        pass


if __name__ == "__main__":
    log("ldg-export siap di :8590")
    ThreadingHTTPServer(("0.0.0.0", 8590), H).serve_forever()
