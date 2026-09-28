#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Detrended Fluctuation Analysis (DFA) on ppi_raw (Polar H10 / ECG Logger).

@tier        research
@purpose.de  Berechnet DFA alpha1/alpha2 je 5-Minuten-Fenster als Marker für
             Vorhofflimmern und autonome Regulation aus Beat-to-beat-Intervallen.
@purpose.en  Computes DFA alpha1/alpha2 per 5-minute window as a marker of atrial
             fibrillation and autonomic regulation from beat-to-beat intervals.
@method.de   alpha1 über Skalen 4-16 (Kubios-Standard), alpha2 über 16-64.
             alpha2 bleibt NULL bei < 256 Schlägen im Fenster.
@method.en   alpha1 over scales 4-16 (Kubios standard), alpha2 over 16-64.
             alpha2 stays NULL for windows with < 256 beats.
@thresholds
    Ruhe (is_training=0):
    alpha1 < 0.75 :: de=[research] AFib-Indikator / Verlust fraktalen Gedächtnisses — mechanistisch begründet (Ho 1997); kein prospektiver Diagnostiktest mit Sensitivität/Spezifität; im AFES-Kontext mit weiteren Signalen kombinieren :: en=[research] AFib indicator / loss of fractal memory — mechanistic rationale (Ho 1997); no prospective diagnostic study with sensitivity/specificity; combine with additional AFES signals
    alpha1 < 0.85 :: de=[research] Mortalitätsprädiktor; validiert für post-AMI mit EF<35% (Mäkikallio 1999); für andere Nutzerprofile als Orientierungswert verwenden, klinische Einordnung nutzerabhängig :: en=[research] mortality predictor; validated for post-AMI with EF<35% (Mäkikallio 1999); use as reference value for other user profiles, clinical interpretation depends on individual context
    alpha1 ~ 1.0  :: de=normaler Sinusrhythmus (1/f-Rauschen) :: en=normal sinus rhythm (1/f noise)
    alpha1 > 1.2  :: de=pathologische Starrheit (z. B. schwere Herzinsuffizienz) :: en=pathological rigidity (e.g. severe heart failure)
    Training (is_training=1):
    alpha1 < 0.75 :: de=[validated] HRVT1 – aerobe Schwelle überschritten; validiert gegen Laktat-Referenz in Gesunden, Sportlern und kardialen Populationen (Rogers & Gronwald 2022); bei autonomer Dysregulation oder Erkrankungen mit veränderter HRV-Dynamik als Näherung verwenden :: en=[validated] HRVT1 – aerobic threshold exceeded; validated against lactate reference in healthy, athletic and cardiac populations (Rogers & Gronwald 2022); use as approximation in autonomic dysfunction or conditions with altered HRV dynamics
    alpha1 < 0.50 :: de=[validated] HRVT2 – anaerobe Schwelle überschritten; validiert gegen VT2/MLSS in Sportstudien (Sempere-Ruiz 2024); Übertragbarkeit auf klinische Populationen nutzerabhängig prüfen :: en=[validated] HRVT2 – anaerobic threshold exceeded; validated against VT2/MLSS in exercise studies (Sempere-Ruiz 2024); applicability to clinical populations depends on individual context
@reads       ppi_raw
@writes      ppi_dfa: window_start TEXT, person TEXT, device TEXT, n_beats INT,
             alpha1 REAL, alpha2 REAL, is_training INT, mean_hr_bpm REAL, computed_at TEXT
             measurements: dfa_alpha1_rest_{avg,min,pct_low,pct_risk},
             dfa_alpha1_train_{avg,min,pct_at,pct_hrvt2}, dfa_hrvt1, dfa_hrvt2
@refs        Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. Chaos: An Interdisciplinary Journal of Nonlinear Science, 5(1):82-87. doi:10.1063/1.166141
             Ho KKL, Moody GB, Peng CK et al. (1997). Predicting Survival in Heart Failure Case and Control Subjects by Use of Fully Automated Methods for Deriving Nonlinear and Conventional Indices of Heart Rate Dynamics. Circulation, 96(3):842-848. doi:10.1161/01.CIR.96.3.842
             Mäkikallio TH, Høiber S, Køber L et al. (1999). Fractal analysis of heart rate dynamics as a predictor of mortality in patients with depressed left ventricular function after acute myocardial infarction. The American Journal of Cardiology, 83(6):836-839. doi:10.1016/s0002-9149(98)01076-5
             Gronwald T, Hoos O (2019). Correlation properties of heart rate variability during endurance exercise: A systematic review. Annals of Noninvasive Electrocardiology, 25(1). doi:10.1111/anec.12697
             Rogers B, Gronwald T (2022). Fractal Correlation Properties of Heart Rate Variability as a Biomarker for Intensity Distribution and Training Prescription in Endurance Exercise: An Update. Frontiers in Physiology, 13. doi:10.3389/fphys.2022.879071
             Sempere-Ruiz N, Sarabia JM, Baladzhaeva S, Moya-Ramón M (2024). Reliability and validity of a non-linear index of heart rate variability to determine intensity thresholds. Frontiers in Physiology, 15. doi:10.3389/fphys.2024.1329360

