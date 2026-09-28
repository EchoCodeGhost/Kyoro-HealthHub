#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Daily Stress Analysis — Multi-source stress index computation (v2 schema).

@tier        heuristic
@purpose.de  Berechnet einen täglichen Stress-Index (0–100) aus HRV, Ruhepuls,
             Schlaf und Trainingslast über mehrere Quellen.
@purpose.en  Computes a daily stress index (0–100) from HRV, resting heart rate,
             sleep and training load across multiple sources.
@method.de   RMSSD als Tagesmittel aus ppi_hrv_advanced (artefakt-/ektopiekorrigierte
             5-Minuten-Fenster; Fallback naive ppi_raw-Tages-RMSSD bei fehlender
             Fensterabdeckung, dann nächtliches Oura), SDNN aus Apple Watch,
             Ruhepuls als 24/7-HR-Perzentil bzw. Geräte-resting_heart_rate, Schlaf
             aus der sleep-View, Garmin-Tagesstress als Korrekturfaktor. Kombiniert
             zu einem Index (höher = mehr Stress). Die HRV-Komponenten (RMSSD, SDNN)
             basieren auf etablierten HRV-Metriken (Task Force 1996).
@method.en   RMSSD as daily mean from ppi_hrv_advanced (artifact-/ectopy-corrected
             5-minute windows; falls back to naive daily ppi_raw RMSSD when window
             coverage is missing, then nightly Oura), SDNN from Apple Watch,
             resting HR as 24/7 HR percentile or device resting_heart_rate, sleep
             from the sleep view, Garmin daily stress as a correction factor.
             Combined into an index (higher = more stress). The HRV components
             (RMSSD, SDNN) are based on established HRV metrics (Task Force 1996).
@scoring
    stress_index = combined(HRV, resting_HR, sleep, training_load, garmin_stress)
    range 0-100, higher = more stress
@reads       measurements, ppi_raw, ppi_hrv_advanced, sleep, training, daily_stress
@writes      daily_stress
@refs        Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

@relevance.de  Ermöglicht die Stressanalyse, essentiell für das psychische Wohlbefinden
@relevance.en  Enables stress analysis, essential for mental well-being
@limits.de   Heuristische Methode: Proprietärer Kombinationsindex, nicht validiert. Gewichtung der
             Komponenten ist heuristisch; quellenabhängige Abdeckung beeinflusst
             die Vergleichbarkeit über die Zeit. HRV-basierte Komponenten nutzen
             etablierte Metriken (Task Force 1996).
@limits.en   Heuristic method: Proprietary combined index, not validated. Component weighting is
             heuristic; source-dependent coverage affects comparability over time.
             HRV-based components use established metrics (Task Force 1996).
@usage
    python compute_stress.py
    python compute_stress.py --from 2025-01-01 --to 2025-12-31
    python compute_stress.py --person self
