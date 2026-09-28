#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
export_research_cohort.py — research cohort export with anonymization

@tier        infrastructure
@purpose.de  Exportiert anonymisierte Forschungs-Kohorten aus mehreren
             Patient:innen-Instanzen. Prüft Einwilligungen, wendet Datumsverschiebung
             und Altersbänderung an, und filtert kleine Gruppen per k-Anonymität.
             Ohne gültige Einwilligung für ALLE aktiven Patient:innen wird KEINE
             Ausgabe geschrieben (Abbruch vor jeglichem Schreiben).
@purpose.en  Exports anonymized research cohorts from multiple patient instances.
             Checks consents, applies date shifting and age banding, and filters
             small groups via k-anonymity. Without valid consent for ALL active
             patients, NO output is written (abort before any writing).
@method.de   1. Liest patient_number_map aus master.db
             2. Prüft research_consent für jeden Scope
             3. Bricht ab, falls irgendeine aktive Instanz keine Einwilligung hat
             4. Aktiviert jede Instanz nacheinander, führt Profil-Export durch
             5. Wendet Datumsverschiebung pro Patient an
             6. Wendet Altersbänderung an
             7. Prüft k-Anonymität auf Quasi-Identifikatoren
             8. Schreibt behaltene Daten + Manifest, unterdrückte Daten separat
@method.en   1. Reads patient_number_map from master.db
             2. Checks research_consent for each scope
             3. Aborts if any active instance lacks consent
             4. Activates each instance sequentially, runs profile export
             5. Applies per-patient date shifting
             6. Applies age banding
             7. Checks k-anonymity on quasi-identifiers
             8. Writes kept data + manifest, suppressed data separately
@reads       ~/.config/kyoro-master/master.db, patient instance health.db files
@writes      KYORO_MASTER_DIR/research_exports/<date>/...
@limits.de   Datumsverschiebung entfernt zeitliche Alignment zwischen Patient:innen.
             k-Anonymität prüft nur explizit angegebene Quasi-Identifikatoren.
             Keine automatische Erkennung von Identifikatoren.

@relevance.de  Ermöglicht den Export von Gesundheitsdaten, essentiell für die Datenweitergabe und Interoperabilität
@relevance.en  Enables export of health data, essential for data sharing and interoperability
@limits.en   Date shifting removes temporal alignment between patients.
             k-anonymity only checks explicitly provided quasi-identifiers.
             No automatic detection of identifiers.
@usage
    python3 scripts/exporters/export_research_cohort.py \
        --scope study-2026-hrv-cohort-a \
        --profile research \
        --quasi-identifiers age_band,timezone \
        --k 5 --age-band-width 5 \
        --date-from 2020-01-01 --date-to 2026-12-31
    python3 scripts/exporters/export_research_cohort.py --help
