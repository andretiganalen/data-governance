#!/bin/bash
# Runs once on first init of the data dir. Metadata DB for Superset (users, charts, dashboards) — idempotent.
# Existing installs: scripts/superset-init-db.sh does the same against the running container.
set -euo pipefail
[[ -n "${SUPERSET_DB_PASSWORD:-}" ]] || exit 0
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d postgres <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'superset') THEN
    CREATE ROLE superset LOGIN PASSWORD '${SUPERSET_DB_PASSWORD}';
  END IF;
END \$\$;
SQL
if ! psql -tAc "SELECT 1 FROM pg_database WHERE datname='superset'" --username "$POSTGRES_USER" -d postgres | grep -q 1; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d postgres -c "CREATE DATABASE superset OWNER superset"
fi
