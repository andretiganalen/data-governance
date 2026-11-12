#!/usr/bin/env bash
# Daily pg_dump of lendatagovernance_db, keep 14 days.
set -euo pipefail
DATA=${LDG_DATA_DIR:-/home/ubuntu/data-governance/data}; OUT=$DATA/backup; mkdir -p "$OUT"
cd "$(dirname "$0")/.."
F="$OUT/lendatagovernance_db-$(date +%Y%m%d-%H%M).dump"
docker compose exec -T postgresql pg_dump -U postgres -Fc lendatagovernance_db > "$F"
find "$OUT" -name 'lendatagovernance_db-*.dump' -mtime +14 -delete
echo "backup: $F ($(du -h "$F" | cut -f1))"
# File store (Documents): snapshot of data/storage (ldg-storage), keep 14 days. Pair it with the pg_dump above when migrating.
tar czf "$OUT/storage-$(date +%Y%m%d-%H%M).tgz" -C "$DATA" storage
find "$OUT" -name 'storage-*.tgz' -mtime +14 -delete
