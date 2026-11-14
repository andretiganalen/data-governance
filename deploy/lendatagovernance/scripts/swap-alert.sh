#!/usr/bin/env bash
# Peringatan memori: jika swap terpakai > 80% (atau memori tersedia < 1 GB), tulis ke journal (peringatan)
# dan unggah log ke Documents > folder Log (maksimal satu berkas per hari). Dijalankan timer lendatagovernance-swapalert (5 menit).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
read -r ST SF < <(awk '/^SwapTotal/{t=$2} /^SwapFree/{f=$2} END{print t, f}' /proc/meminfo)
AV=$(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo)
[ "${ST:-0}" -gt 0 ] || exit 0
PCT=$(( (ST - SF) * 100 / ST ))
[ "$PCT" -gt 80 ] || [ "$AV" -lt 1024 ] || exit 0
MSG="PERINGATAN MEMORI: swap terpakai ${PCT}%, memori tersedia ${AV} MB"
logger -t ldg-swap-alert -p user.warning "$MSG"
TOP=$(ps -eo user:12,rss,etime,comm --sort=-rss | head -8 | awk 'NR==1{print;next}{printf "%s %d MB %s %s\n",$1,$2/1024,$3,$4}')
DAY=$(date +%y%m%d)
D=$(mktemp -d)
F="$D/$DAY Peringatan Memori.md"
{ echo "# Peringatan Memori $(date '+%d-%m-%Y %H:%M WIB')"; echo; echo "$MSG"; echo
  echo "Ambang: swap > 80% atau memori tersedia < 1024 MB. Pemakai memori terbesar saat peringatan pertama hari ini:"; echo; echo '```'; echo "$TOP"; echo '```'
  echo; echo "Tindakan awal: lihat Log Insiden Memori Penuh (261114), periksa AIDE dan aplikasi lain, tutup sesi yang tidak dipakai."; } > "$F"
python3 "$HERE/referensi-sinkron.py" Log "$D" "$(basename "$F")" >/dev/null 2>&1 || true
rm -rf "$D"
