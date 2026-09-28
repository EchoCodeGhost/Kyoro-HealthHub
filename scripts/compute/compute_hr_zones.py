#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
HR zone distribution and daily exertion budget.

@tier        infrastructure
@purpose.de  Verteilt Herzfrequenz-Messungen auf fünf Zonen und berechnet ein
             tägliches Belastungspensum für Pacing bei Dysautonomie/Post-Exertional Malaise (PEM).
@purpose.en  Distributes heart-rate samples across five zones and computes a daily
             exertion budget for pacing under dysautonomia/Post-Exertional Malaise (PEM).
@method.de   Vier bpm-Grenzen definieren fünf Zonen (Erholung → rote Zone). Das
             Tagespensum gewichtet Samples höherer Zonen überproportional. Grenzen
             und Gewichte kommen aus clinical.pacing.zone_thresholds_bpm/zone_weights
             (health_config.json) — ideal aus den Schwellenwerten eines Laktat-/
             Ausbelastungstests, sonst Fallback: Prozente von max_hr (clinical.max_hr
             oder traditionelle Fausteformel). Zonenbasiertes Pacing ist eine heuristische
             Methode zur Belastungssteuerung bei chronischen Erkrankungen.
@method.en   Four bpm thresholds define five zones (recovery → red zone). The daily
             budget weights higher-zone samples disproportionately. Thresholds and
             weights come from clinical.pacing.zone_thresholds_bpm/zone_weights
             (health_config.json) — ideally taken from a lactate/graded-exercise
             test, otherwise falling back to percentages of max_hr (clinical.max_hr
             or traditional rule of thumb). Zone-based pacing is a heuristic method for
             exertion management in chronic conditions.
@scoring
    zones (0..4)   Zone0 <z1 | Zone1 z1-z2 | Zone2 z2-z3 | Zone3 z3-z4 | Zone4 >=z4
    budget         sum(zone_samples * zone_weight)
    default config zone_thresholds_bpm=[90,105,110,115], zone_weights=[0,1,3,8,20]
@reads       measurements (metric='heart_rate')
@writes      daily_hr_zones: samples per zone + daily budget per day and person
@refs        Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x
             Institute of Medicine (2015). Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome: Redefining an Illness. National Academies Press, Washington, DC. doi:10.17226/19012
             Ziaks L et al. (2024). Adaptive Approaches to Exercise Rehabilitation for
             Postural Tachycardia Syndrome and Related Autonomic Disorders. Archives of
             Rehabilitation Research and Clinical Translation, 6(4):100366. doi:10.1016/j.arrct.2024.100366 (stützt den grundsätzlichen Ansatz personenspezifischer statt starrer Zonengrenzen, nicht die konkreten Zahlenwerte)

@relevance.de  Ermöglicht die Analyse von Herzfrequenzzonen, essentiell für die Trainingssteuerung
@relevance.en  Enables heart rate zone analysis, essential for training control
@limits.de   Kein Fitness-/Trainingsmodell. Zonengrenzen sind personenspezifische
             Pacing-Parameter, keine validierten klinischen Schwellen; Aussagekraft
             hängt von korrekter Konfiguration ab. Heuristische Methode.
@limits.en   Not a fitness/training model. Zone thresholds are person-specific
             pacing parameters, not validated clinical cut-offs; meaningfulness
             depends on correct configuration. Heuristic method.
@usage
    python compute_hr_zones.py
    python compute_hr_zones.py --from 2025-01-01 --to 2025-12-31
