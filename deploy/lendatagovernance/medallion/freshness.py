"""Kesegaran data (data freshness) untuk setiap tabel Gold.

- record_runs(): mencatat setiap pengambilan (grab) sumber ke silver_fact_meta_etl_run — untuk sumber LenoDB lengkap dengan
  watermark CDC (lenodb.silver._cdc_watermarks: perubahan terakhir di aplikasi & waktu replika diperbarui); untuk berkas
  (E-GRC, workbook, DBASTACITA) dengan waktu berkas terakhir masuk.
- build_gold(): gold_meta_data_freshness — per tabel Gold (dan per _source_system bila tabelnya multi-sumber): jumlah baris,
  perubahan sumber terakhir, replika CDC terakhir, grab ETL terakhir (= _loaded_at isi tabel), umur, dan status.

Status: Segar | Menunggu ETL (sumber/replika lebih baru dari grab) | Sumber CDC tidak diperbarui (replika > 48 jam) |
Berkas statis (sumber berkas; diperbarui saat berkas baru masuk inbox/Nextcloud).
"""
from __future__ import annotations

from datetime import datetime, timezone

import lakehouse as L

CDC = "lenodb.silver._cdc_watermarks"
REPLICA_STALE_HOURS = 48
LENO_OBJECTS = {
    "LENO_ERM": None,   # diisi dari leno_erm.TABLES saat dipakai
    "LENO_SDM": ["ps_karyawan", "ps_statusbarukaryawan", "ps_ukkaryawan", "ab_absensikaryawan", "hr_unitkerja"],
}
STATIC_SOURCES = {"SDM": "lakekeeper.medallion (prototipe 2026-11-02, data karyawan)",
                  "CORP": "lakekeeper.medallion (prototipe 2026-11-02, data korporasi)"}


def leno_objects(system: str) -> list[str]:
    if system == "LENO_ERM":
        import leno_erm
        return list(leno_erm.TABLES)
    return LENO_OBJECTS[system]


def watermarks(tq: L.Trino, objects: list[str]) -> dict[str, tuple]:
    """tabel → (perubahan sumber terakhir, replika diperbarui)."""
    inl = ", ".join(L.sq(o) for o in objects)
    return {r[0]: (datetime.fromtimestamp(r[1] / 1000, timezone.utc) if r[1] else None, r[2])
            for r in tq.q(f"SELECT table_name, last_source_ts_ms, updated_at FROM {CDC} WHERE table_name IN ({inl})")}


def last_processed(tq: L.Trino, system: str) -> dict[str, datetime]:
    """Watermark replika yang sudah diproses ETL terakhir kali (per tabel sumber)."""
    if "silver_fact_meta_etl_run" not in set(tq.tables()):
        return {}
    return {o.removeprefix("lenodb.silver."): rep for o, rep in tq.q(
        f"SELECT source_object, max(source_replicated_at) FROM {tq.fq('silver_fact_meta_etl_run')} "
        f"WHERE source_system = {L.sq(system)} AND status = 'SUCCESS' GROUP BY 1")}


def cdc_changed(tq: L.Trino, system: str) -> list[str]:
    """Tabel sumber yang replikanya diperbarui sejak grab terakhir (atau belum pernah diproses)."""
    wm, done = watermarks(tq, leno_objects(system)), last_processed(tq, system)
    return [o for o, (_, rep) in wm.items() if rep and (o not in done or done[o] is None or rep > done[o])]


