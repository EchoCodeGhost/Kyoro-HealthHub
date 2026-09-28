#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Hilo/Aktiia PDF-Blutdruckberichte → health.db

@tier        infrastructure
@purpose.de  Liest monatliche PDF-Berichte der Hilo-App (Aktiia Wrist BP)
             und schreibt die enthaltenen Handgelenks-Blutdruckmessungen in
             die Tabelle blood_pressure. Doppelt-Spalten-Layout (zwei
             Messdatensätze pro Zeile) wird automatisch aufgelöst.
@purpose.en  Reads monthly PDF reports from the Hilo app (Aktiia Wrist BP)
             and writes the contained wrist blood pressure measurements into
             the blood_pressure table. Dual-column layout (two measurement
             records per line) is automatically resolved.
@method.de   pdfplumber extrahiert Wörter mit Koordinaten. Zeilen werden
             nach Y-Position (Toleranz 3 pt) gruppiert. Jede Zeile enthält
             zwei Datensätze à 7 Tokens: DD. Monat, JJ + HH:MM + SBP + DBP + HR.
             Datum wird von Lokalzeit (cfg.home_timezone) nach UTC konvertiert.
@method.en   pdfplumber extracts words with coordinates. Lines are grouped
             by Y-position (tolerance 3 pt). Each line holds two records of
             7 tokens: DD. Month, YY + HH:MM + SBP + DBP + HR.
             Date is converted from local time (cfg.home_timezone) to UTC.
@reads       blood_pressure (MAX(date) für --update-Modus)
@writes      blood_pressure: ts TEXT, date TEXT, systolic INTEGER,
             diastolic INTEGER, pulse INTEGER, device_id TEXT,
             person TEXT, source TEXT
             hilo_monthly_summary: report_month TEXT, context TEXT,
             sys_mean INTEGER, dia_mean INTEGER, hr_mean INTEGER,
             sys_sd REAL, dia_sd REAL, hr_sd REAL,
             sys_max INTEGER, dia_max INTEGER, hr_max INTEGER,
             sys_min INTEGER, dia_min INTEGER, hr_min INTEGER,
             measurement_count INTEGER, person TEXT, source TEXT
@limits.de   Kein Zugriff auf rohe PPG-Wellenformen — nur Aggregatwerte.
             Messmodus (Kalibrierung vs. regulär) wird im PDF nicht als
             eigene Spalte geliefert; alle Einträge erhalten source='hilo_pdf'.
             Seitenformat: Seite 1 (Übersicht) wird für Monatsstatistiken genutzt.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No access to raw PPG waveforms — aggregate values only.
             Measurement mode (calibration vs. regular) is not a separate
             column in the PDF; all entries receive source='hilo_pdf'.
             Page layout: page 1 (summary) is used for monthly statistics.
@usage
    python3 import_hilo_pdf.py
    python3 import_hilo_pdf.py --update
    python3 import_hilo_pdf.py --file pfad/bericht.pdf
    python3 import_hilo_pdf.py --inbox
"""

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import

_cfg = _Cfg()

# Verzeichnisse
DB_PATH = _cfg.db_path
HILO_DIR = _cfg.data_root / "hilo"
HILO_DIR.mkdir(parents=True, exist_ok=True)
INBOX_DIR = _cfg.data_root / "_inbox"

# Deutsche Monatsnamen für Parsing
DE_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "dezember": 12
}

# Timezone für Deutschland/Schweiz
TZ = ZoneInfo(_cfg.home_timezone)

# Schema für Monatszusammenfassung
_SUMMARY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS hilo_monthly_summary (
    report_month      TEXT NOT NULL,
    context           TEXT NOT NULL,
    sys_mean          INTEGER,
    dia_mean          INTEGER,
    hr_mean           INTEGER,
    sys_sd            REAL,
    dia_sd            REAL,
    hr_sd             REAL,
    sys_max           INTEGER,
    dia_max           INTEGER,
    hr_max            INTEGER,
    sys_min           INTEGER,
    dia_min           INTEGER,
    hr_min            INTEGER,
    measurement_count INTEGER,
    person            TEXT NOT NULL DEFAULT 'unknown',
    source            TEXT DEFAULT 'hilo_pdf',
    PRIMARY KEY (report_month, context, person)
);
"""


