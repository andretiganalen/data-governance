"""Kerangka SDM (Sumber Daya Manusia) + korporasi: Bronze → Silver → Gold, seluruhnya SQL di Trino.

Bronze (apa adanya, lihat migrate_legacy_medallion.py):
  bronze_sdm_employee_information, bronze_sdm_employee_certification, bronze_corp_company_information,
  bronze_corp_company_investment, bronze_corp_company_tax  (+ lembar dashboard mentah bronze_sdm_dashboard_* / bronze_corp_*)
Silver: silver_dim_company_information, silver_dim_sdm_employee, silver_fact_sdm_certification,
        silver_fact_corp_investment_monthly, silver_fact_corp_tax_monthly
Gold:   gold_sdm_workforce_profile, gold_sdm_company_summary, gold_sdm_certification_summary, gold_sdm_dq_finding

Aturan: nilai sumber tidak diubah diam-diam — nilai baku di kolom baru (mis. gender) dan nilai asli disimpan
(gender_source, training_year_source); penyimpangan masuk dq_note dan gold_sdm_dq_finding.
Dipanggil lakehouse.py rebuild (bila Bronze SDM ada). Definisi kolom: schema/medallion_repository.sql.
"""
from __future__ import annotations

from datetime import datetime

import lakehouse as L

FILE_ID = "legacy-medallion-20261102"   # Bronze SDM/korporasi berasal dari prototipe lakekeeper.medallion
YR = "^((19|20)[0-9]{2})(\\s*[-–/]\\s*((19|20)[0-9]{2}))?$"   # 'YYYY' atau 'YYYY-YYYY' → grup 1 = awal, grup 4 = akhir


def _lineage(src_system: str, src_file: str, batch_id: str, now: datetime) -> dict[str, str]:
    return {"_file_id": L.sq(FILE_ID), "_batch_id": L.sq(batch_id), "_source_system": L.sq(src_system),
            "_source_file": src_file, "_loaded_at": L.lit(now, "timestamp")}


def norm(x: str) -> str:
    """Kunci nama perusahaan: huruf kecil, tanpa PT/Persero/Tbk/tanda baca ('PT Len Industri' = 'Len Industri (Persero), PT')."""
    return (f"trim(regexp_replace(regexp_replace(lower({x}), '\\(persero\\)|\\bpt\\b|\\btbk\\b|\\bpersero\\b', ' '), "
            f"'[^a-z0-9]+', ' '))")


def _company_lookup(tq: L.Trino) -> str:
    """Kunci nama (nama, nama terformat, akronim, tiap alias) → company_id. Bila kunci dipakai beberapa id,
    min() mendahulukan entitas COMP-* atas vendor VEND-*."""
    c = tq.fq("silver_dim_company_information")
    return (f"(SELECT k, min(company_id) AS company_id FROM ("
            f" SELECT {norm('company_name')} AS k, company_id FROM {c}"
            f" UNION ALL SELECT {norm('company_name_formatted')}, company_id FROM {c}"
            f" UNION ALL SELECT {norm('company_acronym')}, company_id FROM {c}"
            f" UNION ALL SELECT {norm('a')}, company_id FROM {c} CROSS JOIN UNNEST(split(coalesce(company_aliases, ''), ',')) AS u(a)"
            f") WHERE k IS NOT NULL AND k <> '' GROUP BY k)")


def _period(year: str, month: str) -> str:
    return f"CAST({year} AS integer) * 10000 + CAST({month} AS integer) * 100 + 1"