"""

import argparse
import sys
from collections import defaultdict
from datetime import datetime, date as date_t, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.metric_loader import DEFAULT_SOURCE_GROUPS, AGGREGATOR_SOURCES

_cfg = _Cfg()
DB_PATH = _cfg.db_path

DEFAULT_WEIGHTS   = [0, 1, 3, 8, 20]
DEFAULT_FRACTIONS = [0.530, 0.625, 0.655, 0.685]

# Maximale Dauer, die einem einzelnen Messpunkt zugerechnet wird. Verhindert, dass
# Geraetepausen (Uhr abgelegt, Ladevorgang) als Zonenzeit gezaehlt werden.
GAP_CAP_MIN = 5


def _source_group(source_app: str) -> str:
    """source_app -> Quellengruppe (mehrere Exportpfade derselben Marke, z. B.
    garmin_connect + garmin_gdpr, gelten als eine Quelle). Siehe
    modules/metric_loader.DEFAULT_SOURCE_GROUPS."""
    for group, members in DEFAULT_SOURCE_GROUPS.items():
        if source_app in members:
            return group
    return source_app


def _group_members(group: str) -> tuple:
    return DEFAULT_SOURCE_GROUPS.get(group, (group,))


def _daily_source_winners(rows: list) -> dict[str, tuple]:
    """Waehlt je Kalendertag GENAU EINE Quellengruppe fuer die Minutenbildung.

    Bisher wurde AVG(value) je Minute ueber ALLE Quellen gebildet — an Tagen
    mit sowohl Garmin- als auch Apple-Messwerten (Apple leitet hier Garmin-Daten
    weiter, over 1000 Tage in dieser DB, siehe compute_clinical/compute_acute_events)
    mischte das zwei unterschiedlich abgetastete, unterschiedlich aufgeloeste
    Reihen desselben Signals in ein Minutenmittel. Gleiche Rangfolge wie
    modules/metric_loader.load_metric_daily: Sammelquellen (AGGREGATOR_SOURCES,
    z. B. apple_health) treten hinter einer vorhandenen Originalquelle zurueck,
    sonst gewinnt die Gruppe mit den meisten Messwerten des Tages. Lokal
    nachgebildet statt load_metric_daily aufgerufen, weil hr_zones die vollen
    Minutenwerte der gewaehlten Quelle braucht, nicht deren Tagesaggregat.
    """
    day_group_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for d, _minute, source_app, _value in rows:
        day_group_counts[d][_source_group(source_app or "")] += 1

    winners: dict[str, tuple] = {}
    for d, counts in day_group_counts.items():
        best_group = min(counts.items(),
                         key=lambda kv: (kv[0] in AGGREGATOR_SOURCES, -kv[1], kv[0]))[0]
        winners[d] = _group_members(best_group)
    return winners


def _bucket_durations(entries: list[tuple[str, int]]) -> list[tuple[int, int]]:
    """
    Rechnet Messpunkte in echte Minuten um.

    @purpose.de Wandelt HR-Messpunkte in (HR, Dauer)-Paare, damit Zonenzeiten
                unabhaengig von der Aufzeichnungsrate des Geraets sind.
    @purpose.en Converts HR samples into (HR, duration) pairs so that zone times
                are independent of the device's recording rate.
    @method.de  Jedem Messpunkt wird der Abstand zum naechsten Messpunkt zugerechnet,
                begrenzt auf GAP_CAP_MIN. Der letzte Punkt eines Tages erhaelt den
                Median der Abstaende dieses Tages (Fallback 1 Minute).
    @method.en  Each sample is credited with the gap to the next sample, capped at
                GAP_CAP_MIN. The last sample of a day gets that day's median gap
                (fallback 1 minute).

    Args:
        entries: nach Zeit sortierte (Minutenstempel, HR)-Paare eines Tages

    Returns:
        Liste aus (HR, Dauer in Minuten)
    """
    if not entries:
        return []

    stamps = [datetime.strptime(m, "%Y-%m-%dT%H:%M") for m, _ in entries]
    gaps   = [max(1, int((b - a).total_seconds() // 60)) for a, b in zip(stamps, stamps[1:])]

    if gaps:
        ordered = sorted(gaps)
        median_gap = ordered[len(ordered) // 2]
    else:
        median_gap = 1

    out: list[tuple[int, int]] = []
    for i, (_minute, hr) in enumerate(entries):
        gap = gaps[i] if i < len(gaps) else median_gap
        out.append((hr, min(gap, GAP_CAP_MIN)))
    return out


def _resolve_max_hr() -> int:
    max_hr = _cfg.max_hr
    if max_hr:
        return max_hr
    dob = _cfg._cfg.get("user", {}).get("birthdate", "")
    if dob:
        today = date_t.today()
        dob_d = datetime.strptime(dob[:10], "%Y-%m-%d").date()
        age = today.year - dob_d.year - ((today.month, today.day) < (dob_d.month, dob_d.day))
        return 220 - age
    return 185


def _resolve_thresholds(pacing_cfg: dict, max_hr: int) -> list[int]:
    if "zone_thresholds_bpm" in pacing_cfg:
        raw = pacing_cfg["zone_thresholds_bpm"]
        if len(raw) == 4:
            return [int(x) for x in raw]
        print(t("Warnung: zone_thresholds_bpm braucht genau 4 Werte. Verwende Prozentwerte.",
                "Warning: zone_thresholds_bpm needs exactly 4 values. Falling back to fractions."))
    return [int(max_hr * f) for f in DEFAULT_FRACTIONS]


def setup_table(conn):
    """
    Erstellt oder migriert die Tabelle daily_hr_zones.

    Args:
        conn: SQLite-Datenbankverbindung
    """
    # Migrate: drop if old schema (zone0_n or tageslast column) still present
    cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_hr_zones)")}
    if cols and ("zone0_n" in cols or "tageslast" in cols):
        conn.execute("DROP TABLE daily_hr_zones")
        conn.commit()

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS daily_hr_zones (
        date        TEXT    NOT NULL,
        person      TEXT    NOT NULL,
        zone0_min   INTEGER,
        zone1_min   INTEGER,
        zone2_min   INTEGER,
        zone3_min   INTEGER,
        zone4_min   INTEGER,
        total_min   INTEGER,
        tagespensum   REAL,
        z1_bpm      INTEGER,
        z2_bpm      INTEGER,
        z3_bpm      INTEGER,
        z4_bpm      INTEGER,
        PRIMARY KEY (date, person)
    );
    """)
    conn.commit()