@relevance.de  Ermöglicht die Analyse von Puls-Puls-Intervall-Daten, essentiell für die HRV-Analyse
@relevance.en  Enables pulse-pulse interval data analysis, essential for HRV analysis
@limits.de   DFA mit Skalen 4-16 zeigt bei unkorrelierten Zeitreihen systematisch alpha1 ≈ 0.58
             statt theoretisch 0.50 (bekannter Finite-Scale-Bias; gilt auch für Kubios). Da die
             publizierten Schwellenwerte mit denselben Skalen ermittelt wurden, ist der Bias in
             den Thresholds absorbiert — Absolutwerte nur intra-individuell vergleichen.
             Nur echte Beat-to-beat-Daten (ppi_raw); optische HR-Sensoren ungeeignet.
             Bekanntes leeres Ergebnis: Ein 5-Min-Fenster braucht _MIN_BEATS (100)
             kontiguierliche Schläge (Lücke <= _GAP_S). In dieser DB stammt ppi_raw
             überwiegend aus kurzen, EKG-Session-gekoppelten Erfassungen (Sekunden bis
             wenige zehn Sekunden je Aufnahme), nicht aus kontinuierlichem
             Brustgurt-Streaming — die längste zusammenhängende Schlagfolge bleibt unter
             _MIN_BEATS. Für solche Zeiträume bleibt ppi_dfa korrekterweise leer; das ist
             kein Bug im Skript, sondern fehlende Eingangsdatengrundlage (siehe
             pipeline-architecture: "Silent empty results as known behavior" — dieses
             Skript meldet die Fensteranzahl explizit im Log, statt stillschweigend
             durchzulaufen). Abhilfe nur durch tatsächliches kontinuierliches
             Brustgurt-/EKG-Logger-Tragen, nicht durch künstliches Befüllen der Tabelle.
             Trainings-Fenster werden markiert (is_training=1) und von AFES ignoriert.
             HRVT1/HRVT2 (alpha1=0.75/0.50) prospektiv validiert gegen Laktat/VT2 in Gesunden,
             Sportlern und kardialen Populationen (Rogers 2022, Sempere-Ruiz 2024). Bei autonomer
             Dysregulation ist alpha1 in Ruhe bereits erniedrigt, was HRVT in Ruhe-HR-Nähe
             zieht — kein valider AT-Wert in diesem Fall (Dysautonomie-Margin-Check in compute_pem.py).
             alpha1 < 0.85 (Mäkikallio 1999): prospektive Validierung für post-AMI mit EF<35%;
             für andere Nutzerprofile als Orientierungswert nutzbar, klinische Einordnung
             erfordert individuellen Kontext.
             alpha1 < 0.75 in Ruhe als AFib-Indikator: mechanistisch begründet, kein prospektiver
             Diagnostiktest mit publizierter Sensitivität/Spezifität — im AFES-Kontext mit
             weiteren Signalen kombinieren.

             Unterschied zu ppi_hrv_advanced.dfa_alpha1 (compute_hrv_advanced.py):
             ppi_dfa verwendet roh-RR (keine Artefaktkorrektur) — dadurch bleibt die
             RR-Irregularität erhalten, die bei AFib und als HRVT-Signal diagnostisch
             entscheidend ist. Weitere Unterschiede:
               Gap-Schwelle: 3 s (hier) vs. 60 s (hrv_advanced) — striktere Segment-
               trennung; Fenstergrenzen können daher abweichen.
               Device-Prio: MIN(device) lexikografisch bei parallelen Quellen
               (polar_h10 > polar_h7 > polar_ignite2 > polar_v3).
               Zusatzfelder: is_training-Flag, alpha2 (≥256 Beats), daily aggregates
               in measurements — nicht in ppi_hrv_advanced.

             Wann welche Quelle verwenden:
               ppi_dfa.alpha1 → akute kardiale Marker: AFES (Vorhofflimmern-Score),
               HRVT1/HRVT2, analyse_dfa_alpha1. Roh-RR ist hier korrekt.
               ppi_hrv_advanced.dfa_alpha1 → Verlaufs- und Trendanalyse: ME/CFS-
               Trajektorie, Postinfektionssyndrome, Changepoint-Detektion,
               Multisource-Reports. Artefaktkorrektur stabilisiert Tagesmittelwerte.
