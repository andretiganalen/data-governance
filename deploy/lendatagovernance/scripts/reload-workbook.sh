#!/usr/bin/env bash
# Reload Workbook Governance into OpenMetadata and compare defect counts with the previous run.
# Usage: scripts/reload-workbook.sh [path/to/workbook.xlsx]
set -euo pipefail
WB=${1:-"/home/ubuntu/data-governance/templates/261016 Rev.0.1_Data Governance_ERM.xlsx"}
REP=/srv/lendatagovernance/reports
[[ -f $WB ]] || { echo "Workbook not found: $WB"; exit 1; }
count() { grep -m1 -oP '^## Cacat \(\K[0-9]+' "$1" 2>/dev/null || echo "?"; }
PREV=$(ls -t $REP/workbook-defects-*.md 2>/dev/null | grep -v -- '-dry' | head -1 || true)
BEFORE=$( [[ -n $PREV ]] && count "$PREV" || echo "-" )
[[ -n $PREV ]] && cp "$PREV" "$PREV.prev"
cd "$(dirname "$0")/../loader"
python3 om_loader.py workbook "$WB"
NOW=$(ls -t $REP/workbook-defects-*.md | grep -v -- '-dry' | head -1)
echo; echo "Defects: before=$BEFORE  after=$(count "$NOW")"
defects() { sed -n '/^## Cacat/,$p' "$1" | grep '^- ' | sort; }
if [[ -n $PREV ]]; then
  CHANGES=$(diff <(defects "$PREV.prev") <(defects "$NOW") | grep -E '^[<>]' | sed 's/^</  closed:/;s/^>/  new:   /' || true)
  echo "--- changes vs previous run:"; echo "${CHANGES:-  (no change)}"
fi
