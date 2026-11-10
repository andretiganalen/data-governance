#!/bin/bash
# Runs once on first init of the data dir. Creates the catalog role + database (idempotent).
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d postgres <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lendatagovernance_user') THEN
    CREATE ROLE lendatagovernance_user LOGIN PASSWORD '${LDG_DB_PASSWORD}';
  END IF;
END \$\$;
SQL
if ! psql -tAc "SELECT 1 FROM pg_database WHERE datname='lendatagovernance_db'" --username "$POSTGRES_USER" -d postgres | grep -q 1; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d postgres -c "CREATE DATABASE lendatagovernance_db OWNER lendatagovernance_user"
fi