def silver_sql(tq: L.Trino, batch_id: str, now: datetime) -> dict[str, dict[str, str]]:
    B = tq.fq
    lk = _company_lookup(tq)
    corp = _lineage("CORP", "source_file", batch_id, now)
    sdm = _lineage("SDM", "source_file", batch_id, now)
    out: dict[str, dict[str, str]] = {}
    out["silver_dim_company_information"] = {"_from": B("bronze_corp_company_information"), **{c: c for c in (
        "company_id company_name company_name_formatted company_aliases company_acronym entity_classification domicile_status "
        "company_group company_level relation_to_main is_central_company company_address city province country postal_code "
        "phone_number email website tax_id_npwp industry_sector business_category vendor_category_finance vendor_category_scm "
        "contact_person contact_phone notes is_active").split()}, **corp}
    emp_cols = ("employee_id nik_npp full_name origin_name company_name company_scope directorate division unit job_title "
                "job_title_detail job_level job_stream sub_job_stream employment_status special_program_assignment age age_group "
                "generation religion education_level major institution years_of_service years_of_service_group physical_condition "
                "is_certified certification_summary project_management_qualification").split()
    g = "lower(regexp_replace(e.gender, '[^A-Za-z]', ''))"
    out["silver_dim_sdm_employee"] = {
        "_from": f"{B('bronze_sdm_employee_information')} e LEFT JOIN {lk} m ON m.k = " + norm("e.company_name"),
        **{c: f"e.{c}" for c in emp_cols},
        "company_id": "m.company_id",
        "gender": f"CASE {g} WHEN 'lakilaki' THEN 'Laki-laki' WHEN 'perempuan' THEN 'Perempuan' END",
        "gender_source": "e.gender", "birth_date": "CAST(NULL AS date)",
        "dq_note": ("NULLIF(concat_ws('; ', "
                    f"CASE WHEN e.gender IS NOT NULL AND {g} NOT IN ('lakilaki','perempuan') THEN 'gender sumber bukan jenis kelamin: ' || e.gender END, "
                    "CASE WHEN m.company_id IS NULL THEN 'perusahaan tidak cocok dengan silver_dim_company_information' END), '')"),
        **{k: (f"e.{v}" if v == "source_file" else v) for k, v in sdm.items()},
    }
    y = "c.training_year"
    out["silver_fact_sdm_certification"] = {
        "_from": f"{B('bronze_sdm_employee_certification')} c LEFT JOIN {lk} m ON m.k = " + norm("c.company_name"),
        **{x: f"c.{x}" for x in "certification_id employee_id company_name certification_name certification_category training_type validity_status".split()},
        "company_id": "m.company_id",
        "period_start_year": f"CASE WHEN regexp_like(trim({y}), '{YR}') THEN CAST(regexp_extract(trim({y}), '{YR}', 1) AS integer) END",
        "period_end_year": f"CASE WHEN regexp_like(trim({y}), '{YR}') THEN CAST(coalesce(regexp_extract(trim({y}), '{YR}', 4), regexp_extract(trim({y}), '{YR}', 1)) AS integer) END",
        "training_year_source": y,
        "dq_note": f"CASE WHEN {y} IS NOT NULL AND NOT regexp_like(trim({y}), '{YR}') THEN 'periode pelatihan bukan YYYY atau YYYY-YYYY: ' || {y} END",
        **{k: (f"c.{v}" if v == "source_file" else v) for k, v in sdm.items()},
    }
    common = {"fact_id": "fact_id", "company_id": "company_id", "company_name": "company_name", "company_group": "company_group",
              "company_level": "company_level", "period_year": "period_year", "period_month": "period_month",
              "date_key": _period("period_year", "period_month"), "notes": "keterangan"}
    out["silver_fact_corp_investment_monthly"] = {"_from": B("bronze_corp_company_investment"), **common,
        "category_code": "category_code", "category_name": "category_name", "item_name": "item_name",
        "annual_budget": "anggaran_tahunan", "monthly_budget": "anggaran_bulanan", "monthly_realization": "realisasi_bulanan",
        "ytd_budget": "anggaran_sd_bulan", "ytd_realization": "realisasi_sd_bulan", "ytd_realization_pct": "persen_realisasi_sd_anggaran",
        "remaining_annual_budget": "sisa_anggaran_tahunan", "mom_growth_nominal": "mom_realisasi_growth_nominal",
        "mom_growth_pct": "mom_realisasi_growth_percent", **corp}
    out["silver_fact_corp_tax_monthly"] = {"_from": B("bronze_corp_company_tax"), **common,
        "tax_jurisdiction": "tax_jurisdiction", "tax_group": "tax_group", "tax_item_code": "tax_item_code", "tax_item_name": "tax_item_name",
        "monthly_realization": "realisasi_bulanan", "ytd_realization": "realisasi_sd_bulan",
        "mom_growth_nominal": "mom_pajak_growth_nominal", "mom_growth_pct": "mom_pajak_growth_percent", **corp}
    return out


