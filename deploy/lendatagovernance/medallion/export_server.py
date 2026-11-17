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
        if path not in ("/_export/fungsi-pdf", "/_export/master-organisasi"):
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
