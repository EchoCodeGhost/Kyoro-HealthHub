#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Clinical Findings Pre-Evaluation — Algorithmic computation of structured clinical findings.

@tier        heuristic
@purpose.de  Berechnet strukturierte klinische Befunde, bevor ein LLM die Daten
             interpretiert — Algorithmen übernehmen die Rechenarbeit, das LLM
             interpretiert nur die Ergebnisse. Dient der Vorstrukturierung für
             medizinische Bewertungen.
@purpose.en  Computes structured clinical findings before an LLM interprets the
             data — algorithms do the computation, the LLM only interprets the
             results. Serves as pre-structuring for medical assessments.
@method.de   Acht Befund-Berechnungen basierend auf physiologischen Daten:
             1. POTS-Kriterium (ΔHR≥30 bpm liegend→stehend) - etabliertes klinisches
                Kriterium (Freeman et al. 2011)
             2. HRV-Change-Points - Erkennung von Zeitpunkten mit signifikantem HRV-Abfall
                (rolling median, 7-Tage-Fenster, Schwelle: 2×MAD)
             3. Post-Exertional Malaise (PEM) - Erkennung von Post-Exertional Malaise Mustern
                basierend auf HRV-Einbruch >20% vs. Baseline in 24-48h nach Belastung
             4. HR-Recovery - Herzfrequenz-Erholung nach Belastung (1-Minuten-Fenster)
             5. Schlaftrend - Lineare Regression der Schlafqualität über 30 Tage
             6. Nocturnal SpO2 Load - Sauerstoffsättigungs-Belastung während des Schlafs
             7. Post-exertional AF - Vorhofflimmern-Erkennung in 3h-Fenster nach Belastung
             8. ANS-Index - Kombinierter Index des autonomen Nervensystems
@method.en   Eight finding computations based on physiological data:
             1. POTS criterion (ΔHR≥30 bpm supine→standing) - established clinical
                criterion (Freeman et al. 2011)
             2. HRV change points - detection of significant HRV drops (rolling median,
                7-day window, threshold: 2×MAD)
             3. Post-Exertional Malaise (PEM) - detection of PEM patterns based on HRV
                drop >20% vs. baseline within 24-48h after exertion
             4. HR recovery - heart rate recovery after exertion (1-minute window)
             5. Sleep trend - linear regression of sleep quality over 30 days
             6. Nocturnal SpO2 load - oxygen saturation burden during sleep
             7. Post-exertional AF - atrial fibrillation detection in 3h window after exertion
             8. ANS index - combined autonomic nervous system index
@scoring
    1. Orthostatic criterion   ΔHR >= 30 bpm supine->standing (POTS criterion)
    2. HRV change points       (when did HRV drop? rolling median, 7-day window)
    3. Post-Exertional Malaise  (HRV drop >20% vs. baseline, 24-48h post-exertion)
    4. HR recovery class        after workout (bpm/min decline in first minute)
    5. Sleep-quality trend      linear regression over 30 days
    6. Nocturnal SpO2 load      burden score (min SpO2, % time <90%)
    7. Post-exertional AF       within 3h after workout
    8. ANS overall status       combined index (HRV + SpO2 + symptoms)
@reads       measurements, polar_nightly_hrv, daily_stress,
             sessions, session_metrics, sleep, health_canonical
@writes      clinical_findings
@refs        Freeman R, Wieling W, Axelrod FB et al. (2011). Consensus statement on the definition of orthostatic hypotension, neurally mediated syncope and the postural tachycardia syndrome. Clinical Autonomic Research, 21(2):69-72. doi:10.1007/s10286-011-0119-5 (POTS Diagnostic Criteria)

@relevance.de  Ermöglicht die Berechnung klinischer Parameter, essentiell für die medizinische Analyse
@relevance.en  Enables calculation of clinical parameters, essential for medical analysis
@limits.de   Heuristische Methode: Nur das POTS-Kriterium (ΔHR≥30 bpm liegend→stehend) ist klinisch etabliert
             (Freeman et al. 2011); alle anderen Befunde sind unvalidierte Heuristiken
             zur Vorstrukturierung. Die Heuristiken basieren auf individuellen Baselines
             und statistischen Schwellenwerten. Ersetzt keine ärztliche Bewertung.
@limits.en   Heuristic method: Only the POTS criterion (ΔHR≥30 bpm supine→standing) is clinically established
             (Freeman et al. 2011); all other findings are unvalidated heuristics for
             pre-structuring. The heuristics are based on individual baselines and
             statistical thresholds. Does not replace clinical assessment.
@usage
    python3 compute_clinical.py
    python3 compute_clinical.py --summary
    python3 compute_clinical.py --person self
    python3 compute_clinical.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import csv
import sqlite3
from datetime import date
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.metric_loader import (
    load_metric_daily, pct_normalizer, source_summary, weakest_confidence,
    DEFAULT_SOURCE_GROUPS,
)
_cfg = _Cfg()

DB_PATH           = _cfg.db_path
ECG_DIR           = _cfg.apple_xml.parent / "electrocardiograms"
HRV_BASELINE_FROM = _cfg.hrv_baseline_from   # in health_config.json setzen
HRV_BASELINE_TO   = _cfg.hrv_baseline_to

# Clinical Thresholde
OI_HR_THRESHOLD     = 30.0   # ΔHR bpm → POTS-Kriterium
OI_HR_BORDERLINE    = 15.0   # ΔHR bpm → grenzwertig
HRV_RECOVERY_THR  = 20.0   # % Einbruch nach Training → PEM-Signal
HR_RECOVERY_GOOD  = 20.0   # bpm/min Abfall in 1. Minute → gut
HR_RECOVERY_BAD   = 12.0   # bpm/min → eingeschränkt
SPO2_MILD         = 95.0   # % → mild eingeschränkt
SPO2_MODERATE     = 90.0   # % → mäßig (klinisch relevant)
SPO2_SEVERE       = 85.0   # % → schwer


