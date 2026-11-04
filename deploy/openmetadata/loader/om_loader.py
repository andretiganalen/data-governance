#!/usr/bin/env python3
"""Phase 3 loader for OpenMetadata (plan/openmetadata_deployment_plan.md §7). Stdlib only.

Idempotent: writes are PUT (create-or-update) or JSON-patch of fixed values — re-running never duplicates.

  om_loader.py foundation [--dry-run]              classification, services, glossary
  om_loader.py workbook <file.xlsx> [--dry-run]    everything from Workbook Governance (+ foundation)
  om_loader.py inspect <file.xlsx>                 sheets + headers

Auth: OM_TOKEN = Personal Access Token of an OpenMetadata *admin* (Profile › Access Token),
read from /srv/openmetadata/secrets/loader.env or the environment. Admin is required because the
workbook load creates teams, roles, policies and custom properties.
Defect report → /srv/openmetadata/reports/ (outside git: the repo is public).
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

OM_URL = os.environ.get("OM_URL", "http://127.0.0.1:8585/api")
SECRETS = os.environ.get("OM_LOADER_ENV", "/srv/openmetadata/secrets/loader.env")
REPORT_DIR = os.environ.get("OM_REPORT_DIR", "/srv/openmetadata/reports")

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
    tok = os.environ.get("OM_TOKEN")
    if not tok and os.path.exists(SECRETS):
        for line in open(SECRETS):
            if line.startswith("OM_TOKEN="):
                tok = line.split("=", 1)[1].strip().strip('"')
    if not tok:
        sys.exit(f"OM_TOKEN not set. Put OM_TOKEN=<admin personal access token> in {SECRETS} (chmod 600).")
    return tok


class OM:
    def __init__(self, dry: bool):
        self.dry = dry
        self.token = "dry" if dry else load_token()
        self.writes = 0

    def call(self, method: str, path: str, body=None, content_type="application/json"):
        req = urllib.request.Request(
            OM_URL + path, method=method,
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
def foundation(om: OM):
    step("foundation: classification Sensitivitas + 4 tags, services LenO ERM, glossary ERM")
    om.put("/v1/classifications", SENSITIVITY)
    for name, display, desc in SENSITIVITY_TAGS:
        om.put("/v1/tags", {"classification": W.CLASSIFICATION, "name": name, "displayName": display,
                            "description": desc})
    om.put("/v1/services/databaseServices", {
        "name": W.SERVICE, "displayName": "LenO ERM", "serviceType": "CustomDatabase",
        "description": "Representasi metadata database Aplikasi ERM LenO. Tanpa koneksi: OpenMetadata tidak "
                       "terhubung ke dan tidak mengubah database LenO."})
    om.put("/v1/services/dashboardServices", {
        "name": W.SERVICE, "displayName": "LenO ERM", "serviceType": "CustomDashboard",
        "description": "Layar Aplikasi ERM LenO (satu Dashboard per layar) untuk lineage kolom → layar. Tanpa koneksi."})
    om.put("/v1/glossaries", {
        "name": W.GLOSSARY, "displayName": "ERM", "mutuallyExclusive": False,
        "description": "Glosarium bisnis ERM: satu istilah per Elemen Data, dari Workbook Governance."})


# ------------------------------------------------------------------------------- workbook
def ensure_custom_property(om: OM, entity_type: str, prop_type: str, name: str, display: str,
                           desc: str, config):
    et = om.get(f"/v1/metadata/types/name/{entity_type}?fields=customProperties")
    pt = om.get(f"/v1/metadata/types/name/{prop_type}")
    body = {"name": name, "displayName": display, "description": desc,
            "propertyType": {"id": pt["id"], "type": "type"}, "customPropertyConfig": {"config": config}}
    om.put(f"/v1/metadata/types/{et['id']}", body)


def load_workbook(om: OM, path: str):
    plan = W.build(W.read_xlsx(path))
    step(f"workbook parsed: {dict(plan.stats)}; {len(plan.defects)} defects")
    foundation(om)

    # Teams
    step(f"teams: root → '{W.ROOT_DISPLAY}', {len(plan.teams)} teams")
    teams = {W.ROOT_TEAM: om.get(f"/v1/teams/name/{W.ROOT_TEAM}")}
    om.patch(f"/v1/teams/{teams[W.ROOT_TEAM]['id']}",
             [{"op": "add", "path": "/displayName", "value": W.ROOT_DISPLAY}])
    for t in plan.teams:
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
                           "Hak akses layar di Aplikasi LenO (referensi, tidak ditegakkan di OpenMetadata).",
                           {"columns": ["Unit Kerja", "Kategori", "Izin"]})

    # Glossary terms
    step(f"glossary terms: {len(plan.terms)}")
    for t in plan.terms:
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

    # Database, schema, tables
    step(f"database {W.SERVICE}.{W.DATABASE}.{W.SCHEMA}: {len(plan.tables)} tables")
    db = om.put("/v1/databases", {"name": W.DATABASE, "service": W.SERVICE, "displayName": "ERM",
                                  "description": "Aplikasi di LenO untuk mengelola risiko operasional Perusahaan (SYS001)."})
    schema = om.put("/v1/databaseSchemas", {"name": W.SCHEMA, "database": db["fullyQualifiedName"],
                                            "description": "Objek database Aplikasi ERM LenO (dari Database_Object)."})
    tables = {}
    for t in plan.tables:
        cols = [{k: v for k, v in c.items() if not k.startswith("_")} for c in t["columns"]]
        tables[t["name"]] = om.put("/v1/tables", {
            "name": t["name"], "databaseSchema": schema["fullyQualifiedName"], "tableType": "Regular",
            "description": t["description"], "columns": cols, "owners": team_refs(t["owners"])})

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


def write_report(plan: W.Plan, path: str, om: OM):
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
        om = OM(dry)
        foundation(om)
        print(f"writes: {om.writes}\ndone")
    elif a[:1] == ["workbook"] and len(a) == 2:
        load_workbook(OM(dry), a[1])
    elif a[:1] == ["inspect"] and len(a) == 2:
        inspect(a[1])
    else:
        sys.exit(__doc__)
