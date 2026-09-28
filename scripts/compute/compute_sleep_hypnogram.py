#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Unified sleep hypnogram from Polar, Oura, Apple and Garmin.

@tier        infrastructure
@purpose.de  Vereinheitlicht die von Geräten gelieferten Schlafstadien zu einem
             gemeinsamen Hypnogramm-Schema. Kein eigenes Klassifikationsverfahren.
@purpose.en  Unifies device-reported sleep stages into a common hypnogram schema.
             No own classification algorithm.
@method.de   Remap der quellenspezifischen Stadien-Kodierungen auf WAKE/LIGHT/DEEP/
             REM. Die Stadien-Klassifikation selbst stammt aus den Geräte-
             Algorithmen (Polar, Oura, Apple, Garmin), nicht aus diesem Script.
@method.en   Remaps source-specific stage encodings to WAKE/LIGHT/DEEP/REM. The
             stage classification itself comes from the device algorithms (Polar,
             Oura), not from this script.
@reads       polar_sleep_hypnogram, oura_sleep_model, measurements, sessions
@writes      sleep_hypnogram: session_id, ts, date, stage, duration_s, source,
             device_id, person
@limits.de   Übernimmt die Genauigkeit und Fehler der Consumer-Geräte-Staging-
             Algorithmen; kein Abgleich mit Polysomnografie.

@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@limits.en   Inherits the accuracy and errors of the consumer-device staging
             algorithms; no comparison against polysomnography.
@usage
    python compute_sleep_hypnogram.py
    python compute_sleep_hypnogram.py --from 2024-01-01 --to 2024-12-31
    python compute_sleep_hypnogram.py --update
"""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
DB_PATH   = _cfg.db_path
_OURA_DEV = _cfg.oura_device_id

POLAR_STAGE_MAP = {
    "WAKE":     "WAKE",
    "NONREM2":  "LIGHT",
    "NONREM3":  "DEEP",
    "REM":      "REM",
}

OURA_STAGE_MAP = {
    "1": "DEEP",
    "2": "LIGHT",
    "3": "REM",
    "4": "WAKE",
}

# MUSS zur Kodierung in import_apple.CATEGORY_MAP passen (dort: 2=Awake, 3=AsleepREM,
# 4=AsleepCore, 5=AsleepDeep). Vorher war dieses Mapping rotiert (4→DEEP) → Tiefschlaf-
# Anteil deutlich zu hoch statt im physiologisch plausiblen Bereich.
APPLE_STAGE_MAP = {
    2.0: "WAKE",
    3.0: "REM",
    4.0: "LIGHT",
    5.0: "DEEP",
}


# Garmin activityLevel aus sleepLevels (import_garmin.import_sleep, Metrik
# 'garmin_sleep_level'). Gegen deep/light/rem/awakeSleepSeconds derselben Nacht
# verifiziert: die Segmentsummen je Level stimmen exakt mit den DTO-Summen ueberein.
# Level -1 (Aufzeichnungsluecke, nicht klassifizierbar) fehlt bewusst: es ist
# keine Schlafphase und wuerde sonst als WAKE o. ae. mitgezaehlt.
GARMIN_STAGE_MAP = {
    0.0: "DEEP",
    1.0: "LIGHT",
    2.0: "REM",
    3.0: "WAKE",
}


def _parse_iso_to_utc(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp (with or without timezone) → UTC datetime."""
    s = ts_str.strip()
    # Remove sub-second part
    if "." in s:
        s = s[:s.index(".")] + s[s.rindex(s[-6:]) if s[-6] in ("+", "-") else len(s):]
    # Handle trailing timezone like +02:00 or Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        # Fallback: try without tz info
        return datetime.fromisoformat(s[:19])