def gold_sql(tq: L.Trino, batch_id: str, now: datetime) -> dict[str, str]:
    # Gold prototipe hanya dari baris SDM (pegawai LenO punya Gold sendiri: gold_sdm_headcount_monthly, leno_sdm.py)
    E = f"(SELECT * FROM {tq.fq('silver_dim_sdm_employee')} WHERE _source_system = 'SDM')"
    C, CO = tq.fq("silver_fact_sdm_certification"), tq.fq("silver_dim_company_information")
    lin = f"{L.sq(batch_id)} AS _batch_id, {L.lit(now, 'timestamp')} AS _loaded_at"
    dims = "company_id, company_name, directorate, division, employment_status, gender, age_group, generation, education_level, years_of_service_group, job_level"
    return {
        "gold_sdm_workforce_profile":
            f"SELECT {dims}, count(*) AS headcount, count_if(is_certified) AS certified_count, avg(age) AS avg_age, "
            f"avg(years_of_service) AS avg_years_of_service, {lin} FROM {E} GROUP BY {dims}",
        "gold_sdm_company_summary":
            f"SELECT e.company_id, e.company_name, max(co.company_group) AS company_group, count(*) AS headcount, "
            f"count_if(e.employment_status = 'PKWTT') AS pkwtt_count, count_if(e.employment_status = 'PKWT') AS pkwt_count, "
            f"count_if(e.employment_status = 'Maganghub') AS intern_count, count_if(e.gender = 'Perempuan') AS female_count, "
            f"CAST(count_if(e.gender = 'Perempuan') AS double) / NULLIF(count_if(e.gender IS NOT NULL), 0) AS female_ratio, "
            f"avg(e.age) AS avg_age, count_if(e.is_certified) AS certified_count, "
            f"CAST(count_if(e.is_certified) AS double) / count(*) AS certified_ratio, "
            f"max(cc.n) AS certification_count, {lin} "
            f"FROM {E} e LEFT JOIN {CO} co ON co.company_id = e.company_id "
            f"LEFT JOIN (SELECT company_name, count(*) AS n FROM {C} GROUP BY company_name) cc ON cc.company_name = e.company_name "
            f"GROUP BY e.company_id, e.company_name",
        "gold_sdm_certification_summary":
            f"SELECT company_name, certification_category, training_type, validity_status, period_start_year, period_end_year, "
            f"count(*) AS certification_count, count(DISTINCT employee_id) AS employee_count, {lin} FROM {C} "
            f"GROUP BY company_name, certification_category, training_type, validity_status, period_start_year, period_end_year",
        "gold_sdm_dq_finding": " UNION ALL ".join(
            f"SELECT {L.sq(t)} AS table_name, {L.sq(c)} AS column_name, {L.sq(r)} AS rule_name, {L.sq(f)} AS finding, "
            f"count(*) AS affected_rows, {lin} FROM {tq.fq(t)} WHERE _source_system = 'SDM' AND ({w})" for t, c, r, f, w in [
                ("silver_dim_sdm_employee", "gender", "Nilai baku", "Jenis kelamin sumber bukan Laki-laki/Perempuan (mis. 'Mahasiswa')", "gender IS NULL AND gender_source IS NOT NULL"),
                ("silver_dim_sdm_employee", "company_id", "Referensi", "Perusahaan pegawai tidak ada di silver_dim_company_information", "company_id IS NULL"),
                ("silver_dim_sdm_employee", "employee_id", "Unik", "employee_id ganda", "employee_id IN (SELECT employee_id FROM " + E + " GROUP BY 1 HAVING count(*) > 1)"),
                ("silver_dim_sdm_employee", "nik_npp", "Wajib terisi", "NIK/NPP kosong", "nik_npp IS NULL OR trim(nik_npp) = ''"),
                ("silver_fact_sdm_certification", "employee_id", "Referensi", "Sertifikasi tanpa pegawai di silver_dim_sdm_employee",
                 "employee_id NOT IN (SELECT employee_id FROM " + E + " WHERE employee_id IS NOT NULL)"),
                ("silver_fact_sdm_certification", "period_start_year", "Format", "Periode pelatihan bukan YYYY atau YYYY-YYYY", "period_start_year IS NULL AND training_year_source IS NOT NULL"),
            ]),
    }


