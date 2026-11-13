#!/usr/bin/env python3
"""Ekstrak tabel "Pembaruan Pemetaan Fungsi Generik ke Fungsi Aktual" dari PDF Nota (mis. 021/N/UQ/VIII/2026) ke JSON.

Tabel PDF itu bersel gabungan, jadi teks hasil `pdftotext -layout` tidak bisa diurai. Skrip ini membaca garis tabel (persegi hitam
tipis di SVG hasil `pdftocairo -svg`) dan koordinat kata (`pdftotext -bbox`), menentukan sel per kolom, lalu membuat satu baris
per sel Tupoksi (kolom terakhir): Direktorat, Divisi, Bagian, Fungsi Generik Lama, Fungsi Generik Baru, Tupoksi.
Sel yang kosong karena gabungan menyambung dari halaman sebelumnya diisi dari baris di atasnya ("-" tetap "-").
Hanya butuh poppler (pdftocairo, pdftotext). Hasil: data/medallion/master_organisasi/<nama>.json (di luar git).

  python nota_extract.py "<berkas.pdf>" [--first 3 --last 9] [--out berkas.json]"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NAMES = ["direktorat", "divisi", "bagian", "fungsi_lama", "fungsi_baru"]


def clean(t: str) -> str:
    t = re.sub(r"\s+", " ", html.unescape(t)).strip()
    return re.sub(r"\b(Pengembanga) n\b", r"\1n", t)   # kata terpotong di sel sempit


def _page(td: Path, pdf: Path, n: int):
    svg, wh = td / f"p{n}.svg", td / f"w{n}.html"
    subprocess.run(["pdftocairo", "-svg", "-f", str(n), "-l", str(n), str(pdf), str(svg)], check=True, capture_output=True)
    subprocess.run(["pdftotext", "-bbox", "-f", str(n), "-l", str(n), str(pdf), str(wh)], check=True, capture_output=True)
    body = svg.read_text().split("</defs>")[-1]
    hor, ver = [], []
    for m in re.finditer(r'fill="rgb\(0%, 0%, 0%\)"[^>]*? d="([^"]+)"', body):
        pts = re.findall(r"[ML] ([\d.]+) ([\d.]+)", m.group(1))
        xs, ys = [float(a) for a, _ in pts], [float(b) for _, b in pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if h < 2.5 and w > 4:
            hor.append((min(xs), max(xs), (min(ys) + max(ys)) / 2))
        elif w < 2.5 and h > 4:
            ver.append((min(xs) + max(xs)) / 2)
    words = [(float(a), float(b), float(c), float(d), w) for a, b, c, d, w in re.findall(
        r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', wh.read_text())]
    cols: list[float] = []
    for x in sorted({round(x) for x in ver}):
        if not cols or x - cols[-1] > 3:
            cols.append(x)
    return hor, words, cols


def page_cells(td: Path, pdf: Path, n: int):
    hor, words, cols = _page(td, pdf, n)
    if len(cols) != 7:
        raise SystemExit(f"halaman {n}: {len(cols)} garis kolom (diharapkan 7): bukan tabel pemetaan")
    out = []
    for c in range(6):
        x0, x1 = cols[c], cols[c + 1]
        mid = (x0 + x1) / 2
        ys: list[float] = []
        for y in sorted({round(y, 1) for a, b, y in hor if a <= mid <= b}):
            if not ys or y - ys[-1] > 2:
                ys.append(y)
        col = []
        for ya, yb in zip(ys, ys[1:]):
            ws = [w for w in words if x0 - 1 <= (w[0] + w[2]) / 2 <= x1 + 1 and ya <= (w[1] + w[3]) / 2 <= yb]
            ws.sort(key=lambda w: (round((w[1] + w[3]) / 2 / 3), w[0]))
            col.append((ya, yb, " ".join(w[4] for w in ws), len(ws)))
        out.append(col)
    return out


def extract(pdf: Path, first: int, last: int) -> list[dict]:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        for n in range(first, last + 1):
            cells = page_cells(td, pdf, n)
            for ya, yb, txt, k in cells[5]:
                if not k or "Ruang Lingkup" in txt:
                    continue
                mid = (ya + yb) / 2
                r = {"halaman": n, "tupoksi": clean(txt)}
                for c, name in enumerate(NAMES):
                    cell = next((x for x in cells[c] if x[0] <= mid <= x[1]), None)
                    r[name] = clean(cell[2]) if cell else ""
                rows.append(r)
    for prev, r in zip([{}] + rows, rows):   # sel gabungan yang menyambung dari halaman sebelumnya
        for name in NAMES:
            if not r[name]:
                r[name] = prev.get(name, "")
    for r in rows:
        r["fungsi_baru_bintang"] = len(re.findall(r"\*+$", r["fungsi_baru"]) and re.findall(r"\*+$", r["fungsi_baru"])[0])
        r["fungsi_baru"] = r["fungsi_baru"].rstrip("*").strip()
        r["tingkat_unit"] = "Divisi" if r["bagian"].startswith("Divisi ") else "Bagian"
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--first", type=int, default=3)
    ap.add_argument("--last", type=int, default=9)
    ap.add_argument("--out", default=str(ROOT / "data" / "medallion" / "master_organisasi" / "nota_021.json"))
    a = ap.parse_args()
    rows = extract(Path(a.pdf), a.first, a.last)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"{len(rows)} baris pemetaan -> {a.out}")


if __name__ == "__main__":
    main()
