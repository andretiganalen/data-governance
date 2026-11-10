"""Program Task Force Asta Cita (domain astacita): Bronze berkas DBASTACITA → Silver → Gold, seluruhnya SQL di Trino.

Sumber: Nextcloud DBASTACITA (nextcloud_sync.py → inbox → Bronze). Berkas utama DBASTACITA/DBASTACITA.xlsx →
tabel bronze_file_dbastacita_dbastacita_<sheet>; tiap tabel dibaca dari versi berkas TERBARU (_file_id dengan _ingested_at
terakhir), sehingga unggahan ulang DBASTACITA.xlsx otomatis menggantikan isi Silver/Gold.

Kunci penghubung = tema bidang (theme_code) lewat daftar sinonim THEMES — nomor "Asta Cita N" berbeda antar sheet
(Profile vs Hasil Kompilasi); nomor resmi mengikuti sheet Profile. Nilai sumber tidak diubah diam-diam: nilai asli
disimpan (budget_source, status_source) dan penyimpangan masuk gold_astacita_dq_finding.
"""
from __future__ import annotations

import re
from datetime import datetime

import lakehouse as L
import sdm

SRC = "ASTACITA"
PREFIX = "bronze_file_dbastacita_dbastacita_"
THEMES = {  # theme_code → ejaan yang ditemui di berkas DBASTACITA
    "SEMICON": ["Semikonduktor", "Semiconductor"],
    "EO_SENSOR": ["Electro-Optic & Sensor Technologies"],
    "AI": ["Artificial Intelligence"],
    "CYBER": ["Cyber Security", "Cybersecurity"],
    "SATELLITE": ["Satellite & Remote Sensing Technologies"],
    "RADAR_EW": ["Radar & Electronic Warfare System"],
    "UAS": ["Automation & Electronic for Unmanned Autonomous", "Robotic, Automation & Electronic for UAS"],
    "C2": ["Command, Control, & Communication, Datalink, and Combat Management System", "C2, Datalink & Combat Management System"],
}


