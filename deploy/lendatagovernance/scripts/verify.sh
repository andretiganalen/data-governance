#!/usr/bin/env bash
cd "$(dirname "$0")/.."
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
echo; printf 'healthcheck (8586): '; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8586/healthcheck
printf 'direct :8585      : '; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8585/
printf 'gateway landing   : '; curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: dev-data.len.co.id' http://127.0.0.1/
printf 'gateway → OM API  : '; curl -s -H 'Host: dev-data.len.co.id' http://127.0.0.1/api/v1/system/version; echo
printf 'auth provider     : '; curl -s http://127.0.0.1:8585/api/v1/system/config/auth | grep -oE '"provider":"[^"]+"'
printf 'last backup       : '; ls -t ${OM_DATA_DIR:-/srv/lendatagovernance}/backup/*.dump 2>/dev/null | head -1 || echo none