"""

import argparse
import math
import statistics
from collections import defaultdict
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH = _cfg.db_path


def setup_stress_table(conn):
    conn.executescript("""
    DROP TABLE IF EXISTS daily_stress_new;
    CREATE TABLE daily_stress_new (
        date            TEXT NOT NULL,
        person          TEXT NOT NULL DEFAULT 'unknown',
        resting_hr      REAL,
        rmssd_ms        REAL,
        hrv_sdnn_ms     REAL,
        sleep_quality   REAL,
        sleep_hours     REAL,
        steps           INTEGER,
        training_load   REAL,
        stress_score    REAL,
        source          TEXT,
        PRIMARY KEY (date, person)
    );
    """)
    conn.commit()
    print(t("Staging-Tabelle daily_stress_new erstellt.", "Staging table daily_stress_new created."))


def compute_resting_hr(conn, person) -> dict:
    """Tägliches 5. Perzentil der 24/7-HR + dedizierte resting_heart_rate."""
    print(t("Berechne Ruhepuls aus 24/7-HR ...", "Computing resting HR from 24/7 HR ..."))
    result = {}

    # 5. Perzentil der 24/7 HR (Polar/Garmin/Apple Watch, all Sourcen)
    rows = conn.execute("""
        SELECT date, bpm
        FROM heart_rate
        WHERE bpm BETWEEN 35 AND 100 AND person=?
        ORDER BY date, bpm
    """, (person,)).fetchall()

    day_hrs = defaultdict(list)
    for date, hr in rows:
        day_hrs[date].append(hr)

    for date, hrs in day_hrs.items():
        hrs.sort()
        p5_idx = max(0, int(len(hrs) * 0.05))
        result[date] = round(sum(hrs[p5_idx:p5_idx+5]) / min(5, len(hrs)-p5_idx), 1)

    print(t(f"  {len(result)} Tage 5%-Perzentil HR", f"  {len(result)} days 5th-percentile HR"))

    # Dedizierte resting_heart_rate-Werte (Apple/Oura/Garmin) als Ergänzung
    rhr_rows = conn.execute("""
        SELECT date, AVG(value)
        FROM measurements
        WHERE metric IN ('resting_heart_rate', 'readiness_hr_resting', 'resting_hr')
          AND value BETWEEN 35 AND 120 AND person=?
        GROUP BY date
    """, (person,)).fetchall()
    added = 0
    for date, hr in rhr_rows:
        if date and date not in result:
            result[date] = round(hr, 1)
            added += 1
    if added:
        print(t(f"  + {added} Tage resting_heart_rate ergänzt", f"  + {added} days resting_heart_rate added"))

    return result


def compute_rmssd(conn, person) -> tuple[dict, dict]:
    """RMSSD: primär Tagesmittel aus ppi_hrv_advanced (5-Minuten-Fenster mit
    Artefakt-/Ektopie-Korrektur), Fallback auf naive Tages-RMSSD aus ppi_raw für
    Tage ohne ppi_hrv_advanced-Abdeckung (zu wenige zusammenhängende Beats für ein
    Fenster). Die naive Variante bildet Sukzessiv-Differenzen über die gesamte
    Tragezeit eines Tages inkl. etwaiger Lücken zwischen Sessions — eine Lücke
    zwischen zwei Trageabschnitten zählt dabei wie ein echtes Beat-zu-Beat-Intervall
    und bläht RMSSD auf (empirisch median +133 %, Tage mit dichter Abdeckung
    weniger betroffen als lückenhafte). Daher nur Lückenfüller, kein Ersatz.
    Gibt (rmssd_per_date, source_per_date) zurück."""
    print(t("Berechne RMSSD aus ppi_hrv_advanced ...", "Computing RMSSD from ppi_hrv_advanced ..."))
    result = {}
    source = {}

    adv_rows = conn.execute("""
        SELECT date(fenster_start) d, AVG(rmssd_ms)
        FROM ppi_hrv_advanced
        WHERE person=?
        GROUP BY d
    """, (person,)).fetchall()
    for date, rmssd in adv_rows:
        if date and rmssd is not None:
            result[date] = round(rmssd, 2)
            source[date] = 'ppi_hrv_advanced'
    print(t(f"  {len(result)} Tage ppi_hrv_advanced RMSSD (artefaktkorrigiert)", f"  {len(result)} days ppi_hrv_advanced RMSSD (artifact-corrected)"))

    # Fallback: naive Tages-RMSSD aus ppi_raw für Tage ohne ppi_hrv_advanced-Fenster
    rows = conn.execute("""
        SELECT substr(datetime, 1, 10) d, pulse_ms
        FROM ppi_raw
        WHERE pulse_ms BETWEEN 300 AND 1500 AND person=?
        ORDER BY datetime
    """, (person,)).fetchall()

    day_ppis = defaultdict(list)
    for date, ppi in rows:
        if date not in result:
            day_ppis[date].append(ppi)

    added = 0
    for date, ppis in day_ppis.items():
        if len(ppis) < 10:
            continue
        diffs = [(ppis[i+1] - ppis[i])**2 for i in range(len(ppis)-1)]
        rmssd = math.sqrt(sum(diffs) / len(diffs))
        result[date] = round(rmssd, 2)
        source[date] = 'ppi_raw_fallback'
        added += 1
    if added:
        print(t(f"  + {added} Tage ppi_raw-Fallback (unkorrigiert, keine ppi_hrv_advanced-Abdeckung)", f"  + {added} days ppi_raw fallback (uncorrected, no ppi_hrv_advanced coverage)"))

    # Naechtliches RMSSD aus measurements (Fallback fuer Tage ganz ohne PPI-Daten).
    # Frueher wurde hier die sleep-View mit source_app='oura_app' abgefragt: deren
    # Spalte hrv_rmssd_ms ist in der Kompat-View konstant NULL, und 'oura_app' kommt
    # dort nicht vor — der Fallback konnte also nie greifen, unabhaengig vom Geraet.
    # Jetzt geraeteagnostisch ueber die Nacht-Werte in measurements (ein Wert je Tag).
    wearable_rows = conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric IN ('hrv_rmssd', 'rmssd_ms') AND value > 0 AND person=?
          AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08')
        GROUP BY date
    """, (person,)).fetchall()
    added = 0
    for date, rmssd in wearable_rows:
        if date and date not in result:
            result[date] = round(rmssd, 2)
            source[date] = 'wearable_night_rmssd'
            added += 1
    if added:
        print(t(f"  + {added} Tage Wearable-Nacht-RMSSD ergänzt",
                f"  + {added} days wearable night RMSSD added"))

    return result, source