@limits.en   DFA with scales 4-16 systematically yields alpha1 ≈ 0.58 for uncorrelated series
             instead of the theoretical 0.50 (known finite-scale bias; same in Kubios). Since
             published thresholds were derived with identical scales, the bias is absorbed into
             the threshold values — absolute alpha1 values should only be compared intra-individually.
             Real beat-to-beat data only (ppi_raw); optical HR sensors unsuitable.
             Known empty result: a 5-minute window needs _MIN_BEATS (100) contiguous
             beats (gap <= _GAP_S). In this DB, ppi_raw mostly comes from short,
             ECG-session-linked captures (seconds to a few tens of seconds per
             recording), not continuous chest-strap streaming — the longest contiguous
             beat run stays below _MIN_BEATS. For such periods ppi_dfa correctly stays
             empty; this is not a script bug but missing input data (see
             pipeline-architecture: "Silent empty results as known behavior" — this
             script explicitly logs the window count instead of running silently).
             Remedy only via actually wearing a continuous chest strap/ECG logger, not
             by artificially populating the table.
             Training windows are flagged (is_training=1) and ignored by AFES.
             HRVT1/HRVT2 (alpha1=0.75/0.50) prospectively validated against lactate/VT2 in healthy,
             athletic and cardiac populations (Rogers 2022, Sempere-Ruiz 2024). In autonomic
             dysfunction alpha1 is already reduced at rest, pulling HRVT close to resting HR —
             not a valid AT in this case (dysautonomia margin check in compute_pem.py).
             alpha1 < 0.85 (Mäkikallio 1999): prospective validation for post-AMI with EF<35%;
             usable as reference value for other user profiles; clinical interpretation requires
             individual context.
             alpha1 < 0.75 at rest as AFib indicator: mechanistically sound, no prospective
             diagnostic study with published sensitivity/specificity — combine with additional
             AFES signals for context.

             Difference from ppi_hrv_advanced.dfa_alpha1 (compute_hrv_advanced.py):
             ppi_dfa uses raw RR (no artefact correction) — preserving the RR irregularity
             that is diagnostically critical for AFib detection and HRVT signalling.
             Further differences:
               Gap threshold: 3 s (here) vs. 60 s (hrv_advanced) — stricter segment
               separation; window boundaries may therefore differ.
               Device priority: MIN(device) lexicographically for parallel sources
               (polar_h10 > polar_h7 > polar_ignite2 > polar_v3).
               Extra fields: is_training flag, alpha2 (≥256 beats), daily aggregates
               in measurements — absent from ppi_hrv_advanced.

             When to use which source:
               ppi_dfa.alpha1 → acute cardiac markers: AFES (atrial fibrillation
               score), HRVT1/HRVT2, analyse_dfa_alpha1. Raw RR is correct here.
               ppi_hrv_advanced.dfa_alpha1 → longitudinal trend analysis: ME/CFS
               trajectory, post-infectious syndromes, changepoint detection,
               multisource reports. Artefact correction stabilises daily means.
@usage
    python compute_ppi_dfa.py                            # recompute all
    python compute_ppi_dfa.py --update                   # from last entry
    python compute_ppi_dfa.py --recompute                # overwrite existing
    python compute_ppi_dfa.py --from 2026-05-01 --to 2026-06-03
"""

import argparse
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_here = Path(__file__).parent.parent
sys.path.insert(0, str(_here))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg    = _Cfg()
DB_PATH = _cfg.db_path

# ── DFA-Parameter ──────────────────────────────────────────────────────────────
_WINDOW_S    = 300        # 5 Minuten pro Fenster
_GAP_S       = 3.0        # Lücke > 3 s → neues Segment
_MIN_BEATS   = 100        # Mindestschläge pro Fenster für alpha1
_MIN_BEATS_2 = 256        # Mindestschläge für alpha2

_SCALES_SHORT = (4, 5, 6, 7, 8, 9, 10, 12, 14, 16)    # alpha1
_SCALES_LONG  = (16, 20, 24, 32, 40, 48, 56, 64)        # alpha2
_MIN_BOXES    = 4          # Mindestboxen pro Skala


# ── Schema ─────────────────────────────────────────────────────────────────────

def setup_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ppi_dfa (
            window_start TEXT NOT NULL,
            person       TEXT NOT NULL DEFAULT 'unknown',
            device       TEXT,
            n_beats      INTEGER,
            alpha1       REAL,
            alpha2       REAL,
            is_training  INTEGER DEFAULT 0,
            mean_hr_bpm  REAL,
            computed_at  TEXT,
            PRIMARY KEY (window_start, person)
        )
    """)
    existing = {r[1] for r in conn.execute("PRAGMA table_info(ppi_dfa)")}
    if "mean_hr_bpm" not in existing:
        conn.execute("ALTER TABLE ppi_dfa ADD COLUMN mean_hr_bpm REAL")
    conn.commit()