def _k(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def nk(x: str) -> str:
    """Kunci tema di SQL: huruf kecil, hanya a-z0-9."""
    return f"regexp_replace(lower(trim({x})), '[^a-z0-9]', '')"


def theme_lookup() -> str:
    pairs = dict.fromkeys((code, _k(n)) for code, names in THEMES.items() for n in names)   # unik: ejaan berbeda bisa berkunci sama
    vals = ", ".join(f"({L.sq(c)}, {L.sq(k)})" for c, k in pairs)
    return f"(SELECT * FROM (VALUES {vals}) AS v(theme_code, k))"


def num(x: str) -> str:
    return f"try_cast(replace(trim({x}), ',', '.') AS double)"


def dt(x: str) -> str:
    return f"try_cast(substr(trim({x}), 1, 10) AS date)"


def silver(tq: L.Trino, batch_id: str, now: datetime) -> dict[str, dict[str, str]]:
    def src(sheet: str) -> str:   # versi berkas terbaru tabel Bronze ini
        t = f'{tq.catalog}.{tq.schema}."{PREFIX}{sheet}"'
        return f"(SELECT * FROM {t} WHERE _file_id = (SELECT max_by(_file_id, _ingested_at) FROM {t}))"
    TL = theme_lookup()
    lin = lambda a: {"_file_id": f"{a}._file_id", "_batch_id": L.sq(batch_id), "_source_system": L.sq(SRC),  # noqa: E731
                     "_source_file": f"{a}._source_file", "_loaded_at": L.lit(now, "timestamp")}
    syn = " UNION ALL ".join(f"SELECT {L.sq(c)} AS theme_code, {L.sq(' | '.join(n))} AS syn" for c, n in THEMES.items())
    S: dict[str, dict[str, str]] = {}
    S["silver_dim_astacita_theme"] = {
        "_from": f"(SELECT tl.theme_code, max(try_cast(regexp_extract(p.astacita, '[0-9]+') AS integer)) AS no, max(p.astacita) AS label, "
                 f"max(p.nama_program_asta_cita) AS nm, max(p._file_id) AS _file_id, max(p._source_file) AS _source_file "
                 f"FROM {src('profile')} p JOIN {TL} tl ON tl.k = {nk('p.nama_program_asta_cita')} GROUP BY tl.theme_code) x "
                 f"JOIN ({syn}) s ON s.theme_code = x.theme_code",
        "theme_code": "x.theme_code", "astacita_no": "x.no", "astacita_label": "x.label", "theme_name": "x.nm",
        "theme_synonyms": "s.syn", **lin("x")}
    S["silver_dim_astacita_program"] = {
        "_from": f"(SELECT p.*, row_number() OVER (PARTITION BY p.nama_program_asta_cita ORDER BY p._row_no) AS rn FROM {src('profile')} p "
                 f"WHERE p.program IS NOT NULL AND trim(p.program) NOT IN ('', '-')) p LEFT JOIN {TL} tl ON tl.k = {nk('p.nama_program_asta_cita')}",
        "program_id": "coalesce(tl.theme_code, 'NA') || '-' || CAST(p.rn AS varchar)", "theme_code": "tl.theme_code",
        "profile_code": "p.kode", "program_no": "p.nomor_program", "program_name": "p.program", "budget_idr": num("p.anggaran"),
        "budget_source": "p.anggaran", "budget_status": "p.status_anggaran", "co_lead": "p.co_lead", "program_lead": "p.program_lead",
        "description": "p.deskripsi", "output_description": "p.output", "operating_concept": "p.konsep_operasi",
        "period_label": "p.periode", "stage_label": "p.tahapan", **lin("p")}
    S["silver_fact_astacita_scurve_weekly"] = {
        "_from": f"{src('kurva_s')} k LEFT JOIN {TL} tl ON tl.k = {nk('k.nama_program_asta_cita')} WHERE {dt('k.bulan')} IS NOT NULL",
        "theme_code": "tl.theme_code", "period_year": f"year({dt('k.bulan')})", "period_month": f"month({dt('k.bulan')})",
        "week_no": "try_cast(regexp_extract(k.week, '[0-9]+') AS integer)",
        "date_key": f"year({dt('k.bulan')}) * 10000 + month({dt('k.bulan')}) * 100 + 1",
        "plan_monthly_ratio": num("k.rencana_bulanan"), "plan_cumulative_ratio": num("k.akumulasi_rencana"),
        "actual_monthly_ratio": num("k.realisasi_bulanan"), "actual_cumulative_ratio": num("k.akumulasi_realisasi"),
        "deviation_cumulative_ratio": num("k.deviasi_akumulasi"), **lin("k")}
    st = "regexp_replace(lower(o.status_completed_in_progress_not_started), '[^a-z]', '')"
    S["silver_fact_astacita_output"] = {
        "_from": f"{src('output')} o LEFT JOIN {TL} tl ON tl.k = {nk('o.nama_program_asta_cita')} WHERE o.output_deliverable IS NOT NULL",
        "theme_code": "tl.theme_code", "output_no": "try_cast(o.no AS integer)", "output_name": "o.output_deliverable",
        "output_summary": "o.summary_output",
        "status": f"CASE {st} WHEN 'completed' THEN 'Completed' WHEN 'inprogress' THEN 'In Progress' WHEN 'onprogress' THEN 'In Progress' "
                  f"WHEN 'notstarted' THEN 'Not Started' ELSE o.status_completed_in_progress_not_started END",
        "status_source": "o.status_completed_in_progress_not_started", "progress_ratio": num("o.progres"),
        "reporting_period_label": "o.priode_pelaporan", "notes": "o.keterangan", **lin("o")}
    S["silver_fact_astacita_issue"] = {
        "_from": f"{src('kendala_dan_strategi')} k LEFT JOIN {TL} tl ON tl.k = {nk('k.nama_program_asta_cita')} "
                 f"WHERE coalesce(k.kendala, k.summary_kendala, k.strategy) IS NOT NULL",
        "theme_code": "tl.theme_code", "period_year": f"year({dt('k.bulan')})", "period_month": f"month({dt('k.bulan')})",
        "date_key": f"year({dt('k.bulan')}) * 10000 + month({dt('k.bulan')}) * 100 + 1", "program_name": "k.program",
        "issue": "k.kendala", "issue_description": "k.deskripsi_masalah", "issue_summary": "k.summary_kendala",
        "strategy": "k.strategy", "strategy_summary": "k.summary_strategy", "support_needed": "k.dukungan_yang_di_butuhkan", **lin("k")}
    S["silver_fact_astacita_activity_monthly"] = {
        "_from": f"{src('8_asta_cita')} a LEFT JOIN {TL} tl ON tl.k = {nk('a.asta_cita')} "
                 f"WHERE a.judul_kegiatan IS NOT NULL AND trim(a.judul_kegiatan) NOT IN ('', '-')",
        "theme_code": "tl.theme_code", "period_year": f"year({dt('a.date')})", "period_month": f"month({dt('a.date')})",
        "date_key": f"year({dt('a.date')}) * 10000 + month({dt('a.date')}) * 100 + 1", "activity_category": "a.kategori_kegiatan",
        "activity_title": "a.judul_kegiatan", "baseline_ratio": num("a.baseline"), "actual_ratio": num("a.realisasi"),
        "deviation_cause": "a.penyebab_deviasi", **lin("a")}
    S["silver_fact_astacita_priority_score"] = {
        "_from": f"{src('hasil_kompilasi')} h LEFT JOIN {TL} tl ON tl.k = {nk('h.program')} WHERE h.program IS NOT NULL",
        "theme_code": "tl.theme_code", "survey_code": "h.kode", "survey_label": "h.asta_cita", "avg_impact": num("h.avg_impact"),
        "avg_business": num("h.avg_business"), "avg_resource": num("h.avg_resource"), "avg_risk": num("h.avg_risk"),
        "risk_score_used": num("h.risk_score_used"), "consensus_score": num("h.consensus_score"),
        "aip_final_score": num("h.aip_final_score"), "aip_rank": f"CAST({num('h.aip_rank')} AS integer)",
        "function_balanced_score": num("h.function_balanced_score"), "balanced_rank": f"CAST({num('h.balanced_rank')} AS integer)",
        **lin("h")}
    S["silver_dim_astacita_manpower"] = {
        "_from": f"{src('manpower')} m LEFT JOIN {TL} tl ON tl.k = {nk('m.nama_asta_cita')} WHERE m.nama IS NOT NULL",
        "theme_code": "tl.theme_code", "person_name": "m.nama", "role_status": "m.status", "program_name": "m.nama_program", **lin("m")}
    return S


def gold(tq: L.Trino, batch_id: str, now: datetime) -> dict[str, dict[str, str]]:
    F = tq.fq
    TH, PR, SC, OU, IS, PS, MP = (F(x) for x in ("silver_dim_astacita_theme", "silver_dim_astacita_program", "silver_fact_astacita_scurve_weekly",
                                                 "silver_fact_astacita_output", "silver_fact_astacita_issue", "silver_fact_astacita_priority_score",
                                                 "silver_dim_astacita_manpower"))
    tail = {"_batch_id": L.sq(batch_id), "_loaded_at": L.lit(now, "timestamp")}
    last = (f"(SELECT theme_code, max_by(date_key * 10 + week_no, date_key * 10 + week_no) AS k, "
            f"max_by(plan_cumulative_ratio, date_key * 10 + week_no) AS pl, max_by(actual_cumulative_ratio, date_key * 10 + week_no) AS ac, "
            f"max_by(deviation_cumulative_ratio, date_key * 10 + week_no) AS dv FROM {SC} WHERE actual_cumulative_ratio IS NOT NULL GROUP BY theme_code)")
    G: dict[str, dict[str, str]] = {}
    G["gold_astacita_program_summary"] = {
        "_from": f"{TH} t LEFT JOIN (SELECT theme_code, count(*) AS n, sum(budget_idr) AS b FROM {PR} GROUP BY 1) p ON p.theme_code = t.theme_code "
                 f"LEFT JOIN {last} s ON s.theme_code = t.theme_code "
                 f"LEFT JOIN (SELECT theme_code, count(*) AS n, count_if(status = 'Completed') AS c, avg(progress_ratio) AS a FROM {OU} GROUP BY 1) o "
                 f"ON o.theme_code = t.theme_code "
                 f"LEFT JOIN (SELECT theme_code, count(*) AS n FROM {IS} GROUP BY 1) i ON i.theme_code = t.theme_code "
                 f"LEFT JOIN {PS} ps ON ps.theme_code = t.theme_code "
                 f"LEFT JOIN (SELECT theme_code, count(DISTINCT person_name) AS n FROM {MP} GROUP BY 1) m ON m.theme_code = t.theme_code",
        "theme_code": "t.theme_code", "astacita_no": "t.astacita_no", "astacita_label": "t.astacita_label", "theme_name": "t.theme_name",
        "program_count": "coalesce(p.n, 0)", "total_budget_idr": "p.b", "last_scurve_date_key": "s.k / 10",
        "plan_cumulative_ratio": "s.pl", "actual_cumulative_ratio": "s.ac", "deviation_cumulative_ratio": "s.dv",
        "schedule_status": "CASE WHEN s.ac IS NULL THEN 'Belum ada realisasi' WHEN s.dv < 0 THEN 'Terlambat' ELSE 'Sesuai/Lebih cepat' END",
        "output_count": "coalesce(o.n, 0)", "output_completed": "coalesce(o.c, 0)", "output_progress_avg": "o.a",
        "issue_count": "coalesce(i.n, 0)", "aip_final_score": "ps.aip_final_score", "aip_rank": "ps.aip_rank",
        "manpower_count": "coalesce(m.n, 0)", **tail}
    G["gold_astacita_scurve_weekly"] = {
        "_from": f"{SC} s JOIN {TH} t ON t.theme_code = s.theme_code",
        "theme_code": "s.theme_code", "astacita_label": "t.astacita_label", "theme_name": "t.theme_name",
        "period_date": "date_parse(CAST(s.date_key AS varchar), '%Y%m%d')", "date_key": "s.date_key", "week_no": "s.week_no",
        "week_label": "CAST(s.period_year AS varchar) || '-' || lpad(CAST(s.period_month AS varchar), 2, '0') || ' W' || CAST(s.week_no AS varchar)",
        "plan_cumulative_ratio": "s.plan_cumulative_ratio", "actual_cumulative_ratio": "s.actual_cumulative_ratio",
        "deviation_cumulative_ratio": "s.deviation_cumulative_ratio", **tail}
    G["gold_astacita_output_status"] = {
        "_from": f"(SELECT theme_code, status, count(*) AS n, avg(progress_ratio) AS a FROM {OU} GROUP BY 1, 2) o "
                 f"LEFT JOIN {TH} t ON t.theme_code = o.theme_code",
        "theme_code": "o.theme_code", "astacita_label": "t.astacita_label", "theme_name": "t.theme_name", "status": "o.status",
        "output_count": "o.n", "progress_avg": "o.a", **tail}
    checks = [
        ("silver_fact_astacita_priority_score", "survey_label", "Konsistensi", "Nomor Asta Cita di survei (Hasil Kompilasi) berbeda dengan sheet Profile untuk tema yang sama",
         f"{PS} ps JOIN {TH} t ON t.theme_code = ps.theme_code WHERE ps.survey_label <> t.astacita_label"),
        ("silver_dim_astacita_program", "budget_idr", "Format", "Anggaran bukan angka (mis. '-')", f"{PR} WHERE budget_idr IS NULL AND budget_source IS NOT NULL"),
        ("silver_fact_astacita_output", "status", "Nilai baku", "Status output di luar Completed/In Progress/Not Started",
         f"{OU} WHERE status NOT IN ('Completed', 'In Progress', 'Not Started')"),
        ("silver_fact_astacita_output", "status_source", "Ejaan", "Status ditulis tidak baku (mis. 'On Progress' dengan spasi khusus)",
         f"{OU} WHERE status_source <> status"),
        ("silver_fact_astacita_scurve_weekly", "plan_monthly_ratio", "Wajib terisi", "Rencana bulanan kosong", f"{SC} WHERE plan_monthly_ratio IS NULL"),
    ] + [(t, "theme_code", "Referensi", "Tema tidak dikenali (tambahkan sinonim di astacita.THEMES)", f"{F(t)} WHERE theme_code IS NULL")
         for t in ("silver_dim_astacita_program", "silver_fact_astacita_scurve_weekly", "silver_fact_astacita_output", "silver_fact_astacita_issue",
                   "silver_fact_astacita_activity_monthly", "silver_fact_astacita_priority_score", "silver_dim_astacita_manpower")]
    G["gold_astacita_dq_finding"] = {
        "_from": "(" + " UNION ALL ".join(f"SELECT {L.sq(t)} AS t, {L.sq(c)} AS c, {L.sq(r)} AS r, {L.sq(f)} AS f, count(*) AS n FROM {w}"
                                          for t, c, r, f, w in checks) + ") d",
        "table_name": "d.t", "column_name": "d.c", "rule_name": "d.r", "finding": "d.f", "affected_rows": "d.n", **tail}
    return G


def available(live: set[str]) -> bool:
    return {f"{PREFIX}profile", f"{PREFIX}kurva_s", f"{PREFIX}output"} <= live


PII = {"nama": "Confidential", "nama_responden": "Confidential", "co_lead": "Restricted", "program_lead": "Restricted"}


def mark_bronze_pii(tq: L.Trino) -> None:
    """Kolom nama orang di semua Bronze DBASTACITA (manpower, responden survei, lead) → komentar Sensitivitas → tag katalog."""
    for t, c, cm in tq.q(f"SELECT table_name, column_name, comment FROM information_schema.columns WHERE table_schema = '{tq.schema}' "
                         f"AND table_name LIKE 'bronze_file_dbastacita%' AND column_name IN ({', '.join(L.sq(k) for k in PII)})"):
        if f"Sensitivitas: {PII[c]}" not in (cm or ""):
            tq.q(f'COMMENT ON COLUMN {tq.catalog}.{tq.schema}."{t}".{c} IS ' + L.sq(f"Nama orang (Bronze mentah) — Sensitivitas: {PII[c]}"))


def build(tq: L.Trino, schema: dict, batch_id: str, now: datetime) -> None:
    live = set(tq.tables())
    if not available(live):
        return
    L.log("Silver/Gold Asta Cita (berkas DBASTACITA, SQL di Trino)")
    mark_bronze_pii(tq)
    for name, m in silver(tq, batch_id, now).items():
        sdm.load_select(tq, schema, live, name, m)
    for name, m in gold(tq, batch_id, now).items():
        sdm.load_select(tq, schema, live, name, m)
