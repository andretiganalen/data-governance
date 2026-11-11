"""SSO Visualisasi ← sesi Len Data Governance, plus aturan data: semua baca/tulis hanya ke Trino lakehouse.

Alur login (tidak ada kredensial terpisah):
  1. leno-menu.js (disisipkan gateway ke UI Len Data Governance) menangkap token Bearer sesi pengguna
     dan menaruhnya di cookie `dg_token` dengan path /visualisasi (hanya terkirim ke modul Visualisasi).
  2. /visualisasi/login/ memeriksa token itu ke API Len Data Governance (GET /api/v1/users/loggedInUser). Bila sah,
     pengguna yang sama dimasukkan ke Superset: dicocokkan lewat email; dibuat otomatis bila belum ada.
     Peran mengikuti Len Data Governance: Admin → Admin; selain itu → Gamma + sql_lab (lihat semua dataset,
     membuat grafik, SQL Lab, unggah CSV/XLSX ke Trino).
  3. Setiap permintaan: bila cookie hilang/berganti (logout atau token diperbarui), sesi Superset diakhiri dan
     login diulang otomatis dari token yang berlaku.

Aturan data (CLAUDE.md, 2026-11-09/10):
  - Koneksi database hanya Trino (`trino://…`): koneksi jenis lain ditolak saat dibuat, diubah, atau diuji.
  - Semua pengguna boleh membuat tabel, tetapi hanya di schema `workspace` (lakekeeper.workspace): pernyataan tulis
    (CREATE/INSERT/UPDATE/DELETE/DROP/ALTER/MERGE) ke schema lain — termasuk medallion_repository yang dikelola
    loader — ditolak. Unggahan CSV/XLSX hanya ke `workspace` (schemas_allowed_for_file_upload).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re

import requests
from flask import Response, redirect, request, session
from flask_appbuilder import expose
from flask_appbuilder.security.views import AuthRemoteUserView
from flask_appbuilder.utils.base import get_safe_redirect
from flask_login import current_user, login_user, logout_user

from superset.security import SupersetSecurityManager

log = logging.getLogger(__name__)
LDG_API = os.environ.get("DG_API", "http://ldg-server:8585/api/v1")
COOKIE = "dg_token"
WRITE_SCHEMA = os.environ.get("DG_WRITE_SCHEMA", "workspace")
TRINO_CATALOG = os.environ.get("DG_TRINO_CATALOG", "lakekeeper")

NOT_SIGNED_IN = """<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Visualisasi</title></head>
<body style="font-family:'UIx Poppins',Arial,sans-serif;color:#364153;background:#f9fafb;padding:40px">
<div style="max-width:520px;margin:auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:28px">
<h3 style="color:#101828;margin-top:0">Sesi Len Data Governance tidak ditemukan</h3>
<p>Visualisasi memakai login Len Data Governance. Masuk terlebih dahulu, lalu buka menu <b>Visualisasi</b>.</p>
<p><a href="/" target="_top" style="color:#ae2524">Buka Len Data Governance</a></p></div></body></html>"""


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def ldg_whoami(token: str) -> dict | None:
    try:
        r = requests.get(f"{LDG_API}/users/loggedInUser", params={"fields": "roles,teams"},
                         headers={"Authorization": f"Bearer {token}"}, timeout=10)
    except requests.RequestException as e:
        log.warning("Len Data Governance tidak terjangkau untuk validasi sesi: %s", e)
        return None
    return r.json() if r.status_code == 200 else None


def _ldg_login(appbuilder):
    next_url = get_safe_redirect(request.args.get("next", ""))
    token = request.cookies.get(COOKIE)
    info = ldg_whoami(token) if token else None
    user = appbuilder.sm.ldg_sync_user(info) if info else None
    if user is None:
        return Response(NOT_SIGNED_IN, status=401, mimetype="text/html")
    login_user(user, remember=False)
    session["dg_tok"] = _sha(token)
    return redirect(next_url or appbuilder.get_url_for_index)


class LDGAuthView(AuthRemoteUserView):
    @expose("/login/")
    def login(self):
        return _ldg_login(self.appbuilder)


def _ldg_login_view():
    """Pengganti SupersetAuthView (/login/) — Superset 6 mendaftarkannya lebih dulu dari view konfigurasi."""
    from superset.views.base import BaseSupersetView
    from flask_appbuilder.security.views import AuthView

    class LDGLoginView(BaseSupersetView, AuthView):
        route_base = "/login"

        @expose("/")
        def login(self, provider=None):
            return _ldg_login(self.appbuilder)

    return LDGLoginView


class LDGSecurityManager(SupersetSecurityManager):
    authremoteuserview = LDGAuthView

    def register_views(self) -> None:
        import superset.views.auth as auth_views
        original = auth_views.SupersetAuthView
        auth_views.SupersetAuthView = _ldg_login_view()
        try:
            super().register_views()
        finally:
            auth_views.SupersetAuthView = original

    def ldg_sync_user(self, info: dict):
        email = (info.get("email") or "").strip().lower()
        name = info.get("name") or email
        if not name:
            return None
        display = (info.get("displayName") or name).strip()
        first, _, last = display.partition(" ")
        roles = [self.find_role("Admin")] if info.get("isAdmin") else [self.find_role("Gamma"), self.find_role("sql_lab")]
        roles = [r for r in roles if r]
        self._grant_user_access()
        user = (self.find_user(email=email) if email else None) or self.find_user(username=email or name)
        if user is None:
            user = self.add_user(username=email or name, first_name=first or name, last_name=last or "-",
                                 email=email or f"{name}@lendatagovernance.local", role=roles)
            log.info("Pengguna Visualisasi dibuat dari sesi Len Data Governance: %s", email or name)
        elif not user.active or sorted(r.name for r in user.roles) != sorted(r.name for r in roles):
            user.active = True
            user.roles = roles          # peran selalu mengikuti Len Data Governance
            self.update_user(user)
        return user

    def _grant_user_access(self) -> None:
        """Gamma (pengguna non-admin): lihat semua dataset, akses database Trino, unggah berkas ke schema workspace."""
        gamma = self.find_role("Gamma")
        if not gamma:
            return
        for perm, view in (("all_datasource_access", "all_datasource_access"),
                           ("all_database_access", "all_database_access"),
                           ("can_upload", "Database")):
            pv = self.find_permission_view_menu(perm, view)
            if pv and pv not in gamma.permissions:
                self.add_permission_role(gamma, pv)


# ------------------------------------------------------------------ aturan data: hanya Trino
def _is_trino(uri: str | None) -> bool:
    return (uri or "").strip().lower().startswith("trino")


class DataRuleError(Exception):
    pass


def dg_sql_guard(sql: str, **kwargs) -> str:
    """SQL_QUERY_MUTATOR: pernyataan tulis hanya boleh ke <catalog>.workspace.<tabel> (nama schema wajib ditulis)."""
    import sqlglot
    from sqlglot import exp
    from superset.exceptions import SupersetException

    write = (exp.Create, exp.Insert, exp.Delete, exp.Update, exp.Drop, exp.Alter, exp.Merge, exp.TruncateTable)
    read_cmds = {"SHOW", "DESCRIBE", "DESC", "EXPLAIN", "USE", "VALUES"}
    hint = (f"Aturan data Len Data Governance: tabel hanya boleh dibuat/diubah di schema '{WRITE_SCHEMA}' "
            f"(tulis lengkap: {WRITE_SCHEMA}.<nama_tabel>). Data medallion_repository dikelola loader dan hanya-baca.")
    try:
        stmts = [s for s in sqlglot.parse(sql, read="trino") if s is not None]
    except Exception:  # noqa: BLE001 — tak terurai: tolak bila tampak menulis, sisanya biar Trino yang menilai
        if re.search(r"^\s*(create|insert|update|delete|drop|alter|merge|truncate|grant|revoke|call)\b", sql, re.I | re.M):
            raise SupersetException(hint)
        return sql
    for st in stmts:
        if isinstance(st, (exp.Query, exp.Describe)) or getattr(exp, "Show", None) and isinstance(st, exp.Show):
            continue                                   # SELECT / WITH / UNION / DESCRIBE / SHOW
        if isinstance(st, exp.Command) and str(st.this).upper() in read_cmds:
            continue
        if not isinstance(st, write):                  # GRANT, SET, CALL, perintah lain → ditolak
            raise SupersetException(hint)
        if isinstance(st, (exp.Create, exp.Drop)) and str(st.args.get("kind") or "").upper() not in ("TABLE", "VIEW"):
            raise SupersetException(hint)
        target = st.this if isinstance(st.this, exp.Table) else st.find(exp.Table)
        # ALTER (mis. RENAME TO) menyebut tabel kedua → semua tabel di pernyataan itu wajib di workspace
        targets = list(st.find_all(exp.Table)) if isinstance(st, exp.Alter) else [target]
        for t in targets:
            if t is None or t.db.lower() != WRITE_SCHEMA or (t.catalog and t.catalog.lower() != TRINO_CATALOG):
                raise SupersetException(hint)
    return sql


def _register_trino_only() -> None:
    from sqlalchemy import event
    from superset.exceptions import SupersetException
    from superset.models.core import Database

    def check(_mapper, _conn, target):
        if not _is_trino(target.sqlalchemy_uri):
            raise SupersetException("Aturan data Len Data Governance: hanya koneksi Trino lakehouse yang diizinkan.")

    event.listen(Database, "before_insert", check)
    event.listen(Database, "before_update", check)


def dg_guard(app) -> None:
    """FLASK_APP_MUTATOR: sesi Superset hanya berlaku selama token Len Data Governance yang sama masih ada;
    koneksi database selain Trino ditolak."""
    _register_trino_only()

    @app.before_request
    def _check_session_and_rules():
        if request.path.startswith(("/static/", "/health", "/login")):
            return None
        if current_user.is_authenticated:
            token = request.cookies.get(COOKIE)
            if not token or _sha(token) != session.get("dg_tok"):
                logout_user()
                session.pop("dg_tok", None)
        # uji koneksi / validasi parameter untuk mesin selain Trino → ditolak sebelum server mencoba terhubung
        if request.method == "POST" and re.search(r"/api/v1/database/(test_connection|validate_parameters)/?$", request.path):
            body = request.get_json(silent=True) or {}
            engine = str(body.get("engine") or body.get("backend") or "").lower()
            if not (_is_trino(body.get("sqlalchemy_uri")) or engine == "trino"):
                return Response(json.dumps({"message": "Hanya koneksi Trino lakehouse yang diizinkan."}),
                                status=422, mimetype="application/json")
        return None
