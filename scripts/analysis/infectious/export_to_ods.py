#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
export_to_ods.py — Exportiert Infektionsanalysen als OpenOffice-Tabellen

@tier        infrastructure
@purpose.de  Liest Ausgabedateien der Infektionsanalysen und konvertiert sie
@relevance.de Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten
@relevance.en Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data
              in sortierbare/filterbare OpenOffice-Tabellen (.ods).
@purpose.en  Reads output files from infection analyses and converts them into
              sortable/filterable OpenOffice spreadsheets (.ods).
@method.de   Liest JSON/CSV-Ausgaben aus analyses/ und schreibt .ods-Dateien
              via odfpy. Unterstützt outbreak_exposure und postinfectious Typen.
@method.en   Reads JSON/CSV outputs from analyses/ and writes .ods files via
              odfpy. Supports outbreak_exposure and postinfectious types.
@limits.de   Erfordert odfpy. Keine DB-Verbindung — liest nur Analysedateien.
@limits.en   Requires odfpy. No DB connection — reads analysis output files only.
@reads       analyses/infectious/, analyses/postinfectious/
@writes      analyses/infectious/outbreak_exposure_tabellen.ods,
             analyses/postinfectious/postinfectious_tabellen.ods,
             analyses/infectious_analysen.ods
@usage
    python3 export_to_ods.py
    python3 export_to_ods.py --type outbreak_exposure
    python3 export_to_ods.py --type postinfectious
    python3 export_to_ods.py --all
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Projekt-Root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def ensure_dependencies():
    """Stellt sicher, dass pandas und odfpy installiert sind."""
    try:
        import pandas as pd
        import odf  # noqa: F401 -- the "odfpy" package imports as "odf", not "odfpy"
        return True
    except ImportError:
        print("Benötigte Pakete fehlen: pandas, odfpy")
        print("Installiere mit: .venv/bin/pip install pandas odfpy")
        return False