def device_id_for_source(source: str) -> str | None:
    """Sucht Device-ID im device_registry nach source-Feld."""
    for device in _cfg.device_registry:
        if device.get("source") == source:
            return device.get("device_id") or device.get("id")
    return None


def get_device_id() -> str:
    """Ermittelt die Device-ID für Hilo/Aktiia."""
    return device_id_for_source("hilo") or "aktiia_wrist"


def parse_summary(pdf_path: Path) -> list[dict]:
    """Extrahiert die Monatszusammenfassung von Seite 1 der Hilo-PDF."""
    import pdfplumber
    import re

    MONTHS_DE = {
        'januar':1,'februar':2,'märz':3,'april':4,'mai':5,'juni':6,
        'juli':7,'august':8,'september':9,'oktober':10,'november':11,'dezember':12
    }
    CONTEXTS = ['day', 'night', 'all']
    _ROWS = ['mean', 'sd', 'max', 'min', 'count']  # noqa: F841

    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()

    # report_month aus "Monatsbericht Juli, 2026"
    m = re.search(r'Monatsbericht\s+(\w+),?\s+(\d{4})', text, re.IGNORECASE)
    if not m:
        return []
    month_num = MONTHS_DE.get(m.group(1).lower())
    year = int(m.group(2))
    if not month_num:
        return []
    report_month = f'{year:04d}-{month_num:02d}'

    # Tabelle: fünf Zeilen mit je 9 Zahlen (3 Kontexte × 3 Metriken)
    # Jede Zeile beginnt mit Mittelwert/SD/Max/Mindest/Messungen
    row_patterns = [
        (r'Mittelwert\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', 'mean'),
        (r'SD\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',           'sd'),
        (r'Max\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',          'max'),
        (r'Mindest\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',      'min'),
        (r'Messungen\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',    'count'),
    ]

    # Werte pro Kontext sammeln
    data = {ctx: {} for ctx in CONTEXTS}
    for pattern, row_key in row_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        vals = [float(g) for g in match.groups()]
        # Reihenfolge: sys_day dia_day hr_day  sys_night dia_night hr_night  sys_all dia_all hr_all
        for i, ctx in enumerate(CONTEXTS):
            data[ctx][row_key] = {
                'sys': vals[i*3],
                'dia': vals[i*3+1],
                'hr':  vals[i*3+2],
            }

    rows = []
    for ctx in CONTEXTS:
        d = data[ctx]
        if not d:
            continue
        rows.append({
            'report_month': report_month,
            'context':      ctx,
            'sys_mean':     int(d.get('mean',{}).get('sys', 0)) or None,
            'dia_mean':     int(d.get('mean',{}).get('dia', 0)) or None,
            'hr_mean':      int(d.get('mean',{}).get('hr',  0)) or None,
            'sys_sd':       d.get('sd',{}).get('sys'),
            'dia_sd':       d.get('sd',{}).get('dia'),
            'hr_sd':        d.get('sd',{}).get('hr'),
            'sys_max':      int(d.get('max',{}).get('sys', 0)) or None,
            'dia_max':      int(d.get('max',{}).get('dia', 0)) or None,
            'hr_max':       int(d.get('max',{}).get('hr',  0)) or None,
            'sys_min':      int(d.get('min',{}).get('sys', 0)) or None,
            'dia_min':      int(d.get('min',{}).get('dia', 0)) or None,
            'hr_min':       int(d.get('min',{}).get('hr',  0)) or None,
            'measurement_count': int(d.get('count',{}).get('sys', 0)) or None,
        })
    return rows


