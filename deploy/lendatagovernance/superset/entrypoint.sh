#!/bin/bash
# Start Superset (modul Visualisasi): migrasi metadata, peran bawaan, lalu web server.
# Tidak ada akun/kata sandi Superset: login memakai sesi Len Data Governance (dg_sso.py).
set -euo pipefail
superset db upgrade
superset init
exec /usr/bin/run-server.sh