def compute_apple_hrv(conn, person) -> dict:
    """Täglicher HRV SDNN aus Apple Health (measurements)."""
    print(t("Lade Apple HRV SDNN ...", "Loading Apple HRV SDNN ..."))
    result = {}
    rows = conn.execute("""
        SELECT date, AVG(value)
        FROM measurements
        WHERE metric = 'hrv_sdnn' AND value > 5 AND person=?
        GROUP BY date
    """, (person,)).fetchall()
    for date, val in rows:
        if date:
            result[date] = round(val, 2)
    print(t(f"  {len(result)} Tage Apple HRV", f"  {len(result)} days Apple HRV"))
    return result


def load_activity(conn, person) -> dict:
    """Sleep + Steps aus sleep view + measurements (allen Sourcen)."""
    print(t("Lade Aktivitätsdaten ...", "Loading activity data ..."))
    result = {}

    # Steps aus allen Sourcen (Apple, Polar, Garmin, Oura)
    steps_rows = conn.execute("""
        SELECT date, MAX(value)
        FROM measurements
        WHERE metric = 'steps' AND value > 0 AND person=?
        GROUP BY date
    """, (person,)).fetchall()
    # sleep_* auf None, NICHT auf 0: an Tagen ohne Schlafdaten landete die 0 sonst als
    # echter Messwert in daily_stress (gemessen: die grosse Mehrheit der Tage hatte
    # sleep_hours=0, nur eine Minderheit einen echten Wert). Auswertungen, die
    # daily_stress.sleep_hours ungefiltert lesen, rechnen dann massenhaft Nullschlaf
    # mit — das erzeugt Scheinkorrelationen, deren Staerke sich allein aus der
    # Ausfallstruktur speist.
    for date, steps in steps_rows:
        if date:
            result[date] = {'sleep_quality': None, 'sleep_hours': None, 'steps': int(steps or 0)}

    # Sleep aus sleep view (priorisiert: Oura > Polar > Garmin > Sleep Cycle > Apple)
    # Bevorzuge längste availablee Sleep-Session pro day
    sleep_rows = conn.execute("""
        SELECT date, source_app,
               COALESCE(total_sleep_min, total_sleep_s/60.0, asleep_min) AS sleep_min,
               COALESCE(efficiency_pct/100.0, quality_pct/100.0, sleep_score/100.0) AS quality
        FROM sleep
        WHERE date IS NOT NULL AND person=?
        ORDER BY date,
                 CASE source_app
                   WHEN 'oura_app'      THEN 1
                   WHEN 'polar_connect' THEN 2
                   WHEN 'garmin_connect'THEN 3
                   WHEN 'sleep_cycle'   THEN 4
                   ELSE 5
                 END
    """, (person,)).fetchall()

    # Zweite Quelle: Garmin-Schlaf liegt NICHT in der sleep-View, sondern in
    # sessions + session_metrics. Die Prioritaetsliste oben nennt garmin_connect an
    # dritter Stelle, doch dort kam nie eine Garmin-Zeile an — die View enthaelt in
    # dieser DB ausschliesslich Apple. daily_stress.sleep_hours war dadurch nur fuer
    # den Apple-Zeitraum befuellt; jede Auswertung, die darauf aufsetzt, sah fuer den
    # Rest der Historie "kein Schlaf" statt der vorhandenen Naechte.
    session_rows = conn.execute("""
        SELECT s.date, s.source_app,
               MAX(CASE WHEN m.metric='duration_s'  THEN m.value END) / 60.0 AS sleep_min,
               MAX(CASE WHEN m.metric='sleep_score' THEN m.value END) / 100.0 AS quality
        FROM sessions s
        JOIN session_metrics m ON m.session_id = s.id
        WHERE s.type='sleep' AND s.person=? AND s.date IS NOT NULL
        GROUP BY s.date, s.source_app
    """, (person,)).fetchall()

    _PRIO = {"oura_app": 1, "polar_connect": 2, "garmin_connect": 3,
             "garmin_gdpr": 3, "sleep_cycle": 4}

    # Kandidaten beider Quellen zusammenfuehren und je Nacht den nach Prioritaet
    # besten Eintrag waehlen — sonst entschiede allein die Reihenfolge der Abfragen.
    best: dict = {}
    for date, source, sleep_min, quality in list(sleep_rows) + list(session_rows):
        if not date or not sleep_min:
            continue
        prio = _PRIO.get(source, 5)
        if date not in best or prio < best[date][0]:
            best[date] = (prio, sleep_min, quality)

    seen = set(best)
    for date, (_prio, sleep_min, quality) in best.items():
        if date not in result:
            result[date] = {'sleep_quality': None, 'sleep_hours': None, 'steps': 0}
        result[date]['sleep_hours']   = round(sleep_min / 60.0, 2)
        result[date]['sleep_quality'] = round(quality, 4) if quality is not None else None

    print(t(f"  {len(result)} Tage Aktivität gesamt ({len(seen)} mit Schlaf)", f"  {len(result)} days activity total ({len(seen)} with sleep)"))
    return result


