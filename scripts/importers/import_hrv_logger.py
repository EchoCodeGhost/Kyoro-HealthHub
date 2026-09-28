#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
HRV Logger (A.S.M.A. B.V. / Marco Altini) → health.db

@tier        infrastructure
@purpose.de  Importiert RR-Intervall-Sessions aus HRV Logger-Exporten in die health.db.
             Die RR-Daten werden in ppi_raw (source='hrv_logger') gespeichert und
             stehen damit allen HRV-Berechnungen (compute_hrv_advanced.py) zur
             Verfügung.
@purpose.en  Imports RR interval sessions from HRV Logger exports into health.db.
             The RR data is stored in ppi_raw (source='hrv_logger') and is thus
             available to all HRV calculations (compute_hrv_advanced.py).
@method.de   Unterstützte Formate: HRV Logger CSV (Zeit(ms), RR(ms)) — Standard-Export,
             einfache Liste (eine RR-Zahl pro Zeile in ms), Kubios-kompatibel
             (.hrm/.txt mit RR-Werten). Session-Metadaten werden in hrv_logger_sessions
             gespeichert.
@method.en   Supported formats: HRV Logger CSV (Time(ms), RR(ms)) — standard export,
             simple list (one RR value per line in ms), Kubios-compatible
             (.hrm/.txt with RR values). Session metadata is stored in
             hrv_logger_sessions.
@reads       HRV Logger Export (CSV/TXT/HRM, Polar H7/H10 etc.)
@writes      health.db (ppi_raw, hrv_logger_sessions)
@limits.de   Keine Validierung der HRV-Datenqualität. Keine automatische
             Interpretation der HRV-Daten. Keine medizinische Diagnose.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No validation of HRV data quality. No automatic interpretation
             of HRV data. No medical diagnosis.
@usage
    python import_hrv_logger.py --file session.csv
    python import_hrv_logger.py --dir ~/Downloads/hrv_logger/
    python import_hrv_logger.py --file session.csv --dry-run
    python import_hrv_logger.py --file session.csv --tags "orthostase,morgen"
"""

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person
from modules.device_registry import device_for_date

DEVICE_CHEST_STRAP_FALLBACK = "hrv_logger_app"
_cfg = _Cfg()
DB_PATH = _cfg.db_path

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS hrv_logger_sessions (
    session_id    TEXT PRIMARY KEY,  -- YYYY-MM-DDTHH:MM:SS
    duration_s    INTEGER,           -- Aufnahmedauer in Sekunden
    n_beats       INTEGER,           -- Anzahl RR-Intervalle
    rmssd_ms      REAL,              -- RMSSD der Session (berechnet)
    mean_rr_ms    REAL,              -- mittleres RR
    mean_hr_bpm   REAL,              -- mittlere HR
    artifact_pct  REAL,              -- Anteil auffälliger RR-Sprünge
    device        TEXT,              -- Gerätename aus Datei-Header
    tags          TEXT,              -- Freitext-Tags
    notes         TEXT,              -- Notizen
    source        TEXT DEFAULT 'hrv_logger',
    wear_location TEXT,              -- Tragort, falls Sensor variiert (z.B. Verity Sense); NULL = unbekannt/Standard
    mode          TEXT               -- Aufzeichnungsmodus (z.B. 'schwimmen'); NULL = Standardmodus
)
"""


def _parse_header(lines: list[str]) -> tuple[str | None, str | None]:
    """Extrahiert Timestamp and devicesame from the File-Header."""
    dt = None
    device = None
    for line in lines[:20]:
        line = line.strip()
        # Timestamp: "Date: YYYY-MM-DD 09:15:00" or im Filenamen
        m = re.search(r'(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)', line)
        if m and dt is None:
            dt = f"{m.group(1)}T{m.group(2)}"
            if len(dt) == 16:
                dt += ":00"
        # Device
        m2 = re.search(r'[Dd]evice[:\s]+([^\n,]+)', line)
        if m2:
            device = m2.group(1).strip()
    return dt, device


def _datum_aus_dateiname(path: Path) -> str | None:
    """macOS-Screenshot-Muster and generische Timestamp-Namen."""
    # HRV Logger benennt oft: "HRV_Logger_YYYY-MM-DD_091500.csv"
    m = re.search(r'(\d{4}-\d{2}-\d{2})[_T](\d{2})[:\-_]?(\d{2})[:\-_]?(\d{2})?',
                  path.stem)
    if m:
        d = m.group(1)
        h, mi = m.group(2), m.group(3)
        s = m.group(4) or "00"
        return f"{d}T{h}:{mi}:{s}"
    # Fallback: File-Änderungszeit
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")


