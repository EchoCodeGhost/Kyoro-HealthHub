#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Detaillierte EKG-Analyse — Apple Watch ECG Sessions

Analysiert alle ECG-Aufnahmen mit Fokus auf:
- Klassifikationsverteilung (Sinusrhythmus, AFib, Hohe HF, Schlechte Aufzeichnung)
- Zeitliche Clusterung und Tageszeit-Verteilung
- AFib-Sessions: Zeitabstände, Kontext, Wochentag
- PPI-Analyse für verfügbare Zeitfenster (AFib vs. Sinusrhythmus)
- HRV-Vergleich an EKG-Tagen vs. EKG-freien Tagen
- Kreuzreferenz mit arrhythmie_episoden (±1 Tag)

Usage:
  python analyse_ecg_detail.py --plot
  python analyse_ecg_detail.py --from 2025-01-01 --to 2026-05-31 --plot --no-llm
  python analyse_ecg_detail.py --plot --lang en

@tier        heuristic
@purpose.de  Analysiert Apple Watch ECG-Sessionen: Klassifikationsverteilung, zeitliche
             Clusterung, Tageszeit-Verteilung, PPI-Analyse für AFib-Fenster und
             Kreuzreferenz mit arrhythmie_episoden.
@purpose.en  Analyses Apple Watch ECG sessions: classification distribution, temporal
             clustering, time-of-day distribution, PPI analysis for AFib windows and
             cross-reference with arrhythmie_episoden.
@method.de   Normalisierung der Apple Watch Klassifikationen (atrial_fibrillation /
             sinus_rhythm / high_hr / inconclusive); Gruppen- und Zeitreihen-Analyse.
             Keine eigene Arrhythmie-Klassifikation — reine Auswertung vorhandener Labels.
@method.en   Normalisation of Apple Watch classifications (atrial_fibrillation /
             sinus_rhythm / high_hr / inconclusive); group and time-series analysis.
             No independent arrhythmia classification — pure evaluation of existing labels.
@limits.de   Heuristische Methode: Apple Watch ECG (Series 4+) ist FDA-freigegeben für Rhythmusanalyse
             bei Erwachsenen (FDA De Novo K172503, 2018). Erkennt nur Rhythmusmuster
             in expliziten 30-Sekunden-Aufnahmen; intermittierende Episoden können fehlen.
             CV > 10% als Indikator für Consumer-PPI-Daten: heuristischer Schwellenwert,
             projektintern — kein klinisch validierter Grenzwert. n=1.
             WICHTIG — zwei unabhängige Grundlagen im selben Bericht: Die
             Geräteklassifikation (Abschnitt 1) stammt aus der EKG-Rohwellenform
             (elektrisches Signal); die CV-RR/RMSSD-Kennzahlen in Abschnitt 5 stammen aus
             ppi_raw (optische Puls-Puls-Intervalle, anderes Messprinzip, zeitlich nahes
             aber unabhängiges Fenster). Ein hohes CV/RMSSD dort widerspricht einer
             "Sinusrhythmus"-Klassifikation NICHT automatisch — Abschnitt 5 weist explizit
             darauf hin.
             Plausibilitätsprüfung je PPI-Fenster (Abschnitt 5): CV-RR > 50% oder
             RMSSD > 200 ms gelten als außerhalb dessen, was in dokumentierten
             Rhythmusklassen (Sinus, AFib) vorkommt, und werden als artefaktverdächtig
             markiert statt als Befund gedruckt (_CV_IMPLAUSIBLE_PCT / _RMSSD_IMPLAUSIBLE_MS
             in diesem Skript). Begründung: dokumentierte AFib-Kohorten erreichen CV-RR
             typischerweise ~15-30%, vereinzelt bis ~40% (Task Force ESC/NASPE 1996;
             arrhythmia_utils.CV_AFIB_HIGH=15% als "hochgradig AFib-verdächtig" in diesem
             Projekt); der theoretische Maximalwert unter dem 350-2000-ms-Filter von
             ppi_raw liegt bei ~70%, kommt physiologisch aber nicht vor. RMSSD liegt in
             Ruhe gesund bei ~20-100 ms, auch in kardial vorbelasteten Kohorten selten
             > 150-200 ms. Diese Schwellen sind heuristisch/projektintern, kein publizierter
             Diagnostik-Cut-off — sie trennen "plausible Messung" von "Artefakt", nicht
             "gesund" von "krank". n=1.