def load_training_load(conn, person) -> dict:
    """Workout load pro day (aus training view)."""
    result = {}
    rows = conn.execute("""
        SELECT date, SUM(training_load)
        FROM training
        WHERE training_load IS NOT NULL AND person=?
        GROUP BY date
    """, (person,)).fetchall()
    for date, tl in rows:
        if date and tl:
            result[date] = round(tl, 1)
    return result


def load_garmin_stress(conn, person) -> dict:
    """Täglicher Averages-Stressscore aus Garmin (measurements)."""
    rows = conn.execute("""
        SELECT date, AVG(value)
        FROM measurements
        WHERE metric = 'avg_stress' AND source_app = 'garmin_connect'
          AND value > 0 AND person=?
        GROUP BY date
    """, (person,)).fetchall()
    result = {r[0]: r[1] for r in rows if r[0]}
    if result:
        print(t(f"  Garmin Tages-Stress: {len(result)} Tage geladen", f"  Garmin daily stress: {len(result)} days loaded"))
    return result


def compute_stress_score(rhr, rhr_baseline, rmssd, rmssd_baseline,
                         sleep_quality, sleep_hours, training_load,
                         garmin_stress=None) -> float:
    """Stressscore 0–100 (höher = mehr Stress / weniger Recovery)."""
    score = 50.0

    if rhr and rhr_baseline:
        score += (rhr - rhr_baseline) * 1.5

    if rmssd and rmssd_baseline and rmssd_baseline > 0:
        score -= (rmssd / rmssd_baseline - 1.0) * 30

    if sleep_quality is not None:
        score += (0.7 - sleep_quality) * 20

    if sleep_hours:
        if sleep_hours < 6:
            score += (6 - sleep_hours) * 5
        elif sleep_hours > 8:
            score -= (sleep_hours - 8) * 2

    if training_load:
        score += min(training_load / 10, 15)

    if garmin_stress is not None:
        score += (garmin_stress - 50) * 0.2

    return round(max(0, min(100, score)), 1)


