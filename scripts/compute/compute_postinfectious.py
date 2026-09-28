#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Reaktionsmuster-Erkennung — Heuristische Identifizierung via rollierender persönlicher Baseline.

@tier        heuristic
@purpose.de  Erkennt Reaktionsmuster nach Belastung, indem Belastung an Tag N mit
             HRV/RHR-Abweichungen an Tag N+1 relativ zu einer individuellen rollenden
             Baseline verglichen wird.
@purpose.en  Detects reaction patterns after exertion by comparing exertion on day N
             with HRV/RHR deviations on day N+1 relative to an individual rolling baseline.
@method.de   Rollende 28-Tage-Baseline bestimmt personenspezifische Schwellenwerte für
             HRV (Root Mean Square of Successive Differences) und RHR (Ruheherzfrequenz).
             Tag N+1, N+2 und N+3 nach Belastung werden geprüft; ein Reaktionsmuster-Signal
             entsteht, wenn HRV an einem dieser Tage mehr als 1 Standardabweichung unter der
             Baseline liegt ODER RHR mehr als 1 Standardabweichung über der Baseline liegt
             (die stärkste Abweichung der drei Tage wird berichtet). Belastung wird aus
             Schritten, aktivem Energieverbrauch und Stress-Score berechnet.
@method.en   A rolling 28-day baseline sets person-specific thresholds for HRV
             (Root Mean Square of Successive Differences) and RHR (Resting Heart Rate).
             Days N+1, N+2 and N+3 after exertion are checked; a reaction pattern signal is
             raised when HRV on any of these days is more than 1 standard deviation below
             baseline OR RHR is more than 1 standard deviation above baseline (the strongest
             deviation of the three days is reported). Exertion is calculated from steps,
             active energy, and stress score.
@reads       measurements, polar_nightly_hrv, daily_stress, sessions
@writes      pem_correlation
@refs        Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x
             [UNVERIFIZIERT] "Jason et al. 2021, Frontiers in Medicine, doi:10.3389/fmed.2021.637976" — DOI löst nicht auf, kein Jason-Paper 2021 in diesem Journal-Jahrgang auffindbar (Crossref-Journal-Direktsuche negativ). Vor Verwendung/Vertrauen manuell prüfen.

@relevance.de  Ermöglicht die Analyse postinfektiöser Muster, essentiell für die Langzeitüberwachung
@relevance.en  Enables post-infectious pattern analysis, essential for long-term monitoring
@limits.de   Heuristische Methode: ±1-SD-Schwelle ist eine statistische Heuristik, keine klinisch validierte
             Definition. 28-Tage-Baseline ist bei stark schwankenden Daten instabil
             und benötigt mindestens 20 Tage mit gültigen Daten. Reaktionsmuster-Signale basieren
             auf individuellen Mustern und sind nicht verallgemeinerbar. Ersetzt keine
             medizinische Diagnose.
@limits.en   Heuristic method: The ±1 SD threshold is a statistical heuristic, not a clinically validated
             definition. The 28-day baseline is unstable with highly variable data and
             requires at least 20 days of valid data. Reaction pattern signals are based on individual
             patterns and are not generalizable. Does not replace medical diagnosis.
@scoring direct = HRV_Abweichung * 40 + RHR_Abweichung * 30 + Belastungsintensitaet * 30
@usage
    python compute_postinfectious.py
    python compute_postinfectious.py --update
    python compute_postinfectious.py --from 2024-01-01 --to 2024-12-31
    python compute_postinfectious.py --person self
