# Superset — menu Visualisasi di dalam Len Data Governance (http://<host>:8585/visualisasi/).
# Tidak ada port terpisah: gateway nginx meneruskan /visualisasi/ ke kontainer superset:8088 (internal).
# Rahasia dibaca dari environment (secrets/superset.env, tidak di git). Data dibaca dari Trino lakehouse;
# Postgres di stack hanya menyimpan metadata Superset (pengguna, grafik, dashboard).
import os
from datetime import timedelta

from flask_appbuilder.security.manager import AUTH_REMOTE_USER

from dg_sso import LDGSecurityManager, dg_guard, dg_sql_guard

APP_ROOT = os.environ.get("SUPERSET_APP_ROOT", "/visualisasi")

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://superset:{os.environ['SUPERSET_DB_PASSWORD']}@postgresql:5432/superset"
)

APP_NAME = "Len Data Governance · Visualisasi"
APP_ICON = f"{APP_ROOT}/static/assets/images/len-logo.png"
LOGO_TARGET_PATH = f"{APP_ROOT}/dashboard/list/"
LOGO_TOOLTIP = "Len Data Governance"
FAVICONS = [{"href": "/static/assets/images/len-logo.png"}]   # Superset menambahkan APP_ROOT sendiri

# Tema standar Len = UIx (plan/interface-menu.md): merah utama #ae2524, Poppins, radius 8; hanya mode terang.
THEME_DEFAULT = {
    "algorithm": "default",
    "token": {
        "colorPrimary": "#ae2524",
        "colorLink": "#ae2524",
        "colorError": "#e7000b",
        "colorSuccess": "#008236",
        "colorWarning": "#bb4d00",
        "colorTextBase": "#364153",
        "colorBgLayout": "#f9fafb",
        "borderRadius": 8,
        "fontFamily": "'UIx Poppins', 'Segoe UI', Arial, sans-serif",
        "brandLogoUrl": f"{APP_ROOT}/static/assets/images/len-logo.png",
        "brandLogoAlt": "Len Data Governance",
        "brandLogoHref": f"{APP_ROOT}/dashboard/list/",
        "brandLogoHeight": "28px",
    },
}
THEME_DARK = None

# Login = sesi Len Data Governance; tidak ada kata sandi/akun Superset terpisah (dg_sso.py).
AUTH_TYPE = AUTH_REMOTE_USER
CUSTOM_SECURITY_MANAGER = LDGSecurityManager
FLASK_APP_MUTATOR = dg_guard
PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
# Ditampilkan di dalam kerangka Len Data Governance (iframe, origin sama).
HTTP_HEADERS = {"X-Frame-Options": "SAMEORIGIN"}

# Di belakang gateway nginx (:8585). TLS menyusul bersama IDS (fase 2).
ENABLE_PROXY_FIX = True
SESSION_COOKIE_NAME = "dg_visualisasi_session"   # beda dari cookie aplikasi utama di origin yang sama
SESSION_COOKIE_PATH = APP_ROOT
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
TALISMAN_ENABLED = False
CONTENT_SECURITY_POLICY_WARNING = False

FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,
    "DRILL_TO_DETAIL": True,
    "DRILL_BY": True,
    "HORIZONTAL_FILTER_BAR": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "ALERT_REPORTS": False,
}

# Aturan data: hanya Trino; tulis (CREATE/INSERT/…/unggah berkas) hanya ke lakekeeper.workspace (dg_sso.py).
SQL_QUERY_MUTATOR = dg_sql_guard
MUTATE_AFTER_SPLIT = False
PREFERRED_DATABASES = ["Trino"]
SQLLAB_CTAS_NO_LIMIT = True

ROW_LIMIT = 50_000
SQL_MAX_ROW = 100_000
SQLLAB_TIMEOUT = 300
SUPERSET_WEBSERVER_TIMEOUT = 300

CACHE_CONFIG = {"CACHE_TYPE": "FileSystemCache", "CACHE_DIR": "/app/superset_home/cache", "CACHE_DEFAULT_TIMEOUT": 300}
DATA_CACHE_CONFIG = {**CACHE_CONFIG, "CACHE_DEFAULT_TIMEOUT": 600}

# Palet standar Len — skema warna bawaan untuk grafik baru.
EXTRA_CATEGORICAL_COLOR_SCHEMES = [{
    "id": "lenDataGovernance",
    "description": "Len Data Governance",
    "label": "Len Data Governance",
    "isDefault": True,
    "colors": ["#194A80", "#DA0000", "#0562C9", "#1E7B34", "#F28C00", "#12375F", "#8BC34A", "#F2C200",
               "#838282", "#54595F", "#FF2121", "#EEF3F9"],
}]
EXTRA_SEQUENTIAL_COLOR_SCHEMES = [{
    "id": "lenRiskLevel",
    "description": "Level risiko: Low → High",
    "label": "Len Level Risiko",
    "isDiverging": False,
    "colors": ["#1E7B34", "#8BC34A", "#F2C200", "#F28C00", "#DA0000"],
}]
