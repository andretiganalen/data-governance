#!/bin/sh
# Satu sumber terjemahan Superset: deploy/lendatagovernance/superset/translations/id.json (dipakai build image).
# Salinannya untuk penerjemah DOM (leno-superset.js) disajikan gateway dari sini — jalankan setelah mengubah id.json.
cd "$(dirname "$0")" && cp ../../../lendatagovernance/superset/translations/id.json superset-id.json && echo "superset-id.json disinkronkan"
