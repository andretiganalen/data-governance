#!/usr/bin/env bash
# Bukti: aplikasi baca/tulis data bisnis hanya lewat Trino (tidak ada database atau berkas lain).
# Pemakaian: bash deploy/lendatagovernance/scripts/bukti-trino-saja.sh   (butuh sudo untuk membaca koneksi kontainer)
set -u
cd "$(dirname "$0")/../../.."
M=deploy/lendatagovernance/medallion
S="$M/app_organisasi.py $M/app_sistem.py $M/app_dataset.py $M/app_objek.py $M/export_server.py $M/erm_xlsx.py"
echo "1. Driver database lain di kode server:"
grep -nE "import (sqlite3|psycopg|pymysql|redis|pymongo|sqlalchemy|elasticsearch|opensearch)" $S || echo "   (tidak ada)"
echo "2. URL keluar selain Trino dan ldg-server:"
grep -nE "https?://[^\"' )]+" $S | grep -v "127.0.0.1\|localhost\|ldg-server" || echo "   (tidak ada)"
echo "3. Penulisan berkas lokal (selain pemicu PDF dan keluaran unduhan):"
grep -nE "open\(.*['\"]w|write_text|write_bytes|to_csv" $S || echo "   (tidak ada)"
echo "4. Penyimpanan browser di halaman baru:"
grep -lE "localStorage|sessionStorage|indexedDB" deploy/ui/leno-theme/{beranda,organisasi,sistem,dataset,objek,glosarium,shell}.* 2>/dev/null || echo "   (tidak ada)"
echo "5. Koneksi TCP aktif dari kontainer ekspor (ldg-export):"
PID=$(docker inspect -f '{{.State.Pid}}' lendatagovernance-ldg-export-1 2>/dev/null)
if [ -n "$PID" ]; then sudo -n nsenter -t "$PID" -n ss -tn 2>/dev/null | awk 'NR>1{print "   "$5}' | sort | uniq -c; else echo "   kontainer tidak berjalan"; fi
echo "   Trino (datahub.len.co.id) = $(getent hosts datahub.len.co.id | awk '{print $1}')"
