"""Workbook Governance (Rev.0.1) → OpenMetadata, per plan §7.

Pure functions: read the .xlsx (stdlib), validate, and build OpenMetadata payloads.
No network here — om_loader.py does the writes.
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

SERVICE = "LenO_ERM"
DATABASE = "ERM"
SCHEMA = "erm"
GLOSSARY = "ERM"
CLASSIFICATION = "Sensitivitas"
ROOT_TEAM = "Organization"          # OpenMetadata's root team == "Seluruh Unit Kerja"
ROOT_DISPLAY = "Seluruh Unit Kerja"

# Workbook classification → tag name in classification "Sensitivitas"
SENSITIVITY_RANK = {"Public": 0, "Restricted": 1, "Confidential": 2, "Strictly Confidential": 3}
SENSITIVITY_TAG = {
    "Public": "Public",
    "Restricted": "Restricted",
    "Confidential": "Confidential",
    "Strictly Confidential": "StrictlyConfidential",
}

# Workbook DATA_TYPE (sheet Library) → OpenMetadata column dataType
DATA_TYPE = {
    "Text/String": "STRING",
    "Integer": "INT",
    "Float/Decimal/Double": "DECIMAL",
    "Boolean": "BOOLEAN",
    "Date": "DATE",
    "Time": "TIME",
    "Datetime/Timestamp": "TIMESTAMP",
    "Currency": "DECIMAL",
    "Percentage": "DECIMAL",
    "Binary/BLOB": "BLOB",
    "Enum": "ENUM",
}

# DG-* rights (ADR 0001: enforced as OpenMetadata policy). LenO screen rights stay reference metadata.
DG_OPERATIONS = {
    "DG-Assign Owner": [("all", ["EditOwners"])],
    "DG-Assign Steward": [("glossary", ["EditReviewers"]), ("glossaryTerm", ["EditReviewers"])],
    "DG-Assign User": [("glossaryTerm", ["EditCustomFields"])],
    "DG-Edit Glossary": [("glossary", ["Create", "EditAll"]), ("glossaryTerm", ["Create", "EditAll"])],
    "DG-Edit DQ Rule": [("table", ["CreateTests", "EditTests"]), ("testCase", ["Create", "EditAll"])],
    "DG-Edit Lineage": [("all", ["EditLineage"])],
    "DG-Classify Data": [("all", ["EditTags"])],
}

# Workbook VALIDATION → OpenMetadata test definition (definition only, not executed)
def dq_test(validation: str):
    v = validation.strip()
    if v == "Not Null":
        return "columnValuesToBeNotNull", []
    if v == "True/False":
        return "columnValuesToBeInSet", [{"name": "allowedValues", "value": '["true","false"]'}]
    if v == "≥ 0":
        return "columnValuesToBeBetween", [{"name": "minValue", "value": "0"}]
    if v == "1-5":
        return "columnValuesToBeBetween", [{"name": "minValue", "value": "1"}, {"name": "maxValue", "value": "5"}]
    if v == "0% ≤ Nilai ≤ 100%":
        return "columnValuesToBeBetween", [{"name": "minValue", "value": "0"}, {"name": "maxValue", "value": "100"}]
    return None  # Lookup, Currency, cross validation, … → described on the column, reported


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


# ---------------------------------------------------------------- xlsx reading (stdlib)
def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path: str) -> dict[str, list[dict[str, str]]]:
    """Return {sheet: [row dict keyed by header]}; empty rows dropped, values stripped."""
    out: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", NS):
            target = rels[sh.get(REL_ID)].lstrip("/")
            target = target if target.startswith("xl/") else "xl/" + target
            grid = []
            for r in ET.fromstring(z.read(target)).findall(".//m:sheetData/m:row", NS):
                vals = {}
                for c in r.findall("m:c", NS):
                    v, inline = c.find("m:v", NS), c.find("m:is", NS)
                    if c.get("t") == "s" and v is not None:
                        val = shared[int(v.text)]
                    elif c.get("t") == "inlineStr" and inline is not None:
                        val = "".join(t.text or "" for t in inline.iter(f"{{{NS['m']}}}t"))
                    else:
                        val = v.text if v is not None and v.text else ""
                    vals[_col_index(c.get("r"))] = val.strip()
                if vals:
                    grid.append([vals.get(i, "") for i in range(max(vals) + 1)])
            if not grid:
                out[sh.get("name")] = []
                continue
            header = grid[0]
            rows = []
            for g in grid[1:]:
                g = g + [""] * (len(header) - len(g))
                if any(g):
                    # duplicate header names (sheet Library) keep the first occurrence
                    row: dict[str, str] = {}
                    for h, x in zip(header, g):
                        row.setdefault(h, x)
                    rows.append(row)
            out[sh.get("name")] = rows
    return out


# ---------------------------------------------------------------- model
@dataclass
class Plan:
    teams: list[dict] = field(default_factory=list)          # ordered parents-first
    terms: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    data_models: list[dict] = field(default_factory=list)
    dashboards: list[dict] = field(default_factory=list)
    lineage: list[dict] = field(default_factory=list)        # symbolic, resolved at load time
    tests: list[dict] = field(default_factory=list)
    dg_policies: list[dict] = field(default_factory=list)
    defects: list[tuple[str, str]] = field(default_factory=list)  # (category, detail)
    stats: Counter = field(default_factory=Counter)


def build(wb: dict[str, list[dict[str, str]]]) -> Plan:
    p = Plan()
    org = wb["Master_Organization"]
    org_by_id = {o["ORG_ID"]: o for o in org}

    def team_name(org_id: str) -> str:
        return ROOT_TEAM if org_id.lower() == "all" else org_id

    # --- Teams: Direktorat (BusinessUnit) › Divisi (Division) › Unit Kerja (Group: only Groups may own assets)
    seen = set()
    for o in org:
        d = "DIR_" + slug(o["DIREKTORAT"])
        v = "DIV_" + slug(o["DIVISI"])
        if d not in seen:
            seen.add(d)
            p.teams.append({"name": d, "displayName": f"Direktorat {o['DIREKTORAT']}",
                            "teamType": "BusinessUnit", "parent": ROOT_TEAM,
                            "description": "Direktorat (dari Master_Organization)."})
        if v not in seen:
            seen.add(v)
            p.teams.append({"name": v, "displayName": f"Divisi {o['DIVISI']}",
                            "teamType": "Division", "parent": d,
                            "description": f"Divisi di Direktorat {o['DIREKTORAT']}."})
        p.teams.append({"name": o["ORG_ID"], "displayName": f"{o['ORG_ID']} {o['UNIT_KERJA']}",
                        "teamType": "Group", "parent": v,
                        "description": f"Unit Kerja {o['UNIT_KERJA']} · {o['FUNGSI']} · "
                                       f"Divisi {o['DIVISI']} · Direktorat {o['DIREKTORAT']}."})
    p.stats["teams"] = len(p.teams)

    # --- Indexes
    tables = {t["TABLE_ID"]: t for t in wb["Database_Object"]}
    datasets = {d["DATASET_ID"]: d for d in wb["Business_Dataset"]}
    glossary = {g["FIELD_ID"]: g for g in wb["Business_Glossary"]}
    fields = wb["Data_Element_Attribute"]
    field_ids = {f["FIELD_ID"] for f in fields}

    assign = defaultdict(lambda: defaultdict(set))  # field → role → {org}
    for a in wb["Data_Governance_Assignment"]:
        if a["ORG_ID"].lower() != "all" and a["ORG_ID"] not in org_by_id:
            p.defects.append(("ORG_ID tidak dikenal", f"{a['FIELD_ID']} {a['ROLE']}: {a['ORG_ID']}"))
            continue
        assign[a["FIELD_ID"]][a["ROLE"]].add(team_name(a["ORG_ID"]))

    rules = defaultdict(list)
    for r in wb["Data_Quality_Rules"]:
        rules[r["FIELD_ID"]].append(r)

    access = wb["Data_Security_Access"]
    classes = defaultdict(set)
    for s in access:
        if s["CLASSIFICATION"]:
            classes[s["FIELD_ID"]].add(s["CLASSIFICATION"])

    def strictest(fid: str):
        cs = classes.get(fid)
        if not cs:
            return None
        if len(cs) > 1:
            p.defects.append(("Konflik klasifikasi", f"{fid}: {sorted(cs)} → dipakai yang terketat"))
        return max(cs, key=lambda c: SENSITIVITY_RANK.get(c, -1))

    # --- Glossary terms: one per Elemen Data (FIELD_ID)
    for fid in sorted(field_ids):
        g = glossary.get(fid)
        if not g:
            p.defects.append(("Glosarium kosong", f"{fid}: tidak ada di Business_Glossary"))
            continue
        a = assign.get(fid, {})
        stewards = sorted(a.get("Data Steward", ()))
        owners = sorted(a.get("Data Owner", ()))
        # OpenMetadata allows ONE reviewer team per term: prefer the business steward (also Data Owner).
        # All stewards are kept in the custom property "Data Steward".
        reviewer = next((s for s in stewards if s in owners), stewards[0] if stewards else None)
        p.terms.append({
            "name": fid,
            "displayName": g["BUSINESS_TERM"],
            "description": g["DEFINISI"] or f"(definisi belum diisi) — {g['BUSINESS_TERM']}",
            "reviewer": reviewer,
            "stewards": stewards,
            "owners": owners,
            "users": sorted(a.get("Data User", ())),
        })
        if not g["DEFINISI"]:
            p.defects.append(("Glosarium kosong", f"{fid}: definisi kosong"))
    for fid in sorted(set(glossary) - field_ids):
        p.defects.append(("Glosarium tanpa Elemen Data", fid))
    p.stats["glossary_terms"] = len(p.terms)
    term_ids = {t["name"] for t in p.terms}

    # --- Tables + columns
    cols_by_table = defaultdict(list)
    for f in fields:
        if f["TABLE_ID"] not in tables:
            p.defects.append(("Tabel Not Found", f"{f['FIELD_ID']} ({f['COLUMN_NAME']}) → {f['TABLE_ID']} "
                                                 f"'{f['TABLE_NAME']}' tidak ada di Database_Object"))
            continue
        cols_by_table[f["TABLE_ID"]].append(f)

    sensitivity_used = Counter()
    for tid, t in sorted(tables.items()):
        ds = datasets.get(t["DATASET_ID"], {})
        cols, names, owners = [], {}, set()
        for f in cols_by_table.get(tid, []):
            key = f["COLUMN_NAME"].lower()
            if key in names:
                p.defects.append(("Kolom kembar", f"{t['TABLE_NAME']}.{f['COLUMN_NAME']}: "
                                                  f"{names[key]} dan {f['FIELD_ID']} — hanya yang pertama dimuat"))
                continue
            names[key] = f["FIELD_ID"]
            fid = f["FIELD_ID"]
            if f["DATA_TYPE"] not in DATA_TYPE:
                p.defects.append(("Tipe data tidak dikenal", f"{fid} {f['COLUMN_NAME']}: '{f['DATA_TYPE']}'"))
            tags = []
            cls = strictest(fid)
            if cls:
                tags.append({"tagFQN": f"{CLASSIFICATION}.{SENSITIVITY_TAG[cls]}", "source": "Classification",
                             "labelType": "Manual", "state": "Confirmed"})
                sensitivity_used[cls] += 1
            else:
                p.defects.append(("Tanpa klasifikasi", f"{fid}: tidak ada di Data_Security_Access"))
            if fid in term_ids:
                tags.append({"tagFQN": f"{GLOSSARY}.{fid}", "source": "Glossary",
                             "labelType": "Manual", "state": "Confirmed"})
            desc = [f"**Elemen Data:** {fid} · {f['BUSINESS_TERM']}"]
            if fid in glossary and glossary[fid]["DEFINISI"]:
                desc.append(glossary[fid]["DEFINISI"])
            if rules.get(fid):
                desc.append("**Aturan kualitas:** " + "; ".join(f"{r['RULE']} ({r['VALIDATION']})" for r in rules[fid]))
            a = assign.get(fid, {})
            for role in ("Data Owner", "Data Steward", "Data User"):
                if a.get(role):
                    desc.append(f"**{role}:** {', '.join(sorted(a[role]))}")
            owners |= a.get("Data Owner", set())
            cols.append({"name": f["COLUMN_NAME"], "dataType": DATA_TYPE.get(f["DATA_TYPE"], "UNKNOWN"),
                         "dataTypeDisplay": f["DATA_TYPE"], "description": "\n\n".join(desc), "tags": tags,
                         "_field": fid})
            for r in rules.get(fid, []):
                td = dq_test(r["VALIDATION"])
                if td:
                    p.tests.append({"table": t["TABLE_NAME"], "column": f["COLUMN_NAME"],
                                    "name": f"{fid}_{slug(r['VALIDATION']) or 'rule'}_{slug(t['TABLE_NAME'])}",
                                    "testDefinition": td[0], "parameterValues": td[1],
                                    "description": f"{r['RULE']} — {r['VALIDATION']} (Workbook, tidak dijalankan)"})
                else:
                    p.stats["dq_rules_description_only"] += 1
        if not cols:
            p.defects.append(("Tabel tanpa kolom", t["TABLE_NAME"]))
        p.tables.append({
            "name": t["TABLE_NAME"],
            "description": f"**Dataset:** {ds.get('BUSINESS_DATASET', t['DATASET_NAME'])} ({t['DATASET_ID']}) · "
                           f"**Domain:** {ds.get('BUSINESS_DOMAIN', '-')} · **Objek:** {t['OBJECT_TYPE']} · "
                           f"**ID:** {tid}",
            "columns": cols,
            "owners": sorted(owners),
        })
    p.stats["tables"] = len(p.tables)
    p.stats["columns"] = sum(len(t["columns"]) for t in p.tables)
    p.stats["dq_test_cases"] = len(p.tests)
    p.stats.update({f"sensitivity_{k}": v for k, v in sensitivity_used.items()})

    # --- LenO screens: Dashboard + Data Model (columns = screen fields), lineage column → screen
    screens = defaultdict(list)
    for l in wb["Data_Flow_Lineage"]:
        screens[l["TARGET_ASSET"]].append(l)
    table_names = {t["TABLE_ID"]: t["TABLE_NAME"] for t in wb["Database_Object"]}
    perms = defaultdict(lambda: defaultdict(set))   # screen → (org, category) → {permission}
    for s in access:
        perms[s["TARGET_ASSET"]][(s["ORG_ID"], s["PERMISSION_CATEGORY"])].add(s["PERMISSION_TYPE"])
    loaded_cols = {(t["name"], c["name"]) for t in p.tables for c in t["columns"]}

    for screen, items in sorted(screens.items()):
        sname = "SCR_" + slug(screen)
        mcols, seen_labels, edges = [], set(), defaultdict(lambda: defaultdict(list))
        for l in items:
            label = slug(l["TARGET_LABEL"]) or slug(l["FIELD_NAME"])
            if label not in seen_labels:
                seen_labels.add(label)
                mcols.append({"name": label, "displayName": l["TARGET_LABEL"], "dataType": "STRING",
                              "description": f"Field layar '{l['TARGET_LABEL']}' · Elemen Data {l['FIELD_ID']} · "
                                             f"{l['LINEAGE_ID']}"})
            tname = table_names.get(l["TABLE_ID"], l["TABLE_NAME"])
            if (tname, l["FIELD_NAME"]) in loaded_cols:
                edges[tname][label].append(l["FIELD_NAME"])
            else:
                p.defects.append(("Lineage tanpa kolom", f"{l['LINEAGE_ID']}: {tname}.{l['FIELD_NAME']} → {screen}"))
        rows = []
        for (org_id, cat), types in sorted(perms.get(screen, {}).items()):
            unit = ROOT_DISPLAY if org_id.lower() == "all" else (
                f"{org_id} {org_by_id[org_id]['UNIT_KERJA']}" if org_id in org_by_id else org_id)
            rows.append({"Unit Kerja": unit, "Kategori": cat, "Izin": ", ".join(sorted(types))})
        p.data_models.append({"name": sname, "displayName": f"Model layar: {screen}", "columns": mcols,
                              "description": f"Field yang tampil di layar LenO ERM '{screen}'."})
        p.dashboards.append({"name": sname, "displayName": screen, "dataModel": sname, "access_rows": rows,
                             "description": f"Layar Aplikasi ERM LenO: **{screen}** ({items[0]['ASSET_TYPE']}). "
                                            f"Hak akses LenO pada properti *Hak Akses LenO* (referensi)."})
        for tname, m in edges.items():
            p.lineage.append({"table": tname, "data_model": sname,
                              "columns": [{"from": sorted(set(src)), "to": lbl} for lbl, src in m.items()]})
    p.stats["dashboards"] = len(p.dashboards)
    p.stats["lineage_edges"] = len(p.lineage)

    # --- DG-* rights → policy + role per Unit Kerja
    dg = defaultdict(set)
    for s in access:
        if s["PERMISSION_CATEGORY"] == "Data Governance":
            dg[s["ORG_ID"]].add(s["PERMISSION_TYPE"])
    for org_id, rights in sorted(dg.items()):
        rules_ = []
        for right in sorted(rights):
            if right not in DG_OPERATIONS:
                p.defects.append(("Hak DG tidak dipetakan", f"{org_id}: {right}"))
                continue
            for res, ops in DG_OPERATIONS[right]:
                rules_.append({"name": slug(f"{right}-{res}"), "description": f"{right} (Workbook)",
                               "effect": "allow", "resources": [res], "operations": ops})
        rules_.append({"name": "ViewAll", "description": "Lihat semua metadata", "effect": "allow",
                       "resources": ["all"], "operations": ["ViewAll"]})
        p.dg_policies.append({"team": team_name(org_id), "rights": sorted(rights),
                              "policy": f"DG_{slug(org_id)}", "role": f"DataGovernance_{slug(org_id)}",
                              "rules": rules_})
    p.stats["dg_roles"] = len(p.dg_policies)

    # de-duplicate defects, keep order
    p.defects = list(dict.fromkeys(p.defects))
    return p