def parse_outbreak_exposure_file(file_path):
    """
    Parst eine outbreak_exposure Ausgabedatei und extrahiert tabellarische Daten.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Daten-Struktur
    data = {
        'exposures': [],
        'reisen': [],
        'syndrome': [],
        'locations': []
    }
    
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Überschriften erkennen. Die "### Empfohlene Syndrome ..."-Überschrift
        # matcht auch dieses generische "### "-Pattern und wurde deshalb, bevor
        # der speziellere "Empfohlene Syndrome"-Check weiter unten je erreicht
        # wurde, hier schon mit "continue" auf den vollen Überschriftentext
        # gesetzt -- current_section wurde nie exakt "syndrome", die Syndrome
        # darunter wurden nie eingesammelt. Deshalb hier direkt normalisieren.
        if line.startswith('## '):
            current_section = line[3:].strip()
            if 'Empfohlene Syndrome' in current_section:
                current_section = 'syndrome'
            continue

        if line.startswith('### '):
            current_section = line[4:].strip()
            if 'Empfohlene Syndrome' in current_section:
                current_section = 'syndrome'
            continue
        
        # Reisen-Daten. Der Generator (analyse_outbreak_exposure.py) nannte
        # das Feld frueher "Reisen analysiert", inzwischen "Aufenthalte
        # analysiert" -- beide Formulierungen kommen in bestehenden
        # Reports vor, deshalb beide matchen statt nur die veraltete.
        if 'Reisen analysiert:' in line or 'Aufenthalte analysiert:' in line:
            match = re.search(r'(?:Reisen|Aufenthalte) analysiert:\s*(\d+)', line)
            if match:
                data['reisen_count'] = int(match.group(1))
        
        if 'Expositions-Treffer:' in line:
            match = re.search(r'Expositions-Treffer:\s*(\d+)', line)
            if match:
                data['exposures_count'] = int(match.group(1))
        
        # Syndrome
        if 'Empfohlene Syndrome' in line:
            current_section = 'syndrome'
            continue
        
        if current_section == 'syndrome' and line.startswith('- `'):
            syndrome = re.search(r'`([^`]+)`', line)
            if syndrome:
                data['syndrome'].append(syndrome.group(1))
        
        # GPS-Koordinaten mit Expositions
        gps_match = re.match(r'### GPS (\d+\.\d+),(-?\d+\.\d+) \((\d+) Aufenthalte\)', line)
        if gps_match:
            current_gps = {
                'lat': gps_match.group(1),
                'lon': gps_match.group(2),
                'aufenthalte': int(gps_match.group(3)),
                'exposures': []
            }
            data['locations'].append(current_gps)
            current_section = 'gps_exposures'
            continue
        
        # Expositions-Einträge
        if current_section == 'gps_exposures':
            # [Endemie] 🟡 **West-Nil-Virus** — Po-Ebene/Norditalien  →  `generic`  |  endemisch (kein Zeitlimit)
            exp_match = re.match(
                r'\[([^\]]+)\]\s*[🟡🟢🔴]\s*\*\*([^\*]+)\*\*\s*—\s*([^\s]+)\s*—\s*([^\s]+)\s*→\s*`([^`]+)`\s*\|\s*([^\|]+)\(\s*([^)]+)\)',
                line
            )
            if exp_match:
                exposure = {
                    'typ': exp_match.group(1),
                    'pathogen': exp_match.group(2),
                    'region': exp_match.group(3),
                    'land': exp_match.group(4),
                    'syndrome': exp_match.group(5),
                    'status': exp_match.group(6),
                    'zeitlimit': exp_match.group(7)
                }
                if data['locations']:
                    data['locations'][-1]['exposures'].append(exposure)
    
    return data


def outbreak_exposure_to_tables(data):
    """Konvertiert outbreak_exposure Daten in Tabellen."""
    import pandas as pd
    
    tables = {}
    
    # 1. Übersichtstabelle
    overview_data = {
        'Metrik': ['Reisen analysiert', 'Expositions-Treffer', 'Empfohlene Syndrome'],
        'Wert': [
            data.get('reisen_count', 0),
            data.get('exposures_count', 0),
            ', '.join(data.get('syndrome', []))
        ]
    }
    tables['Übersicht'] = pd.DataFrame(overview_data)
    
    # 2. Locations-Tabelle
    if data.get('locations'):
        location_rows = []
        for loc in data['locations']:
            for exp in loc.get('exposures', []):
                location_rows.append({
                    'Latitude': loc['lat'],
                    'Longitude': loc['lon'],
                    'Aufenthalte': loc['aufenthalte'],
                    'Typ': exp['typ'],
                    'Pathogen': exp['pathogen'],
                    'Region': exp['region'],
                    'Land': exp['land'],
                    'Syndrom': exp['syndrome'],
                    'Status': exp['status'],
                    'Zeitlimit': exp['zeitlimit']
                })
        tables['Expositions nach GPS'] = pd.DataFrame(location_rows)
    
    # 3. Syndrome-Tabelle
    if data.get('syndrome'):
        syndrome_rows = [{'Syndrom': s} for s in data['syndrome']]
        tables['Empfohlene Syndrome'] = pd.DataFrame(syndrome_rows)
    
    return tables


def parse_postinfectious_file(file_path):
    """
    Parst eine postinfectious Diagnose-Datei.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Tabellen im Markdown-Format extrahieren
    tables = {}
    
    # Nach Tabellen suchen (| Syntax)
    lines = content.split('\n')
    current_header = None
    in_table = False
    table_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Überschrift
        if stripped.startswith('#') or stripped.startswith('##'):
            if in_table and table_lines:
                df = parse_markdown_table(table_lines)
                if df is not None and current_header:
                    tables[current_header] = df
                table_lines = []
                in_table = False
            current_header = stripped
            continue
        
        # Tabellenzeile
        if stripped.startswith('|'):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(stripped)
        else:
            if in_table and table_lines:
                df = parse_markdown_table(table_lines)
                if df is not None and current_header:
                    tables[current_header] = df
                table_lines = []
                in_table = False
    
    # Letzte Tabelle
    if in_table and table_lines:
        df = parse_markdown_table(table_lines)
        if df is not None and current_header:
            tables[current_header] = df
    
    return tables


