#!/bin/bash
# Start Superset: migrasi metadata, admin awal (sekali), peran bawaan, lalu web server.
set -euo pipefail
superset db upgrade
if ! superset fab list-users 2>/dev/null | grep -q "username:${SUPERSET_ADMIN_USER:-admin}"; then
  superset fab create-admin --username "${SUPERSET_ADMIN_USER:-admin}" --firstname Admin --lastname "Data Governance" \
    --email "dg-admin@localhost" --password "${SUPERSET_ADMIN_PASSWORD}"
fi
superset init
exec /usr/bin/run-server.sh
