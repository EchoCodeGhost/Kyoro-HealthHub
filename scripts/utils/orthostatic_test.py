#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
orthostatic_test — Geführter Orthostase-Test (modifizierter Schellong-Test)

@tier        heuristic
@purpose.de  Führt einen geführten Orthostase-Test durch — oder wertet einen bereits
              anderweitig aufgezeichneten Test aus (--evaluate, z.B. eine manuell mit
              ECGLogger erfasste Sitzung, optional mit --auto-detect ohne manuelle
              Zeiteingabe) — und speichert die Ergebnisse in sessions/session_metrics
              (type='orthostatic', source_app='guided_test'), derselben Zielstruktur
              wie die echten Polar-Tests und die heuristische Kandidaten-Erkennung,
              damit analyse_orthostatic.py sie einheitlich sieht.
              Implementiert einen modifizierten Schellong-Test: 10 Minuten Liegen, 10 Minuten Stehen.
              Datenquellen: Primär ppi_raw (RR-Intervalle von H10/H7 für exakte RMSSD-Berechnung),
              Fallback: measurements mit metric='heart_rate' (HR-Werte, RMSSD näherungsweise).
              Zusätzlich, geräteagnostisch und optional (nur falls im Zeitfenster
              vorhanden): SpO2 aus measurements (z.B. Wellue O2Ring) und Blutdruck
              aus blood_pressure (z.B. Withings BPM Core) — jedes Gerät, das
              parallel zur H10-Aufzeichnung lief, fließt automatisch mit ein.
@purpose.en  Conducts a guided orthostatic test — or evaluates one already recorded
              elsewhere (--evaluate, e.g. a session manually captured via ECGLogger,
              optionally with --auto-detect to skip manual time entry) — and stores
              results in sessions/session_metrics (type='orthostatic',
              source_app='guided_test'), the same target structure as the real Polar
              tests and the heuristic candidate detector, so analyse_orthostatic.py
              sees all of them consistently.
              Implements a modified Schellong test: 10 minutes supine, 10 minutes standing.
              Data sources: Primary ppi_raw (RR intervals from H10/H7 for exact RMSSD calculation),
              fallback: measurements with metric='heart_rate' (HR values, RMSSD approximate).
              Additionally, device-agnostic and optional (only if present in the time
              window): SpO2 from measurements (e.g. Wellue O2Ring) and blood pressure
              from blood_pressure (e.g. Withings BPM Core) — any device that ran
              alongside the H10 recording is automatically included.
@method.de   Interaktiver Modus: Zeigt Anleitung mit ASCII-Art, führt durch die Testphasen mit
              Countdown-Timer. Bewertungsmodus (--evaluate): Manuelle Eingabe von Zeitfenstern —
              liest, wie der geführte Modus, aus bereits importierten ppi_raw/measurements-Daten,
              egal aus welchem Importer sie stammen (ECGLogger, HRV Logger, Polar, ...).
              Mit --evaluate --auto-detect: statt exakter Zeiten nur ein grobes
              Suchfenster nötig — der Aufsteh-Moment wird über dieselbe Sprung-
              Heuristik wie compute_orthostatic_detection.py gefunden (scharfer,
              anhaltender HF-Anstieg ≥HR_JUMP_MIN bpm, dieselbe Funktion importiert,
              nicht neu implementiert), Liegephase = REF_WINDOW_S davor, Stehphase
              = 10 Min danach (oder bis Suchfenster-Ende).
              Alle Nutzereingaben/datetime.now() sind lokale Wanduhrzeit und werden
              vor jeder DB-Abfrage nach UTC konvertiert (ppi_raw/measurements/
              blood_pressure/sessions.ts_start sind projektweit UTC gespeichert) —
              nur für Anzeige/Print wird gezielt zurück nach lokal konvertiert.
              Berechnet: hr_supine, hr_stand, hr_stand_peak, hr_delta, rmssd_supine,
              rmssd_stand, rmssd_delta, und falls vorhanden spo2_supine_avg/min,
              spo2_stand_avg/min, bp_supine_sys/dia_avg, bp_stand_sys/dia_min,
              bp_drop_sys/dia. Bewertung: POTS-Kriterium (ΔHR), orthostatische
              Hypotonie (RR-Abfall ≥20/10mmHg falls Blutdruckdaten vorhanden),
              SpO2-Abfall <92% im Stehen.
              Vergleich mit persönlicher Baseline (Ø aller früheren guided_test-Sessions
              DERSELBEN Person, nicht mit echten Polar-Tests oder ppi_detected-Kandidaten
              vermischt) nach 2+ Tests.
              Speichert Ergebnisse in sessions/session_metrics und als Markdown-Datei.
@method.en   Interactive mode: Shows instructions with ASCII art, guides through test phases
              with countdown timer. Evaluation mode (--evaluate): Manual input of time windows —
              reads, like the guided mode, from already-imported ppi_raw/measurements data,
              regardless of which importer produced it (ECGLogger, HRV Logger, Polar, ...).
              With --evaluate --auto-detect: only a rough search window is needed
              instead of exact times — the standing-up moment is found via the same
              jump heuristic as compute_orthostatic_detection.py (sharp, sustained
              HR rise ≥HR_JUMP_MIN bpm, the same function is imported, not
              reimplemented), supine phase = REF_WINDOW_S before it, standing phase
              = 10 min after (or until search window end).
              All user input/datetime.now() is local wall-clock time and gets
              converted to UTC before every DB query (ppi_raw/measurements/
              blood_pressure/sessions.ts_start are stored in UTC project-wide) —
              only display/print output converts back to local.
              Calculates: hr_supine, hr_stand, hr_stand_peak, hr_delta, rmssd_supine,
              rmssd_stand, rmssd_delta, and if present spo2_supine_avg/min,
              spo2_stand_avg/min, bp_supine_sys/dia_avg, bp_stand_sys/dia_min,
              bp_drop_sys/dia. Assessment: POTS criterion (ΔHR), orthostatic
              hypotension (BP drop ≥20/10mmHg if blood pressure data present),
              SpO2 drop <92% while standing.
              Comparison with personal baseline (average of all previous guided_test
              sessions for the SAME person, not mixed with real Polar tests or
              ppi_detected candidates) after 2+ tests.
              Saves results to sessions/session_metrics and as a Markdown file.
