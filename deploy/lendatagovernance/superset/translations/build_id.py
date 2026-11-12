#!/usr/bin/env python3
"""Bangun paket bahasa Indonesia (id) untuk Superset dari id.json ({"teks English": "terjemahan"}) dan messages.pot bawaan image.
Menghasilkan translations/id/LC_MESSAGES/{messages.po, messages.mo (backend/Flask-Babel), messages.json (frontend, format jed)}.
Dijalankan oleh Dockerfile saat build; aman dijalankan ulang. Teks yang belum diterjemahkan jatuh ke English."""
import json
import sys
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/superset/translations")
SRC = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/id.json")
tr = json.loads(SRC.read_text(encoding="utf-8"))

with open(BASE / "messages.pot", "rb") as f:
    cat = read_po(f, locale="id")
cat.locale = "id"
cat.project = "Superset"
cat._num_plurals, cat._plural_expr = 1, "0"   # bahasa Indonesia: satu bentuk (properti plural_forms hanya-baca di Babel 2.17)
jed = {"": {"domain": "superset", "lang": "id", "plural_forms": "nplurals=1; plural=0"}}
n = 0
for m in cat:
    if not m.id:
        continue
    mid = m.id if isinstance(m.id, str) else m.id[0]
    t = tr.get(mid)
    if not t:
        continue
    m.string = t if isinstance(m.id, str) else (t,)
    key = f"{m.context}\x04{mid}" if m.context else mid
    jed[key] = [t]
    n += 1
# teks yang dipakai frontend tetapi tidak ada di messages.pot bawaan: tambahkan langsung (backend + frontend)
known = {(m.id if isinstance(m.id, str) else m.id[0]) for m in cat if m.id}
extra = 0
for k, t in tr.items():
    if k not in known and t:
        cat.add(k, string=t)
        jed[k] = [t]
        extra += 1
out = BASE / "id" / "LC_MESSAGES"
out.mkdir(parents=True, exist_ok=True)
with open(out / "messages.po", "wb") as f:
    write_po(f, cat)
with open(out / "messages.mo", "wb") as f:
    write_mo(f, cat)
(out / "messages.json").write_text(json.dumps({"domain": "superset", "locale_data": {"superset": jed}}, ensure_ascii=False), encoding="utf-8")
print(f"id: {n} teks dari .pot + {extra} tambahan = {n + extra} diterjemahkan")
