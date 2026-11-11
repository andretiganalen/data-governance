#!/usr/bin/env python3
"""Daftarkan berkas referensi berversi ke data/referensi (diunduh lewat menu Referensi di aplikasi).
Aturan nama: "YYMMDD CC [Nama sesuai nomenklatur judul].ext" — CC = nomor perintah unggah, naik 1 dari CC terbesar
yang ada (semua berkas dalam satu perintah memakai CC yang sama); berkas lama tidak pernah ditimpa.
Pakai:  referensi-tambah.py "<berkas>=<Nama>" ["<berkas>=<Nama>" ...]    (Nama opsional; default: nama berkas)
Berkas referensi internal Len ("dokumen tidak terkontrol") sengaja di luar git (data/ di-ignore)."""
import re, shutil, sys
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / "data" / "referensi"
OUT.mkdir(parents=True, exist_ok=True)
cc = max([int(m.group(1)) for p in OUT.iterdir() if (m := re.match(r"^\d{6} (\d{2}) ", p.name))], default=0) + 1
for arg in sys.argv[1:]:
    src, _, name = arg.partition("=")
    src = Path(src)
    dst = OUT / f"{datetime.now():%y%m%d} {cc:02d} {name or src.stem}{src.suffix.lower()}"
    shutil.copyfile(src, dst)
    print(dst.name)

# Otomatis ke Context Center > Documents > folder "Reference" (gagal di sini tidak membatalkan pendaftaran berkas).
import subprocess
_r = subprocess.run([sys.executable, str(Path(__file__).with_name("referensi-sinkron.py"))], capture_output=True, text=True)
print(_r.stdout, end="")
if _r.returncode:
    print("PERINGATAN: sinkron ke Documents gagal:", _r.stderr.strip().splitlines()[-1:] , file=sys.stderr)
