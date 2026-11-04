#!/usr/bin/env bash
# Daily pg_dump of openmetadata_db, keep 14 days.
set -euo pipefail
DATA=${OM_DATA_DIR:-/srv/openmetadata}; OUT=$DATA/backup; mkdir -p "$OUT"
cd "$(dirname "$0")/.."
F="$OUT/openmetadata_db-$(date +%Y%m%d-%H%M).dump"
docker compose exec -T postgresql pg_dump -U postgres -Fc openmetadata_db > "$F"
find "$OUT" -name 'openmetadata_db-*.dump' -mtime +14 -delete
echo "backup: $F ($(du -h "$F" | cut -f1))"
