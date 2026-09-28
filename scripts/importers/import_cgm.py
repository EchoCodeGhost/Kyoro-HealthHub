#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Freestyle Libre 3 (via Apple Health) → health.db

@tier        infrastructure
@purpose.de  Importiert Continuous Glucose Monitoring (CGM) Daten von Freestyle
             Libre 3 (über Apple Health) in die health.db. Unterstützt sowohl die
             kontinuierlichen Sensor-Messungen als auch manuelle Blutzucker-Messungen.
@purpose.en  Imports Continuous Glucose Monitoring (CGM) data from Freestyle
             Libre 3 (via Apple Health) into health.db. Supports both continuous
             sensor measurements and manual blood glucose measurements.
@method.de   Liest Daten aus dem Apple Health Export.xml. FLwatch (Freestyle Libre
             3) → cgm_readings (5-Minuten-Intervall), HealthManager Pro (Beurer GL60)
             → blood_glucose (manuelle Fingerstich-Messungen). Kalibrierungsfunktion
             zeigt Abweichungen zwischen CGM und manuellen Messungen innerhalb
             ±15 Minuten an.
@method.en   Reads data from Apple Health export.xml. FLwatch (Freestyle Libre 3)
             → cgm_readings (5-minute interval), HealthManager Pro (Beurer GL60)
             → blood_glucose (manual fingerstick measurements). Calibration
             function shows deviations between CGM and manual measurements within
             ±15 minutes.
@reads       {apple_xml} (Apple Health Export)
@writes      health.db (cgm_readings, blood_glucose)
@limits.de   Keine Validierung der CGM-Datenqualität. Kalibrierung ist optional
             und dient nur zur Analyse. Keine medizinische Bewertung aus CGM-Daten.
             Rohdaten (flwatch_raw) sind interstitielle Libre-Messwerte, systematisch
             niedriger als Fingerstick-Referenz — unkalibrierte Hypo-Raten daraus sind
             nicht klinisch belastbar (eigene Beobachtung: deutlich erhöhte "Hypo"-Rate
             auf Rohbasis gegenüber Fingerstick-Referenzwerten <70 mg/dl im selben
             Zeitraum, wo keine einzige Referenzmessung eine Hypo bestätigte). calibrate()
             schreibt erst ab n≥10 GL60/CGM-Paaren eine Korrekturfunktion UND nur bei
             physiologisch plausibler Steigung (0,5–2,0) — bei n=3-4 überfittet die
             2-Parameter-Regression fast immer auf Rauschen (eigene Beobachtung: eine
             deutlich zu flache Steigung bei kleiner Stichprobe, die das Rohsignal
             praktisch ignoriert hätte).

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No validation of CGM data quality. Calibration is optional and for
             analysis only. No medical evaluation from CGM data.
             Raw data (flwatch_raw) is interstitial Libre readings, systematically
             lower than fingerstick reference — uncalibrated hypo rates from it are
             not clinically reliable (own observation: a markedly elevated "hypo" rate
             on raw data compared to fingerstick reference readings <70 mg/dl in the
             same period, where not a single reference reading confirmed a hypo).
             calibrate() only writes a correction function once n≥10 GL60/CGM pairs
             exist AND the fitted slope is physiologically plausible (0.5–2.0) — at
             n=3-4 the 2-parameter regression almost always overfits to noise (own
             observation: a markedly too-flat slope at a small sample size, which
             would have effectively discarded the raw signal).
@usage
    python3 import_cgm.py             # vollständiger Import
    python3 import_cgm.py --update    # nur neue Einträge ergänzen
    python3 import_cgm.py --calibrate # nur Kalibrierungsauswertung (kein Import)