# ── Table ───────────────────────────────────────────────────────────────────
def setup_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS clinical_findings_new;
        CREATE TABLE clinical_findings_new (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_date TEXT,
            period_end   TEXT,
            category     TEXT NOT NULL,
            finding_type TEXT NOT NULL,
            value        REAL,
            unit         TEXT,
            threshold    REAL,
            status       TEXT,
            severity     TEXT CHECK(severity IN ('critical','warning','info','normal')),
            description  TEXT NOT NULL,
            source       TEXT,
            person       TEXT NOT NULL DEFAULT 'unknown'
        );
        CREATE INDEX IF NOT EXISTS idx_cfn_category ON clinical_findings_new(category);
        CREATE INDEX IF NOT EXISTS idx_cfn_date     ON clinical_findings_new(finding_date);
    """)
    conn.commit()
    print(t("Staging-Tabelle clinical_findings_new erstellt.", "Staging table clinical_findings_new created."))


def insert(conn, rows: list, person: str) -> int:
    conn.executemany("""
        INSERT INTO clinical_findings_new
            (finding_date, period_end, category, finding_type,
             value, unit, threshold, status, severity, description, source, person)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(*row, person) for row in rows])
    conn.commit()
    return len(rows)


# ── 1. POTS-Kriterium ─────────────────────────────────────────────────────────
def compute_oi_criterion(conn: sqlite3.Connection, person: str) -> list:
    # sessions/session_metrics (type='orthostatic'), nicht die verwaiste
    # orthostatic_tests-Tabelle (leer in der echten DB) bzw. deren
    # orthostatic_test-Compat-View — s. compute_orthostatic_detection.py.
    rows_in = conn.execute("""
        WITH t AS (
            SELECT s.id, s.date,
                   MAX(CASE WHEN sm.metric='hr_delta'     THEN sm.value END) AS hr_delta,
                   MAX(CASE WHEN sm.metric='rmssd_supine' THEN sm.value END) AS rmssd_supine,
                   MAX(CASE WHEN sm.metric='rmssd_stand'  THEN sm.value END) AS rmssd_stand,
                   MAX(CASE WHEN sm.metric='rmssd_delta'  THEN sm.value END) AS rmssd_delta,
                   MAX(CASE WHEN sm.metric='beat_source'  THEN sm.value_text END) AS beat_source
            FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type='orthostatic' AND s.person=?
            GROUP BY s.id
        )
        SELECT date, hr_delta, rmssd_supine, rmssd_stand, rmssd_delta, beat_source
        FROM t
        WHERE hr_delta IS NOT NULL
        ORDER BY date
    """, (person,)).fetchall()
    if not rows_in:
        return []

    results = []
    n_total   = len(rows_in)
    n_oi    = sum(1 for r in rows_in if r[1] >= OI_HR_THRESHOLD)
    n_border  = sum(1 for r in rows_in if OI_HR_BORDERLINE <= r[1] < OI_HR_THRESHOLD)
    avg_delta = round(sum(r[1] for r in rows_in) / n_total, 1)
    max_delta = max(r[1] for r in rows_in)
    # beat_source fehlt bei aelteren, vor Einfuehrung dieser Metrik berechneten
    # Sessions -- dann als 'ppi_raw' angenommen (bis dahin die einzige Quelle),
    # s. compute_orthostatic_detection.py.
    n_ppi_raw = sum(1 for r in rows_in if (r[5] or "ppi_raw") == "ppi_raw")

    # RMSSD-Einbruch liegend→stehend
    rmssd_pairs = [(r[2], r[3]) for r in rows_in if r[2] and r[3] and r[2] > 0]
    avg_rmssd_drop = round(
        sum((s - st) / s * 100 for s, st in rmssd_pairs) / len(rmssd_pairs), 1
    ) if rmssd_pairs else None

    d_first = rows_in[0][0]
    d_last  = rows_in[-1][0]

    # Gesamtbewertung
    beat_src_note = f" (davon {n_ppi_raw}/{n_total} mit RMSSD-Rohdaten, Rest nur HF-Sprung)"
    if n_oi > 0:
        status   = "met"
        severity = "warning"
        desc = (f"POTS-Kriterium (ΔHR ≥{OI_HR_THRESHOLD} bpm): {n_oi}/{n_total} Tests erfüllt. "
                f"ΔHR ∅{avg_delta} bpm (max {max_delta} bpm).{beat_src_note}")
    elif n_border > 0:
        status   = "borderline"
        severity = "warning"
        desc = (f"POTS grenzwertig (ΔHR 15–29 bpm): {n_border}/{n_total} Tests. "
                f"ΔHR ∅{avg_delta} bpm (max {max_delta} bpm). Kipptisch-Test empfohlen."
                f"{beat_src_note}")
    else:
        status   = "not_met"
        severity = "normal"
        desc = (f"POTS-Kriterium nicht erfüllt. ΔHR ∅{avg_delta} bpm (max {max_delta} bpm)."
                f"{beat_src_note}")

    results.append((d_first, d_last, "pots", "pots_criterion",
                    avg_delta, "bpm", OI_HR_THRESHOLD, status, severity, desc,
                    "sessions/session_metrics"))

    if avg_rmssd_drop is not None:
        sev = "warning" if avg_rmssd_drop > 70 else "info"
        results.append((d_first, d_last, "pots", "rmssd_orthostatic_drop",
                        avg_rmssd_drop, "%", 50.0,
                        "critical" if avg_rmssd_drop > 80 else "elevated",
                        sev,
                        f"RMSSD-Einbruch liegend→stehend: ∅{avg_rmssd_drop}% "
                        f"({'stark eingeschränkte' if avg_rmssd_drop>80 else 'eingeschränkte'} "
                        f"vagale Antwort)",
                        "sessions/session_metrics"))

    # Einzeltests
    for d, delta, rs, rst, rd in rows_in:
        if delta >= OI_HR_THRESHOLD:
            results.append((d, None, "pots", "pots_single_test",
                            delta, "bpm", OI_HR_THRESHOLD, "met", "warning",
                            f"POTS-Kriterium erfüllt: ΔHR {delta} bpm",
                            "sessions/session_metrics"))

    return results