# ── DFA-Algorithmus ────────────────────────────────────────────────────────────

def _dfa_exponent(rr: list[float], scales: tuple, min_boxes: int) -> float | None:
    """
    DFA-Skalierungsexponent für eine gegebene Skalenmenge.

    Methode:
      1. Demean + kumulative Summe (Integration der RR-Zeitreihe)
      2. Für jede Skala n: nicht-überlappende Boxen → lineares Detrending →
         RMS der Residuen F(n)
      3. Lineare Regression log(n) vs log(F(n)) → Steigung = alpha

    Reine Python-Implementierung (kein numpy), O(N * |scales|) pro Fenster.
    """
    N = len(rr)
    if N < min(scales) * min_boxes:
        return None

    # Integrierte Zeitreihe (demeaned cumulative sum)
    mean_rr = sum(rr) / N
    y: list[float] = []
    s = 0.0
    for x in rr:
        s += x - mean_rr
        y.append(s)

    log_n_vals: list[float] = []
    log_F_vals: list[float] = []

    for n in scales:
        n_boxes = N // n
        if n_boxes < min_boxes:
            continue

        # Vorberechnete Konstanten für lineares Detrending
        x_bar    = (n - 1) / 2.0
        # sum((i - x_bar)^2) für i in 0..n-1 = n*(n^2-1)/12
        sum_xx_c = n * (n * n - 1) / 12.0

        sum_sq = 0.0
        count  = 0

        for box in range(n_boxes):
            seg = y[box * n: box * n + n]
            y_bar   = sum(seg) / n
            sum_xy_c = sum((i - x_bar) * (v - y_bar) for i, v in enumerate(seg))
            a = sum_xy_c / sum_xx_c if sum_xx_c > 0 else 0.0
            b = y_bar - a * x_bar
            for i, v in enumerate(seg):
                r = v - (a * i + b)
                sum_sq += r * r
                count  += 1

        if count == 0:
            continue
        F_n = math.sqrt(sum_sq / count)
        if F_n > 0:
            log_n_vals.append(math.log(n))
            log_F_vals.append(math.log(F_n))

    if len(log_n_vals) < 4:
        return None

    m   = len(log_n_vals)
    mx  = sum(log_n_vals) / m
    my  = sum(log_F_vals) / m
    num = sum((x - mx) * (f - my) for x, f in zip(log_n_vals, log_F_vals))
    den = sum((x - mx) ** 2 for x in log_n_vals)
    return num / den if den > 0 else None


def dfa_alpha(rr: list[float]) -> tuple[float | None, float | None]:
    """Gibt (alpha1, alpha2) zurück. alpha2 ist None wenn < 256 Schläge."""
    alpha1 = _dfa_exponent(rr, _SCALES_SHORT, _MIN_BOXES)
    alpha2 = _dfa_exponent(rr, _SCALES_LONG,  _MIN_BOXES) if len(rr) >= _MIN_BEATS_2 else None
    return alpha1, alpha2


# ── Timestamp-Parsing ──────────────────────────────────────────────────────────

