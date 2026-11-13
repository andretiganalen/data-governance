#!/usr/bin/env bash
# Rilis manual mingguan (timer lendatagovernance-manual, tiap Senin 06:00): 3 manual PDF baru (YYMMDD CC) dengan angka dan
# daftar Master Organisasi dari Trino, lalu Manual Pengguna dan Manual Admin didaftarkan ke Dokumen > Reference.
# Tidak melakukan git commit/push: PDF baru di docs/manuals/ ditinjau lalu di-commit manual.
set -euo pipefail
ROOT=/home/ubuntu/data-governance
PY=$ROOT/data/medallion/.venv/bin/python
cd "$ROOT"
"$PY" docs/manuals/src/rilis.py
REL=$(ls docs/manuals | grep -E '^[0-9]{6} [0-9]{2} Manual Pengembang\.pdf$' | sort | tail -1 | cut -c1-9)
[ -n "$REL" ] || { echo "rilis tidak ditemukan"; exit 1; }
"$PY" deploy/lendatagovernance/scripts/referensi-tambah.py \
  "docs/manuals/$REL Manual Pengembang.pdf=Manual Admin Len Data Governance (rilis $REL)" \
  "docs/manuals/$REL Manual Pengguna.pdf=Manual Pengguna Len Data Governance (rilis $REL)"
echo "rilis mingguan selesai: $REL"
