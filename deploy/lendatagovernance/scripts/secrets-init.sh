#!/usr/bin/env bash
# Generate per-server secrets ONCE. Never overwrites existing files.
set -euo pipefail
DATA=${OM_DATA_DIR:-/srv/lendatagovernance}
SEC=$DATA/secrets
mkdir -p "$SEC/jwt"; chmod 700 "$SEC"
rnd() { openssl rand -base64 36 | tr -dc 'A-Za-z0-9' | head -c "${1:-32}"; }

if [[ ! -f $SEC/postgres.env ]]; then
  PG_PW=$(rnd); OM_PW=$(rnd)
  printf 'POSTGRES_USER=postgres\nPOSTGRES_PASSWORD=%s\nOM_DB_PASSWORD=%s\n' "$PG_PW" "$OM_PW" > "$SEC/postgres.env"
  echo "created postgres.env"
fi
source "$SEC/postgres.env"

if [[ ! -f $SEC/openmetadata.env ]]; then
  cat > "$SEC/openmetadata.env" <<ENV
# --- secrets (generated $(date -I)) ---
DB_USER_PASSWORD=${OM_DB_PASSWORD}
FERNET_KEY=$(openssl rand -base64 32)
JWT_KEY_ID=$(cat /proc/sys/kernel/random/uuid)

# --- admins: email local-part (basic) / full principal (OIDC) ---
AUTHORIZER_ADMIN_PRINCIPALS=[admin,andre.tigana]

# --- Authentication: phase 1 = basic. Switch to IDS with scripts/enable-ids.sh ---
AUTHENTICATION_PROVIDER=basic
AUTHENTICATION_CLIENT_TYPE=public
AUTHENTICATION_ENABLE_SELF_SIGNUP=true
AUTHENTICATION_PUBLIC_KEYS=[http://localhost:8585/api/v1/system/config/jwks]
ENV
  echo "created openmetadata.env"
fi

if [[ ! -f $SEC/superset.env ]]; then
  SS_DB=$(rnd)
  printf 'SUPERSET_SECRET_KEY=%s\nSUPERSET_DB_PASSWORD=%s\n' "$(rnd 48)" "$SS_DB" > "$SEC/superset.env"
  grep -q '^SUPERSET_DB_PASSWORD=' "$SEC/postgres.env" || echo "SUPERSET_DB_PASSWORD=$SS_DB" >> "$SEC/postgres.env"
  chmod 600 "$SEC/superset.env"
  echo "created superset.env (no login password: Visualisasi uses the Len Data Governance session)"
fi

if [[ ! -f $SEC/jwt/private_key.der ]]; then
  openssl genrsa -out "$SEC/jwt/private_key.pem" 2048 2>/dev/null
  openssl pkcs8 -topk8 -inform PEM -outform DER -in "$SEC/jwt/private_key.pem" -out "$SEC/jwt/private_key.der" -nocrypt
  openssl rsa -in "$SEC/jwt/private_key.pem" -pubout -outform DER -out "$SEC/jwt/public_key.der" 2>/dev/null
  echo "created JWT RSA keypair"
fi
chmod 600 "$SEC"/*.env; chmod 644 "$SEC"/jwt/*.der; chmod 600 "$SEC"/jwt/*.pem
echo "Secrets in $SEC — copy this folder to the team password vault."
