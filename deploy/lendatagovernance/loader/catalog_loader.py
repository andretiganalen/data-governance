#!/usr/bin/env python3
"""Phase 3 loader for the Len Data Governance catalog (plan/lendatagovernance_deployment_plan.md §7). Stdlib only.

Idempotent: writes are PUT (create-or-update) or JSON-patch of fixed values — re-running never duplicates.

  catalog_loader.py foundation [--dry-run]              classification, services, glossary
  catalog_loader.py workbook <file.xlsx> [--dry-run]    everything from Workbook Governance (+ foundation)
  catalog_loader.py inspect <file.xlsx>                 sheets + headers

ERM tables (sheet Database_Object) are NOT a separate service: their metadata (descriptions, sensitivity tags,
glossary terms, owners, DQ tests, lineage to LenO screens) is applied to the matching Trino tables in
len_lakehouse_trino.lakekeeper.medallion_repository (workbook.TABLE_MAP). The old LenO_ERM database service is removed.

Auth: LDG_TOKEN = Personal Access Token of a Len Data Governance *admin* (Profile › Access Token),
read from /home/ubuntu/data-governance/data/secrets/loader.env or the environment. Admin is required because the
workbook load creates teams, roles, policies and custom properties.
Defect report → /home/ubuntu/data-governance/data/reports/ (outside git: the repo is public).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workbook as W  # noqa: E402

API_URL = os.environ.get("LDG_API_URL", "http://127.0.0.1:8585/api")
SECRETS = os.environ.get("LDG_LOADER_ENV", "/home/ubuntu/data-governance/data/secrets/loader.env")
REPORT_DIR = os.environ.get("LDG_REPORT_DIR", "/home/ubuntu/data-governance/data/reports")

SENSITIVITY = {
    "name": W.CLASSIFICATION, "displayName": W.CLASSIFICATION, "mutuallyExclusive": True,
    "description": "Klasifikasi sensitivitas Elemen Data ERM. Per kolom berlaku level terketat dari Elemen Data-nya.",
}
SENSITIVITY_TAGS = [
    ("Public", "Public", "Data yang dapat diakses atau dibagikan kepada publik tanpa menimbulkan dampak signifikan bagi perusahaan."),
    ("Restricted", "Restricted", "Data yang penggunaannya terbatas untuk kebutuhan internal dan hanya dapat diakses oleh pihak yang memiliki kewenangan."),
    ("Confidential", "Confidential", "Data yang akses atau pengungkapannya secara tidak sah dapat menimbulkan risiko atau kerugian bagi perusahaan, sehingga memerlukan pengendalian akses yang lebih ketat."),
    ("StrictlyConfidential", "Strictly Confidential", "Data yang sangat sensitif dan pengungkapan atau akses tanpa kewenangan dapat menimbulkan dampak serius bagi perusahaan, sehingga memerlukan pengamanan dan akses yang sangat terbatas."),
]


def load_token() -> str:
    tok = os.environ.get("LDG_TOKEN")
    if not tok and os.path.exists(SECRETS):
        for line in open(SECRETS):
            if line.startswith("LDG_TOKEN="):
                tok = line.split("=", 1)[1].strip().strip('"')
    if not tok:
        sys.exit(f"LDG_TOKEN not set. Put LDG_TOKEN=<admin personal access token> in {SECRETS} (chmod 600).")
    return tok


class Catalog:
    def __init__(self, dry: bool):
        self.dry = dry
        self.token = "dry" if dry else load_token()
        self.writes = 0

    def call(self, method: str, path: str, body=None, content_type="application/json"):
        req = urllib.request.Request(
            API_URL + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": content_type},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            sys.exit(f"\nFAILED {method} {path} → HTTP {e.code}: {e.read().decode()[:600]}\n"
                     f"payload: {json.dumps(body)[:600] if body else ''}")

    def get(self, path: str):
        if self.dry:
            name = path.rstrip("/").split("/")[-1].split("?")[0]
            return {"id": f"dry-{name}", "name": name, "fullyQualifiedName": name}
        return self.call("GET", path)

    def put(self, path: str, body: dict):
        self.writes += 1
        if self.dry:
            fqn = body.get("name", "?")
            return {"id": f"dry-{fqn}", "name": fqn, "fullyQualifiedName": fqn,
                    "columns": [{"name": c["name"], "fullyQualifiedName": f"{fqn}.{c['name']}"}
                                for c in body.get("columns", [])]}
        return self.call("PUT", path, body)

    def find(self, path: str):
        """GET, None bila 404 (entitas belum/tidak ada)."""
        if self.dry:
            return self.get(path)
        req = urllib.request.Request(API_URL + path, headers={"Authorization": f"Bearer {self.token}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            sys.exit(f"\nFAILED GET {path} → HTTP {e.code}: {e.read().decode()[:600]}")

    def patch(self, path: str, ops: list):
        self.writes += 1
        if self.dry:
            return {}
        return self.call("PATCH", path, ops, "application/json-patch+json")


def q(name: str) -> str:
    return urllib.parse.quote(name, safe="")


def ref(entity: dict, typ: str) -> dict:
    return {"id": entity["id"], "type": typ}


def step(msg: str):
    print(f"• {msg}", flush=True)


# ------------------------------------------------------------------------------- foundation
def foundation(om: Catalog):
    step("foundation: classification Sensitivitas + 4 tags, dashboard service LenO ERM, glossary ERM")
    om.put("/v1/classifications", SENSITIVITY)
    for name, display, desc in SENSITIVITY_TAGS:
        om.put("/v1/tags", {"classification": W.CLASSIFICATION, "name": name, "displayName": display,
                            "description": desc})
    om.put("/v1/services/dashboardServices", {
        "name": W.SERVICE, "displayName": "LenO ERM", "serviceType": "CustomDashboard",
        "description": "Layar Aplikasi ERM LenO (satu Dashboard per layar) untuk lineage kolom → layar. Tanpa koneksi."})
    om.put("/v1/glossaries", {
        "name": W.GLOSSARY, "displayName": "ERM", "mutuallyExclusive": False,
        "description": "Glosarium bisnis ERM: satu istilah per Elemen Data, dari Workbook Governance."})


# ------------------------------------------------------------------------------- workbook
def ensure_custom_property(om: Catalog, entity_type: str, prop_type: str, name: str, display: str,
                           desc: str, config):
    et = om.get(f"/v1/metadata/types/name/{entity_type}?fields=customProperties")
    pt = om.get(f"/v1/metadata/types/name/{prop_type}")
    body = {"name": name, "displayName": display, "description": desc,
            "propertyType": {"id": pt["id"], "type": "type"}, "customPropertyConfig": {"config": config}}
    om.put(f"/v1/metadata/types/{et['id']}", body)


def load_workbook(om: Catalog, path: str):
    plan = W.to_lakehouse(W.build(W.read_xlsx(path)))
    step(f"workbook parsed: {dict(plan.stats)}; {len(plan.defects)} defects")
    foundation(om)

    # Teams
    step(f"teams: root → '{W.ROOT_DISPLAY}', {len(plan.teams)} teams")
    teams = {W.ROOT_TEAM: om.get(f"/v1/teams/name/{W.ROOT_TEAM}")}
    om.patch(f"/v1/teams/{teams[W.ROOT_TEAM]['id']}",
             [{"op": "add", "path": "/displayName", "value": W.ROOT_DISPLAY}])
    for t in plan.teams:
        cur = om.find(f"/v1/teams/name/{q(t['name'])}") if t["name"].startswith("FN_") else None
        if cur and cur.get("displayName") != t["displayName"]:   # Fungsi diganti namanya oleh admin DG di aplikasi → dipertahankan
            teams[t["name"]] = cur
            continue
        teams[t["name"]] = om.put("/v1/teams", {
            "name": t["name"], "displayName": t["displayName"], "teamType": t["teamType"],
            "description": t["description"], "parents": [teams[t["parent"]]["id"]], "isJoinable": False})

    def team_refs(names):
        return [ref(teams[n], "team") for n in names if n in teams]

    def team_refs_full(names):  # custom-property values are rendered from the stored reference itself
        return [{"id": teams[n]["id"], "type": "team", "name": teams[n]["name"],
                 "fullyQualifiedName": teams[n].get("fullyQualifiedName", teams[n]["name"]),
                 "displayName": teams[n].get("displayName", teams[n]["name"])} for n in names if n in teams]

    # Custom properties
    step("custom properties: glossaryTerm.dataSteward/dataUser, dashboard.hakAksesLenO")
    ensure_custom_property(om, "glossaryTerm", "entityReferenceList", "dataSteward", "Data Steward",
                           "Semua unit kerja Data Steward (Workbook). Reviewer istilah = steward bisnis.", ["team"])
    ensure_custom_property(om, "glossaryTerm", "entityReferenceList", "dataUser", "Data User",
                           "Unit kerja pengguna data (Workbook: Data_Governance_Assignment).", ["team"])
    ensure_custom_property(om, "dashboard", "table-cp", "hakAksesLenO", "Hak Akses LenO",
                           "Hak akses layar di Aplikasi LenO (referensi, tidak ditegakkan di Len Data Governance).",
                           {"columns": ["Unit Kerja", "Kategori", "Izin"]})

    # Glossary terms
    step(f"glossary terms: {len(plan.terms)}")
    me = om.get("/v1/users/loggedInUser").get("name")   # identitas loader: istilah yang terakhir diubah orang lain (admin DG di aplikasi) tidak ditimpa
    app_edited: set[str] = set()   # istilah yang dicatat gold_meta_glossary sebagai "Aplikasi" (termasuk edit atas nama pemilik token loader)
    if not om.dry:
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "medallion"))
            import lakehouse as _L
            _t = _L.Trino()
            app_edited = {r[0] for r in _t.q(f"SELECT field_id FROM {_t.fq('gold_meta_glossary_app')} WHERE sumber_perubahan = 'Aplikasi'")}
        except Exception as e:  # noqa: BLE001 — tanpa Trino: hanya aturan updatedBy
            print(f"  ! daftar istilah hasil edit aplikasi tidak terbaca ({str(e)[:80]})")
    kept = 0
    for t in plan.terms:
        cur = om.find(f"/v1/glossaryTerms/name/{q(W.GLOSSARY + '.' + t['name'])}")
        if cur and (t["name"] in app_edited or cur.get("updatedBy") not in (None, me, "governance-bot")):
            kept += 1
            continue
        body = {"glossary": W.GLOSSARY, "name": t["name"], "displayName": t["displayName"],
                "description": t["description"],
                "reviewers": team_refs([t["reviewer"]] if t["reviewer"] else []),
                "owners": team_refs(t["owners"])}
        ext = {}
        if t["stewards"]:
            ext["dataSteward"] = team_refs_full(t["stewards"])
        if t["users"]:
            ext["dataUser"] = team_refs_full(t["users"])
        if ext:
            body["extension"] = ext
        om.put("/v1/glossaryTerms", body)
    if kept:
        step(f"glossary terms: {kept} istilah diubah admin di aplikasi → dipertahankan (tidak ditimpa Workbook)")

    # ERM tables → their Trino tables in lakekeeper.medallion_repository (metadata only; data comes from the lakehouse)
    step(f"ERM → Trino {W.LAKEHOUSE_SCHEMA_FQN}: {len(plan.tables)} tables")
    if not om.dry and any(om.find(f"/v1/tables/name/{q(W.LAKEHOUSE_SCHEMA_FQN + '.' + t['name'])}") is None
                          for t in plan.tables):
        import catalog_trino  # tables not catalogued yet → sync from Trino first
        catalog_trino.main()
    tables = {}
    for t in plan.tables:
        cur = om.get(f"/v1/tables/name/{q(W.LAKEHOUSE_SCHEMA_FQN + '.' + t['name'])}?fields=columns,tags,owners")
        wb_cols = {c["name"]: c for c in t["columns"]}
        cols = []
        for c in cur.get("columns", []):
            base = (c.get("description") or "").split(W.WORKBOOK_MARK)[0]
            col = {k: c[k] for k in ("name", "dataType", "dataTypeDisplay", "precision", "scale") if k in c}
            tags = [g for g in c.get("tags", []) if g.get("source") != "Glossary" and not g["tagFQN"].startswith(W.CLASSIFICATION + ".")]
            if c["name"] in wb_cols:
                w = wb_cols[c["name"]]
                col["description"] = base + W.WORKBOOK_MARK + "\n\n" + w["description"]
                tags += [{k: g[k] for k in ("tagFQN", "source", "labelType", "state")} for g in w["tags"]]
            elif base:
                col["description"] = base
            col["tags"] = [{k: g[k] for k in ("tagFQN", "source", "labelType", "state") if k in g} for g in tags]
            cols.append(col)
        missing = set(wb_cols) - {c["name"] for c in cols}
        if missing and not om.dry:
            plan.defects.append(("Kolom belum ada di Trino", f"{t['name']}: {sorted(missing)}"))
        body = {"name": t["name"], "databaseSchema": W.LAKEHOUSE_SCHEMA_FQN, "tableType": cur.get("tableType", "Iceberg"),
                "description": (cur.get("description") or "").split(W.WORKBOOK_MARK)[0] + W.WORKBOOK_MARK + "\n\n"
                               + t["description"],
                "columns": cols or t["columns"], "owners": team_refs(t["owners"])}
        tb = om.put("/v1/tables", body)
        # Column tags: PUT does not change tags of existing columns → JSON-patch the full tag list per column.
        ops = [{"op": "add", "path": f"/columns/{i}/tags", "value": c["tags"]}
               for i, c in enumerate(cols) if c["name"] in wb_cols]
        tables[t["name"]] = om.patch(f"/v1/tables/{tb['id']}", ops) if ops and not om.dry else tb

    # The old CustomDatabase service (LenO ERM, no data) is replaced by the Trino tables above.
    old = om.find(f"/v1/services/databaseServices/name/{q(W.LEGACY_DB_SERVICE)}")
    if old and not om.dry and old.get("serviceType") == "CustomDatabase":
        step(f"remove old database service {W.LEGACY_DB_SERVICE} (CustomDatabase) — moved to Trino")
        om.call("DELETE", f"/v1/services/databaseServices/{old['id']}?hardDelete=true&recursive=true")

    # Screens: data models + dashboards
    step(f"LenO screens: {len(plan.dashboards)} dashboards + data models")
    models = {}
    for m in plan.data_models:
        models[m["name"]] = om.put("/v1/dashboard/datamodels", {
            "name": m["name"], "displayName": m["displayName"], "description": m["description"],
            "service": W.SERVICE, "dataModelType": "SupersetDataModel", "columns": m["columns"]})
    dashboards = {}
    for d in plan.dashboards:
        body = {"name": d["name"], "displayName": d["displayName"], "description": d["description"],
                "service": W.SERVICE, "dataModels": [models[d["dataModel"]]["fullyQualifiedName"]]}
        if d["access_rows"]:
            body["extension"] = {"hakAksesLenO": {"columns": ["Unit Kerja", "Kategori", "Izin"],
                                                  "rows": d["access_rows"]}}
        dashboards[d["name"]] = om.put("/v1/dashboards", body)

    # Lineage: table → data model (column level) → dashboard
    step(f"lineage: {len(plan.lineage)} table→screen edges")
    for e in plan.lineage:
        t, m = tables[e["table"]], models[e["data_model"]]
        tcol = {c["name"]: c["fullyQualifiedName"] for c in t.get("columns", [])}
        mcol = {c["name"]: c["fullyQualifiedName"] for c in m.get("columns", [])}
        cl = [{"fromColumns": [tcol[s] for s in c["from"] if s in tcol], "toColumn": mcol[c["to"]]}
              for c in e["columns"] if c["to"] in mcol]
        om.put("/v1/lineage", {"edge": {
            "fromEntity": ref(t, "table"), "toEntity": ref(m, "dashboardDataModel"),
            "lineageDetails": {"description": "Workbook Data_Flow_Lineage", "columnsLineage": cl}}})
    for d in plan.dashboards:
        om.put("/v1/lineage", {"edge": {"fromEntity": ref(models[d["dataModel"]], "dashboardDataModel"),
                                        "toEntity": ref(dashboards[d["name"]], "dashboard")}})

    # Data quality: definitions only
    step(f"data quality test cases (definitions, not executed): {len(plan.tests)}")
    for tc in plan.tests:
        fqn = tables[tc["table"]]["fullyQualifiedName"]
        om.put("/v1/dataQuality/testCases", {
            "name": tc["name"], "description": tc["description"], "testDefinition": tc["testDefinition"],
            "entityLink": f"<#E::table::{fqn}::columns::{tc['column']}>",
            "parameterValues": tc["parameterValues"]})

    # DG-* → policy + role, default role of the team
    step(f"DG rights → policies/roles: {[p['team'] for p in plan.dg_policies]}")
    for p in plan.dg_policies:
        pol = om.put("/v1/policies", {"name": p["policy"], "displayName": f"Data Governance {p['team']}",
                                      "description": "Hak DG-* dari Workbook (Data_Security_Access): "
                                                     + ", ".join(p["rights"]), "rules": p["rules"]})
        role = om.put("/v1/roles", {"name": p["role"], "displayName": f"Data Governance {p['team']}",
                                    "description": "Peran tata kelola data dari Workbook.",
                                    "policies": [pol["fullyQualifiedName"]]})
        team = teams[p["team"]]
        om.patch(f"/v1/teams/{team['id']}", [{"op": "add", "path": "/defaultRoles",
                                              "value": [{"id": role["id"], "type": "role"}]}])

    write_report(plan, path, om)


def write_report(plan: W.Plan, path: str, om: Catalog):
    by_cat: dict[str, list[str]] = {}
    for cat, detail in plan.defects:
        by_cat.setdefault(cat, []).append(detail)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Laporan Cacat Workbook Governance", "",
             f"- Sumber: `{os.path.basename(path)}`", f"- Dibuat: {now} · mode: {'dry-run' if om.dry else 'dimuat'}",
             f"- Untuk tindak lanjut: UG-1 (Data Owner) / UV-1 (Data Governance)", "",
             "## Ringkasan muatan", "", "| Item | Jumlah |", "| :-- | --: |"]
    lines += [f"| {k} | {v} |" for k, v in sorted(plan.stats.items())]
    lines += ["", f"## Cacat ({len(plan.defects)})", ""]
    for cat, items in by_cat.items():
        lines += [f"### {cat} ({len(items)})", ""] + [f"- {i}" for i in items] + [""]
    os.makedirs(REPORT_DIR, exist_ok=True)
    out = os.path.join(REPORT_DIR, f"workbook-defects-{dt.date.today()}{'-dry' if om.dry else ''}.md")
    open(out, "w").write("\n".join(lines))
    print(f"\nreport: {out}\nwrites: {om.writes}\ndone{' (dry-run, nothing written)' if om.dry else ''}")


def inspect(path: str):
    for name, rows in W.read_xlsx(path).items():
        print(f"{name}  ({len(rows)} rows)\n    {list(rows[0]) if rows else []}")


if __name__ == "__main__":
    a = sys.argv[1:]
    dry = "--dry-run" in a
    a = [x for x in a if x != "--dry-run"]
    if a[:1] == ["foundation"]:
        om = Catalog(dry)
        foundation(om)
        print(f"writes: {om.writes}\ndone")
    elif a[:1] == ["workbook"] and len(a) == 2:
        load_workbook(Catalog(dry), a[1])
    elif a[:1] == ["inspect"] and len(a) == 2:
        inspect(a[1])
    else:
        sys.exit(__doc__)