def parse_markdown_table(table_lines):
    """Konvertiert Markdown-Tabellenzeilen in DataFrame."""
    import pandas as pd
    from io import StringIO
    
    if not table_lines:
        return None
    
    # Tabellen-Text bereinigen
    cleaned_lines = []
    for line in table_lines:
        line = line.strip()
        if line.startswith('|'):
            line = line[1:]
        if line.endswith('|'):
            line = line[:-1]
        line = line.replace('|', '\t')
        cleaned_lines.append(line)
    
    table_text = '\n'.join(cleaned_lines)
    
    try:
        df = pd.read_csv(StringIO(table_text), sep='\t', header=0, dtype=str)
        return df
    except Exception:
        return None


def save_tables_to_ods(tables_dict, output_path):
    """Speichert ein Dictionary von DataFrames als ODS-Datei."""
    import pandas as pd
    
    if not tables_dict:
        print(f"Keine Tabellen zum Speichern für {output_path}")
        return False
    
    try:
        with pd.ExcelWriter(output_path, engine='odf') as writer:
            for sheet_name, df in tables_dict.items():
                # Blatt-Name bereinigen
                clean_name = sheet_name[:31].replace('*', '').replace('#', '').replace('`', '')
                clean_name = re.sub(r'[\\/*?:\[\]]', '_', clean_name)
                df.to_excel(writer, sheet_name=clean_name, index=False)
        return True
    except ImportError:
        print("odfpy nicht verfügbar, versuche xlsx...")
        return save_tables_to_xlsx(tables_dict, output_path.replace('.ods', '.xlsx'))


def save_tables_to_xlsx(tables_dict, output_path):
    """Speichert als XLSX (Fallback)."""
    import pandas as pd
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, df in tables_dict.items():
            clean_name = sheet_name[:31].replace('*', '').replace('#', '').replace('`', '')
            clean_name = re.sub(r'[\\/*?:\[\]]', '_', clean_name)
            df.to_excel(writer, sheet_name=clean_name, index=False)
    print(f"Hinweis: XLSX-Datei erstellt: {output_path}")
    return True


def get_latest_outbreak_exposure_files(days=30):
    """Findet die neuesten outbreak_exposure Ausgabedateien."""
    out_dir = PROJECT_ROOT / "analyses" / "infectious"
    if not out_dir.exists():
        return []
    
    files = sorted(out_dir.glob("outbreak_exposure_*.md"), reverse=True)
    
    # Nur Dateien der letzten N Tage
    cutoff = datetime.now() - timedelta(days=days)
    recent_files = []
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime >= cutoff:
            recent_files.append(f)
    
    return recent_files[:5]  # Maximal 5 neueste


def get_latest_postinfectious_files(days=30):
    """Findet die neuesten postinfectious Ausgabedateien."""
    out_dir = PROJECT_ROOT / "analyses" / "postinfectious"
    if not out_dir.exists():
        return []
    
    files = sorted(out_dir.glob("*.md"), reverse=True)
    
    cutoff = datetime.now() - timedelta(days=days)
    recent_files = []
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime >= cutoff:
            recent_files.append(f)
    
    return recent_files[:5]


def process_outbreak_exposure():
    """Verarbeitet alle outbreak_exposure Analysen."""
    print("\n=== Verarbeite Outbreak-Exposure Analysen ===")
    
    files = get_latest_outbreak_exposure_files()
    if not files:
        print("Keine outbreak_exposure Dateien gefunden in analyses/infectious/")
        return
    
    all_tables = {}
    
    for file_path in files:
        print(f"  Verarbeite: {file_path.name}")
        data = parse_outbreak_exposure_file(file_path)
        tables = outbreak_exposure_to_tables(data)
        
        for sheet_name, df in tables.items():
            # Sheet-Namen mit Datei-Namen prefixen
            prefix = file_path.stem.replace('outbreak_exposure_', '').replace('_', ' ')
            new_name = f"{prefix[:20]} - {sheet_name}"[:31]
            all_tables[new_name] = df
    
    if all_tables:
        output_path = PROJECT_ROOT / "analyses" / "infectious" / "outbreak_exposure_tabellen.ods"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if save_tables_to_ods(all_tables, output_path):
            print(f"  ✓ Gespeichert: {output_path}")
        else:
            print(f"  ✗ Fehler beim Speichern: {output_path}")
    else:
        print("  Keine Tabellen extrahiert")


