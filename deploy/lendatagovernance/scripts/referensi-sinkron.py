#!/usr/bin/env python3
"""Sinkronkan data/referensi/ ke Context Center > Documents, folder "Reference" (dibuat otomatis jika belum ada).
Idempoten: berkas yang namanya sudah ada di folder dilewati. Dipanggil oleh referensi-tambah.py; aman dijalankan sendiri.
Catatan: folder Documents bersifat datar (API tidak mendukung sub-folder), jadi "Reference" berdampingan dengan "ERM"."""
import json, mimetypes, re, sys, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "referensi"
API = "http://localhost:8585/api/v1/contextCenter/drive"
FOLDER = "Reference"
TOKEN = re.search(r"^LDG_TOKEN=(.+)$", (ROOT / "data/secrets/loader.env").read_text(), re.M).group(1).strip()


def call(method, path, body=None, headers=None):
    h = {"Authorization": f"Bearer {TOKEN}", **(headers or {})}
    data = body
    if isinstance(body, (dict, list)):
        data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
    with urllib.request.urlopen(urllib.request.Request(API + path, data=data, headers=h, method=method), timeout=120) as r:
        return json.loads(r.read() or b"{}")


def main():
    folders = call("GET", "/folders?limit=100")["data"]
    fid = next((f["id"] for f in folders if f["name"] == FOLDER), None)
    if not fid:
        fid = call("POST", "/folders", {"name": FOLDER, "displayName": FOLDER})["id"]
        print("folder dibuat:", FOLDER)
    have, after = set(), None
    while True:
        q = f"/files?fields=folder&limit=100&folderId={fid}" + (f"&after={after}" if after else "")
        r = call("GET", q)
        have |= {f.get("displayName") or f["name"] for f in r["data"]}
        after = r.get("paging", {}).get("after")
        if not after:
            break
    for p in sorted(SRC.iterdir()) if SRC.exists() else []:
        if not p.is_file() or p.name in have:
            continue
        b = uuid.uuid4().hex
        ct = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        body = (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{p.name}"\r\nContent-Type: {ct}\r\n\r\n').encode() \
            + p.read_bytes() + (f'\r\n--{b}\r\nContent-Disposition: form-data; name="folder"\r\n\r\n{FOLDER}\r\n--{b}--\r\n').encode()
        call("POST", "/files/upload", body, {"Content-Type": f"multipart/form-data; boundary={b}"})
        print("diunggah:", p.name)


if __name__ == "__main__":
    sys.exit(main())
