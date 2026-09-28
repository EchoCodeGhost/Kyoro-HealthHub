#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
export_analyses_to_ods.py — Master-Exporter für alle Infektionsanalysen

@tier        infrastructure
@purpose.de  Konvertiert Ausgabedateien aller Infektionsanalyse-Scripts in
@relevance.de Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten
@relevance.en Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data
             sortierbare/filterbare OpenOffice-Tabellen (.ods).
@purpose.en  Converts output files from all infection analysis scripts into
             sortable/filterable OpenOffice spreadsheets (.ods).
@method.de   Liest JSON/CSV/MD-Ausgaben aus analyses/*/ und schreibt .ods-Dateien
             via odfpy. Unterstützt outbreak_exposure, pathogen_exposure,
             postinfectious_diagnose, acute_response und combined-Export.
@method.en   Reads JSON/CSV/MD outputs from analyses/*/ and writes .ods files
             via odfpy. Supports outbreak_exposure, pathogen_exposure,
             postinfectious_diagnose, acute_response, and combined export.
@limits.de   Erfordert odfpy. Keine DB-Verbindung — liest nur Analysedateien.
@limits.en   Requires odfpy. No DB connection — reads analysis output files only.
@reads       analyses/infectious/ (outbreak_exposure_*.md, pathogen_exposure_*.md,
             acute_response_*.md), analyses/postinfectious/