def parse_date(date_str: str) -> str | None:
    """Parsed 'D. Monat, JJ' → 'YYYY-MM-DD'. Beispiele: '23. Juni, 26' → '2026-06-23'"""
    try:
        # Regex für Datumsformat: optional Punkt nach Tag, optional Komma nach Monat
        match = re.match(
            r'(\d{1,2})\.?\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember),?\s+(\d{2})',
            date_str.strip()
        )
        if not match:
            return None
        
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year_short = int(match.group(3))
        
        # Jahr 2000 + short_year (26 → 2026)
        year = 2000 + year_short
        month = DE_MONTHS.get(month_name)
        
        if not month or year < 2000 or year > 2100:
            return None
            
        return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception:
        return None


def parse_time(time_str: str) -> str | None:
    """Parsed 'HH:MM' → 'HH:MM:SS'"""
    try:
        s = time_str.strip()
        if len(s) == 5:  # HH:MM
            s += ":00"
        elif len(s) != 8:  # HH:MM:SS
            return None
        return s
    except Exception:
        return None



def _group_words_into_rows(words: list[dict], y_tolerance: float = 3) -> list[list[str]]:
    """Gruppiert Wörter nach Y-Position in Zeilen."""
    if not words:
        return []
    
    # Nach Y-Position sortieren
    words_sorted = sorted(words, key=lambda w: w['top'])
    
    rows = []
    current_row = [words_sorted[0]]
    
    for word in words_sorted[1:]:
        # Prüfen, ob Wort zur aktuellen Zeile gehört (ähnliche Y-Position)
        if abs(word['top'] - current_row[0]['top']) <= y_tolerance:
            current_row.append(word)
        else:
            # Neue Zeile beginnen
            if current_row:
                rows.append(current_row)
            current_row = [word]
    
    if current_row:
        rows.append(current_row)
    
    # Jede Zeile nach X-Position sortieren und Texte extrahieren
    return [[w['text'] for w in sorted(row, key=lambda w: w['x0'])] for row in rows]


def parse_pdf(pdf_path: Path) -> list[dict]:
    """Extrahiert alle Messdaten aus einer Hilo-PDF. Gibt Liste von Dicts zurück."""
    import pdfplumber
    
    records = []
    skipped_rows = 0
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Seite 0 ist Übersicht → überspringen, beginnen mit Seite 1
            for page in pdf.pages[1:]:
                words = page.extract_words()
                if not words:
                    continue
                
                # Wörter nach Y-Position gruppieren (Zeilen erkennen)
                rows = _group_words_into_rows(words, y_tolerance=3)
                
                for row in rows:
                    # Header-Zeilen überspringen
                    if not row or len(row) < 3:
                        continue
                        
                    first_token = row[0].strip().lower()
                    if first_token in {'datum', 'blutdruck-', '⊕', 'dieser', 'kalibrierung', 'diese'}:
                        continue
                    
                    # Jede Zeile enthält zwei Datensätze: links und rechts
                    # Format: DATUM UHRZEIT SBP DBP HR DATUM UHRZEIT SBP DBP HR
                    # Wir teilen die Zeile in der Mitte
                    
                    for half_idx in [0, 1]:
                        # Jeder Datensatz besteht aus 7 Elementen: 3 für Datum + 1 für Zeit + 3 für Werte
                        # Erster Datensatz: Indizes 0-6, zweiter Datensatz: Indizes 7-13
                        start_idx = half_idx * 7
                        end_idx = start_idx + 7
                        
                        if end_idx > len(row):
                            continue
                        
                        half_row = row[start_idx:end_idx]
                        
                        # Versuchen, Datum zu parsen (Spalten 0-2 des Halbdatensatzes kombinieren)
                        # Format: ['23', 'Juni,', '26'] → "23 Juni, 26"
                        if len(half_row) >= 3:
                            date_str = f"{half_row[0]} {half_row[1]} {half_row[2]}"
                        else:
                            date_str = half_row[0] if len(half_row) > 0 else ""
                        date_iso = parse_date(date_str)
                        
                        if not date_iso:
                            skipped_rows += 1
                            continue
                        
                        # Zeit parsen (Spalte 3, da Spalten 0-2 das Datum sind)
                        time_str = half_row[3] if len(half_row) > 3 else ""
                        time_iso = parse_time(time_str)
                        
                        if not time_iso:
                            skipped_rows += 1
                            continue
                        
                        # Messwerte parsen (Spalten 4-6: SBP, DBP, HR, da Spalten 0-2 Datum und 3 Zeit sind)
                        try:
                            sbp = int(half_row[4].strip()) if len(half_row) > 4 and half_row[4].strip() else None
                            dbp = int(half_row[5].strip()) if len(half_row) > 5 and half_row[5].strip() else None
                            hr = int(half_row[6].strip()) if len(half_row) > 6 and half_row[6].strip() else None
                        except ValueError:
                            skipped_rows += 1
                            continue
                        
                        if sbp is None or dbp is None or hr is None:
                            skipped_rows += 1
                            continue
                        
                        # Messmodus ist standardmäßig 'wrist' für PDF-Daten
                        # (Icons sind in der PDF nicht als separate Spalte vorhanden)
                        measurement_mode = 'wrist'
                        
                        # Zeitstempel erstellen (Lokalzeit → UTC)
                        local_dt_str = f"{date_iso} {time_iso}"
                        local_dt = datetime.strptime(local_dt_str, "%Y-%m-%d %H:%M:%S")
                        local_dt = local_dt.replace(tzinfo=TZ)
                        ts_utc = local_dt.astimezone(timezone.utc).isoformat()
                        
                        records.append({
                            'ts': ts_utc,
                            'date': date_iso,
                            'systolic': sbp,
                            'diastolic': dbp,
                            'pulse': hr,
                            'measurement_mode': measurement_mode
                        })
    
    except Exception as e:
        print(f"Fehler beim Parsen von {pdf_path}: {e}")
        raise
    
    if skipped_rows > 0:
        print(f"  {skipped_rows} Zeilen übersprungen (ungültiges Format)")
    
    return records