def parse_rr_file(path: Path) -> tuple[str, list[int], str | None]:
    """
    Liest RR-Intervall aus der File.
    Rückgabe: (session_datetime, rr_liste_ms, device_name)
    """
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.splitlines()

    dt, device = _parse_header(lines)
    if dt is None:
        dt = _datum_aus_dateiname(path)

    rr_values: list[int] = []

    # Format 1: CSV with zwei columns (Zeit_ms, RR_ms) or (Zeit_s, RR_ms)
    # Erkennung: erste Daten-Zeile hat zwei numerische Werte
    data_lines = [ln for ln in lines if re.match(r'^\s*[\d.]+\s*[,;\t]\s*[\d.]+', ln)]
    if len(data_lines) > 5:
        for line in data_lines:
            parts = re.split(r'[,;\t]', line.strip())
            if len(parts) >= 2:
                try:
                    rr = float(parts[1].strip())
                    # Plausibilitätscheck: 200–2500ms = 24–300 bpm
                    if 200 <= rr <= 2500:
                        rr_values.append(int(round(rr)))
                    elif 0.2 <= rr <= 2.5:
                        # seconds statt ms
                        rr_values.append(int(round(rr * 1000)))
                except ValueError:
                    pass
    else:
        # Format 2: Einfache Liste, eine Zahl pro Zeile
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or re.match(r'[A-Za-z]', line):
                continue
            try:
                rr = float(line.replace(',', '.'))
                if 200 <= rr <= 2500:
                    rr_values.append(int(round(rr)))
                elif 0.2 <= rr <= 2.5:
                    rr_values.append(int(round(rr * 1000)))
            except ValueError:
                pass

    return dt, rr_values, device


def _compute_stats(rr: list[int]) -> dict:
    """berechnet RMSSD, withtlere HR, Artifact-Rate."""
    if len(rr) < 2:
        return {}
    import math
    diffs = [abs(rr[i+1] - rr[i]) for i in range(len(rr)-1)]
    rmssd = math.sqrt(sum(d**2 for d in diffs) / len(diffs))
    mean_rr = sum(rr) / len(rr)
    # Artifact: Sprünge > 20% des vorigen RR
    artifacts = sum(1 for i in range(1, len(rr)) if abs(rr[i] - rr[i-1]) > 0.2 * rr[i-1])
    return {
        "rmssd_ms":     round(rmssd, 2),
        "mean_rr_ms":   round(mean_rr, 1),
        "mean_hr_bpm":  round(60000 / mean_rr, 1),
        "artifact_pct": round(artifacts / len(rr) * 100, 1),
    }


