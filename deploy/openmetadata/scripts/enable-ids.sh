#!/usr/bin/env bash
# Switch OpenMetadata login from basic auth to IDS (OIDC, confidential client).
# Usage: scripts/enable-ids.sh <client_id> <client_secret>
# Prereq: IDS team registered redirect URI http://dev-data.len.co.id/callback
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: $0 <client_id> <client_secret>"; exit 1; }
SEC=${OM_DATA_DIR:-/srv/openmetadata}/secrets/openmetadata.env
URL=http://dev-data.len.co.id
IDS=https://ids.len.co.id

# Preflight: fail before touching config if IDS is unreachable or rejects the credentials.
curl -fsS -m 10 -o /dev/null "$IDS/.well-known/openid-configuration" \
  || { echo "IDS discovery unreachable: $IDS"; exit 1; }
resp=$(curl -sS -m 10 -u "$1:$2" -d grant_type=client_credentials "$IDS/connect/token" || true)
grep -q '"invalid_client"' <<<"$resp" && { echo "IDS rejected client_id/client_secret (invalid_client)"; exit 1; }
getent hosts "${URL#http://}" >/dev/null \
  || echo "WARN: ${URL#http://} has no DNS record; IDS will redirect there, so each PC needs a hosts entry (README › DNS)"

cp "$SEC" "$SEC.bak.$(date +%s)"
sed -i '/^AUTHENTICATION_\|^OIDC_\|^CUSTOM_OIDC_/d' "$SEC"
cat >> "$SEC" <<ENV
AUTHENTICATION_PROVIDER=custom-oidc
CUSTOM_OIDC_AUTHENTICATION_PROVIDER_NAME=IDS
AUTHENTICATION_CLIENT_TYPE=confidential
AUTHENTICATION_AUTHORITY=https://ids.len.co.id
AUTHENTICATION_CLIENT_ID=$1
AUTHENTICATION_CALLBACK_URL=$URL/callback
AUTHENTICATION_PUBLIC_KEYS=[http://localhost:8585/api/v1/system/config/jwks,https://ids.len.co.id/.well-known/openid-configuration/jwks]
AUTHENTICATION_JWT_PRINCIPAL_CLAIMS=[email,preferred_username,sub]
AUTHENTICATION_ENABLE_SELF_SIGNUP=true
OIDC_TYPE=custom
OIDC_CLIENT_ID=$1
OIDC_CLIENT_SECRET=$2
OIDC_SCOPE=openid email profile
OIDC_DISCOVERY_URI=https://ids.len.co.id/.well-known/openid-configuration
OIDC_RESPONSE_TYPE=code
OIDC_CALLBACK=$URL/callback
OIDC_SERVER_URL=$URL
OIDC_CLIENT_AUTH_METHOD=client_secret_post
OIDC_PROMPT_TYPE=login
ENV
sed -i 's/^AUTHORIZER_ADMIN_PRINCIPALS=.*/AUTHORIZER_ADMIN_PRINCIPALS=[admin,andre.tigana]/' "$SEC"
sed -i 's/data-ids-status" content="[a-z]*"/data-ids-status" content="on"/' "$(dirname "$0")/../gateway/html/index.html"
cd "$(dirname "$0")/.." && docker compose up -d --force-recreate openmetadata-server gateway
echo "IDS enabled. Login at $URL"