def process_postinfectious():
    """Verarbeitet postinfectious Diagnose-Analysen."""
    print("\n=== Verarbeite Postinfectious Analysen ===")
    
    out_dir = PROJECT_ROOT / "analyses" / "postinfectious"
    if not out_dir.exists():
        print("Kein postinfectious Verzeichnis gefunden")
        return
    
    files = sorted(out_dir.glob("*.md"), reverse=True)
    
    all_tables = {}
    
    for file_path in files[:5]:  # Maximal 5 neueste
        print(f"  Verarbeite: {file_path.name}")
        tables = parse_postinfectious_file(file_path)
        
        for sheet_name, df in tables.items():
            prefix = file_path.stem[:15]
            new_name = f"{prefix} - {sheet_name}"[:31]
            all_tables[new_name] = df
    
    if all_tables:
        output_path = out_dir / "postinfectious_tabellen.ods"
        
        if save_tables_to_ods(all_tables, output_path):
            print(f"  ✓ Gespeichert: {output_path}")
        else:
            print(f"  ✗ Fehler beim Speichern: {output_path}")
    else:
        print("  Keine Tabellen extrahiert")


def process_all_infectious():
    """Verarbeitet alle Infektions-Analysen."""
    print("\n=== Verarbeite alle Infektions-Analysen ===")
    
    all_tables = {}
    
    # 1. Outbreak-Exposure
    files = get_latest_outbreak_exposure_files()
    for file_path in files:
        data = parse_outbreak_exposure_file(file_path)
        tables = outbreak_exposure_to_tables(data)
        for sheet_name, df in tables.items():
            prefix = file_path.stem.replace('outbreak_exposure_', '')[:10]
            all_tables[f"OE - {prefix} - {sheet_name}"] = df
    
    # 2. Postinfectious
    out_dir = PROJECT_ROOT / "analyses" / "postinfectious"
    if out_dir.exists():
        files = sorted(out_dir.glob("*.md"), reverse=True)[:5]
        for file_path in files:
            tables = parse_postinfectious_file(file_path)
            for sheet_name, df in tables.items():
                prefix = file_path.stem[:10]
                all_tables[f"PI - {prefix} - {sheet_name}"] = df
    
    if all_tables:
        output_path = PROJECT_ROOT / "analyses" / "infectious_analysen.ods"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if save_tables_to_ods(all_tables, output_path):
            print(f"  ✓ Gespeichert: {output_path}")
        else:
            print(f"  ✗ Fehler beim Speichern: {output_path}")
    else:
        print("  Keine Tabellen extrahiert")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Exportiert Infektionsanalysen als OpenOffice-Tabellen'
    )
    parser.add_argument('--type', choices=['outbreak_exposure', 'postinfectious', 'all'],
                        default='all', help='Typ der Analyse')
    parser.add_argument('--output', '-o', help='Ausgabedatei (überschreibt Standard)')
    
    args = parser.parse_args()
    
    # Abhängigkeiten prüfen
    if not ensure_dependencies():
        sys.exit(1)
    
    if args.type == 'outbreak_exposure':
        process_outbreak_exposure()
    elif args.type == 'postinfectious':
        process_postinfectious()
    else:
        process_all_infectious()
        
        # Auch Einzeldateien erstellen
        process_outbreak_exposure()
        process_postinfectious()
    
    print("\n✓ Fertig! Alle Tabellen wurden erstellt.")
    print("Öffne die .ods-Dateien mit LibreOffice Calc für Sortieren und Filtern.")


if __name__ == '__main__':
    main()