def get_last_import(conn) -> str | None:
    """Ermittelt das Datum des letzten Imports aus der blood_pressure-Tabelle."""
    r = conn.execute(
        "SELECT MAX(date) FROM blood_pressure WHERE person=? AND source='hilo_pdf'",
        (OWN_PERSON_ID,)
    ).fetchone()
    return r[0] if r and r[0] else None


def import_pdf(conn, pdf_path: Path, update_from: str | None) -> int:
    """Importiert eine PDF in die DB. Gibt Anzahl eingefügter Zeilen zurück."""
    records = parse_pdf(pdf_path)
    if not records:
        print(f"  Keine gültigen Messdaten in {pdf_path.name} gefunden")
        return 0
    
    # Filter für Update-Modus
    if update_from:
        records = [r for r in records if r['date'] >= update_from]
    
    if not records:
        print(f"  Keine neuen Messdaten ab {update_from} in {pdf_path.name}")
        return 0
    
    # Device-ID ermitteln
    device_id = get_device_id()
    
    # Daten für DB vorbereiten
    rows = [(
        r['ts'], r['date'],
        r['systolic'], r['diastolic'], r['pulse'],
        None, None, None,  # ihb_flag, afib_possible, truread
        None, None,        # symptoms, movement
        None,              # cuff_ok
        device_id,        # device_id
        None,             # notes
        OWN_PERSON_ID,
        'hilo_pdf'
    ) for r in records]
    
    # In Datenbank einfügen
    conn.executemany("""
        INSERT OR IGNORE INTO blood_pressure
        (ts, date, systolic, diastolic, pulse,
         ihb_flag, afib_possible, truread, symptoms, movement,
         cuff_ok, device_id, notes, person, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    
    # Monatszusammenfassung
    conn.executescript(_SUMMARY_SCHEMA_SQL)
    summary_rows = parse_summary(pdf_path)
    for s in summary_rows:
        conn.execute("""
            INSERT OR IGNORE INTO hilo_monthly_summary
            (report_month, context, sys_mean, dia_mean, hr_mean,
             sys_sd, dia_sd, hr_sd, sys_max, dia_max, hr_max,
             sys_min, dia_min, hr_min, measurement_count, person, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            s['report_month'], s['context'],
            s['sys_mean'], s['dia_mean'], s['hr_mean'],
            s['sys_sd'],   s['dia_sd'],   s['hr_sd'],
            s['sys_max'],  s['dia_max'],  s['hr_max'],
            s['sys_min'],  s['dia_min'],  s['hr_min'],
            s['measurement_count'],
            OWN_PERSON_ID, 'hilo_pdf'
        ))
    
    count = len(rows)
    if summary_rows:
        count += conn.execute(
            "SELECT COUNT(*) FROM hilo_monthly_summary WHERE report_month=? AND person=?",
            (summary_rows[0]['report_month'], OWN_PERSON_ID)
        ).fetchone()[0]
    
    log_import(conn, 'hilo_pdf', str(pdf_path), count)
    conn.commit()
    
    return count


