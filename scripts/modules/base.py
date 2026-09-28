#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
base.py — Gemeinsame Hilfsfunktionen für Importer

@tier        infrastructure
@purpose.de  Stellt gemeinsame Hilfsfunktionen und Primitiven für Importer bereit.
             Dokumentiert in CLAUDE.md.
@purpose.en  Provides common utility functions and primitives for importers.
             Documented in CLAUDE.md.
@method.de   Enthält: ImportResult (standardisierter Rückgabewert), resolve_person()
             (Person-ID aus Argument oder Standard), resolve_timezone() (IANA-Zeitzone),
             local_date() (UTC → lokales Datum), log_import() (forensisch sicherer Log).
@method.en   Contains: ImportResult (standardized return value), resolve_person()
             (person ID from argument or default), resolve_timezone() (IANA timezone),
             local_date() (UTC → local date), log_import() (forensic-safe logging).
@reads       persons Tabelle (für resolve_timezone)
@writes      import_log Tabelle (über log_import)

@limits.de   Internes Hilfsmodul. Aenderungen der Signaturen brechen alle Importer.

@relevance.de  Bietet Grundfunktionen für die Modulstruktur, essentiell für die Systemarchitektur
@relevance.en  Provides base functions for module structure, essential for system architecture
@limits.en   Internal helper module. Signature changes break all importers.
@usage
    python base.py
    python base.py --help
    python base.py --from 2024-01-01 --to 2024-12-31
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import subprocess
from modules.db import DB_OPERATIONAL_ERRORS
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from timezonefinder import TimezoneFinder as _TZF
    _tzf = _TZF()
except ImportError:
    _tzf = None

_REPO_ROOT = Path(__file__).resolve().parents[2]
_git_commit_cache: "str | None | bool" = False  # False = noch nicht ermittelt


def _git_commit_hash() -> "str | None":
    """Aktueller Git-Commit-Hash des Repos, fuer log_import()/compute_log/analysis_log.

    Wird einmal pro Prozess ermittelt und gecacht. None, wenn kein Git-Repo
    verfuegbar ist (z.B. Quell-Tarball ohne .git). Urspruenglich in
    modules/pipeline_runner.py, hierher verschoben, damit log_import() (in-process
    aufgerufen von Importer-/Migrationsskripten) und pipeline_runner.py
    (Subprozess-Ebene fuer compute_all.py/analyse_all.py) denselben, einmal
    gecachten Wert nutzen statt zwei unabhaengige git-rev-parse-Implementierungen
    auseinanderlaufen zu lassen.
    """
    global _git_commit_cache
    if _git_commit_cache is False:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT,
                capture_output=True, text=True, timeout=5,
            )
            _git_commit_cache = result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            _git_commit_cache = None
    return _git_commit_cache


def tz_from_coords(lat: float, lon: float) -> str | None:
    """IANA-Timezone aus GPS-Koordinaten (offline, via timezonefinder). None falls nicht installiert."""
    if _tzf is None:
        return None
    return _tzf.timezone_at(lat=lat, lng=lon)


@dataclass
class ImportResult:
    source: str
    rows_inserted: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        parts = [f"{self.source}: {self.rows_inserted} inserted"]
        if self.rows_skipped:
            parts.append(f"{self.rows_skipped} skipped")
        if self.errors:
            parts.append(f"{len(self.errors)} errors")
        return ", ".join(parts)


def resolve_person(person_arg: Optional[str] = None) -> str:
    """Return person_arg if set, else OWN_PERSON_ID from health_config."""
    if person_arg:
        return person_arg
    from health_config import get_own_person_id
    return get_own_person_id()


def resolve_timezone(conn: sqlite3.Connection, person: str,
                     default: str | None = None,
                     ts: Optional[str] = None) -> str:
    """Return IANA timezone for person at optional timestamp ts.

    Lookup order:
    1. location_stays: stay covering ts (if ts given) → travel-aware timezone
    2. persons table: home timezone
    3. default (if None: cfg.home_timezone, fallback UTC)
    """
    if ts:
        try:
            row = conn.execute("""
                SELECT timezone FROM location_stays
                WHERE person=? AND timezone IS NOT NULL
                  AND start_ts <= ? AND (end_ts IS NULL OR end_ts >= ?)
                ORDER BY start_ts DESC LIMIT 1
            """, (person, ts, ts)).fetchone()
            if row and row[0]:
                return row[0]
        except DB_OPERATIONAL_ERRORS:
            pass

    try:
        row = conn.execute(
            "SELECT timezone FROM persons WHERE person_id=? LIMIT 1", (person,)
        ).fetchone()
        if row and row[0]:
            return row[0]
    except DB_OPERATIONAL_ERRORS:
        pass

    if default is None:
        try:
            from health_config import Config
            default = Config().home_timezone
        except Exception:
            default = "UTC"
    return default


