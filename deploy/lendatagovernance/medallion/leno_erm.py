"""Aplikasi ERM LenO (replika CDC di Trino: lenodb.silver) → Bronze → Silver/Gold ERM, seluruhnya SQL di Trino.

BRONZE  snapshot penuh tiap rebuild: lenodb.silver.erm_* + hr_unitkerja → medallion_repository.bronze_leno_*
        (apa adanya; satu sistem rekam: medallion_repository).
SILVER  baris _source_system = 'LENO_ERM' di tabel silver_dim_erm_* / silver_fact_erm_* (berdampingan dengan baris
        EGRC; hanya baris LENO_ERM yang diganti). ID diberi awalan LENO-<jenis>- agar tidak bertabrakan.
GOLD    baris _source_system = 'LENO_ERM' di gold_erm_risk_register, gold_erm_risk_assessment_monthly,
        gold_erm_risk_heatmap_monthly, gold_erm_mitigation_progress_monthly.

Aturan: hanya rekaman aktif (recordstatus = 'A'). Perusahaan: semua data ERM LenO dari tenant Len Industri
(perusahaanid 2, database lendb) → company_id COMP-LEN-001. Unit kerja: hr_unitkerja.kodeuk = ORG_ID workbook.
"""
from __future__ import annotations

from datetime import datetime

import lakehouse as L
import sdm

SRC = "LENO_ERM"
CATALOG_SRC = "lenodb.silver"
TABLES = ["erm_analisaswot", "erm_assessmentefektivitas", "erm_assessmentkecukupan", "erm_dasarsasaran", "erm_efektivitas",
          "erm_existingcontrol", "erm_heatmap", "erm_kecukupan", "erm_kriteriadampakkualitatif", "erm_kriteriadampakkuantitatif",
          "erm_kriteriakemungkinan", "erm_masterrisk", "erm_monitoring", "erm_pelaporan", "erm_penerimaanrisiko",
          "erm_penyebabrisiko", "erm_perencanaan", "erm_realisasimitigasi", "erm_rencanamitigasi", "erm_riskevaluation",
          "erm_riskinherent", "erm_riskregister", "erm_riskresidual", "erm_sasaran", "hr_unitkerja"]
COMPANY = ("COMP-LEN-001", "LEN")
LEVEL = {"Low": (1, "#1E7B34"), "Low to Moderate": (2, "#8BC34A"), "Moderate": (3, "#F2C200"),
         "Moderate to High": (4, "#F28C00"), "High": (5, "#DA0000")}
WHERE_SRC = f"_source_system = '{SRC}'"


def level(x: str) -> str:
    """Ejaan baku tingkat risiko (LenO menulis mis. 'Moderate To High'); hanya kapitalisasi yang dibakukan."""
    return f"CASE lower(trim({x})) " + " ".join(f"WHEN {L.sq(k.lower())} THEN {L.sq(k)}" for k in LEVEL) + f" ELSE {x} END"


def bronze(tq: L.Trino) -> dict[str, int]:
    """Snapshot lenodb.silver → bronze_leno_* (CREATE OR REPLACE, apa adanya)."""
    out = {}
    for t in TABLES:
        b = f"bronze_leno_{t}"
        tq.q(f"CREATE OR REPLACE TABLE {tq.fq(b)} WITH (format = 'PARQUET', format_version = 2) AS "
             f"SELECT * FROM {CATALOG_SRC}.{t}")
        tq.q(f"COMMENT ON TABLE {tq.fq(b)} IS " + L.sq(
            f"Bronze: snapshot apa adanya dari {CATALOG_SRC}.{t} (replika CDC Aplikasi ERM LenO), diganti tiap rebuild."))
        out[b] = tq.q(f"SELECT count(*) FROM {tq.fq(b)}")[0][0]
    return out