def record_runs(tq: L.Trino, schema: dict, systems: list[str], batch_id: str, grab_at: datetime, trigger: str,
                status: str = "SUCCESS") -> None:
    name = "silver_fact_meta_etl_run"
    L.ensure_table(tq, name, schema[name], set(tq.tables()), managed=False)
    fin = datetime.now(timezone.utc)
    rows = []
    for s in systems:
        base = {"run_id": batch_id, "source_system": s, "etl_grab_at": grab_at, "etl_finished_at": fin, "trigger_kind": trigger, "status": status}
        if s.startswith("LENO_"):
            for o, (chg, rep) in watermarks(tq, leno_objects(s)).items():
                rows.append({**base, "source_object": f"lenodb.silver.{o}", "source_last_change_at": chg, "source_replicated_at": rep})
        elif s in STATIC_SOURCES:
            rows.append({**base, "source_object": STATIC_SOURCES[s], "source_last_change_at": datetime(2026, 11, 2, tzinfo=timezone.utc)})
        else:
            cond = "file_name LIKE 'DBASTACITA%'" if s == "ASTACITA" else f"source_system = {L.sq(s)}"
            r = tq.q(f"SELECT max_by(file_name, ingested_at), max(ingested_at) FROM {tq.fq('bronze_repository')} WHERE {cond}")
            if r and r[0][1]:
                rows.append({**base, "source_object": r[0][0], "source_last_change_at": r[0][1]})
    L.insert(tq, name, [(c, t) for c, t, _ in schema[name]["cols"]], rows)


def domain(t: str) -> str:
    for p, d in (("gold_erm_", "ERM"), ("gold_sdm_", "SDM"), ("gold_astacita_", "ASTACITA"), ("gold_meta_", "META")):
        if t.startswith(p):
            return d
    return "LAIN"


def default_source(t: str) -> str:
    if t.startswith("gold_astacita_"):
        return "ASTACITA"
    if t.startswith("gold_sdm_"):
        return "LENO_SDM" if t == "gold_sdm_headcount_monthly" else "SDM"
    if t.startswith("gold_meta_"):
        return "DG_WORKBOOK"
    return "EGRC"


HIGHLIGHT_DAYS = 7   # status "Diperbarui" bertahan 7 hari setelah isi Gold terakhir berubah; selebihnya "Eksisting"
FRESH_NAME = "gold_meta_data_freshness"


def previous_state(tq: L.Trino) -> dict[tuple, tuple]:
    """(tabel, sumber) → (sidik isi, jumlah baris, kapan terakhir berubah, jumlah baris sebelum perubahan) dari pemeriksaan sebelumnya.
    Harus dibaca SEBELUM ensure_table (skema baru membuat ulang tabel)."""
    if FRESH_NAME not in set(tq.tables()) or "content_fingerprint" not in {c for c, _ in tq.columns(FRESH_NAME)}:
        return {}
    return {(r[0], r[1]): r[2:] for r in tq.q(
        f"SELECT target_table, source_system, content_fingerprint, row_count, last_changed_at, previous_row_count FROM {tq.fq(FRESH_NAME)}")}


def update_info(prev, fp: str, n: int, grab, now: datetime) -> dict:
    """Status pembaruan — tidak pernah kosong: 'Diperbarui' (isi berubah ≤ 7 hari) atau 'Eksisting'."""
    if prev is None or prev[0] is None:      # pemeriksaan pertama: belum ada pembanding → isi dianggap eksisting
        chg, before, note, note_en = None, None, "Eksisting: pemeriksaan pertama, belum ada pembanding.", "Existing: first check, no baseline to compare."
    elif prev[0] != fp:
        chg, before = now, prev[1]
        d = n - (prev[1] or 0)
        note = f"Isi berubah: {prev[1]} → {n} baris ({d:+d})." if d else f"Isi berubah: jumlah baris tetap {n}, nilai ada yang berbeda."
        note_en = f"Content changed: {prev[1]} → {n} rows ({d:+d})." if d else f"Content changed: row count unchanged at {n}, some values differ."
    else:
        chg, before = prev[2], prev[3]
        note, note_en = (f"Eksisting: tidak ada perubahan isi (terakhir berubah {chg:%Y-%m-%d}).", f"Existing: no content change (last changed {chg:%Y-%m-%d}).") \
            if chg else ("Eksisting: tidak ada perubahan isi sejak pertama dipantau.", "Existing: no content change since first monitored.")
    recent = chg is not None and (now - chg).days < HIGHLIGHT_DAYS
    if recent and prev is not None and prev[0] == fp:   # perubahan lama yang masih dalam masa sorotan: pakai ringkasan perubahannya
        d = n - (before or 0)
        note = f"Diperbarui {chg:%Y-%m-%d}: {before} → {n} baris ({d:+d})." if before is not None else f"Diperbarui {chg:%Y-%m-%d}."
        note_en = f"Updated {chg:%Y-%m-%d}: {before} → {n} rows ({d:+d})." if before is not None else f"Updated {chg:%Y-%m-%d}."
    return {"content_fingerprint": fp, "last_changed_at": chg, "previous_row_count": before,
            "update_status": "Diperbarui" if recent else "Eksisting", "update_status_en": "Updated" if recent else "Existing",
            "update_note": note, "update_note_en": note_en}


