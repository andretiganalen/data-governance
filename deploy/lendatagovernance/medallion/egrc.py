"""E-GRC → Medallion: Bronze (Excel apa adanya) → Silver (dim/fact/bridge) → Gold (siap dashboard).

Dipanggil oleh build_medallion.py (--egrc <xlsx>). Standar penamaan & field_id: docs/adr/dg-0002-medallion-penamaan-field-id.md.
- Setiap kolom keluaran WAJIB terdaftar di registry/field_registry.csv (satu nama kolom = satu field_id = satu arti).
- Kunci deterministik dari kode bisnis (risiko_key = '2026-RDF001'); hash SHA-1 hanya bila sumber tidak punya kode.
- ETL tidak "membetulkan" isi bisnis diam-diam: nilai sumber disimpan, nilai hitung ulang di kolom terpisah, temuan dicatat.
Isi E-GRC bersifat Confidential: Silver/Gold hanya di server; Gold disajikan di /unduh/ dengan akun khusus E-GRC.
"""
from __future__ import annotations

import csv
import hashlib
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "registry/field_registry.csv"
REF = HERE / "reference"

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
         "November", "Desember"]
BLN3 = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
LEVELS = ["Low", "Low to Moderate", "Moderate", "Moderate to High", "High"]
KELAS = ["jt_idr", "key", "kode", "nama", "label", "uraian", "teks", "kategori", "no", "tahun", "tgl", "rasio",
         "prob", "skor", "nilai", "jml", "flag", "id"]
FIELD_ID = re.compile(r"^[A-Z]{3,4}-F\d{4}$")


# ------------------------------------------------------------------ util
def txt(v) -> str | None:
    if v is None:
        return None
    s = str(v).replace("​", "").replace("\xa0", " ").replace("\r", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = "\n".join(x.strip() for x in s.split("\n")).strip()
    return s or None


def one_line(v) -> str | None:
    s = txt(v)
    return re.sub(r"\s*\n\s*", " ", s) if s else None


def num(v):
    """→ (angka|None, teks|None). '-', '' → kosong; '1,8%' → 0.018; teks lain → teks."""
    if v is None or isinstance(v, bool):
        return None, None
    if isinstance(v, (int, float)):
        return float(v), None
    s = one_line(v)
    if s is None or s in ("-", "–"):
        return None, None
    m = re.fullmatch(r"(-?\d+(?:[.,]\d+)?)\s*(%?)", s)
    if m:
        x = float(m.group(1).replace(",", "."))
        return (x / 100 if m.group(2) else x), None
    return None, s


def level_upper(s: str | None):
    m = re.fullmatch(r"Level\s*(\d+)(?:\s*-\s*(\d+))?", s or "")
    return float(m.group(2) or m.group(1)) if m else None


def parse_level(v):
    """'24 - High' → (24, 'High')."""
    s = one_line(v)
    m = re.fullmatch(r"(\d+)\s*-\s*(.+)", s or "")
    return (int(m.group(1)), m.group(2).strip()) if m else (None, s)


def r2(x):
    return None if x is None else round(x, 6)


def sha8(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:8]


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("true" if r.get(c) is True else "false" if r.get(c) is False else r.get(c)) for c in cols})


# ------------------------------------------------------------------ registry
def load_registry() -> dict[str, dict]:
    rows = list(csv.DictReader(REGISTRY.open(encoding="utf-8")))
    ids, cols, errs = set(), {}, []
    for r in rows:
        fid, col = r["field_id"], r["kolom_nama"]
        if not FIELD_ID.match(fid):
            errs.append(f"format field_id salah: {fid}")
        if fid in ids:
            errs.append(f"field_id ganda: {fid}")
        if col in cols:
            errs.append(f"kolom terdaftar dua kali: {col}")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,59}", col):
            errs.append(f"nama kolom tidak snake_case: {col}")
        if not (col == r["kelas_kode"] or col.endswith("_" + r["kelas_kode"])) or r["kelas_kode"] not in KELAS:
            errs.append(f"kata kelas tidak cocok: {col} / {r['kelas_kode']}")
        ids.add(fid)
        cols[col] = r
    for r in rows:
        if r["turunan_dari_field_id"] and r["turunan_dari_field_id"] not in ids:
            errs.append(f"turunan_dari tidak dikenal: {r['kolom_nama']} → {r['turunan_dari_field_id']}")
    if errs:
        raise SystemExit("Registry tidak valid:\n  " + "\n  ".join(errs))
    return cols


# ------------------------------------------------------------------ main
class Temuan:
    def __init__(self):
        self.rows = []

    def add(self, kategori, tingkat, sheet, jml, uraian, contoh, tindakan, pemilik="Pemilik data E-GRC (Risk Management)"):
        self.rows.append({"temuan_kode": f"GRC-Q{len(self.rows) + 1:02d}", "temuan_kategori": kategori,
                          "tingkat_kategori": tingkat, "sheet_nama": sheet, "baris_jml": jml, "temuan_uraian": uraian,
                          "contoh_uraian": contoh, "tindakan_etl_uraian": tindakan,
                          "tindak_lanjut_pemilik_nama": pemilik})