"""

import argparse
import statistics
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH = _cfg.db_path
BASELINE_TAGE = 28


def rolling_baseline(values_dict: dict, datum: str, tage: int = 28) -> tuple:
    """28-days gleitender Mean and Std vor dem Datum."""
    d = datetime.strptime(datum, "%Y-%m-%d")
    vals = []
    for i in range(1, tage + 1):
        v = values_dict.get((d - timedelta(days=i)).strftime("%Y-%m-%d"))
        if v is not None and v > 0:
            vals.append(v)
    if len(vals) < 5:
        return None, None
    return statistics.mean(vals), statistics.stdev(vals)


def _load_z(value: float, values_dict: dict, datum: str,
            fallback_min: float | None = None) -> float:
    """
    Belastungs-z-Wert einer Groesse gegen ihre eigene 28-Tage-Baseline.

    @purpose.de Normiert eine Belastungsgroesse (Trainingslast, Schritte,
                Aktiv-Energie) auf die persoenliche Streuung, damit absolute
                Schwellen entfallen.
    @purpose.en Normalises an exertion metric (training load, steps, active
                energy) against personal variability, avoiding absolute cut-offs.
    @method.de  z = (Wert − Mittel) / Standardabweichung der letzten 28 Tage,
                begrenzt auf 0..3. Ohne belastbare Baseline greift fallback_min.
    @method.en  z = (value − mean) / stdev over the past 28 days, clamped to
                0..3. Without a usable baseline, fallback_min applies.

    Args:
        value:        Tageswert
        values_dict:  {datum: wert} derselben Groesse
        datum:        Bezugstag (YYYY-MM-DD)
        fallback_min: Schwelle, ab der ohne Baseline 1.0 gilt

    Returns:
        z-Wert im Bereich 0..3
    """
    if not value:
        return 0.0
    base_mean, base_sd = rolling_baseline(values_dict, datum)
    if base_mean and base_sd and base_sd > 0:
        return max(0.0, min((value - base_mean) / base_sd, 3.0))
    if fallback_min is not None and value > fallback_min:
        return 1.0
    return 0.0


def main():
    parser = argparse.ArgumentParser(
        description=t("PEM-Korrelationsberechnung", "PEM correlation computation"))
    parser.add_argument("--person", default=None,
                        help=t("Person (default: self)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person or OWN_PERSON_ID

    conn = open_db()

    # Staging pattern: schreibe in pem_correlation_new, dann atomisch tauschen
    conn.executescript("""
    DROP TABLE IF EXISTS pem_correlation_new;
    CREATE TABLE pem_correlation_new (
        date             TEXT NOT NULL,
        person           TEXT NOT NULL,
        training_load    REAL,
        steps            INTEGER,
        active_energy    REAL,
        belastungs_score REAL,
        hrv_heute        REAL,
        rhr_heute        REAL,
        hrv_morgen       REAL,
        rhr_morgen       REAL,
        hrv_uebermorgen  REAL,
        rhr_uebermorgen  REAL,
        hrv_lag3         REAL,
        rhr_lag3         REAL,
        hrv_delta_pct    REAL,
        rhr_delta        REAL,
        pem_lag          INTEGER,
        pem_signal       INTEGER,
        pem_staerke      REAL,
        had_sport        INTEGER DEFAULT 0,
        sport_prior_3d   INTEGER DEFAULT 0,
        source           TEXT DEFAULT 'computed',
        PRIMARY KEY (date, person)
    );
    """)
    conn.commit()

    print(t("Lade Daten ...", "Loading data ..."))
    # Polar Nightly HRV (beste Source)
    hrv = {r[0]: r[1] for r in conn.execute(
        "SELECT date, rmssd_ms FROM polar_nightly_hrv WHERE rmssd_ms > 0 AND person=?",
        (person,)
    ).fetchall()}

    # Fallback 2: naechtliches RMSSD aus measurements, geraeteagnostisch.
    # Vorher: sleep-View mit source_app='oura_app' — die View-Spalte hrv_rmssd_ms
    # ist konstant NULL und 'oura_app' kommt dort nicht vor, der Fallback lief also
    # immer ins Leere, egal welches Geraet Daten lieferte.
    oura_rows = conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE metric IN ('hrv_rmssd','rmssd_ms') AND value > 0 AND person = ? "
        "AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08') GROUP BY date",
        (person,)
    ).fetchall()
    oura_added = sum(1 for r in oura_rows if r[0] and r[0] not in hrv)
    for date, rmssd in oura_rows:
        if date and date not in hrv:
            hrv[date] = rmssd
    if oura_added:
        print(t(f"  + {oura_added} Tage Oura RMSSD für PEM-Analyse ergänzt",
                f"  + {oura_added} days Oura RMSSD added for PEM analysis"))

    # Fallback 3: hrv_rmssd aus measurements (Garmin, cameraHRV, etc.)
    meas_rmssd_rows = conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE metric='hrv_rmssd' AND person=? AND value>0 "
        "GROUP BY date",
        (person,)
    ).fetchall()
    meas_rmssd_added = sum(1 for r in meas_rmssd_rows if r[0] and r[0] not in hrv)
    for date, rmssd in meas_rmssd_rows:
        if date and date not in hrv:
            hrv[date] = rmssd
    if meas_rmssd_added:
        print(t(f"  + {meas_rmssd_added} Tage RMSSD aus measurements ergänzt (Polar/Garmin/Oura/cameraHRV)",
                f"  + {meas_rmssd_added} days RMSSD from measurements added (Polar/Garmin/Oura/cameraHRV)"))

    # Fallback 4: Apple Watch SDNN für Perioden ohne jedes RMSSD-Gerät.
    # SDNN und RMSSD messen unterschiedliche HRV-Domänen — nie im selben Baseline-
    # Fenster mischen. Tage ohne RMSSD bekommen source='sdnn_apple' als Marker.
    hrv_sdnn = {r[0]: r[1] for r in conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE metric='hrv_sdnn' AND source_app='apple_health' AND person=? AND value>0 "
        "GROUP BY date",
        (person,)
    ).fetchall()}
    sdnn_added = sum(1 for d in hrv_sdnn if d not in hrv)
    if sdnn_added:
        print(t(f"  + {sdnn_added} Tage Apple-SDNN für PEM-Analyse ergänzt (source=sdnn_apple)",
                f"  + {sdnn_added} days Apple SDNN added for PEM analysis (source=sdnn_apple)"))

    # Resting heart rate aus daily_stress
    rhr = {r[0]: r[1] for r in conn.execute(
        "SELECT date, resting_hr FROM daily_stress WHERE resting_hr IS NOT NULL AND person=?",
        (person,)
        ).fetchall()}

    # Workout load
    tl = {r[0]: r[1] for r in conn.execute("""
        SELECT date, SUM(training_load)
        FROM training WHERE training_load > 0 AND person = ? GROUP BY date""",
        (person,)).fetchall()}

    # Tage mit mindestens einer Trainings-Session (unabhängig von training_load)
    training_dates = {r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM sessions WHERE type='training' AND person=?",
        (person,)).fetchall()}

    # Steps
    steps = {r[0]: r[1] for r in conn.execute(
        "SELECT date, steps FROM daily_stress WHERE steps IS NOT NULL AND person=?",
        (person,)
        ).fetchall()}

    # Aktiv-Energie je nach Quelle: Apple 'active_energy', Oura 'active_calories',
    # Garmin Connect 'active_kcal'. Pro Tag das Maximum der Quellen-Summen statt der
    # Gesamtsumme — sonst waeren Tage mit zwei Quellen doppelt gezaehlt.
    energy = {r[0]: r[1] for r in conn.execute("""
        SELECT date, MAX(metric_sum) FROM (
            SELECT date, metric, SUM(value) AS metric_sum
            FROM measurements
            WHERE metric IN ('active_energy', 'active_calories', 'active_kcal')
              AND person = ?
            GROUP BY date, metric
        )
        GROUP BY date""", (person,)).fetchall()}

    # All days with HRV-Daten (brauchen Baseline) — SDNN-only-Tage ebenfalls einschließen
    all_dates = sorted(set(hrv.keys()) | set(hrv_sdnn.keys()) | set(tl.keys()))
    rows = []
    pem_count = 0

    print(t(f"Analysiere {len(all_dates)} Tage ...", f"Analysing {len(all_dates)} days ..."))
    for date in all_dates:
        d  = datetime.strptime(date, "%Y-%m-%d")
        d1 = (d + timedelta(days=1)).strftime("%Y-%m-%d")
        d2 = (d + timedelta(days=2)).strftime("%Y-%m-%d")
        d3 = (d + timedelta(days=3)).strftime("%Y-%m-%d")

        # Wähle HRV-Quelle: RMSSD hat Vorrang; SDNN nur wenn kein RMSSD vorhanden.
        # Beide Quellen bleiben in getrennten Dicts — nie im selben Baseline-Fenster mischen.
        use_sdnn = date not in hrv and date in hrv_sdnn
        hrv_dict = hrv_sdnn if use_sdnn else hrv
        row_source = 'sdnn_apple' if use_sdnn else 'computed'

        hrv_heute    = hrv_dict.get(date)
        hrv_morgen   = hrv_dict.get(d1)
        hrv_uebermorgen = hrv_dict.get(d2)
        hrv_lag3     = hrv_dict.get(d3)
        rhr_heute    = rhr.get(date)
        rhr_morgen   = rhr.get(d1)
        rhr_uebermorgen = rhr.get(d2)
        rhr_lag3     = rhr.get(d3)
        tl_heute     = tl.get(date, 0) or 0
        steps_heute  = steps.get(date, 0) or 0
        ae_heute     = energy.get(date, 0) or 0

        # Baseline (28 days vor heute) — aus demselben Dict wie hrv_heute
        hrv_base_mean, hrv_base_sd = rolling_baseline(hrv_dict, date)
        rhr_base_mean, rhr_base_sd = rolling_baseline(rhr, date)

        # Belastung relativ zur persoenlichen 28-Tage-Baseline (0..3).
        # Frueher ausschliesslich aus training_load — bei Alltagsbelastung ohne
        # geloggtes Workout blieb der Score damit dauerhaft 0 und pem_signal
        # konnte per Konstruktion nie ausloesen. Jetzt zaehlt zusaetzlich, was
        # tatsaechlich vorliegt: Schritte und Aktiv-Energie. Es gilt das
        # staerkste Einzelsignal, nicht die Summe.
        belastungs_score = max(
            _load_z(tl_heute,    tl,     date, fallback_min=30),
            _load_z(steps_heute, steps,  date),
            _load_z(ae_heute,    energy, date),
        )

        # HRV-Change Tag+1/+2/+3 vs Baseline — stärkste Abweichung der drei Tage gewinnt.
        # PEM kann verzögert auftreten (>24h), daher reicht ein Lag+1-Check nicht.
        hrv_delta_pct = None
        pem_hrv = False
        pem_lag_hrv = None
        if hrv_base_mean and hrv_base_sd:
            worst_drop_pct = None
            for lag, hrv_lag_wert in ((1, hrv_morgen), (2, hrv_uebermorgen), (3, hrv_lag3)):
                if hrv_lag_wert is None:
                    continue
                drop_pct = (hrv_lag_wert - hrv_base_mean) / hrv_base_mean * 100
                if worst_drop_pct is None or drop_pct < worst_drop_pct:
                    worst_drop_pct = drop_pct
                    hrv_delta_pct = drop_pct
                    pem_lag_hrv = lag
                if hrv_lag_wert < hrv_base_mean - hrv_base_sd:
                    pem_hrv = True

        # RHR-Change Tag+1/+2/+3 vs Baseline — stärkste Abweichung der drei Tage gewinnt.
        rhr_delta = None
        pem_rhr = False
        pem_lag_rhr = None
        if rhr_base_mean:
            rhr_threshold = rhr_base_sd or 3
            worst_rise = None
            for lag, rhr_lag_wert in ((1, rhr_morgen), (2, rhr_uebermorgen), (3, rhr_lag3)):
                if rhr_lag_wert is None:
                    continue
                rise = rhr_lag_wert - rhr_base_mean
                if worst_rise is None or rise > worst_rise:
                    worst_rise = rise
                    rhr_delta = rise
                    pem_lag_rhr = lag
                if rise > rhr_threshold:
                    pem_rhr = True

        pem_lag = pem_lag_hrv if pem_hrv else (pem_lag_rhr if pem_rhr else None)

        # PEM-Signal: erhöhte Last UND messbare Verschlechterung.
        # Schwelle 0,5: Last mindestens 0,5 SD über der 28-Tage-Baseline —
        # bewusst sensitiv gewählt, um auch moderate Overexertion-Tage zu erfassen.
        # 1,0 SD wäre konservativer und würde weniger, dafür klarere PEM-Signale liefern.
        pem_signal = 1 if (belastungs_score > 0.5 and (pem_hrv or pem_rhr)) else 0
        if pem_signal:
            pem_count += 1

        # Stärke 0-3
        pem_staerke = 0
        if pem_signal:
            if pem_hrv: pem_staerke += abs(hrv_delta_pct or 0) / 20
            if pem_rhr: pem_staerke += (rhr_delta or 0) / 5
            pem_staerke = min(round(pem_staerke, 2), 3.0)

        had_sport = 1 if date in training_dates else 0
        sport_prior_3d = 1 if any(
            (d - timedelta(days=i)).strftime("%Y-%m-%d") in training_dates
            for i in range(1, 4)
        ) else 0

        rows.append((
            date, person, tl_heute or None, steps_heute or None, ae_heute or None,
            round(belastungs_score, 3),
            hrv_heute, rhr_heute, hrv_morgen, rhr_morgen,
            hrv_uebermorgen, rhr_uebermorgen, hrv_lag3, rhr_lag3,
            round(hrv_delta_pct, 1) if hrv_delta_pct is not None else None,
            round(rhr_delta, 1) if rhr_delta is not None else None,
            pem_lag,
            pem_signal, pem_staerke, had_sport, sport_prior_3d, row_source
        ))

    conn.executemany("""INSERT OR IGNORE INTO pem_correlation_new
        (date,person,training_load,steps,active_energy,belastungs_score,
         hrv_heute,rhr_heute,hrv_morgen,rhr_morgen,
         hrv_uebermorgen,rhr_uebermorgen,hrv_lag3,rhr_lag3,
         hrv_delta_pct,rhr_delta,pem_lag,
         pem_signal,pem_staerke,had_sport,sport_prior_3d,source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()

    # Atomisch tauschen: bei Fehler bleibt pem_correlation unangetastet
    conn.executescript("""
    BEGIN;
    DROP TABLE IF EXISTS pem_correlation;
    ALTER TABLE pem_correlation_new RENAME TO pem_correlation;
    COMMIT;
    """)

    total_mit_hrv = sum(1 for r in rows if r[6] or r[8])
    print(t(f"\n{len(rows)} Tage | {total_mit_hrv} mit HRV-Daten | {pem_count} PEM-Signale", f"\n{len(rows)} days | {total_mit_hrv} with HRV data | {pem_count} PEM signals"))

    print(t("\n── PEM-Signale nach Jahr ──────────────────────────", "\n── PEM signals by year ──────────────────────────"))
    for r in conn.execute("""
        SELECT strftime('%Y',date), COUNT(*), SUM(pem_signal),
               ROUND(AVG(CASE WHEN pem_signal=1 THEN pem_staerke END),2),
               ROUND(AVG(hrv_delta_pct),1)
        FROM pem_correlation WHERE hrv_morgen IS NOT NULL AND person = ?
        GROUP BY 1 ORDER BY 1""", (person,)):
        pct = (r[2] or 0)/(r[1] or 1)*100
        print(f"  {r[0]}: {r[2]:>3}/{r[1]} PEM ({pct:.0f}%) | Stärke∅{r[3]} | HRV-Δ∅{r[4]}%")

    print(t("\n── Stärkste PEM-Tage (Top 10) ─────────────────────", "\n── Strongest PEM days (top 10) ─────────────────────"))
    for r in conn.execute("""
        SELECT date, training_load, hrv_heute, hrv_morgen, hrv_delta_pct, pem_staerke
        FROM pem_correlation WHERE pem_signal=1 AND person = ?
        ORDER BY pem_staerke DESC LIMIT 10""", (person,)):
        fmt = lambda v, p=0: f"{v:.{p}f}" if v is not None else "—"
        print(f"  {r[0]}: TL={fmt(r[1])} | HRV {fmt(r[2])}→{fmt(r[3])}ms ({fmt(r[4])}%) | Stärke {r[5]}")

    conn.close()
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))


if __name__ == "__main__":
    main()