@writes      analyses/*/..._tabellen.ods, analyses/infectious_analysen_kombiniert.ods
@usage
    python3 export_analyses_to_ods.py
    python3 export_analyses_to_ods.py --type outbreak_exposure
    python3 export_analyses_to_ods.py --type all --output alle_infektionen.ods
    python3 export_analyses_to_ods.py --recent-only
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Projekt-Root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Pfade zu den Analyse-Verzeichnissen. outbreak_exposure/pathogen_exposure/
# acute_response teilen sich seit der Fachgebiets-Umstellung (2026-09-28) das
# gemeinsame Verzeichnis analyses/infectious/ — die Trennung nach Kategorie
# passiert weiterhin sauber über das dateiname-basierte Glob-Muster in
# get_recent_files() (f"{analysis_type}_*.md"), nicht mehr über den Ordner.
# postinfectious bleibt bewusst eine fachgebietsübergreifende Ausnahme
# (Skripte aus neurology/, infectious/ und internal_medicine/ schreiben
# gemeinsam dorthin).
ANALYSIS_DIRS = {
    'outbreak_exposure': PROJECT_ROOT / "analyses" / "infectious",
    'pathogen_exposure': PROJECT_ROOT / "analyses" / "infectious",
    'postinfectious': PROJECT_ROOT / "analyses" / "postinfectious",
    'acute_response': PROJECT_ROOT / "analyses" / "infectious",
}


def ensure_dependencies():
    """Prüft und installiert Abhängigkeiten."""
    try:
        import pandas as pd
        try:
            import odfpy
            return True
        except ImportError:
            # odfpy nicht verfügbar, aber pandas ist da - wir können xlsx verwenden
            print("Hinweis: odfpy nicht installiert, verwende xlsx als Fallback")
            print("Für ODS-Format: pip install odfpy")
            return True
    except ImportError as e:
        print(f"Fehler: {e}")
        print("Benötigte Pakete: pandas")
        print("Installiere mit: .venv/bin/pip install pandas")
        return False


class AnalysisExporter:
    """Basis-Klasse für Exporter."""
    
    def __init__(self, analysis_type):
        self.analysis_type = analysis_type
        self.out_dir = ANALYSIS_DIRS.get(analysis_type)
        self.tables = {}
    
    def get_recent_files(self, days=90, max_files=10):
        """Findet neueste Ausgabedateien."""
        if not self.out_dir or not self.out_dir.exists():
            return []
        
        pattern = f"{self.analysis_type}_*.md"
        if self.analysis_type == 'postinfectious':
            pattern = "*.md"
        
        files = sorted(self.out_dir.glob(pattern), reverse=True)
        
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        for f in files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime >= cutoff:
                recent.append(f)
            if len(recent) >= max_files:
                break
        
        return recent
    
    def extract_tables_from_file(self, file_path):
        """Extrahiert alle Tabellen aus einer Markdown-Datei."""
        raise NotImplementedError
    
    def process_file(self, file_path):
        """Verarbeitet eine einzelne Datei."""
        print(f"  Verarbeite: {file_path.name}")
        tables = self.extract_tables_from_file(file_path)
        
        for sheet_name, df in tables.items():
            prefix = file_path.stem[:15]
            new_name = f"{prefix} - {sheet_name}"[:31]
            self.tables[new_name] = df
        
        return len(tables)
    
    def process_all(self):
        """Verarbeitet alle Dateien."""
        files = self.get_recent_files()
        if not files:
            print(f"  Keine Dateien gefunden in {self.out_dir}")
            return 0
        
        count = 0
        for file_path in files:
            count += self.process_file(file_path)
        
        return count
    
    def save_to_ods(self, output_path=None):
        """Speichert alle Tabellen als ODS-Datei."""
        if not self.tables:
            print("  Keine Tabellen zum Speichern")
            return False
        
        if output_path is None:
            output_path = self.out_dir / f"{self.analysis_type}_tabellen.ods"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            import pandas as pd
            with pd.ExcelWriter(output_path, engine='odf') as writer:
                for sheet_name, df in self.tables.items():
                    clean_name = self._clean_sheet_name(sheet_name)
                    df.to_excel(writer, sheet_name=clean_name, index=False)
            print(f"  ✓ Gespeichert: {output_path}")
            return True
        except ImportError:
            print("  odfpy nicht verfügbar, versuche xlsx...")
            return self._save_to_xlsx(output_path.replace('.ods', '.xlsx'))
    
    def _save_to_xlsx(self, output_path):
        """Fallback: Speichert als XLSX."""
        import pandas as pd
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for sheet_name, df in self.tables.items():
                clean_name = self._clean_sheet_name(sheet_name)
                df.to_excel(writer, sheet_name=clean_name, index=False)
        print(f"  ✓ XLSX gespeichert: {output_path}")
        return True
    
    @staticmethod
    def _clean_sheet_name(name):
        """Bereinigt Blatt-Namen für ODS/XLSX."""
        name = name[:31]
        name = re.sub(r'[\\/*?:\[\]]', '_', name)
        name = name.replace('#', '').replace('*', '').replace('`', '')
        return name


class OutbreakExposureExporter(AnalysisExporter):
    """Exporter für outbreak_exposure Analysen."""
    
    def __init__(self):
        super().__init__('outbreak_exposure')
    
    def extract_tables_from_file(self, file_path):
        """Extrahiert Tabellen aus outbreak_exposure Ausgabe."""
        import pandas as pd
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tables = {}
        
        # 1. Übersichtstabelle
        reisen_count = self._extract_number(content, 'Reisen analysiert:')
        exposure_count = self._extract_number(content, 'Expositions-Treffer:')
        syndromes = self._extract_list(content, r'`([^`]+)`', 'Empfohlene Syndrome')
        
        overview_data = {
            'Metrik': ['Reisen analysiert', 'Expositions-Treffer', 'Empfohlene Syndrome'],
            'Wert': [
                reisen_count or 0,
                exposure_count or 0,
                ', '.join(syndromes) if syndromes else 'keine'
            ]
        }
        tables['Übersicht'] = pd.DataFrame(overview_data)
        
        # 2. Expositions-Tabelle nach GPS
        gps_sections = re.findall(
            r'### GPS (\d+\.\d+),(-?\d+\.\d+) \((\d+) Aufenthalte\)',
            content
        )
        
        if gps_sections:
            exposure_rows = []
            lines = content.split('\n')
            
            for gps_match in gps_sections:
                lat, lon, aufenthalte = gps_match
                
                # Suche nach dem nächsten GPS-Abschnitt und extrahiere alle Expositions
                gps_start_idx = content.find(f"### GPS {lat},{lon}")
                if gps_start_idx == -1:
                    continue
                
                # Finde das nächste GPS oder das Ende des Dokuments
                next_gps_idx = content.find('### GPS', gps_start_idx + 10)
                section = content[gps_start_idx:next_gps_idx] if next_gps_idx != -1 else content[gps_start_idx:]
                
                # Extrahiere Expositions aus diesem Abschnitt
                exp_pattern = r'\[([^\]]+)\]\s*[🟡🟢🔴⚪]\s*\*\*([^\*]+)\*\*\s*—\s*([^\s|]+)\s*—?\s*([^\s|]*)\s*→\s*`([^`]+)`\s*\|\s*([^\|]+)\(\s*([^)]+)\)'
                
                for exp_match in re.finditer(exp_pattern, section):
                    exp_data = {
                        'Latitude': lat,
                        'Longitude': lon,
                        'Aufenthalte': int(aufenthalte),
                        'Typ': exp_match.group(1),
                        'Pathogen': exp_match.group(2),
                        'Region': exp_match.group(3),
                        'Land': exp_match.group(4),
                        'Syndrom': exp_match.group(5),
                        'Status': exp_match.group(6),
                        'Zeitlimit': exp_match.group(7)
                    }
                    exposure_rows.append(exp_data)
            
            if exposure_rows:
                tables['Expositions nach GPS'] = pd.DataFrame(exposure_rows)
        
        # 3. Bekannte Vorinfektionen
        infections = self._extract_infections(content)
        if infections:
            tables['Bekannte Vorinfektionen'] = pd.DataFrame(infections)
        
        # 4. Dauerrisiko-Expositionen
        risk_exposures = self._extract_risk_exposures(content)
        if risk_exposures:
            tables['Dauerrisiko-Expositionen'] = pd.DataFrame(risk_exposures)
        
        return tables
    
    @staticmethod
    def _extract_number(text, pattern):
        """Extrahiert eine Zahl nach einem bestimmten Pattern."""
        match = re.search(rf'{pattern}\s*(\d+)', text)
        return int(match.group(1)) if match else None
    
    @staticmethod
    def _extract_list(text, pattern, section_start):
        """Extrahiert eine Liste von Items nach einem bestimmten Pattern."""
        if section_start not in text:
            return []
        
        start_idx = text.find(section_start)
        if start_idx == -1:
            return []
        
        end_idx = text.find('###', start_idx + 1)
        if end_idx == -1:
            end_idx = len(text)
        
        section = text[start_idx:end_idx]
        matches = re.findall(pattern, section)
        return matches
    
    @staticmethod
    def _extract_infections(content):
        """Extrahiert bekannte Infektionen."""
        lines = content.split('\n')
        infections = []
        in_section = False
        
        for line in lines:
            line = line.strip()
            
            if 'Bekannte Vorinfektionen' in line:
                in_section = True
                continue
            
            if in_section and line.startswith('###'):
                break
            
            if in_section and line.startswith('- **'):
                match = re.match(r'-\s*\*\*(.+?)\*\*\s*\((.+?)\)\s*.*→\s*`([^`]+)`', line)
                if match:
                    infections.append({
                        'Name': match.group(1),
                        'Datum': match.group(2),
                        'Typ': match.group(3)
                    })
        
        return infections
    
    @staticmethod
    def _extract_risk_exposures(content):
        """Extrahiert Dauerrisiko-Expositionen."""
        lines = content.split('\n')
        exposures = []
        in_section = False
        
        for line in lines:
            line = line.strip()
            
            if 'Dauerrisiko-Expositionen' in line:
                in_section = True
                continue
            
            if in_section and (line.startswith('###') or line.startswith('##')):
                break
            
            if in_section and line and not line.startswith('['):
                # 🔴 `slug` — Beschreibung (Notizen)
                match = re.match(r'[🟡🟢🔴⚪]\s*`([^`]+)`\s*—\s*(.+?)', line)
                if match:
                    exposures.append({
                        'Slug': match.group(1),
                        'Beschreibung': match.group(2).split('(')[0].strip()
                    })
        
        return exposures


class PathogenExposureExporter(AnalysisExporter):
    """Exporter für pathogen_exposure Analysen."""
    
    def __init__(self):
        super().__init__('pathogen_exposure')
    
    def extract_tables_from_file(self, file_path):
        """Extrahiert Tabellen aus pathogen_exposure Ausgabe."""
        import pandas as pd
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tables = {}
        
        # 1. Übersichtstabelle - Suche nach Zusammenfassungen
        # Pathogen-Rangliste
        ranked_pattern = r'\d+\.\s+([^:]+):\s+([\d.]+)'
        ranked_matches = re.findall(ranked_pattern, content)
        
        if ranked_matches:
            ranked_data = {'Pathogen': [], 'Score': []}
            for match in ranked_matches[:20]:  # Top 20
                ranked_data['Pathogen'].append(match[0])
                ranked_data['Score'].append(float(match[1]))
            tables['Pathogen-Rangliste'] = pd.DataFrame(ranked_data)
        
        # 2. Aufenthaltszeitlinie
        timeline_rows = []
        timeline_match = re.search(
            r'## Aufenthaltszeitlinie(.*?)(?=\n## |\n\*\*|\Z)',
            content,
            re.DOTALL
        )
        
        if timeline_match:
            timeline_section = timeline_match.group(1)
            # Suche nach Zeilen wie: 2020-01-01 - 2020-01-15: Ort (Quelle)
            date_pattern = r'(\d{4}-\d{2}-\d{2})\s*[–-]\s*(\d{4}-\d{2}-\d{2}):\s*([^,]+)'
            
            for match in re.finditer(date_pattern, timeline_section):
                timeline_rows.append({
                    'Von': match.group(1),
                    'Bis': match.group(2),
                    'Ort': match.group(3).strip()
                })
            
            if timeline_rows:
                tables['Aufenthaltszeitlinie'] = pd.DataFrame(timeline_rows)
        
        # 3. Empfohlene Serologie
        serology_match = re.search(
            r'## Empfohlene Serologie(.*?)(?=\n## |\Z)',
            content,
            re.DOTALL
        )
        
        if serology_match:
            serology_section = serology_match.group(1)
            serology_items = []
            
            for line in serology_section.split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    # - **Pathogen** ( Priorität, Gründe)
                    match = re.match(r'-\s*\*\*(.+?)\*\*\s*\((.+?)\)', line)
                    if match:
                        serology_items.append({
                            'Pathogen': match.group(1),
                            'Details': match.group(2)
                        })
            
            if serology_items:
                tables['Empfohlene Serologie'] = pd.DataFrame(serology_items)
        
        return tables


class PostinfectiousExporter(AnalysisExporter):
    """Exporter für postinfectious Diagnose-Analysen."""
    
    def __init__(self):
        super().__init__('postinfectious')
    
    def extract_tables_from_file(self, file_path):
        """Extrahiert Tabellen aus postinfectious Ausgabe."""
        import pandas as pd
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tables = {}
        
        # Suche nach Markdown-Tabellen (| Syntax)
        current_header = None
        in_table = False
        table_lines = []
        
        lines = content.split('\n')
        
        for line in lines:
            stripped = line.strip()
            
            # Überschrift
            if stripped.startswith('#'):
                if in_table and table_lines:
                    df = self._parse_markdown_table(table_lines)
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
                    df = self._parse_markdown_table(table_lines)
                    if df is not None and current_header:
                        tables[current_header] = df
                    table_lines = []
                    in_table = False
        
        # Letzte Tabelle
        if in_table and table_lines:
            df = self._parse_markdown_table(table_lines)
            if df is not None and current_header:
                tables[current_header] = df
        
        return tables
    
    @staticmethod
    def _parse_markdown_table(table_lines):
        """Konvertiert Markdown-Tabellenzeilen in DataFrame."""
        import pandas as pd
        from io import StringIO
        
        if not table_lines or len(table_lines) < 2:
            return None
        
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


class AcuteResponseExporter(AnalysisExporter):
    """Exporter für acute_response Analysen."""
    
    def __init__(self):
        super().__init__('acute_response')
    
    def extract_tables_from_file(self, file_path):
        """Extrahiert Tabellen aus acute_response Ausgabe."""
        import pandas as pd
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tables = {}
        
        # Suche nach Tabellen und Listen
        # NEWS2-Scores
        news_pattern = r'NEWS2-(Lite)?\s*Score:\s*(\d+)'
        news_matches = re.findall(news_pattern, content)
        
        if news_matches:
            scores = [{'Typ': m[0] or 'Standard', 'Score': int(m[1])} for m in news_matches]
            tables['NEWS2-Scores'] = pd.DataFrame(scores)
        
        # Vitaldaten-Entwicklung
        vital_pattern = r'(\d{4}-\d{2}-\d{2}):\s*([^\n]+)'
        vital_matches = re.findall(vital_pattern, content)
        
        if vital_matches:
            vital_data = [{'Datum': m[0], 'Werte': m[1]} for m in vital_matches]
            tables['Vitaldaten-Entwicklung'] = pd.DataFrame(vital_data)
        
        # Empfohlene Maßnahmen
        measures_match = re.search(
            r'## Empfohlene Maßnahmen(.*?)(?=\n## |\Z)',
            content,
            re.DOTALL
        )
        
        if measures_match:
            measures_section = measures_match.group(1)
            measures = []
            
            for line in measures_section.split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    measures.append({'Maßnahme': line[2:]})
            
            if measures:
                tables['Empfohlene Maßnahmen'] = pd.DataFrame(measures)
        
        return tables


def export_single_analysis(analysis_type):
    """Exportiert eine einzelne Analyse."""
    print(f"\n{'='*60}")
    print(f"  Exporte {analysis_type}")
    print(f"{'='*60}")
    
    exporter_map = {
        'outbreak_exposure': OutbreakExposureExporter,
        'pathogen_exposure': PathogenExposureExporter,
        'postinfectious': PostinfectiousExporter,
        'acute_response': AcuteResponseExporter,
    }
    
    if analysis_type not in exporter_map:
        print(f"  Unsupported analysis type: {analysis_type}")
        return False
    
    exporter = exporter_map[analysis_type]()
    count = exporter.process_all()
    
    if count > 0:
        exporter.save_to_ods()
    else:
        print(f"  Keine Tabellen für {analysis_type} gefunden")
    
    return count > 0


def export_all_analyses():
    """Exportiert alle Infektionsanalysen."""
    print("\n" + "="*60)
    print("  Exporte ALLE Infektionsanalysen")
    print("="*60)
    
    all_tables = {}
    
    for analysis_type, ExporterClass in [
        ('outbreak_exposure', OutbreakExposureExporter),
        ('pathogen_exposure', PathogenExposureExporter),
        ('postinfectious', PostinfectiousExporter),
        ('acute_response', AcuteResponseExporter),
    ]:
        exporter = ExporterClass()
        count = exporter.process_all()
        
        if count > 0:
            # Tabellen mit Präfix speichern
            for name, df in exporter.tables.items():
                prefix = analysis_type[:4].upper()
                new_name = f"{prefix} - {name}"[:31]
                all_tables[new_name] = df
    
    # Kombinierte Datei speichern
    if all_tables:
        output_path = PROJECT_ROOT / "analyses" / "infectious_analysen_kombiniert.ods"
        
        try:
            import pandas as pd
            with pd.ExcelWriter(output_path, engine='odf') as writer:
                for sheet_name, df in all_tables.items():
                    clean_name = AnalysisExporter._clean_sheet_name(sheet_name)
                    df.to_excel(writer, sheet_name=clean_name, index=False)
            print(f"\n✓ Kombinierte Datei gespeichert: {output_path}")
        except ImportError:
            print("  odfpy nicht verfügbar")
    
    # Einzelne Dateien auch speichern
    for analysis_type in ['outbreak_exposure', 'pathogen_exposure', 'postinfectious', 'acute_response']:
        export_single_analysis(analysis_type)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Exportiert Infektionsanalysen als OpenOffice-Tabellen',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python3 export_analyses_to_ods.py                    # Alle Analysen
  python3 export_analyses_to_ods.py --type outbreak_exposure  # Nur outbreak_exposure
  python3 export_analyses_to_ods.py --recent-only    # Nur letzte 7 Tage
  python3 export_analyses_to_ods.py --output mein_output.ods

Ausgabe-Verzeichnisse:
  - analyses/infectious/ (outbreak_exposure, pathogen_exposure, acute_response)
  - analyses/postinfectious/
        """
    )
    parser.add_argument('--type', choices=['outbreak_exposure', 'pathogen_exposure', 'postinfectious', 'acute_response', 'all'],
                        default='all', help='Typ der Analyse')
    parser.add_argument('--recent-only', action='store_true',
                        help='Nur Dateien der letzten 7 Tage')
    parser.add_argument('--output', '-o',
                        help='Ausgabedatei (für Einzelanalyse)')
    
    args = parser.parse_args()
    
    # Abhängigkeiten prüfen
    if not ensure_dependencies():
        sys.exit(1)
    
    # Standard-Days für "recent" anpassen
    if args.recent_only:
        # Überschreibe in den Exporter-Klassen
        AnalysisExporter.get_recent_files = lambda self, days=7, max_files=5: \
            super(AnalysisExporter, self).get_recent_files(days, max_files)
    
    if args.type == 'all':
        export_all_analyses()
    else:
        export_single_analysis(args.type)
    
    print("\n" + "="*60)
    print("✓ Fertig! Alle Tabellen wurden erstellt.")
    print("="*60)
    print("Öffne die .ods-Dateien mit LibreOffice Calc für:")
    print("  • Sortieren")
    print("  • Filtern")
    print("  • Analysieren")
    print("="*60)


if __name__ == '__main__':
    main()