def run(xlsx: str, release: str, work: Path, gold_dir: Path) -> dict:
    import openpyxl

    regf = load_registry()
    src = Path(xlsx)
    T = Temuan()
    meta_r = {"meta_rilis_kode": release}

    # ---------------- Bronze: berkas asli + CSV per sheet (nilai tersimpan, apa adanya)
    bronze = work / "bronze" / "egrc"
    bronze.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, bronze / src.name)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    wb = openpyxl.load_workbook(src, data_only=True)
    wbf = openpyxl.load_workbook(src, data_only=False)
    sheets = {}
    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        sheets[ws.title] = grid
        with (bronze / f"{ws.title}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            for i, r in enumerate(grid, 1):
                if any(c is not None for c in r):
                    w.writerow([i] + ["" if c is None else c for c in r])
    no_cache = sum(1 for ws in wbf.worksheets for row in ws.iter_rows() for c in row
                   if isinstance(c.value, str) and c.value.startswith("=") and '""' not in c.value
                   and wb[ws.title][c.coordinate].value is None)
    if no_cache:
        T.add("Format", "Tinggi", "(semua)", no_cache, "Sel berumus tanpa nilai tersimpan (berkas belum dihitung ulang di Excel).",
              "", "Nilai dianggap kosong. Buka dan simpan ulang berkas di Excel sebelum dimuat.")

    def table(name):
        g = sheets[name]
        hdr = [one_line(h) for h in g[0]]
        out = []
        for i, r in enumerate(g[1:], 2):
            if any(c is not None for c in r):
                d = dict(zip(hdr, r))
                d["_row"] = i
                out.append(d)
        return hdr, out

    def srow(sheet, r, note=""):
        return {"meta_sumber_sheet_nama": sheet, "meta_sumber_baris_no": r["_row"], **meta_r,
                "meta_catatan_mutu_uraian": note or None}

    # ---------------- Referensi
    ent_ref = list(csv.DictReader((REF / "entitas.csv").open(encoding="utf-8")))
    ent_by_name = {one_line(v).lower(): e for e in ent_ref for v in e["varian_sumber_uraian"].split("|")}
    ent_by_prefix = {e["entitas_risiko_prefiks_kode"]: e for e in ent_ref if e["entitas_risiko_prefiks_kode"]}
    tak_ref = list(csv.DictReader((REF / "grc_taksonomi.csv").open(encoding="utf-8")))
    tak_by_var = {one_line(v).lower(): t for t in tak_ref for v in t["varian_sumber_uraian"].split("|")}
    fungsi_ref = {r["fungsi_kode"]: r["fungsi_nama"] for r in csv.DictReader((REF / "grc_fungsi.csv").open(encoding="utf-8"))}

    S: dict[str, list[dict]] = {}

    # ---------------- dim entitas (bersama)
    S["silver_dim_entitas"] = [{"entitas_key": e["entitas_key"], "entitas_nama": e["entitas_nama"],
                                "entitas_risiko_prefiks_kode": e["entitas_risiko_prefiks_kode"] or None,
                                "entitas_kode_status_kategori": e["entitas_kode_status_kategori"], **meta_r}
                               for e in ent_ref]
    usulan = [e["entitas_key"] for e in ent_ref if e["entitas_kode_status_kategori"] != "Disetujui"]
    if usulan:
        T.add("Asumsi", "Sedang", "R_Risk Strategy Matrix", len(usulan),
              "Sumber tidak punya kode entitas. Kode 3 huruf diusulkan di reference/entitas.csv.",
              ", ".join(usulan), "Dipakai sebagai entitas_key berstatus Usulan.", "Staf DG (UV-1) + Risk Management")

    # ---------------- fact ambang risiko tahunan
    _, rsm = table("R_Risk Strategy Matrix")
    S["silver_fact_grc_ambang_risiko_tahunan"] = []
    tahun_entitas, limit_entitas, bad_order, contoh_kapasitas = {}, {}, [], "-"
    for r in rsm:
        e = ent_by_name.get((one_line(r["Entity"]) or "").lower())
        m = re.search(r"(\d{4})", str(r["Periode"] or ""))
        th = int(m.group(1)) if m else None
        vals = {k: num(r[c])[0] for k, c in (("kapasitas_risiko_jt_idr", "Risk_Capacity"), ("selera_risiko_jt_idr", "Risk_Appetite"),
                                              ("toleransi_risiko_jt_idr", "Risk_Tolerance"), ("limit_risiko_jt_idr", "Risk_Limit"))}
        note = []
        if not e:
            note.append("entitas tidak ada di referensi")
        if None not in vals.values() and not (vals["limit_risiko_jt_idr"] <= vals["selera_risiko_jt_idr"]
                                             <= vals["toleransi_risiko_jt_idr"] <= vals["kapasitas_risiko_jt_idr"]):
            note.append("urutan ambang tidak limit<=selera<=toleransi<=kapasitas")
            bad_order.append(r["RSMatrix_Id"])
        ek = e["entitas_key"] if e else None
        if contoh_kapasitas == "-" and e and vals["kapasitas_risiko_jt_idr"] is not None:
            contoh_kapasitas = f"Risk_Capacity {e['entitas_nama']} = {vals['kapasitas_risiko_jt_idr']:,.0f}".replace(",", ".")
        if ek:
            tahun_entitas[ek], limit_entitas[(ek, th)] = th, vals["limit_risiko_jt_idr"]
        S["silver_fact_grc_ambang_risiko_tahunan"].append({"entitas_key": ek, "rkap_tahun": th,
                                                           **{k: r2(v) for k, v in vals.items()},
                                                           **srow("R_Risk Strategy Matrix", r, "; ".join(note))})
    if bad_order:
        T.add("Konsistensi", "Sedang", "R_Risk Strategy Matrix", len(bad_order),
              "Urutan ambang tidak memenuhi limit <= selera <= toleransi <= kapasitas.", ", ".join(bad_order),
              "Disimpan apa adanya; ambang_urutan_valid_flag = false di Gold.")
    T.add("Asumsi", "Sedang", "R_Risk Strategy Matrix, R_Risk Register", len(rsm),
          "Satuan nilai uang tidak tertulis di sumber. Rumus Excel membagi nilai asal dengan 1.000 / 1.000.000, "
          "sehingga diasumsikan seluruh nilai dalam juta rupiah.", contoh_kapasitas,
          "Kolom uang diberi akhiran _jt_idr. Mohon konfirmasi satuan.")

    # ---------------- dim periode (bersama)
    years = sorted({y for y in tahun_entitas.values() if y}) or [2026]
    S["silver_dim_periode"] = [{"periode_key": y * 100 + b, "tahun_no": y, "bulan_no": b, "bulan_nama": BULAN[b - 1],
                                "kuartal_no": (b - 1) // 3 + 1, "semester_no": (b - 1) // 6 + 1,
                                "periode_label": f"{BLN3[b - 1]} {y}", **meta_r}
                               for y in years for b in range(1, 13)]
    label = {p["periode_key"]: p["periode_label"] for p in S["silver_dim_periode"]}

    # ---------------- dim matriks & level risiko (dari sheet Trigger)
    trig = sheets["Trigger"]
    matriks = {}
    for i, row in enumerate(trig):
        for j, v in enumerate(row):
            sk, lv = parse_level(v) if isinstance(v, str) else (None, None)
            if sk is None or lv not in LEVELS:
                continue
            # sel "skala - level": skor dampak = angka terdekat di atasnya (baris judul), skor kemungkinan = angka terdekat di kirinya
            dampak = next(trig[k][j] for k in range(i - 1, -1, -1) if isinstance(trig[k][j], int))
            kemungkinan = next(row[c] for c in range(j - 1, -1, -1) if isinstance(row[c], int))
            matriks[(kemungkinan, dampak)] = (sk, lv)
    if len(matriks) != 25:
        raise SystemExit(f"Matriks risiko di sheet Trigger tidak terbaca lengkap ({len(matriks)} sel)")
    S["silver_dim_grc_matriks_risiko"] = [{"matriks_key": f"K{k}-D{d}", "kemungkinan_skor": k, "dampak_skor": d,
                                           "skala_risiko_nilai": sk, "level_risiko_kategori": lv, **meta_r}
                                          for (k, d), (sk, lv) in sorted(matriks.items())]
    S["silver_dim_grc_level_risiko"] = []
    for n, lv in enumerate(LEVELS, 1):
        sks = [sk for sk, l in matriks.values() if l == lv]
        S["silver_dim_grc_level_risiko"].append({"level_risiko_kategori": lv, "level_risiko_urutan_no": n,
                                                 "skala_risiko_min_nilai": min(sks), "skala_risiko_max_nilai": max(sks), **meta_r})
    lvl_rank = {lv: n for n, lv in enumerate(LEVELS, 1)}

    # ---------------- dim taksonomi
    tak_seen = defaultdict(set)

    def map_tak(v, sheet):
        out = []
        for part in [p for p in re.split(r"\s*;\s*", one_line(v) or "") if p]:
            t = tak_by_var.get(part.lower())
            tak_seen[t["taksonomi_key"] if t else "LAIN"].add(part)
            out.append(t["taksonomi_key"] if t else "LAIN")
        return out

    # ---------------- Risk Register → dim risiko, bridge taksonomi, dim sasaran, fact penilaian
    hdr, reg = table("R_Risk Register")
    pat = re.compile(r"^(Target|Realisasi|Realiasi) (.+?) (" + "|".join(BULAN) + r")$")
    measure_cols = defaultdict(dict)  # (jenis, bulan) → {measure: header}
    typo = set()
    for h in hdr:
        m = pat.match(h or "")
        if m:
            if m.group(1) == "Realiasi":
                typo.add(h)
            measure_cols[("TARGET" if m.group(1) == "Target" else "REALISASI", BULAN.index(m.group(3)) + 1)][m.group(2)] = h
    if typo:
        T.add("Format", "Rendah", "R_Risk Register", len(typo), "Salah ketik judul kolom 'Realiasi'.", sorted(typo)[0],
              "Dibaca sebagai 'Realisasi'.", "Pemilik template E-GRC")
    M = {"TARGET": {"dampak": "Dampak Residual", "rasio_src": "Residual Dampak terhadap Limit", "skor_d": "Skor Dampak",
                    "prob": "Kemungkinan", "skor_k": "Skor Kemungkinan", "eksp": "Exposure Risiko", "level": "Level Risiko"},
         "REALISASI": {"dampak": "Nilai Dampak", "rasio_src": "Dampak terhadap Limit", "skor_d": "Skor Dampak",
                       "prob": "Kemungkinan", "skor_k": "Skor Kemungkinan", "eksp": "Exposure Risiko", "level": "Level Risiko",
                       "biaya": "Biaya Pengendalian", "biaya_r": "% Biaya Pengendalian"}}

    sasaran, dim_risiko, bridge, fakta = {}, [], [], []
    cek = Counter()
    contoh = defaultdict(list)
    for r in reg:
        kode = one_line(r["Risk ID"])
        e = ent_by_name.get((one_line(r["Entity"]) or "").lower())
        ek = e["entitas_key"] if e else None
        pref = re.match(r"^R([A-Z]{2})\d+$", kode or "")
        if not e or (pref and ent_by_prefix.get(pref.group(1), {}).get("entitas_key") != ek):
            cek["prefiks"] += 1
            contoh["prefiks"].append(kode)
        th = tahun_entitas.get(ek)
        rk = f"{th}-{kode}"
        s_txt = one_line(r["Strategic Objective"])
        s_key = "SS-" + sha8(s_txt.lower()) if s_txt else None
        if s_txt and s_key not in sasaran:
            tema = re.split(r"\s+[–-]\s+", s_txt, maxsplit=1)[0]
            sasaran[s_key] = {"sasaran_key": s_key, "sasaran_tema_nama": tema, "sasaran_uraian": s_txt, **srow("R_Risk Register", r)}
        taks = map_tak(r["Taksonomi"], "R_Risk Register")
        for n, t in enumerate(taks, 1):
            bridge.append({"risiko_key": rk, "taksonomi_key": t, "taksonomi_urutan_no": n, **meta_r})
        dim_risiko.append({"risiko_key": rk, "risiko_kode": kode, "rkap_tahun": th, "entitas_key": ek, "sasaran_key": s_key,
                           "taksonomi_key": taks[0] if taks else None, "risiko_nama": one_line(r["Risk Register"]),
                           "risiko_penyebab_uraian": txt(r["Penyebab"]), "dampak_uraian": one_line(r["Deskripsi Dampak"]),
                           "dampak_asumsi_uraian": one_line(r["Asumsi Dampak"]), **srow("R_Risk Register", r)})
        lim = limit_entitas.get((ek, th))

        def fact(jenis, periode, g):
            d_num, d_txt = num(g("dampak"))
            src_ratio, _ = num(g("rasio_src"))
            prob, prob_txt = num(g("prob"))
            sk, lv = parse_level(g("level"))
            sd, sk_ = num(g("skor_d"))[0], num(g("skor_k"))[0]
            note = []
            if prob_txt:
                note.append(f"kemungkinan bukan angka: '{prob_txt}'")
                cek["prob_teks"] += 1
                contoh["prob_teks"].append(f"{kode} {periode or 'inheren'}")
            exp_ = num(g("eksp"))[0]
            if None not in (sd, sk_):
                m_sk, m_lv = matriks.get((int(sk_), int(sd)), (None, None))
                if (sk, lv) != (m_sk, m_lv) and sk is not None:
                    note.append(f"level sumber {sk}-{lv} ≠ matriks {m_sk}-{m_lv}")
                    cek["level"] += 1
                    contoh["level"].append(f"{kode} {periode or 'inheren'}")
                if sk is None:
                    sk, lv = m_sk, m_lv
            if None not in (d_num, prob, exp_) and abs(d_num * prob - exp_) > max(1.0, 0.01 * abs(exp_)):
                if prob and abs(d_num * 1000 * prob - exp_) <= max(1.0, 0.01 * abs(exp_)):
                    note.append("dampak tampak 1.000x terlalu kecil (salah satuan)")
                    cek["satuan"] += 1
                    contoh["satuan"].append(f"{kode} {periode or 'inheren'}: dampak {d_num:,.2f}, eksposur {exp_:,.2f}")
                else:
                    note.append("eksposur ≠ dampak × kemungkinan")
                    cek["eksposur"] += 1
                    contoh["eksposur"].append(f"{kode} {periode or 'inheren'}")
            ratio = d_num / lim if (d_num is not None and lim) else None
            if ratio is not None and src_ratio is not None and abs(ratio - src_ratio) > 1e-6:
                cek["rasio"] += 1
                contoh["rasio"].append(f"{kode} {periode or 'inheren'}: sumber {src_ratio:.2f}, hitung {ratio:.3f}")
                note.append("rasio limit sumber ≠ hitung ulang")
            if jenis != "INHEREN" and all(v is None for v in (d_num, d_txt, sd, sk_, exp_, lv)):
                return
            row = {"risiko_key": rk, "periode_key": periode, "penilaian_jenis_kategori": jenis,
                   "dampak_jt_idr": r2(d_num), "dampak_teks": d_txt, "dampak_thd_limit_rasio": r2(ratio),
                   "dampak_thd_limit_sumber_rasio": r2(src_ratio), "dampak_skor": None if sd is None else int(sd),
                   "kemungkinan_prob": r2(prob), "kemungkinan_skor": None if sk_ is None else int(sk_),
                   "skala_risiko_nilai": sk, "level_risiko_kategori": lv, "eksposur_jt_idr": r2(exp_),
                   "biaya_pengendalian_jt_idr": r2(num(g("biaya"))[0]), "biaya_pengendalian_rasio": r2(num(g("biaya_r"))[0]),
                   **srow("R_Risk Register", r, "; ".join(note))}
            fakta.append(row)

        inh = {"dampak": "Dampak Inheren", "rasio_src": "Dampak terhadap Limit", "skor_d": "Skor Dampak", "prob": "Kemungkinan",
               "skor_k": "Skor Kemungkinan", "eksp": "Exposure Risiko", "level": "Level Risiko", "biaya": "Biaya Pengendalian"}
        fact("INHEREN", None, lambda k: r.get(inh[k]) if k in inh else None)
        for (jenis, b), cols in sorted(measure_cols.items()):
            fact(jenis, th * 100 + b, lambda k, cols=cols, jenis=jenis: r.get(cols.get(M[jenis].get(k, "")), None))

    S["silver_dim_grc_sasaran_strategis"] = list(sasaran.values())
    S["silver_dim_grc_risiko"] = dim_risiko
    S["silver_bridge_grc_risiko_taksonomi"] = bridge
    S["silver_fact_grc_penilaian_risiko"] = fakta

    if cek["rasio"]:
        T.add("Perhitungan", "Tinggi", "R_Risk Register", cek["rasio"],
              "Rasio 'Dampak terhadap Limit' di sumber tidak sama dengan dampak / limit entitas (nilai diketik, bukan rumus).",
              "; ".join(contoh["rasio"][:4]),
              "Dihitung ulang (dampak_thd_limit_rasio). Nilai sumber tetap disimpan di dampak_thd_limit_sumber_rasio.")
    if cek["level"]:
        T.add("Konsistensi", "Sedang", "R_Risk Register", cek["level"], "Level risiko tertulis tidak sama dengan matriks (skor kemungkinan × skor dampak).",
              ", ".join(contoh["level"][:5]), "Nilai sumber dipertahankan; ditandai di meta_catatan_mutu_uraian.")
    if cek["eksposur"]:
        T.add("Konsistensi", "Sedang", "R_Risk Register", cek["eksposur"], "Eksposur tidak sama dengan dampak × kemungkinan (selisih > 1%).",
              ", ".join(contoh["eksposur"][:5]), "Nilai sumber dipertahankan; ditandai.")
    if cek["satuan"]:
        T.add("Perhitungan", "Tinggi", "R_Risk Register", cek["satuan"],
              "Nilai dampak 1.000 kali lebih kecil dari seharusnya: eksposur = dampak × 1.000 × kemungkinan. "
              "Rumus sel membagi nilai yang sudah dalam juta dengan 1.000 lagi.",
              "; ".join(contoh["satuan"][:3]),
              "Nilai sumber dipertahankan dan ditandai (tidak dikoreksi otomatis). Mohon perbaiki di sumber.")
    if cek["prob_teks"]:
        T.add("Format", "Rendah", "R_Risk Register", cek["prob_teks"], "Kemungkinan berisi teks, bukan angka 0-1.",
              ", ".join(contoh["prob_teks"][:5]), "Dikosongkan; ditandai.")
    if cek["prefiks"]:
        T.add("Konsistensi", "Sedang", "R_Risk Register", cek["prefiks"], "Prefiks kode risiko tidak cocok dengan entitas.",
              ", ".join(contoh["prefiks"][:5]), "Entitas diambil dari kolom Entity.")
    T.add("Kelengkapan", "Sedang", "R_Risk Register, R_Risk Profile", len(reg),
          "Tidak ada kolom periode/tahun RKAP. Tahun diambil dari Risk Strategy Matrix entitas yang sama.",
          f"RKAP {years[0]}", "rkap_tahun diisi dari ambang entitas; risiko_key = '<tahun>-<kode>'.", "Pemilik template E-GRC")
    n_qual = sum(1 for f in fakta if f["dampak_teks"])
    if n_qual:
        T.add("Format", "Rendah", "R_Risk Register", n_qual,
              "Kolom dampak berisi angka dan teks kualitatif sekaligus (mis. 'Tujuan strategis tertunda 6-9 bulan').",
              next(f["dampak_teks"] for f in fakta if f["dampak_teks"])[:80],
              "Dipisah: dampak_jt_idr (angka) dan dampak_teks (kualitatif).")
    # ---------------- D_Pengendalian → penyebab, rencana, fungsi, progres
    hdr_d, dp = table("D_Pengendalian Risiko")
    by_code = {r["risiko_kode"]: r for r in dim_risiko}
    penyebab, rencana, rb, progres = {}, {}, [], []
    name_diff, float_ids, dup_ren = set(), 0, []
    pat_d = re.compile(r"^(Realisasi|% Progress) (" + "|".join(BLN3) + r")$")
    for r in dp:
        kode = one_line(r["Id Risiko"])
        rs = by_code.get(kode)
        if not rs:
            continue
        if one_line(r["Risiko"]) != rs["risiko_nama"]:
            name_diff.add(kode)
        pid = r["Id Penyebab"]
        pno = str(int(pid)) if isinstance(pid, (int, float)) else one_line(pid)
        pk = f"{rs['risiko_key']}-P{int(float(pno)):02d}" if pno and re.fullmatch(r"\d+(\.0)?", pno) else f"{rs['risiko_key']}-P{pno}"
        if pk not in penyebab:
            penyebab[pk] = {"penyebab_key": pk, "risiko_key": rs["risiko_key"], "penyebab_kode": pno,
                            "penyebab_uraian": one_line(r["Penyebab"]), "penyebab_sumber_kategori": "D_Pengendalian Risiko",
                            **srow("D_Pengendalian Risiko", r)}
        rid = r["Id Rencana Pengendalian"]
        if isinstance(rid, float) and not rid.is_integer():
            float_ids += 1
            rno = repr(rid)
        else:
            rno = str(int(rid)) if isinstance(rid, (int, float)) else one_line(rid)
        head, _, tail = rno.partition(".")
        rnk = f"{rs['risiko_key']}-R{int(head):02d}" + (f".{tail}" if tail else "")
        if rnk in rencana:
            dup_ren.append(rnk)
            continue
        pic = one_line(r["PIC/Fungsi"])
        rencana[rnk] = {"rencana_key": rnk, "risiko_key": rs["risiko_key"], "penyebab_key": pk, "rencana_kode": rno,
                        "rencana_uraian": one_line(r["Rencana Pengendalian"]), "pic_uraian": pic,
                        **srow("D_Pengendalian Risiko", r, "" if pic else "PIC/Fungsi kosong")}
        for f in [x.strip().upper() for x in re.split(r"[,;/]", pic or "") if x.strip()]:
            rb.append({"rencana_key": rnk, "fungsi_kode": f, **meta_r})
        months = defaultdict(dict)
        for h in hdr_d:
            m = pat_d.match(h or "")
            if m:
                months[BLN3.index(m.group(2)) + 1][m.group(1)] = r.get(h)
        th = rs["rkap_tahun"]
        for b, v in sorted(months.items()):
            real = v.get("Realisasi")
            real_txt = None if isinstance(real, (int, float)) else one_line(real)
            pr = num(v.get("% Progress"))[0]
            if real_txt is None and pr is None:
                continue
            progres.append({"rencana_key": rnk, "periode_key": th * 100 + b, "progres_rasio": r2(pr),
                            "progres_realisasi_uraian": real_txt, **srow("D_Pengendalian Risiko", r)})
    # penyebab dari teks Risk Register untuk risiko tanpa baris D_Pengendalian
    have = {p["risiko_key"] for p in penyebab.values()}
    parsed = 0
    for rs in dim_risiko:
        if rs["risiko_key"] in have or not rs["risiko_penyebab_uraian"]:
            continue
        t = rs["risiko_penyebab_uraian"]
        parts = [p.strip() for p in re.split(r"(?:^|\s)\d+[a-z]?\.\s+", t) if p.strip()] if re.match(r"^\s*1\.", t) else [one_line(t)]
        for n, p in enumerate(parts, 1):
            pk = f"{rs['risiko_key']}-P{n:02d}"
            penyebab[pk] = {"penyebab_key": pk, "risiko_key": rs["risiko_key"], "penyebab_kode": str(n),
                            "penyebab_uraian": one_line(p), "penyebab_sumber_kategori": "Risk Register (dipecah dari teks)",
                            "meta_sumber_sheet_nama": "R_Risk Register", "meta_sumber_baris_no": rs["meta_sumber_baris_no"],
                            **meta_r, "meta_catatan_mutu_uraian": "dipecah otomatis dari teks bernomor"}
            parsed += 1
    S["silver_dim_grc_penyebab"] = sorted(penyebab.values(), key=lambda x: x["penyebab_key"])
    S["silver_dim_grc_rencana_pengendalian"] = list(rencana.values())
    S["silver_bridge_grc_rencana_fungsi"] = rb
    S["silver_dim_grc_fungsi"] = [{"fungsi_kode": f, "fungsi_nama": fungsi_ref.get(f) or None, **meta_r,
                                   "meta_catatan_mutu_uraian": None if fungsi_ref.get(f) else "nama fungsi belum ada di referensi"}
                                  for f in sorted({x["fungsi_kode"] for x in rb})]
    S["silver_fact_grc_progres_pengendalian_bulanan"] = progres
    if name_diff:
        T.add("Konsistensi", "Sedang", "D_Pengendalian Risiko", len(name_diff),
              "Nama risiko di sheet pengendalian berbeda dengan Risk Register untuk kode yang sama.", ", ".join(sorted(name_diff)),
              "Nama dari Risk Register dipakai (risiko_nama).")
    if float_ids:
        T.add("Format", "Sedang", "D_Pengendalian Risiko", float_ids,
              "Nomor rencana bertingkat (3.1, 3.2) disimpan sebagai angka desimal. Nomor 1.10 akan terbaca 1.1.",
              "Id Rencana Pengendalian = 3.1", "Diubah menjadi teks (rencana_kode). Simpan sebagai teks di sumber.", "Pemilik template E-GRC")
    if dup_ren:
        T.add("Konsistensi", "Sedang", "D_Pengendalian Risiko", len(dup_ren), "Nomor rencana ganda dalam satu risiko.",
              ", ".join(dup_ren[:5]), "Baris kedua diabaikan.")
    no_ctrl = sorted({r["risiko_kode"] for r in dim_risiko} - {one_line(r["Id Risiko"]) for r in dp})
    if no_ctrl:
        ents = Counter(by_code[k]["entitas_key"] for k in no_ctrl)
        T.add("Kelengkapan", "Tinggi", "D_Pengendalian Risiko", len(no_ctrl),
              "Risiko tanpa rencana pengendalian/progres: " + ", ".join(f"{k} {v} risiko" for k, v in ents.items()) + ".",
              ", ".join(no_ctrl[:6]), f"Penyebab dipecah dari teks Risk Register ({parsed} penyebab). Rencana & progres kosong.")
    no_pic = sum(1 for x in rencana.values() if not x["pic_uraian"])
    no_prog = len({x["rencana_key"] for x in rencana.values()} - {p["rencana_key"] for p in progres})
    if no_pic or no_prog:
        T.add("Kelengkapan", "Tinggi", "D_Pengendalian Risiko", max(no_pic, no_prog),
              f"{no_pic} dari {len(rencana)} rencana tanpa PIC/Fungsi; {no_prog} rencana tanpa laporan realisasi/progres.",
              "", "Dibiarkan kosong; progres_status_kategori = 'Belum ada laporan'.")
    if any(not x["fungsi_nama"] for x in S["silver_dim_grc_fungsi"]):
        T.add("Kelengkapan", "Rendah", "D_Pengendalian Risiko", len(S["silver_dim_grc_fungsi"]),
              "Kode fungsi PIC (mis. MSC, BDGP, IC) belum punya nama lengkap.", ", ".join(x["fungsi_kode"] for x in S["silver_dim_grc_fungsi"]),
              "fungsi_nama kosong; isi reference/grc_fungsi.csv.", "Staf DG (UV-1)")

    # ---------------- Risk Profile → dim parameter + fact profil bulanan
    hdr_p, prof = table("R_Risk Profile")
    pf = wbf["R_Risk Profile"]
    col_status = hdr_p.index("Status") + 1
    status_formula = str(pf.cell(2, col_status).value or "")
    th_prof = years[0]
    params, pfact = [], []
    stop = {"dan", "dalam", "yang", "pada", "terhadap", "the", "dengan", "atau", "untuk", "ytd"}
    words = lambda s: {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) >= 3 and w not in stop}  # noqa: E731
    shift, empty_formula, cannot, mismatch = [], [], [], []
    prev_name = None
    for r in prof:
        kode = one_line(r["Id Risk Profile"])
        nama = one_line(r["Risk Parameter"])
        rumus = txt(r["Target"])
        own, prv = len(words(nama) & words(rumus)), len(words(prev_name) & words(rumus))
        note = []
        if not rumus:
            empty_formula.append(kode)
        elif prev_name and prv > own:
            shift.append(kode)
            note.append("rumus tampak milik parameter baris sebelumnya")
        prev_name = nama
        lim_n, lim_t = num(r["Risk Limit"])
        tol_n, tol_t = num(r["Risk Tolerance"])
        is_level = bool(level_upper(lim_t) is not None or level_upper(tol_t) is not None)
        if is_level:
            lim_n, tol_n, jenis = level_upper(lim_t), level_upper(tol_t), "Level"
        elif tol_n is not None and tol_n > 1.5:
            jenis = "Hari" if re.search(r"days|cycle|hari", nama or "", re.I) else "Nilai"
        elif lim_n == 0 and tol_n == 1:
            jenis = "Jumlah"
        else:
            jenis = "Rasio"
        arah = None if None in (lim_n, tol_n) or lim_n == tol_n else (
            "Makin tinggi makin buruk" if tol_n > lim_n else "Makin rendah makin buruk")
        pk = f"{th_prof}-{kode}"
        taks = map_tak(r["Taksonomi"], "R_Risk Profile")
        params.append({"parameter_key": pk, "parameter_kode": kode, "rkap_tahun": th_prof, "entitas_key": None,
                       "taksonomi_key": taks[0] if taks else None, "parameter_nama": nama, "parameter_rumus_uraian": rumus,
                       "parameter_nilai_jenis_kategori": jenis, "parameter_arah_kategori": arah,
                       "ambang_limit_nilai": r2(lim_n), "ambang_limit_teks": lim_t, "ambang_selera_teks": one_line(r["Risk Appetite"]),
                       "ambang_toleransi_nilai": r2(tol_n), "ambang_toleransi_teks": tol_t,
                       "profil_status_sumber_kategori": one_line(r["Status"]), **srow("R_Risk Profile", r, "; ".join(note))})
        last_status = None
        for b, m3 in enumerate(BLN3, 1):
            v = r.get(f"Aktual {m3}")
            if v is None:
                continue
            a_n, a_t = num(v)
            x = level_upper(a_t) if is_level else a_n
            if x is None or arah is None:
                st = "Tidak dapat dinilai"
                cannot.append(f"{kode} {m3}")
            else:
                worse = (lambda p, q: p > q) if arah.startswith("Makin tinggi") else (lambda p, q: p < q)
                st = "Bahaya" if worse(x, tol_n) else "Hati-hati" if worse(x, lim_n) else "Aman"
            last_status = (b, st)
            pfact.append({"parameter_key": pk, "periode_key": th_prof * 100 + b, "aktual_nilai": r2(a_n), "aktual_teks": a_t,
                          "profil_status_kategori": st, **srow("R_Risk Profile", r)})
        if last_status and one_line(r["Status"]) and last_status[1] != one_line(r["Status"]):
            mismatch.append(f"{kode}: sumber {one_line(r['Status'])}, hitung {BLN3[last_status[0] - 1]} {last_status[1]}")
    S["silver_dim_grc_parameter_risiko"] = params
    S["silver_fact_grc_profil_risiko_bulanan"] = pfact
    if shift:
        T.add("Konsistensi", "Tinggi", "R_Risk Profile", len(shift),
              "Rumus parameter tampak bergeser satu baris: rumus lebih cocok dengan parameter di baris sebelumnya.",
              ", ".join(shift), "Rumus disimpan apa adanya dan ditandai. Mohon periksa dan perbaiki di sumber.")
    if empty_formula:
        T.add("Kelengkapan", "Sedang", "R_Risk Profile", len(empty_formula), "Rumus/definisi parameter kosong.",
              ", ".join(empty_formula), "parameter_rumus_uraian kosong.")
    if "IF(" in status_formula:
        T.add("Perhitungan", "Tinggi", "R_Risk Profile", len(prof),
              "Status di sumber hanya membandingkan satu bulan (rumus " + status_formula[:40] + "...) dengan limit. "
              "Cabang 'Hati-Hati' tidak pernah tercapai karena kondisi '=' sudah tertangkap oleh '<='.",
              "; ".join(mismatch[:4]),
              "Status dihitung ulang setiap bulan: Aman (<= limit), Hati-hati (<= toleransi), Bahaya (> toleransi). "
              "Status sumber disimpan di profil_status_sumber_kategori.")
    if cannot:
        T.add("Format", "Sedang", "R_Risk Profile", len(cannot),
              "Nilai aktual tidak bisa dibandingkan dengan ambang (campuran angka dan 'Level x-y', atau ambang tidak lengkap).",
              ", ".join(cannot[:6]), "profil_status_kategori = 'Tidak dapat dinilai'.")
    var_multi = {k: v for k, v in tak_seen.items() if len(v) > 1}
    multi = sum(1 for b in bridge if b["taksonomi_urutan_no"] > 1)
    if var_multi or multi or "LAIN" in tak_seen:
        T.add("Konsistensi", "Rendah", "R_Risk Register, R_Risk Profile", multi + sum(len(v) for v in var_multi.values()),
              "Penulisan taksonomi berbeda-beda, dan sebagian risiko memiliki dua taksonomi dalam satu sel ('A; B').",
              "; ".join(f"{k}: {' | '.join(sorted(v))}" for k, v in var_multi.items())[:160],
              "Dipetakan ke kode baku (reference/grc_taksonomi.csv). Taksonomi ganda dipecah ke silver_bridge_grc_risiko_taksonomi.")

    T.add("Kelengkapan", "Sedang", "R_Risk Profile", len(prof), "Profil risiko tidak mencantumkan entitas.",
          "RP01-RP17", "entitas_key kosong. Mohon tambahkan kolom Entity di sumber.", "Pemilik template E-GRC")

    # ---------------- Gold
    G: dict[str, list[dict]] = {}
    ent = {e["entitas_key"]: e["entitas_nama"] for e in S["silver_dim_entitas"]}
    tak_nm = {t["taksonomi_key"]: t["taksonomi_nama"] for t in tak_ref}
    tak_nm["LAIN"] = "Lainnya (belum dipetakan)"
    tak_all = defaultdict(list)
    for b in sorted(bridge, key=lambda x: x["taksonomi_urutan_no"]):
        tak_all[b["risiko_key"]].append(tak_nm[b["taksonomi_key"]])
    by_rk = defaultdict(list)
    for f in fakta:
        by_rk[f["risiko_key"]].append(f)
    prog_by_ren = defaultdict(list)
    for p in progres:
        prog_by_ren[p["rencana_key"]].append(p)
    ren_by_rk = defaultdict(list)
    for x in rencana.values():
        ren_by_rk[x["risiko_key"]].append(x)
    pen_by_rk = Counter(p["risiko_key"] for p in penyebab.values())

    reg_rows, kin_rows, peta = [], [], []
    for rs in dim_risiko:
        rk = rs["risiko_key"]
        fs = by_rk[rk]
        inh = next(f for f in fs if f["penilaian_jenis_kategori"] == "INHEREN")
        tg = {f["periode_key"]: f for f in fs if f["penilaian_jenis_kategori"] == "TARGET"}
        rl = {f["periode_key"]: f for f in fs if f["penilaian_jenis_kategori"] == "REALISASI"}
        t_last = tg[max(tg)] if tg else {}
        r_last_k = max(rl) if rl else None
        r_last = rl.get(r_last_k, {})
        tren = None
        if r_last.get("skala_risiko_nilai") is not None and inh["skala_risiko_nilai"] is not None:
            d = r_last["skala_risiko_nilai"] - inh["skala_risiko_nilai"]
            tren = "Membaik" if d < 0 else "Memburuk" if d > 0 else "Tetap"
        base = {"risiko_key": rk, "risiko_kode": rs["risiko_kode"], "rkap_tahun": rs["rkap_tahun"],
                "entitas_key": rs["entitas_key"], "entitas_nama": ent.get(rs["entitas_key"])}
        rens = ren_by_rk[rk]
        reg_rows.append({**base, "sasaran_tema_nama": sasaran.get(rs["sasaran_key"], {}).get("sasaran_tema_nama"),
                         "sasaran_uraian": sasaran.get(rs["sasaran_key"], {}).get("sasaran_uraian"),
                         "taksonomi_semua_nama": "; ".join(tak_all[rk]), "risiko_nama": rs["risiko_nama"],
                         "dampak_uraian": rs["dampak_uraian"],
                         "inheren_dampak_jt_idr": inh["dampak_jt_idr"], "inheren_dampak_teks": inh["dampak_teks"],
                         "inheren_dampak_thd_limit_rasio": inh["dampak_thd_limit_rasio"], "inheren_dampak_skor": inh["dampak_skor"],
                         "inheren_kemungkinan_prob": inh["kemungkinan_prob"], "inheren_kemungkinan_skor": inh["kemungkinan_skor"],
                         "inheren_skala_risiko_nilai": inh["skala_risiko_nilai"], "inheren_level_risiko_kategori": inh["level_risiko_kategori"],
                         "inheren_eksposur_jt_idr": inh["eksposur_jt_idr"], "biaya_pengendalian_anggaran_jt_idr": inh["biaya_pengendalian_jt_idr"],
                         "target_akhir_skala_risiko_nilai": t_last.get("skala_risiko_nilai"),
                         "target_akhir_level_risiko_kategori": t_last.get("level_risiko_kategori"),
                         "target_akhir_eksposur_jt_idr": t_last.get("eksposur_jt_idr"),
                         "realisasi_akhir_periode_key": r_last_k, "realisasi_akhir_skala_risiko_nilai": r_last.get("skala_risiko_nilai"),
                         "realisasi_akhir_level_risiko_kategori": r_last.get("level_risiko_kategori"),
                         "realisasi_akhir_eksposur_jt_idr": r_last.get("eksposur_jt_idr"),
                         "biaya_pengendalian_realisasi_jt_idr": r_last.get("biaya_pengendalian_jt_idr"),
                         "biaya_pengendalian_realisasi_rasio": r_last.get("biaya_pengendalian_rasio"),
                         "tren_kategori": tren, "penyebab_jml": pen_by_rk[rk], "rencana_jml": len(rens),
                         "rencana_berprogres_jml": sum(1 for x in rens if any((p["progres_rasio"] or 0) > 0 for p in prog_by_ren[x["rencana_key"]])),
                         **meta_r})
        for pkey in sorted(set(tg) | set(rl)):
            t, a = tg.get(pkey, {}), rl.get(pkey, {})
            dev = (a["eksposur_jt_idr"] - t["eksposur_jt_idr"]) if a.get("eksposur_jt_idr") is not None and t.get("eksposur_jt_idr") is not None else None
            cap = ("Belum ada realisasi" if not a or a.get("skala_risiko_nilai") is None else
                   "Sesuai target" if t.get("skala_risiko_nilai") is not None and a["skala_risiko_nilai"] <= t["skala_risiko_nilai"] else
                   "Di atas target" if t.get("skala_risiko_nilai") is not None else None)
            kin_rows.append({**base, "taksonomi_semua_nama": "; ".join(tak_all[rk]), "risiko_nama": rs["risiko_nama"],
                             "periode_key": pkey, "periode_label": label.get(pkey),
                             "target_dampak_jt_idr": t.get("dampak_jt_idr"), "realisasi_dampak_jt_idr": a.get("dampak_jt_idr"),
                             "target_dampak_teks": t.get("dampak_teks"), "realisasi_dampak_teks": a.get("dampak_teks"),
                             "realisasi_dampak_thd_limit_rasio": a.get("dampak_thd_limit_rasio"),
                             "target_eksposur_jt_idr": t.get("eksposur_jt_idr"), "realisasi_eksposur_jt_idr": a.get("eksposur_jt_idr"),
                             "eksposur_deviasi_jt_idr": r2(dev),
                             "target_skala_risiko_nilai": t.get("skala_risiko_nilai"), "realisasi_skala_risiko_nilai": a.get("skala_risiko_nilai"),
                             "target_level_risiko_kategori": t.get("level_risiko_kategori"),
                             "realisasi_level_risiko_kategori": a.get("level_risiko_kategori"), "capaian_kategori": cap,
                             "biaya_pengendalian_realisasi_jt_idr": a.get("biaya_pengendalian_jt_idr"),
                             "biaya_pengendalian_realisasi_rasio": a.get("biaya_pengendalian_rasio"), **meta_r})
        for pos, f, pkey in (("Inheren", inh, None), ("Target Desember", t_last, max(tg) if tg else None),
                             ("Realisasi terakhir", r_last, r_last_k)):
            if f and f.get("dampak_skor") is not None:
                peta.append({**base, "risiko_nama": rs["risiko_nama"], "posisi_kategori": pos, "periode_key": pkey,
                             "dampak_skor": f["dampak_skor"], "kemungkinan_skor": f["kemungkinan_skor"],
                             "skala_risiko_nilai": f["skala_risiko_nilai"], "level_risiko_kategori": f["level_risiko_kategori"],
                             "level_risiko_urutan_no": lvl_rank.get(f["level_risiko_kategori"]), **meta_r})
    G["gold_grc_register_risiko"] = reg_rows
    G["gold_grc_kinerja_risiko_bulanan"] = kin_rows
    G["gold_grc_peta_risiko"] = peta

    prm = {p["parameter_key"]: p for p in params}
    G["gold_grc_profil_risiko_bulanan"] = [{
        "parameter_key": f["parameter_key"], "parameter_kode": prm[f["parameter_key"]]["parameter_kode"],
        "taksonomi_nama": tak_nm.get(prm[f["parameter_key"]]["taksonomi_key"]), "parameter_nama": prm[f["parameter_key"]]["parameter_nama"],
        "parameter_rumus_uraian": prm[f["parameter_key"]]["parameter_rumus_uraian"],
        "parameter_nilai_jenis_kategori": prm[f["parameter_key"]]["parameter_nilai_jenis_kategori"],
        "periode_key": f["periode_key"], "periode_label": label.get(f["periode_key"]),
        "aktual_nilai": f["aktual_nilai"], "aktual_teks": f["aktual_teks"],
        "ambang_limit_nilai": prm[f["parameter_key"]]["ambang_limit_nilai"], "ambang_selera_teks": prm[f["parameter_key"]]["ambang_selera_teks"],
        "ambang_toleransi_nilai": prm[f["parameter_key"]]["ambang_toleransi_nilai"],
        "profil_status_kategori": f["profil_status_kategori"],
        "profil_status_sumber_kategori": prm[f["parameter_key"]]["profil_status_sumber_kategori"], **meta_r} for f in pfact]

    rprog = []
    for x in rencana.values():
        rs = next(r for r in dim_risiko if r["risiko_key"] == x["risiko_key"])
        ps = sorted(prog_by_ren[x["rencana_key"]], key=lambda p: p["periode_key"])
        last = next((p for p in reversed(ps) if p["progres_rasio"] is not None), None)
        st = ("Belum ada laporan" if not ps else "Belum mulai" if not last or not last["progres_rasio"] else
              "Selesai" if last["progres_rasio"] >= 1 else "Berjalan")
        rprog.append({"rencana_key": x["rencana_key"], "risiko_kode": rs["risiko_kode"], "entitas_nama": ent.get(rs["entitas_key"]),
                      "risiko_nama": rs["risiko_nama"], "penyebab_uraian": penyebab.get(x["penyebab_key"], {}).get("penyebab_uraian"),
                      "rencana_kode": x["rencana_kode"], "rencana_uraian": x["rencana_uraian"], "pic_uraian": x["pic_uraian"],
                      "progres_akhir_rasio": last["progres_rasio"] if last else None,
                      "progres_akhir_periode_key": last["periode_key"] if last else None, "progres_status_kategori": st, **meta_r})
    G["gold_grc_rencana_pengendalian"] = rprog
    G["gold_grc_progres_pengendalian_bulanan"] = [{
        "rencana_key": p["rencana_key"], "risiko_kode": rencana[p["rencana_key"]]["risiko_key"].split("-", 1)[1],
        "rencana_kode": rencana[p["rencana_key"]]["rencana_kode"], "periode_key": p["periode_key"],
        "periode_label": label.get(p["periode_key"]), "progres_rasio": p["progres_rasio"],
        "progres_realisasi_uraian": p["progres_realisasi_uraian"], **meta_r} for p in progres]

    amb = []
    for a in S["silver_fact_grc_ambang_risiko_tahunan"]:
        rr = [g for g in reg_rows if g["entitas_key"] == a["entitas_key"] and g["rkap_tahun"] == a["rkap_tahun"]]
        eks = sum(g["inheren_eksposur_jt_idr"] or 0 for g in rr)
        vals = [a[k] for k in ("limit_risiko_jt_idr", "selera_risiko_jt_idr", "toleransi_risiko_jt_idr", "kapasitas_risiko_jt_idr")]
        amb.append({"entitas_key": a["entitas_key"], "entitas_nama": ent.get(a["entitas_key"]), "rkap_tahun": a["rkap_tahun"],
                    "kapasitas_risiko_jt_idr": a["kapasitas_risiko_jt_idr"], "selera_risiko_jt_idr": a["selera_risiko_jt_idr"],
                    "toleransi_risiko_jt_idr": a["toleransi_risiko_jt_idr"], "limit_risiko_jt_idr": a["limit_risiko_jt_idr"],
                    "ambang_urutan_valid_flag": None if None in vals else vals == sorted(vals),
                    "risiko_jml": len(rr), "risiko_high_jml": sum(1 for g in rr if g["inheren_level_risiko_kategori"] == "High"),
                    "inheren_dampak_total_jt_idr": r2(sum(g["inheren_dampak_jt_idr"] or 0 for g in rr)) if rr else None,
                    "inheren_eksposur_total_jt_idr": r2(eks) if rr else None,
                    "eksposur_thd_limit_rasio": r2(eks / a["limit_risiko_jt_idr"]) if rr and a["limit_risiko_jt_idr"] else None,
                    **meta_r})
    G["gold_grc_ambang_risiko"] = amb
    G["gold_grc_temuan_mutu"] = [{**t, **meta_r} for t in T.rows]

    # ---------------- validasi kolom vs registry, lalu kamus data
    used = defaultdict(list)
    errs = []
    for layer in (S, G):
        for tname, rows in layer.items():
            if not re.fullmatch(r"(silver_(dim|fact|bridge)(_[a-z]+)?_[a-z_]+|gold_[a-z]+_[a-z_]+)", tname):
                errs.append(f"nama tabel tidak standar: {tname}")
            for c in (rows[0].keys() if rows else []):
                if c not in regf:
                    errs.append(f"{tname}.{c} belum terdaftar di registry")
                used[c].append(tname)
    kamus = [{"field_id": r["field_id"], "kolom_nama": c, "bisnis_nama": r["bisnis_nama"], "definisi_uraian": r["definisi_uraian"],
              "kelas_kode": r["kelas_kode"], "tipe_data_kode": r["tipe_data_kode"], "satuan_kode": r["satuan_kode"],
              "sensitivitas_kategori": r["sensitivitas_kategori"], "turunan_dari_field_id": r["turunan_dari_field_id"] or None,
              "field_status_kategori": r["field_status_kategori"], "berlaku_sejak_tgl": r["berlaku_sejak_tgl"],
              "tabel_uraian": "; ".join(sorted(set(used[c]))), **meta_r}
             for c, r in regf.items() if used.get(c) or r["field_id"].startswith("GRC-")]
    G["gold_grc_kamus_data"] = sorted(kamus, key=lambda x: x["field_id"])
    for c in G["gold_grc_kamus_data"][0]:
        if c not in regf:
            errs.append(f"gold_grc_kamus_data.{c} belum terdaftar")
    if errs:
        raise SystemExit("E-GRC: keluaran melanggar standar:\n  " + "\n  ".join(errs))

    # ---------------- tulis
    silver_dir = work / "silver" / "egrc"
    for tname, rows in S.items():
        write_csv(silver_dir / f"{tname}.csv", rows, list(rows[0].keys()) if rows else [])
    gold_dir.mkdir(parents=True, exist_ok=True)
    for tname, rows in G.items():
        write_csv(gold_dir / f"{tname}.csv", rows, list(rows[0].keys()) if rows else [])
    xlsx_name = f"{release} Data Siap Pakai E-GRC (Gold).xlsx"
    write_xlsx(gold_dir / xlsx_name, G, release, src.name, regf)

    info = {
        "gold_grc_register_risiko": ("Register Risiko", "Satu baris per risiko: entitas, sasaran, taksonomi, penilaian inheren, target Desember, realisasi terakhir, tren, jumlah penyebab & rencana.", "Risiko apa saja, seberapa besar, dan bagaimana trennya?"),
        "gold_grc_kinerja_risiko_bulanan": ("Kinerja Risiko Bulanan", "Risiko × bulan: target vs realisasi dampak, eksposur, skala & level, deviasi, capaian, serapan biaya.", "Apakah mitigasi mencapai target bulan ini?"),
        "gold_grc_peta_risiko": ("Peta Risiko (Heatmap)", "Posisi risiko pada matriks 5×5: inheren, target Desember, realisasi terakhir.", "Di mana posisi risiko pada heatmap?"),
        "gold_grc_profil_risiko_bulanan": ("Profil Risiko Bulanan", "Parameter × bulan: nilai aktual vs limit/selera/toleransi, status dihitung ulang dan status sumber.", "Indikator mana yang melewati toleransi?"),
        "gold_grc_rencana_pengendalian": ("Rencana Pengendalian", "Satu baris per rencana: risiko, penyebab, PIC, progres terakhir, status.", "Rencana mana yang belum berjalan?"),
        "gold_grc_progres_pengendalian_bulanan": ("Progres Pengendalian Bulanan", "Rencana × bulan: progres dan uraian realisasi.", "Bagaimana kemajuan pengendalian per bulan?"),
        "gold_grc_ambang_risiko": ("Ambang Risiko Entitas", "Per entitas: kapasitas, selera, toleransi, limit, total eksposur inheren dan rasionya.", "Apakah eksposur entitas masih di bawah limit?"),
        "gold_grc_temuan_mutu": ("Temuan Mutu Data", "Temuan pada sumber E-GRC dan tindakan ETL.", "Apa yang perlu diperbaiki di sumber?"),
        "gold_grc_kamus_data": ("Kamus Data E-GRC", "Setiap kolom: field_id, definisi, satuan, sensitivitas, turunan, tabel pemakai.", "Apa arti kolom ini?"),
    }
    gold_meta = [{"key": k, "file": f"{k}.csv", "nama": info[k][0], "isi": info[k][1], "menjawab": info[k][2],
                  "baris": len(G[k]), "kolom": list(G[k][0].keys()) if G[k] else [],
                  "sha256": hashlib.sha256((gold_dir / f"{k}.csv").read_bytes()).hexdigest()[:16]} for k in info]
    lv = Counter(g["inheren_level_risiko_kategori"] for g in reg_rows)
    return {
        "sumber": src.name, "sumber_sha256": digest[:16], "xlsx": xlsx_name, "gold": gold_meta,
        "bronze": {k: sum(1 for r in v[1:] if any(c is not None for c in r)) for k, v in sheets.items()},
        "silver": {k: len(v) for k, v in S.items()},
        "temuan": T.rows,
        "registry": {"total": len(regf), "grc": sum(1 for r in regf.values() if r["field_id"].startswith("GRC-")),
                     "cmn": sum(1 for r in regf.values() if r["field_id"].startswith("CMN-"))},
        "ringkas": {"risiko": len(reg_rows), "entitas_berisiko": len({g["entitas_key"] for g in reg_rows}),
                    "entitas_ambang": len(amb), "parameter": len(params), "rencana": len(rencana),
                    "rencana_berprogres": sum(1 for x in rprog if x["progres_status_kategori"] in ("Berjalan", "Selesai")),
                    "level_inheren": dict(lv), "realisasi_bulan_terakhir": label.get(max((g["realisasi_akhir_periode_key"] or 0) for g in reg_rows), "-"),
                    "profil_bahaya_terakhir": sum(1 for p in params if any(f["parameter_key"] == p["parameter_key"] for f in pfact) and
                                                  [f for f in pfact if f["parameter_key"] == p["parameter_key"]][-1]["profil_status_kategori"] == "Bahaya")},
    }


