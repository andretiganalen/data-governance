#!/usr/bin/env bash
# Create or rotate a login for the panel "Data Siap Pakai" (/unduh/).
#   scripts/panel-account.sh <user>          → generates a password, prints it ONCE
#   scripts/panel-account.sh --remove <user> → removes the login
#   add --grc first to manage E-GRC (Confidential) logins instead: scripts/panel-account.sh --grc <user>
#   E-GRC logins only with approval of the data owner (Risk Management).
# Hashes live in $DATA/secrets/unduh.htpasswd (mounted read-only into the gateway); passwords are never stored.
# Hand each password to its owner directly; rotate when someone leaves UV-1. Replaced by IDS login in phase 2.
set -euo pipefail
DATA=${OM_DATA_DIR:-/srv/lendatagovernance}
F=$DATA/secrets/unduh.htpasswd
if [[ ${1:-} == --grc ]]; then F=$DATA/secrets/unduh-grc.htpasswd; shift; fi
touch "$F"; chmod 644 "$F"          # hashes only; the gateway's nginx user must read it
if [[ ${1:-} == --remove ]]; then
  sed -i "/^${2:?user}:/d" "$F"; echo "removed ${2}"; exit 0
fi
U=${1:?usage: panel-account.sh <user>}
[[ $U =~ ^[a-z0-9._-]+$ ]] || { echo "user: a-z 0-9 . _ - only"; exit 1; }
PW=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 16)
HASH=$(openssl passwd -apr1 "$PW")
sed -i "/^${U}:/d" "$F"; echo "${U}:${HASH}" >> "$F"
echo "panel login  user: ${U}  password: ${PW}   (shown once)"
