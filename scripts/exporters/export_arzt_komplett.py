#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
export_arzt_komplett.py - Vollständige medizinische Übersicht für Ärzte

Erstellt eine umfassende ODS-Datei mit allen relevanten medizinischen Daten:
- Familienanamnese
- Eigenanamnese (Vorerkrankungen, Infektionen)
- Medikamentationshistorie
- Lifestyle-Expositionen
- Risikomarker
- Expositionsprofil
- Reisehistorie

Verwendung:
    python3 scripts/exporters/export_arzt_komplett.py
    python3 scripts/exporters/export_arzt_komplett.py --output arzt_mappe.ods
    python3 scripts/exporters/export_arzt_komplett.py --type Infektiologe
    python3 scripts/exporters/export_arzt_komplett.py --type alle

@tier        infrastructure
@purpose.de  Exportiert arztspezifische ODS-Tabellenmappen aus den manuell
             gepflegten Kyoro-Konfig-JSON-Dateien (Familienanamnese,
             Vorerkrankungen, Medikamente, Lifestyle-Expositionen, Reisehistorie).
             Unterstützt 9 Fachrichtungs-Profile mit individueller Blatt-Auswahl.
@purpose.en  Exports doctor-specific ODS spreadsheets from manually maintained
             Kyoro config JSON files (family history, medical history, medications,
             lifestyle exposures, travel history). Supports 9 specialty profiles
             with individual sheet selection.
@method.de   Liest JSON-Dateien aus KYORO_CONFIG_DIR, konvertiert sie via pandas
             in DataFrames und schreibt sie als mehrseitige ODS-Datei. Fallback
             auf xlsx wenn odfpy nicht installiert. Arzt-Mapping definiert
             welche Tabellenblätter pro Fachrichtung exportiert werden.
@method.en   Reads JSON files from KYORO_CONFIG_DIR, converts them to DataFrames
             via pandas and writes a multi-sheet ODS file. Falls back to xlsx if
             odfpy is not installed. Doctor mapping defines which sheets are
             exported per specialty.
@limits.de   Liest nur manuell gepflegte JSON-Konfigdateien — keine Wearable-
             Zeitreihen oder Labordaten aus health.db. Ausgabe spiegelt nur
             wider was in den JSON-Dateien steht.

@relevance.de  Ermöglicht den Export von Gesundheitsdaten, essentiell für die Datenweitergabe und Interoperabilität
@relevance.en  Enables export of health data, essential for data sharing and interoperability
@limits.en   Reads only manually maintained JSON config files — no wearable
             time-series or lab data from health.db. Output reflects only
             what is present in the JSON files.
@reads       ~/.config/kyoro/family_history.json, clinical_events.json,
             medication_history.json, known_risk_exposures.json,
             own_risk_markers.json, exposure_profile.json, travel_history.json
@writes      <output>.ods — arztspezifische Tabellenmappe
@usage
    python3 scripts/exporters/export_arzt_komplett.py
    python3 scripts/exporters/export_arzt_komplett.py --type Infektiologe -o arzt_infektiologe.ods
    python3 scripts/exporters/export_arzt_komplett.py --type alle --output arzt_komplett.ods
    python3 scripts/exporters/export_arzt_komplett.py --list

Erzeugt:
    - arzt_komplett_YYYY-MM-DD.ods (oder benuterdefinierter Name)
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Projekt-Root und Config-Pfad aus health_config
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))  # scripts/ ist working dir-Konvention
from health_config import KYORO_CONFIG_DIR