def build_gold(tq: L.Trino, schema: dict, batch_id: str) -> int:
    now = datetime.now(timezone.utc)
    prev_state = previous_state(tq)
    R = tq.fq("silver_fact_meta_etl_run")
    latest = {}   # source_system → (objects, last change, replica)
    for s, objs, chg, rep in tq.q(
            f"SELECT source_system, array_join(array_agg(DISTINCT source_object), ', '), max(source_last_change_at), max(source_replicated_at) "
            f"FROM {R} r WHERE status = 'SUCCESS' AND run_id = (SELECT max_by(run_id, etl_grab_at) FROM {R} x "
            f"WHERE x.source_system = r.source_system AND x.status = 'SUCCESS') GROUP BY 1"):
        latest[s] = (objs, chg, rep)
    rows = []
    for t in sorted(x for x in tq.tables() if x.startswith("gold_") and x != "gold_meta_data_freshness"):
        cols = {c for c, _ in tq.columns(t)}
        if "_loaded_at" not in cols:
            continue
        content = ", ".join(f'"{c}"' for c, _ in tq.columns(t) if not c.startswith("_")) or "1"
        fpx = f"to_hex(checksum(ROW({content})))"
        q = (f"SELECT _source_system, count(*), max(_loaded_at), {fpx} FROM {tq.fq(t)} GROUP BY 1" if "_source_system" in cols
             else f"SELECT NULL, count(*), max(_loaded_at), {fpx} FROM {tq.fq(t)}")
        for src, n, grab, fp in tq.q(q):
            src = src or default_source(t)
            objs, chg, rep = latest.get(src, (None, None, None))
            h_grab = (now - grab).total_seconds() / 3600 if grab else None
            h_rep = (now - rep).total_seconds() / 3600 if rep else None
            if src.startswith("LENO_"):
                if rep and grab and rep > grab:
                    st, note = "Menunggu ETL", "Replika CDC lebih baru dari grab terakhir; ETL berikutnya (≤ 15 menit) akan mengambilnya."
                elif h_rep is not None and h_rep > REPLICA_STALE_HOURS:
                    st, note = "Sumber CDC tidak diperbarui", f"Replika LenoDB terakhir diperbarui {rep:%Y-%m-%d %H:%M} UTC (> {REPLICA_STALE_HOURS} jam)."
                else:
                    st, note = "Segar", "Gold = isi replika CDC terakhir."
            else:
                if chg and grab and chg > grab:
                    st, note = "Menunggu ETL", "Berkas sumber lebih baru dari grab terakhir."
                else:
                    st, note = "Berkas statis", "Sumber berkas; diperbarui saat berkas baru masuk inbox/Nextcloud."
            rows.append({"target_table": t, "domain": domain(t), "source_system": src, "source_objects": objs, "row_count": n,
                         "source_last_change_at": chg, "source_replicated_at": rep, "last_etl_grab_at": grab,
                         "hours_since_grab": h_grab, "hours_replica_age": h_rep, "freshness_status": st, "status_note": note,
                         "checked_at": now, **update_info(prev_state.get((t, src)), fp or "", n, grab, now),
                         "_batch_id": batch_id, "_loaded_at": now})
    name = "gold_meta_data_freshness"
    L.ensure_table(tq, name, schema[name], set(tq.tables()), managed=True)
    L.replace_rows(tq, name, schema[name], rows)
    return len(rows)