def _parse_utc(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ── Trainings-Sessions laden ────────────────────────────────────────────────────

def _load_training_sessions(conn, person: str, d0: str, d1: str) -> dict:
    """date → [(ts_start_utc, ts_end_utc)]  für alle Trainings-Sessions."""
    sessions: dict[str, list] = defaultdict(list)
    d0_buf = (datetime.strptime(d0, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    d1_buf = (datetime.strptime(d1, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    for ts_s, ts_e, sess_date in conn.execute("""
        SELECT ts_start, ts_end, date
        FROM sessions
        WHERE person=? AND type='training'
          AND ts_start IS NOT NULL AND ts_end IS NOT NULL
          AND date BETWEEN ? AND ?
    """, (person, d0_buf, d1_buf)):
        ts_start = _parse_utc(ts_s)
        ts_end   = _parse_utc(ts_e)
        if ts_start and ts_end:
            # 90-Min-Puffer vor Session-Start: H7 wird oft vor dem offiziellen
            # Workout-Beginn angelegt — diese Fenster sind trotzdem Belastung.
            sessions[sess_date].append((ts_start - timedelta(minutes=90), ts_end))

    return sessions


def _is_training(window_start: datetime, window_end: datetime,
                 sessions: dict, date_str: str) -> bool:
    """True wenn das Fenster eine Trainings-Session überlappt."""
    day_sessions = sessions.get(date_str, [])
    for ts_s, ts_e in day_sessions:
        if window_start < ts_e and window_end > ts_s:
            return True
    return False


# ── Fenster-Verarbeitung ───────────────────────────────────────────────────────

def _iter_windows(beats: list[tuple[datetime, int, str]]):
    """Generator: teilt eine kontiguierliche Beat-Liste in 5-Min-Fenster auf.
    Yields: (window_start_utc, rr_list, device)
    """
    if not beats:
        return

    ws    = beats[0][0]       # window start
    rr    = []
    dev   = beats[0][2]
    last  = beats[0][0]

    for ts, rr_ms, device in beats:
        gap = (ts - last).total_seconds()
        elapsed = (ts - ws).total_seconds()

        if gap > _GAP_S:
            # Lücke → aktuelles Fenster abschließen, neues starten
            if len(rr) >= _MIN_BEATS:
                yield ws, rr, dev
            ws, rr, dev, last = ts, [], device, ts

        if elapsed >= _WINDOW_S:
            # Fenster voll → ausgeben
            if len(rr) >= _MIN_BEATS:
                yield ws, rr, dev
            ws  = ts
            rr  = []
            dev = device

        rr.append(rr_ms)
        last = ts

    if len(rr) >= _MIN_BEATS:
        yield ws, rr, dev


# ── Haupt-Berechnung ───────────────────────────────────────────────────────────

def compute_dfa(conn, person: str, d0: str, d1: str) -> int:
    """Berechnet DFA-Fenster für person im Bereich d0..d1.
    Gibt Anzahl neuer Einträge zurück.
    """
    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Trainings-Sessions vorab laden (für is_training-Flag)
    training = _load_training_sessions(conn, person, d0, d1)

    # ppi_raw streamen — dedupliziert nach (datetime, pulse_ms):
    # Wenn H10 und Watch dieselben Beats gleichzeitig speichern, gewinnt
    # MIN(device) lexikografisch: polar_h10 < polar_h7 < polar_ignite2 < polar_loop < polar_v3
    cur = conn.execute("""
        SELECT "datetime", pulse_ms, MIN(device) AS device
        FROM ppi_raw
        WHERE person=? AND substr("datetime", 1, 10) BETWEEN ? AND ?
          AND pulse_ms BETWEEN 300 AND 2000
        GROUP BY "datetime", pulse_ms
        ORDER BY "datetime"
    """, (person, d0, d1))

    # Segmentierung und Fenster-Bildung
    segment: list[tuple[datetime, int, str]] = []
    last_ts: datetime | None = None
    rows_written = 0
    batch: list[tuple] = []

    def flush_segment():
        nonlocal rows_written
        for ws, rr_list, device in _iter_windows(segment):
            a1, a2 = dfa_alpha(rr_list)
            ws_str      = ws.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            date_s      = ws.strftime("%Y-%m-%d")
            we          = ws + timedelta(seconds=_WINDOW_S)
            is_tr       = 1 if _is_training(ws, we, training, date_s) else 0
            mean_hr_bpm = round(60000.0 / (sum(rr_list) / len(rr_list)), 1)
            batch.append((ws_str, person, device, len(rr_list),
                          round(a1, 4) if a1 is not None else None,
                          round(a2, 4) if a2 is not None else None,
                          is_tr, mean_hr_bpm, computed_at))
            rows_written += 1

            if len(batch) >= 500:
                _write_batch(conn, batch)
                batch.clear()

    while True:
        chunk = cur.fetchmany(50_000)
        if not chunk:
            break

        for ts_raw, rr_ms, device in chunk:
            ts = _parse_utc(ts_raw)
            if ts is None:
                continue

            if last_ts is not None and (ts - last_ts).total_seconds() > _GAP_S:
                flush_segment()
                segment.clear()

            segment.append((ts, int(rr_ms), device))
            last_ts = ts

    flush_segment()

    if batch:
        _write_batch(conn, batch)

    return rows_written


def _write_batch(conn, batch: list[tuple]):
    conn.executemany("""
        INSERT OR IGNORE INTO ppi_dfa
        (window_start, person, device, n_beats, alpha1, alpha2, is_training, mean_hr_bpm, computed_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, batch)
    conn.commit()


def _derive_hrvt(conn, person: str, date_str: str) -> tuple[float | None, float | None]:
    """
    HRVT1 (DFA alpha1=0.75) und HRVT2 (alpha1=0.50) aus Trainingsfenstern eines Tages.

    Methode: HR in 5-bpm-Bins gruppieren, Median-alpha1 pro Bin, linearer Crossing-Point.
    Benötigt >= 6 Fenster mit mean_hr_bpm; gibt (None, None) zurück wenn zu wenig Daten.

    Nur anwendbar auf aerobe Dauerbelastung mit kontinuierlich steigender HR.
    Ausgeschlossen: Krafttraining, Pilates, Tanzen, Turnen (nicht-monotone HR-Kurven).
    Sessions werden per EXISTS aus sessions-Tabelle gefiltert; Mehrfachquellen
    (Garmin + Polar + Apple Watch) durch DISTINCT date(window_start) dedupliziert.

    Validierung: Rogers & Gronwald 2022, doi:10.3389/fphys.2022.879071
    Nicht in ME/CFS-Populationen validiert — als Näherung verwenden.
    """
    # Aerobe Sportarten: kontinuierliche Belastung mit progredientem HR-Anstieg.
    # Polar "Outdoorsport" = typisch eBike/Wandern; ebenfalls auswertbar.
    _AEROBIC_SPORTS = (
        'Radfahren', 'cycling', 'Cycling', 'Outdoorsport',
        'Laufen', 'Wandern', 'Hiking', 'Crosstrainer',
        'Aerobics', 'SUP', 'Skifahren', 'Schwimmen',
        'running', 'swimming', 'walking', 'Walking',
    )
    placeholders = ','.join('?' for _ in _AEROBIC_SPORTS)

    rows = conn.execute(f"""
        SELECT mean_hr_bpm, alpha1 FROM ppi_dfa
        WHERE person=? AND date(window_start)=? AND is_training=1
          AND alpha1 IS NOT NULL AND mean_hr_bpm IS NOT NULL
          AND mean_hr_bpm BETWEEN 40 AND 220
          AND EXISTS (
              SELECT 1 FROM sessions s
              WHERE s.person=ppi_dfa.person
                AND s.date=date(ppi_dfa.window_start)
                AND s.type='training'
                AND s.sport IN ({placeholders})
          )
    """, (person, date_str, *_AEROBIC_SPORTS)).fetchall()

    if len(rows) < 6:
        return None, None

    bins: dict[int, list[float]] = {}
    for hr, a1 in rows:
        bins.setdefault(round(hr / 5) * 5, []).append(a1)

    smoothed = sorted(
        [(hr, statistics.median(vals)) for hr, vals in bins.items()],
        key=lambda x: x[0]
    )
    if len(smoothed) < 4:
        return None, None

    def _cross(points: list, threshold: float) -> float | None:
        for i in range(len(points) - 1):
            hr1, a1 = points[i]
            hr2, a2 = points[i + 1]
            if a1 >= threshold > a2:
                frac = (threshold - a1) / (a2 - a1)
                return round(hr1 + frac * (hr2 - hr1), 1)
        return None

    return _cross(smoothed, 0.75), _cross(smoothed, 0.50)


def _write_daily_metrics(conn, person: str, d0: str, d1: str) -> tuple[int, int]:
    """Tägliche DFA-Aggregate (Ruhe + Training) in measurements schreiben.

    Ruhe-Metriken (is_training=0):
      dfa_alpha1_rest_avg      — mittleres alpha1 in Ruhe
      dfa_alpha1_rest_min      — minimales alpha1 (schlechtestes Fenster des Tages)
      dfa_alpha1_rest_pct_low  — Anteil Fenster alpha1 < 0.75 (AFib-Indikator)
      dfa_alpha1_rest_pct_risk — Anteil Fenster alpha1 < 0.85 (Mäkikallio-Bereich)

    Training-Metriken (is_training=1):
      dfa_alpha1_train_avg       — mittleres alpha1 während Training
      dfa_alpha1_train_min       — minimales alpha1 (AT-Nadir)
      dfa_alpha1_train_pct_at    — Anteil Fenster alpha1 < 0.75 (HRVT1 überschritten)
      dfa_alpha1_train_pct_hrvt2 — Anteil Fenster alpha1 < 0.50 (HRVT2 überschritten)
      dfa_hrvt1                  — HR bei DFA alpha1=0.75 (aerobe Schwelle; bpm)
      dfa_hrvt2                  — HR bei DFA alpha1=0.50 (anaerobe Schwelle; bpm)

    Voraussetzung: ppi_dfa muss für den Zeitraum bereits berechnet sein.
    Idempotent via INSERT OR IGNORE.
    Gibt (n_rest_days, n_train_days) zurück.
    """
    batch = []

    rest_rows = conn.execute("""
        SELECT date(window_start),
               AVG(alpha1), MIN(alpha1),
               ROUND(100.0 * SUM(CASE WHEN alpha1 < 0.75 THEN 1 ELSE 0 END)
                     / COUNT(*), 1),
               ROUND(100.0 * SUM(CASE WHEN alpha1 < 0.85 THEN 1 ELSE 0 END)
                     / COUNT(*), 1),
               MIN(device)
        FROM ppi_dfa
        WHERE person=? AND date(window_start) BETWEEN ? AND ?
          AND is_training=0 AND n_beats >= 100 AND alpha1 IS NOT NULL
        GROUP BY date(window_start)
    """, (person, d0, d1)).fetchall()

    for d, avg_a1, min_a1, pct_low, pct_risk, dev in rest_rows:
        if avg_a1 is None:
            continue
        ts = f"{d}T00:00:00+00:00"
        batch.extend([
            (ts, d, "dfa_alpha1_rest_avg",      round(avg_a1, 4), dev, person),
            (ts, d, "dfa_alpha1_rest_min",      round(min_a1, 4), dev, person),
            (ts, d, "dfa_alpha1_rest_pct_low",  pct_low  or 0.0,  dev, person),
            (ts, d, "dfa_alpha1_rest_pct_risk", pct_risk or 0.0,  dev, person),
        ])

    train_rows = conn.execute("""
        SELECT date(window_start),
               AVG(alpha1), MIN(alpha1),
               ROUND(100.0 * SUM(CASE WHEN alpha1 < 0.75 THEN 1 ELSE 0 END)
                     / COUNT(*), 1),
               ROUND(100.0 * SUM(CASE WHEN alpha1 < 0.50 THEN 1 ELSE 0 END)
                     / COUNT(*), 1),
               MIN(device)
        FROM ppi_dfa
        WHERE person=? AND date(window_start) BETWEEN ? AND ?
          AND is_training=1 AND n_beats >= 100 AND alpha1 IS NOT NULL
        GROUP BY date(window_start)
    """, (person, d0, d1)).fetchall()

    for d, avg_a1, min_a1, pct_at, pct_hrvt2, dev in train_rows:
        if avg_a1 is None:
            continue
        ts = f"{d}T00:00:00+00:00"
        batch.extend([
            (ts, d, "dfa_alpha1_train_avg",       round(avg_a1, 4), dev, person),
            (ts, d, "dfa_alpha1_train_min",       round(min_a1, 4), dev, person),
            (ts, d, "dfa_alpha1_train_pct_at",    pct_at    or 0.0, dev, person),
            (ts, d, "dfa_alpha1_train_pct_hrvt2", pct_hrvt2 or 0.0, dev, person),
        ])
        hrvt1, hrvt2 = _derive_hrvt(conn, person, d)
        if hrvt1 is not None:
            batch.append((ts, d, "dfa_hrvt1", hrvt1, dev, person))
        if hrvt2 is not None:
            batch.append((ts, d, "dfa_hrvt2", hrvt2, dev, person))

    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO measurements (ts, date, metric, value, device_id, person)
            VALUES (?, ?, ?, ?, ?, ?)
        """, batch)
        conn.commit()

    return len(rest_rows), len(train_rows)


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("DFA alpha1 auf ppi_raw berechnen", "Compute DFA alpha1 on ppi_raw"))
    parser.add_argument("--person",    default=OWN_PERSON_ID)
    parser.add_argument("--from",      dest="date_from", default=None)
    parser.add_argument("--to",        dest="date_to",   default=None)
    parser.add_argument("--update",    action="store_true",
                        help=t("Nur neue Tage", "Append new days only"))
    parser.add_argument("--recompute", action="store_true",
                        help=t("Vorhandene Einträge überschreiben", "Overwrite existing"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person
    conn   = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    setup_table(conn)

    d1 = args.date_to or date.today().isoformat()

    fallback_start = _cfg.data_start
    if not fallback_start:
        print(t("  Warnung: clinical.data_start nicht in Config — verarbeite alle Daten.",
                "  Warning: clinical.data_start not set in config — processing all data."))
        fallback_start = "1900-01-01"
    if args.update:
        last = conn.execute(
            "SELECT MAX(date(window_start)) FROM ppi_dfa WHERE person=?", (person,)
        ).fetchone()[0]
        d0 = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") \
             if last else fallback_start
    else:
        d0 = args.date_from or fallback_start

    if d0 > d1:
        print(t("Bereits aktuell.", "Already up to date."))
        conn.close()
        return

    if args.recompute:
        conn.execute(
            "DELETE FROM ppi_dfa WHERE person=? AND date(window_start) BETWEEN ? AND ?",
            (person, d0, d1)
        )
        conn.execute(
            """DELETE FROM measurements WHERE person=? AND date BETWEEN ? AND ?
               AND metric IN (
                   'dfa_alpha1_rest_avg','dfa_alpha1_rest_min',
                   'dfa_alpha1_rest_pct_low','dfa_alpha1_rest_pct_risk',
                   'dfa_alpha1_train_avg','dfa_alpha1_train_min',
                   'dfa_alpha1_train_pct_at','dfa_alpha1_train_pct_hrvt2',
                   'dfa_hrvt1','dfa_hrvt2'
               )""",
            (person, d0, d1)
        )
        conn.commit()

    print(t(f"Berechne DFA alpha1 für {person}: {d0} → {d1}",
            f"Computing DFA alpha1 for {person}: {d0} → {d1}"))
    print(t(f"  Fenstergröße: {_WINDOW_S}s | Lücken-Threshold: {_GAP_S}s | "
            f"Min. Schläge: {_MIN_BEATS}",
            f"  Window: {_WINDOW_S}s | Gap threshold: {_GAP_S}s | "
            f"Min beats: {_MIN_BEATS}"), flush=True)

    n = compute_dfa(conn, person, d0, d1)

    n_rest, n_train = _write_daily_metrics(conn, person, d0, d1)
    if n_rest or n_train:
        print(t(f"  DFA → measurements: Ruhe {n_rest} Tage | Training {n_train} Tage",
                f"  DFA → measurements: rest {n_rest} days | training {n_train} days"))

    # Statistik
    stats = conn.execute("""
        SELECT COUNT(*), SUM(is_training),
               ROUND(AVG(alpha1), 3), ROUND(MIN(alpha1), 3), ROUND(MAX(alpha1), 3),
               SUM(CASE WHEN alpha1 < 0.75 AND is_training=0 THEN 1 ELSE 0 END)
        FROM ppi_dfa
        WHERE person=? AND date(window_start) BETWEEN ? AND ?
    """, (person, d0, d1)).fetchone()

    print("\n── DFA-Ergebnis ─────────────────────────────────────────────────────")
    print(f"  Neue Fenster:       {n:>8,}")
    if stats[0]:
        print(f"  Gesamt (Periode):   {stats[0]:>8,}  davon Training: {stats[1] or 0:,}")
        print(f"  alpha1:  ø {stats[2]}  min {stats[3]}  max {stats[4]}")
        print(f"  Fenster alpha1<0.75 (Ruhe): {stats[5] or 0:,}  "
              f"({100*(stats[5] or 0)/max(stats[0]-(stats[1] or 0),1):.1f}%)")

    # Top-Tage nach Anteil alpha1<0.75
    print("\n── Tage mit höchstem AFib-DFA-Anteil ────────────────────────────────")
    for row in conn.execute("""
        SELECT date(window_start) as d,
               COUNT(*) as n_total,
               SUM(CASE WHEN alpha1 < 0.75 THEN 1 ELSE 0 END) as n_afib,
               ROUND(100.0*SUM(CASE WHEN alpha1<0.75 THEN 1 ELSE 0 END)/COUNT(*),1) as pct,
               ROUND(AVG(alpha1),3) as avg_a1
        FROM ppi_dfa
        WHERE person=? AND date(window_start) BETWEEN ? AND ?
          AND is_training=0 AND n_beats >= 100
        GROUP BY d HAVING n_total >= 30
        ORDER BY pct DESC, d DESC LIMIT 10
    """, (person, d0, d1)):
        print(f"  {row[0]}  n={row[1]:>3}  afib-Fenster={row[2]:>2}  "
              f"({row[3]:>5}%)  ø alpha1={row[4]}")

    conn.close()
    print(f"\n{t('Datenbank:', 'Database:')} {DB_PATH}")


if __name__ == "__main__":
    main()
