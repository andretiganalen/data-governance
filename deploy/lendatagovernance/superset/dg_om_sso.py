"""SSO Visualisasi ← sesi Len Data Governance (OpenMetadata). Tidak ada kredensial terpisah.

Alur:
  1. leno-menu.js (disisipkan gateway ke UI OpenMetadata) menangkap token Bearer yang dipakai UI OpenMetadata
     dan menaruhnya di cookie `dg_om_token` dengan path /visualisasi (hanya terkirim ke modul Visualisasi).
  2. /visualisasi/login/ memeriksa token itu ke OpenMetadata (GET /api/v1/users/loggedInUser). Bila sah,
     pengguna yang sama dimasukkan ke Superset: dicocokkan lewat email; dibuat otomatis bila belum ada.
     Peran mengikuti OpenMetadata: Admin OM → Admin; selain itu → Gamma (lihat semua dataset, bisa membuat grafik).
  3. Setiap permintaan: bila cookie hilang/berganti (logout atau token diperbarui di OpenMetadata), sesi Superset
     diakhiri dan login diulang otomatis dari token yang berlaku.
"""
from __future__ import annotations

import hashlib
import logging
import os

import requests
from flask import Response, redirect, request, session
from flask_appbuilder import expose
from flask_appbuilder.security.views import AuthRemoteUserView
from flask_appbuilder.utils.base import get_safe_redirect
from flask_login import current_user, login_user, logout_user

from superset.security import SupersetSecurityManager

log = logging.getLogger(__name__)
OM_API = os.environ.get("DG_OM_API", "http://openmetadata-server:8585/api/v1")
COOKIE = "dg_om_token"

NOT_SIGNED_IN = """<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Visualisasi</title></head>
<body style="font-family:Montserrat,'Open Sans',Arial,sans-serif;color:#3B3B3B;background:#F5F6F8;padding:40px">
<div style="max-width:520px;margin:auto;background:#fff;border:1px solid #E6E6E6;border-radius:4px;padding:28px">
<h3 style="color:#194A80;margin-top:0">Sesi Len Data Governance tidak ditemukan</h3>
<p>Visualisasi memakai login Len Data Governance. Masuk terlebih dahulu, lalu buka menu <b>Visualisasi</b>.</p>
<p><a href="/" target="_top" style="color:#0562C9">Buka Len Data Governance</a></p></div></body></html>"""


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def om_whoami(token: str) -> dict | None:
    try:
        r = requests.get(f"{OM_API}/users/loggedInUser", params={"fields": "roles,teams"},
                         headers={"Authorization": f"Bearer {token}"}, timeout=10)
    except requests.RequestException as e:
        log.warning("OpenMetadata tidak terjangkau untuk validasi sesi: %s", e)
        return None
    return r.json() if r.status_code == 200 else None


def _om_login(appbuilder):
    next_url = get_safe_redirect(request.args.get("next", ""))
    token = request.cookies.get(COOKIE)
    info = om_whoami(token) if token else None
    user = appbuilder.sm.om_sync_user(info) if info else None
    if user is None:
        return Response(NOT_SIGNED_IN, status=401, mimetype="text/html")
    login_user(user, remember=False)
    session["dg_tok"] = _sha(token)
    return redirect(next_url or appbuilder.get_url_for_index)


class OMAuthView(AuthRemoteUserView):
    @expose("/login/")
    def login(self):
        return _om_login(self.appbuilder)


def _om_login_view():
    """Pengganti SupersetAuthView (/login/) — Superset 6 mendaftarkannya lebih dulu dari view konfigurasi."""
    from superset.views.base import BaseSupersetView
    from flask_appbuilder.security.views import AuthView

    class OMLoginView(BaseSupersetView, AuthView):
        route_base = "/login"

        @expose("/")
        def login(self, provider=None):
            return _om_login(self.appbuilder)

    return OMLoginView


class OMSecurityManager(SupersetSecurityManager):
    authremoteuserview = OMAuthView

    def register_views(self) -> None:
        import superset.views.auth as auth_views
        original = auth_views.SupersetAuthView
        auth_views.SupersetAuthView = _om_login_view()
        try:
            super().register_views()
        finally:
            auth_views.SupersetAuthView = original

    def om_sync_user(self, info: dict):
        email = (info.get("email") or "").strip().lower()
        name = info.get("name") or email
        if not name:
            return None
        display = (info.get("displayName") or name).strip()
        first, _, last = display.partition(" ")
        role = self.find_role("Admin" if info.get("isAdmin") else "Gamma")
        self._grant_viewer_access()
        user = (self.find_user(email=email) if email else None) or self.find_user(username=email or name)
        if user is None:
            user = self.add_user(username=email or name, first_name=first or name, last_name=last or "-",
                                 email=email or f"{name}@openmetadata.local", role=role)
            log.info("Pengguna Visualisasi dibuat dari sesi OpenMetadata: %s", email or name)
        else:
            if not user.active or [r.name for r in user.roles] != [role.name]:
                user.active = True
                user.roles = [role]          # peran selalu mengikuti OpenMetadata
                self.update_user(user)
        return user

    def _grant_viewer_access(self) -> None:
        """Gamma (pengguna non-admin) boleh melihat semua dataset Gold — akses data tetap hanya-baca di Trino."""
        gamma = self.find_role("Gamma")
        pv = self.find_permission_view_menu("all_datasource_access", "all_datasource_access")
        if gamma and pv and pv not in gamma.permissions:
            self.add_permission_role(gamma, pv)


def dg_guard(app) -> None:
    """FLASK_APP_MUTATOR: sesi Superset hanya berlaku selama token Len Data Governance yang sama masih ada."""
    @app.before_request
    def _check_om_session():
        if request.path.startswith(("/static/", "/health", "/login")):
            return None
        if current_user.is_authenticated:
            token = request.cookies.get(COOKIE)
            if not token or _sha(token) != session.get("dg_tok"):
                logout_user()
                session.pop("dg_tok", None)
        return None