def setup_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sleep_hypnogram (
            session_id  TEXT,
            ts          TEXT NOT NULL,
            date        TEXT NOT NULL,
            stage       TEXT NOT NULL CHECK(stage IN ('WAKE','LIGHT','DEEP','REM')),
            duration_s  INTEGER,
            source      TEXT NOT NULL,
            device_id   TEXT,
            person      TEXT NOT NULL DEFAULT 'unknown',
            PRIMARY KEY (ts, source, person)
        )
    """)
    conn.commit()


def build_polar(conn, rebuild: bool = False) -> int:
    if rebuild:
        conn.execute("DELETE FROM sleep_hypnogram WHERE source='polar'")
        conn.commit()

    # Alle Einträge inkl. WS_UNKNOWN laden um korrekte Lücken zu berechnen
    rows = conn.execute("""
        SELECT h.date, h.offset_s, h.state, h.sleep_start, h.person,
               s.id AS session_id, s.device_id
        FROM polar_sleep_hypnogram h
        LEFT JOIN sessions s
          ON s.type = 'sleep'
         AND s.source_app = 'polar_connect'
         AND s.person = h.person
         AND s.date = h.date
        ORDER BY h.person, h.date, h.sleep_start, h.offset_s
    """).fetchall()

    # Gruppen: je (person, date, sleep_start) → duration = Abstand zum nächsten Offset
    from itertools import groupby
    inserted = 0
    batch = []
    for _, group in groupby(rows, key=lambda r: (r[4], r[0], r[3])):
        session_rows = list(group)
        for i, (date, offset_s, state, sleep_start, person, session_id, device_id) in enumerate(session_rows):
            stage = POLAR_STAGE_MAP.get(state)
            if not stage:
                continue
            try:
                base = _parse_iso_to_utc(sleep_start)
            except Exception:
                continue
            ts = (base + timedelta(seconds=offset_s)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            # Dauer = Abstand zum nächsten Offset; letzter Eintrag → None
            if i + 1 < len(session_rows):
                duration_s = session_rows[i + 1][1] - offset_s
            else:
                duration_s = None
            batch.append((session_id, ts, date, stage, duration_s, "polar",
                          device_id or "polar_device", person))

    if batch:
        before = conn.execute("SELECT COUNT(*) FROM sleep_hypnogram WHERE source='polar'").fetchone()[0]
        conn.executemany("""
            INSERT OR IGNORE INTO sleep_hypnogram
              (session_id, ts, date, stage, duration_s, source, device_id, person)
            VALUES (?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM sleep_hypnogram WHERE source='polar'").fetchone()[0]
        inserted = after - before
    return inserted


def build_oura(conn, rebuild: bool = False) -> int:
    if rebuild:
        conn.execute("DELETE FROM sleep_hypnogram WHERE source='oura'")
        conn.commit()

    rows = conn.execute("""
        SELECT o.day, o.bedtime_start, o.sleep_phase_30_sec, o.person, o.id
        FROM oura_sleep_model o
        WHERE o.sleep_phase_30_sec IS NOT NULL AND o.bedtime_start IS NOT NULL
    """).fetchall()

    batch = []
    for day, bedtime_start, phase_str, person, oura_id in rows:
        try:
            base = _parse_iso_to_utc(bedtime_start)
        except Exception:
            continue

        for i, ch in enumerate(phase_str):
            stage = OURA_STAGE_MAP.get(ch)
            if not stage:
                continue
            ts = (base + timedelta(seconds=i * 30)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            # date: use ts date not day (bedtime often starts before midnight)
            ts_date = (base + timedelta(seconds=i * 30)).strftime("%Y-%m-%d")
            session_id = f"oura_{oura_id}" if oura_id else None
            batch.append((session_id, ts, ts_date, stage, 30, "oura", _OURA_DEV, person))

    if batch:
        before = conn.execute("SELECT COUNT(*) FROM sleep_hypnogram WHERE source='oura'").fetchone()[0]
        conn.executemany("""
            INSERT OR IGNORE INTO sleep_hypnogram
              (session_id, ts, date, stage, duration_s, source, device_id, person)
            VALUES (?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM sleep_hypnogram WHERE source='oura'").fetchone()[0]
        inserted = after - before
    else:
        inserted = 0
    return inserted


def build_apple(conn, rebuild: bool = False) -> int:
    if rebuild:
        conn.execute("DELETE FROM sleep_hypnogram WHERE source='apple'")
        conn.commit()

    rows = conn.execute("""
        SELECT m.ts, m.date, m.value, m.device_id, m.person,
               s.id AS session_id
        FROM measurements m
        LEFT JOIN sessions s
          ON s.type = 'sleep'
         AND s.source_app = 'apple_health'
         AND s.person = m.person
         AND s.date = m.date
        WHERE m.metric = 'sleep_analysis'
          AND m.value IN (2.0, 3.0, 4.0, 5.0)
        ORDER BY m.person, m.ts
    """).fetchall()

    # Apple-Segmente sind innerhalb einer Nacht zusammenhängend → Dauer aus dem
    # Abstand zum Folge-Segment (wie Polar/Oura). Großer Abstand = Session-Grenze.
    parsed = []
    for ts, date, value, device_id, person, session_id in rows:
        stage = APPLE_STAGE_MAP.get(value)
        if not stage:
            continue
        try:
            tdt = datetime.fromisoformat(ts)
        except Exception:
            tdt = None
        parsed.append((ts, date, stage, device_id, person, session_id, tdt))

    batch = []
    for i, (ts, date, stage, device_id, person, session_id, tdt) in enumerate(parsed):
        dur = None
        if tdt is not None and i + 1 < len(parsed):
            nxt, nxt_person = parsed[i + 1][6], parsed[i + 1][4]
            if nxt is not None and nxt_person == person:
                gap = (nxt - tdt).total_seconds()
                if 0 < gap <= 7200:          # ≤2h → selbe Nacht; sonst Session-Grenze
                    dur = int(gap)
        batch.append((session_id, ts, date, stage, dur, "apple",
                      device_id or "apple_watch", person))

    if batch:
        before = conn.execute("SELECT COUNT(*) FROM sleep_hypnogram WHERE source='apple'").fetchone()[0]
        conn.executemany("""
            INSERT OR IGNORE INTO sleep_hypnogram
              (session_id, ts, date, stage, duration_s, source, device_id, person)
            VALUES (?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM sleep_hypnogram WHERE source='apple'").fetchone()[0]
        inserted = after - before
    else:
        inserted = 0
    return inserted


def print_summary(conn) -> None:
    print(t("\n── sleep_hypnogram Übersicht ────────────────────────────────",
            "\n── sleep_hypnogram overview ─────────────────────────────────"))
    for source, stage, n in conn.execute("""
        SELECT source, stage, COUNT(*)
        FROM sleep_hypnogram
        GROUP BY source, stage
        ORDER BY source, stage
    """).fetchall():
        print(f"  {source:<8} {stage:<6} {n:>7,}")

    print()
    for source, n, d_min, d_max in conn.execute("""
        SELECT source, COUNT(*), MIN(date), MAX(date)
        FROM sleep_hypnogram
        GROUP BY source ORDER BY source
    """).fetchall():
        print(t(f"  {source:<8} {n:>8,} Intervalle | {d_min} – {d_max}",
                f"  {source:<8} {n:>8,} intervals  | {d_min} – {d_max}"))


def build_garmin(conn, rebuild: bool = False) -> int:
    """Garmin-Schlafphasen. Die Segmentdauer kommt aus dem mitgelieferten
    Segment-Ende (value_text), nicht aus dem Abstand zum Folgesegment."""
    if rebuild:
        conn.execute("DELETE FROM sleep_hypnogram WHERE source='garmin'")
        conn.commit()

    rows = conn.execute("""
        SELECT m.ts, m.date, m.value, m.value_text, m.device_id, m.person,
               s.id AS session_id
        FROM measurements m
        LEFT JOIN sessions s
          ON s.type = 'sleep'
         AND s.id LIKE 'garmin_sleep_%'
         AND s.person = m.person
         AND s.date = m.date
        WHERE m.metric = 'garmin_sleep_level'
        ORDER BY m.person, m.ts
    """).fetchall()

    batch = []
    for ts, date, value, ts_end, device_id, person, session_id in rows:
        stage = GARMIN_STAGE_MAP.get(value)
        if not stage:
            continue
        dur = None
        if ts_end:
            try:
                dur = int((datetime.fromisoformat(ts_end) - datetime.fromisoformat(ts)).total_seconds())
            except ValueError:
                dur = None
        batch.append((session_id, ts, date, stage, dur, "garmin", device_id, person))

    if not batch:
        return 0
    before = conn.execute("SELECT COUNT(*) FROM sleep_hypnogram WHERE source='garmin'").fetchone()[0]
    conn.executemany("""
        INSERT OR IGNORE INTO sleep_hypnogram
          (session_id, ts, date, stage, duration_s, source, device_id, person)
        VALUES (?,?,?,?,?,?,?,?)
    """, batch)
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM sleep_hypnogram WHERE source='garmin'").fetchone()[0]
    return after - before


def main():
    parser = argparse.ArgumentParser(
        description=t("Einheitliches Schlaf-Hypnogramm aus Polar + Oura berechnen",
                      "Build unified sleep hypnogram from Polar + Oura"))
    parser.add_argument("--rebuild", action="store_true",
                        help=t("Tabelle leeren und neu aufbauen",
                               "Clear table and rebuild from scratch"))
    parser.add_argument("--source", choices=["polar", "oura", "apple", "garmin", "all"], default="all",
                        help=t("Nur diese Quelle verarbeiten", "Process only this source"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    setup_table(conn)

    total = 0

    if args.source in ("polar", "all"):
        print(t("Polar Schlaf-Hypnogramm ...", "Polar sleep hypnogram ..."), flush=True)
        n = build_polar(conn, rebuild=args.rebuild)
        print(t(f"  → {n:,} neue Intervalle eingefügt",
                f"  → {n:,} new intervals inserted"))
        total += n

    if args.source in ("oura", "all"):
        print(t("Oura Schlaf-Phasen ...", "Oura sleep phases ..."), flush=True)
        n = build_oura(conn, rebuild=args.rebuild)
        print(t(f"  → {n:,} neue Intervalle eingefügt",
                f"  → {n:,} new intervals inserted"))
        total += n

    if args.source in ("apple", "all"):
        print(t("Apple Watch Schlaf-Phasen ...", "Apple Watch sleep phases ..."), flush=True)
        n = build_apple(conn, rebuild=args.rebuild)
        print(t(f"  → {n:,} neue Intervalle eingefügt",
                f"  → {n:,} new intervals inserted"))
        total += n

    if args.source in ("garmin", "all"):
        print(t("Garmin Schlaf-Phasen ...", "Garmin sleep phases ..."), flush=True)
        n = build_garmin(conn, rebuild=args.rebuild)
        print(t(f"  → {n:,} neue Intervalle eingefügt",
                f"  → {n:,} new intervals inserted"))
        total += n

    print(t(f"\nGesamt: {total:,} neue Intervalle.", f"\nTotal: {total:,} new intervals."))
    print_summary(conn)
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))
    conn.close()


if __name__ == "__main__":
    main()