def silver(tq: L.Trino, batch_id: str, now: datetime) -> dict[str, dict[str, str]]:
    B = lambda t: tq.fq(f"bronze_leno_{t}")  # noqa: E731
    A = "recordstatus = 'A'"
    comp = L.sq(COMPANY[0])
    lin = lambda src: {"_file_id": L.sq(f"{CATALOG_SRC}@{now:%Y-%m-%d %H:%M}Z"), "_batch_id": L.sq(batch_id),  # noqa: E731
                       "_source_system": L.sq(SRC), "_source_file": L.sq(f"{CATALOG_SRC}.{src}"), "_loaded_at": L.lit(now, "timestamp")}
    scd = lambda a: {"valid_from": f"CAST({a}.createddate AS date)", "valid_to": "DATE '9999-12-31'", "is_current": "TRUE"}  # noqa: E731
    # konteks risiko: risk register aktif + perencanaan (tahun, unit kerja) + unit & induknya + master risk + sasaran
    risk_ctx = (f"(SELECT rr.*, year(p.tahun) AS fy, uk.kodeuk AS org_id, par.kodeuk AS divisi_id, mr.maincategory, mr.subcategory, "
                f"s.keterangansasaran FROM {B('erm_riskregister')} rr "
                f"LEFT JOIN {B('erm_perencanaan')} p ON p.id = rr.perencanaanrisikoid "
                f"LEFT JOIN {B('hr_unitkerja')} uk ON uk.id = p.unitkerjaid "
                f"LEFT JOIN {B('hr_unitkerja')} par ON par.id = uk.parentid "
                f"LEFT JOIN {B('erm_masterrisk')} mr ON mr.id = rr.masterriskid "
                f"LEFT JOIN {B('erm_sasaran')} s ON s.id = rr.sasaranid "
                f"WHERE rr.{A})")
    cause_ctx = (f"(SELECT pr.*, r.fy, r.divisi_id FROM {B('erm_penyebabrisiko')} pr "
                 f"JOIN {risk_ctx} r ON r.id = pr.riskregisterid WHERE pr.{A})")
    color = "CASE lower(h.kategoritingkatrisiko) " + " ".join(f"WHEN {L.sq(k.lower())} THEN {L.sq(v[1])}" for k, v in LEVEL.items()) + " END"
    S: dict[str, dict[str, str]] = {}
    S["silver_dim_erm_risk_taxonomy"] = {"_from": f"{B('erm_masterrisk')} m WHERE m.{A}",
        "risk_taxonomy_id": "'LENO-MR-' || CAST(m.id AS varchar)", "main_category": "m.maincategory", "sub_category": "m.subcategory",
        "definisi_kategori": "m.definisi", **scd("m"), **lin("erm_masterrisk")}
    S["silver_dim_erm_risk_matrix"] = {"_from": f"{B('erm_heatmap')} h WHERE h.{A}",
        "risk_matrix_id": "'LENO-HM-' || CAST(h.id AS varchar)", "kategori_operasional_proyek": "h.kategori",
        "skor_dampak": "h.skordampak", "skor_kemungkinan": "h.skorkemungkinan", "tingkat_risiko": "h.tingkatrisiko",
        "kategori_tingkat_risiko": level("h.kategoritingkatrisiko"), "kategori_tingkat_risiko_color_hex": color, **scd("h"), **lin("erm_heatmap")}
    S["silver_dim_erm_objective_basis"] = {"_from": f"{B('erm_dasarsasaran')} d WHERE d.{A}",
        "objective_basis_id": "'LENO-DS-' || CAST(d.id AS varchar)", "nama_sasaran": "d.namasasaran", **scd("d"), **lin("erm_dasarsasaran")}
    S["silver_dim_erm_objective"] = {
        "_from": f"{B('erm_sasaran')} s LEFT JOIN {B('erm_dasarsasaran')} d ON d.id = s.dasarsasaranid "
                 f"LEFT JOIN {B('erm_perencanaan')} p ON p.id = s.perencanaanrisikoid WHERE s.{A}",
        "objective_id": "'LENO-SS-' || CAST(s.id AS varchar)", "company_id": comp, "fiscal_year": "year(p.tahun)",
        "nama_sasaran": "d.namasasaran", "keterangan_sasaran": "s.keterangansasaran", "proses_bisnis": "s.prosesbisnis",
        "input_proses": "s.inputproses", "output_proses": "s.outputproses", "stakeholders_terkait": "s.stakeholdersterkait",
        **scd("s"), **lin("erm_sasaran")}
    for name, t, pre, col in [("silver_dim_erm_control_effectiveness", "erm_efektivitas", "EF", "efektivitas"),
                              ("silver_dim_erm_control_adequacy", "erm_kecukupan", "KC", "kecukupan")]:
        key = "control_effectiveness_id" if col == "efektivitas" else "control_adequacy_id"
        S[name] = {"_from": f"{B(t)} x WHERE x.{A}", key: f"'LENO-{pre}-' || CAST(x.id AS varchar)",
                   f"parameter_{col}": "x.parameter", f"urutan_{col}": "row_number() OVER (ORDER BY x.id)", **scd("x"), **lin(t)}
    S["silver_dim_erm_impact_criteria_quantitative"] = {"_from": f"{B('erm_kriteriadampakkuantitatif')} k WHERE k.{A}",
        "impact_criteria_quantitative_id": "'LENO-KQN-' || CAST(k.id AS varchar)", "skor_dampak": "k.skala",
        "kriteria_dampak_kuantitatif": "k.kriteriadampak", "min_dampak": "k.mindampak", "max_dampak": "k.maxdampak",
        "deskripsi_dampak": "k.deskripsidampak", "currency_code": "'IDR'", **scd("k"), **lin("erm_kriteriadampakkuantitatif")}
    S["silver_dim_erm_impact_criteria_qualitative"] = {"_from": f"{B('erm_kriteriadampakkualitatif')} k WHERE k.{A}",
        "impact_criteria_qualitative_id": "'LENO-KQL-' || CAST(k.id AS varchar)", "skor_dampak": "k.skala",
        "kategori_operasional_proyek": "k.kategori", "kriteria_dampak_kualitatif": "k.kriteriadampak", "tipe_risiko": "k.tiperisiko",
        "parameter_dampak_kualitatif": "k.parameter", **scd("k"), **lin("erm_kriteriadampakkualitatif")}
    S["silver_dim_erm_likelihood_criteria"] = {"_from": f"{B('erm_kriteriakemungkinan')} k WHERE k.{A}",
        "likelihood_criteria_id": "'LENO-KK-' || CAST(k.id AS varchar)", "kategori_operasional_proyek": "k.kategori",
        "parameter_kemungkinan": "k.parameter", "kriteria_kemungkinan": "k.kriteria", "kriteria_dampak_kemungkinan": "k.kriteriadampak",
        "skor_kemungkinan": "k.skala", **scd("k"), **lin("erm_kriteriakemungkinan")}
    S["silver_dim_erm_risk"] = {"_from": f"{risk_ctx} r",
        "risk_id": "'LENO-RR-' || CAST(r.id AS varchar)", "company_id": comp, "divisi_id": "r.divisi_id", "org_id": "r.org_id",
        "objective_id": "'LENO-SS-' || CAST(r.sasaranid AS varchar)", "fiscal_year": "r.fy", "kategori_operasional_proyek": "NULL",
        "main_category": "r.maincategory", "sub_category": "r.subcategory", "kriteria_dampak_kualitatif": "NULL",
        "keterangan_sasaran": "r.keterangansasaran", "peristiwa_risiko": "r.peristiwarisiko", "peluang_terjadi": "r.peluang",
        "asumsi_dampak": "NULL", "deskripsi_dampak": "r.dampakrisiko",
        "valid_from": "CAST(coalesce(r.tanggalpembuatan, r.createddate) AS date)", "valid_to": "DATE '9999-12-31'", "is_current": "TRUE",
        **lin("erm_riskregister")}
    S["silver_dim_erm_risk_cause"] = {"_from": f"{cause_ctx} c",
        "risk_cause_id": "'LENO-PR-' || CAST(c.id AS varchar)", "risk_id": "'LENO-RR-' || CAST(c.riskregisterid AS varchar)",
        "divisi_id": "c.divisi_id", "cause_seq": "row_number() OVER (PARTITION BY c.riskregisterid ORDER BY c.id)",
        "penyebab": "c.penyebab", "dampak": "c.dampak", **scd("c"), **lin("erm_penyebabrisiko")}
    S["silver_fact_erm_existing_control"] = {
        "_from": f"{B('erm_existingcontrol')} e JOIN {cause_ctx} c ON c.id = e.penyebabrisikoid WHERE e.{A}",
        "existing_control_id": "'LENO-EC-' || CAST(e.id AS varchar)", "risk_id": "'LENO-RR-' || CAST(c.riskregisterid AS varchar)",
        "risk_cause_id": "'LENO-PR-' || CAST(c.id AS varchar)", "company_id": comp, "period_year": "c.fy",
        "existing_control": "e.existing", "parameter_efektivitas": "e.efektivitas", "parameter_kecukupan": "e.kecukupan",
        **lin("erm_existingcontrol")}
    # penilaian: inheren & residual (per tahun perencanaan) + realisasi monitoring (per periode pelaporan)
    kq, kl, kk = B("erm_kriteriadampakkuantitatif"), B("erm_kriteriadampakkualitatif"), B("erm_kriteriakemungkinan")
    parts = []
    for t, typ, per in [("erm_riskinherent", "INHEREN", None), ("erm_riskresidual", "RESIDUAL", None), ("erm_monitoring", "REALISASI", "pl.periode")]:
        y = f"year({per})" if per else "r.fy"
        mth = f"month({per})" if per else "CAST(NULL AS integer)"
        join_pl = f"LEFT JOIN {B('erm_pelaporan')} pl ON pl.id = a.pelaporanrisikoid " if per else ""
        parts.append(
            f"SELECT 'LENO-RR-' || CAST(a.riskregisterid AS varchar) AS risk_id, '{typ}' AS assessment_type, {y} AS period_year, "
            f"{mth} AS period_month, coalesce(q.skala, ql.skala) AS skor_dampak, k.skala AS skor_kemungkinan, a.tingkatrisiko, "
            f"a.kategoritingkatrisiko, q.kriteriadampak AS kq_kriteria, q.mindampak, q.maxdampak, q.deskripsidampak, "
            f"ql.kriteriadampak AS kl_kriteria, ql.parameter AS kl_parameter, ql.tiperisiko, k.parameter AS kk_parameter, "
            f"k.kriteria AS kk_kriteria, k.kriteriadampak AS kk_kriteriadampak, a.dampakfinansial, '{t}' AS src "
            f"FROM {B(t)} a JOIN {risk_ctx} r ON r.id = a.riskregisterid {join_pl}"
            f"LEFT JOIN {kq} q ON q.id = a.kriteriadampakkuantitatifid LEFT JOIN {kl} ql ON ql.id = a.kriteriadampakkualitatifid "
            f"LEFT JOIN {kk} k ON k.id = a.kriteriakemungkinanid WHERE a.{A}")
    S["silver_fact_erm_risk_assessment"] = {"_from": "(" + " UNION ALL ".join(parts) + ") x",
        "risk_id": "x.risk_id", "company_id": comp, "assessment_type": "x.assessment_type", "period_year": "x.period_year",
        "period_month": "x.period_month",
        "date_key": "CASE WHEN x.period_month IS NOT NULL THEN x.period_year * 10000 + x.period_month * 100 + 1 END",
        "skor_dampak": "x.skor_dampak", "skor_kemungkinan": "x.skor_kemungkinan", "tingkat_risiko": "x.tingkatrisiko",
        "kategori_tingkat_risiko": level("x.kategoritingkatrisiko"), "kriteria_dampak_kuantitatif": "x.kq_kriteria", "min_dampak": "x.mindampak",
        "max_dampak": "x.maxdampak", "deskripsi_dampak": "x.deskripsidampak", "kriteria_dampak_kualitatif": "x.kl_kriteria",
        "parameter_dampak_kualitatif": "x.kl_parameter", "parameter_kemungkinan": "x.kk_parameter", "kriteria_kemungkinan": "x.kk_kriteria",
        "kriteria_dampak_kemungkinan": "x.kk_kriteriadampak", "tipe_risiko": "x.tiperisiko", "dampak_finansial": "x.dampakfinansial",
        "currency_code": "'IDR'", "fx_rate_to_idr": "1.0", "nilai_dampak": "x.dampakfinansial", "dampak_terhadap_limit": "NULL",
        "exposure_risiko": "NULL", "kemungkinan_pct": "NULL", "biaya_pengendalian": "NULL",
        "_file_id": L.sq(f"{CATALOG_SRC}@{now:%Y-%m-%d %H:%M}Z"), "_batch_id": L.sq(batch_id), "_source_system": L.sq(SRC),
        "_source_file": "'lenodb.silver.' || x.src", "_loaded_at": L.lit(now, "timestamp")}
    S["silver_fact_erm_swot_analysis"] = {
        "_from": f"{B('erm_analisaswot')} w LEFT JOIN {B('erm_perencanaan')} p ON p.id = w.perencanaanrisikoid WHERE w.{A}",
        "swot_id": "'LENO-SW-' || CAST(w.id AS varchar)", "company_id": comp, "objective_id": "NULL", "period_year": "year(p.tahun)",
        "swot_kekuatan": "w.kekuatan", "swot_kelemahan": "w.kelemahan", "swot_peluang": "w.peluang", "swot_ancaman": "w.ancaman",
        **lin("erm_analisaswot")}
    bulan = ", ".join(f"m.bulan{i}" for i in range(1, 13))
    S["silver_fact_erm_mitigation_plan_monthly"] = {
        "_from": f"{B('erm_rencanamitigasi')} m JOIN {cause_ctx} c ON c.id = m.penyebabrisikoid "
                 f"CROSS JOIN UNNEST(sequence(1, 12)) AS u(mo) WHERE m.{A}",
        "mitigation_plan_id": "'LENO-RM-' || CAST(m.id AS varchar)", "risk_id": "'LENO-RR-' || CAST(c.riskregisterid AS varchar)",
        "risk_cause_id": "'LENO-PR-' || CAST(c.id AS varchar)", "company_id": comp, "period_year": "c.fy", "period_month": "u.mo",
        "date_key": "c.fy * 10000 + u.mo * 100 + 1", "rencana_penanganan": "m.rencanapenanganan",
        "target_waktu_penyelesaian": "m.targetwaktupenyelesaian", "anggaran_penanganan": "m.anggaranpenanganan",
        "currency_code": "'IDR'", "fx_rate_to_idr": "1.0", "is_rencana_bulan": f"coalesce(element_at(ARRAY[{bulan}], u.mo), 0) = 1",
        "source_month_column": "'bulan' || CAST(u.mo AS varchar)", **lin("erm_rencanamitigasi")}
    S["silver_fact_erm_mitigation_realization"] = {
        "_from": f"{B('erm_realisasimitigasi')} z JOIN {B('erm_rencanamitigasi')} m ON m.id = z.rencanamitigasiid "
                 f"JOIN {cause_ctx} c ON c.id = m.penyebabrisikoid "
                 f"LEFT JOIN {B('erm_monitoring')} mo ON mo.id = z.monitoringrisikoid "
                 f"LEFT JOIN {B('erm_pelaporan')} pl ON pl.id = mo.pelaporanrisikoid WHERE z.{A}",
        "mitigation_plan_id": "'LENO-RM-' || CAST(m.id AS varchar)", "risk_id": "'LENO-RR-' || CAST(c.riskregisterid AS varchar)",
        "company_id": comp, "period_year": "year(pl.periode)", "period_month": "month(pl.periode)",
        "date_key": "year(pl.periode) * 10000 + month(pl.periode) * 100 + 1", "realisasi_penanganan": "z.realisasipenanganan",
        "persentase_realisasi": "z.persentaserealisasi", "penggunaan_anggaran": "z.penggunaananggaran", "currency_code": "'IDR'",
        "fx_rate_to_idr": "1.0", "status_penanganan_risiko": "z.statuspenangananrisiko", "dokumen_path": "z.dokumen",
        "dokumen_sha256": "NULL", "alasan_tidak_direalisasikan": "z.alasantidakdirealisasikan", "persentase_biaya_pengendalian": "NULL",
        "pic_fungsi": "m.unitkerjaterkait", **lin("erm_realisasimitigasi")}
    S["silver_fact_erm_risk_appetite"] = {"_from": f"{B('erm_penerimaanrisiko')} a WHERE a.{A}",
        "company_id": comp, "period_year": "year(a.tahun)", "date_key": "year(a.tahun) * 10000 + 101", "plan_label": "'RKAP'",
        "nilai_kapasitas_risiko": "a.nilaikapasitasrisiko", "nilai_selera_risiko": "a.nilaiselerarisiko",
        "nilai_toleransi_risiko": "a.nilaitoleransirisiko", "nilai_batasan_risiko": "a.nilaibatasanrisiko",
        "currency_code": "'IDR'", "fx_rate_to_idr": "1.0", "amount_unit": "'IDR'", **lin("erm_penerimaanrisiko")}
    return S