"""

import argparse
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
from modules.identity_resolver import resolve_device

_cfg = _Cfg()
DB_PATH   = _cfg.db_path
APPLE_XML = _cfg.apple_xml

MG_DL_TO_MMOL = 0.0555179

_REC_PAT = re.compile(
    r'<Record[^>]*type="HKQuantityTypeIdentifierBloodGlucose"'
    r'[^>]*sourceName="([^"]+)"'
    r'[^>]*unit="([^"]+)"'
    r'[^>]*startDate="([^"]+)"'
    r'[^>]*value="([^"]+)"'
)


def _norm_ts(raw: str) -> str:
    """'2026-06-03 21:06:17 +0200' → '2026-06-03T19:06:17+00:00'"""
    m = re.match(r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) ([+-]\d{2})(\d{2})', raw)
    if not m:
        return raw.replace(' ', 'T')
    dt   = datetime.strptime(f"{m.group(1)}T{m.group(2)}", "%Y-%m-%dT%H:%M:%S")
    sign = 1 if m.group(3)[0] == '+' else -1
    off  = sign * (int(m.group(3)[1:]) * 60 + int(m.group(4)))
    utc  = dt - timedelta(minutes=off)
    return utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _ensure_device(cur: sqlite3.Cursor) -> None:
    # brand/model ('Abbott'/'Freestyle Libre 3') deliberately not written to
    # health.db — see devices table comment in create_schema.py; they stay
    # local-only in registry.json.
    cur.execute(
        "INSERT OR IGNORE INTO devices(device_id, sensor_type, date_from) VALUES (?,'cgm',NULL)",
        (resolve_device("libre3"),),
    )


def parse_xml(xml_path: Path) -> tuple[list, list]:
    """Returns (cgm_rows, gl60_rows) from Apple Health XML."""
    cgm_rows  = []
    gl60_rows = []
    pat = re.compile(
        r'sourceName="([^"]+)"[^>]*unit="([^"]+)"[^>]*startDate="([^"]+)"[^>]*value="([^"]+)"'
    )
    with open(xml_path, 'r', errors='replace') as f:
        for line in f:
            if 'BloodGlucose' not in line:
                continue
            m = pat.search(line)
            if not m:
                continue
            source, unit, raw_ts, raw_val = m.groups()
            try:
                val_mgdl = float(raw_val)
            except ValueError:
                continue
            if unit == 'mmol/L':
                val_mgdl = val_mgdl / MG_DL_TO_MMOL
            ts   = _norm_ts(raw_ts)
            date = ts[:10]
            if source == 'FLwatch':
                cgm_rows.append((ts, date, val_mgdl * MG_DL_TO_MMOL, val_mgdl))
            elif source == 'HealthManager Pro':
                gl60_rows.append((ts, date, val_mgdl * MG_DL_TO_MMOL, val_mgdl))
    return cgm_rows, gl60_rows


def import_cgm(conn: sqlite3.Connection, update_only: bool = False) -> tuple[int, int]:
    cgm_rows, gl60_rows = parse_xml(APPLE_XML)
    cur = conn.cursor()
    _ensure_device(cur)

    # Bereits importierte Rohwerte mit altem source-Label migrieren
    cur.execute("UPDATE cgm_readings SET source='flwatch_raw' WHERE source='flwatch' AND person=?", (OWN_PERSON_ID,))

    cgm_n = gl60_n = 0
    for ts, date, mmol, mgdl in cgm_rows:
        if update_only:
            if cur.execute(
                "SELECT 1 FROM cgm_readings WHERE ts=? AND person=? AND source='flwatch_raw'", (ts, OWN_PERSON_ID)
            ).fetchone():
                continue
        cur.execute(
            "INSERT OR IGNORE INTO cgm_readings(ts, date, glucose_mmol, glucose_mgdl, device_id, person, source) "
            "VALUES (?,?,?,?,'libre3',?,'flwatch_raw')",
            (ts, date, mmol, mgdl, OWN_PERSON_ID)
        )
        cgm_n += cur.rowcount

    for ts, date, mmol, mgdl in gl60_rows:
        if update_only:
            if cur.execute("SELECT 1 FROM blood_glucose WHERE ts=? AND person=?", (ts, OWN_PERSON_ID)).fetchone():
                continue
        cur.execute(
            "INSERT OR IGNORE INTO blood_glucose(ts, date, glucose_mmol, glucose_mgdl, device_id, person, source) "
            "VALUES (?,?,?,?,'beurer_gl60',?,'healthmanager_pro')",
            (ts, date, mmol, mgdl, OWN_PERSON_ID)
        )
        gl60_n += cur.rowcount

    log_import(conn, 'cgm', str(APPLE_XML), cgm_n + gl60_n)
    conn.commit()
    return cgm_n, gl60_n


def _write_calibrated(conn: sqlite3.Connection, cur: sqlite3.Cursor,
                      a: float, b: float) -> None:
    """
    Berechnet kalibrierte CGM-Werte aus allen flwatch_raw-Einträgen und schreibt
    sie als source='flwatch_calibrated' (synthetisch). Alte kalibrierte Werte werden
    zuerst gelöscht, damit der Faktor immer aktuell ist.
    """
    cur.execute("DELETE FROM cgm_readings WHERE source='flwatch_calibrated' AND person=?", (OWN_PERSON_ID,))
    raw_rows = cur.execute(
        "SELECT ts, date, glucose_mgdl FROM cgm_readings "
        "WHERE source='flwatch_raw' AND person=? ORDER BY ts",
        (OWN_PERSON_ID,)
    ).fetchall()

    written = 0
    for ts, date, raw_mgdl in raw_rows:
        corr_mgdl = max(20.0, a * raw_mgdl + b)   # physiologisches Minimum
        corr_mmol = corr_mgdl * MG_DL_TO_MMOL
        cur.execute(
            "INSERT OR IGNORE INTO cgm_readings"
            "(ts, date, glucose_mmol, glucose_mgdl, device_id, person, source) "
            "VALUES (?,?,?,?,'libre3',?,'flwatch_calibrated')",
            (ts, date, corr_mmol, corr_mgdl, OWN_PERSON_ID)
        )
        written += 1

    conn.commit()
    print(t(
        f"  {written:,} kalibrierte Werte als 'flwatch_calibrated' gespeichert.",
        f"  {written:,} calibrated values written as 'flwatch_calibrated'."
    ))


def calibrate(conn: sqlite3.Connection) -> None:
    """
    Vergleicht CGM (FLwatch) mit GL60-Referenzmessungen innerhalb ±15 min.
    Ab ≥3 Paaren: linearer Korrekturfaktor (Steigung + Offset via least-squares).
    """
    cur = conn.cursor()
    gl60_rows = cur.execute(
        "SELECT ts, glucose_mgdl FROM blood_glucose "
        "WHERE source='healthmanager_pro' AND person=? ORDER BY ts",
        (OWN_PERSON_ID,)
    ).fetchall()

    if not gl60_rows:
        print(t("  Keine GL60-Referenzmessungen in DB.", "  No GL60 reference measurements in DB."))
        return

    pairs = []
    for gl60_ts, gl60_val in gl60_rows:
        gl60_dt = datetime.fromisoformat(gl60_ts).replace(tzinfo=timezone.utc)
        # nächste CGM-Messung ±15 min
        lo = (gl60_dt - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        hi = (gl60_dt + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        nearest = cur.execute(
            "SELECT ts, glucose_mgdl FROM cgm_readings "
            "WHERE person=? AND ts BETWEEN ? AND ? "
            "ORDER BY ABS(strftime('%s',ts) - strftime('%s',?)) LIMIT 1",
            (OWN_PERSON_ID, lo, hi, gl60_ts)
        ).fetchone()
        if nearest:
            cgm_ts, cgm_val = nearest
            diff    = gl60_val - cgm_val
            rel_pct = diff / gl60_val * 100
            pairs.append((gl60_ts[:16], gl60_val, cgm_val, diff, rel_pct))

    print(t("\n── CGM-Kalibrierung (GL60 vs. Libre 3) ──────────────────",
            "\n── CGM Calibration (GL60 vs. Libre 3) ───────────────────"))
    if not pairs:
        print(t("  Keine zeitgleichen GL60/CGM-Paare (±15 min) gefunden.",
                "  No simultaneous GL60/CGM pairs (±15 min) found."))
        return

    header = t(
        f"  {'Zeitpunkt':16}  {'GL60':>7}  {'Libre':>7}  {'Diff':>7}  {'Abw%':>7}",
        f"  {'Timestamp':16}  {'GL60':>7}  {'Libre':>7}  {'Diff':>7}  {'Dev%':>7}"
    )
    print(header)
    print("  " + "─" * 54)
    for gl60_ts, gl60_val, cgm_val, diff, rel_pct in pairs:
        flag = "  ← Zone C" if abs(rel_pct) > 20 else ""
        print(f"  {gl60_ts}  {gl60_val:7.1f}  {cgm_val:7.1f}  {diff:+7.1f}  {rel_pct:+7.1f}%{flag}")

    diffs   = [p[3] for p in pairs]
    rel_pcts = [p[4] for p in pairs]
    mean_diff = sum(diffs) / len(diffs)
    mean_rel  = sum(rel_pcts) / len(rel_pcts)
    print(t(f"\n  n={len(pairs)}  Mittlere Diff: {mean_diff:+.1f} mg/dL  Mittlere Abw: {mean_rel:+.1f}%",
            f"\n  n={len(pairs)}  Mean diff: {mean_diff:+.1f} mg/dL  Mean dev: {mean_rel:+.1f}%"))

    # MIN_PAIRS=3 ist die bloße mathematische Untergrenze fuer eine 2-Parameter-
    # Regression (Steigung+Achsenabschnitt), aber bei n=3-4 ueberfittet die
    # Gerade praktisch immer auf Rauschen statt auf ein echtes Kalibrierungs-
    # muster (eigene Beobachtung: bei kleiner Stichprobe eine deutlich zu
    # flache Steigung statt physiologisch plausibler ~1.0 - die Korrektur
    # haette das Rohsignal fast komplett ignoriert). Deshalb deutlich hoehere
    # Schwelle + Plausibilitaetscheck auf die Steigung, bevor ueberhaupt
    # geschrieben wird.
    MIN_PAIRS = 10
    PLAUSIBLE_SLOPE = (0.5, 2.0)

    if len(pairs) >= MIN_PAIRS:
        # Least-squares: gl60 = a * cgm + b  →  corrected = a * raw + b
        n   = len(pairs)
        xs  = [p[2] for p in pairs]   # cgm values
        ys  = [p[1] for p in pairs]   # gl60 reference
        sx  = sum(xs); sy = sum(ys)
        sxx = sum(x*x for x in xs); sxy = sum(x*y for x,y in zip(xs,ys))
        a   = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        b   = (sy - a * sx) / n
        print(t(
            f"\n  Korrekturfunktion (n≥{MIN_PAIRS}): corrected = {a:.4f} × raw + {b:.2f}",
            f"\n  Correction function (n≥{MIN_PAIRS}): corrected = {a:.4f} × raw + {b:.2f}"
        ))
        if not (PLAUSIBLE_SLOPE[0] <= a <= PLAUSIBLE_SLOPE[1]):
            print(t(
                f"  ⚠ Steigung {a:.4f} liegt außerhalb des physiologisch plausiblen "
                f"Bereichs ({PLAUSIBLE_SLOPE[0]}–{PLAUSIBLE_SLOPE[1]}) — vermutlich "
                "Überanpassung an wenige Punkte. Keine kalibrierten Werte geschrieben.",
                f"  ⚠ Slope {a:.4f} is outside the physiologically plausible range "
                f"({PLAUSIBLE_SLOPE[0]}–{PLAUSIBLE_SLOPE[1]}) — likely overfit to few "
                "points. No calibrated values written."
            ))
            cur.execute("DELETE FROM cgm_readings WHERE source='flwatch_calibrated' AND person=?", (OWN_PERSON_ID,))
            conn.commit()
            return
        print(t(
            "  Hinweis: Faktor aus wenigen Messpunkten — nur orientierend verwenden.",
            "  Note: Factor from few data points — use as rough guidance only."
        ))
        _write_calibrated(conn, cur, a, b)
    else:
        print(t(
            f"  Noch {MIN_PAIRS - len(pairs)} GL60-Messung(en) für Korrekturfaktor nötig "
            f"(Mindest-n={MIN_PAIRS} für eine verlässliche 2-Parameter-Regression).",
            f"  {MIN_PAIRS - len(pairs)} more GL60 measurement(s) needed for a correction "
            f"factor (minimum n={MIN_PAIRS} for a reliable 2-parameter regression)."
        ))
        # Bereits vorhandene kalibrierte Werte aus früheren Läufen entfernen (Faktor veraltet)
        cur.execute("DELETE FROM cgm_readings WHERE source='flwatch_calibrated' AND person=?", (OWN_PERSON_ID,))
        if cur.rowcount:
            print(t(
                f"  {cur.rowcount} veraltete kalibrierte Werte gelöscht (Faktor noch unzureichend).",
                f"  {cur.rowcount} stale calibrated values removed (factor not yet sufficient)."
            ))
        conn.commit()


def main():
    """
    Hauptfunktion: Koordiniert den Import der CGM-Daten.

    Command-Line-Argumente:
        --update: Nur neue Einträge ergänzen
        --calibrate: Nur Kalibrierungsauswertung (kein Import)
    """
    parser = argparse.ArgumentParser(
        description=t("Freestyle Libre 3 → health.db", "Freestyle Libre 3 → health.db")
    )
    parser.add_argument("--update",    action="store_true",
                        help=t("Nur neue Einträge ergänzen", "Append new entries only"))
    parser.add_argument("--calibrate", action="store_true",
                        help=t("Nur Kalibrierungsauswertung", "Calibration report only"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print(t("\n── Freestyle Libre 3 / CGM ────────────────────────────",
            "\n── Freestyle Libre 3 / CGM ────────────────────────────"))

    if not args.calibrate:
        cgm_n, gl60_n = import_cgm(conn, update_only=args.update)
        print(t(f"  cgm_readings:  {cgm_n:,} neu", f"  cgm_readings:  {cgm_n:,} new"))
        print(t(f"  blood_glucose: {gl60_n:,} neu (GL60 via HealthManager Pro)",
                f"  blood_glucose: {gl60_n:,} new (GL60 via HealthManager Pro)"))

        for src, label in [('flwatch_raw', 'cgm raw'), ('flwatch_calibrated', 'cgm calibrated')]:
            r = conn.execute(
                "SELECT COUNT(*), MIN(date), MAX(date) FROM cgm_readings "
                "WHERE person=? AND source=?", (OWN_PERSON_ID, src)
            ).fetchone()
            if r[0]:
                print(t(f"  {label:16}: {r[0]:,} | {r[1]}–{r[2]}",
                        f"  {label:16}: {r[0]:,} | {r[1]}–{r[2]}"))
        r_bg = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM blood_glucose WHERE person=?",
            (OWN_PERSON_ID,)
        ).fetchone()
        print(t(f"  Gesamt bg:     {r_bg[0]:,} | {r_bg[1]}–{r_bg[2]}",
                f"  Total bg:      {r_bg[0]:,} | {r_bg[1]}–{r_bg[2]}"))
        print(t(
            "  Analysen: 'flwatch_calibrated' bevorzugen, Fallback 'flwatch_raw'.",
            "  Analyses: prefer 'flwatch_calibrated', fallback to 'flwatch_raw'."
        ))

    calibrate(conn)
    conn.close()


if __name__ == "__main__":
    main()
