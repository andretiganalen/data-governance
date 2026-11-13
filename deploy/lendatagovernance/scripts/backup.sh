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
# tar runs INSIDE the ldg-storage container (as root): the files there are owned by root and unreadable for the host user,
# which made the earlier host-side tar exit with errors and leave a partial archive.
S="$OUT/storage-$(date +%Y%m%d-%H%M).tgz"
docker compose exec -T ldg-storage tar czf - -C /data . > "$S.part"
tar tzf "$S.part" > /dev/null          # archive must be readable end to end before it replaces anything
mv "$S.part" "$S"
echo "backup: $S ($(du -h "$S" | cut -f1))"
find "$OUT" -name 'storage-*.tgz' -mtime +14 -delete
