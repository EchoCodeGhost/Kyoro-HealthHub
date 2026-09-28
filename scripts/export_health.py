#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
export_health.py — Themenspezifische Gesundheitsdaten-Exporte

@tier        infrastructure
@purpose.de  Exportiert kuratierte Gesundheitsdaten-Pakete aus health.db und medicine.db
@purpose.en  Exports curated health data packages from health.db and medicine.db
@method.de   Exportiert Daten aus health.db und medicine.db als CSV oder JSON basierend auf
             Profil-Definitionen. Jede Profil-Query wird anhand ihrer FROM-Tabelle automatisch
             an die richtige Datenbank geroutet (lab_manual/lab_results/medications/assessments
             -> medicine.db, alles andere -> health.db; siehe MEDICINE_DB_TABLES).
             Profil-Definitionen liegen als JSON-Dateien unter scripts/exporters/profiles/.
             Unterstützt Filterung nach Datum, Person und Ausgabeformat.
@method.en   Exports data from health.db and medicine.db as CSV or JSON based on profile
             definitions. Each profile query is routed to the correct database by its FROM
             table (lab_manual/lab_results/medications/assessments -> medicine.db, everything
             else -> health.db; see MEDICINE_DB_TABLES).
             Profile definitions are stored as JSON files in scripts/exporters/profiles/.
             Supports filtering by date, person, and output format.
@reads       health.db, medicine.db, Profil-Definitionen aus scripts/exporters/profiles/
@writes      Exportierte CSV/JSON-Dateien in exports/-Verzeichnis
@limits.de   Datenauswahl basiert auf Profilen. Keine automatische Anonymisierung.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Data selection based on profiles. No automatic anonymisation.
@usage
    python export_health.py --profile cardiology --from 2026-01-01 --format csv
    python export_health.py --profile general_practitioner --last 365d --person self
    python export_health.py --profile research --person all --format json
    python export_health.py --list                  # alle verfügbaren Profile
"""

import argparse
import csv
import json
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, open_medicine_db, DB_OPERATIONAL_ERRORS
from modules.i18n import t, set_lang
_cfg = _Cfg()

DB_PATH      = _cfg.db_path
PROFILES_DIR = Path(__file__).parent / "exporters" / "profiles"
EXPORTS_DIR  = _cfg.data_root.parent / "exports"

# Tables that live in medicine.db (clinical values a doctor measures or
# orders), not health.db — see docs/ARCHITECTURE.md. Query routing below
# picks the connection by matching the queried table's FROM clause against
# this set, since a profile's query key (e.g. "infection_labs") often
# doesn't match the underlying table name (e.g. "lab_results").
MEDICINE_DB_TABLES = {"lab_manual", "lab_results", "medications", "assessments"}

_FROM_TABLE_RE = re.compile(r"\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


def query_targets_medicine_db(sql: str) -> bool:
    """True if sql's FROM table lives in medicine.db rather than health.db."""
    match = _FROM_TABLE_RE.search(sql)
    return bool(match) and match.group(1).lower() in MEDICINE_DB_TABLES