def local_date(ts_utc: str, tz_name: str | None = None) -> str:
    """Convert a UTC ISO-8601 timestamp string to a local calendar date string."""
    from zoneinfo import ZoneInfo
    if tz_name is None:
        try:
            from health_config import Config
            tz_name = Config().home_timezone
        except Exception:
            tz_name = "UTC"
    dt = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(tz_name)).date().isoformat()


_UNSET = object()  # unterscheidet "person nicht angegeben" von "explizit person=None"


def _compute_sha256_chunked(file_path: Path) -> str:
    """Berechne SHA-256-Hash einer Datei in Chunks, um Speicherverbrauch zu minimieren.
    
    Liest die Datei in 64KB-Chunks statt komplett in den Speicher zu laden.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)  # 64KB Chunks
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def _ensure_import_file_hashes_table(conn: sqlite3.Connection) -> None:
    """Stellt sicher, dass die import_file_hashes Tabelle existiert.
    
    Selbstheilung für Datenbanken, die vor dieser Erweiterung erstellt wurden.
    """
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS import_file_hashes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                import_log_id INTEGER NOT NULL REFERENCES import_log(id),
                file_path     TEXT NOT NULL,
                sha256        TEXT NOT NULL,
                file_size     INTEGER,
                file_mtime    TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_importfilehashes_log 
            ON import_file_hashes(import_log_id)
        """)
    except DB_OPERATIONAL_ERRORS:
        # Tabelle existiert bereits oder sonstiger Fehler - ignorieren
        pass


def log_import(conn: sqlite3.Connection, source: str, data_path: str,
               rows_inserted: int, rows_skipped: int = 0,
               person: "str | None | object" = _UNSET) -> None:
    """Schreibt einen import_log-Eintrag in derselben Transaktion wie die importierten Daten.

    Muss VOR conn.commit() aufgerufen werden — nur so ist der Log-Eintrag
    atomar mit den Daten und forensisch belastbar.

    person hat drei Zustaende, nicht zwei:
    - nicht angegeben (bestehende Aufrufer, unveraendert durch diese Erweiterung):
      faellt ueber resolve_person() auf OWN_PERSON_ID zurueck — korrekter Standard
      fuer eine Einzelperson-Installation.
    - ein echter person_id-String: wird so gespeichert (Aufrufer kennt die
      betroffene Person explizit, z.B. via --person-Flag).
    - explizit person=None: wird als NULL gespeichert, NICHT auf OWN_PERSON_ID
      zurueckgefallen. Fuer Skripte, die absichtlich personenuebergreifend
      arbeiten (z.B. pseudonymize_device_person_identifiers.py,
      dedupe_plaintext_device_ids.py) — dort waere OWN_PERSON_ID als Log-Wert
      schlicht falsch, da mehrere/unbekannte Personen betroffen sein koennen.
    git_commit wird automatisch erfasst (_git_commit_hash()), kein Parameter noetig.
    """
    _ensure_import_log_git_commit_column(conn)
    _ensure_import_file_hashes_table(conn)
    resolved_person = None if person is None else resolve_person(
        None if person is _UNSET else person
    )
    cursor = conn.execute(
        "INSERT OR IGNORE INTO import_log"
        " (ts_run, source, data_path, rows_inserted, rows_skipped, person, git_commit)"
        " VALUES (datetime('now'), ?, ?, ?, ?, ?, ?)",
        (source, str(data_path), rows_inserted, rows_skipped,
         resolved_person, _git_commit_hash()),
    )
    
    # Datei-Hashes für Chain-of-Custody (forensische Integrität)
    import_log_id = cursor.lastrowid  # lastrowid des gerade inserteten import_log
    
    # Prüfe data_path
    if not data_path:
        # Leerer String - nichts zu tun (viele Importer rufen mit leerem data_path auf)
        return
    
    data_path_obj = Path(data_path)
    
    # Fall 1: data_path existiert nicht
    if not data_path_obj.exists():
        return
    
    # Fall 2: data_path ist eine einzelne Datei
    if data_path_obj.is_file():
        files_to_hash = [data_path_obj]
    # Fall 3: data_path ist ein Verzeichnis - nur Dateien auf oberster Ebene (nicht rekursiv)
    elif data_path_obj.is_dir():
        files_to_hash = [f for f in data_path_obj.iterdir() if f.is_file()]
    else:
        # Sonstiger Fall (z.B. symlink, socket, etc.) - ignorieren
        return
    
    # Für jede Datei: SHA-256 berechnen und in import_file_hashes speichern
    for file_path in files_to_hash:
        try:
            # Hash berechnen
            sha256_hash = _compute_sha256_chunked(file_path)
            
            # Dateimetadaten
            stat = file_path.stat()
            file_size = stat.st_size
            file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            
            # In Datenbank speichern
            conn.execute(
                "INSERT INTO import_file_hashes (import_log_id, file_path, sha256, file_size, file_mtime)"
                " VALUES (?, ?, ?, ?, ?)",
                (import_log_id, str(file_path), sha256_hash, file_size, file_mtime)
            )
        except (OSError, PermissionError) as e:
            # Fehler beim Lesen der Datei - nicht den ganzen Import abbrechen
            logging.warning(f"Konnte Datei {file_path} nicht hashen: {e}")
        except Exception as e:
            # Sonstiger Fehler - loggen und weitermachen
            logging.warning(f"Unerwarteter Fehler beim Hashen von {file_path}: {e}")


