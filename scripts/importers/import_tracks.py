#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_tracks.py — GPX → session_tracks (+ neue Sessions falls kein Match)

@tier        infrastructure
@purpose.de  Importiert GPX-Track-Daten in die session_tracks Tabelle und erstellt bei Bedarf neue Sessions
@purpose.en  Imports GPX track data into session_tracks table and creates new sessions if no match found
@method.de   Verarbeitet GPX-Dateien aus verschiedenen Quellen (Garmin GPSMAP, Polar Flow, Apple Health, Garmin InReach).
             Jede GPX-Datei wird einem bestehenden Training-Session ueber Zeitueberlappung (±30 min) zugeordnet.
             Falls kein Match: neue Session wird mit ID Format gpx_YYYY-MM-DD_stem angelegt.
             Track-Punkte werden bei >3000 Punkten downgesampelt. Koordinaten werden anonymisiert (round_coords).
@method.en   Processes GPX files from various sources (Garmin GPSMAP, Polar Flow, Apple Health, Garmin InReach).
             Each GPX file is matched to an existing training session via time overlap (±30 min).
             If no match: new session is created with ID format gpx_YYYY-MM-DD_stem.
             Track points are downsampled when exceeding 3000 points. Coordinates are anonymized (round_coords).
@reads       GPX-Dateien aus garmin_gpsmap, polar_gpx, apple_health_export/workout-routes, garmin_gdpr/INREACH Verzeichnissen
@writes      sessions, session_tracks, import_log
@limits.de   Abhaengig von GPX-Datei Struktur. Zeit-Matching funktioniert nur bei korrekter Timezone.
             Downsampling kann Details verlieren.
             run()/import_tracks_dir() reichten person schon vorher korrekt durch
             (Fallback: _main_person(conn)); main() hatte aber kein --person-Flag
             — jetzt ergaenzt.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Depends on GPX file structure. Time matching only works with correct timezone.
             Downsampling may lose details.
             run()/import_tracks_dir() already threaded person through correctly
             (fallback: _main_person(conn)); main() had no --person flag — now added.
@usage
    python import_tracks.py
    python import_tracks.py --dir /pfad/zu/gpx
    python import_tracks.py --person PER-xxxxxxxx