"""
import argparse
import csv
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import KYORO_MASTER_DIR
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from utils.deidentify_cohort import (
    date_shift_offset_days,
    shift_date,
    age_band,
    check_k_anonymity,
    looks_like_date_value,
)

_MASTER_DB = KYORO_MASTER_DIR / "master.db"


def _is_date_column(col_name: str) -> bool:
    """Namensbasierte Heuristik zur Erkennung von Datums-Spalten.

    Zusätzlich zur Namenserkennung prüft _apply_deidentification() jeden
    Wert selbst per deidentify_cohort.looks_like_date_value() -- eine
    Spalte, deren Name hier nicht erkannt wird (z.B. ein zukünftig
    hinzugefügtes Profil-Feld), wird trotzdem verschoben, wenn ihr Wert
    wie ein ISO-Datum aussieht. Das ist bewusst redundant: ein reales
    Kalenderdatum, das unverschoben bleibt, ermöglicht die Rekonstruktion
    des Patient-Offsets über andere, korrekt verschobene Spalten hinweg.
    """
    col_lower = col_name.lower()
    date_suffixes = ("_at", "_date", "_start", "_end", "_from", "_to", "_dt")
    date_names = {"ts", "datetime", "date", "timestamp", "day"}
    return col_lower.endswith(date_suffixes) or col_lower in date_names


def _load_patient_instances():
    """Lädt alle aktiven Patient:innen-Instanzen aus master.db."""
    con = sqlite3.connect(_MASTER_DB)
    rows = con.execute(
        "SELECT patient_pseudo, instance_dir FROM patient_number_map "
        "WHERE active = 1 ORDER BY patient_pseudo"
    ).fetchall()
    con.close()
    return rows


def _check_consent(patient_pseudo: str, scope: str) -> bool:
    """Prüft, ob Patient:in für den Scope eingewilligt hat (nicht widerrufen)."""
    con = sqlite3.connect(_MASTER_DB)
    row = con.execute(
        "SELECT 1 FROM research_consent WHERE patient_pseudo=? AND consent_scope=? AND revoked_at IS NULL",
        (patient_pseudo, scope),
    ).fetchone()
    con.close()
    return row is not None


def _load_profile(profile_name: str) -> dict:
    """Lädt Export-Profil-Definition."""
    profiles_dir = Path(__file__).parent / "profiles"
    profile_path = profiles_dir / f"{profile_name}.json"
    
    if not profile_path.exists():
        # Aliase prüfen
        for p in sorted(profiles_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text())
                if profile_name in data.get("aliases", []):
                    return data
            except Exception:
                pass
        raise SystemExit(t(f"Profil '{profile_name}' nicht gefunden in {profiles_dir}",
                           f"Profile '{profile_name}' not found in {profiles_dir}"))
    
    return json.loads(profile_path.read_text())


class InstanceExportError(RuntimeError):
    """Wird ausgelöst, wenn der Export-Subprozess für eine Instanz fehlschlägt.

    Bewusst nicht abgefangen-und-mit-{}-fortgesetzt: eine unvollständige
    Kohorte (manche konsentierten Patient:innen fehlen im Export) ist
    genauso ein Integritätsproblem wie eine fehlende Einwilligung -- beide
    führen zum Abbruch vor jeglichem Schreiben, statt still einen Teil der
    Kohorte auszulassen und trotzdem "✅ Fertig" zu melden.
    """


_WORKER_SCRIPT = Path(__file__).parent / "_export_instance_worker.py"


def _run_instance_export(instance_dir: Path, profile_name: str, args) -> dict[str, list[dict]]:
    """Führt Export für eine einzelne Instanz durch.

    Läuft als eigener Subprozess mit KYORO_ACTIVE_PATIENT_DIR in dessen
    Umgebung, statt die Variable im laufenden Prozess mehrfach umzusetzen:
    scripts/health_config.py berechnet KYORO_CONFIG_DIR als Modul-Konstante
    beim ersten Import (sys.modules-Caching) — ein erneutes Umsetzen der
    Env-Var im selben Prozess hat auf ein bereits importiertes
    health_config-Modul keine Wirkung mehr. Siehe Docstring von
    _export_instance_worker.py und docs/CLINIC_DEPLOYMENT.md
    ("Nebenläufigkeit verstehen").
    """
    env = {**os.environ, "KYORO_ACTIVE_PATIENT_DIR": str(instance_dir)}
    cmd = [sys.executable, str(_WORKER_SCRIPT),
           "--profile", profile_name,
           "--person", args.person or "all"]
    if args.date_from:
        cmd += ["--date-from", args.date_from]
    if args.date_to:
        cmd += ["--date-to", args.date_to]

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise InstanceExportError(
            t(f"Export-Subprozess für Instanz {instance_dir} fehlgeschlagen (exit {result.returncode}): "
              f"{result.stderr.strip()}",
              f"Export subprocess for instance {instance_dir} failed (exit {result.returncode}): "
              f"{result.stderr.strip()}")
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise InstanceExportError(
            t(f"Export-Subprozess für Instanz {instance_dir} lieferte kein gültiges JSON zurück: {e}",
              f"Export subprocess for instance {instance_dir} did not return valid JSON: {e}")
        ) from e


def _apply_deidentification(data: dict[str, list[dict]], patient_pseudo: str, args) -> dict[str, list[dict]]:
    """Wendet Anonymisierung auf die Export-Daten an."""
    deidentified = {}
    
    for table_name, rows in data.items():
        processed_rows = []
        
        for row in rows:
            new_row = row.copy()
            
            # Datumsverschiebung -- Name ODER Wert muss wie ein Datum
            # aussehen (siehe _is_date_column-Docstring: Verteidigung
            # gegen unerwartete Spaltennamen, die ein echtes Datum
            # unverschoben durchlassen würden)
            offset = date_shift_offset_days(patient_pseudo)
            for col, value in row.items():
                if value and (_is_date_column(col) or looks_like_date_value(value)):
                    try:
                        new_row[col] = shift_date(value, offset)
                    except (ValueError, TypeError):
                        pass
            
            # Altersbänderung (falls Geburtsdatum vorhanden)
            if "birthdate" in row and row["birthdate"]:
                new_row["age_band"] = age_band(row["birthdate"], args.reference_date, args.age_band_width)
                # Geburtsdatum entfernen, da wir Altersband haben
                new_row.pop("birthdate", None)
            
            # Patient-Pseudonym hinzufügen
            new_row["patient_pseudo"] = patient_pseudo
            
            processed_rows.append(new_row)
        
        deidentified[table_name] = processed_rows
    
    return deidentified


def _merge_and_check_k_anonymity(all_data: dict[str, list[dict]], args) -> dict[str, tuple[list[dict], list[dict], dict, list[str]]]:
    """Führt k-Anonymitätsprüfung durch und trennt behaltene/unterdrückte Daten."""
    results = {}
    qids = [qid.strip() for qid in args.quasi_identifiers.split(",")]

    for table_name, rows in all_data.items():
        if not rows:
            results[table_name] = ([], [], {}, [])
            continue

        # k-Anonymität prüfen
        kept, suppressed, hist, missing_qis = check_k_anonymity(rows, qids, args.k)

        if missing_qis:
            # Keine der angeforderten Quasi-Identifikator-Spalten existiert in
            # dieser Tabelle -- die Prüfung wäre wirkungslos (jede Zeile
            # bekäme denselben Platzhalter-Schlüssel und "bestünde" trivial).
            # Laut sichtbar melden statt still als "geprüft" auszugeben.
            print(t(f"  ⚠ {table_name}: Quasi-Identifikator(en) {missing_qis} in keiner Zeile vorhanden — "
                    f"k-Anonymität für diese Tabelle NICHT wirksam geprüft",
                    f"  ⚠ {table_name}: quasi-identifier(s) {missing_qis} absent from every row — "
                    f"k-anonymity NOT effectively enforced for this table"),
                  file=sys.stderr)

        results[table_name] = (kept, suppressed, hist, missing_qis)

    return results


def _write_output(base_dir: Path, table_name: str, rows: list[dict], format: str) -> None:
    """Schreibt Daten in CSV oder JSON Format."""
    if not rows:
        return
    
    base_dir.mkdir(parents=True, exist_ok=True)
    
    if format == "csv":
        path = base_dir / f"{table_name}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    elif format == "json":
        path = base_dir / f"{table_name}.json"
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str))


def main():
    # Argument-Parsing
    ap = argparse.ArgumentParser(
        description=t("Forschungs-Kohorten-Export mit Anonymisierung",
                      "Export anonymized research cohorts")
    )
    ap.add_argument("--scope", required=True,
                    help=t("Studien-Scope (z.B. study-2026-hrv-cohort)",
                           "Study scope (e.g. study-2026-hrv-cohort)"))
    ap.add_argument("--profile", required=True,
                    help=t("Export-Profilname", "Export profile name"))
    ap.add_argument("--person", default="all",
                    help=t("Personenfilter innerhalb jeder Instanz (Standard: all)",
                           "Person filter within each instance (default: all)"))
    ap.add_argument("--quasi-identifiers", required=True,
                    help=t("Komma-getrennte Liste der Quasi-Identifikatoren (z.B. age_band,timezone)",
                           "Comma-separated list of quasi-identifiers (e.g. age_band,timezone)"))
    ap.add_argument("--k", type=int, default=5,
                    help=t("Mindestgruppengröße für k-Anonymität", "Minimum group size for k-anonymity"))
    ap.add_argument("--age-band-width", type=int, default=5,
                    help=t("Breite der Altersbänder in Jahren", "Age band width in years"))
    ap.add_argument("--date-from", 
                    help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    ap.add_argument("--date-to",
                    help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    ap.add_argument("--reference-date", default=date.today().isoformat(),
                    help=t("Referenzdatum für Altersbänderung (Standard: heute)",
                           "Reference date for age banding (default: today)"))
    ap.add_argument("--format", choices=["csv", "json"], default="csv",
                    help=t("Ausgabeformat", "Output format"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    
    # 1. Aktive Instanzen laden
    instances = _load_patient_instances()
    if not instances:
        print(t("Keine aktiven Patient:innen-Instanzen gefunden",
                "No active patient instances found"))
        sys.exit(1)
    
    print(t(f"Gefunden {len(instances)} aktive Instanz(en)",
            f"Found {len(instances)} active instance(s)"))
    
    # 2. Einwilligungen prüfen
    consented = []
    excluded = []
    
    for pseudo, instance_dir in instances:
        if _check_consent(pseudo, args.scope):
            consented.append((pseudo, instance_dir))
            print(t(f"  ✓ {pseudo} — eingewilligt", f"  ✓ {pseudo} — consented"))
        else:
            excluded.append((pseudo, instance_dir))
            print(t(f"  ✗ {pseudo} — KEINE Einwilligung", f"  ✗ {pseudo} — NO consent"))
    
    # 3. Bei Ausschlüssen: Abbruch
    if excluded:
        print(t("\n❌ ABBRUCH: Nicht alle Patient:innen haben eingewilligt",
                "\n❌ ABORT: Not all patients have consented"))
        print(t("Keine Daten werden exportiert.", "No data will be exported."))
        sys.exit(1)
    
    # 4. Profil laden
    profile = _load_profile(args.profile)
    print(t(f"\nProfil geladen: {profile.get('name', args.profile)}",
            f"\nProfile loaded: {profile.get('name', args.profile)}"))
    
    # 5. Export-Verzeichnis vorbereiten
    export_root = KYORO_MASTER_DIR / "research_exports" / date.today().isoformat()
    kept_dir = export_root / "deliverable"
    suppressed_dir = export_root / "suppressed"
    
    print(t(f"Export-Verzeichnis: {export_root}",
            f"Export directory: {export_root}"))
    
    # 6. Jede Instanz exportieren und anonymisieren
    all_merged_data = {}
    
    for pseudo, instance_dir in consented:
        print(t(f"\nVerarbeite {pseudo}...", f"\nProcessing {pseudo}..."))

        # Instanz-Export -- schlägt der Subprozess fehl, wird sofort
        # abgebrochen (kein Schreiben bisher erfolgt), statt die fehlende
        # Instanz still auszulassen und trotzdem Erfolg zu melden.
        try:
            instance_data = _run_instance_export(Path(instance_dir), args.profile, args)
        except InstanceExportError as e:
            print(t(f"\n❌ ABBRUCH: {e}", f"\n❌ ABORT: {e}"))
            print(t("Keine Daten werden exportiert — die Kohorte wäre unvollständig.",
                    "No data will be exported — the cohort would be incomplete."))
            sys.exit(1)

        # Anonymisierung
        deidentified_data = _apply_deidentification(instance_data, pseudo, args)
        
        # In gesammelte Daten mergen
        for table_name, rows in deidentified_data.items():
            if table_name not in all_merged_data:
                all_merged_data[table_name] = []
            all_merged_data[table_name].extend(rows)
    
    # 7. k-Anonymität prüfen
    print(t("\nPrüfe k-Anonymität...", "\nChecking k-anonymity..."))
    
    k_results = _merge_and_check_k_anonymity(all_merged_data, args)
    
    # Histogramm anzeigen
    total_groups = 0
    total_suppressed = 0
    for table_name, (kept, suppressed, hist, _missing_qis) in k_results.items():
        if hist:
            total_groups += sum(hist.values())
            total_suppressed += len(suppressed)
            print(f"  {table_name}: {hist}")
    
    print(t(f"\n  Gruppen insgesamt: {total_groups}",
            f"\n  Total groups: {total_groups}"))
    print(t(f"  Unterdrückte Zeilen: {total_suppressed}",
            f"  Suppressed rows: {total_suppressed}"))
    
    # 8. Daten schreiben
    print(t("\nSchreibe Ausgabedateien...", "\nWriting output files..."))
    
    # Behaltene Daten (Deliverable)
    for table_name, (kept, _, _, _) in k_results.items():
        _write_output(kept_dir, table_name, kept, args.format)
        print(f"  ✓ {table_name}.{args.format} ({len(kept)} Zeilen)")

    # Unterdrückte Daten
    for table_name, (_, suppressed, _, _) in k_results.items():
        if suppressed:
            _write_output(suppressed_dir, table_name, suppressed, args.format)
            print(f"  ⚠ {table_name}_suppressed.{args.format} ({len(suppressed)} Zeilen)")

    # 9. Manifest schreiben
    manifest = {
        "scope": args.scope,
        "profile": profile.get("name", args.profile),
        "k": args.k,
        "age_band_width": args.age_band_width,
        "quasi_identifiers": args.quasi_identifiers,
        "instances_included": len(consented),
        "instances_excluded_count": len(excluded),
        "rows_suppressed": {},
        "quasi_identifiers_missing_per_table": {},
        "generated_at": date.today().isoformat(),
    }

    for table_name, (_, suppressed, _, missing_qis) in k_results.items():
        manifest["rows_suppressed"][table_name] = len(suppressed)
        if missing_qis:
            manifest["quasi_identifiers_missing_per_table"][table_name] = missing_qis
    
    export_root.mkdir(parents=True, exist_ok=True)
    manifest_path = export_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    print(t(f"\n✅ Fertig! Manifest: {manifest_path}",
            f"\n✅ Done! Manifest: {manifest_path}"))
    print(t(f"  Deliverable: {kept_dir}", f"  Deliverable: {kept_dir}"))
    print(t(f"  Unterdrückt:  {suppressed_dir}", f"  Suppressed:  {suppressed_dir}"))


if __name__ == "__main__":
    main()