def _ensure_import_log_git_commit_column(conn: sqlite3.Connection) -> None:
    """Selbstheilung fuer DBs, die vor dieser Erweiterung erstellt wurden.

    Analog zum bestehenden Muster in create_schema.py (_migrate_anamnese_findings_slug)
    und zum CREATE TABLE IF NOT EXISTS-Muster von compute_log — kein separates
    Migrationsskript noetig, das man vergessen kann auszufuehren.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(import_log)")}
    if "git_commit" not in cols:
        conn.execute("ALTER TABLE import_log ADD COLUMN git_commit TEXT")


# Rangfolge, wer bei zeitgleich erfassten Trainingseinheiten den
# training_load-Wert stellen darf. Garmin zuerst: eigener HF-basierter
# Trainingseffekt (Firstbeat), geraeteseitig einer konkreten Sportart
# zugeordnet. Polar danach: ebenfalls HF-basiert, aber teils automatisch
# erkannt (s. is_polar_auto_detected). Oura zuletzt: nur eine grobe
# Kalorien-Naeherung (s. import_oura_csv.py::_oura_training_load), kein
# eigenes HF-basiertes Load-Signal. Unbekannte/neue Quellen bekommen 0 und
# verlieren gegen jede bekannte Quelle.
TRAINING_LOAD_SOURCE_PRIORITY = {
    "garmin_connect": 3,
    "polar_connect": 2,
    "oura": 1,
}


def claim_training_load_slot(conn: sqlite3.Connection, person: str, session_id: str,
                              source_app: str, date: str, ts_start: str,
                              ts_end: "str | None") -> bool:
    """Entscheidet, ob diese Session einen eigenen training_load bekommen darf,
    und raeumt dafuer noetigenfalls das Feld.

    Prueft alle im selben Zeitfenster ueberlappenden Sessions, die entweder
    bereits training_load>0 tragen oder selbst als auto_detected=1 markiert
    sind (eine explizite "das ist kein Training"-Ablehnung zaehlt genauso wie
    ein Datenwert). Traegt eine ueberlappende Session eine GLEICH- oder
    HOEHERrangige Quelle (s. TRAINING_LOAD_SOURCE_PRIORITY), gibt diese
    Funktion False zurueck — diese Session bekommt keinen training_load.
    Traegt sie eine NIEDRIGERrangige Quelle, wird deren training_load
    geloescht (die neue, hoeherrangige Quelle verdraengt sie) und die
    Funktion gibt True zurueck.

    Das macht die Prioritaet unabhaengig von der Importreihenfolge: kommt
    Garmins Aufzeichnung erst NACH einer bereits importierten Oura- oder
    (automatisch erkannten) Polar-Session fuer dasselbe Ereignis, verdraengt
    Garmin sie nachtraeglich, statt stumm zu verlieren.
    """
    my_priority = TRAINING_LOAD_SOURCE_PRIORITY.get(source_app, 0)
    competitors = conn.execute("""
        SELECT s.id, s.source_app FROM sessions s
        WHERE s.type = 'training' AND s.person = ? AND s.id != ?
          AND s.date BETWEEN date(?, '-1 day') AND date(?, '+1 day')
          AND s.ts_start < ? AND (s.ts_end > ? OR s.ts_end IS NULL)
          AND (
            EXISTS (SELECT 1 FROM session_metrics tl
                    WHERE tl.session_id = s.id AND tl.metric = 'training_load')
            OR
            EXISTS (SELECT 1 FROM session_metrics ad
                    WHERE ad.session_id = s.id AND ad.metric = 'auto_detected' AND ad.value = 1.0)
          )
    """, (person, session_id, date, date, ts_end, ts_start)).fetchall()

    blocked = False
    for comp_id, comp_source in competitors:
        comp_priority = TRAINING_LOAD_SOURCE_PRIORITY.get(comp_source, 0)
        if comp_priority >= my_priority:
            blocked = True
        else:
            conn.execute(
                "DELETE FROM session_metrics WHERE session_id=? AND metric='training_load'",
                (comp_id,)
            )
    return not blocked
