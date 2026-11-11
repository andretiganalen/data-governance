#!/usr/bin/env python3
"""Komentar tabel Silver (bahasa Indonesia) — dipasang ke Trino lalu terbaca katalog.
Hanya mengisi tabel yang komentarnya kosong; dipanggil di akhir `lakehouse.py rebuild`."""
from __future__ import annotations
import lakehouse as L

C = {
 "silver_dim_company_hierarchy": "Hierarki perusahaan: induk, anak, kedalaman, dan hubungan terhadap Len.",
 "silver_dim_date": "Dimensi tanggal (hari, bulan, kuartal, tahun) untuk semua tabel Gold.",
 "silver_dim_erm_control_adequacy": "Referensi skala kecukupan kontrol risiko (ERM).",
 "silver_dim_erm_control_effectiveness": "Referensi skala efektivitas kontrol risiko (ERM).",
 "silver_dim_erm_impact_criteria_qualitative": "Kriteria dampak risiko kualitatif per skor (ERM).",
 "silver_dim_erm_impact_criteria_quantitative": "Kriteria dampak risiko kuantitatif per skor, dalam rentang nilai (ERM).",
 "silver_dim_erm_likelihood_criteria": "Kriteria kemungkinan terjadinya risiko per skor (ERM).",
 "silver_dim_erm_objective": "Sasaran perusahaan/unit yang menjadi dasar penilaian risiko (ERM).",
 "silver_dim_erm_objective_basis": "Referensi dasar sasaran (nama sasaran) untuk penilaian risiko (ERM).",
 "silver_dim_erm_risk": "Daftar risiko terdaftar (satu baris per risiko): perusahaan, divisi, unit, sasaran, dan kategori (ERM).",
 "silver_dim_erm_risk_cause": "Penyebab setiap risiko terdaftar (ERM).",
 "silver_dim_erm_risk_matrix": "Matriks risiko 5x5: skor dampak x kemungkinan menjadi level risiko (ERM).",
 "silver_dim_erm_risk_taxonomy": "Taksonomi kategori risiko (ERM).",
 "silver_dim_fx_rate": "Kurs mata uang ke rupiah per tanggal.",
 "silver_dim_meta_access": "Hak akses data per unit kerja dan aset target, dengan klasifikasinya (metadata tata kelola).",
 "silver_dim_meta_data_domain": "Domain data dan pemilik domain (metadata tata kelola).",
 "silver_dim_meta_dataset": "Katalog dataset bisnis (metadata tata kelola).",
 "silver_dim_meta_dq_dimension": "Dimensi kualitas data: akurasi, kelengkapan, konsistensi, dan sebagainya.",
 "silver_dim_meta_dq_rule": "Aturan kualitas data per elemen data.",
 "silver_dim_meta_field": "Elemen data (field) beserta definisi bisnisnya (metadata tata kelola).",
 "silver_dim_meta_field_alias": "Nama lain (alias) elemen data pada sistem sumber.",
 "silver_dim_meta_glossary": "Glosarium istilah bisnis dan definisinya.",
 "silver_dim_meta_governance_assignment": "Penetapan Data Owner, Data Steward, dan Data User per elemen data.",
 "silver_dim_meta_kpi": "Daftar indikator kinerja (KPI): definisi, rumus, target, frekuensi, sumber data, dan pemilik.",
 "silver_dim_meta_library": "Pustaka referensi tata kelola data: grup, item, deskripsi, dan kategori izin.",
 "silver_dim_meta_lineage": "Alur data (lineage) dari sumber ke tabel dan layar aplikasi.",
 "silver_dim_meta_system": "Sistem sumber data: jenis aplikasi, status siklus hidup, kritikalitas, pemilik bisnis, Data Owner, dan Data Steward.",
 "silver_dim_meta_table": "Tabel basis data yang terdaftar di tata kelola data.",
 "silver_dim_organization": "Struktur organisasi: Direktorat, Divisi (Eselon 1), unit kerja (Eselon 2), dan Fungsi.",
 "silver_fact_erm_existing_control": "Kontrol yang sudah ada untuk setiap risiko dan penyebabnya, dengan efektivitas dan kecukupannya (ERM).",
 "silver_fact_erm_kri_monthly": "Nilai dan status Key Risk Indicator (KRI) per bulan (ERM).",
 "silver_fact_erm_mitigation_plan_monthly": "Rencana progres penanganan risiko per bulan (ERM).",
 "silver_fact_erm_mitigation_realization": "Realisasi penanganan risiko per bulan: persentase realisasi dan penggunaan anggaran (ERM).",
 "silver_fact_erm_risk_appetite": "Batasan selera risiko (risk appetite) per periode (ERM).",
 "silver_fact_erm_risk_assessment": "Penilaian risiko inheren dan residual per risiko dan periode (ERM).",
 "silver_fact_erm_swot_analysis": "Analisis SWOT yang mendasari identifikasi risiko (ERM).",
 "silver_fact_meta_baseline_correction": "Catatan koreksi pada berkas baseline: sheet, rentang sel, jenis masalah, rumus/nilai asli dan usulan.",
 "silver_fact_meta_dq_result": "Hasil pengujian aturan kualitas data per jalankan.",
}

def main() -> None:
    tq = L.Trino()
    have = {r[0] for r in tq.q(f"SELECT table_name FROM system.metadata.table_comments WHERE catalog_name = '{tq.catalog}' "
                               f"AND schema_name = '{tq.schema}' AND comment IS NOT NULL AND comment <> ''")}
    exist = {r[0] for r in tq.q(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{tq.schema}'")}
    n = 0
    for t, c in C.items():
        if t in exist and t not in have:
            tq.q(f"COMMENT ON TABLE {tq.fq(t)} IS " + L.sq(c)); n += 1
    L.log(f"komentar tabel Silver: {n} diisi")

if __name__ == "__main__":
    main()