@reads       health.db.ppi_raw, health.db.measurements, health.db.blood_pressure,
             health.db.sessions, health.db.session_metrics
@writes      health.db.sessions, health.db.session_metrics, analyses/orthostatic/*.md
@refs        Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183

@relevance.de  Ermöglicht orthostatische Tests und Analysen, essentiell für die kardiovaskuläre Diagnostik
@relevance.en  Enables orthostatic tests and analyses, essential for cardiovascular diagnostics
@limits.de   Heuristische Methode: Benötigt ausreichend Messwerte (≥2 pro Phase) für valide Ergebnisse.
              RMSSD aus HR-Werten ist nur eine Näherung.
              Dient nur der Selbstbeobachtung, kein medizinisches Gerät.
              --person wird jetzt tatsächlich bis zu den Schreibpfaden durchgereicht
              (vorher deklariert, aber ignoriert — beide Schreib-/Vergleichspfade
              hingen fest an OWN_PERSON_ID) — wichtig bei geteilten Geräten, wo die
              Geräte-ID allein nichts über die Person aussagt.
              --auto-detect findet nur EINEN Kandidaten pro Suchfenster (den mit dem
              größten ΔHR) — bei mehreren Lagewechseln im Fenster (z.B. mehrere
              Steh-Tests hintereinander) das Suchfenster entsprechend eng wählen.
              Blutdruckwerte fließen als Ø (liegend) bzw. Minimum (stehend) ein,
              nicht als Zeitreihe — für die vollständige Messreihe mit
              Einzelzeitstempeln direkt in blood_pressure nachschauen.
@limits.en   Heuristic method: Requires sufficient measurements (≥2 per phase) for valid results.
              RMSSD from HR values is only approximate.
              For self-monitoring only, not a medical device.
              --person is now actually threaded through to the write paths
              (previously declared but ignored — both the write and comparison
              paths were hardcoded to OWN_PERSON_ID) — important for shared
              devices, where the device id alone says nothing about the person.
              --auto-detect only finds ONE candidate per search window (the one
              with the largest ΔHR) — for multiple posture changes in the window
              (e.g. several stand tests in a row), narrow the search window
              accordingly. Blood pressure values are included as average (supine)
              or minimum (standing), not as a time series — check blood_pressure
              directly for the full series with individual timestamps.
@scoring Bewertungs-Score basierend auf Herzfrequenzänderung (ΔHR) und HRV-Reaktion
@usage
    python scripts/utils/orthostatic_test.py
    python scripts/utils/orthostatic_test.py --evaluate
    python scripts/utils/orthostatic_test.py --evaluate --auto-detect
    python scripts/utils/orthostatic_test.py --notes "Test nach Mittagessen"
    python scripts/utils/orthostatic_test.py --evaluate --person PER-xxxxxxxx
    # Geführter Test: Interaktive Anleitung mit Countdown
    # --evaluate: Nachauswertung bestehender Daten (manuelle Zeitfenstereingabe) —
    #   funktioniert mit jeder bereits importierten Quelle (ECGLogger, HRV Logger, ...)
    # --evaluate --auto-detect: wie --evaluate, aber Aufsteh-Zeitpunkt automatisch
    #   aus H10-HF-Sprung gefunden — nur grobes Suchfenster statt exakter Zeiten
    # --notes: Freitext-Notiz zum Test
    # --person: Person-ID für Test (Standard: eigene Person) — wichtig bei
    #   geteilten Geräten, wird jetzt tatsächlich bis zum Schreibpfad durchgereicht
"""

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.device_registry import best_hr_device, label as dev_label
from compute.compute_orthostatic_detection import (
    _detect_day as detect_stand_jump, REF_WINDOW_S,
)

_cfg    = _Cfg()
DB_PATH = _cfg.db_path

MIN_PPI_BEATS = 20   # Mindest-RR-Intervalle pro Phase für ppi_raw-Pfad


# ── Anleitung ─────────────────────────────────────────────────────────────────

def show_instructions() -> None:
    print(t("""
╔══════════════════════════════════════════════════════════════╗
║           ORTHOSTASE-TEST — VORBEREITUNG                     ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  EMPFOHLEN: Polar H10 Brustgurt verwenden                    ║
║  → H10 anlegen, mit Apple Watch / Vantage V3 koppeln         ║
║    Apple Watch → Workout-App → Workout "Andere" starten      ║
║    → H10 erscheint als HR-Quelle; Workout läuft still        ║
║  → ODER: HRV Logger App starten (liefert RR-Intervalle)      ║
║                                                              ║
║  Ohne H10: Workout "Andere" auf Apple Watch starten          ║
║  (optischer Sensor, RMSSD näherungsweise)                    ║
║                                                              ║
║  Test-Protokoll (modifizierter Schellong-Test):              ║
║  1. Hinlegen:  10 Minuten still liegen, ruhig atmen          ║
║  2. Aufstehen: langsam aufstehen, sofort stehen bleiben      ║
║  3. Stehen:    10 Minuten ruhig stehen (kein Herumgehen)     ║
║                                                              ║
║  Nicht während des Tests: trinken, essen, telefonieren       ║
╚══════════════════════════════════════════════════════════════╝
""", """
╔══════════════════════════════════════════════════════════════╗
║           ORTHOSTATIC TEST — PREPARATION                     ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  RECOMMENDED: Use Polar H10 chest strap                      ║
║  → Put on H10, pair with Apple Watch / Vantage V3            ║
║    Apple Watch → Workout app → start workout "Other"         ║
║    → H10 appears as HR source; workout runs silently         ║
║  → OR: start HRV Logger app (delivers RR intervals)          ║
║                                                              ║
║  Without H10: start workout "Other" on Apple Watch           ║
║  (optical sensor, RMSSD is approximate)                      ║
║                                                              ║
║  Test protocol (modified Schellong test):                    ║
║  1. Supine:   lie still for 10 min, breathe calmly           ║
║  2. Stand up: rise slowly, stay standing immediately         ║
║  3. Standing: stand quietly for 10 min (no walking)          ║
║                                                              ║
║  During test avoid: drinking, eating, phone calls            ║
╚══════════════════════════════════════════════════════════════╝
"""))


def countdown_wait(seconds: int, message: str) -> None:
    print(f"\n{message}")
    for remaining in range(seconds, 0, -30):
        if remaining % 60 == 0:
            print(t(f"  → noch {remaining // 60} Min.",
                    f"  → {remaining // 60} min. remaining"), flush=True)
        elif remaining == 30:
            print(t("  → noch 30 Sekunden!", "  → 30 seconds remaining!"), flush=True)
        time.sleep(30)


# ── Datenabruf ────────────────────────────────────────────────────────────────

def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _local_to_utc(dt_local: datetime) -> datetime:
    """Naive lokale Wanduhrzeit (z.B. vom Nutzer eingetippt oder
    datetime.now()) → naive UTC-Zeit. Noetig weil ppi_raw/measurements/
    blood_pressure/sessions.ts_start projektweit in UTC gespeichert werden
    (s. CLAUDE.md 'ts columns are always UTC'), aber der Mensch in lokaler
    Wanduhrzeit denkt und tippt."""
    return dt_local.replace(tzinfo=ZoneInfo(_cfg.home_timezone)).astimezone(timezone.utc).replace(tzinfo=None)


def _utc_to_local(dt_utc: datetime) -> datetime:
    """Naive UTC-Zeit → naive lokale Wanduhrzeit, nur für Anzeige/Reports."""
    return dt_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(_cfg.home_timezone)).replace(tzinfo=None)


def query_ppi(conn, start: datetime, end: datetime,
              person: str) -> tuple[list[int], str, str | None]:
    """RR-Intervalle aus ppi_raw — bestes Gerät laut device_registry.
    Gibt (rr, label, device_id) zurück — device_id ist die rohe Pseudonym-ID
    (z.B. DEV-xxxxxxxx) zum Speichern, label die menschenlesbare Anzeige."""
    s, e = _fmt(start), _fmt(end)
    devs = [r[0] for r in conn.execute("""
        SELECT DISTINCT device FROM ppi_raw
        WHERE person=? AND datetime >= ? AND datetime < ?
    """, (person, s, e)).fetchall() if r[0]]

    chosen = best_hr_device(devs)
    if not chosen:
        return [], t("kein Gerät", "no device"), None

    rows = conn.execute("""
        SELECT pulse_ms FROM ppi_raw
        WHERE person=? AND device=? AND datetime >= ? AND datetime < ?
        ORDER BY datetime
    """, (person, chosen, s, e)).fetchall()

    rr = [r[0] for r in rows if r[0] and 300 < r[0] < 2000]
    return rr, dev_label(chosen), chosen


def query_ppi_beats(conn, start: datetime, end: datetime,
                    person: str) -> tuple[list[tuple[datetime, int]], str, str | None]:
    """Wie query_ppi(), behält aber die Zeitstempel pro Schlag —
    detect_stand_jump() (compute_orthostatic_detection._detect_day) braucht
    (datetime, pulse_ms)-Paare, nicht nur die Pulswerte, um den Sprung-
    Zeitpunkt selbst zu finden."""
    s, e = _fmt(start), _fmt(end)
    devs = [r[0] for r in conn.execute("""
        SELECT DISTINCT device FROM ppi_raw
        WHERE person=? AND datetime >= ? AND datetime < ?
    """, (person, s, e)).fetchall() if r[0]]

    chosen = best_hr_device(devs)
    if not chosen:
        return [], t("kein Gerät", "no device"), None

    rows = conn.execute("""
        SELECT datetime, pulse_ms FROM ppi_raw
        WHERE person=? AND device=? AND datetime >= ? AND datetime < ?
        ORDER BY datetime
    """, (person, chosen, s, e)).fetchall()

    beats = [(datetime.fromisoformat(r[0]), r[1]) for r in rows if r[1] and 300 < r[1] < 2000]
    return beats, dev_label(chosen), chosen


def query_hr(conn, start: datetime, end: datetime,
             person: str) -> tuple[list[float], str, str | None]:
    """HR-Werte aus measurements — bestes Gerät laut device_registry.
    Gibt (hr, label, device_id) zurück, s. query_ppi()."""
    s, e = _fmt(start), _fmt(end)
    devs = [r[0] for r in conn.execute("""
        SELECT DISTINCT device_id FROM measurements
        WHERE person=? AND metric='heart_rate' AND ts >= ? AND ts < ?
    """, (person, s, e)).fetchall() if r[0]]

    chosen = best_hr_device(devs)
    if not chosen:
        return [], t("kein Gerät", "no device"), None

    rows = conn.execute("""
        SELECT value FROM measurements
        WHERE person=? AND metric='heart_rate' AND device_id=? AND ts >= ? AND ts < ?
          AND value > 0
        ORDER BY ts
    """, (person, chosen, s, e)).fetchall()

    return [float(r[0]) for r in rows], dev_label(chosen), chosen


def query_spo2(conn, start: datetime, end: datetime,
               person: str) -> tuple[list[float], str, str | None]:
    """SpO2-Werte aus measurements für ein Zeitfenster — geräteagnostisch wie
    query_hr(), aber ohne eigene Prioritäts-Registry für SpO2 (die gibt es
    projektweit nicht): wählt das Gerät mit den meisten Messungen im
    Fenster, in der Praxis das Gerät, das tatsächlich für diesen Test
    getragen wurde (z.B. Wellue O2Ring), nicht ein nebenbei laufendes
    Handgelenksgerät mit vereinzelten Werten. Gibt (spo2, label, device_id)
    zurück; leere Liste + 'kein Gerät' wenn nichts im Fenster liegt (z.B.
    kein Pulsoximeter getragen) — kein Fehlerfall, SpO2 ist optional."""
    s, e = _fmt(start), _fmt(end)
    counts = conn.execute("""
        SELECT device_id, COUNT(*) FROM measurements
        WHERE person=? AND metric='spo2' AND ts >= ? AND ts < ? AND device_id IS NOT NULL
        GROUP BY device_id ORDER BY COUNT(*) DESC LIMIT 1
    """, (person, s, e)).fetchone()
    if not counts:
        return [], t("kein Gerät", "no device"), None
    chosen = counts[0]

    rows = conn.execute("""
        SELECT value FROM measurements
        WHERE person=? AND metric='spo2' AND device_id=? AND ts >= ? AND ts < ?
          AND value > 0
        ORDER BY ts
    """, (person, chosen, s, e)).fetchall()
    return [float(r[0]) for r in rows], dev_label(chosen), chosen


def query_bp(conn, start: datetime, end: datetime, person: str) -> list[dict]:
    """Blutdruckmessungen aus blood_pressure für ein Zeitfenster —
    geräteunabhängig per Konstruktion (blood_pressure vereint bereits alle
    Quellen), keine Geräteauswahl nötig. Anders als HR/SpO2 sind das
    diskrete Einzelmessungen (typisch mehrere pro Phase bei wiederholter
    Messung, z.B. Withings-BPM-Core-START-3-Serie) — daher Liste statt
    Einzelwert, jede Messung mit eigenem Zeitstempel für den Bericht."""
    s, e = _fmt(start), _fmt(end)
    rows = conn.execute("""
        SELECT ts, systolic, diastolic, pulse FROM blood_pressure
        WHERE person=? AND ts >= ? AND ts < ?
          AND systolic IS NOT NULL AND diastolic IS NOT NULL
        ORDER BY ts
    """, (person, s, e)).fetchall()
    return [{"ts": r[0], "systolic": r[1], "diastolic": r[2], "pulse": r[3]} for r in rows]


def select_data(conn, t_start: datetime, t_stand: datetime,
                t_end: datetime, person: str):
    """
    Wählt Datenquelle: ppi_raw wenn ≥ MIN_PPI_BEATS pro Phase, sonst measurements.
    Gibt (sup_data, sta_data, device_label, mode, device_id) zurück.
    mode = 'ppi' | 'hr'
    """
    sup_rr, label, device_id = query_ppi(conn, t_start, t_stand, person)
    sta_rr, _, _             = query_ppi(conn, t_stand, t_end,   person)

    if len(sup_rr) >= MIN_PPI_BEATS and len(sta_rr) >= MIN_PPI_BEATS:
        return sup_rr, sta_rr, label, 'ppi', device_id

    sup_hr, hr_label, hr_device_id = query_hr(conn, t_start, t_stand, person)
    sta_hr, _, _                   = query_hr(conn, t_stand, t_end,   person)

    if not sup_hr and sup_rr:
        return sup_rr, sta_rr, label, 'ppi', device_id

    return sup_hr, sta_hr, hr_label, 'hr', hr_device_id


# ── Metriken ──────────────────────────────────────────────────────────────────

def _rmssd(vals: list[float]) -> float | None:
    if len(vals) < 2:
        return None
    diffs = [(vals[i+1] - vals[i]) ** 2 for i in range(len(vals) - 1)]
    return round((sum(diffs) / len(diffs)) ** 0.5, 1)


def compute_from_ppi(sup_rr: list[int], sta_rr: list[int]) -> dict:
    """Metriken aus echten RR-Intervallen (ppi_raw)."""
    def mean_rr(rr): return sum(rr) / len(rr) if rr else None

    mr_sup = mean_rr(sup_rr)
    mr_sta = mean_rr(sta_rr)

    # Peak HR: kürzestes RR in den ersten ~3 Minuten stehend
    if sta_rr and mr_sta:
        n_3min = max(1, int(3 * 60 * 1000 / mr_sta))
        hr_peak = round(60000.0 / min(sta_rr[:n_3min]), 1)
    else:
        hr_peak = None

    hr_sup   = round(60000.0 / mr_sup, 1) if mr_sup else None
    hr_sta   = round(60000.0 / mr_sta, 1) if mr_sta else None
    hr_delta = round(hr_peak - hr_sup, 1) if (hr_peak and hr_sup) else 0.0

    return {
        "hr_supine":     hr_sup,
        "hr_stand":      hr_sta,
        "hr_stand_peak": hr_peak,
        "hr_delta":      hr_delta,
        "rmssd_supine":  _rmssd(sup_rr),
        "rmssd_stand":   _rmssd(sta_rr),
        "n_supine":      len(sup_rr),
        "n_standing":    len(sta_rr),
        "mode":          "ppi",
    }


def compute_from_hr(sup_hr: list[float], sta_hr: list[float]) -> dict:
    """Metriken aus HR-Werten (measurements-Fallback). RMSSD näherungsweise."""
    def avg(lst): return sum(lst) / len(lst) if lst else None

    hr_sup_avg = avg(sup_hr)
    hr_sta_avg = avg(sta_hr)
    hr_peak    = max(sta_hr) if sta_hr else None

    rr_sup = [60000.0 / h for h in sup_hr if h > 0]
    rr_sta = [60000.0 / h for h in sta_hr if h > 0]

    return {
        "hr_supine":     round(hr_sup_avg, 1) if hr_sup_avg else None,
        "hr_stand":      round(hr_sta_avg, 1) if hr_sta_avg else None,
        "hr_stand_peak": hr_peak,
        "hr_delta":      round((hr_peak or 0) - (hr_sup_avg or 0), 1),
        "rmssd_supine":  _rmssd(rr_sup),
        "rmssd_stand":   _rmssd(rr_sta),
        "n_supine":      len(sup_hr),
        "n_standing":    len(sta_hr),
        "mode":          "hr",
    }


def compute(sup, sta, mode: str) -> dict:
    return compute_from_ppi(sup, sta) if mode == 'ppi' else compute_from_hr(sup, sta)


def compute_spo2(spo2_sup: list[float], spo2_sta: list[float]) -> dict:
    """Ø und Minimum pro Phase — Minimum ist das klinisch relevante (Desaturation),
    nicht nur der Durchschnitt."""
    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None
    return {
        "spo2_supine_avg": avg(spo2_sup),
        "spo2_supine_min": min(spo2_sup) if spo2_sup else None,
        "spo2_stand_avg":  avg(spo2_sta),
        "spo2_stand_min":  min(spo2_sta) if spo2_sta else None,
    }


def compute_bp(bp_sup: list[dict], bp_sta: list[dict]) -> dict:
    """Ø liegend als Baseline, Minimum stehend für den Hypotonie-Check —
    ein einzelner tiefer Ausreißer im Stehen ist der klinisch entscheidende
    Wert, nicht im Ø versteckt. bp_drop_* ist Ø-liegend minus Minimum-stehend,
    also der ungünstigste beobachtete Abfall (nicht zwingend der Abfall
    innerhalb der ersten 3 Minuten, da BPM-Core-Messungen diskret sind statt
    kontinuierlich — Zeitpunkt jeder Messung steht trotzdem im Bericht)."""
    def avg(key, rows): return (round(sum(r[key] for r in rows) / len(rows), 1)
                                 if rows else None)
    sys_sup_avg = avg("systolic", bp_sup)
    dia_sup_avg = avg("diastolic", bp_sup)
    sys_sta_min = min((r["systolic"] for r in bp_sta), default=None)
    dia_sta_min = min((r["diastolic"] for r in bp_sta), default=None)
    return {
        "bp_supine_sys_avg": sys_sup_avg,
        "bp_supine_dia_avg": dia_sup_avg,
        "bp_stand_sys_min":  sys_sta_min,
        "bp_stand_dia_min":  dia_sta_min,
        "bp_drop_sys": (round(sys_sup_avg - sys_sta_min, 1)
                        if sys_sup_avg is not None and sys_sta_min is not None else None),
        "bp_drop_dia": (round(dia_sup_avg - dia_sta_min, 1)
                        if dia_sup_avg is not None and dia_sta_min is not None else None),
    }


# ── Bewertung ─────────────────────────────────────────────────────────────────

def assess(m: dict) -> str:
    lines = []
    delta = m["hr_delta"] or 0
    if delta >= 30:
        lines.append(t("⚠️  POTS-Kriterium erfüllt (≥30 bpm) — Abklärung empfohlen",
                       "⚠️  POTS criterion met (≥30 bpm) — cardiology referral recommended"))
    elif delta >= 20:
        lines.append(t("⚡  Deutlich erhöhte Reaktion (20–29 bpm) — Kipptisch-Test empfohlen",
                       "⚡  Markedly elevated response (20–29 bpm) — tilt table test recommended"))
    elif delta >= 15:
        lines.append(t("⚡  Grenzwertig erhöht (15–19 bpm) — Verlaufskontrolle empfohlen",
                       "⚡  Borderline elevated (15–19 bpm) — follow-up monitoring recommended"))
    else:
        lines.append(t("✅  Normaler orthostatischer Response (<15 bpm)",
                       "✅  Normal orthostatic response (<15 bpm)"))

    bp_drop_sys = m.get("bp_drop_sys")
    bp_drop_dia = m.get("bp_drop_dia")
    if bp_drop_sys is not None or bp_drop_dia is not None:
        if (bp_drop_sys or 0) >= 20 or (bp_drop_dia or 0) >= 10:
            lines.append(t(
                "⚠️  Orthostatische Hypotonie-Kriterium erfüllt (≥20 mmHg systolisch "
                "oder ≥10 mmHg diastolisch) — andere Diagnose als POTS, ärztlich abklären",
                "⚠️  Orthostatic hypotension criterion met (≥20 mmHg systolic or "
                "≥10 mmHg diastolic) — different diagnosis than POTS, needs clinical follow-up"))
        else:
            lines.append(t("✅  Kein Hinweis auf orthostatische Hypotonie im Blutdruck",
                           "✅  No sign of orthostatic hypotension in blood pressure"))

    spo2_min = m.get("spo2_stand_min")
    if spo2_min is not None and spo2_min < 92:
        lines.append(t(f"⚠️  SpO2 im Stehen auf {spo2_min}% gefallen — abklären",
                       f"⚠️  SpO2 dropped to {spo2_min}% while standing — needs follow-up"))

    return "\n  ".join(lines)


def compare_baseline(conn, m: dict, person: str) -> str:
    """Vergleicht mit dem Ø aller frueheren guided_test-Sessions DIESER Person —
    bewusst nicht mit echten Polar-Tests oder ppi_detected-Kandidaten gemischt,
    da orthostatic_tests (die alte Zieltabelle) historisch ausschliesslich von
    diesem Skript befuellt wurde; sessions/session_metrics wird jetzt genauso
    eng gefiltert (source_app='guided_test'), um dieselbe Baseline-Bedeutung
    ("meine eigenen bisherigen geführten Tests") zu erhalten."""
    baseline = conn.execute("""
        SELECT ROUND(AVG(CASE WHEN sm.metric='hr_delta' THEN sm.value END),1),
               ROUND(AVG(CASE WHEN sm.metric='rmssd_supine' THEN sm.value END),1),
               ROUND(AVG(CASE WHEN sm.metric='rmssd_stand' THEN sm.value END),1),
               COUNT(DISTINCT s.id)
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type='orthostatic' AND s.source_app='guided_test' AND s.person=?
    """, (person,)).fetchone()

    if not baseline or not baseline[0] or baseline[3] < 2:
        return t("  (Noch keine Baseline — nach 2+ Tests verfügbar.)",
                 "  (No baseline yet — available after 2+ tests.)")

    delta_diff = round((m["hr_delta"] or 0) - (baseline[0] or 0), 1)
    direction  = (t("↑ schlechter", "↑ worse")    if delta_diff > 3
                  else t("↓ besser", "↓ better")  if delta_diff < -3
                  else t("≈ unverändert", "≈ unchanged"))

    lines = [
        f"\n{'─'*60}",
        t("VERGLEICH MIT EIGENER BASELINE", "COMPARISON WITH PERSONAL BASELINE"),
        f"{'─'*60}",
        f"                  {t('Baseline (Ø)', 'Baseline (avg)')}   {t('Heute', 'Today')}",
        f"  ΔHR:            {baseline[0]:>7} bpm   {m['hr_delta']:>5} bpm  {direction}",
    ]
    if m["rmssd_supine"] and baseline[1]:
        diff = round((m["rmssd_supine"] or 0) - (baseline[1] or 0), 1)
        lines.append(
            f"  RMSSD {t('liegend', 'supine')}:  {baseline[1]:>7} ms    {m['rmssd_supine']:>5} ms  "
            f"({'↑' if diff > 3 else '↓' if diff < -3 else '≈'})")
    if m["rmssd_stand"] and baseline[2]:
        lines.append(
            f"  RMSSD {t('stehend', 'stand')}:   {baseline[2]:>7} ms    {m['rmssd_stand']:>5} ms")
    return "\n".join(lines)


# ── Speichern ─────────────────────────────────────────────────────────────────

def save_result(conn, m: dict, t_stand: datetime, device_id: str | None,
                mode: str, person: str, notes: str | None = None) -> None:
    """Schreibt nach sessions/session_metrics (type='orthostatic',
    source_app='guided_test') — NICHT mehr in die verwaiste orthostatic_tests-
    Tabelle (0 Zeilen in der echten DB, wird von analyse_orthostatic.py und
    mehreren anderen Skripten gar nicht gelesen; die tatsaechlich gelesene
    Zielstruktur ist sessions/session_metrics, s. compute_orthostatic_detection.py
    und import_polar.py::import_orthostatic_tests() fuer dasselbe Muster).
    t_stand muss UTC sein (Aufrufer konvertiert via _local_to_utc) — ts_start
    ist UTC, date wird daraus als lokaler Kalendertag abgeleitet (s. CLAUDE.md
    Konvention: ts immer UTC, date immer lokal)."""
    dt_str   = t_stand.strftime("%Y-%m-%dT%H:%M:%S")
    date_str = _utc_to_local(t_stand).strftime("%Y-%m-%d")
    sid = f"guided_test_ortho_{dt_str}_{person}"

    conn.execute("""
        INSERT OR IGNORE INTO sessions
        (id, type, ts_start, ts_end, date, device_id, person, source_app)
        VALUES (?, 'orthostatic', ?, NULL, ?, ?, ?, 'guided_test')
    """, (sid, dt_str, date_str, device_id, person))

    rmssd_delta = (round((m["rmssd_stand"] or 0) - (m["rmssd_supine"] or 0), 1)
                   if (m["rmssd_stand"] is not None and m["rmssd_supine"] is not None) else None)
    mode_note = t(f"Quelle: {mode}", f"source: {mode}")
    hr_delta_note = f"{mode_note}" + (f" | {notes}" if notes else "")

    metric_pairs = [
        ("hr_supine",      m["hr_supine"],     "bpm", None),
        ("hr_standup_min", m["hr_stand_peak"], "bpm", None),
        ("hr_stand",       m["hr_stand"],      "bpm", None),
        ("hr_delta",       m["hr_delta"],      "bpm", hr_delta_note),
        ("rmssd_supine",   m["rmssd_supine"],  "ms",  None),
        ("rmssd_stand",    m["rmssd_stand"],   "ms",  None),
        ("rmssd_delta",    rmssd_delta,        "ms",  None),
        ("n_supine",       m["n_supine"],      None,  None),
        ("n_standing",     m["n_standing"],    None,  None),
        # Optional: SpO2 (z.B. Wellue O2Ring) und Blutdruck (z.B. Withings
        # BPM Core), falls im Zeitfenster vorhanden — jedes Gerät, das
        # parallel zur H10-Aufzeichnung lief, wird automatisch mit
        # ausgewertet, kein separater Eintrag noetig.
        ("spo2_supine_avg", m.get("spo2_supine_avg"), "%",    None),
        ("spo2_supine_min", m.get("spo2_supine_min"), "%",    None),
        ("spo2_stand_avg",  m.get("spo2_stand_avg"),  "%",    None),
        ("spo2_stand_min",  m.get("spo2_stand_min"),  "%",    None),
        ("bp_supine_sys_avg", m.get("bp_supine_sys_avg"), "mmHg", None),
        ("bp_supine_dia_avg", m.get("bp_supine_dia_avg"), "mmHg", None),
        ("bp_stand_sys_min",  m.get("bp_stand_sys_min"),  "mmHg", None),
        ("bp_stand_dia_min",  m.get("bp_stand_dia_min"),  "mmHg", None),
        ("bp_drop_sys",       m.get("bp_drop_sys"),       "mmHg", None),
        ("bp_drop_dia",       m.get("bp_drop_dia"),       "mmHg", None),
    ]
    for metric, value, unit, value_text in metric_pairs:
        if value is None:
            continue
        conn.execute("""
            INSERT OR IGNORE INTO session_metrics (session_id, metric, value, value_text, unit)
            VALUES (?,?,?,?,?)
        """, (sid, metric, value, value_text, unit))
    conn.commit()


# ── Ausgabe ───────────────────────────────────────────────────────────────────

def _spo2_bp_lines(m: dict) -> list[str]:
    """Zusätzliche Report-Zeilen für SpO2/Blutdruck — nur falls im Zeitfenster
    vorhanden, sonst leer (kein Pflichtbestandteil des Tests)."""
    lines = []
    if m.get("spo2_supine_avg") is not None or m.get("spo2_stand_avg") is not None:
        lines.append(t(
            f"  SpO2 liegend:    ∅{m.get('spo2_supine_avg')}%  (min {m.get('spo2_supine_min')}%)",
            f"  SpO2 supine:     ∅{m.get('spo2_supine_avg')}%  (min {m.get('spo2_supine_min')}%)"))
        lines.append(t(
            f"  SpO2 stehend:    ∅{m.get('spo2_stand_avg')}%  (min {m.get('spo2_stand_min')}%)",
            f"  SpO2 standing:   ∅{m.get('spo2_stand_avg')}%  (min {m.get('spo2_stand_min')}%)"))
    if m.get("bp_supine_sys_avg") is not None or m.get("bp_stand_sys_min") is not None:
        lines.append(t(
            f"  RR liegend (Ø):  {m.get('bp_supine_sys_avg')}/{m.get('bp_supine_dia_avg')} mmHg",
            f"  BP supine (avg): {m.get('bp_supine_sys_avg')}/{m.get('bp_supine_dia_avg')} mmHg"))
        lines.append(t(
            f"  RR stehend (min):{m.get('bp_stand_sys_min')}/{m.get('bp_stand_dia_min')} mmHg  "
            f"(Abfall: {m.get('bp_drop_sys')}/{m.get('bp_drop_dia')} mmHg)",
            f"  BP standing (min):{m.get('bp_stand_sys_min')}/{m.get('bp_stand_dia_min')} mmHg  "
            f"(drop: {m.get('bp_drop_sys')}/{m.get('bp_drop_dia')} mmHg)"))
    return lines


def print_result(m: dict, mode: str, device: str, conn, person: str) -> None:
    mode_label = (t("ppi_raw (RMSSD exakt)", "ppi_raw (RMSSD exact)")
                  if mode == 'ppi'
                  else t("measurements (RMSSD Näherung)", "measurements (RMSSD approx.)"))
    assessment = assess(m)
    extra_lines = _spo2_bp_lines(m)
    extra_block = ("\n" + "\n".join(extra_lines) +
                   f"\n╠══════════════════════════════════════════════════════════════╣") if extra_lines else ""

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          {t('ORTHOSTASE-TEST ERGEBNIS', 'ORTHOSTATIC TEST RESULT'):<50}║
╠══════════════════════════════════════════════════════════════╣
  {t('Sensor', 'Sensor')}:          {device}
  {t('Datenquelle', 'Data source')}:    {mode_label}
  {t('Messungen', 'Readings')}:       {m['n_supine']} {t('liegend', 'supine')} / {m['n_standing']} {t('stehend', 'standing')}
╠══════════════════════════════════════════════════════════════╣
  {t('Liegend', 'Supine')}:         ∅{m['hr_supine']:>5} bpm
  {t('Stehend', 'Standing')}:        ∅{m['hr_stand']:>5} bpm  (Peak: {m['hr_stand_peak']} bpm)
  ΔHR:             {m['hr_delta']:>+5} bpm
  RMSSD {t('liegend', 'supine')}:   {m['rmssd_supine']:>5} ms
  RMSSD {t('stehend', 'standing')}:  {m['rmssd_stand']:>5} ms{extra_block}
  {assessment}
╚══════════════════════════════════════════════════════════════╝""")

    print(compare_baseline(conn, m, person))


def save_markdown(m: dict, mode: str, device: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"orthostatic_{ts}.md"
    mode_label = "ppi_raw (exakt)" if mode == 'ppi' else "measurements (Näherung)"

    extra_md = ""
    if m.get("spo2_supine_avg") is not None or m.get("spo2_stand_avg") is not None:
        extra_md += (
            f"- SpO2 liegend: ∅{m.get('spo2_supine_avg')}% (min {m.get('spo2_supine_min')}%)\n"
            f"- SpO2 stehend: ∅{m.get('spo2_stand_avg')}% (min {m.get('spo2_stand_min')}%)\n")
    if m.get("bp_supine_sys_avg") is not None or m.get("bp_stand_sys_min") is not None:
        extra_md += (
            f"- RR liegend (Ø): {m.get('bp_supine_sys_avg')}/{m.get('bp_supine_dia_avg')} mmHg\n"
            f"- RR stehend (min): {m.get('bp_stand_sys_min')}/{m.get('bp_stand_dia_min')} mmHg "
            f"(Abfall: {m.get('bp_drop_sys')}/{m.get('bp_drop_dia')} mmHg)\n")

    out.write_text(
        f"# Orthostase-Test {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"## Ergebnis\n"
        f"- Sensor: {device}\n"
        f"- Datenquelle: {mode_label}\n"
        f"- Messungen: {m['n_supine']} liegend / {m['n_standing']} stehend\n"
        f"- Liegend: ∅{m['hr_supine']} bpm\n"
        f"- Stehend: ∅{m['hr_stand']} bpm (Peak: {m['hr_stand_peak']} bpm)\n"
        f"- ΔHR: {m['hr_delta']:+} bpm\n"
        f"- RMSSD liegend: {m['rmssd_supine']} ms\n"
        f"- RMSSD stehend: {m['rmssd_stand']} ms\n"
        f"{extra_md}\n"
        f"## Bewertung\n{assess(m)}\n\n"
        f"⚕️ Kein Ersatz für ärztliche Diagnose.\n",
        encoding="utf-8",
    )
    return out


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Geführter Orthostase-Test", "Guided orthostatic test"))
    parser.add_argument("--evaluate", action="store_true",
                        help=t("Nur Auswertung — Zeitfenster manuell eingeben",
                               "Evaluation only — enter time window manually"))
    parser.add_argument("--auto-detect", action="store_true",
                        help=t(
                            "Mit --evaluate: Aufsteh-Zeitpunkt automatisch aus dem "
                            "H10-HF-Sprung finden statt ihn einzutippen — nur grobes "
                            "Suchfenster nötig",
                            "With --evaluate: automatically find the standing-up moment "
                            "from the H10 HR jump instead of typing it — only a rough "
                            "search window needed"))
    parser.add_argument("--notes", default="", metavar="TEXT",
                        help=t("Freitext-Notiz zum Test", "Free-text note for this test"))
    parser.add_argument("--person", default=OWN_PERSON_ID)
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.auto_detect and not args.evaluate:
        print(t("--auto-detect braucht --evaluate.", "--auto-detect requires --evaluate."))
        return

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    # Ab hier gilt durchgehend: t_start/t_stand/t_end sind UTC (fuer alle
    # DB-Abfragen, s. _local_to_utc/_utc_to_local oben) — Nutzereingaben und
    # datetime.now() sind lokale Wanduhrzeit und werden vor der Weitergabe
    # konvertiert; fuer Anzeige/Print wird gezielt zurueckkonvertiert.
    if args.evaluate and args.auto_detect:
        print(t(
            "Grobes Suchfenster (muss Liegephase + Aufstehen enthalten, "
            "Format: YYYY-MM-DDTHH:MM):",
            "Rough search window (must contain the supine phase + standing up, "
            "format: YYYY-MM-DDTHH:MM):"))
        search_start = _local_to_utc(datetime.fromisoformat(
            input(t("  Von (z.B. Testbeginn liegend): ", "  From (e.g. start of test lying down): ")).strip()))
        search_end = _local_to_utc(datetime.fromisoformat(
            input(t("  Bis (z.B. Testende): ", "  To (e.g. end of test): ")).strip()))

        print(t("\nSuche HF-Sprung im Fenster …", "\nSearching for HR jump in window …"))
        beats, device_label, _ = query_ppi_beats(conn, search_start, search_end, args.person)
        if len(beats) < 2 * 15:  # MIN_BEATS-Größenordnung, s. compute_orthostatic_detection
            print(t(
                f"⚠️  Zu wenige H10-Schläge im Fenster ({len(beats)}) — "
                "Auto-Erkennung nicht möglich. Weiter mit --evaluate (ohne --auto-detect) "
                "und Zeiten manuell eingeben.",
                f"⚠️  Too few H10 beats in window ({len(beats)}) — "
                "auto-detection not possible. Use --evaluate (without --auto-detect) "
                "and enter times manually instead."))
            conn.close()
            return

        candidate = detect_stand_jump(beats, None)
        if not candidate:
            print(t(
                "⚠️  Kein scharfer HF-Sprung im Fenster gefunden (kein klarer "
                "Lagewechsel erkannt). Weiter mit --evaluate (ohne --auto-detect) "
                "und Zeiten manuell eingeben.",
                "⚠️  No sharp HR jump found in window (no clear posture change "
                "detected). Use --evaluate (without --auto-detect) and enter "
                "times manually instead."))
            conn.close()
            return

        # candidate["datetime"] kommt aus den (UTC-gestempelten) beats,
        # ist also bereits UTC — keine weitere Konvertierung noetig.
        t_stand = datetime.fromisoformat(candidate["datetime"])
        t_start = t_stand - timedelta(seconds=REF_WINDOW_S)
        t_end   = min(search_end, t_stand + timedelta(seconds=600))
        t_stand_local = _utc_to_local(t_stand)
        print(t(
            f"→ Aufsteh-Moment erkannt: {t_stand_local.strftime('%H:%M:%S')} "
            f"(ΔHR-Sprung {candidate['hr_delta']:+.1f} bpm, Sensor: {device_label})",
            f"→ Standing-up moment detected: {t_stand_local.strftime('%H:%M:%S')} "
            f"(ΔHR jump {candidate['hr_delta']:+.1f} bpm, sensor: {device_label})"))
    elif args.evaluate:
        print(t("Zeitfenster (Format: YYYY-MM-DDTHH:MM):",
                "Time window (format: YYYY-MM-DDTHH:MM):"))
        t_start  = _local_to_utc(datetime.fromisoformat(
            input(t("  Hinlegen um: ", "  Lying down at: ")).strip()))
        t_stand  = _local_to_utc(datetime.fromisoformat(
            input(t("  Aufstehen um: ", "  Standing up at: ")).strip()))
        t_end    = _local_to_utc(datetime.fromisoformat(
            input(t("  Ende um: ", "  End at: ")).strip()))
    else:
        show_instructions()
        input(t("Drücke ENTER wenn du bereit bist hinzuliegen …",
                "Press ENTER when you are ready to lie down …"))
        t_start_local = datetime.now()
        print(f"\n→ {t('Start', 'Start')}: {t_start_local.strftime('%H:%M:%S')}")
        countdown_wait(600, t("⏱ Liegephase: 10 Minuten", "⏱ Supine phase: 10 minutes"))

        input(t("\n→ Steh jetzt langsam auf. ENTER sobald du stehst …",
                "\n→ Stand up slowly. Press ENTER when standing …"))
        t_stand_local = datetime.now()
        print(f"→ {t('Aufgestanden', 'Standing')}: {t_stand_local.strftime('%H:%M:%S')}")
        countdown_wait(600, t("⏱ Stehphase: 10 Minuten", "⏱ Standing phase: 10 minutes"))

        t_end_local = datetime.now()
        print(f"\n→ {t('Test beendet', 'Test complete')}: {t_end_local.strftime('%H:%M:%S')}")

        t_start = _local_to_utc(t_start_local)
        t_stand = _local_to_utc(t_stand_local)
        t_end   = _local_to_utc(t_end_local)

    print(t("\nLade Daten …", "\nLoading data …"))
    sup, sta, device, mode, device_id = select_data(conn, t_start, t_stand, t_end, args.person)

    mode_label = t("ppi_raw (RR-Intervalle)", "ppi_raw (RR intervals)") if mode == 'ppi' \
                 else t("measurements (HR-Werte)", "measurements (HR values)")
    print(f"  {t('Sensor', 'Sensor')}:       {device}")
    print(f"  {t('Quelle', 'Source')}:       {mode_label}")
    print(f"  {t('Liegend', 'Supine')}:      {len(sup)} {t('Werte', 'values')}")
    print(f"  {t('Stehend', 'Standing')}:     {len(sta)} {t('Werte', 'values')}")

    if len(sup) < 2 or len(sta) < 2:
        print(t(
            "\n⚠️  Zu wenige Messwerte!\n"
            "  Tipp: Workout \"Andere\" auf Apple Watch starten (misst sekündlich)\n"
            "  ODER: HRV Logger App parallel laufen lassen (liefert RR-Intervalle)",
            "\n⚠️  Too few readings!\n"
            "  Tip: Start workout \"Other\" on Apple Watch (measures every second)\n"
            "  OR: Run HRV Logger app in parallel (delivers RR intervals)"))
        conn.close()
        return

    m = compute(sup, sta, mode)

    # Optional: SpO2 (z.B. Wellue O2Ring) und Blutdruck (z.B. Withings BPM
    # Core), falls parallel zur H10-Aufzeichnung im selben Zeitfenster
    # gemessen — automatisch geräteagnostisch mit ausgewertet, kein
    # zusätzlicher manueller Schritt nötig. Fehlt eine Quelle einfach
    # (kein Pulsoximeter/Blutdruckmessgerät benutzt), bleiben die
    # entsprechenden Metriken None und tauchen im Bericht nicht auf.
    spo2_sup, _, _ = query_spo2(conn, t_start, t_stand, args.person)
    spo2_sta, _, _ = query_spo2(conn, t_stand, t_end, args.person)
    m.update(compute_spo2(spo2_sup, spo2_sta))

    bp_sup = query_bp(conn, t_start, t_stand, args.person)
    bp_sta = query_bp(conn, t_stand, t_end, args.person)
    m.update(compute_bp(bp_sup, bp_sta))

    print_result(m, mode, device, conn, args.person)

    notes = args.notes.strip() or None
    save_result(conn, m, t_stand, device_id, mode, args.person, notes)

    out = save_markdown(m, mode, device, _cfg.analyses_dir / "orthostatic")
    print(t(f"\n→ Gespeichert: {out}", f"\n→ Saved: {out}"))
    print(t("⚕️  Kein Ersatz für ärztliche Diagnose.", "⚕️  Not a substitute for professional diagnosis."))

    conn.close()


if __name__ == "__main__":
    main()