@limits.en   Heuristic method: Apple Watch ECG (Series 4+) is FDA-cleared for rhythm analysis in adults
             (FDA De Novo K172503, 2018). Detects rhythm patterns only in explicit
             30-second recordings; intermittent episodes may be missed. CV > 10% as
             indicator for consumer PPI data: heuristic threshold, project-internal —
             no clinically validated cut-off. n=1.
             IMPORTANT — two independent bases in the same report: the device
             classification (Section 1) comes from the raw ECG waveform (electrical
             signal); the CV-RR/RMSSD metrics in Section 5 come from ppi_raw (optical
             pulse-to-pulse intervals, different measurement principle, temporally close
             but independent window). A high CV/RMSSD there does NOT automatically
             contradict a "sinus rhythm" classification — Section 5 states this explicitly.
             Per-window plausibility check (Section 5): CV-RR > 50% or RMSSD > 200 ms are
             considered outside what occurs in documented rhythm classes (sinus, AFib) and
             are flagged as artifact-suspect instead of being printed as a finding
             (_CV_IMPLAUSIBLE_PCT / _RMSSD_IMPLAUSIBLE_MS in this script). Rationale:
             documented AFib cohorts typically reach CV-RR ~15-30%, occasionally up to ~40%
             (Task Force ESC/NASPE 1996; arrhythmia_utils.CV_AFIB_HIGH=15% as "highly
             AFib-suspect" in this project); the theoretical maximum under ppi_raw's
             350-2000 ms filter is ~70%, but that does not occur physiologically. RMSSD at
             healthy rest is ~20-100 ms, and rarely exceeds ~150-200 ms even in
             cardiac-compromised cohorts. These thresholds are heuristic/project-internal,
             not a published diagnostic cut-off — they separate "plausible measurement"
             from "artifact", not "healthy" from "diseased". n=1.
@scoring
    ECG classification: sinus_rhythm | atrial_fibrillation | high_hr | inconclusive
    AFib indicator: CV > 10% in PPI data (heuristic threshold)
    Artifact-suspect (excluded from findings): CV-RR > 50% or RMSSD > 200 ms per window
@refs        FDA De Novo Authorization K172503 (2018). Apple Watch ECG for AFib detection.
             https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN170037.pdf
             Task Force of the ESC and NASPE (1996). Heart rate variability.
             Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@reads       ecg_sessions, ppi_raw, arrhythmie_episoden
@writes      analyses/cardiovascular/*.{md,png} (kein DB-Write)

@usage
    python analyse_ecg_detail.py
    python analyse_ecg_detail.py --help
    python analyse_ecg_detail.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.device_registry import is_device_active
from modules.confidence import label_finding
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_ECG_DETAIL_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_ECG_DETAIL_EN as SYSTEM_PROMPT_EN,
)

cfg = Config()
DB_PATH = cfg.db_path
OUT_DIR = cfg.analyses_dir / "cardiovascular"

# ── Classification normalisation ──────────────────────────────────────────────

# Muss das Vokabular abdecken, das die Importer tatsaechlich schreiben
# (import_garmin_gdpr._ECG_CLASSIF_MAP, import_ecg_apple.CLASSIF_MAP) — nicht die
# Rohbezeichnungen der Geraete. Fehlt ein Wert, fiel er still auf "inconclusive"
# durch: so wurden sechs unauffaellige Sinusrhythmen als "uneindeutig" berichtet.
_CLS_MAP = {
    "atrial_fibrillation": "afib",
    "afib":                "afib",
    "sinus_rhythm":        "sinus_rhythm",
    "sinus_normal":        "sinus_rhythm",
    "high_heart_rate":     "high_hr",
    "high_hr":             "high_hr",
    "poor_recording":      "inconclusive",
    "inconclusive":        "inconclusive",
    # Legacy-Rohbezeichnungen aus frueheren Importen
    "Hohe Herzfrequenz":   "high_hr",
    "Schlechte Aufzeichnung": "inconclusive",
    "Uneindeutig":         "inconclusive",
}

_CLS_LABEL_DE = {
    "afib":          "VHF / AFib",
    "sinus_rhythm":  "Sinusrhythmus",
    "high_hr":       "Hohe Herzfrequenz",
    "inconclusive":  "Schlechte Aufz./Uneindeutig",
}
_CLS_LABEL_EN = {
    "afib":          "AFib",
    "sinus_rhythm":  "Sinus rhythm",
    "high_hr":       "High HR",
    "inconclusive":  "Poor recording / inconclusive",
}

COLOR_MAP = {
    "sinus_rhythm": "#50FA7B",
    "afib":         "#FF4444",
    "high_hr":      "#FFD700",
    "inconclusive": "#888888",
}

BG    = "#1A1A2E"
AXES  = "#16213E"
TXT   = "#E0E0E0"
TICK  = "#AAAAAA"
SPINE = "#555577"


_UNMAPPED_CLS: set[str] = set()


def _norm_cls(raw: str) -> str:
    """Klassifikation auf das Berichtsvokabular abbilden.

    Unbekannte Werte werden gesammelt statt still zu "inconclusive" zu verfallen —
    ein stiller Durchfall hat unauffaellige Befunde jahrelang als nicht bewertbar
    ausgewiesen. Der Aufrufer meldet die Sammlung im Bericht.
    """
    key = raw or ""
    if key and key not in _CLS_MAP:
        _UNMAPPED_CLS.add(key)
    return _CLS_MAP.get(key, "inconclusive")


def _cls_label(cls: str) -> str:
    return t(_CLS_LABEL_DE.get(cls, cls), _CLS_LABEL_EN.get(cls, cls))


# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    return open_db()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0


def _verify_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return set of column names for table."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# ── Statistics helpers ────────────────────────────────────────────────────────

def _avg(lst: list) -> float | None:
    valid = [x for x in lst if x is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


def _std(lst: list) -> float | None:
    valid = [x for x in lst if x is not None]
    n = len(valid)
    if n < 2:
        return None
    mu = sum(valid) / n
    return round(math.sqrt(sum((x - mu) ** 2 for x in valid) / (n - 1)), 2)


def _rmssd(ppi_list: list[float]) -> float | None:
    """RMSSD from successive PPI differences."""
    if len(ppi_list) < 2:
        return None
    diffs = [(ppi_list[i + 1] - ppi_list[i]) ** 2 for i in range(len(ppi_list) - 1)]
    return round(math.sqrt(sum(diffs) / len(diffs)), 2)


def _cv(vals: list[float]) -> float | None:
    """Coefficient of variation = SD/mean × 100."""
    mu = _avg(vals)
    sd = _std(vals)
    if mu and mu > 0 and sd is not None:
        return round(sd / mu * 100, 2)
    return None


# ── Fenster-Plausibilität (Artefakt vs. Befund) ───────────────────────────────
# ppi_raw ist bereits auf 350-2000 ms gefiltert (30-170 bpm), aber innerhalb
# dieser Grenze bleiben einzelne Ausreisser-Intervalle möglich (Signalabriss,
# Sensor-Kontaktverlust bei einer 30s-Wrist-/Brustgurt-Messung). Ein 30s-Fenster
# mit wenigen Schlägen reagiert auf solche Ausreisser viel empfindlicher als ein
# Mehrminuten-Fenster, weil ein einzelner Fehlwert bereits SD/RMSSD dominiert.
# Schwellen sind heuristisch/projektintern (wie der bestehende CV>10%-Marker
# oben) — kein klinisch validierter Cut-off, sondern eine Obergrenze dessen,
# was in dokumentierten Rhythmusklassen (Sinus, AFib) überhaupt vorkommt:
#   CV-RR: dokumentierte AFib-Kohorten liegen typischerweise bei ~15-30%,
#     vereinzelt bis ~40% (Task Force ESC/NASPE 1996; arrhythmia_utils.CV_AFIB_HIGH
#     = 15% als "hochgradig AFib-verdächtig" in diesem Projekt). Der theoretische
#     Maximalwert unter dem 350-2000-ms-Filter liegt bei ~70% (Alternieren
#     zwischen den Filtergrenzen) — physiologisch kommt das nicht vor.
#   RMSSD: gesunde Ruhewerte ~20-100 ms (Task Force 1996); auch in kardial
#     vorbelasteten Kohorten selten > 150-200 ms.
# Ein Fenster oberhalb dieser Grenzen wird als artefaktverdächtig markiert statt
# als Rhythmus-Befund gedruckt (siehe section_ppi_analysis / @limits).
_CV_IMPLAUSIBLE_PCT   = 50.0   # CV-RR oberhalb: artefaktverdächtig
_RMSSD_IMPLAUSIBLE_MS = 200.0  # RMSSD oberhalb: artefaktverdächtig


def _artifact_suspect(cv_pct: float | None, rmssd_ms: float | None) -> bool:
    """True wenn CV-RR oder RMSSD eines PPI-Fensters außerhalb plausibler Grenzen liegt.

    Siehe Kommentar über _CV_IMPLAUSIBLE_PCT für die Begründung der Schwellen.
    """
    if cv_pct is not None and cv_pct > _CV_IMPLAUSIBLE_PCT:
        return True
    if rmssd_ms is not None and rmssd_ms > _RMSSD_IMPLAUSIBLE_MS:
        return True
    return False


# ── Data loading ──────────────────────────────────────────────────────────────

def load_ecg_sessions(conn: sqlite3.Connection, d_from: str, d_to: str) -> list[dict]:
    """Load ecg_sessions within date range."""
    if not _table_exists(conn, "ecg_sessions"):
        return []
    cols = _verify_columns(conn, "ecg_sessions")
    # Build SELECT based on available columns
    select_cols = ["datetime", "classification", "duration_s", "device_id", "person"]
    if "symptoms" in cols:
        select_cols.insert(2, "symptoms")
    if "notes" in cols:
        select_cols.append("notes")
    try:
        rows = conn.execute(
            f"SELECT {', '.join(select_cols)} FROM ecg_sessions "
            f"WHERE DATE(datetime) >= ? AND DATE(datetime) <= ? "
            "ORDER BY datetime",
            (d_from, d_to),
        ).fetchall()
        result = []
        dropped = 0
        for row in rows:
            d = dict(zip(select_cols, row))
            if d.get("device_id") and not is_device_active(d["device_id"], d["datetime"]):
                dropped += 1
                continue
            d["cls"] = _norm_cls(d.get("classification", ""))
            # Parse datetime
            try:
                d["dt"] = datetime.strptime(d["datetime"][:19], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                d["dt"] = None
            result.append(d)
        if dropped:
            print(t(f"  ⚠ {dropped} ECG-Session(s) außerhalb der Geräte-Trageperiode laut registry.json übersprungen",
                    f"  ⚠ {dropped} ECG session(s) outside the device's registry.json wear period skipped"))
        return result
    except Exception as e:
        print(t(f"Fehler beim Laden von ecg_sessions: {e}",
                f"Error loading ecg_sessions: {e}"))
        return []


def load_ppi_window(
    conn: sqlite3.Connection, ts_start: str, duration_s: float = 30.0
) -> list[float]:
    """Load pulse_ms values from ppi_raw within [ts_start, ts_start + duration_s + 30s buffer].

    Uses GROUP BY datetime to deduplicate identical beats recorded by multiple
    concurrent Polar devices (e.g. H10 + V3 streaming the same PPI interval).
    Physiological filter: 350–2000 ms (30–170 bpm).
    NEVER loads without WHERE clause on datetime.
    """
    if not _table_exists(conn, "ppi_raw"):
        return []
    try:
        dt_start = datetime.strptime(ts_start[:19], "%Y-%m-%dT%H:%M:%S")
        # window = session duration + 30 s buffer for beat boundary alignment
        window_s = duration_s + 30.0
        dt_end = dt_start + timedelta(seconds=window_s)
        ts_end = dt_end.strftime("%Y-%m-%dT%H:%M:%S")
        rows = conn.execute(
            "SELECT AVG(pulse_ms) FROM ppi_raw "
            "WHERE datetime BETWEEN ? AND ? "
            "AND pulse_ms >= 350 AND pulse_ms <= 2000 "
            "GROUP BY datetime "
            "ORDER BY datetime",
            (ts_start, ts_end),
        ).fetchall()
        return [r[0] for r in rows if r[0] is not None]
    except Exception:
        return []


def load_arrhythmia_episodes(conn: sqlite3.Connection, d_from: str, d_to: str) -> list[tuple]:
    """Load arrhythmie_episoden rows within the date range."""
    if not _table_exists(conn, "arrhythmie_episoden"):
        return []
    try:
        return conn.execute(
            "SELECT episode_start, episode_end, dauer_min, cv_max, cv_mean, hr_mean, time_of_day "
            "FROM arrhythmie_episoden "
            "WHERE DATE(episode_start) >= ? AND DATE(episode_start) <= ? "
            "ORDER BY episode_start",
            (d_from, d_to),
        ).fetchall()
    except Exception:
        return []


def load_hrv(conn: sqlite3.Connection, d_from: str, d_to: str) -> dict[str, float]:
    """Load polar_nightly_hrv, return dict {date_str: rmssd_ms}."""
    if not _table_exists(conn, "polar_nightly_hrv"):
        return {}
    try:
        rows = conn.execute(
            "SELECT date, rmssd_ms FROM polar_nightly_hrv "
            "WHERE date >= ? AND date <= ? AND rmssd_ms IS NOT NULL AND rmssd_ms > 0 "
            "ORDER BY date",
            (d_from, d_to),
        ).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


# ── Section 1: ECG overview ───────────────────────────────────────────────────

def section_overview(sessions: list[dict], d_from: str, d_to: str) -> list[str]:
    n = len(sessions)
    if n == 0:
        return [t("Keine EKG-Sessions im gewählten Zeitraum.", "No ECG sessions in selected period.")]

    lines = [
        t(f"## 1. EKG-Übersicht  ({d_from} – {d_to})\n",
          f"## 1. ECG Overview  ({d_from} – {d_to})\n"),
        t(f"Gesamtzahl Sessions: **{n}**", f"Total sessions: **{n}**"),
    ]

    # Date range
    dts = [s["dt"] for s in sessions if s["dt"]]
    if dts:
        lines.append(t(
            f"Zeitraum:    {min(dts).strftime('%Y-%m-%d')} – {max(dts).strftime('%Y-%m-%d')}",
            f"Date range:  {min(dts).strftime('%Y-%m-%d')} – {max(dts).strftime('%Y-%m-%d')}",
        ))

    # Classification distribution
    by_cls: dict[str, int] = defaultdict(int)
    for s in sessions:
        by_cls[s["cls"]] += 1

    lines.append("")
    lines.append(t("### Klassifikationsverteilung", "### Classification distribution"))
    for cls in ["sinus_rhythm", "afib", "high_hr", "inconclusive"]:
        cnt = by_cls.get(cls, 0)
        pct = round(cnt / n * 100, 1)
        bar = "█" * int(pct / 5)
        lines.append(f"  {_cls_label(cls):<35} {cnt:>3} ({pct:>5.1f}%)  {bar}")

    if _UNMAPPED_CLS:
        # Nicht stillschweigend als "uneindeutig" verbuchen — sonst erscheinen
        # bewertbare Befunde als nicht bewertbar.
        lines.append("")
        lines.append(t(
            f"  ⚠ Unbekannte Klassifikationswerte, als uneindeutig gezaehlt: "
            f"{', '.join(sorted(_UNMAPPED_CLS))}. Sie gehoeren in _CLS_MAP.",
            f"  ⚠ Unknown classification values, counted as inconclusive: "
            f"{', '.join(sorted(_UNMAPPED_CLS))}. They belong in _CLS_MAP."))

    # Sessions per month
    by_month: dict[str, int] = defaultdict(int)
    for s in sessions:
        if s["dt"]:
            by_month[s["dt"].strftime("%Y-%m")] += 1
    lines.append("")
    lines.append(t("### Sessions pro Monat", "### Sessions per month"))
    for ym in sorted(by_month):
        lines.append(f"  {ym}  {by_month[ym]:>3}")

    # Device
    by_dev: dict[str, int] = defaultdict(int)
    for s in sessions:
        dev = s.get("device_id") or "unknown"
        by_dev[dev] += 1
    lines.append("")
    lines.append(t("### Geräte", "### Devices"))
    for dev, cnt in sorted(by_dev.items(), key=lambda x: -x[1]):
        lines.append(f"  {dev:<25} {cnt:>3}")

    return lines


# ── Section 2: AFib sessions detail ──────────────────────────────────────────

_WEEKDAY_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
_WEEKDAY_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _time_of_day_label(hour: int) -> str:
    if 6 <= hour < 12:
        return t("Morgen (06–12h)", "Morning (06–12h)")
    if 12 <= hour < 18:
        return t("Nachmittag (12–18h)", "Afternoon (12–18h)")
    if 18 <= hour < 24:
        return t("Abend (18–24h)", "Evening (18–24h)")
    return t("Nacht (00–06h)", "Night (00–06h)")


def section_afib_detail(
    sessions: list[dict],
    arrhythmia: list[tuple],
) -> list[str]:
    afib_sessions = [s for s in sessions if s["cls"] == "afib"]
    n = len(afib_sessions)

    lines = [t("## 2. AFib-Sessions im Detail", "## 2. AFib Sessions Detail"), ""]
    if n == 0:
        lines.append(t("Keine AFib-Sessions im Zeitraum.", "No AFib sessions in period."))
        return lines

    lines.append(t(f"Anzahl AFib-EKGs: **{n}**\n", f"AFib ECG count: **{n}**\n"))

    # Episode dates for cross-reference
    arrhythmia_dates: set[str] = set()
    for ep in arrhythmia:
        arrhythmia_dates.add(ep[0][:10])

    prev_dt = None
    for i, s in enumerate(afib_sessions, 1):
        dt = s["dt"]
        date_str = dt.strftime("%Y-%m-%d") if dt else "?"
        time_str = dt.strftime("%H:%M") if dt else "?"
        weekday = (
            t(_WEEKDAY_DE[dt.weekday()], _WEEKDAY_EN[dt.weekday()])
            if dt else "?"
        )
        tod = _time_of_day_label(dt.hour) if dt else "?"
        dur = s.get("duration_s") or 30.0

        # Inter-event interval
        gap_str = "—"
        if prev_dt and dt:
            gap_h = round((dt - prev_dt).total_seconds() / 3600, 1)
            gap_str = f"{gap_h} h"
        prev_dt = dt

        # Arrhythmia episodes on same day (±1 day)
        epi_context = []
        if dt:
            for offset in (-1, 0, 1):
                chk = (dt + timedelta(days=offset)).strftime("%Y-%m-%d")
                if chk in arrhythmia_dates:
                    epi_context.append(f"{chk} ({'+0d' if offset == 0 else f'{offset:+d}d'})")

        notes = s.get("symptoms") or s.get("notes") or ""

        lines.append(f"  AFib #{i}: {date_str} {time_str}  [{weekday}]  {tod}")
        lines.append(
            t(f"           Dauer: {dur:.0f}s  |  Abstand zur letzten AFib: {gap_str}",
              f"           Duration: {dur:.0f}s  |  Gap since last AFib: {gap_str}")
        )
        if epi_context:
            lines.append(
                t(f"           Arrhythmie-Episoden nahe diesem Tag: {', '.join(epi_context)}",
                  f"           Arrhythmia episodes near this date: {', '.join(epi_context)}")
            )
        if notes:
            lines.append(t(f"           Notizen: {notes}", f"           Notes: {notes}"))
        lines.append("")

    # Cluster: multiple AFib within 24 h
    cluster_days: dict[str, int] = defaultdict(int)
    for s in afib_sessions:
        if s["dt"]:
            cluster_days[s["dt"].strftime("%Y-%m-%d")] += 1
    days_multi = {d: c for d, c in cluster_days.items() if c > 1}
    if days_multi:
        lines.append(t("### AFib-Cluster (mehrere EKGs am gleichen Tag)",
                       "### AFib clusters (multiple ECGs on same day)"))
        for d, c in sorted(days_multi.items()):
            lines.append(f"  {d}: {c} AFib-EKGs")
        lines.append("")

    return lines


# ── Section 3: High HR sessions ───────────────────────────────────────────────

def section_high_hr(sessions: list[dict]) -> list[str]:
    hr_sessions = [s for s in sessions if s["cls"] == "high_hr"]
    n = len(hr_sessions)

    lines = [t("## 3. Hohe-Herzfrequenz-Sessions", "## 3. High HR Sessions"), ""]
    if n == 0:
        lines.append(t("Keine High-HR-Sessions.", "No high HR sessions."))
        return lines

    lines.append(t(f"Anzahl: {n}\n", f"Count: {n}\n"))

    # Time-of-day distribution
    tod_counts: dict[str, int] = defaultdict(int)
    for s in hr_sessions:
        if s["dt"]:
            tod_counts[_time_of_day_label(s["dt"].hour)] += 1

    lines.append(t("### Tageszeit-Verteilung", "### Time-of-day distribution"))
    for label, cnt in sorted(tod_counts.items(), key=lambda x: -x[1]):
        pct = round(cnt / n * 100, 1)
        lines.append(f"  {label:<30} {cnt:>3} ({pct:.1f}%)")

    # Monthly distribution
    by_month: dict[str, int] = defaultdict(int)
    for s in hr_sessions:
        if s["dt"]:
            by_month[s["dt"].strftime("%Y-%m")] += 1
    lines.append("")
    lines.append(t("### Pro Monat", "### Per month"))
    for ym in sorted(by_month):
        lines.append(f"  {ym}: {by_month[ym]}")

    # Note about HR estimation from waveform
    lines.append("")
    lines.append(t(
        "  Hinweis: Herzfrequenz aus Rohwaveform (512 Hz, 30 s) nicht numerisch gespeichert —"
        " Apple Watch klassifiziert direkt.",
        "  Note: HR value not stored numerically — Apple Watch classifies directly from waveform.",
    ))

    return lines


# ── Section 4: Time-of-day clustering ────────────────────────────────────────

def section_time_of_day(sessions: list[dict]) -> list[str]:
    lines = [t("## 4. Tageszeit-Clustering (alle Sessions)",
               "## 4. Time-of-day clustering (all sessions)"), ""]

    hour_all: list[int] = []
    hour_afib: list[int] = []

    for s in sessions:
        if s["dt"]:
            h = s["dt"].hour
            hour_all.append(h)
            if s["cls"] == "afib":
                hour_afib.append(h)

    if not hour_all:
        lines.append(t("Keine Daten.", "No data."))
        return lines

    # Slot counts
    slots = {
        t("Morgen   (06–12h)", "Morning   (06–12h)"): (6, 12),
        t("Nachmitt.(12–18h)", "Afternoon (12–18h)"): (12, 18),
        t("Abend    (18–24h)", "Evening   (18–24h)"): (18, 24),
        t("Nacht    (00–06h)", "Night     (00–06h)"): (0, 6),
    }
    n = len(hour_all)
    lines.append(t("### Zeitfenster-Übersicht (alle EKGs)",
                   "### Time window overview (all ECGs)"))
    for label, (lo, hi) in slots.items():
        cnt = sum(1 for h in hour_all if lo <= h < hi)
        afib_cnt = sum(1 for h in hour_afib if lo <= h < hi)
        pct = round(cnt / n * 100, 1)
        afib_tag = f"  [AFib: {afib_cnt}]" if afib_cnt else ""
        bar = "█" * int(pct / 5)
        lines.append(f"  {label:<30} {cnt:>3} ({pct:.1f}%){afib_tag}  {bar}")

    # Hour histogram (0–23)
    lines.append("")
    lines.append(t("### Stunden-Histogramm (alle EKGs / AFib)", "### Hourly histogram (all ECGs / AFib)"))
    hour_cnts = [hour_all.count(h) for h in range(24)]
    afib_cnts = [hour_afib.count(h) for h in range(24)]
    max_cnt = max(hour_cnts) if hour_cnts else 1
    for h in range(24):
        bar_len = int(hour_cnts[h] / max_cnt * 20)
        afib_marker = " ▲" * afib_cnts[h] if afib_cnts[h] else ""
        lines.append(f"  {h:02d}h  {'█' * bar_len:<20} {hour_cnts[h]:>2}{afib_marker}")

    return lines


# ── Section 5: PPI analysis for ECG windows ──────────────────────────────────

def section_ppi_analysis(
    sessions: list[dict], conn: sqlite3.Connection
) -> tuple[list[str], list | None, list | None]:
    """
    Returns (text_lines, afib_ppis_combined, sinus_ppis_combined)
    for use in the plot. Returns None if no data.
    """
    lines = [t("## 5. PPI-Analyse für EKG-Zeitfenster",
               "## 5. PPI analysis for ECG windows"), ""]

    afib_sessions = [s for s in sessions if s["cls"] == "afib"]
    sinus_sessions = [s for s in sessions if s["cls"] == "sinus_rhythm"]

    lines.append(t(
        "Hinweis: ppi_raw (pulse_ms) wird im Zeitfenster [ts_start, ts_start + duration_s + 30 s] "
        "ausgelesen (Puffer für Beat-Grenzen). Duplikate durch gleichzeitige H10/V3-Aufnahmen "
        "werden via GROUP BY datetime dedupliziert. Physiologischer Filter: 350–2000 ms.",
        "Note: ppi_raw (pulse_ms) is read in window [ts_start, ts_start + duration_s + 30 s] "
        "(buffer for beat boundaries). Duplicates from concurrent H10/V3 recordings are "
        "deduplicated via GROUP BY datetime. Physiological filter: 350–2000 ms.",
    ))
    lines.append("")
    # (b) Die Geräteklassifikation (Abschnitt 1) und die folgenden PPI-Fenster-Kennzahlen
    # beruhen auf unterschiedlichen Grundlagen — ohne diese Einordnung liest sich ein
    # hohes CV/RMSSD in einem als "Sinusrhythmus" klassifizierten EKG wie ein Widerspruch.
    lines.append(t(
        "Einordnung: Die Geräteklassifikation in Abschnitt 1 (Sinusrhythmus/AFib/…) stammt aus der "
        "Analyse der 30s-EKG-Rohwellenform (elektrisches Signal, FDA-freigegebener Watch-Algorithmus, "
        "siehe @limits). Die CV-RR/RMSSD-Kennzahlen unten stammen dagegen aus ppi_raw — optischen "
        "Puls-Puls-Intervallen eines zeitlich nahen, aber unabhängigen Fensters (anderer Sensor, "
        "anderes Messprinzip). Ein hohes CV/RMSSD in diesem Abschnitt widerspricht der "
        "EKG-Klassifikation NICHT automatisch: es kann echte kurzfristige Irregularität abbilden "
        "oder — bei einer 30s-Wrist-/Brustgurt-Messung häufiger — ein Bewegungs-/Kontaktartefakt der "
        "optischen Messung sein. Fenster außerhalb physiologisch plausibler Grenzen werden unten "
        "als artefaktverdächtig markiert statt als Befund gedruckt.",
        "Framing: The device classification in Section 1 (sinus rhythm/AFib/…) comes from analysis "
        "of the 30s raw ECG waveform (electrical signal, FDA-cleared Watch algorithm, see @limits). "
        "The CV-RR/RMSSD metrics below instead come from ppi_raw — optical pulse-to-pulse intervals "
        "from a temporally close but independent window (different sensor, different measurement "
        "principle). A high CV/RMSSD in this section does NOT automatically contradict the ECG "
        "classification: it may reflect genuine short-term irregularity, or — more commonly for a "
        "30s wrist/chest-strap recording — a motion/contact artifact of the optical measurement. "
        "Windows outside physiologically plausible bounds are flagged as artifact-suspect below "
        "instead of being printed as a finding.",
    ))
    lines.append("")

    def _analyse_session_ppi(s: dict, label: str) -> dict | None:
        ppis = load_ppi_window(conn, s["datetime"], s.get("duration_s") or 30.0)
        if not ppis:
            return None
        mu = _avg(ppis)
        sd = _std(ppis)
        cv = _cv(ppis)
        rmssd = _rmssd(ppis)
        return {
            "label": label,
            "datetime": s["datetime"],
            "n": len(ppis),
            "mean_ms": mu,
            "sd_ms": sd,
            "rmssd_ms": rmssd,
            "cv_pct": cv,
            "ppis": ppis,
            # (a) Plausibilitätsprüfung: Kennzahlen außerhalb physiologisch möglicher
            # Bereiche sind artefaktverdächtig statt Befund — s. _artifact_suspect().
            "artifact_suspect": _artifact_suspect(cv, rmssd),
        }

    afib_results = []
    for s in afib_sessions:
        r = _analyse_session_ppi(s, s["datetime"])
        if r:
            afib_results.append(r)

    sinus_results = []
    for s in sinus_sessions[:10]:  # limit to first 10 to keep runtime manageable
        r = _analyse_session_ppi(s, s["datetime"])
        if r:
            sinus_results.append(r)
            if len(sinus_results) >= 5:
                break  # 5 sinus windows enough for comparison

    if not afib_results and not sinus_results:
        lines.append(t(
            "Keine ppi_raw-Daten im Zeitfenster der EKG-Sessions verfügbar "
            "(Datenbank-Coverage endet vor diesen Aufnahmen).",
            "No ppi_raw data available in ECG session windows "
            "(database coverage ends before these recordings).",
        ))
        return lines, None, None

    def _fmt_result(r: dict) -> str:
        if r["artifact_suspect"]:
            # (a) Außerhalb physiologisch plausibler Grenzen (_CV_IMPLAUSIBLE_PCT /
            # _RMSSD_IMPLAUSIBLE_MS) — als Artefakt markiert, NICHT als Rhythmus-Befund
            # gedruckt. Kein label_finding(): das ist keine kommunizierte Assoziation,
            # sondern eine Datenqualitäts-Einstufung.
            cv_flag = t(
                " ← ⚠ artefaktverdächtig (außerhalb physiolog. plausibler Grenzen, s. @limits)",
                " ← ⚠ artifact-suspect (outside physiologically plausible range, see @limits)",
            )
        elif r["cv_pct"] and r["cv_pct"] > 10:
            # CV > 10% als AFib-Indikator: heuristischer Schwellenwert, kein publizierter
            # Grenzwert für Consumer-PPI-Daten. AFib ist durch irreguläre RR-Abstände
            # charakterisiert (Task Force ESC 1996, doi:10.1161/01.CIR.93.5.1043);
            # die 10%-Grenze ist projektintern → als "suspected" gekennzeichnet, nicht
            # als bestätigter Befund.
            de, en = label_finding(
                "CV-RR>10%: AFib-typisch (heuristischer Schwellenwert)",
                "CV-RR>10%: AFib-typical (heuristic threshold)",
                "suspected",
            )
            cv_flag = f" ← {t(de, en)}"
        else:
            cv_flag = ""
        return (
            f"  {r['datetime'][:16]}  n={r['n']:>3}  "
            f"mean={r['mean_ms'] or '?':>6.1f} ms  "
            f"SD={r['sd_ms'] or '?':>5.1f}  "
            f"RMSSD={r['rmssd_ms'] or '?':>5.1f}  "
            f"CV={r['cv_pct'] or '?':>5.1f}%{cv_flag}"
        )

    # (a) Nur plausible Fenster fließen in Mittelwerte/Vergleiche ein — ein einzelnes
    # artefaktverdächtiges Fenster darf die aggregierte Aussage nicht dominieren.
    afib_plausible  = [r for r in afib_results  if not r["artifact_suspect"]]
    sinus_plausible = [r for r in sinus_results if not r["artifact_suspect"]]
    n_afib_artifact  = len(afib_results) - len(afib_plausible)
    n_sinus_artifact = len(sinus_results) - len(sinus_plausible)

    def _artifact_note(n: int) -> str:
        return t(
            f"  ⚠ {n} Fenster als artefaktverdächtig ausgeschlossen (s. Markierung oben).",
            f"  ⚠ {n} window(s) excluded as artifact-suspect (see marker above).",
        )

    if afib_results:
        lines.append(t("### AFib-Zeitfenster", "### AFib windows"))
        for r in afib_results:
            lines.append(_fmt_result(r))
        afib_cv = [r["cv_pct"] for r in afib_plausible if r["cv_pct"] is not None]
        if afib_cv:
            lines.append(t(
                f"\n  Ø CV AFib-Fenster (plausible Fenster): {round(sum(afib_cv)/len(afib_cv), 2)}%  "
                f"(Grenze: 10% = AFib-typisch)",
                f"\n  Mean CV AFib windows (plausible windows): {round(sum(afib_cv)/len(afib_cv), 2)}%  "
                f"(threshold: 10% = AFib-typical)",
            ))
        if n_afib_artifact:
            lines.append(_artifact_note(n_afib_artifact))
        lines.append("")

    if sinus_results:
        lines.append(t("### Sinusrhythmus-Zeitfenster (Vergleich)", "### Sinus rhythm windows (comparison)"))
        for r in sinus_results:
            lines.append(_fmt_result(r))
        sinus_cv = [r["cv_pct"] for r in sinus_plausible if r["cv_pct"] is not None]
        if sinus_cv:
            lines.append(t(
                f"\n  Ø CV Sinus-Fenster (plausible Fenster): {round(sum(sinus_cv)/len(sinus_cv), 2)}%",
                f"\n  Mean CV sinus windows (plausible windows): {round(sum(sinus_cv)/len(sinus_cv), 2)}%",
            ))
        if n_sinus_artifact:
            lines.append(_artifact_note(n_sinus_artifact))
        lines.append("")

    # Comparison summary — nur aus plausiblen Fenstern, sonst kann ein einzelnes
    # Artefakt-Fenster den Δ-Wert dominieren.
    if afib_plausible and sinus_plausible:
        afib_cv_mean = _avg([r["cv_pct"] for r in afib_plausible if r["cv_pct"] is not None])
        sinus_cv_mean = _avg([r["cv_pct"] for r in sinus_plausible if r["cv_pct"] is not None])
        if afib_cv_mean is not None and sinus_cv_mean is not None:
            delta = round(afib_cv_mean - sinus_cv_mean, 2)
            if delta > 0:
                de, en = label_finding(
                    f"AFib-Fenster zeigen höhere Irregularität als Sinus-Fenster (ΔCV={delta:+.2f}%, "
                    f"nur plausible Fenster)",
                    f"AFib windows show higher irregularity than sinus windows (ΔCV={delta:+.2f}%, "
                    f"plausible windows only)",
                    "suspected",
                )
                lines.append(t(f"  {de}", f"  {en}"))
            else:
                lines.append(t(
                    f"  Δ CV (AFib − Sinus, plausible Fenster): {delta:+.2f}%  (kein klarer Unterschied)",
                    f"  Δ CV (AFib − sinus, plausible windows): {delta:+.2f}%  (no clear difference)",
                ))

    # Data quality note if sinus CV is unexpectedly high (activity artifacts in ppi_raw)
    if sinus_plausible:
        sinus_cv_vals = [r["cv_pct"] for r in sinus_plausible if r["cv_pct"] is not None]
        if sinus_cv_vals and _avg(sinus_cv_vals) and _avg(sinus_cv_vals) > 15:  # type: ignore[operator]
            lines.append(t(
                "\n  Datenqualitäts-Hinweis: Hohe CV in (plausiblen) Sinus-Fenstern deutet auf Polar-"
                "Artefakte hin (Bewegung, schlechter Kontakt). ppi_raw-Fenster fallen zeitlich "
                "evtl. in Aktivitätsphasen. Interpretation mit Vorsicht.",
                "\n  Data quality note: High CV in (plausible) sinus windows suggests Polar artefacts "
                "(motion, poor contact). ppi_raw windows may coincide with activity. "
                "Interpret with caution.",
            ))

    afib_ppis = [p for r in afib_results for p in r["ppis"]] if afib_results else None
    sinus_ppis = [p for r in sinus_results for p in r["ppis"]] if sinus_results else None

    return lines, afib_ppis, sinus_ppis


# ── Section 6: HRV on ECG days ───────────────────────────────────────────────

def section_hrv_ecg_days(sessions: list[dict], hrv_dict: dict[str, float]) -> list[str]:
    lines = [t("## 6. HRV an EKG-Tagen", "## 6. HRV on ECG days"), ""]

    if not hrv_dict:
        lines.append(t(
            "Keine polar_nightly_hrv-Daten im Zeitraum.",
            "No polar_nightly_hrv data in the period.",
        ))
        return lines

    ecg_dates: set[str] = set()
    afib_dates: set[str] = set()
    for s in sessions:
        if s["dt"]:
            d = s["dt"].strftime("%Y-%m-%d")
            ecg_dates.add(d)
            if s["cls"] == "afib":
                afib_dates.add(d)

    hrv_ecg, hrv_no_ecg, hrv_afib = [], [], []
    for date_str, rmssd in hrv_dict.items():
        if date_str in afib_dates:
            hrv_afib.append(rmssd)
        if date_str in ecg_dates:
            hrv_ecg.append(rmssd)
        else:
            hrv_no_ecg.append(rmssd)

    def _fmt(vals: list) -> str:
        if not vals:
            return t("keine Daten", "no data")
        mu = _avg(vals)
        sd = _std(vals)
        sd_str = f"±{sd}" if sd is not None else ""
        return f"{mu} {sd_str} ms  (n={len(vals)})"

    lines.append(t("### Nacht-RMSSD", "### Nightly RMSSD"))
    lines.append(t(f"  EKG-Tage:            {_fmt(hrv_ecg)}",
                   f"  ECG days:            {_fmt(hrv_ecg)}"))
    lines.append(t(f"  EKG-freie Tage:      {_fmt(hrv_no_ecg)}",
                   f"  Non-ECG days:        {_fmt(hrv_no_ecg)}"))
    lines.append(t(f"  AFib-EKG-Tage:       {_fmt(hrv_afib)}",
                   f"  AFib ECG days:       {_fmt(hrv_afib)}"))

    if hrv_ecg and hrv_no_ecg:
        mu_ecg = _avg(hrv_ecg)
        mu_no_ecg = _avg(hrv_no_ecg)
        if mu_ecg is not None and mu_no_ecg is not None:
            delta = round(mu_ecg - mu_no_ecg, 2)
            lines.append(t(
                f"\n  Δ EKG-Tage vs. EKG-frei: {delta:+.2f} ms",
                f"\n  Δ ECG days vs. no-ECG: {delta:+.2f} ms",
            ))

    if len(hrv_ecg) < 3 or len(hrv_no_ecg) < 3:
        lines.append(t(
            "\n  WARNUNG: Zu wenige Datenpunkte für belastbare statistische Aussage.",
            "\n  WARNING: Too few data points for a reliable statistical statement.",
        ))

    return lines


# ── Section 7: Arrhythmia episodes context ───────────────────────────────────

def section_arrhythmia_context(
    sessions: list[dict], arrhythmia: list[tuple]
) -> list[str]:
    lines = [t("## 7. Arrhythmie-Episoden-Kontext um AFib-EKG-Tage",
               "## 7. Arrhythmia episode context around AFib ECG days"), ""]

    afib_sessions = [s for s in sessions if s["cls"] == "afib"]
    if not afib_sessions:
        lines.append(t("Keine AFib-Sessions.", "No AFib sessions."))
        return lines
    if not arrhythmia:
        lines.append(t("Keine arrhythmie_episoden im Zeitraum.", "No arrhythmia episodes in period."))
        return lines

    # Build lookup by date
    epi_by_date: dict[str, list[tuple]] = defaultdict(list)
    for ep in arrhythmia:
        epi_by_date[ep[0][:10]].append(ep)

    for s in afib_sessions:
        if not s["dt"]:
            continue
        lines.append(f"  AFib-EKG: {s['datetime'][:16]}")

        found_any = False
        for offset in (-1, 0, 1):
            chk = (s["dt"] + timedelta(days=offset)).strftime("%Y-%m-%d")
            eps = epi_by_date.get(chk, [])
            if eps:
                found_any = True
                label = (
                    t("selber Tag", "same day") if offset == 0
                    else t(f"Vortag ({chk})", f"day before ({chk})") if offset == -1
                    else t(f"Folgetag ({chk})", f"next day ({chk})")
                )
                dauer_sum = sum(ep[2] for ep in eps if ep[2])
                cv_vals = [ep[3] for ep in eps if ep[3]]
                hr_vals = [ep[5] for ep in eps if ep[5]]
                cv_str = f"  CV-max={max(cv_vals):.3f}" if cv_vals else ""
                hr_str = f"  HR={_avg(hr_vals)} bpm" if hr_vals else ""
                lines.append(
                    t(f"    → {label}: {len(eps)} Episoden, {dauer_sum:.0f} min gesamt{cv_str}{hr_str}",
                      f"    → {label}: {len(eps)} episodes, {dauer_sum:.0f} min total{cv_str}{hr_str}")
                )

        if not found_any:
            lines.append(t(
                "    → Keine Arrhythmie-Episoden ±1 Tag um diesen EKG-Termin.",
                "    → No arrhythmia episodes within ±1 day of this ECG.",
            ))
        lines.append("")

    # Overall summary: episode burden on AFib-ECG days vs. other days
    afib_ecg_dates = {s["dt"].strftime("%Y-%m-%d") for s in afib_sessions if s["dt"]}
    # Include ±1 day
    afib_window_dates: set[str] = set()
    for d in afib_ecg_dates:
        dt = datetime.strptime(d, "%Y-%m-%d")
        for off in (-1, 0, 1):
            afib_window_dates.add((dt + timedelta(days=off)).strftime("%Y-%m-%d"))

    epi_near_afib = [ep for ep in arrhythmia if ep[0][:10] in afib_window_dates]
    epi_far = [ep for ep in arrhythmia if ep[0][:10] not in afib_window_dates]

    if epi_near_afib or epi_far:
        dauer_near = [ep[2] for ep in epi_near_afib if ep[2]]
        dauer_far = [ep[2] for ep in epi_far if ep[2]]
        lines.append(t(
            f"  Episoden nahe AFib-EKG (±1d): {len(epi_near_afib)}  "
            f"| Ø Dauer: {_avg(dauer_near)} min",
            f"  Episodes near AFib ECG (±1d): {len(epi_near_afib)}  "
            f"| Mean duration: {_avg(dauer_near)} min",
        ))
        lines.append(t(
            f"  Episoden an anderen Tagen:     {len(epi_far)}  "
            f"| Ø Dauer: {_avg(dauer_far)} min",
            f"  Episodes on other days:        {len(epi_far)}  "
            f"| Mean duration: {_avg(dauer_far)} min",
        ))

    return lines


# ── Report assembly ───────────────────────────────────────────────────────────

def build_report(
    sessions: list[dict],
    arrhythmia: list[tuple],
    hrv_dict: dict[str, float],
    conn: sqlite3.Connection,
    d_from: str,
    d_to: str,
) -> tuple[str, list | None, list | None]:
    """Assemble full text report. Returns (report_text, afib_ppis, sinus_ppis)."""
    blocks = []

    blocks.extend(section_overview(sessions, d_from, d_to))
    blocks.append("")
    blocks.extend(section_afib_detail(sessions, arrhythmia))
    blocks.append("")
    blocks.extend(section_high_hr(sessions))
    blocks.append("")
    blocks.extend(section_time_of_day(sessions))
    blocks.append("")
    ppi_lines, afib_ppis, sinus_ppis = section_ppi_analysis(sessions, conn)
    blocks.extend(ppi_lines)
    blocks.append("")
    blocks.extend(section_hrv_ecg_days(sessions, hrv_dict))
    blocks.append("")
    blocks.extend(section_arrhythmia_context(sessions, arrhythmia))

    return "\n".join(blocks), afib_ppis, sinus_ppis


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(
    sessions: list[dict],
    afib_ppis: list | None,
    sinus_ppis: list | None,
    arrhythmia: list[tuple],
    d_from: str,
    d_to: str,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        fig, axes = plt.subplots(3, 1, figsize=(14, 12), facecolor=BG)
        fig.suptitle(
            t(f"EKG-Detailanalyse  {d_from} – {d_to}",
              f"ECG Detail Analysis  {d_from} – {d_to}"),
            color=TXT, fontsize=13, fontweight="bold",
        )
        for ax in axes:
            ax.set_facecolor(AXES)
            ax.tick_params(colors=TICK, labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor(SPINE)

        # ── Panel 1: ECG sessions timeline (scatter, colored by classification)
        ax1 = axes[0]
        cls_order = ["sinus_rhythm", "high_hr", "inconclusive", "afib"]
        for cls in cls_order:
            grp = [s for s in sessions if s["cls"] == cls and s["dt"]]
            if not grp:
                continue
            dts = [s["dt"] for s in grp]
            ys = [0.5] * len(dts)  # single y level
            ax1.scatter(
                dts, ys,
                color=COLOR_MAP[cls],
                s=80 if cls == "afib" else 40,
                alpha=0.9 if cls == "afib" else 0.65,
                zorder=4 if cls == "afib" else 3,
                label=_cls_label(cls),
                marker="D" if cls == "afib" else "o",
            )
        ax1.set_title(t("EKG-Sessions-Timeline (farbig nach Klassifikation)",
                        "ECG sessions timeline (colored by classification)"),
                      color=TXT, fontsize=10)
        ax1.set_yticks([])
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        fig.autofmt_xdate(rotation=30)
        legend = ax1.legend(fontsize=8, facecolor=AXES, labelcolor=TXT, loc="upper left")
        for txt in legend.get_texts():
            txt.set_color(TXT)

        # ── Panel 2: Hour-of-day histogram, all sessions + AFib overlay
        ax2 = axes[1]
        hours_all = [s["dt"].hour for s in sessions if s["dt"]]
        hours_afib = [s["dt"].hour for s in sessions if s["dt"] and s["cls"] == "afib"]
        bins = list(range(25))

        if hours_all:
            ax2.hist(hours_all, bins=bins, color="#74B9FF", alpha=0.65,
                     label=t("Alle EKGs", "All ECGs"), edgecolor=SPINE, linewidth=0.5)
        if hours_afib:
            ax2.hist(hours_afib, bins=bins, color="#FF4444", alpha=0.85,
                     label=t("AFib-EKGs", "AFib ECGs"), edgecolor="#CC0000", linewidth=0.5)

        ax2.set_xlabel(t("Stunde des Tages", "Hour of day"), color=TXT, fontsize=9)
        ax2.set_ylabel(t("Anzahl Sessions", "Session count"), color=TXT, fontsize=9)
        ax2.set_title(t("Tageszeit-Verteilung (blau=alle, rot=AFib)",
                        "Time-of-day distribution (blue=all, red=AFib)"),
                      color=TXT, fontsize=10)
        ax2.set_xticks(range(0, 25, 2))
        legend2 = ax2.legend(fontsize=8, facecolor=AXES)
        for txt in legend2.get_texts():
            txt.set_color(TXT)

        # ── Panel 3: PPI histogram (AFib vs sinus) or arrhythmia timeline
        ax3 = axes[2]
        if afib_ppis or sinus_ppis:
            bin_edges = list(range(300, 2001, 20))
            if sinus_ppis:
                ax3.hist(sinus_ppis, bins=bin_edges, color="#50FA7B", alpha=0.55,
                         label=t("Sinus PPI", "Sinus PPI"), edgecolor=SPINE, linewidth=0.3)
            if afib_ppis:
                ax3.hist(afib_ppis, bins=bin_edges, color="#FF4444", alpha=0.70,
                         label=t("AFib PPI", "AFib PPI"), edgecolor="#CC0000", linewidth=0.3)
            ax3.set_xlabel(t("PPI (ms)", "PPI (ms)"), color=TXT, fontsize=9)
            ax3.set_ylabel(t("Häufigkeit", "Count"), color=TXT, fontsize=9)
            ax3.set_title(
                t("PPI-Histogramm: AFib-Fenster vs. Sinus-Fenster (Bin=20 ms)",
                  "PPI histogram: AFib windows vs. sinus windows (bin=20 ms)"),
                color=TXT, fontsize=10,
            )
            ax3.set_xlim(300, 1800)
            legend3 = ax3.legend(fontsize=8, facecolor=AXES)
            for txt in legend3.get_texts():
                txt.set_color(TXT)
        else:
            # Fallback: arrhythmia episodes timeline
            if arrhythmia:
                try:
                    epi_dts = []
                    epi_durs = []
                    for ep in arrhythmia:
                        try:
                            epi_dts.append(datetime.strptime(ep[0][:16], "%Y-%m-%dT%H:%M"))
                            epi_durs.append(ep[2] or 0)
                        except Exception:
                            pass
                    if epi_dts:
                        ax3.bar(epi_dts, epi_durs, width=0.3, color="#E17055", alpha=0.7,
                                label=t("Arrhythmie-Episoden", "Arrhythmia episodes"))
                        ax3.set_ylabel(t("Dauer (min)", "Duration (min)"), color=TXT, fontsize=9)
                        ax3.set_title(
                            t("Arrhythmie-Episoden (Fallback: kein PPI-Overlap mit EKG-Fenstern)",
                              "Arrhythmia episodes (fallback: no PPI overlap with ECG windows)"),
                            color=TXT, fontsize=10,
                        )
                        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
                        legend4 = ax3.legend(fontsize=8, facecolor=AXES)
                        for txt in legend4.get_texts():
                            txt.set_color(TXT)
                except Exception as e:
                    ax3.text(0.5, 0.5, t(f"Plot-Fehler: {e}", f"Plot error: {e}"),
                             ha="center", va="center", color=TXT, transform=ax3.transAxes)
            else:
                ax3.text(
                    0.5, 0.5,
                    t("Keine PPI-Daten im EKG-Fenster und keine Arrhythmie-Episoden.",
                      "No PPI data in ECG window and no arrhythmia episodes."),
                    ha="center", va="center", color=TXT, transform=ax3.transAxes,
                )

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"ecg_detail_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor=BG)
        plt.close()
        print(t(f"Plot gespeichert: {path}", f"Plot saved: {path}"))
    except Exception as e:
        print(t(f"Plot fehlgeschlagen: {e}", f"Plot failed: {e}"))


# ── LLM ──────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1400)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save ──────────────────────────────────────────────────────────────────────

def _save(report: str, llm_text: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"ecg_detail_{ts}.md"
    content = t("# EKG-Detailanalyse\n\n", "# ECG Detail Analysis\n\n") + report + "\n"
    if llm_text:
        content += t("\n## Klinische Interpretation\n\n",
                     "\n## Clinical Interpretation\n\n") + llm_text + "\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=t(
            "Detaillierte EKG-Analyse — Apple Watch ECG Sessions",
            "Detailed ECG analysis — Apple Watch ECG sessions",
        )
    )
    parser.add_argument("--from", dest="date_from", default=cfg.data_start or "2000-01-01",
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to",   dest="date_to",   default=today,
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot", action="store_true",
                        help=t("Plots erzeugen und speichern", "Generate and save plots"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Interpretation überspringen", "Skip LLM interpretation"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    print(t(
        f"EKG-Detailanalyse  {args.date_from} → {args.date_to}",
        f"ECG detail analysis  {args.date_from} → {args.date_to}",
    ))
    print(t(f"Datenbank: {DB_PATH}", f"Database: {DB_PATH}"))

    conn = _conn()

    # Verify expected tables exist
    for tbl in ("ecg_sessions", "ecg_samples", "ppi_raw", "arrhythmie_episoden", "polar_nightly_hrv"):
        exists = _table_exists(conn, tbl)
        print(t(f"  Tabelle {tbl}: {'OK' if exists else 'NICHT GEFUNDEN'}",
                f"  Table {tbl}: {'OK' if exists else 'NOT FOUND'}"))

    sessions = load_ecg_sessions(conn, args.date_from, args.date_to)
    print(t(f"\nEKG-Sessions geladen: {len(sessions)}", f"\nECG sessions loaded: {len(sessions)}"))

    if not sessions:
        print(t("Keine EKG-Daten — Abbruch.", "No ECG data — aborting."))
        conn.close()
        return

    # Distribution summary
    by_cls: dict[str, int] = defaultdict(int)
    for s in sessions:
        by_cls[s["cls"]] += 1
    print(t("Verteilung:", "Distribution:"),
          "  ".join(f"{_cls_label(c)}={n}" for c, n in sorted(by_cls.items())))

    arrhythmia = load_arrhythmia_episodes(conn, args.date_from, args.date_to)
    hrv_dict   = load_hrv(conn, args.date_from, args.date_to)
    print(t(
        f"Arrhythmie-Episoden: {len(arrhythmia)}  |  HRV-Nächte: {len(hrv_dict)}",
        f"Arrhythmia episodes: {len(arrhythmia)}  |  HRV nights: {len(hrv_dict)}",
    ))

    report, afib_ppis, sinus_ppis = build_report(
        sessions, arrhythmia, hrv_dict, conn, args.date_from, args.date_to
    )
    conn.close()

    print("\n" + report)

    if args.plot:
        _plot(sessions, afib_ppis, sinus_ppis, arrhythmia, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