def write_xlsx(path: Path, G: dict, release: str, source: str, reg: dict) -> None:
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Info"
    head, fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="194A80")
    ws.append(["Len Data Governance — Data Siap Pakai E-GRC (Gold)"])
    ws["A1"].font = Font(bold=True, size=14, color="194A80")
    ws.append([f"Rilis {release}", f"Sumber: {source}", "Klasifikasi: CONFIDENTIAL — hanya untuk unit yang berhak"])
    ws["C2"].font = Font(bold=True, color="DA0000")
    ws.append(["Nilai uang dalam juta rupiah (_jt_idr). Rasio dalam pecahan desimal (0,25 = 25%). Arti setiap kolom: sheet kamus_data."])
    ws.append([])
    ws.append(["Sheet", "Baris"])
    for c in ws[5]:
        c.font, c.fill = head, fill
    for k, rows in G.items():
        ws.append([k.removeprefix("gold_grc_")[:31], len(rows)])
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 34, 10
    for k, rows in G.items():
        s = wb.create_sheet(k.removeprefix("gold_grc_")[:31])
        cols = list(rows[0].keys()) if rows else []
        s.append(cols)
        for i, c in enumerate(s[1], 1):
            c.font, c.fill = head, fill
            r = reg.get(cols[i - 1])
            if r:
                c.comment = Comment(f"{r['field_id']} · {r['bisnis_nama']}\n{r['definisi_uraian']}\nSatuan: {r['satuan_kode']}", "DG")
        for row in rows:
            s.append([row[c] for c in cols])
        s.freeze_panes = "A2"
        if cols:
            s.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(rows) + 1}"
        for i, c in enumerate(cols, 1):
            w = max([len(c)] + [len(str(r[c] or "")) for r in rows[:200]])
            s.column_dimensions[get_column_letter(i)].width = min(max(10, w + 2), 55)
            if c.endswith("_jt_idr"):
                for cell in s[get_column_letter(i)][1:]:
                    cell.number_format = "#,##0.00"
            elif c.endswith("_rasio") or c.endswith("_prob"):
                for cell in s[get_column_letter(i)][1:]:
                    cell.number_format = "0.0%"
    wb.save(path)