def gold(tq: L.Trino, batch_id: str, now: datetime) -> dict[str, dict[str, str]]:
    R, A, MP, MR, D = (tq.fq(x) for x in ("silver_dim_erm_risk", "silver_fact_erm_risk_assessment", "silver_fact_erm_mitigation_plan_monthly",
                                         "silver_fact_erm_mitigation_realization", "silver_dim_erm_risk_cause"))
    co_rest = f"'PT Len Industri (Persero)' AS company_name, {L.sq(COMPANY[1])} AS company_acronym, {L.sq(L.HOLDING)} AS holding_name"
    co = f"{L.sq(COMPANY[0])} AS company_id, {co_rest}"   # untuk subquery tanpa company_id; a.*/p.* sudah membawa company_id
    urut = "CASE kategori_tingkat_risiko " + " ".join(f"WHEN {L.sq(k)} THEN {v[0]}" for k, v in LEVEL.items()) + " END"
    warna = "CASE kategori_tingkat_risiko " + " ".join(f"WHEN {L.sq(k)} THEN {L.sq(v[1])}" for k, v in LEVEL.items()) + " END"
    mon = "ARRAY['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des']"
    tail = {"_batch_id": L.sq(batch_id), "_loaded_at": L.lit(now, "timestamp"), "_source_system": L.sq(SRC)}
    per = lambda a: {"period_date": f"date_parse(CAST({a}.date_key AS varchar), '%Y%m%d')", "date_key": f"{a}.date_key",  # noqa: E731
                     "period_month": f"{a}.period_month", "month_name": f"element_at({mon}, {a}.period_month)",
                     "quarter_label": f"'Q' || CAST(({a}.period_month + 2) / 3 AS varchar)"}
    leno = f"_source_system = '{SRC}'"
    G: dict[str, dict[str, str]] = {}
    G["gold_erm_risk_assessment_monthly"] = {
        "_from": f"(SELECT a.*, r.peristiwa_risiko, r.main_category, {co_rest}, {urut} AS urutan, a.period_year AS fiscal_year "
                 f"FROM {A} a JOIN {R} r ON r.risk_id = a.risk_id AND r.{leno} WHERE a.{leno} AND a.period_month IS NOT NULL) g",
        "fiscal_year": "g.fiscal_year", "company_id": "g.company_id", "company_name": "g.company_name", "company_acronym": "g.company_acronym",
        "holding_name": "g.holding_name", **per("g"), "risk_id": "g.risk_id", "peristiwa_risiko": "g.peristiwa_risiko",
        "main_category": "g.main_category", "assessment_type": "g.assessment_type", "skor_dampak": "g.skor_dampak",
        "skor_kemungkinan": "g.skor_kemungkinan", "kemungkinan_pct": "g.kemungkinan_pct", "tingkat_risiko": "g.tingkat_risiko",
        "kategori_tingkat_risiko": "g.kategori_tingkat_risiko", "urutan_tingkat": "g.urutan", "nilai_dampak": "g.nilai_dampak",
        "dampak_terhadap_limit": "g.dampak_terhadap_limit", "exposure_risiko": "g.exposure_risiko", **tail}
    G["gold_erm_risk_heatmap_monthly"] = {
        "_from": f"(SELECT period_year AS fiscal_year, date_key, period_month, assessment_type, skor_dampak, skor_kemungkinan, "
                 f"max(tingkat_risiko) AS tingkat_risiko, max(kategori_tingkat_risiko) AS kategori_tingkat_risiko, "
                 f"max({urut}) AS urutan, max({warna}) AS warna, count(DISTINCT risk_id) AS n, "
                 f"array_join(array_agg(DISTINCT risk_id), ', ') AS ids, sum(exposure_risiko) AS exp "
                 f"FROM {A} WHERE {leno} AND period_month IS NOT NULL "
                 f"GROUP BY period_year, date_key, period_month, assessment_type, skor_dampak, skor_kemungkinan) g "
                 f"CROSS JOIN (SELECT {co}) c",
        "fiscal_year": "g.fiscal_year", "company_id": "c.company_id", "company_name": "c.company_name", "company_acronym": "c.company_acronym",
        "holding_name": "c.holding_name", **per("g"), "assessment_type": "g.assessment_type", "skor_dampak": "g.skor_dampak",
        "skor_kemungkinan": "g.skor_kemungkinan", "tingkat_risiko": "g.tingkat_risiko", "kategori_tingkat_risiko": "g.kategori_tingkat_risiko",
        "urutan_tingkat": "g.urutan", "warna_hex": "g.warna", "jumlah_risiko": "g.n", "daftar_risk_id": "substr(g.ids, 1, 4000)",
        "total_exposure_risiko": "g.exp", **tail}
    G["gold_erm_mitigation_progress_monthly"] = {
        "_from": f"(SELECT p.*, r.peristiwa_risiko, r.main_category, d.penyebab, z.persentase_realisasi, z.realisasi_penanganan, "
                 f"z.pic_fungsi, {co_rest} FROM {MP} p JOIN {R} r ON r.risk_id = p.risk_id AND r.{leno} "
                 f"LEFT JOIN {D} d ON d.risk_cause_id = p.risk_cause_id AND d.{leno} "
                 f"LEFT JOIN (SELECT mitigation_plan_id, date_key, max(persentase_realisasi) AS persentase_realisasi, "
                 f"max(realisasi_penanganan) AS realisasi_penanganan, max(pic_fungsi) AS pic_fungsi FROM {MR} WHERE {leno} "
                 f"GROUP BY mitigation_plan_id, date_key) z ON z.mitigation_plan_id = p.mitigation_plan_id AND z.date_key = p.date_key "
                 f"WHERE p.{leno} AND p.is_rencana_bulan) g",
        "fiscal_year": "g.period_year", "company_id": "g.company_id", "company_name": "g.company_name", "company_acronym": "g.company_acronym",
        "holding_name": "g.holding_name", **per("g"), "risk_id": "g.risk_id", "peristiwa_risiko": "g.peristiwa_risiko",
        "main_category": "g.main_category", "mitigation_plan_id": "g.mitigation_plan_id", "risk_cause_id": "g.risk_cause_id",
        "penyebab": "g.penyebab", "rencana_penanganan": "g.rencana_penanganan", "pic_fungsi": "g.pic_fungsi",
        "persentase_realisasi": "g.persentase_realisasi", "realisasi_penanganan": "g.realisasi_penanganan",
        "is_dilaporkan": "g.persentase_realisasi IS NOT NULL",
        "status_progres": "CASE WHEN g.persentase_realisasi IS NULL THEN 'Belum dilaporkan' WHEN g.persentase_realisasi >= 100 THEN 'Selesai' "
                          "WHEN g.persentase_realisasi > 0 THEN 'Berjalan' ELSE 'Belum mulai' END", **tail}
    inh = f"(SELECT * FROM {A} WHERE {leno} AND assessment_type = 'INHEREN')"
    last = (f"(SELECT * FROM (SELECT a.*, row_number() OVER (PARTITION BY risk_id ORDER BY date_key DESC) AS rn FROM {A} a "
            f"WHERE {leno} AND assessment_type = 'REALISASI') WHERE rn = 1)")
    G["gold_erm_risk_register"] = {
        "_from": f"{R} r LEFT JOIN (SELECT risk_id, max_by(skor_dampak, tingkat_risiko) AS sd, max_by(skor_kemungkinan, tingkat_risiko) AS sk, "
                 f"max(tingkat_risiko) AS tr, max_by(kategori_tingkat_risiko, tingkat_risiko) AS kt, max(nilai_dampak) AS nd "
                 f"FROM {inh} GROUP BY risk_id) i ON i.risk_id = r.risk_id LEFT JOIN {last} l ON l.risk_id = r.risk_id "
                 f"LEFT JOIN (SELECT risk_id, count(*) AS n FROM {D} WHERE {leno} GROUP BY risk_id) dc ON dc.risk_id = r.risk_id "
                 f"LEFT JOIN (SELECT risk_id, count(DISTINCT mitigation_plan_id) AS n FROM {MP} WHERE {leno} GROUP BY risk_id) pc ON pc.risk_id = r.risk_id "
                 f"LEFT JOIN (SELECT risk_id, avg(persentase_realisasi) AS p FROM {MR} WHERE {leno} GROUP BY risk_id) pr ON pr.risk_id = r.risk_id "
                 f"LEFT JOIN {tq.fq('silver_dim_erm_objective')} o ON o.objective_id = r.objective_id AND o.{leno} "
                 f"WHERE r.{leno}",
        "fiscal_year": "r.fiscal_year", "company_id": L.sq(COMPANY[0]), "company_name": "'PT Len Industri (Persero)'",
        "company_acronym": L.sq(COMPANY[1]), "holding_name": L.sq(L.HOLDING), "risk_id": "r.risk_id", "objective_id": "r.objective_id",
        "nama_sasaran": "o.nama_sasaran", "keterangan_sasaran": "r.keterangan_sasaran", "main_category": "r.main_category",
        "peristiwa_risiko": "r.peristiwa_risiko", "deskripsi_dampak": "r.deskripsi_dampak", "asumsi_dampak": "r.asumsi_dampak",
        "skor_dampak_inheren": "i.sd", "skor_kemungkinan_inheren": "i.sk", "kemungkinan_pct_inheren": "NULL",
        "tingkat_risiko_inheren": "i.tr", "kategori_tingkat_risiko_inheren": "i.kt",
        "urutan_tingkat_inheren": "CASE i.kt " + " ".join(f"WHEN {L.sq(k)} THEN {v[0]}" for k, v in LEVEL.items()) + " END",
        "nilai_dampak_inheren": "i.nd", "dampak_terhadap_limit_inheren": "NULL", "exposure_risiko_inheren": "NULL",
        "biaya_pengendalian": "NULL", "periode_realisasi_terakhir": "date_parse(CAST(l.date_key AS varchar), '%Y%m%d')",
        "skor_dampak_realisasi": "l.skor_dampak", "skor_kemungkinan_realisasi": "l.skor_kemungkinan",
        "tingkat_risiko_realisasi": "l.tingkat_risiko", "kategori_tingkat_risiko_realisasi": "l.kategori_tingkat_risiko",
        "nilai_dampak_realisasi": "l.nilai_dampak", "exposure_risiko_realisasi": "NULL", "jumlah_penyebab": "coalesce(dc.n, 0)",
        "jumlah_rencana_penanganan": "coalesce(pc.n, 0)", "progres_penanganan_rata2": "pr.p", "status_aktif": "r.is_current", **tail}
    return G


def available(tq: L.Trino) -> bool:
    try:
        tq.q(f"SELECT 1 FROM {CATALOG_SRC}.erm_riskregister LIMIT 1", attempts=2)
        return True
    except Exception as e:  # noqa: BLE001 — katalog lenodb tidak terjangkau: lewati, data LENO_ERM lama tetap
        L.log(f"  ! {CATALOG_SRC} tidak terjangkau ({str(e)[:100]}) — ERM LenO dilewati")
        return False


def build(tq: L.Trino, schema: dict, batch_id: str, now: datetime) -> None:
    if not available(tq):
        return
    L.log(f"Bronze/Silver/Gold ERM dari {CATALOG_SRC} (Aplikasi ERM LenO)")
    for b, n in bronze(tq).items():
        L.log(f"  {b:45s} {n:6d} baris")
    live = set(tq.tables())
    for name, m in silver(tq, batch_id, now).items():
        sdm.load_select(tq, schema, live, name, m, delete_where=WHERE_SRC)
    for name, m in gold(tq, batch_id, now).items():
        sdm.load_select(tq, schema, live, name, m, delete_where=WHERE_SRC)