def compute(conn, d0: str, d1: str, person: str):
    """
    Berechnet HR-Zonen und Tagespensum für einen Zeitraum.

    Verteilt Herzfrequenz-Messungen auf fünf Zonen und berechnet das
    gewichtete Tagespensum für Pacing bei Dysautonomie/PEM.

    Args:
        conn: SQLite-Datenbankverbindung
        d0: Startdatum (YYYY-MM-DD)
        d1: Enddatum (YYYY-MM-DD)
        person: Personen-ID
    """
    pacing_cfg = _cfg._cfg.get("clinical", {}).get("pacing", {})
    max_hr     = _resolve_max_hr()
    thresholds = _resolve_thresholds(pacing_cfg, max_hr)
    weights    = pacing_cfg.get("zone_weights", DEFAULT_WEIGHTS)
    if len(weights) != 5:
        print(t("Warnung: zone_weights braucht genau 5 Einträge. Verwende Standard.",
                "Warning: zone_weights needs exactly 5 entries. Using default."))
        weights = DEFAULT_WEIGHTS

    z1, z2, z3, z4 = thresholds
    w0, w1, w2, w3, w4 = weights

    print(t(
        f"  Zonen: <{z1} | {z1}–{z2} | {z2}–{z3} | {z3}–{z4} | ≥{z4} bpm",
        f"  Zones: <{z1} | {z1}–{z2} | {z2}–{z3} | {z3}–{z4} | ≥{z4} bpm",
    ))
    print(t(
        f"  Gewichte: {w0} / {w1} / {w2} / {w3} / {w4}",
        f"  Weights:  {w0} / {w1} / {w2} / {w3} / {w4}",
    ))

    # Minute-Bucketing: AVG(HR) pro Minute, aber NUR aus der je Tag gewaehlten
    # Quellengruppe (siehe _daily_source_winners) — sonst wuerden z. B. Garmin-
    # und die per Apple weitergeleiteten Garmin-Werte desselben Tages in ein
    # Minutenmittel gemischt. Mehrere Messungen in derselben Minute (innerhalb
    # der gewaehlten Quelle) werden weiterhin zusammengefasst — Minuten OHNE
    # Messung entstehen dadurch aber nicht. Garmin misst z. B. alle 2 Minuten,
    # ein voller Tag ergibt also nur ~720 Buckets. Deshalb wird jedem Bucket
    # unten die Dauer bis zum naechsten Bucket zugerechnet, statt ihn als eine
    # Minute zu zaehlen (siehe _bucket_durations).
    raw_rows = conn.execute("""
        SELECT date,
               strftime('%Y-%m-%dT%H:%M', ts) AS minute,
               source_app,
               value
        FROM measurements
        WHERE metric = 'heart_rate'
          AND value BETWEEN 30 AND 250
          AND person = ?
          AND date BETWEEN ? AND ?
        ORDER BY date, minute
    """, (person, d0, d1)).fetchall()

    winning_members = _daily_source_winners(raw_rows)

    minute_vals: dict[tuple[str, str], list[float]] = defaultdict(list)
    for d, minute, source_app, value in raw_rows:
        if source_app not in winning_members.get(d, ()):
            continue
        minute_vals[(d, minute)].append(value)

    day_rows: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (d, minute), vals in sorted(minute_vals.items()):
        avg_hr = round(sum(vals) / len(vals))
        day_rows[d].append((minute, avg_hr))

    n_days = 0
    for d, entries in sorted(day_rows.items()):
        vals = _bucket_durations(entries)   # [(hr, dauer_min), ...]
        z0n = sum(m for v, m in vals if v < z1)
        z1n = sum(m for v, m in vals if z1 <= v < z2)
        z2n = sum(m for v, m in vals if z2 <= v < z3)
        z3n = sum(m for v, m in vals if z3 <= v < z4)
        z4n = sum(m for v, m in vals if v >= z4)
        total = z0n + z1n + z2n + z3n + z4n   # echte Minuten mit Messabdeckung
        tagespensum = z0n * w0 + z1n * w1 + z2n * w2 + z3n * w3 + z4n * w4

        conn.execute("""
            INSERT OR REPLACE INTO daily_hr_zones
            (date, person, zone0_min, zone1_min, zone2_min, zone3_min, zone4_min,
             total_min, tagespensum, z1_bpm, z2_bpm, z3_bpm, z4_bpm)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (d, person, z0n, z1n, z2n, z3n, z4n, total, tagespensum, z1, z2, z3, z4))
        n_days += 1

    conn.commit()
    print(t(f"  {n_days} Tage berechnet.", f"  {n_days} days computed."))


def main():
    """
    Hauptfunktion: Parsed Argumente und startet die Berechnung.

    Command-Line-Argumente:
        --from: Startdatum (YYYY-MM-DD)
        --to: Enddatum (YYYY-MM-DD)
        --update: Nur neue Tage berechnen
        --recompute: Alle Tage neu berechnen
        --person: Personen-ID (Standard: eigene ID)
    """
    parser = argparse.ArgumentParser(
        description=t("HR-Zonenverteilung und Tagespensum berechnen",
                      "Compute HR zone distribution and daily exertion score"))
    parser.add_argument("--from",    dest="date_from", default=None)
    parser.add_argument("--to",      dest="date_to",   default=None)
    parser.add_argument("--update",  action="store_true",
                        help=t("Nur neue Tage berechnen", "Only compute new days"))
    parser.add_argument("--recompute", action="store_true",
                        help=t("Alle Tage neu berechnen", "Recompute all days"))
    parser.add_argument("--person",  default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person or OWN_PERSON_ID

    with open_db(DB_PATH) as conn:
        setup_table(conn)

        fallback_start = _cfg.data_start or "2017-01-01"

        if args.update and not args.recompute:
            last = conn.execute(
                "SELECT MAX(date) FROM daily_hr_zones WHERE person=?", (person,)
            ).fetchone()[0]
            d0 = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") \
                 if last else fallback_start
        else:
            d0 = args.date_from or fallback_start

        d1 = args.date_to or date_t.today().strftime("%Y-%m-%d")

        if d0 > d1:
            print(t("Nichts zu tun (d0 > d1).", "Nothing to do (d0 > d1)."))
            return

        print(t(f"HR-Zonen & Tagespensum: {d0} → {d1} (Person: {person})",
                f"HR zones & Tagespensum: {d0} → {d1} (person: {person})"))
        compute(conn, d0, d1, person)

    print(t("Fertig.", "Done."))


if __name__ == "__main__":
    main()
