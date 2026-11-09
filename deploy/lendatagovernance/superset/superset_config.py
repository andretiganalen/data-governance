# Superset — menu Visualisasi Gold di dalam OpenMetadata (http://<host>:8585/visualisasi/), Len Data Governance.
# Tidak ada port terpisah: gateway nginx meneruskan /visualisasi/ ke kontainer superset:8088 (internal).
# Rahasia dibaca dari environment (secrets/superset.env, tidak di git). Data dibaca dari Trino lakehouse;
# Postgres di stack hanya menyimpan metadata Superset (pengguna, grafik, dashboard).
import os

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

# Tema standar Len (plan/interface-menu.md): navy utama, merah aksen, biru tautan; hanya mode terang.
THEME_DEFAULT = {
    "algorithm": "default",
    "token": {
        "colorPrimary": "#194A80",
        "colorLink": "#0562C9",
        "colorError": "#DA0000",
        "colorSuccess": "#1E7B34",
        "colorWarning": "#F28C00",
        "colorTextBase": "#3B3B3B",
        "colorBgLayout": "#F5F6F8",
        "borderRadius": 4,
        "fontFamily": "Montserrat, 'Open Sans', 'Segoe UI', Arial, sans-serif",
        "brandLogoUrl": f"{APP_ROOT}/static/assets/images/len-logo.png",
        "brandLogoAlt": "Len Data Governance",
        "brandLogoHref": f"{APP_ROOT}/dashboard/list/",
        "brandLogoHeight": "28px",
    },
}
THEME_DARK = None

# Di belakang gateway nginx (:8585). TLS menyusul bersama IDS (fase 2).
ENABLE_PROXY_FIX = True
SESSION_COOKIE_NAME = "dg_visualisasi_session"   # beda dari cookie OpenMetadata di origin yang sama
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
