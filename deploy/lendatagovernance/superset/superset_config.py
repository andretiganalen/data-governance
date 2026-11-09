# Superset — modul Visualisasi Gold, Len Data Governance.
# Rahasia dibaca dari environment (secrets/superset.env, tidak di git). Data dibaca dari Trino lakehouse;
# basis data Postgres di stack hanya menyimpan metadata Superset (pengguna, grafik, dashboard).
import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://superset:{os.environ['SUPERSET_DB_PASSWORD']}@postgresql:5432/superset"
)

APP_NAME = "Len Data Governance · Visualisasi"
APP_ICON = "/static/assets/images/len-logo.png"
APP_ICON_WIDTH = 120
LOGO_TARGET_PATH = "/superset/welcome/"
LOGO_TOOLTIP = "Len Data Governance"
FAVICONS = [{"href": "/static/assets/images/len-logo.png"}]

# Diakses lewat gateway nginx (http://<host>:8088). TLS menyusul bersama IDS (fase 2).
ENABLE_PROXY_FIX = True
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
TALISMAN_ENABLED = False
CONTENT_SECURITY_POLICY_WARNING = False

FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,          # akses dashboard per peran
    "DRILL_TO_DETAIL": True,
    "DRILL_BY": True,
    "HORIZONTAL_FILTER_BAR": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "ALERT_REPORTS": False,
}

ROW_LIMIT = 50_000
SQL_MAX_ROW = 100_000
SQLLAB_TIMEOUT = 300
SUPERSET_WEBSERVER_TIMEOUT = 300

CACHE_CONFIG = {"CACHE_TYPE": "FileSystemCache", "CACHE_DIR": "/app/superset_home/cache", "CACHE_DEFAULT_TIMEOUT": 300}
DATA_CACHE_CONFIG = {**CACHE_CONFIG, "CACHE_DEFAULT_TIMEOUT": 600}

# Palet standar Len (plan/interface-menu.md) — skema warna bawaan untuk grafik baru.
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