def load_profile(name: str) -> dict:
    """Load profile definition from profiles/<name>.json."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        # Check aliases
        for p in sorted(PROFILES_DIR.glob("*.json")):
            try:
                data = json.loads(p.read_text())
                if name in data.get("aliases", []):
                    return data
            except Exception:
                pass
        raise SystemExit(t(f"Profil '{name}' nicht gefunden in {PROFILES_DIR}",
                           f"Profile '{name}' not found in {PROFILES_DIR}"))
    return json.loads(path.read_text())


def list_profiles() -> None:
    if not PROFILES_DIR.exists():
        print(t(f"Profile-Verzeichnis nicht gefunden: {PROFILES_DIR}",
                f"Profile directory not found: {PROFILES_DIR}"))
        return
    print(t("\n── Verfügbare Export-Profile ─────────────────────────",
            "\n── Available export profiles ─────────────────────────"))
    for p in sorted(PROFILES_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            name = d.get("name", p.stem)
            desc_de = d.get("description", "")
            desc_en = d.get("description_en", desc_de)
            desc = t(desc_de, desc_en)
            aliases = d.get("aliases", [])
            alias_str = f" (alias: {', '.join(aliases)})" if aliases else ""
            print(f"  {name:<20}{alias_str}")
            if desc:
                print(f"    {desc}")
        except Exception as e:
            print(t(f"  {p.stem:<20} (Fehler beim Laden: {e})",
                    f"  {p.stem:<20} (load error: {e})"))


def parse_last(arg: str) -> str:
    """'365d', '90d', '12w', '6m', '1y' → ISO date (today - N)."""
    arg = arg.strip().lower()
    units = {'d': 1, 'w': 7, 'm': 30, 'y': 365}
    unit = arg[-1]
    if unit not in units:
        raise ValueError(t(f"Unbekannte Einheit: {arg}",
                           f"Unknown unit: {arg}"))
    days = int(arg[:-1]) * units[unit]
    return (date.today() - timedelta(days=days)).isoformat()


def run_query(conn: sqlite3.Connection, sql: str,
              person: str | None, date_from: str | None, date_to: str | None,
              counts: dict | None = None, table_name: str = "") -> list[dict]:
    """Führt SQL with Named Parameters aus. Person + Datumsfilter werden injiziert."""
    params = {}
    if ":person" in sql:
        params["person"] = person if person and person != "all" else "%"
    if ":date_from" in sql:
        params["date_from"] = date_from or "2000-01-01"
    if ":date_to" in sql:
        params["date_to"] = date_to or date.today().isoformat()

    # 'all' = all Personen — use regex to handle varying whitespace and
    # column names that merely contain "person" (e.g. "session_person",
    # "person_id"), not just the literal column "person". The "%" wildcard
    # fallback set above only works under LIKE, not "=" — under "=" it
    # would just match the literal string "%" and silently return 0 rows
    # for every query this substitution doesn't catch. Only drop the
    # bound :person value if the substitution actually removed the
    # placeholder from the SQL text.
    if person == "all":
        sql_eff = re.sub(r"\b\w*person\w*\s*=\s*:person\b", "1=1", sql)
        if ":person" not in sql_eff:
            params.pop("person", None)
    else:
        sql_eff = sql

    try:
        cur = conn.execute(sql_eff, params)
    except DB_OPERATIONAL_ERRORS as e:
        msg = t(f"    ⚠ SQL-Fehler in '{table_name}': {e}",
                f"    ⚠ SQL error in '{table_name}': {e}")
        print(msg, file=sys.stderr)
        if counts is not None:
            counts[table_name] = {"rows": 0, "error": str(e)}
        return []
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def export_profile(profile: dict, args, out_dir: Path) -> dict:
    conn = open_db()
    conn_medicine = open_medicine_db()

    counts: dict = {}
    errors = 0
    rows_by_query = {}

    for table_name, query_def in profile.get("queries", {}).items():
        if isinstance(query_def, str):
            sql = query_def
        else:
            sql = query_def.get("sql", "")

        query_conn = conn_medicine if query_targets_medicine_db(sql) else conn
        rows = run_query(query_conn, sql, args.person, args.date_from, args.date_to,
                         counts, table_name)
        if table_name not in counts:
            counts[table_name] = len(rows)
        if isinstance(counts[table_name], dict):
            errors += 1
        
        # Für FHIR-Export alle Zeilen sammeln
        if args.format == "fhir":
            rows_by_query[table_name] = rows
        
        # Für CSV/JSON direkt schreiben
        if args.format in ["csv", "json"] and rows:
            write_output(rows, out_dir, table_name, args.format)
            
        row_count = rows.__len__() if rows else 0
        print(f"  {table_name:<30} {row_count:>8,} {t('Zeilen', 'rows')}")

    # FHIR-Export verarbeiten
    if args.format == "fhir":
        write_fhir_output(rows_by_query, out_dir, args.person)

    if errors:
        print(t(f"\n  ⚠ {errors} Abfrage(n) mit SQL-Fehler — Daten fehlen im Export!",
                f"\n  ⚠ {errors} query/queries with SQL error — data missing from export!"),
              file=sys.stderr)

    conn.close()
    conn_medicine.close()
    return counts


# FHIR Export Imports
import json as json_lib
from typing import Dict, Set

# FHIR Export Functions
def write_fhir_output(rows_by_query: dict, out_dir: Path, patient_pseudo: str) -> None:
    """
    Erstellt FHIR Bundle mit Observations, Conditions und Patient-Ressource.
    
    Args:
        rows_by_query: Dictionary mit Abfrageergebnissen
        out_dir: Ausgabeverzeichnis
        patient_pseudo: Patienten-Pseudonym
    """
    # write_manifest() also mkdir's out_dir, but it only runs after
    # export_profile() returns — too late for a FHIR-only export, which
    # never went through write_output() (the csv/json path) either.
    out_dir.mkdir(parents=True, exist_ok=True)

    # Import FHIR Builder
    sys.path.insert(0, str(Path(__file__).parent / "exporters"))
    from fhir_resources import build_patient_resource, build_observation, build_condition, build_medication_statement
    from fhir_mapping import load_metric_code, track_unmapped, write_unmapped_report
    from fhir_validate import validate_bundle
    
    # Sammle alle Ressourcen
    resources = []
    unmapped_metrics = set()
    
    # 1. Patient-Ressource
    patient_resource = build_patient_resource(patient_pseudo)
    resources.append(patient_resource)
    
    # 2. Observation-Ressourcen aus Metrik-Daten
    for table_name, rows in rows_by_query.items():
        if not rows:
            continue
            
        # Nur Tabellen mit Metrik-Daten verarbeiten
        if "metric" in rows[0] and "wert_num" in rows[0]:
            for row in rows:
                metric_name = row.get("metric")
                if not metric_name:
                    continue
                    
                # LOINC-Mapping laden
                metric_code = load_metric_code(metric_name)
                
                if metric_code:
                    # Observation erstellen
                    observation = build_observation(row, metric_code, f"Patient/{patient_pseudo}")
                    if observation:
                        resources.append(observation)
                else:
                    # Nicht gemappte Metrik verfolgen
                    track_unmapped(metric_name, unmapped_metrics)
        
        # 3. Condition-Ressourcen aus klinischen Ereignissen
        if table_name == "clinical_events" and "type" in rows[0]:
            for event in rows:
                if event.get("type") == "diagnosis":
                    condition = build_condition(event, f"Patient/{patient_pseudo}")
                    resources.append(condition)
    
    # 4. FHIR Bundle erstellen
    bundle = {
        "resourceType": "Bundle",
        # FHIR id must match ^[A-Za-z0-9\-.]+$ — isoformat()'s colons (HH:MM:SS)
        # violate that, so every real export failed structural validation
        # regardless of fhir.resources version. strftime keeps microsecond-level
        # uniqueness without colons.
        "id": f"kyoro-export-{datetime.now().strftime('%Y%m%dT%H%M%S%f')}",
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry": []
    }
    
    for resource in resources:
        bundle["entry"].append({
            "fullUrl": f"urn:uuid:{resource.get('id', 'unknown')}",
            "resource": resource
        })
    
    # Strukturelle FHIR-Validierung vor dem Schreiben — bricht mit klarer
    # Fehlermeldung ab statt ein potenziell ungültiges Bundle zu schreiben.
    # Structural FHIR validation before writing — aborts with a clear error
    # message instead of writing a potentially invalid bundle.
    try:
        validate_bundle(bundle)
    except (ValueError, RuntimeError) as e:
        print(t(f"  ✗ FHIR-Bundle-Validierung fehlgeschlagen: {e}",
                 f"  ✗ FHIR bundle validation failed: {e}"), file=sys.stderr)
        sys.exit(1)

    # Bundle schreiben
    bundle_path = out_dir / f"fhir_bundle.json"
    bundle_path.write_text(json_lib.dumps(bundle, indent=2, ensure_ascii=False, default=str))
    print(f"  FHIR Bundle geschrieben: {bundle_path}")
    
    # Unmapped Metrics Report schreiben
    write_unmapped_report(unmapped_metrics, out_dir)

def write_output(rows: list[dict], out_dir: Path, name: str, fmt: str, patient_pseudo: str = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        path = out_dir / f"{name}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    elif fmt == "json":
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
    elif fmt == "fhir":
        # FHIR Export wird separat verarbeitet
        pass  # FHIR wird in export_profile verarbeitet


def write_manifest(out_dir: Path, profile: dict, args, counts: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "profile": profile.get("name"),
        "description": profile.get("description"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "person": args.person,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "format": args.format,
        "lang": args.lang,
        "tables": counts,
        "total_rows": sum(v for v in counts.values() if isinstance(v, int)),
    }
    (out_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False))


def main():
    # First pass: detect --lang to apply it before showing localized help.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", choices=["de", "en"], default="de")
    pre_args, _ = pre.parse_known_args()
    set_lang(pre_args.lang)

    parser = argparse.ArgumentParser(
        description=t("Themenspezifische Datenpakete exportieren",
                      "Export themed data packages")
    )
    parser.add_argument("--profile",   help=t("Profilname (z.B. cardiology)",
                                              "Profile name (e.g. cardiology)"))
    parser.add_argument("--list",      action="store_true",
                        help=t("Verfügbare Profile auflisten",
                               "List available profiles"))
    parser.add_argument("--from",      dest="date_from", metavar="DATE")
    parser.add_argument("--to",        dest="date_to",   metavar="DATE")
    parser.add_argument("--last",      metavar="N[d|w|m|y]",
                        help=t("z.B. 365d, 12w, 6m",
                               "e.g. 365d, 12w, 6m"))
    parser.add_argument("--person",    default=OWN_PERSON_ID,
                        help=t("Person-ID, partner, all (Standard: OWN_PERSON_ID)",
                               "Person ID, partner, all (default: OWN_PERSON_ID)"))
    parser.add_argument("--format",    choices=["csv", "json", "fhir"], default="csv")
    parser.add_argument("--lang",      choices=["de", "en"], default="de",
                        help=t("Ausgabesprache", "Output language"))
    parser.add_argument("--out",       metavar="DIR",
                        help=t("Ausgabeverzeichnis (Standard: <Daten>/exports/<Profil>_<Datum>)",
                               "Output directory (default: <data>/exports/<profile>_<date>)"))
    args = parser.parse_args()
    set_lang(args.lang)

    if args.list:
        list_profiles()
        return

    if not args.profile:
        parser.error(t("--profile erforderlich (oder --list)",
                       "--profile required (or --list)"))

    if args.last:
        args.date_from = parse_last(args.last)

    profile = load_profile(args.profile)
    profile_name = profile.get("name", args.profile)

    out_dir = Path(args.out) if args.out else (
        EXPORTS_DIR / f"{profile_name}_{date.today().isoformat()}"
    )
    print(t(f"\nExportiere Profil: {profile_name}",
            f"\nExporting profile: {profile_name}"))
    print(t(f"Person:    {args.person}",
            f"Person:     {args.person}"))
    print(t(f"Zeitraum:  {args.date_from or '—'} → {args.date_to or 'heute'}",
            f"Date range: {args.date_from or '—'} → {args.date_to or 'today'}"))
    print(t(f"Format:    {args.format}",
            f"Format:     {args.format}"))
    print(t(f"Ziel:      {out_dir}\n",
            f"Output:     {out_dir}\n"))

    counts = export_profile(profile, args, out_dir)
    write_manifest(out_dir, profile, args, counts)

    total_rows = sum(v for v in counts.values() if isinstance(v, int))
    print(t(f"\nGesamt: {total_rows:,} Zeilen in {len(counts)} Dateien",
            f"\nTotal: {total_rows:,} rows in {len(counts)} files"))
    print(t(f"Manifest: {out_dir}/_manifest.json",
            f"Manifest: {out_dir}/_manifest.json"))


if __name__ == "__main__":
    main()
