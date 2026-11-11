#!/usr/bin/env python3
"""Bangun id-id.js (modul bahasa Indonesia formal untuk aplikasi) dari id-id.json.
id-id.json = sumber yang diedit: {"label": {...}, "message": {...}, "server": {...}} dengan kunci sama seperti en-US.
Kunci yang belum diterjemahkan jatuh ke English (fallback bawaan aplikasi)."""
import json
from pathlib import Path
d = Path(__file__).parent
j = json.loads((d / "id-id.json").read_text(encoding="utf-8"))
js = "const e=JSON.parse(%s),t=JSON.parse(%s),a=JSON.parse(%s),n={label:e,message:t,server:a};export{n as default,e as label,t as message,a as server};\n" % tuple(
    json.dumps(json.dumps(j.get(k, {}), ensure_ascii=False)) for k in ("label", "message", "server"))
(d / "id-id.js").write_text(js, encoding="utf-8")
print("id-id.js:", {k: len(j.get(k, {})) for k in ("label", "message", "server")})