def list_inbox_pdfs() -> list[Path]:
    """Gibt alle Hilo-PDFs aus dem Inbox-Verzeichnis zurück."""
    return sorted(INBOX_DIR.glob("Hilo*.pdf"))


def move_to_processed(pdf: Path) -> None:
    """Verschiebt eine verarbeitete PDF nach _inbox/processed/."""
    processed_dir = INBOX_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    target = processed_dir / f"{pdf.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{pdf.suffix}"
    pdf.rename(target)


def main():
    parser = argparse.ArgumentParser(description=t("Hilo/Aktiia PDF → health.db", "Hilo/Aktiia PDF → health.db"))
    parser.add_argument("--file", help=t("Bestimmte PDF-Datei", "Specific PDF file"))
    parser.add_argument("--inbox", action="store_true", help=t("Verarbeite _inbox/Hilo*.pdf", "Process _inbox/Hilo*.pdf"))
    parser.add_argument("--update", action="store_true", help=t("Nur neue Daten", "Only new data"))
    add_lang_arg(parser)
    
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    
    update_from = None
    if args.update:
        last = get_last_import(conn)
        if last:
            from datetime import timedelta
            d = datetime.strptime(last, "%Y-%m-%d")
            update_from = (d + timedelta(days=1)).strftime("%Y-%m-%d")
            print(t(f"Update-Modus: ab {update_from}", f"Update mode: from {update_from}"))
    
    # Dateien ermitteln
    if args.file:
        files = [Path(args.file)]
    elif args.inbox:
        files = list_inbox_pdfs()
    else:
        files = sorted(HILO_DIR.glob("*.pdf"))

    if not files:
        if args.inbox:
            print(t(f"Keine Hilo-PDFs in {INBOX_DIR}", f"No Hilo PDFs in {INBOX_DIR}"))
        else:
            print(t(f"Keine PDF-Dateien in {HILO_DIR}", f"No PDF files in {HILO_DIR}"))
        return

    total = 0
    for f in files:
        print(f"  {f.name} ...", flush=True)
        try:
            n = import_pdf(conn, f, update_from)
            total += n
            print(t(f"    {n} Einträge", f"    {n} entries"))
            if args.inbox:
                move_to_processed(f)
        except Exception as e:
            print(f"    Fehler: {e}")
    
    # Statistik anzeigen
    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date),"
        " ROUND(AVG(systolic),1), ROUND(AVG(diastolic),1),"
        " ROUND(AVG(pulse),1)"
        " FROM blood_pressure WHERE person=? AND source='hilo_pdf'",
        (OWN_PERSON_ID,)
    ).fetchone()
    
    print(t("\n── Hilo Blutdruck ──────────────────────────────────────────────", "\n── Hilo blood pressure ─────────────────────────────────────────"))
    print(t(f"  Gesamt: {r[0]} Messungen | {r[1]} – {r[2]}", f"  Total: {r[0]} measurements | {r[1]} – {r[2]}"))
    print(f"  ∅ {r[3]}/{r[4]} mmHg, {r[5]} bpm")
    
    conn.close()


if __name__ == "__main__":
    main()