def load_json_config(file_path):
    """Lädt JSON-Konfigurationsdatei aus KYORO_CONFIG_DIR."""
    full_path = KYORO_CONFIG_DIR / file_path
    
    if not full_path.exists():
        print(f"Warnung: {full_path} nicht gefunden")
        return []
    
    with open(full_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_familienanamnese():
    """Formatiert die Familienanamnese für die Tabelle."""
    data = load_json_config("family_history.json")
    
    if not data:
        return None, "Familienanamnese"
    
    # Gruppieren nach Verwandten
    by_relative = {}
    for entry in data:
        relative = entry.get("relative", "Unbekannt")
        if relative not in by_relative:
            by_relative[relative] = []
        by_relative[relative].append(entry)
    
    # Tabelle erstellen
    rows = []
    for relative, conditions in by_relative.items():
        side = conditions[0].get("side", "")
        for cond in conditions:
            rows.append({
                "Verwandter": relative,
                "Seite": side,
                "Erkrankung": cond.get("condition", ""),
                "Status": cond.get("status", ""),
                "Alter bei Beginn": cond.get("age_at_onset", ""),
                "Hinweise": cond.get("notes", "")
            })
    
    return rows, "Familienanamnese"


def format_vorerkrankungen():
    """Formatiert die Vorerkrankungen aus clinical_events.json."""
    data = load_json_config("clinical_events.json")
    
    if not data:
        return None, "Vorerkrankungen & Anamnese"
    
    rows = []
    for event in data:
        rows.append({
            "Ereignis": event.get("name", ""),
            "Datum": event.get("date", ""),
            "Typ": event.get("type", ""),
            "Hinweise": event.get("notes", "")
        })
    
    return rows, "Vorerkrankungen & Anamnese"


def format_persistente_infektionen():
    """Filtert persistente Infektionen aus clinical_events.json."""
    data = load_json_config("clinical_events.json")
    
    if not data:
        return None, "Persistente Infektionen"
    
    # Infektionen, die persistent sein können
    persistent_keywords = [
        "borreliose", "lyme", "epstein", "ebv", "cmv", "zytomegalie",
        "hepatitis", "hiv", "herpes", "vzv", "varizell", "syphilis",
        "tuberculosis", "tb", "malaria", "toxoplasmose", "q-fieber", "coxiella"
    ]
    
    rows = []
    for event in data:
        name_lower = event.get("name", "").lower()
        type_lower = event.get("type", "").lower()
        
        if type_lower == "infection" or any(kw in name_lower for kw in persistent_keywords):
            rows.append({
                "Infektion": event.get("name", ""),
                "Datum": event.get("date", ""),
                "Typ": event.get("type", ""),
                "Status": "persistent/chronisch" if any(kw in name_lower for kw in ["hashimoto", "hypothyreose"]) else "akut",
                "Hinweise": event.get("notes", "")
            })
    
    return rows, "Persistente Infektionen"


def format_medikamentationshistorie():
    """Formatiert die Medikamentationshistorie."""
    data = load_json_config("medication_history.json")
    
    if not data:
        return None, "Medikamentationshistorie"
    
    rows = []
    for med in data:
        rows.append({
            "Medikament": med.get("name", ""),
            "Wirkstoff": med.get("wirkstoff", ""),
            "Dosierung": med.get("dosis", ""),
            "Häufigkeit": med.get("frequenz", ""),
            "Indikation": med.get("indikation", ""),
            "Von": med.get("date_from", ""),
            "Bis": med.get("date_to", ""),
            "Verordnet von": med.get("verordnet_von", ""),
            "Hinweise": med.get("notes", "")
        })
    
    return rows, "Medikamentationshistorie"


def format_lifestyle_expositionen():
    """Formatiert die Lifestyle-Expositionen aus known_risk_exposures.json."""
    data = load_json_config("known_risk_exposures.json")
    
    if not data:
        return None, "Lifestyle- & Dauerrisiko-Expositionen"
    
    rows = []
    for exp in data:
        rows.append({
            "Exposition": exp.get("slug", ""),
            "Beschreibung": exp.get("description", ""),
            "Risikostufe": exp.get("level", ""),
            "Hinweise": exp.get("notes", "")
        })
    
    return rows, "Lifestyle- & Dauerrisiko-Expositionen"


def format_eigene_risikomarker():
    """Formatiert die eigenen Risikomarker."""
    data = load_json_config("own_risk_markers.json")
    
    if not data:
        return None, "Eigene Risikomarker"
    
    rows = []
    for marker in data:
        rows.append({
            "Marker": marker.get("name", marker.get("slug", "")),
            "Typ": marker.get("type", ""),
            "Wert": marker.get("value", ""),
            "Einheit": marker.get("unit", ""),
            "Datum": marker.get("date", ""),
            "Hinweise": marker.get("notes", "")
        })
    
    return rows, "Eigene Risikomarker"


def format_exposure_profile():
    """Formatiert das Expositionsprofil."""
    data = load_json_config("exposure_profile.json")
    
    if not data:
        return None, "Expositionsprofil"
    
    rows = []
    for exp in data:
        rows.append({
            "Kategorie": exp.get("category", ""),
            "Exposition": exp.get("exposure", ""),
            "Stufe": exp.get("level", ""),
            "Dauer": exp.get("duration", ""),
            "Hinweise": exp.get("notes", "")
        })
    
    return rows, "Expositionsprofil"


def format_reisehistorie():
    """Formatiert die Reisehistorie."""
    data = load_json_config("travel_history.json")
    
    if not data:
        return None, "Reisehistorie"
    
    rows = []
    for trip in data:
        rows.append({
            "Reise": trip.get("name", ""),
            "Land": trip.get("country", ""),
            "Region": trip.get("region", ""),
            "Von": trip.get("date_from", ""),
            "Bis": trip.get("date_to", ""),
            "Hinweise": trip.get("notes", "")
        })
    
    return rows, "Reisehistorie"


def save_to_ods(tables_dict, output_path):
    """Speichert ein Dictionary von Tabellen als ODS-Datei."""
    try:
        import pandas as pd
        
        with pd.ExcelWriter(output_path, engine='odf') as writer:
            for sheet_name, rows in tables_dict.items():
                if rows is None:
                    continue
                df = pd.DataFrame(rows)
                # Blatt-Name bereinigen
                clean_name = sheet_name[:31].replace('*', '').replace('#', '')
                df.to_excel(writer, sheet_name=clean_name, index=False)
        
        print(f"✓ ODS-Datei gespeichert: {output_path}")
        return True
    except ImportError:
        print("odfpy nicht verfügbar, versuche xlsx...")
        return save_to_xlsx(tables_dict, output_path)


def save_to_xlsx(tables_dict, output_path):
    """Fallback: Speichert als XLSX."""
    import pandas as pd
    
    output_path = output_path.replace('.ods', '.xlsx')
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, rows in tables_dict.items():
            if rows is None:
                continue
            df = pd.DataFrame(rows)
            clean_name = sheet_name[:31].replace('*', '').replace('#', '')
            df.to_excel(writer, sheet_name=clean_name, index=False)
    
    print(f"✓ XLSX-Datei gespeichert: {output_path}")
    return True


def ensure_dependencies():
    """Prüft Abhängigkeiten."""
    try:
        import pandas as pd
        try:
            import odfpy
            return True
        except ImportError:
            print("Hinweis: odfpy nicht installiert, verwende xlsx als Fallback")
            return True
    except ImportError:
        print("Fehler: pandas nicht installiert")
        print("Installiere mit: .venv/bin/pip install pandas odfpy")
        return False


# Mapping: Welche Daten für welchen Arzt?
ARZT_MAPPING = {
    "Hausarzt": [
        "Vorerkrankungen & Anamnese",
        "Medikamentationshistorie",
        "Lifestyle- & Dauerrisiko-Expositionen",
        "Eigene Risikomarker",
        "Persistente Infektionen"
    ],
    "Infektiologe": [
        "Vorerkrankungen & Anamnese",
        "Persistente Infektionen",
        "Medikamentationshistorie",
        "Lifestyle- & Dauerrisiko-Expositionen",
        "Reisehistorie",
        "Expositionsprofil",
        "Eigene Risikomarker"
    ],
    "Internist": [
        "Vorerkrankungen & Anamnese",
        "Medikamentationshistorie",
        "Persistente Infektionen",
        "Lifestyle- & Dauerrisiko-Expositionen",
        "Eigene Risikomarker"
    ],
    "Neurologe": [
        "Vorerkrankungen & Anamnese",
        "Medikamentationshistorie",
        "Persistente Infektionen",
        "Familienanamnese",
        "Lifestyle- & Dauerrisiko-Expositionen"
    ],
    "Psychiater": [
        "Vorerkrankungen & Anamnese",
        "Medikamentationshistorie",
        "Familienanamnese"
    ],
    "Gynäkologe": [
        "Vorerkrankungen & Anamnese",
        "Medikamentationshistorie",
        "Familienanamnese",
        "Eigene Risikomarker"
    ],
    "Reisemediziner": [
        "Reisehistorie",
        "Lifestyle- & Dauerrisiko-Expositionen",
        "Persistente Infektionen",
        "Medikamentationshistorie"
    ],
    "Immunologe": [
        "Familienanamnese",
        "Vorerkrankungen & Anamnese",
        "Persistente Infektionen",
        "Lifestyle- & Dauerrisiko-Expositionen",
        "Eigene Risikomarker",
        "Expositionsprofil"
    ],
    "Allergologe": [
        "Familienanamnese",
        "Vorerkrankungen & Anamnese",
        "Lifestyle- & Dauerrisiko-Expositionen",
        "Medikamentationshistorie"
    ]
}


def create_arzt_specific_output(arzt_type):
    """Erstellt eine arzt-spezifische Auswahl."""
    # Alle Daten laden
    all_tables = {}
    
    all_tables["Familienanamnese"] = format_familienanamnese()[0]
    all_tables["Vorerkrankungen & Anamnese"] = format_vorerkrankungen()[0]
    all_tables["Persistente Infektionen"] = format_persistente_infektionen()[0]
    all_tables["Medikamentationshistorie"] = format_medikamentationshistorie()[0]
    all_tables["Lifestyle- & Dauerrisiko-Expositionen"] = format_lifestyle_expositionen()[0]
    all_tables["Eigene Risikomarker"] = format_eigene_risikomarker()[0]
    all_tables["Expositionsprofil"] = format_exposure_profile()[0]
    all_tables["Reisehistorie"] = format_reisehistorie()[0]
    
    # Arzt-spezifische Auswahl
    if arzt_type in ARZT_MAPPING:
        selected_tables = {}
        for sheet_name in ARZT_MAPPING[arzt_type]:
            if sheet_name in all_tables:
                selected_tables[sheet_name] = all_tables[sheet_name]
        return selected_tables
    else:
        return all_tables


def print_uebersicht():
    """Druckt eine Übersicht aller verfügbaren Daten."""
    print("\n" + "="*80)
    print("VERFÜGBARE DATEN FÜR ÄRZTE")
    print("="*80)
    
    data_sources = [
        ("Familienanamnese", "~/.config/kyoro/family_history.json", "Blutsverwandte, Erkrankungen, Vererbungsmuster", "Alle Ärzte"),
        ("Vorerkrankungen", "~/.config/kyoro/clinical_events.json", "Alle Diagnosen, Symptome, OPs, Infektionen", "Alle Ärzte"),
        ("Persistente Infektionen", "~/.config/kyoro/clinical_events.json (gefiltert)", "EBV, CMV, Borreliose, Hepatitis, etc.", "Infektiologe, Internist, Immunologe"),
        ("Medikamentationshistorie", "~/.config/kyoro/medication_history.json", "Alle Medikamente mit Dosierung, Indikation, Dauer", "Alle Ärzte"),
        ("Lifestyle-Expositionen", "~/.config/kyoro/known_risk_exposures.json", "Tierhaltung, Beruf, Wohnort, Reisen", "Infektiologe, Immunologe, Allergologe"),
        ("Eigene Risikomarker", "~/.config/kyoro/own_risk_markers.json", "Biomarker, Laborwerte, genetische Marker", "Internist, Immunologe, Hausarzt"),
        ("Expositionsprofil", "~/.config/kyoro/exposure_profile.json", "Kumulierte Expositionen nach Kategorie", "Immunologe, Reisemediziner"),
        ("Reisehistorie", "~/.config/kyoro/travel_history.json", "Alle Reisen mit Datum, Land, Region", "Reisemediziner, Infektiologe"),
    ]
    
    print(f"\n{'SCRIPT':<25} {'DATEI':<40} {'INHALT':<35} {'ARZT'}")
    print("-" * 80)
    
    for script, datei, inhalt, arzt in data_sources:
        print(f"{script:<25} {datei:<40} {inhalt:<35} {arzt}")
    
    print("\n" + "="*80)
    print("EMPFOHLENE KOMBINATIONEN")
    print("="*80)
    
    for arzt, sheets in ARZT_MAPPING.items():
        print(f"\n{arzt}:")
        for sheet in sheets:
            print(f"  ✓ {sheet}")


def print_arzt_mappe():
    """Druckt eine Übersicht der Arzt-Mappe."""
    print("\n" + "="*80)
    print("ARZT-MAPPE: WAS WIRD EXPORTIERT?")
    print("="*80)
    
    print("\n📋 STANDARD-EXPORT (Alle Daten):")
    print("  • Familienanamnese")
    print("  • Vorerkrankungen & Anamnese")
    print("  • Persistente Infektionen")
    print("  • Medikamentationshistorie")
    print("  • Lifestyle- & Dauerrisiko-Expositionen")
    print("  • Eigene Risikomarker")
    print("  • Expositionsprofil")
    print("  • Reisehistorie")
    
    print("\n👨‍⚕️  ARZT-SPEZIFISCHE EXPORTE:")
    for arzt, sheets in ARZT_MAPPING.items():
        print(f"\n  {arzt}:")
        for sheet in sheets:
            print(f"    • {sheet}")


def main():
    parser = argparse.ArgumentParser(
        description='Erstellt eine vollständige medizinische Übersicht für Ärzte',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
BEISPIELE:
  python3 scripts/exporters/export_arzt_komplett.py                     # Alle Daten
  python3 scripts/exporters/export_arzt_komplett.py --type Infektiologe  # Nur Infektiologe-Daten
  python3 scripts/exporters/export_arzt_komplett.py --output arzt.ods    # Benutzerdefinierter Name
  python3 scripts/exporters/export_arzt_komplett.py --list               # Übersicht anzeigen

VERFÜGBARE TYPEN:
  alle, familienanamnese, vorerkrankungen, infektionen, medikamente,
  lifestyle, risikomarker, expositionen, reisen
  Hausarzt, Infektiologe, Internist, Neurologe, Psychiater, Gynäkologe, Reisemediziner, Immunologe, Allergologe
        """
    )
    parser.add_argument('--type', choices=list(ARZT_MAPPING.keys()) + ['alle', 'familienanamnese', 'vorerkrankungen', 'infektionen', 'medikamente', 'lifestyle', 'risikomarker', 'expositionen', 'reisen'],
                        default='alle', help='Typ der Übersicht')
    parser.add_argument('--output', '-o', help='Ausgabedatei (Standard: arzt_komplett_DATUM.ods)')
    parser.add_argument('--list', '-l', action='store_true', help='Übersicht anzeigen')
    
    args = parser.parse_args()
    
    # Übersicht anzeigen
    if args.list:
        print_uebersicht()
        print_arzt_mappe()
        sys.exit(0)
    
    # Abhängigkeiten prüfen
    if not ensure_dependencies():
        sys.exit(1)
    
    # Output-Datei bestimmen
    if args.output:
        output_path = Path(args.output)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = PROJECT_ROOT / f"arzt_komplett_{today}.ods"
    
    output_path = output_path.absolute()
    
    # Daten je nach Typ auswählen
    if args.type == 'alle':
        tables = {}
        tables["Familienanamnese"] = format_familienanamnese()[0]
        tables["Vorerkrankungen & Anamnese"] = format_vorerkrankungen()[0]
        tables["Persistente Infektionen"] = format_persistente_infektionen()[0]
        tables["Medikamentationshistorie"] = format_medikamentationshistorie()[0]
        tables["Lifestyle- & Dauerrisiko-Expositionen"] = format_lifestyle_expositionen()[0]
        tables["Eigene Risikomarker"] = format_eigene_risikomarker()[0]
        tables["Expositionsprofil"] = format_exposure_profile()[0]
        tables["Reisehistorie"] = format_reisehistorie()[0]
    elif args.type in ARZT_MAPPING:
        tables = create_arzt_specific_output(args.type)
    else:
        # Einzelne Tabelle
        table_map = {
            'familienanamnese': format_familienanamnese,
            'vorerkrankungen': format_vorerkrankungen,
            'infektionen': format_persistente_infektionen,
            'medikamente': format_medikamentationshistorie,
            'lifestyle': format_lifestyle_expositionen,
            'risikomarker': format_eigene_risikomarker,
            'expositionen': format_exposure_profile,
            'reisen': format_reisehistorie
        }
        if args.type in table_map:
            rows, title = table_map[args.type]()
            tables = {title: rows}
        else:
            tables = {}
    
    # Leere Tabellen entfernen
    tables = {k: v for k, v in tables.items() if v is not None and len(v) > 0}
    
    if not tables:
        print("Keine Daten zum Exportieren gefunden")
        sys.exit(1)
    
    # Speichern
    save_to_ods(tables, output_path)
    
    # Zusammenfassung
    print(f"\n✓ Export erfolgreich!")
    print(f"  Datei: {output_path}")
    print(f"  Tabellen: {len(tables)}")
    for sheet_name in tables.keys():
        print(f"    • {sheet_name}")
    
    # Arzt-Tipps
    if args.type == 'alle':
        print(f"\n💡 Tipp: Für spezifische Ärzte verwende:")
        for arzt in ['Hausarzt', 'Infektiologe', 'Internist']:
            print(f"    --type {arzt}")


if __name__ == '__main__':
    main()
