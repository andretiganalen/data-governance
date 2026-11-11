#!/usr/bin/env python3
"""Sinkron folder sumber Bronze dari Nextcloud (WebDAV) ke inbox lakehouse.

Kredensial: $LDG_DATA_DIR/secrets/nextcloud.env (NEXTCLOUD_URL, NEXTCLOUD_USER, NEXTCLOUD_APP_PASSWORD, NEXTCLOUD_FOLDER)
— app password (Login Flow v2 / Settings › Security), bukan kata sandi akun; tidak pernah di git.

Berkas .xlsx/.xlsm/.csv yang baru atau berubah (ETag) diunduh ke $LDG_DATA_DIR/medallion/inbox/ dengan nama
"<folder>__<subfolder>__<berkas>" lalu dimuat timer inbox (lakehouse.py) ke Bronze di Trino. Berkas sumber hanya
masukan Bronze — sistem rekamnya Trino. Status ETag: $LDG_DATA_DIR/medallion/nextcloud-state.json.

Pemakaian:  nextcloud_sync.py [--list] [--ingest]
  --list    hanya tampilkan isi folder (tanpa unduh)
  --ingest  setelah unduh, langsung jalankan lakehouse.py inbox (tanpa menunggu timer)
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

DATA = Path(os.environ.get("LDG_DATA_DIR", "/home/ubuntu/data-governance/data"))
INBOX = DATA / "medallion" / "inbox"
STATE = DATA / "medallion" / "nextcloud-state.json"
EXT = (".xlsx", ".xlsm", ".csv")
NS = {"d": "DAV:"}


def env() -> dict[str, str]:
    e = dict(l.strip().split("=", 1) for l in (DATA / "secrets" / "nextcloud.env").read_text().splitlines()
             if "=" in l and not l.lstrip().startswith("#"))
    for k in ("NEXTCLOUD_URL", "NEXTCLOUD_USER", "NEXTCLOUD_APP_PASSWORD", "NEXTCLOUD_FOLDER"):
        if not e.get(k):
            raise SystemExit(f"{k} kosong di secrets/nextcloud.env")
    return e


class DAV:
    def __init__(self, e: dict[str, str]):
        self.base = f"{e['NEXTCLOUD_URL'].rstrip('/')}/remote.php/dav/files/{urllib.parse.quote(e['NEXTCLOUD_USER'])}"
        self.auth = "Basic " + base64.b64encode(f"{e['NEXTCLOUD_USER']}:{e['NEXTCLOUD_APP_PASSWORD']}".encode()).decode()

    def req(self, method: str, path: str, headers: dict | None = None, body: bytes | None = None):
        url = self.base + "/" + "/".join(urllib.parse.quote(p) for p in path.strip("/").split("/"))
        r = urllib.request.Request(url, data=body, method=method,
                                   headers={"Authorization": self.auth, "User-Agent": "LenDataGovernance-ETL", **(headers or {})})
        return urllib.request.urlopen(r, timeout=120)

    def ls(self, path: str) -> list[dict]:
        body = (b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:getetag/><d:getcontentlength/>'
                b'<d:getlastmodified/><d:resourcetype/></d:prop></d:propfind>')
        root = ET.fromstring(self.req("PROPFIND", path, {"Depth": "1", "Content-Type": "application/xml"}, body).read())
        out = []
        for resp in root.findall("d:response", NS)[1:]:            # elemen pertama = folder itu sendiri
            href = urllib.parse.unquote(resp.find("d:href", NS).text)
            rel = href.split("/remote.php/dav/files/", 1)[1].split("/", 1)[1].strip("/")   # buang "<user id>/"
            p = resp.find("d:propstat/d:prop", NS)
            out.append({"path": rel, "dir": p.find("d:resourcetype/d:collection", NS) is not None,
                        "etag": (p.findtext("d:getetag", "", NS) or "").strip('"'),
                        "size": int(p.findtext("d:getcontentlength", "0", NS) or 0),
                        "modified": p.findtext("d:getlastmodified", "", NS)})
        return out

    def walk(self, path: str) -> list[dict]:
        files = []
        for it in self.ls(path):
            files += self.walk(it["path"]) if it["dir"] else [it]
        return files


def main() -> None:
    e = env()
    dav = DAV(e)
    files = dav.walk(e["NEXTCLOUD_FOLDER"])
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if "--list" in sys.argv:
        for f in files:
            print(f"{f['size']:>12,d}  {f['modified']:31s}  {f['path']}")
        print(f"{len(files)} berkas; {sum(1 for f in files if f['path'].lower().endswith(EXT))} berformat {'/'.join(EXT)}")
        return
    INBOX.mkdir(parents=True, exist_ok=True)
    new = 0
    for f in files:
        if not f["path"].lower().endswith(EXT) or state.get(f["path"]) == f["etag"]:
            continue
        name = f["path"].replace("/", "__")
        tmp = INBOX / f".{name}.part"
        with dav.req("GET", f["path"]) as r, open(tmp, "wb") as out:
            while chunk := r.read(1 << 20):
                out.write(chunk)
        tmp.rename(INBOX / name)          # nama berawalan titik diabaikan inbox sampai unduhan lengkap
        state[f["path"]] = f["etag"]
        new += 1
        print(f"  ↓ {f['path']} ({f['size']:,d} byte)")
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    print(f"{new} berkas baru/berubah diunduh ke {INBOX}")
    if new and "--ingest" in sys.argv:
        subprocess.run([sys.executable, str(Path(__file__).with_name("lakehouse.py")), "inbox"], check=True)


if __name__ == "__main__":
    main()