def _save(conn, session_dt: str, rr: list[int], device: str | None,
              tags: str, notes: str, dry_run: bool = False, person: str | None = None) -> bool:
    person = resolve_person(person)
    if not rr:
        print(t("  ⚠ Keine RR-Werte — übersprungen", "  ⚠ No RR values — skipped"))
        return False

    stats = _compute_stats(rr)
    duration_s = sum(rr) // 1000

    existing = conn.execute(
        "SELECT session_id FROM hrv_logger_sessions WHERE session_id = ?",
        (session_dt,)
    ).fetchone()
    if existing:
        print(t(f"  ↺ Session bereits vorhanden: {session_dt[:16]}", f"  ↺ Session already exists: {session_dt[:16]}"))
        return False

    if dry_run:
        print(t(f"  [DRY] {session_dt[:16]}  {len(rr)} Beats  "
                f"RMSSD={stats.get('rmssd_ms')} ms  "
                f"HR={stats.get('mean_hr_bpm')} bpm  "
                f"Dauer={duration_s//60}:{duration_s%60:02d} min",
                f"  [DRY] {session_dt[:16]}  {len(rr)} beats  "
                f"RMSSD={stats.get('rmssd_ms')} ms  "
                f"HR={stats.get('mean_hr_bpm')} bpm  "
                f"duration={duration_s//60}:{duration_s%60:02d} min"))
        return True

    # Session-Metadaten
    conn.execute("""
        INSERT INTO hrv_logger_sessions
          (session_id, duration_s, n_beats, rmssd_ms, mean_rr_ms, mean_hr_bpm,
           artifact_pct, device, tags, notes, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (session_dt, duration_s, len(rr),
          stats.get("rmssd_ms"), stats.get("mean_rr_ms"), stats.get("mean_hr_bpm"),
          stats.get("artifact_pct"), device, tags or None, notes or None,
          "hrv_logger"))

    # RR-Intervall in ppi_raw (source='hrv_logger')
    # Timestamp rekonstruieren: Session-Start + kumulative Summe der RR
    base = datetime.fromisoformat(session_dt)
    strap_device_id = device_for_date("chest_strap", session_dt[:10]) or DEVICE_CHEST_STRAP_FALLBACK
    cumulative_ms = 0
    rows = []
    for r in rr:
        ts = base + timedelta(milliseconds=cumulative_ms)
        rows.append((ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3], r, strap_device_id, "hrv_logger", person))
        cumulative_ms += r

    conn.executemany(
        "INSERT OR IGNORE INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?,?,?,?,?)",
        rows
    )
    if tags or notes:
        ts_end = (base + timedelta(milliseconds=cumulative_ms)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        conn.execute(
            "INSERT OR IGNORE INTO user_context"
            " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (f"hrv_logger:{session_dt}", session_dt[:10],
             session_dt, ts_end,
             person, 'hrv_logger', 'hrv_logger_app',
             tags or None, notes or None),
        )
    conn.commit()

    print(t(f"  ✓ {session_dt[:16]}  {len(rr)} Beats  "
            f"RMSSD={stats.get('rmssd_ms')} ms  HR≈{stats.get('mean_hr_bpm')} bpm  "
            f"Dauer={duration_s//60}:{duration_s%60:02d} min",
            f"  ✓ {session_dt[:16]}  {len(rr)} beats  "
            f"RMSSD={stats.get('rmssd_ms')} ms  HR≈{stats.get('mean_hr_bpm')} bpm  "
            f"duration={duration_s//60}:{duration_s%60:02d} min")
          + (t(f"  Artefakte={stats.get('artifact_pct')}%", f"  Artifacts={stats.get('artifact_pct')}%") if stats.get("artifact_pct", 0) > 5 else ""))
    return True


def main():
    """
    Hauptfunktion: Koordiniert den Import der HRV Logger-Daten.

    Command-Line-Argumente:
        --file: HRV-Logger CSV/TXT-Datei
        --dir: Ordner mit Sessions
        --tags: Kommaseparierte Tags (z. B. "orthostase,morgen,pem")
        --notes: Notizen zur Session
        --dry-run: Testlauf ohne Import
    """
    parser = argparse.ArgumentParser(description=t("HRV Logger RR-Daten importieren", "Import HRV Logger RR data"))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", metavar="DATEI",  help="HRV-Logger CSV/TXT")
    group.add_argument("--dir",  metavar="ORDNER", help="Folder with Sessions")
    parser.add_argument("--tags",    default="", metavar="TAGS",
                        help="Kommagetrennte days, e.g. orthostase,morgen,pem")
    parser.add_argument("--notes",   default="", metavar="TEXT")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    paths: list[Path] = []
    if args.file:
        paths = [Path(args.file)]
    else:
        d = Path(args.dir)
        for ext in ("*.csv", "*.txt", "*.hrm", "*.CSV", "*.TXT"):
            paths += sorted(d.glob(ext))

    if not paths:
        print(t("Keine Dateien gefunden.", "No files found."))
        return

    conn = open_db()
    row = conn.execute("SELECT type FROM sqlite_master WHERE name='hrv_logger_sessions'").fetchone()
    if row and row[0] == "view":
        conn.execute("DROP VIEW hrv_logger_sessions")
    conn.execute(CREATE_SESSIONS)
    conn.commit()

    neu = 0
    for p in paths:
        print(f"\n→ {p.name}", flush=True)
        dt, rr, device = parse_rr_file(p)
        if not rr:
            print(t("  ⚠ Keine RR-Werte erkannt", "  ⚠ No RR values detected"))
            continue
        if _save(conn, dt, rr, device, args.tags, args.notes,
                     dry_run=args.dry_run, person=person):
            neu += 1

    if not args.dry_run:
        log_import(conn, 'hrv_logger', str(paths[0].parent) if paths else '', neu, person=person)
        conn.commit()
    conn.close()
    print(t(f"\n{neu} Session(s) importiert", f"\n{neu} session(s) imported") + (" (DRY-RUN)" if args.dry_run else ""))
    if neu > 0 and not args.dry_run:
        print(t("HRV-Berechnung: python compute/compute_hrv_advanced.py",
                "HRV computation: python compute/compute_hrv_advanced.py"))


if __name__ == "__main__":
    main()
