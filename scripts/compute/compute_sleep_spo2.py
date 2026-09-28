#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Nocturnal SpO2 minimum from raw measurement data.

@tier        infrastructure
@purpose.de  Extrahiert das nächtliche SpO2-Minimum aus Rohmessungen als Eingang
             für das Apnoe-Screening. Reine Extraktion, keine Klassifikation.
@purpose.en  Extracts the nocturnal SpO2 minimum from raw measurements as input to
             apnea screening. Pure extraction, no classification.
@method.de   Fenster 21:00–07:59 Lokalzeit, gefiltert nach Rohdaten-Timestamps.
             Quellen: Garmin GDPR-Export (1-Min-Sampling, historisch), Garmin
             Connect API (laufender täglicher Import), Apple Watch (~30-Min)
             und Wellue O2Ring (kontinuierlich, 150-436 Messungen/Nacht wenn
             getragen -- einziges Geraet, das fuer durchgehende naechtliche
             SpO2-Messung gebaut ist). Oura (Tagesmittel mit Platzhalter-
             Zeitstempel T00:00:00, kein echter Nachtwert -- liefert
             nachweislich nur EINEN Wert pro Nacht, kein Rohdatenzugriff),
             Polar/Beurer/Withings (verstreute Einzel-Spot-Checks, kein
             echtes naechtliches Minimum ableitbar) ungeeignet -- jeweils
             gepruefte Rohdaten-Stichprobe, nicht nur Annahme. WICHTIG (von
             der Nutzerin bestaetigt, nicht nur aus dem Zeitstempel-Muster
             erschlossen): kein Polar-Geraet, das sie je besass oder besitzt
             (inkl. Vantage V3), unterstuetzt durchgehende naechtliche SpO2-
             Aufzeichnung -- die 35 in dieser DB gefundenen Polar-SpO2-Werte
             (2024, Vantage V3) sind durchgehend EINZELNE, manuell
             ausgeloeste Sport-/Nachbelastungs-Messungen (Stichprobe
             gegengeprueft: ein 85%-Ausreisser am 13.04.2024 21:13 fiel ca.
             3h nach einem 2h14min-Training desselben Tages -- klassischer
             Nachbelastungs-Check, keine Zufallsnachtmessung), keine
             Geraetefunktion, die zwischen Schlafphasen automatisch misst.
             Diese Einschraenkung ist also eine GERAETE-KAPAZITAETSGRENZE,
             kein bloss ungluecklicher Nutzungszeitraum -- ein spaeteres
             Polar-Modell wuerde daran nichts aendern, ohne dass Polar
             selbst durchgehende naechtliche SpO2 als Feature einfuehrt.
@method.en   Window 21:00–07:59 local, filtered by raw-data timestamps. Sources:
             Garmin GDPR export (1-min sampling, historical), Garmin Connect API
             (ongoing daily import), Apple Watch (~30-min), and Wellue O2Ring
             (continuous, 150-436 readings/night when worn -- the only device
             actually built for continuous nocturnal SpO2 monitoring). Oura
             (daily average with a placeholder T00:00:00 timestamp, not a real
             nighttime value -- demonstrably delivers only ONE value per
             night, no raw-data access), Polar/Beurer/Withings (scattered
             single spot-checks, no genuine nocturnal minimum derivable)
             unsuitable -- each a checked raw-data sample, not an
             assumption. IMPORTANT (confirmed by the user, not just inferred
             from the timestamp pattern): no Polar device she has ever owned
             or currently owns (incl. Vantage V3) supports continuous
             nocturnal SpO2 recording -- the 35 Polar SpO2 values found in
             this DB (2024, Vantage V3) are consistently INDIVIDUAL,
             manually triggered sport/post-exertion checks (cross-checked
             sample: an 85% outlier on 2024-04-13 21:13 fell ~3h after a
             2h14min training session the same day -- a classic post-
             exertion check, not a chance nighttime reading), not a device
             feature that measures automatically between sleep stages. This
             limitation is therefore a DEVICE CAPABILITY CEILING, not merely
             an unlucky usage period -- a later Polar model would not change
             this unless Polar itself introduces continuous nocturnal SpO2
             as a feature.
@reads       measurements (metric in spo2, oxygen_saturation)
@writes      measurements (metric='sleep_spo2_min', one entry per source), import_log
@limits.de   Getrennte Einträge pro Quelle — Leser müssen MIN() über alle Quellen
             nehmen. Genauigkeit ist durch die Consumer-Sensoren begrenzt; ersetzt
             keine Pulsoxymetrie/Polygraphie.