# Kolom pribadi di Bronze mentah: diberi komentar "Sensitivitas: …" agar katalog memberi tag yang sama dengan Silver.
BRONZE_PII = {
    "bronze_sdm_employee_information": {"nik_npp": "Confidential", "full_name": "Confidential", "origin_name": "Confidential",
                                        "gender": "Restricted", "age": "Restricted", "religion": "Strictly Confidential",
                                        "physical_condition": "Strictly Confidential"},
    "bronze_sdm_employee_certification": {"nik_npp": "Confidential", "employee_name": "Confidential", "origin_name": "Confidential"},
    "bronze_corp_company_information": {"tax_id_npwp": "Restricted", "contact_person": "Confidential", "contact_phone": "Confidential"},
}


def mark_bronze_pii(tq: L.Trino, live: set[str]) -> None:
    for t, cols in BRONZE_PII.items():
        if t not in live:
            continue
        have = {c: (cm or "") for c, cm in tq.q(f"SELECT column_name, comment FROM information_schema.columns "
                                               f"WHERE table_schema = '{tq.schema}' AND table_name = '{t}'")}
        for c, lvl in cols.items():
            if c in have and f"Sensitivitas: {lvl}" not in have[c]:
                tq.q(f"COMMENT ON COLUMN {tq.fq(t)}.{c} IS " + L.sq(f"Data pribadi (Bronze mentah) — Sensitivitas: {lvl}"))


def load_select(tq: L.Trino, schema: dict, live: set[str], name: str, m: dict[str, str], delete_where: str | None = None) -> int:
    """Isi tabel `name` (definisi di berkas skema) dengan INSERT … SELECT di Trino.
    m = {kolom: ekspresi SQL, "_from": klausa FROM [+ JOIN/WHERE]}; setiap kolom skema wajib ada di m.
    delete_where membatasi baris yang diganti (mis. hanya satu _source_system); None = ganti semua."""
    spec = schema[name]
    st = L.ensure_table(tq, name, spec, live, managed=True)
    cols = [c for c, _, _ in spec["cols"]]
    missing = [c for c in cols if c not in m]
    if missing:
        raise SystemExit(f"{name}: ekspresi kolom belum ada {missing}")
    tq.q(f"DELETE FROM {tq.fq(name)}" + (f" WHERE {delete_where}" if delete_where else ""))
    sel = ", ".join(f"CAST({m[c]} AS {t}) AS {c}" for c, t, _ in spec["cols"])
    tq.q(f"INSERT INTO {tq.fq(name)} ({', '.join(cols)}) SELECT {sel} FROM {m['_from']}")
    n = tq.q(f"SELECT count(*) FROM {tq.fq(name)}" + (f" WHERE {delete_where}" if delete_where else ""))[0][0]
    L.log(f"  {name:45s} {n:6d} baris" + ("" if st == "sama" else f"  [{st}]"))
    return n


def available(tq: L.Trino, live: set[str]) -> bool:
    return {"bronze_sdm_employee_information", "bronze_corp_company_information"} <= live


def build(tq: L.Trino, schema: dict, batch_id: str, now: datetime) -> None:
    live = set(tq.tables())
    if not available(tq, live):
        return
    L.log("Silver/Gold SDM + korporasi (Trino SQL)")
    mark_bronze_pii(tq, live)
    for name, m in silver_sql(tq, batch_id, now).items():   # tiap sumber (SDM/CORP) hanya mengganti barisnya sendiri
        src = "CORP" if "corp" in name or "company" in name else "SDM"
        load_select(tq, schema, live, name, m, delete_where=f"_source_system = '{src}'")
    for name, sql in gold_sql(tq, batch_id, now).items():
        spec = schema[name]
        st = L.ensure_table(tq, name, spec, live, managed=True)
        cols = [c for c, _, _ in spec["cols"]]
        tq.q(f"DELETE FROM {tq.fq(name)}")
        tq.q(f"INSERT INTO {tq.fq(name)} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM ({sql})")
        n = tq.q(f"SELECT count(*) FROM {tq.fq(name)}")[0][0]
        L.log(f"  {name:45s} {n:6d} baris" + ("" if st == "sama" else f"  [{st}]"))