# ── 2. HRV Change-Points ──────────────────────────────────────────────────────
def compute_hrv_changepoints(conn: sqlite3.Connection, person: str) -> list:
    hrv = conn.execute("""
        SELECT date, rmssd_ms FROM polar_nightly_hrv
        WHERE rmssd_ms > 0 AND person=? ORDER BY date
    """, (person,)).fetchall()
    if len(hrv) < 30:
        return []

    results = []
    dates = [r[0] for r in hrv]
    vals  = [r[1] for r in hrv]

    # Gleitender 30-days-Average
    def moving_avg(v, w=30):
        return [sum(v[max(0,i-w):i+1]) / len(v[max(0,i-w):i+1]) for i in range(len(v))]

    ma = moving_avg(vals)

    # Baseline (erste 6 months)
    baseline_vals = vals[:min(180, len(vals)//4)]
    baseline = round(sum(baseline_vals) / len(baseline_vals), 1)

    # Aktuell (letzte 30 days)
    current = round(sum(vals[-30:]) / 30, 1)
    total_drop_pct = round((baseline - current) / baseline * 100, 1) if baseline > 0 else 0

    # Größten Einbruch innerhalb from 60 daysn finden (Change-Point)
    best_drop = 0
    best_idx  = 0
    for i in range(30, len(ma) - 30):
        pre  = sum(vals[max(0,i-30):i]) / min(30, i)
        post = sum(vals[i:min(len(vals),i+30)]) / min(30, len(vals)-i)
        drop = pre - post
        if drop > best_drop:
            best_drop = drop
            best_idx  = i

    cp_date = dates[best_idx] if best_idx > 0 else None
    pre_cp  = round(sum(vals[max(0,best_idx-30):best_idx]) / min(30, best_idx), 1) if best_idx > 0 else None
    post_cp = round(sum(vals[best_idx:min(len(vals),best_idx+30)]) / min(30, len(vals)-best_idx), 1)

    # Langzeit-Summary
    results.append((dates[0], dates[-1], "hrv", "hrv_longterm",
                    total_drop_pct, "%", None, None,
                    "critical" if total_drop_pct > 50 else "warning",
                    f"HRV-Langzeitentwicklung: Baseline ∅{baseline}ms → aktuell ∅{current}ms "
                    f"({'-' if total_drop_pct>0 else '+'}{abs(total_drop_pct)}%)",
                    "polar_nightly_hrv"))

    # Change-Point
    if cp_date and pre_cp:
        cp_drop_pct = round((pre_cp - post_cp) / pre_cp * 100, 1) if pre_cp > 0 else 0
        results.append((cp_date, None, "hrv", "hrv_changepoint",
                        cp_drop_pct, "%", None, None,
                        "critical" if cp_drop_pct > 40 else "warning",
                        f"HRV-Change-Point: {cp_date} — vor: ∅{pre_cp}ms, after: ∅{post_cp}ms "
                        f"(Einbruch -{cp_drop_pct}%)",
                        "polar_nightly_hrv"))

    # Jährliche HRV-Averagee als Verlaufsübersicht
    from collections import defaultdict
    hrv_by_year: dict = defaultdict(list)
    for d, v in hrv:
        hrv_by_year[d[:4]].append(v)
    for year in sorted(hrv_by_year):
        vals_y = hrv_by_year[year]
        if len(vals_y) >= 5:
            avg = round(sum(vals_y) / len(vals_y), 1)
            results.append((f"{year}-01-01", f"{year}-12-31", "hrv", "hrv_phase",
                            avg, "ms", None, year, "info",
                            f"HRV {year}: ∅{avg}ms ({len(vals_y)} Nights)",
                            "polar_nightly_hrv"))

    return results


# ── 3. Post-exertionelle HRV-Einbrüche ───────────────────────────────────────
def compute_pem_hrv(conn: sqlite3.Connection, person: str) -> list:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "pem_correlation" not in tables:
        return [(None, None, "pem", "pem_summary", 0, "events", None,
                 "none", "normal", "pem_correlation nicht vorhanden — compute_postinfectious zuerst ausführen.",
                 "pem_correlation")]

    pem = conn.execute("""
        SELECT date, training_load, hrv_heute, hrv_morgen, hrv_delta_pct,
               pem_signal, pem_staerke
        FROM pem_correlation
        WHERE pem_signal = 1 AND person=?
        ORDER BY date
    """, (person,)).fetchall()

    if not pem:
        return [(None, None, "pem", "pem_summary", 0, "events", None,
                 "none", "normal", "No PEM signals detektiert.",
                 "pem_correlation")]

    n_pem = len(pem)
    total = conn.execute("SELECT COUNT(*) FROM pem_correlation WHERE person=?",
                         (person,)).fetchone()[0]
    avg_drop = round(sum(abs(r[4]) for r in pem if r[4]) / n_pem, 1) if n_pem else 0
    avg_load = round(sum(r[1] for r in pem if r[1]) / n_pem, 1) if n_pem else 0

    results = [(pem[0][0], pem[-1][0], "pem", "pem_summary",
                float(n_pem), "events", None, None, "warning",
                f"PEM signals: {n_pem}/{total} days ({round(n_pem/total*100,1)}%) — "
                f"∅HRV-Einbruch -{avg_drop}% nach Workout (∅Last {avg_load})",
                "pem_correlation")]

    # Häufung by year
    by_year: dict = {}
    for r in pem:
        y = r[0][:4]
        by_year[y] = by_year.get(y, 0) + 1
    for y, n in sorted(by_year.items()):
        results.append((f"{y}-01-01", f"{y}-12-31", "pem", "pem_by_year",
                        float(n), "events", None, y, "info",
                        f"PEM signals {y}: {n} Ereignisse",
                        "pem_correlation"))

    return results


# ── 4. HR-Recovery-Classification ─────────────────────────────────────────────
def compute_hr_recovery(conn: sqlite3.Connection, person: str) -> list:
    trainings = conn.execute("""
        SELECT ts_start, ts_end, sport, hr_max
        FROM training
        WHERE hr_max > 100 AND ts_end IS NOT NULL AND person=?
        ORDER BY ts_start
    """, (person,)).fetchall()

    if not trainings:
        return []

    # Batch per Datum: idx_meas_date nutzbar, verhindert N+1 auf 39M-Zeilen-Tabelle.
    import bisect
    from collections import defaultdict
    dates_needed = sorted({t[1][:10] for t in trainings})
    ph = ",".join("?" * len(dates_needed))
    hr_by_date: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    for ts, bpm in conn.execute(
        f"SELECT ts, value FROM measurements WHERE metric='heart_rate' AND person=? AND date IN ({ph}) ORDER BY ts",
        (person, *dates_needed),
    ):
        lst_ts, lst_bpm = hr_by_date[ts[:10]]
        lst_ts.append(ts)
        lst_bpm.append(bpm)

    def _lookup(ts_end: str, lo_s: int, hi_s: int) -> "float | None":
        lst_ts, lst_bpm = hr_by_date[ts_end[:10]]
        if not lst_ts:
            return None
        lo = ts_end[:10] + "T" + (
            __import__("datetime").datetime.fromisoformat(ts_end) +
            __import__("datetime").timedelta(seconds=lo_s)
        ).strftime("%H:%M:%S")
        hi = ts_end[:10] + "T" + (
            __import__("datetime").datetime.fromisoformat(ts_end) +
            __import__("datetime").timedelta(seconds=hi_s)
        ).strftime("%H:%M:%S")
        i = bisect.bisect_left(lst_ts, lo)
        j = bisect.bisect_right(lst_ts, hi)
        return lst_bpm[i] if i < j else None

    rows = []
    for start_time, stop_time, sport_name, hr_max in trainings:
        rows.append((start_time, stop_time, sport_name, hr_max,
                     _lookup(stop_time, 0, 30),
                     _lookup(stop_time, 30, 180)))

    good = 0; border = 0; poor = 0; n_valid = 0
    for st, _, sport, hmax, hsofort, h1min in rows:
        if hmax and h1min:
            delta = hmax - h1min
            n_valid += 1
            if delta >= HR_RECOVERY_GOOD:
                good += 1
            elif delta >= HR_RECOVERY_BAD:
                border += 1
            else:
                poor += 1

    if n_valid == 0:
        return []

    pct_poor = round(poor / n_valid * 100, 1)
    status   = "impaired" if pct_poor > 30 else ("borderline" if pct_poor > 10 else "normal")
    severity = "warning" if pct_poor > 30 else ("info" if pct_poor > 10 else "normal")

    return [(rows[0][0][:10], rows[-1][0][:10], "hr_recovery", "hr_recovery_summary",
             float(pct_poor), "%", HR_RECOVERY_BAD, status, severity,
             f"HR-Recovery nach Workout ({n_valid} evaluable): "
             f"gut {good} | grenzwertig {border} | eingeschränkt {poor} "
             f"({pct_poor}% eingeschränkt, <{HR_RECOVERY_BAD} bpm/min in 1. Minute)",
             "training+heart_rate")]


# ── 5. Sleep — all Sourcen zusammengeführt ─────────────────────────────────
def compute_sleep_trend(conn: sqlite3.Connection, person: str) -> list:
    """
    Baut eine quellen-bereinigte Nacht-für-Nacht-Tabelle aus der sleep view.
    Priorität: oura_app > polar_connect > garmin_connect > sleep_cycle > apple_health
    Sleep Cycle metrics (Schnarchen, Atemstörungen) werden via session_metrics ergänzt.
    """
    # Beste Sleepsession pro day aus sleep view nach Sourcen-Priorität
    nights: dict = {}
    sleep_rows = conn.execute("""
        SELECT date, source_app,
               COALESCE(total_sleep_min, total_sleep_s/60.0, asleep_min) AS sleep_min,
               efficiency_pct
        FROM sleep
        WHERE date IS NOT NULL AND person=?
          AND COALESCE(total_sleep_min, total_sleep_s/60.0, asleep_min) > 60
        ORDER BY date,
                 CASE source_app
                   WHEN 'oura_app'       THEN 1
                   WHEN 'polar_connect'  THEN 2
                   WHEN 'garmin_connect' THEN 3
                   WHEN 'sleep_cycle'    THEN 4
                   ELSE 5
                 END
    """, (person,)).fetchall()

    # Zweite Quelle: Garmin-Schlaf liegt NICHT in der sleep-View, sondern in
    # sessions + session_metrics. Die Prioritaetsliste oben nennt garmin_connect
    # an Position 3, aber die View selbst fuehrt nie eine Garmin-Zeile, egal wie
    # viele Garmin-Naechte importiert sind -- ohne diese zweite Quelle wuerde die
    # Schlafauswertung Garmin-Naechte stillschweigend ignorieren.
    session_rows = conn.execute("""
        SELECT s.date, s.source_app, m.value/60.0 AS sleep_min
        FROM sessions s
        JOIN session_metrics m ON m.session_id = s.id AND m.metric = 'duration_s'
        WHERE s.type='sleep' AND s.person=? AND s.date IS NOT NULL AND m.value > 3600
    """, (person,)).fetchall()

    _PRIO = {"oura_app": 1, "polar_connect": 2, "garmin_connect": 3,
             "garmin_gdpr": 3, "sleep_cycle": 4}

    # Kandidaten beider Quellen zusammenfuehren und je Nacht den nach Prioritaet
    # besten Eintrag waehlen — sonst gewaenne allein die Reihenfolge der Abfragen.
    candidates: dict = {}
    for d, source, sleep_min, eff in [(r[0], r[1], r[2], r[3]) for r in sleep_rows] \
            + [(r[0], r[1], r[2], None) for r in session_rows]:
        if not sleep_min:
            continue
        prio = _PRIO.get(source, 5)
        if d not in candidates or prio < candidates[d][0]:
            candidates[d] = (prio, source, sleep_min, eff)

    for d, (_prio, source, sleep_min, eff) in candidates.items():
        nights[d] = {"h": round(sleep_min / 60, 2), "source": source,
                     "efficiency": eff, "snore": None, "bd": None}

    # Sleep Cycle Anreicherung (Snoring/Breathing disturbances) via session_metrics
    for d, snore_s, bd in conn.execute("""
        SELECT s.date,
               MAX(CASE WHEN sm.metric='snore_s'          THEN sm.value END),
               MAX(CASE WHEN sm.metric='breathing_disrupt'THEN sm.value END)
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.source_app='sleep_cycle' AND s.type='sleep' AND s.person=?
        GROUP BY s.date
    """, (person,)):
        if d in nights:
            if snore_s is not None:
                nights[d]["snore"] = round(snore_s / 60.0, 1)
            if bd is not None:
                nights[d]["bd"] = bd

    if not nights:
        return []

    sorted_nights = sorted(nights.items())
    all_dates = [d for d, _ in sorted_nights]
    all_h     = [v["h"] for _, v in sorted_nights]
    sources   = {v["source"] for _, v in sorted_nights}

    n_total   = len(sorted_nights)
    avg_h     = round(sum(all_h) / n_total, 1)
    n_ander6  = sum(1 for h in all_h if h < 6)
    n_ander7  = sum(1 for h in all_h if h < 7)
    pct_u6    = round(n_ander6 / n_total * 100, 1)

    # Source-Verteilung
    src_counts = {}
    for _, v in sorted_nights:
        s = v["source"]
        src_counts[s] = src_counts.get(s, 0) + 1
    src_str = " | ".join(f"{s}: {n}" for s, n in sorted(src_counts.items()))

    results = [(all_dates[0], all_dates[-1], "sleep", "sleep_combined_summary",
                avg_h, "h", 7.0,
                "short" if avg_h < 6.5 else "normal",
                "warning" if pct_u6 > 40 else "info",
                f"Sleep gesamt ({n_total} Nights, {all_dates[0]}–{all_dates[-1]}): "
                f"∅{avg_h}h | {n_ander6} Nights <6h ({pct_u6}%) | "
                f"{n_ander7} Nights <7h | Sourcen: {src_str}",
                "+".join(sorted(sources)))]

    # Kurze Nights by year
    by_year: dict = {}
    for d, v in sorted_nights:
        y = d[:4]
        if y not in by_year:
            by_year[y] = {"n": 0, "u6": 0, "h_sum": 0.0}
        by_year[y]["n"]     += 1
        by_year[y]["h_sum"] += v["h"]
        if v["h"] < 6:
            by_year[y]["u6"] += 1

    for y, s in sorted(by_year.items()):
        avg = round(s["h_sum"] / s["n"], 1)
        pct = round(s["u6"] / s["n"] * 100, 1)
        sev = "warning" if pct > 40 else "info"
        results.append((f"{y}-01-01", f"{y}-12-31", "sleep", "sleep_short_nights_by_year",
                        float(s["u6"]), "Nights", 6.0, y, sev,
                        f"Sleep {y}: ∅{avg}h | {s['u6']}/{s['n']} Nights <6h ({pct}%)",
                        "combined"))

    # Sleep-Score-Trend (Polar, lineare Regression)
    polar_scores = conn.execute("""
        SELECT date, sleep_score FROM sleep
        WHERE source_app='polar_connect' AND sleep_score > 0 AND person=?
        ORDER BY date
    """, (person,)).fetchall()
    if len(polar_scores) >= 60:
        n = len(polar_scores)
        xs = list(range(n)); ys = [r[1] for r in polar_scores]
        mx = sum(xs)/n; my = sum(ys)/n
        cov = sum((xs[i]-mx)*(ys[i]-my) for i in range(n))
        var = sum((xs[i]-mx)**2 for i in range(n))
        slope_yr = round(cov / var * 365, 2) if var > 0 else 0
        f90 = round(sum(r[1] for r in polar_scores[:90])/90, 1)
        l90 = round(sum(r[1] for r in polar_scores[-90:])/90, 1)
        trend = "sinkend" if slope_yr < -2 else ("steigend" if slope_yr > 2 else "stabil")
        results.append((polar_scores[0][0], polar_scores[-1][0],
                        "sleep", "sleep_score_trend",
                        slope_yr, "Points/Jahr", None, trend,
                        "warning" if slope_yr < -3 else "info",
                        f"Polar Sleep Score Trend: {slope_yr:+.1f} Points/Jahr ({trend}) "
                        f"— erste 90 Nights ∅{f90}, letzte 90 ∅{l90}",
                        "sleep"))

    # Sleep Cycle Zusatzinfo (Snoring + Breathing disturbances)
    sc_nights = [(d, v) for d, v in sorted_nights if v.get("snore") is not None]
    if sc_nights:
        avg_snore = round(sum(v["snore"] for _, v in sc_nights) / len(sc_nights), 1)
        avg_bd    = round(sum(v["bd"] for _, v in sc_nights if v["bd"]) /
                          max(1, sum(1 for _, v in sc_nights if v["bd"])), 2)
        n_sc = len(sc_nights)
        results.append((sc_nights[0][0], sc_nights[-1][0],
                        "sleep", "sleep_cycle_enrichment",
                        avg_snore, "min/Night", None, None, "info",
                        f"Sleep Cycle Anreicherung ({n_sc} Nights): "
                        f"Snoring ∅{avg_snore}min | Breathing disturbances ∅{avg_bd}/h",
                        "sleep_cycle"))

    return results


def _source_group_members(source_app: "str | None") -> tuple:
    """Alle source_app-Werte derselben Marke wie source_app.

    Zusatzstatistiken (Einzelwert-Schwellen, Nachtanteil) muessen aus denselben
    Rohzeilen stammen wie der von load_metric_daily fuer diesen Tag gewaehlte
    Wert — sonst waere die Dedup-Auswahl fuer den Haupt-Tageswert zwar korrekt,
    die Zusatzzahlen aber weiterhin quellenuebergreifend gemischt.
    """
    for members in DEFAULT_SOURCE_GROUPS.values():
        if source_app in members:
            return members
    return (source_app,) if source_app else ()


# ── 6. Nächtliche SpO2-Load ──────────────────────────────────────────────
def compute_spo2_burden(conn: sqlite3.Connection, person: str) -> list:
    results = []

    # Wearable-SpO2, geraeteagnostisch UND quellendedupliziert.
    #
    # Frueher gab es hier nur einen Apple-Zweig (metric='oxygen_saturation',
    # Bruchwert 0..1) und weiter unten einen Polar-Zweig. Ein Garmin-Zweig fehlte
    # vollstaendig — in einer Garmin-DB entstand dadurch KEIN einziger
    # SpO2-Eintrag in clinical_findings, obwohl Hunderttausende Messwerte
    # vorlagen. Beide Metriknamen wurden gelesen und jeder Messwert auf Prozent
    # normalisiert (Apple 0..1 -> %, alle anderen bereits %) — das blieb.
    # NEU: die GROUP BY date-Mittelung pool­te bislang ALLE Quellen eines Tages
    # ungewichtet zusammen. An Tagen, an denen dieselbe Messung sowohl ueber
    # garmin_connect als auch ueber garmin_gdpr importiert war (>1100 Tage in
    # dieser DB), zaehlte sie doppelt in Tagesmittel/-minimum. load_metric_daily
    # waehlt je Tag GENAU EINE Quelle (Exportpfade derselben Marke gelten als
    # eine Quelle, reine Sammelquellen wie apple_health treten hinter der
    # Originalquelle zurueck) und liefert Sensorklasse/Konfidenz gleich mit.
    date_range = conn.execute("""
        SELECT MIN(date), MAX(date) FROM measurements
        WHERE metric IN ('spo2','oxygen_saturation') AND person=?
    """, (person,)).fetchone()

    if date_range and date_range[0]:
        d_from, d_to = date_range
        min_days = load_metric_daily(conn, ('spo2', 'oxygen_saturation'), d_from, d_to,
                                      person=person, agg='min',
                                      normalizer=pct_normalizer, valid_range=(50.0, 100.0))
        avg_days = load_metric_daily(conn, ('spo2', 'oxygen_saturation'), d_from, d_to,
                                      person=person, agg='avg',
                                      normalizer=pct_normalizer, valid_range=(50.0, 100.0))

        raw_rows = conn.execute("""
            SELECT date, ts, source_app, value FROM measurements
            WHERE metric IN ('spo2','oxygen_saturation') AND person=?
              AND date BETWEEN ? AND ? AND value IS NOT NULL
        """, (person, d_from, d_to)).fetchall()

        per_day: dict[str, dict] = {}
        for r_date, ts, source_app, value in raw_rows:
            winning = min_days.get(r_date)
            if winning is None:
                continue
            if source_app not in _source_group_members(winning.source_app):
                continue
            v = pct_normalizer(value, None)
            if not (50.0 <= v <= 100.0):
                continue
            d = per_day.setdefault(r_date, {"n": 0, "sev": 0, "mod": 0, "night": False})
            d["n"] += 1
            if v < 85:
                d["sev"] += 1
            elif v < 90:
                d["mod"] += 1
            hour = (ts or "")[11:13]
            if hour and (hour < "07" or hour >= "21"):
                d["night"] = True

        dates_sorted = sorted(min_days.keys())
        if dates_sorted:
            n_days   = len(dates_sorted)
            n_sev    = sum(1 for d in dates_sorted if per_day.get(d, {}).get("sev", 0) > 0)
            n_mod    = sum(1 for d in dates_sorted if per_day.get(d, {}).get("mod", 0) > 0)
            min_ever = round(min(min_days[d].value for d in dates_sorted), 1)
            avg_min  = round(sum(min_days[d].value for d in dates_sorted) / n_days, 1)
            total_n  = sum(per_day.get(d, {}).get("n", 0) for d in dates_sorted)
            n_nights_measured = sum(1 for d in dates_sorted if per_day.get(d, {}).get("night"))

            # n_sev/n_mod zaehlen Tage mit MINDESTENS EINEM Einzelmesswert unter der
            # Schwelle, nicht Tage unterhalb der Schwelle. Frueher stand im Text
            # "days with <85%" und der Schweregrad wurde daraus auf "high"/"critical"
            # gesetzt: optisches Handgelenks-SpO2 erzeugt regelmaessig kurze
            # Tiefstwerte (Bewegung, Sensorkontakt), sodass fast jeder Tag als
            # kritischer Befund erschien. Der Schweregrad richtet sich weiterhin nach
            # den TAGESMITTELN (anhaltende Erniedrigung), die Einzelwert-Zaehlungen
            # bleiben als Zusatzinfo mit korrekter Bezeichnung erhalten.
            n_days_avg_lt90 = sum(1 for d in dates_sorted if d in avg_days and avg_days[d].value < 90)
            n_days_avg_lt95 = sum(1 for d in dates_sorted if d in avg_days and 90 <= avg_days[d].value < 95)
            sev = "warning" if n_days_avg_lt90 > 5 else "info"

            # Konfidenz/Quellenherkunft statt eines fest formulierten
            # Handgelenks-Hinweises: kommt der Tageswert von einem Fingerclip-
            # Oximeter statt vom optischen Handgelenkssensor, gilt der alte
            # pauschale Vorbehalt nicht mehr — sensor_confidence.py entscheidet
            # das je Sensorklasse.
            conf = weakest_confidence(min_days)
            src_counts = source_summary(min_days)
            src_str = ", ".join(f"{k}:{v}" for k, v in src_counts.items())
            day_notes = sorted({d.note for d in min_days.values() if d.note})
            note_str = f" — {' / '.join(day_notes)}" if day_notes else ""

            results.append((dates_sorted[0], dates_sorted[-1], "spo2", "spo2_wearable",
                            float(n_days_avg_lt90), "days", SPO2_SEVERE,
                            "moderate" if n_days_avg_lt90 > 5 else "low",
                            sev,
                            f"Wearable-SpO2 ({n_days} days, {total_n} Messungen, "
                            f"{n_nights_measured} with Night-Messung, Quellen: {src_str}, "
                            f"Konfidenz: {conf}): "
                            f"Tage mit Tagesmittel <90%: {n_days_avg_lt90} | 90-94%: {n_days_avg_lt95} | "
                            f"Tage mit einzelnem Messwert <85%: {n_sev} | <90%: {n_mod} | "
                            f"niedrigster Einzelwert: {min_ever}% | ∅Tages-Min: {avg_min}%"
                            f"{note_str}",
                            "measurements"))

    # Polar SpO2 (in measurements als spo2 in % or oxygen_saturation 0..1)
    polar_spo2 = conn.execute("""
        SELECT date, MIN(value), AVG(value),
               SUM(CASE WHEN value < 90 THEN 1 ELSE 0 END)
        FROM measurements
        WHERE metric='spo2' AND source_app='polar_connect' AND person=?
        GROUP BY date ORDER BY date
    """, (person,)).fetchall()

    if polar_spo2:
        min_ever = min(r[1] for r in polar_spo2)
        n_low    = sum(1 for r in polar_spo2 if r[3] > 0)
        results.append((polar_spo2[0][0], polar_spo2[-1][0], "spo2", "spo2_polar",
                        float(min_ever), "%", SPO2_MODERATE,
                        "low" if min_ever < 90 else "normal",
                        "warning" if min_ever < 90 else "info",
                        f"Polar SpO2 ({len(polar_spo2)} days): "
                        f"Min {min_ever}% | {n_low} Messungen <90%",
                        "measurements"))

    return results


# ── 7. Post-exertionelles Atrial fibrillation ──────────────────────────────────────
def compute_af_pattern(conn: sqlite3.Connection, person: str) -> list:
    if not ECG_DIR.exists():
        return []

    af_events = []
    for f in sorted(ECG_DIR.glob("ecg_*.csv")):
        meta = {}
        try:
            for row in csv.reader(open(f)):
                if len(row) >= 2 and row[0] in ("Aufzeichnungsdatum", "Klassifizierung"):
                    meta[row[0]] = row[1].strip()
                if row and row[0] == "Einheit":
                    break
        except Exception:
            continue
        if "Atrial fibrillation" in meta.get("Klassifizierung", ""):
            af_events.append(meta.get("Aufzeichnungsdatum", "")[:16])

    if not af_events:
        return [(None, None, "arrhythmia", "af_total", 0.0, "events",
                 None, "none", "normal", "No Atrial fibrillation in EKG-Aufzeichnungen.",
                 "ecg_csv")]

    results = []
    n_post_exertional = 0
    post_details = []

    for af_ts in af_events:
        # Workout-Session aus training view (jede Source: apple/polar/garmin)
        r = conn.execute("""
            SELECT sport, ts_end, source_app,
                   ROUND((JULIANDAY(?) - JULIANDAY(substr(ts_end,1,19)))*1440) min_nach
            FROM training
            WHERE ts_end <= ? AND ts_end >= datetime(?, '-3 hours') AND person=?
            ORDER BY ts_end DESC LIMIT 1
        """, (af_ts, af_ts, af_ts, person)).fetchone()
        if r:
            n_post_exertional += 1
            post_details.append(f"{af_ts} ({int(r[3])}min nach {r[0]} [{r[2]}])")

    n_total = len(af_events)
    sev = "critical" if n_post_exertional >= 2 else "warning" if n_post_exertional >= 1 else "info"

    results.append((af_events[0][:10], af_events[-1][:10],
                    "arrhythmia", "af_total",
                    float(n_total), "events", None,
                    f"{n_post_exertional} post-exertionell",
                    sev,
                    f"Atrial fibrillation (EKG Apple Watch): {n_total} Episodes gesamt, "
                    f"{n_post_exertional} post-exertionell (innerhalb 3h nach Workout). "
                    + (f"Details: {'; '.join(post_details)}" if post_details else ""),
                    "ecg_csv"))

    return results


# ── 8. ANS-Gesamtstatus ───────────────────────────────────────────────────────
def compute_ans_status(conn: sqlite3.Connection, person: str) -> list:
    """Kombinierter autonomer Nervensystem Index aus health_canonical / Fallback measurements."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    # Aktuelle HRV (letzte 90 days)
    if "health_canonical" in tables:
        hrv_current = conn.execute("""
            SELECT ROUND(AVG(value),1) FROM health_canonical
            WHERE metric IN ('hrv_rmssd','hrv_sdnn') AND date >= date('now','-90 days')
              AND person=?
        """, (person,)).fetchone()[0]
        hrv_src_row = conn.execute("""
            SELECT source FROM health_canonical
            WHERE metric IN ('hrv_rmssd','hrv_sdnn') AND date >= date('now','-90 days')
              AND person=?
            ORDER BY date DESC LIMIT 1
        """, (person,)).fetchone()
        hrv_src = hrv_src_row[0] if hrv_src_row else None
    else:
        # Fallback: polar_nightly_hrv + measurements (hrv_sdnn from Apple)
        hrv_polar = conn.execute("""
            SELECT ROUND(AVG(rmssd_ms),1) FROM polar_nightly_hrv
            WHERE rmssd_ms > 0 AND date >= date('now','-90 days') AND person=?
        """, (person,)).fetchone()[0]
        hrv_meas = conn.execute("""
            SELECT ROUND(AVG(value),1) FROM measurements
            WHERE metric IN ('hrv_rmssd','hrv_sdnn') AND value > 0
              AND date >= date('now','-90 days') AND person=?
        """, (person,)).fetchone()[0]
        hrv_current = hrv_polar or hrv_meas
        hrv_src = "polar_nightly_hrv" if hrv_polar else "measurements"

    # Resting heart rate (letzte 90 days)
    rhr_current = conn.execute("""
        SELECT ROUND(AVG(value),1) FROM measurements
        WHERE metric IN ('resting_heart_rate','readiness_hr_resting','resting_hr')
          AND value > 0 AND date >= date('now','-90 days') AND person=?
    """, (person,)).fetchone()[0]
    if not rhr_current:
        rhr_current = conn.execute("""
            SELECT ROUND(AVG(resting_hr),1) FROM daily_stress
            WHERE resting_hr IS NOT NULL AND date >= date('now','-90 days') AND person=?
        """, (person,)).fetchone()[0]

    # Baseline HRV
    hrv_baseline = None
    if HRV_BASELINE_FROM and HRV_BASELINE_TO:
        if "health_canonical" in tables:
            hrv_baseline = conn.execute("""
                SELECT ROUND(AVG(value),1) FROM health_canonical
                WHERE metric='hrv_rmssd' AND date BETWEEN ? AND ? AND person=?
            """, (HRV_BASELINE_FROM, HRV_BASELINE_TO, person)).fetchone()[0]
        else:
            hrv_baseline = conn.execute("""
                SELECT ROUND(AVG(rmssd_ms),1) FROM polar_nightly_hrv
                WHERE rmssd_ms > 0 AND date BETWEEN ? AND ? AND person=?
            """, (HRV_BASELINE_FROM, HRV_BASELINE_TO, person)).fetchone()[0]

    today = date.today().isoformat()
    parts = []
    severity = "info"

    if hrv_baseline and hrv_current:
        src_label = f" [{hrv_src}]" if hrv_src else ""
        drop = round((hrv_baseline - hrv_current) / hrv_baseline * 100, 1) if hrv_baseline > 0 else 0
        parts.append(f"HRV: {hrv_current}ms{src_label} (Baseline {hrv_baseline}ms, -{drop}%)")
        if drop > 50:
            severity = "critical"
        elif drop > 30:
            severity = "warning"

    if rhr_current:
        parts.append(f"RHR: {rhr_current} bpm")
        if rhr_current > 90:
            severity = max(severity, "warning",
                          key=["normal","info","warning","critical"].index)

    if not parts:
        return []

    return [(today, None, "ans", "ans_current_status",
             None, None, None, None, severity,
             "ANS-Gesamtstatus (letzte 90 days): " + " | ".join(parts),
             "polar_nightly_hrv+measurements+daily_stress")]


# ── Summary ───────────────────────────────────────────────────────────
def print_summary(conn: sqlite3.Connection) -> None:
    print(t("\n── Klinische Befunde ──────────────────────────────────────────────", "\n── Clinical findings ──────────────────────────────────────────────"))
    for cat, ft, d, val, unit, status, sev, desc in conn.execute("""
        SELECT category, finding_type, finding_date,
               value, unit, status, severity, description
        FROM clinical_findings
        ORDER BY
            CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1
                          WHEN 'info'     THEN 2 ELSE 3 END,
            category, finding_date
    """):
        marker = {"critical": "⚠️ CRITICAL",
                  "warning":  "⚡ WARNUNG ",
                  "info":     "ℹ  INFO    ",
                  "normal":   "✅ NORMAL  "}.get(sev, sev)
        val_str = f" [{val} {unit}]" if val is not None and unit else ""
        print(f"  {marker}  {cat:<12} {ft:<28}{val_str}")
        print(f"    {desc[:120]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=t("Klinische Kriterien berechnen", "Compute clinical criteria"))
    parser.add_argument("--summary", action="store_true",
                        help="Only Resultse anzeigen")
    parser.add_argument("--person", default=None)
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = args.person or OWN_PERSON_ID

    conn = open_db()

    if args.summary:
        print_summary(conn)
        conn.close()
        return

    setup_tables(conn)

    checks = [
        ("POTS-Kriterium",              compute_oi_criterion),
        ("HRV Change-Points",           compute_hrv_changepoints),
        ("PEM / Post-exertionell HRV",  compute_pem_hrv),
        ("HR-Recovery",                 compute_hr_recovery),
        ("Sleepqualitäts-Trend",       compute_sleep_trend),
        ("Nächtliche SpO2-Load",   compute_spo2_burden),
        ("Post-exertionelles AF",       compute_af_pattern),
        ("ANS-Gesamtstatus",            compute_ans_status),
    ]

    total = 0
    for name, fn in checks:
        print(f"  {name} ...", flush=True)
        rows = fn(conn, person)
        n = insert(conn, rows, person)
        total += n
        print(t(f"    → {n} Befunde", f"    → {n} findings"))

    # Atomisch tauschen: bei Fehler bleibt clinical_findings unangetastet
    conn.executescript("""
    BEGIN;
    DROP TABLE IF EXISTS clinical_findings;
    ALTER TABLE clinical_findings_new RENAME TO clinical_findings;
    COMMIT;
    """)

    print(t(f"\n{total} klinische Befunde gespeichert.", f"\n{total} clinical findings saved."))
    print_summary(conn)
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))
    conn.close()


if __name__ == "__main__":
    main()