def main():
    ap = argparse.ArgumentParser(description=t("Stress-Score berechnen", "Compute stress score"))
    ap.add_argument("--person", default=None)
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    person = args.person or OWN_PERSON_ID

    conn = open_db()
    setup_stress_table(conn)

    rhr_data    = compute_resting_hr(conn, person)
    rmssd_data, rmssd_source = compute_rmssd(conn, person)
    apple_hrv   = compute_apple_hrv(conn, person)
    activity    = load_activity(conn, person)
    training    = load_training_load(conn, person)
    garmin_stress_data = load_garmin_stress(conn, person)

    rhr_vals   = sorted(rhr_data.values())
    rmssd_vals = sorted(rmssd_data.values())
    rhr_baseline   = statistics.median(rhr_vals)   if rhr_vals   else 60
    rmssd_baseline = statistics.median(rmssd_vals) if rmssd_vals else 40

    apple_hrv_vals = sorted(apple_hrv.values())
    apple_hrv_baseline = statistics.median(apple_hrv_vals) if apple_hrv_vals else rmssd_baseline
    print(t(f"\nBaselines: Ruhepuls {rhr_baseline} bpm | RMSSD {rmssd_baseline} ms | Apple SDNN {apple_hrv_baseline} ms", f"\nBaselines: resting HR {rhr_baseline} bpm | RMSSD {rmssd_baseline} ms | Apple SDNN {apple_hrv_baseline} ms"))

    all_dates = sorted(d for d in set(list(rhr_data) + list(rmssd_data) +
                       list(apple_hrv) + list(activity) +
                       list(garmin_stress_data)) if d is not None)
    print(t(f"Berechne Stress-Scores für {len(all_dates)} Tage ...", f"Computing stress scores for {len(all_dates)} days ..."))

    rows = []
    for date in all_dates:
        rhr      = rhr_data.get(date)
        rmssd    = rmssd_data.get(date)
        hrv_sdnn = apple_hrv.get(date)
        act      = activity.get(date, {})
        tl       = training.get(date)
        g_stress = garmin_stress_data.get(date)

        rmssd_eff = rmssd or hrv_sdnn
        rmssd_bl  = rmssd_baseline if rmssd else apple_hrv_baseline

        sq = act.get('sleep_quality')
        sh = act.get('sleep_hours')

        score = compute_stress_score(
            rhr, rhr_baseline,
            rmssd_eff, rmssd_bl,
            sq, sh, tl,
            garmin_stress=g_stress
        )

        source_parts = []
        if rhr:      source_parts.append('hr_24_7')
        if rmssd:    source_parts.append(rmssd_source.get(date, 'ppi_raw'))
        if hrv_sdnn: source_parts.append('apple_hrv')
        if act.get('sleep_hours'): source_parts.append('sleep')
        if g_stress: source_parts.append('garmin_stress')

        rows.append((
            date, person, rhr, rmssd, hrv_sdnn,
            sq, sh,
            act.get('steps'), tl,
            score,
            '+'.join(source_parts),
        ))

    conn.executemany("""INSERT OR IGNORE INTO daily_stress_new
        (date, person, resting_hr, rmssd_ms, hrv_sdnn_ms, sleep_quality, sleep_hours,
         steps, training_load, stress_score, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()

    # Atomisch tauschen: bei Fehler bleibt daily_stress unangetastet
    conn.executescript("""
    BEGIN;
    DROP TABLE IF EXISTS daily_stress;
    ALTER TABLE daily_stress_new RENAME TO daily_stress;
    COMMIT;
    """)

    print(t(f"\n{len(rows)} Stress-Tage berechnet.\n", f"\n{len(rows)} stress days computed.\n"))
    print(t("── Stress-Übersicht nach Jahr ──────────────────────────", "── Stress overview by year ──────────────────────────"))
    for r in conn.execute("""
        SELECT strftime('%Y', date) yr,
               ROUND(AVG(stress_score),1)        avg_stress,
               ROUND(AVG(resting_hr),1)          avg_rhr,
               ROUND(AVG(rmssd_ms),1)            avg_rmssd,
               ROUND(AVG(sleep_quality)*100,1)   avg_sleep_pct,
               COUNT(*) n
        FROM daily_stress
        WHERE person=?
        GROUP BY yr ORDER BY yr
    """, (person,)):
        def fmt(v): return f"{v:.1f}" if v is not None else "—"
        print(t(
            f"  {r[0]}: Stress∅ {fmt(r[1]):>5} | RHR∅ {fmt(r[2]):>5} | RMSSD∅ {fmt(r[3]):>6} | Schlaf∅ {fmt(r[4])}% | {r[5]} Tage",
            f"  {r[0]}: Stress∅ {fmt(r[1]):>5} | RHR∅ {fmt(r[2]):>5} | RMSSD∅ {fmt(r[3]):>6} | Sleep∅ {fmt(r[4])}% | {r[5]} days",
        ))

    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))
    conn.close()


if __name__ == "__main__":
    main()