"""

import argparse
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import ImportResult, tz_from_coords, log_import
from utils.anonymize import round_coords

_cfg = _Cfg()

GPX_NS = {
    'gpx':   'http://www.topografix.com/GPX/1/1',
    'gpxtpx':'http://www.garmin.com/xmlschemas/TrackPointExtension/v1',
}
# Fallback: GPX 1.0
GPX_NS_10 = {'gpx': 'http://www.topografix.com/GPX/1/0'}

MATCH_WINDOW_S = 1800    # ±30 min in Lokalzeit
MAX_TRACK_PTS  = 3000    # downsample oberhalb dieser Schwelle
_TZ_FALLBACK = ZoneInfo(_cfg.home_timezone)

SPORT_HINTS = {
    'wandern': 'Wandern', 'hiking': 'Wandern', 'tag': 'Wandern',
    'laufen': 'Laufen', 'run': 'Laufen',
    'rad': 'Radfahren', 'cycling': 'Radfahren', 'bike': 'Radfahren',
    'swim': 'Schwimmen',
}


def _gpx_ns(root: ET.Element) -> str:
    """Return active namespace URI from root element."""
    tag = root.tag
    if tag.startswith('{'):
        return tag[1:tag.index('}')]
    return ''


def _parse_gpx(path: Path) -> tuple[list[dict], str, str]:
    """
    Parse GPX file → (points, track_name, creator).
    Each point: {lat, lon, ele, ts_utc (datetime)}
    """
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        return [], '', str(e)

    root = tree.getroot()
    ns = _gpx_ns(root)
    pfx = f'{{{ns}}}' if ns else ''

    creator = root.get('creator', '')
    name = ''
    for trk in root.iter(f'{pfx}trk'):
        name_el = trk.find(f'{pfx}name')
        if name_el is not None and name_el.text:
            name = name_el.text.strip()
        break

    points = []
    for trkpt in root.iter(f'{pfx}trkpt'):
        try:
            lat = float(trkpt.get('lat'))
            lon = float(trkpt.get('lon'))
        except (TypeError, ValueError):
            continue
        ele_el = trkpt.find(f'{pfx}ele')
        ele = float(ele_el.text) if ele_el is not None and ele_el.text else None
        time_el = trkpt.find(f'{pfx}time')
        if time_el is None or not time_el.text:
            continue
        ts_str = time_el.text.strip().rstrip('Z')
        try:
            ts = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if ts.year < 2000:   # GPS clock not set (Garmin epoch / device reset)
            continue
        points.append({'lat': lat, 'lon': lon, 'ele': ele, 'ts': ts})

    return points, name, creator


def _main_person(conn: sqlite3.Connection) -> str:
    """Return the primary person_id from the DB (device_user_id='u1')."""
    row = conn.execute(
        "SELECT person_id FROM persons WHERE device_user_id='u1' AND active=1 LIMIT 1"
    ).fetchone()
    if row:
        return row[0]
    # Fallback: most frequent person in training sessions
    row = conn.execute(
        "SELECT person, COUNT(*) FROM sessions WHERE type='training' "
        "GROUP BY person ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else OWN_PERSON_ID


def _sport_from_name(name: str, creator: str, path: Path) -> str | None:
    combined = (name + ' ' + path.stem + ' ' + creator).lower()
    for kw, sport in SPORT_HINTS.items():
        if kw in combined:
            return sport
    return None


def _match_session(conn: sqlite3.Connection, gpx_start: datetime, gpx_end: datetime,
                   person: str, tz: ZoneInfo | None = None) -> str | None:
    """Find best-matching training session by time overlap.

    GPX timestamps are UTC; Polar stores naive local time.
    Convert GPX to local naive time so SQLite julianday comparison is
    consistent (both are treated as the same clock face).
    Skip sessions created by this importer (source_app='gpx').
    """
    local_tz    = tz or _TZ_FALLBACK
    local_start = gpx_start.astimezone(local_tz).replace(tzinfo=None)
    local_str   = local_start.strftime('%Y-%m-%dT%H:%M:%S')
    date_s = local_start.strftime('%Y-%m-%d')
    d_prev = (local_start - timedelta(days=1)).strftime('%Y-%m-%d')
    d_next = (local_start + timedelta(days=1)).strftime('%Y-%m-%d')

    # julianday difference in seconds; exclude own GPX sessions from matching.
    # No person filter: OWN_PERSON_ID may differ from person IDs in existing sessions.
    rows = conn.execute("""
        SELECT id,
               ABS(julianday(ts_start) - julianday(?)) * 86400 AS diff_s
        FROM sessions
        WHERE type = 'training' AND source_app != 'gpx'
          AND date IN (?, ?, ?)
        ORDER BY diff_s ASC
        LIMIT 5
    """, (local_str, d_prev, date_s, d_next)).fetchall()

    for sid, diff_s in rows:
        if diff_s is not None and diff_s <= MATCH_WINDOW_S:
            return sid

    return None


def _ensure_session(conn: sqlite3.Connection, gpx_path: Path,
                    points: list[dict], name: str, creator: str,
                    person: str) -> tuple[str, bool]:
    """Return (session_id, created_new)."""
    gpx_start = points[0]['ts']
    gpx_end   = points[-1]['ts']

    # Timezone aus erstem Track-Punkt ableiten (reisebewusst)
    tz_name = tz_from_coords(points[0]['lat'], points[0]['lon'])
    tz      = ZoneInfo(tz_name) if tz_name else None

    sid = _match_session(conn, gpx_start, gpx_end, person, tz=tz)
    if sid:
        return sid, False

    # No match — create a new session
    sport = _sport_from_name(name, creator, gpx_path)
    date_s = gpx_start.strftime('%Y-%m-%d')
    ts_s   = gpx_start.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    ts_e   = gpx_end.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    stem   = gpx_path.stem.replace(' ', '_')[:40]
    new_id = f"gpx_{date_s}_{stem}"

    conn.execute(
        "INSERT OR IGNORE INTO sessions "
        "(id, type, ts_start, ts_end, date, device_id, person, source_app, sport) "
        "VALUES (?, 'training', ?, ?, ?, ?, ?, 'gpx', ?)",
        (new_id, ts_s, ts_e, date_s, creator[:40] or 'gpx', person, sport)
    )
    conn.commit()
    return new_id, True


def _downsample(points: list[dict], max_pts: int) -> list[dict]:
    if len(points) <= max_pts:
        return points
    step = len(points) / max_pts
    return [points[int(i * step)] for i in range(max_pts)]


def import_tracks_dir(conn: sqlite3.Connection, gpx_dir: Path,
                   person: str | None = None) -> ImportResult:
    result = ImportResult(source=f'gpx:{gpx_dir.name}')
    files = sorted(gpx_dir.glob('*.gpx'))
    if not files:
        return result

    if person is None:
        person = _main_person(conn)

    for gpx_path in files:
        points, name, creator = _parse_gpx(gpx_path)
        if len(points) < 2:
            result.rows_skipped += 1
            continue

        sid, is_new = _ensure_session(conn, gpx_path, points, name, creator, person)

        pts = _downsample(points, MAX_TRACK_PTS)
        rows = [
            (sid,
             p['ts'].strftime('%Y-%m-%dT%H:%M:%S+00:00'),
             round_coords(p['lat'], p['lon'], precision=5)[0] if p['lat'] is not None and p['lon'] is not None else None,
             round_coords(p['lat'], p['lon'], precision=5)[1] if p['lat'] is not None and p['lon'] is not None else None,
             p['ele'], None)
            for p in pts
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO session_tracks "
            "(session_id, ts, lat, lon, elevation_m, speed_ms) "
            "VALUES (?,?,?,?,?,?)",
            rows
        )
        conn.commit()
        result.rows_inserted += len(rows)
        if is_new:
            result.rows_skipped += 0  # new sessions counted in inserted tracks

    return result


def run(conn: sqlite3.Connection, _data_path=None,
        lang: str = 'de', person: str | None = None) -> ImportResult:
    person = person or _main_person(conn)
    total = ImportResult(source='gpx')

    dirs: list[Path] = []
    if _cfg.garmin_gpsmap_dir and _cfg.garmin_gpsmap_dir.exists():
        dirs.append(_cfg.garmin_gpsmap_dir)
    # fallback: auto-detect garmin_gpsmap next to garmin dir
    elif (_cfg.garmin_dir.parent / 'garmin_gpsmap').exists():
        dirs.append(_cfg.garmin_dir.parent / 'garmin_gpsmap')
    if _cfg.polar_gpx_dir and _cfg.polar_gpx_dir.exists():
        dirs.append(_cfg.polar_gpx_dir)
    apple_routes = _cfg.data_root / "apple_health_export" / "workout-routes"
    if apple_routes.exists():
        dirs.append(apple_routes)
    garmin_inreach = _cfg.data_root / "garmin_gdpr" / "INREACH"
    if garmin_inreach.exists():
        dirs.append(garmin_inreach)

    for d in dirs:
        r = import_tracks_dir(conn, d, person)
        total.rows_inserted += r.rows_inserted
        total.rows_skipped  += r.rows_skipped
        total.errors.extend(r.errors)
        print(t(f"  {d.name}: {r.rows_inserted:,} Punkte", f"  {d.name}: {r.rows_inserted:,} points"), flush=True)

    log_import(conn, 'tracks', '', total.rows_inserted, total.rows_skipped)
    conn.commit()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("GPX-Dateien → session_tracks", "GPX files → session_tracks"))
    parser.add_argument('--dir', metavar='DIR',
                        help=t("Zusätzliches GPX-Verzeichnis", "Extra GPX directory"))
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--person', default=None, metavar='PERSON_ID',
                        help=t("Person-ID (Standard: Haupt-Person aus der DB)",
                               "Person ID (default: main person from the DB)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    print(t("\n── GPX-Import ───────────────────────────────────────────",
            "\n── GPX import ───────────────────────────────────────────"))

    result = run(conn, person=args.person)

    if args.dir:
        extra = Path(args.dir).expanduser()
        if extra.exists():
            r = import_tracks_dir(conn, extra, person=args.person)
            print(t(f"  {extra.name}: {r.rows_inserted:,} Punkte", f"  {extra.name}: {r.rows_inserted:,} points"))
            result.rows_inserted += r.rows_inserted

    # Stats
    r = conn.execute(
        "SELECT COUNT(DISTINCT session_id), COUNT(*) FROM session_tracks"
    ).fetchone()
    print(t(f"\n  session_tracks: {r[1]:,} Punkte in {r[0]} Sessions",
            f"\n  session_tracks: {r[1]:,} points in {r[0]} sessions"))

    conn.close()


if __name__ == '__main__':
    main()