@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@limits.en   Separate entries per source — readers must take MIN() across sources.
             Accuracy is limited by the consumer sensors; not a substitute for
             pulse oximetry / polygraphy.
@usage
    python3 compute_sleep_spo2.py
    python3 compute_sleep_spo2.py --from 2025-09-01
    python3 compute_sleep_spo2.py --dry-run
"""

import argparse
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
DB_PATH = _cfg.db_path

NIGHT_START_HOUR = 21   # 21:00 Lokalzeit → Nacht beginnt
NIGHT_END_HOUR   = 8    # 08:00 Lokalzeit → Nacht endet
MIN_SAMPLES      = 2    # mind. 2 Messungen pro Nacht für validen Wert
METRIC_OUT       = "sleep_spo2_min"

# (metric_in, source_app, value_is_fraction, device_id_out, source_app_out, min_samples, minute_offset)
#
# minute_offset: The synthetic output ts is night_date+21:00 local. Since device_id_out
# is identical for both Garmin sources, the (ts, metric, device_id, person) primary key
# would collide between them for the same night, silently dropping one row via
# INSERT OR IGNORE. The offset keeps the two Garmin sources' rows distinct without
# fabricating a second device_id for the same physical watch.
SOURCES = [
    ("spo2",              "garmin_gdpr",    False, "garmin_fenix6",  "garmin_gdpr",    2, 0),
    ("spo2",              "garmin_connect", False, "garmin_fenix6",  "garmin_connect", 2, 1),
    ("oxygen_saturation", "apple_health",   True,  "apple_watch",    "apple_health",   2, 0),
    # Ergaenzt: Wellue O2Ring liefert 'spo2' bereits in measurements, bereits
    # in % (kein Bruchwert wie bei Apples oxygen_saturation, is_frac=False),
    # wurde hier aber bisher nicht verarbeitet. Einziges Geraet, das
    # durchgehende naechtliche SpO2-Messung ueberhaupt zum Zweck hat --
    # geprueft: 150-436 Messungen/Nacht wenn getragen (echte kontinuierliche
    # Abdeckung, kein Spot-Check).
    ("spo2",              "wellue_o2ring",  False, "wellue_o2ring",  "wellue_o2ring",  2, 2),
    # BEWUSST NICHT ergaenzt (geprueft, nicht nur uebersehen):
    # - oura_app: genau 1 Zeile/Tag, Zeitstempel immer T00:00:00 -- Ouras
    #   eigener TAGESDURCHSCHNITT mit Platzhalter-Zeitstempel, kein echter
    #   Nacht-Minimalwert; als "naechtliches Minimum" behandelt waere das
    #   irrefuehrend (dieselbe Erwaehnung im @method-Docstring wie zuvor,
    #   jetzt mit dem konkreten Befund dahinter).
    # - polar_connect: Zeitstempel ueber den ganzen Tag verstreut (Sport-
    #   Spot-Checks) -- ein "Minimum" aus 1-2 zufaelligen Tageswerten ist
    #   kein echtes naechtliches Minimum.
    # - beurer_hmp/withings: dasselbe Spot-Check-Problem wie Polar, dazu
    #   verschwindend wenige Zeilen insgesamt (28 bzw. 3 ueber die gesamte
    #   Historie) -- kein nennenswerter Abdeckungsgewinn, gleiches
    #   methodisches Problem.
]


def _night_date(ts_str: str, tz) -> str | None:
    """Gibt das Nacht-Datum zurück (Datum des Abends, an dem die Nacht beginnt)."""
    try:
        dt = datetime.fromisoformat(ts_str).astimezone(tz)
    except Exception:
        return None
    h = dt.hour
    if h >= NIGHT_START_HOUR:
        return dt.strftime("%Y-%m-%d")
    if h < NIGHT_END_HOUR:
        return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    return None


def _compute_nights(conn, metric_in: str, source_app_in: str, is_fraction: bool,
                    person: str, d_from: str | None, d_to: str | None, tz) -> dict[str, tuple[float, int]]:
    """Gibt {night_date: (spo2_min_pct, n_samples)} zurück."""
    where = ["metric=?", "source_app=?", "person=?", "value>0"]
    params: list = [metric_in, source_app_in, person]
    if is_fraction:
        where.append("value<=1.5")
    else:
        where.extend(["value>=50", "value<=100"])
    if d_from:
        where.append("date>=?"); params.append(d_from)
    if d_to:
        where.append("date<=?"); params.append(d_to)

    rows = conn.execute(
        f"SELECT ts, value FROM measurements WHERE {' AND '.join(where)} ORDER BY ts",
        params
    ).fetchall()

    night_vals: dict[str, list[float]] = defaultdict(list)
    for ts_str, val in rows:
        nd = _night_date(ts_str, tz)
        if nd:
            pct = val * 100.0 if is_fraction else float(val)
            night_vals[nd].append(pct)

    return {
        nd: (round(min(vals), 1), len(vals))
        for nd, vals in night_vals.items()
        if len(vals) >= 2
    }


def main():
    parser = argparse.ArgumentParser(
        description=t("Nächtliches SpO2-Minimum aus Rohdaten berechnen",
                      "Compute nightly SpO2 minimum from raw sensor data"))
    parser.add_argument("--from", dest="d_from", default=None,
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to", dest="d_to", default=None,
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--person", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur anzeigen, nichts schreiben", "Show only, do not write"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person or OWN_PERSON_ID

    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(_cfg.home_timezone)
    except Exception:
        import pytz
        tz = pytz.timezone(_cfg.home_timezone)

    conn = open_db()
    t0 = time.time()

    # Bereits berechnete Nächte pro Quelle — INSERT OR IGNORE reicht, aber zur Info
    existing = {(r[0], r[1]) for r in conn.execute(
        "SELECT date, source_app FROM measurements WHERE metric=? AND person=?",
        (METRIC_OUT, person)
    ).fetchall()}

    total_inserted = 0
    all_to_insert: list[tuple] = []

    for (metric_in, src_in, is_frac, dev_out, src_out, min_s, min_off) in SOURCES:
        nights = _compute_nights(conn, metric_in, src_in, is_frac, person,
                                 args.d_from, args.d_to, tz)
        new_n = sum(1 for nd in nights if (nd, src_out) not in existing)
        print(t(f"  {src_in}: {len(nights)} Nächte berechnet ({new_n} neu)",
                f"  {src_in}: {len(nights)} nights computed ({new_n} new)"))

        for night_date, (spo2_min, n) in sorted(nights.items()):
            # Synthetischer ts: Nacht-Startpunkt in Lokalzeit (+ min_off zur
            # Kollisionsvermeidung zwischen Quellen mit identischem device_id_out)
            night_start = (datetime.strptime(f"{night_date}T21:00:00", "%Y-%m-%dT%H:%M:%S")
                           + timedelta(minutes=min_off))
            try:
                from zoneinfo import ZoneInfo as _ZI
                ts_out = night_start.replace(tzinfo=_ZI(_cfg.home_timezone)).isoformat()
            except Exception:
                import pytz as _pytz
                ts_out = _pytz.timezone(_cfg.home_timezone).localize(night_start).isoformat()

            all_to_insert.append((ts_out, night_date, METRIC_OUT, spo2_min, "%",
                                   dev_out, person, src_out, n))

    if args.dry_run:
        print(t("\n── Dry-run: Vorschau ──", "\n── Dry-run: preview ──"))
        # Zeige nach Datum sortiert mit Quellen-Vergleich
        by_date: dict[str, list] = defaultdict(list)
        for r in all_to_insert:
            by_date[r[1]].append(r)
        for nd in sorted(by_date)[-30:]:
            parts = "  ".join(f"{r[7]}={r[3]:.0f}%(n={r[8]})" for r in by_date[nd])
            print(f"  {nd}  {parts}")
        return

    inserted = 0
    for row in all_to_insert:
        cur = conn.execute(
            """INSERT OR IGNORE INTO measurements
               (ts, date, metric, value, unit, device_id, person, source_app)
               VALUES (?,?,?,?,?,?,?,?)""",
            row[:8]
        )
        inserted += cur.rowcount

    conn.execute(
        """INSERT INTO import_log (ts_run, source, data_path, person, rows_inserted, rows_skipped, duration_s)
           VALUES (datetime('now'), ?, '', ?, ?, ?, ?)""",
        ("compute_sleep_spo2", person, inserted,
         len(all_to_insert) - inserted, round(time.time() - t0, 2))
    )
    conn.commit()
    conn.close()
    total_inserted = inserted

    print(t(f"\n{total_inserted} neue Nacht-SpO2-Minima gespeichert "
            f"({len(all_to_insert) - total_inserted} bereits vorhanden).",
            f"\n{total_inserted} new nightly SpO2 minima saved "
            f"({len(all_to_insert) - total_inserted} already present)."))
    print(t(f"Datenbank: {DB_PATH}", f"Database: {DB_PATH}"))


if __name__ == "__main__":
    main()
