"""SDM dari Aplikasi LenO (katalog Trino lenodb.silver) → Bronze → Silver → Gold, seluruhnya SQL di Trino.

BRONZE  snapshot tiap rebuild, HANYA kolom yang diperlukan (minimisasi data pribadi; KTP, paspor, NPWP, PIN, dokumen,
        agama, dll. tidak disalin): bronze_leno_ps_karyawan, bronze_leno_ps_statusbarukaryawan, bronze_leno_ps_ukkaryawan.
SILVER  silver_dim_sdm_employee (baris _source_system = LENO_SDM), silver_fact_sdm_employment_status (riwayat status,
        rentang berlaku), silver_fact_sdm_unit_assignment (riwayat unit kerja).
GOLD    gold_sdm_headcount_monthly — posisi AKHIR BULAN, Jan 2024 s.d. bulan berjalan: perusahaan × unit × gender ×
        kontrak/non kontrak × status × kelompok umur → jumlah orang, umur min/maks/rata-rata. Tanpa data pribadi.

Aturan: rekaman aktif (recordstatus A) yang tidak sedang menunggu persetujuan. Status berlaku [TMT, tanggal berakhir],
dibatasi TMT berhenti karyawan. Kelompok status: reference/sdm_status_kepegawaian.csv (dapat dikoreksi Unit HC).
Semua pegawai di tenant Len Industri (database lendb) → company_id COMP-LEN-001.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import lakehouse as L
import sdm

SRC = "LENO_SDM"
CAT = "lenodb.silver"
COMPANY = ("COMP-LEN-001", "PT Len Industri (Persero)")
START = "2024-01-01"                     # awal deret bulanan Gold
BRONZE = {  # tabel sumber → kolom yang disalin (minimisasi)
    "ps_karyawan": "id, nik, nama, kelamin, tanggallahir, aktif, jeniskaryawan, statuskaryawan, tmtkerja, tmtberhenti, "
                   "kategoriberhenti, jobstream, recordstatus, lastmodifieddate, __db",
    "ps_statusbarukaryawan": "id, karyawanid, status, jeniskaryawan, subjeniskaryawan, organisasi, tmt, tglberakhir, iscurrent, "
                             "isprogressapproval, pemutusanhubungankerja, recordstatus, lastmodifieddate",
    "ps_ukkaryawan": "id, karyawanid, unitkerjaid, datefrom, dateto, iscurrent, isprogressapproval, recordstatus, lastmodifieddate",
}
PII = {"bronze_leno_ps_karyawan": {"nik": "Confidential", "nama": "Confidential", "tanggallahir": "Restricted", "kelamin": "Restricted"}}
REF = Path(__file__).resolve().parent / "reference" / "sdm_status_kepegawaian.csv"


def age_group(a: str) -> str:
    return (f"CASE WHEN {a} IS NULL THEN NULL WHEN {a} < 25 THEN '<25' WHEN {a} < 35 THEN '25-34' WHEN {a} < 45 THEN '35-44' "
            f"WHEN {a} < 55 THEN '45-54' ELSE '55+' END")


def status_ref() -> str:
    rows = list(csv.DictReader(REF.open(encoding="utf-8")))
    vals = ", ".join(f"({L.sq(r['status_name'])}, {L.sq(r['employment_class'])}, {L.sq(r['contract_flag'])}, "
                     f"{r['is_employee']}, {r['is_active']})" for r in rows)
    return f"(SELECT * FROM (VALUES {vals}) AS v(status_name, employment_class, contract_flag, is_employee, is_active))"


def bronze(tq: L.Trino) -> None:
    # absensi (±4 juta baris): hanya ringkasan tanggal hadir terakhir per pegawai (≤ hari ini) sebagai perkiraan tanggal berhenti
    b = "bronze_leno_ab_absensikaryawan_last"
    tq.q(f"CREATE OR REPLACE TABLE {tq.fq(b)} WITH (format = 'PARQUET', format_version = 2) AS "
         f"SELECT karyawanid, max(CAST(tanggal AS date)) AS last_attendance_date, count(*) AS attendance_rows "
         f"FROM {CAT}.ab_absensikaryawan WHERE CAST(tanggal AS date) <= current_date GROUP BY karyawanid")
    tq.q(f"COMMENT ON TABLE {tq.fq(b)} IS " + L.sq(
        f"Bronze ringkas: tanggal absensi terakhir per pegawai dari {CAT}.ab_absensikaryawan (tanggal > hari ini diabaikan)."))
    L.log(f"  {b:45s} {tq.q(f'SELECT count(*) FROM {tq.fq(b)}')[0][0]:6d} baris")
    for t, cols in BRONZE.items():
        b = f"bronze_leno_{t}"
        tq.q(f"CREATE OR REPLACE TABLE {tq.fq(b)} WITH (format = 'PARQUET', format_version = 2) AS SELECT {cols} FROM {CAT}.{t}")
        tq.q(f"COMMENT ON TABLE {tq.fq(b)} IS " + L.sq(
            f"Bronze: snapshot {CAT}.{t} (Aplikasi LenO), hanya kolom yang diperlukan ETL SDM; diganti tiap rebuild."))
        for c, lvl in PII.get(b, {}).items():
            tq.q(f"COMMENT ON COLUMN {tq.fq(b)}.{c} IS " + L.sq(f"Data pribadi (Bronze) — Sensitivitas: {lvl}"))
        L.log(f"  {b:45s} {tq.q(f'SELECT count(*) FROM {tq.fq(b)}')[0][0]:6d} baris")


def silver(tq: L.Trino, batch_id: str, now: datetime) -> dict[str, dict[str, str]]:
    K, ST, UK = (tq.fq(f"bronze_leno_{t}") for t in ("ps_karyawan", "ps_statusbarukaryawan", "ps_ukkaryawan"))
    HU = tq.fq("bronze_leno_hr_unitkerja")   # dari leno_erm.py (snapshot hr_unitkerja)
    ok = "recordstatus = 'A' AND coalesce(isprogressapproval, 0) = 0"
    end = "DATE '9999-12-31'"
    lin = lambda t: {"_file_id": L.sq(f"{CAT}@{now:%Y-%m-%d %H:%M}Z"), "_batch_id": L.sq(batch_id),  # noqa: E731
                     "_source_system": L.sq(SRC), "_source_file": L.sq(f"{CAT}.{t}"), "_loaded_at": L.lit(now, "timestamp")}
    stop = f"(CASE WHEN k.tmtberhenti IS NULL OR year(k.tmtberhenti) >= 9999 THEN {end} ELSE CAST(k.tmtberhenti AS date) END)"
    ref = status_ref()
    cur_st = (f"(SELECT karyawanid, max_by(status, tmt) AS status FROM {ST} WHERE {ok} AND iscurrent = 1 GROUP BY karyawanid)")
    cur_uk = (f"(SELECT u.karyawanid, max_by(h.kodeuk, u.datefrom) AS org_id, max_by(h.namauk, u.datefrom) AS unit "
              f"FROM {UK} u JOIN {HU} h ON h.id = u.unitkerjaid WHERE u.{ok} AND u.iscurrent = 1 GROUP BY u.karyawanid)")
    first_tmt = f"(SELECT karyawanid, min(tmt) AS tmt FROM {ST} WHERE {ok} GROUP BY karyawanid)"
    g = "lower(regexp_replace(k.kelamin, '[^A-Za-z]', ''))"
    birth = "CAST(k.tanggallahir AS date)"
    age_now = f"date_diff('year', {birth}, current_date)"
    svc_from = "coalesce(CASE WHEN year(k.tmtkerja) < 9999 THEN CAST(k.tmtkerja AS date) END, CAST(f.tmt AS date))"
    S: dict[str, dict[str, str]] = {}
    nulls = ("origin_name company_scope directorate division job_title job_title_detail job_level sub_job_stream "
             "special_program_assignment religion education_level major institution physical_condition certification_summary "
             "project_management_qualification").split()
    S["silver_dim_sdm_employee"] = {
        "_from": f"{K} k LEFT JOIN {cur_st} cs ON cs.karyawanid = k.id LEFT JOIN {cur_uk} cu ON cu.karyawanid = k.id "
                 f"LEFT JOIN {first_tmt} f ON f.karyawanid = k.id WHERE k.recordstatus = 'A'",
        "employee_id": "'LENO-K-' || CAST(k.id AS varchar)", "nik_npp": "k.nik", "full_name": "k.nama",
        **{c: "NULL" for c in nulls}, "company_id": L.sq(COMPANY[0]), "company_name": L.sq(COMPANY[1]),
        "unit": "cu.unit", "job_stream": "k.jobstream", "employment_status": "cs.status",
        "gender": f"CASE {g} WHEN 'lakilaki' THEN 'Laki-laki' WHEN 'perempuan' THEN 'Perempuan' END", "gender_source": "k.kelamin",
        "age": age_now, "birth_date": birth, "age_group": age_group(age_now),
        "generation": (f"CASE WHEN year({birth}) >= 1997 THEN 'Gen Z' WHEN year({birth}) >= 1981 THEN 'Milenial' "
                       f"WHEN year({birth}) >= 1965 THEN 'Gen X' WHEN year({birth}) IS NOT NULL THEN 'Baby Boomer' END"),
        "years_of_service": f"CAST(date_diff('day', {svc_from}, current_date) AS double) / 365.25",
        "years_of_service_group": (f"CASE WHEN {svc_from} IS NULL THEN NULL WHEN date_diff('year', {svc_from}, current_date) < 5 THEN '<5' "
                                   f"WHEN date_diff('year', {svc_from}, current_date) < 10 THEN '5-9' "
                                   f"WHEN date_diff('year', {svc_from}, current_date) < 20 THEN '10-19' ELSE '20+' END"),
        "is_certified": "NULL",
        "dq_note": ("NULLIF(concat_ws('; ', "
                    f"CASE WHEN {g} NOT IN ('lakilaki', 'perempuan') OR k.kelamin IS NULL THEN 'jenis kelamin tidak baku/kosong' END, "
                    "CASE WHEN k.tanggallahir IS NULL THEN 'tanggal lahir kosong' END, "
                    "CASE WHEN cs.status IS NULL THEN 'tidak ada status kepegawaian berlaku' END), '')"),
        **lin("ps_karyawan")}
    AB = tq.fq("bronze_leno_ab_absensikaryawan_last")
    to_ = f"coalesce(CAST(s.tglberakhir AS date), {end})"
    inactive = (f"(CASE WHEN k.aktif = 0 THEN coalesce(ab.last_attendance_date, CAST(k.lastmodifieddate AS date), CAST(s.tmt AS date)) "
                f"ELSE {end} END)")
    S["silver_fact_sdm_employment_status"] = {
        "_from": f"{ST} s JOIN {K} k ON k.id = s.karyawanid AND k.recordstatus = 'A' LEFT JOIN {ref} r ON r.status_name = s.status "
                 f"LEFT JOIN {AB} ab ON ab.karyawanid = s.karyawanid WHERE s.{ok}",
        "status_id": "'LENO-S-' || CAST(s.id AS varchar)", "employee_id": "'LENO-K-' || CAST(s.karyawanid AS varchar)",
        "company_id": L.sq(COMPANY[0]), "status_name": "s.status", "employment_class": "coalesce(r.employment_class, 'TIDAK_DIKENAL')",
        "contract_flag": "r.contract_flag", "is_employee": "r.is_employee", "is_active": "coalesce(r.is_active, TRUE)",
        "job_category": "s.jeniskaryawan", "valid_from": "CAST(s.tmt AS date)",
        "valid_to": f"least({to_}, {stop}, {inactive})",
        "end_date_basis": (f"CASE WHEN least({to_}, {stop}, {inactive}) = {end} THEN 'terbuka' "
                           f"WHEN least({to_}, {stop}, {inactive}) = {to_} THEN 'tanggal berakhir' "
                           f"WHEN least({to_}, {stop}, {inactive}) = {stop} THEN 'TMT berhenti' "
                           f"WHEN ab.last_attendance_date IS NOT NULL THEN 'absensi terakhir (perkiraan)' "
                           f"ELSE 'perubahan data terakhir (perkiraan)' END"),
        "is_current": "s.iscurrent = 1",
        **lin("ps_statusbarukaryawan")}
    S["silver_fact_sdm_unit_assignment"] = {
        "_from": f"{UK} u LEFT JOIN {HU} h ON h.id = u.unitkerjaid WHERE u.{ok}",
        "assignment_id": "'LENO-U-' || CAST(u.id AS varchar)", "employee_id": "'LENO-K-' || CAST(u.karyawanid AS varchar)",
        "org_id": "h.kodeuk", "unit_name": "h.namauk", "valid_from": "CAST(u.datefrom AS date)",
        "valid_to": f"CASE WHEN u.dateto IS NULL OR year(u.dateto) >= 9999 THEN {end} ELSE CAST(u.dateto AS date) END",
        "is_current": "u.iscurrent = 1", **lin("ps_ukkaryawan")}
    return S


def gold(tq: L.Trino, batch_id: str, now: datetime) -> dict[str, dict[str, str]]:
    E, ST, UA = (tq.fq(t) for t in ("silver_dim_sdm_employee", "silver_fact_sdm_employment_status", "silver_fact_sdm_unit_assignment"))
    src = f"_source_system = '{SRC}'"
    months = (f"(SELECT d AS ms, last_day_of_month(d) AS me FROM "
              f"UNNEST(sequence(DATE '{START}', CAST(date_trunc('month', current_date) AS date), INTERVAL '1' MONTH)) AS t(d))")
    # posisi akhir bulan: status yang berlaku pada hari terakhir bulan (TMT terbaru bila tumpang tindih)
    pos = (f"(SELECT * FROM (SELECT s.*, m.ms, m.me, row_number() OVER (PARTITION BY s.employee_id, m.ms "
           f"ORDER BY s.valid_from DESC, s.status_id DESC) AS rn FROM {ST} s JOIN {months} m "
           f"ON s.valid_from <= m.me AND s.valid_to >= m.me WHERE s.{src}) WHERE rn = 1)")
    unit = (f"(SELECT * FROM (SELECT u.employee_id, u.org_id, u.unit_name, m.ms, row_number() OVER (PARTITION BY u.employee_id, m.ms "
            f"ORDER BY u.valid_from DESC, u.assignment_id DESC) AS rn FROM {UA} u JOIN {months} m "
            f"ON u.valid_from <= m.me AND u.valid_to >= m.me WHERE u.{src}) WHERE rn = 1)")
    x = (f"(SELECT p.ms, p.me, p.employment_class, p.contract_flag, p.status_name, p.is_employee, p.is_active, e.gender, "
         f"date_diff('year', e.birth_date, p.me) AS age, un.org_id, un.unit_name FROM {pos} p "
         f"JOIN {E} e ON e.employee_id = p.employee_id AND e.{src} "
         f"LEFT JOIN {unit} un ON un.employee_id = p.employee_id AND un.ms = p.ms)")
    grp = "ms, org_id, unit_name, gender, employment_class, contract_flag, status_name, is_employee, is_active, " + age_group("age")
    return {"gold_sdm_headcount_monthly": {
        "_from": f"(SELECT ms, org_id, unit_name, gender, employment_class, contract_flag, status_name, is_employee, is_active, "
                 f"{age_group('age')} AS ag, count(*) AS n, min(age) AS amin, max(age) AS amax, avg(age) AS aavg FROM {x} GROUP BY {grp}) g",
        "period_year": "year(g.ms)", "period_month": "month(g.ms)", "period_date": "g.ms",
        "date_key": "year(g.ms) * 10000 + month(g.ms) * 100 + 1", "company_id": L.sq(COMPANY[0]), "company_name": L.sq(COMPANY[1]),
        "org_id": "g.org_id", "unit_name": "g.unit_name", "gender": "g.gender", "employment_class": "g.employment_class",
        "contract_flag": "g.contract_flag", "employment_status": "g.status_name", "is_employee": "g.is_employee",
        "is_active": "g.is_active", "age_group": "g.ag", "headcount": "g.n", "age_min": "g.amin", "age_max": "g.amax",
        "age_avg": "g.aavg", "_source_system": L.sq(SRC), "_batch_id": L.sq(batch_id), "_loaded_at": L.lit(now, "timestamp")}}


def available(tq: L.Trino) -> bool:
    try:
        tq.q(f"SELECT 1 FROM {CAT}.ps_karyawan LIMIT 1", attempts=2)
        return "bronze_leno_hr_unitkerja" in set(tq.tables())
    except Exception as e:  # noqa: BLE001
        L.log(f"  ! {CAT} tidak terjangkau ({str(e)[:100]}) — SDM LenO dilewati")
        return False


def build(tq: L.Trino, schema: dict, batch_id: str, now: datetime) -> None:
    if not available(tq):
        return
    L.log(f"Bronze/Silver/Gold SDM dari {CAT} (Aplikasi LenO)")
    bronze(tq)
    live = set(tq.tables())
    for name, m in silver(tq, batch_id, now).items():
        sdm.load_select(tq, schema, live, name, m, delete_where=f"_source_system = '{SRC}'")
    for name, m in gold(tq, batch_id, now).items():
        sdm.load_select(tq, schema, live, name, m, delete_where=f"_source_system = '{SRC}'")
