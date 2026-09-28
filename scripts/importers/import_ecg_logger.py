#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
ECGLogger (Matti Mononen) → health.db

@tier        infrastructure
@purpose.de  Importiert EKG-Traces und RR-Intervalle aus ECGLogger-Exporten in die
             health.db. Ermöglicht Arrhythmie-Nachweis mit echtem EKG-Bild, QRS-
             Erkennung für präzise RR-Intervalle und AFib-Morphologie-Analyse.
@purpose.en  Imports ECG traces and RR intervals from ECGLogger exports into
             health.db. Enables arrhythmia detection with actual ECG images,
             QRS detection for precise RR intervals, and AFib morphology analysis.
@method.de   ECGLogger zeichnet mit Polar H7/H10 bei 130 Hz auf (7.69 ms/Sample).
             Unterstützte Formate: ECG-CSV (time_ms, ecg_mV, 130 Hz Rohsignal),
             RR-TXT (ein RR-Wert pro Zeile in ms), Kubios-HRM (Polar-kompatibel).
             Speicherung: ecg_logger_sessions (Session-Metadaten + QRS-Statistik),
             ecg_logger_ecg (rohe EKG-Samples für Plots/Arztberichte), ppi_raw
             (RR-Intervalle, source='ecg_logger') — alle drei jetzt mit der
             tatsächlich übergebenen person (CLI --person oder run()-Parameter,
             via resolve_person()), nicht mehr fest auf OWN_PERSON_ID verdrahtet.
             Bietet sowohl run(conn, data_path, lang, person) nach der Projekt-
             Konvention als auch die volle main()-CLI (--tags/--notes/--dry-run/
             --plot) — beide rufen dieselbe _import_files()-Kernschleife auf,
             keine doppelte Logik.
@method.en   ECGLogger records with Polar H7/H10 at 130 Hz (7.69 ms/sample).
             Supported formats: ECG-CSV (time_ms, ecg_mV, 130 Hz raw signal),
             RR-TXT (one RR value per line in ms), Kubios-HRM (Polar-compatible).
             Storage: ecg_logger_sessions (session metadata + QRS statistics),
             ecg_logger_ecg (raw ECG samples for plots/medical reports), ppi_raw
             (RR intervals, source='ecg_logger') — all three now use the actually
             passed-in person (CLI --person or the run() parameter, via
             resolve_person()) instead of being hardcoded to OWN_PERSON_ID.
             Provides both run(conn, data_path, lang, person) per the project
             convention and the full main() CLI (--tags/--notes/--dry-run/
             --plot) — both call the same _import_files() core loop, no
             duplicated logic.
@reads       ECGLogger Export (CSV/TXT, Polar H7/H10)
@writes      health.db (ecg_logger_sessions, ecg_logger_ecg, ppi_raw)
@limits.de   Keine Validierung der EKG-Datenqualität. Keine automatische
             Arrhythmie-Erkennung. Keine medizinische Bewertung aus EKG-Daten.
             Wichtig bei geteilten Geräten (z. B. Arztpraxis-Sensor für mehrere
             Personen): die Geräte-ID allein sagt nichts über die Person aus —
             --person muss dann bei jedem Lauf explizit gesetzt werden, sonst
             greift der Config-Standard (eigene Person).

@relevance.de  Ermöglicht den Import von EKG-Daten, essentiell für die kardiologische Analyse
@relevance.en  Enables import of ECG data, essential for cardiological analysis
@limits.en   No validation of ECG data quality. No automatic arrhythmia
             detection. No medical evaluation from ECG data.
             Important for shared devices (e.g. a clinic sensor used across
             multiple people): the device id alone says nothing about the
             person — --person must be set explicitly on each run, otherwise
             the config default (own person) applies.
@usage
    python import_ecg_logger.py --file session.csv
    python import_ecg_logger.py --file session.csv --plot        # EKG-Strip erzeugen
    python import_ecg_logger.py --dir ~/Downloads/ecglogger/
    python import_ecg_logger.py --file session.csv --dry-run
    python import_ecg_logger.py --file session.csv --tags "tachykardie,aufstehen"
    python import_ecg_logger.py --file session.csv --person PER-xxxxxxxx
"""

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import math

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import ImportResult, log_import, resolve_person
from modules.device_registry import device_for_date

DEVICE_CHEST_STRAP_FALLBACK = "ecg_logger_app"
_cfg = _Cfg()
DB_PATH  = _cfg.db_path
OUT_DIR  = _cfg.analyses_dir / "ecg"

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS ecg_logger_sessions (
    session_id      TEXT PRIMARY KEY,   -- YYYY-MM-DDTHH:MM:SS
    duration_s      REAL,
    sample_rate_hz  REAL,               -- typisch 130 Hz (Polar H10)
    n_samples       INTEGER,            -- Anzahl EKG-Samples
    n_rr            INTEGER,            -- extrahierte RR-Intervalle
    rmssd_ms        REAL,
    sdnn_ms         REAL,
    mean_hr_bpm     REAL,
    min_rr_ms       INTEGER,
    max_rr_ms       INTEGER,
    artifact_pct    REAL,               -- Anteil auffälliger RR-Sprünge
    -- Arrhythmie-Flags
    afib_suspected  INTEGER DEFAULT 0,  -- 1 = Konsens ≥3/5 Ebene-1-Metriken
    afib_score      REAL,               -- 0.0–1.0 (Anteil positiver Votes)
    afib_votes      INTEGER,            -- Anzahl positiver Votes (0–5)
    poincare_ratio  REAL,               -- SD1/SD2 (AFib ≈1.0, Sinus <<1)
    sampen          REAL,               -- Sample Entropy (AFib >1.0)
    turning_pt_ratio REAL,              -- Turning Point Ratio (AFib >0.62)
    cv_drr          REAL,               -- CV der ΔRR-Serie (Tateno & Glass)
    cv_rr           REAL,               -- CV der RR-Serie
    tachy_sustained INTEGER DEFAULT 0,  -- 1 = HR > 100 bpm für ≥30 aufeinanderfolgend
    brady_flag      INTEGER DEFAULT 0,  -- 1 = HR < 50 bpm
    -- Kontext
    device          TEXT,
    tags            TEXT,
    notes           TEXT,
    file_path       TEXT,
    source          TEXT DEFAULT 'ecg_logger',
    person          TEXT NOT NULL DEFAULT 'unknown',
    wear_location   TEXT,               -- Tragort, falls Sensor variiert; NULL = unbekannt/Standard
    mode            TEXT                -- Aufzeichnungsmodus (z.B. 'schwimmen'); NULL = Standardmodus
)
"""

CREATE_ECG = """
CREATE TABLE IF NOT EXISTS ecg_logger_ecg (
    session_id   TEXT,
    ts_ns        INTEGER,    -- Unix-Timestamp in Nanosekunden (Rohwert vom Sensor)
    ts_ms        REAL,       -- ms seit Session-Start (für Plots / Analyse)
    mv           REAL,       -- EKG-Amplitude in mV
    PRIMARY KEY (session_id, ts_ns)
)
"""


# ─── Format-Erkennung & Parsing ───────────────────────────────────────────────

def _datum_aus_header_or_name(lines: list[str], path: Path) -> tuple[str, str | None, float]:
    """Liest Datum, Device, Sample-Rate aus Header. Fallback: Filename / mtime."""
    dt = None
    device = None
    sample_rate = 130.0

    for line in lines[:25]:
        s = line.strip()
        # Datum: "Date: 31.05.2026 09:15:00" or ISO
        m = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)', s)
        if m and dt is None:
            d, mo, y, t = m.groups()
            dt = f"{y}-{mo.zfill(2)}-{d.zfill(2)}T{t if len(t)==8 else t+':00'}"
        m2 = re.search(r'(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)', s)
        if m2 and dt is None:
            dt = f"{m2.group(1)}T{m2.group(2)}"
            if len(dt) == 16:
                dt += ":00"
        # Device
        m3 = re.search(r'[Dd]evice[:\s]+([^\n,]+)', s)
        if m3:
            device = m3.group(1).strip()
        # Sample-Rate
        m4 = re.search(r'(\d+\.?\d*)\s*[Hh]z', s)
        if m4:
            sample_rate = float(m4.group(1))
        m5 = re.search(r'[Ss]ample\s+interval[:\s]+([\d.]+)\s*ms', s)
        if m5:
            sample_rate = round(1000 / float(m5.group(1)), 2)

    if dt is None:
        # Filename: ECGLogger_YYYY-MM-DD_091500
        m = re.search(r'(\d{4}-\d{2}-\d{2})[_T](\d{2})[:\-_]?(\d{2})[:\-_]?(\d{2})?', path.stem)
        if m:
            d = m.group(1)
            h, mi, s_ = m.group(2), m.group(3), (m.group(4) or "00")
            dt = f"{d}T{h}:{mi}:{s_}"
        else:
            dt = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")

    return dt, device, sample_rate


def _parse_ecg_csv(path: Path) -> tuple[str, list[int], list[float], list[int], str | None, float]:
    """
    Liest ECGLogger CSV: time(ns), ecg(mV), hr(bpm, optional), rr(ms, optional), marker(optional).
    RR-Intervalle werden direkt aus der rr-Spalte gelesen — keine QRS-Detektion nötig.
    Gibt (session_id, ts_ns_list, mv_list, rr_list, device, sample_rate) zurück.
    ts_ns_list enthält rohe Nanosekunden-Timestamps vom Sensor.
    """
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.splitlines()

    _, device, sr = _datum_aus_header_or_name(lines, path)

    # Header-Zeile finden und Spalten-Indizes bestimmen
    col_ecg = 1
    col_rr  = -1
    data_start = 0
    for i, line in enumerate(lines[:25]):
        parts = re.split(r'[,;\t]', line.strip())
        pl = [p.strip().lower() for p in parts]
        if 'ecg' in pl or ('time' in pl and len(pl) >= 2):
            col_ecg    = pl.index('ecg') if 'ecg' in pl else 1
            col_rr     = pl.index('rr')  if 'rr'  in pl else -1
            data_start = i + 1
            break

    ts_ns_list: list[int]   = []
    mv_list:    list[float] = []
    rr_list:    list[int]   = []

    for line in lines[data_start:]:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = re.split(r'[,;\t]', line)
        if len(parts) < 2:
            continue
        try:
            t_ns  = int(float(parts[0].strip()))
            m_val = float(parts[col_ecg].strip())
        except (ValueError, IndexError):
            continue
        if abs(m_val) > 10:
            continue

        ts_ns_list.append(t_ns)
        mv_list.append(m_val)

        # RR direkt aus Spalte lesen
        if col_rr >= 0 and col_rr < len(parts):
            rr_str = parts[col_rr].strip()
            if rr_str:
                try:
                    rr_val = float(rr_str)
                    if 200 <= rr_val <= 2500:
                        rr_list.append(int(round(rr_val)))
                except ValueError:
                    pass

    # session_id aus erstem Timestamp
    if ts_ns_list:
        session_id = datetime.fromtimestamp(ts_ns_list[0] / 1_000_000_000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    else:
        session_id = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")

    return session_id, ts_ns_list, mv_list, rr_list, device, sr


def _parse_rr_txt(path: Path) -> tuple[str, list[int], str | None]:
    """Liest RR-only TXT (eine Zahl pro Zeile)."""
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.splitlines()
    dt, device, _ = _datum_aus_header_or_name(lines, path)
    rr: list[int] = []
    for line in lines:
        line = line.strip()
        if not line or not re.match(r'^[\d.]+$', line):
            continue
        try:
            v = float(line)
            if 200 <= v <= 2500:
                rr.append(int(round(v)))
            elif 0.2 <= v <= 2.5:
                rr.append(int(round(v * 1000)))
        except ValueError:
            pass
    return dt, rr, device


# ─── QRS-Erkennung ────────────────────────────────────────────────────────────

def _qrs_detect(ts_ms: list[float], mv: list[float], sr: float) -> list[float]:
    """
    Einfache QRS-Detektion via Bandpass + Peak-Finding (Pan-Tompkins-Ansatz).
    Gibt Timestamp der R-Peaks zurück (in ms).
    """
    try:
        import numpy as np
        from scipy import signal

        sig = np.array(mv)
        n = len(sig)
        if n < int(sr * 2):       # weniger als 2 Sekunden → nicht auswertbar
            return []

        # 1) Bandpass 5–40 Hz (entfernt Baseline-Drift and Muskelartefakte)
        sos = signal.butter(3, [5, 40], btype='band', fs=sr, output='sos')
        filtered = signal.sosfiltfilt(sos, sig)

        # 2) Differenzieren + quadrieren → R-Peak-Energie
        diff  = np.diff(filtered)
        squared = diff ** 2

        # 3) Gleitender Average (150 ms Fenster)
        win = max(1, int(0.150 * sr))
        kernel = np.ones(win) / win
        mwa = np.convolve(squared, kernel, mode='same')

        # 4) Peaks finden: min. Abstand 300 ms (max 200 bpm), Höhe > 0.4 * max
        min_dist = int(0.30 * sr)
        threshold = 0.4 * mwa.max()
        peaks, _ = signal.find_peaks(mwa, height=threshold, distance=min_dist)

        ts = np.array(ts_ms)
        if len(ts) == len(diff):
            return [float(ts[p]) for p in peaks]
        else:
            # Gleichmäßige Abtastung annehmen
            dt_ms = 1000 / sr
            return [float(p * dt_ms) for p in peaks]

    except Exception:
        return []


def _rr_aus_peaks(peak_ts: list[float]) -> list[int]:
    """berechnet RR-Intervall aus R-Peak-Timestampn (ms)."""
    rr = []
    for i in range(1, len(peak_ts)):
        interval = int(round(peak_ts[i] - peak_ts[i-1]))
        if 200 <= interval <= 2500:   # 24–300 bpm
            rr.append(interval)
    return rr


# ─── Statistik & Arrhythmia-Flags ─────────────────────────────────────────────

def _stats(rr: list[int]) -> dict:
    if len(rr) < 2:
        return {}
    diffs_sq = [(rr[i+1] - rr[i])**2 for i in range(len(rr)-1)]
    rmssd = math.sqrt(sum(diffs_sq) / len(diffs_sq))
    mean_rr = sum(rr) / len(rr)
    sdnn = math.sqrt(sum((r - mean_rr)**2 for r in rr) / (len(rr) - 1))
    artifacts = sum(1 for i in range(1, len(rr)) if abs(rr[i] - rr[i-1]) > 0.2 * rr[i-1])
    return {
        "rmssd_ms":     round(rmssd, 2),
        "sdnn_ms":      round(sdnn, 2),
        "mean_hr_bpm":  round(60000 / mean_rr, 1),
        "min_rr_ms":    min(rr),
        "max_rr_ms":    max(rr),
        "artifact_pct": round(artifacts / len(rr) * 100, 1),
    }


def _afib_level1(rr: list[int]) -> dict:
    """
    AFib-Detektion Ebene 1: vier RR-basierte Metriken, Konsens-Voting (≥3/4 → Verdacht).

    Thresholds kalibriert auf MIT-BIH AFDB (24 Records, 14965 Fenster à 150 Beats):
      1. Poincaré SD1/SD2-Ratio  — > 0.740  (AUC=0.537, F1=0.679)
      2. Sample Entropy (SampEn) — > 1.587  (AUC=0.853, F1=0.793)
      3. Turning Point Ratio     — > 0.574  (AUC=0.882, F1=0.816)
      4. CV der RR-Serie          — > 0.148  (AUC=0.916, F1=0.834)

    cv_drr (Tateno & Glass 2001): AUC=0.288 auf AFDB → deaktiviert, nur gespeichert.

    TODO Ebene 2 (P-Wellen-Analyse, Raw-ECG benötigt):
      - Bandpass 1–20 Hz, Segment 80–200 ms vor jedem QRS extrahieren
      - Kreuzkorrelation mit P-Wellen-Schablone (aus Sinus-Segmenten gelernt)
      - f-Wellen-Energie im PR-Intervall als Feature
      - Implementierung in compute/compute_afib_pwaves.py
      - Voraussetzung: ecg_logger_ecg muss vollständig geladen sein (nicht 10-min-Limit)

    TODO Ebene 3 (ML / validierte Bibliothek):
      - NeuroKit2: nk.ecg_findpeaks() + nk.hrv_nonlinear() für Poincaré/Entropie
      - PhysioNet CinC Challenge 2017 Gewinner-Modell (LSTM auf RR-Features)
      - Implementierung in compute/compute_afib_ml.py nach 72h-Datensatz
      - Voraussetzung: gelabelter Datensatz (AFib-Episoden aus Apple Watch EKG)
    """
    n = len(rr)
    if n < 30:
        return {"afib_votes": 0, "afib_score": 0.0,
                "poincare_ratio": None, "sampen": None,
                "turning_pt_ratio": None, "cv_drr": None, "cv_rr": None}

    mean_rr = sum(rr) / n
    diffs = [rr[i+1] - rr[i] for i in range(n - 1)]

    # 1) Poincaré SD1/SD2-Ratio
    sd1 = math.sqrt(sum(d**2 for d in diffs) / (2 * len(diffs)))
    sd2 = math.sqrt(max(0, sum((r - mean_rr)**2 for r in rr) / (n - 1) * 2 - sd1**2))
    ratio = round(sd1 / sd2, 3) if sd2 > 0 else 1.0
    vote_poincare = 1 if ratio > 0.740 else 0

    # 2) Sample Entropy (SampEn, m=2, r=0.2*std)
    def _sampen(series: list[int], m: int = 2, r_fac: float = 0.2) -> float:
        s = series
        std = math.sqrt(sum((x - sum(s)/len(s))**2 for x in s) / len(s))
        r = r_fac * std
        if r == 0:
            return 0.0
        def _count(length):
            cnt = 0
            for i in range(len(s) - length):
                for j in range(i + 1, len(s) - length):
                    if all(abs(s[i+k] - s[j+k]) < r for k in range(length)):
                        cnt += 1
            return cnt
        # Approximation auf max. 300 Schläge begrenzen (Performance)
        sub = s[:300]
        a = _count_fast(sub, m + 1, r)
        b = _count_fast(sub, m, r)
        return -math.log(a / b) if a > 0 and b > 0 else 0.0

    def _count_fast(s, m, r):
        cnt = 0
        for i in range(len(s) - m):
            for j in range(i + 1, len(s) - m):
                if all(abs(s[i+k] - s[j+k]) < r for k in range(m)):
                    cnt += 1
        return cnt

    sampen = round(_sampen(rr[:300]), 3)
    vote_sampen = 1 if sampen > 1.587 else 0

    # 3) Turning Point Ratio
    turns = sum(
        1 for i in range(1, n - 1)
        if (rr[i] > rr[i-1] and rr[i] > rr[i+1]) or
           (rr[i] < rr[i-1] and rr[i] < rr[i+1])
    )
    tpr = round(turns / (n - 2), 3)
    vote_tpr = 1 if tpr > 0.574 else 0

    # 4) CV der ΔRR-Serie (Tateno & Glass 2001) — nur gespeichert, kein Vote (AUC=0.331 auf AFDB)
    mean_drr = sum(abs(d) for d in diffs) / len(diffs)
    std_drr = math.sqrt(sum((abs(d) - mean_drr)**2 for d in diffs) / len(diffs))
    cv_drr = round(std_drr / mean_drr, 3) if mean_drr > 0 else 0.0

    # 5) CV der RR-Serie
    cv_rr = round(math.sqrt(sum((r - mean_rr)**2 for r in rr) / n) / mean_rr, 3)
    vote_cvrr = 1 if cv_rr > 0.148 else 0

    votes = vote_poincare + vote_sampen + vote_tpr + vote_cvrr  # 4 aktive Metriken
    score = round(votes / 4, 2)

    return {
        "afib_votes":       votes,
        "afib_score":       score,
        "poincare_ratio":   ratio,
        "sampen":           sampen,
        "turning_pt_ratio": tpr,
        "cv_drr":           cv_drr,
        "cv_rr":            cv_rr,
    }


def _arrhythmie_flags(rr: list[int], stats: dict) -> dict:
    flags = {"afib_suspected": 0, "tachy_sustained": 0, "brady_flag": 0}
    if not rr:
        return flags

    # AFib Ebene 1: Konsens-Voting ≥3/4 aktive Metriken
    afib = _afib_level1(rr)
    flags["afib_suspected"] = 1 if afib["afib_votes"] >= 3 else 0
    flags["afib_score"]     = afib["afib_score"]
    flags["afib_votes"]     = afib["afib_votes"]
    flags["poincare_ratio"] = afib["poincare_ratio"]
    flags["sampen"]         = afib["sampen"]
    flags["turning_pt_ratio"] = afib["turning_pt_ratio"]
    flags["cv_drr"]         = afib["cv_drr"]
    flags["cv_rr"]          = afib["cv_rr"]

    # Sustained Tachycardia: ≥30 aufeinanderfolgende Schläge > 100 bpm (~3 min)
    consec_tachy = 0
    for r in rr:
        if 60000 / r > 100:
            consec_tachy += 1
            if consec_tachy >= 30:
                flags["tachy_sustained"] = 1
                break
        else:
            consec_tachy = 0

    # Bradycardia
    if stats.get("mean_hr_bpm", 100) < 50:
        flags["brady_flag"] = 1

    return flags


# ─── EKG-Strip-Plot ───────────────────────────────────────────────────────────

def _plot_ecg(session_id: str, ts_ms: list[float], mv: list[float],
              peak_ts: list[float], stats: dict, flags: dict, path_out: Path):
    """Erzeugt einen clinical formatierten EKG-Strip (25mm/s, 10mm/mV Standard)."""
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ts  = np.array(ts_ms)
        sig = np.array(mv)

        # Maximal 30 seconds zeigen (clinicaler EKG-Strip)
        show_s = min(30.0, ts[-1] / 1000 if len(ts) > 0 else 30.0)
        mask = ts <= show_s * 1000
        ts_s   = ts[mask] / 1000
        sig_s  = sig[mask]

        fig, ax = plt.subplots(figsize=(15, 4), facecolor="#1A1A2E")
        ax.set_facecolor("#0D1B1E")

        # EKG-Raster (1mm-Linien, 5mm hervorgehoben — clinicaler Standard)
        for x in np.arange(0, show_s + 0.04, 0.04):      # 1mm bei 25mm/s = 40ms
            ax.axvline(x, color="#2A3A3A", linewidth=0.3, alpha=0.6)
        for x in np.arange(0, show_s + 0.2, 0.2):         # 5mm = 200ms
            ax.axvline(x, color="#3A5A5A", linewidth=0.6, alpha=0.7)
        for y in np.arange(-2.0, 2.1, 0.1):               # 1mm vertikal
            ax.axhline(y, color="#2A3A3A", linewidth=0.3, alpha=0.6)
        for y in np.arange(-2.0, 2.1, 0.5):               # 5mm vertikal
            ax.axhline(y, color="#3A5A5A", linewidth=0.6, alpha=0.7)

        ax.plot(ts_s, sig_s, color="#00FF88", linewidth=0.7, alpha=0.95)

        # R-Peaks markieren
        for p_ms in peak_ts:
            if p_ms / 1000 <= show_s:
                ax.axvline(p_ms / 1000, color="#FFD700", linewidth=0.8,
                           alpha=0.5, linestyle=":")

        # Arrhythmia-Label
        flags_text = []
        if flags.get("afib_suspected"):
            flags_text.append("⚠ AFib-Verdacht")
        if flags.get("tachy_sustained"):
            flags_text.append("⚠ Sinustachykardie")
        if flags.get("brady_flag"):
            flags_text.append("⚠ Bradykardie")

        title = (f"EKG-Strip  {session_id[:16]}  |  "
                 f"HR≈{stats.get('mean_hr_bpm', '?')} bpm  "
                 f"RMSSD={stats.get('rmssd_ms', '?')} ms")
        if flags_text:
            title += "  |  " + "  ".join(flags_text)

        ax.set_title(title, color="#E0E0E0", fontsize=9, pad=6)
        ax.set_xlabel("Zeit (s) — 25 mm/s", color="#808080", fontsize=8)
        ax.set_ylabel("Amplitude (mV)", color="#808080", fontsize=8)
        ax.set_xlim(0, show_s)
        ax.set_ylim(-1.5, 1.5)
        ax.tick_params(colors="#606060", labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#3A5A5A")

        # Kalibrierimpuls (1 mV, 200 ms — clinicaler Standard)
        ax.annotate("", xy=(0.15, 1.0), xytext=(0.15, 0.0),
                    arrowprops=dict(arrowstyle="-", color="#FF6060", lw=1.5))
        ax.text(0.16, 0.5, "1mV", color="#FF6060", fontsize=6, va='center')

        fig.tight_layout()
        path_out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(path_out), dpi=150, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(t(f"  EKG-Strip: {path_out}", f"  ECG strip: {path_out}"))
    except Exception as e:
        print(t(f"  Plot fehlgeschlagen: {e}", f"  Plot failed: {e}"))


# ─── DB-Speicherung ───────────────────────────────────────────────────────────

def _save(conn, session_id: str, ts_ns: list[int], mv_list: list[float],
              rr: list[int], device: str | None, sr: float, tags: str, notes: str,
              person: str, dry_run: bool = False, make_plot: bool = False) -> bool:

    existing = conn.execute(
        "SELECT session_id FROM ecg_logger_sessions WHERE session_id = ?",
        (session_id,)
    ).fetchone()
    if existing:
        print(t(f"  ↺ Bereits vorhanden: {session_id[:16]}", f"  ↺ Already exists: {session_id[:16]}"))
        return False

    stats = _stats(rr)
    flags = _arrhythmie_flags(rr, stats)
    duration_s = (ts_ns[-1] - ts_ns[0]) / 1_000_000_000 if len(ts_ns) > 1 else (sum(rr) / 1000 if rr else 0)

    # Clinical Kurzauswertung
    print(t(f"  Dauer:   {duration_s/60:.1f} min  |  {len(rr)} RR-Intervalle  "
            f"|  {len(mv_list)} EKG-Samples @ {sr:.0f} Hz",
            f"  Duration: {duration_s/60:.1f} min  |  {len(rr)} RR intervals  "
            f"|  {len(mv_list)} ECG samples @ {sr:.0f} Hz"))
    if stats:
        print(t(f"  HR:      {stats.get('mean_hr_bpm')} bpm  "
                f"(min RR={stats.get('min_rr_ms')} ms = "
                f"{round(60000/stats['min_rr_ms'],0):.0f} bpm max)",
                f"  HR:      {stats.get('mean_hr_bpm')} bpm  "
                f"(min RR={stats.get('min_rr_ms')} ms = "
                f"{round(60000/stats['min_rr_ms'],0):.0f} bpm max)"))
        print(t(f"  RMSSD:   {stats.get('rmssd_ms')} ms  |  SDNN={stats.get('sdnn_ms')} ms",
                f"  RMSSD:   {stats.get('rmssd_ms')} ms  |  SDNN={stats.get('sdnn_ms')} ms"))
        if stats.get("artifact_pct", 0) > 5:
            print(t(f"  ⚠ Artefakte: {stats['artifact_pct']}%",
                    f"  ⚠ Artifacts: {stats['artifact_pct']}%"))
    print(t(f"  AFib L1: {flags.get('afib_votes', 0)}/5 Votes  "
            f"(Poincaré={flags.get('poincare_ratio')}  "
            f"SampEn={flags.get('sampen')}  "
            f"TPR={flags.get('turning_pt_ratio')}  "
            f"CV_ΔRR={flags.get('cv_drr')}  "
            f"CV_RR={flags.get('cv_rr')})",
            f"  AFib L1: {flags.get('afib_votes', 0)}/5 votes  "
            f"(Poincaré={flags.get('poincare_ratio')}  "
            f"SampEn={flags.get('sampen')}  "
            f"TPR={flags.get('turning_pt_ratio')}  "
            f"CV_ΔRR={flags.get('cv_drr')}  "
            f"CV_RR={flags.get('cv_rr')})"))
    for label, label_en, key in [
        ("⚠ AFib-Verdacht (≥3/5)",       "⚠ AFib suspected (≥3/5)",        "afib_suspected"),
        ("⚠ Sinustachykardie anhaltend",  "⚠ Sustained sinus tachycardia",  "tachy_sustained"),
        ("⚠ Bradykardie",                 "⚠ Bradycardia",                   "brady_flag"),
    ]:
        if flags.get(key):
            print(f"  {t(label, label_en)}")

    if dry_run:
        print(t("  [DRY] Würde importiert werden", "  [DRY] Would be imported"))
        return True

    # Session-Metadaten
    conn.execute("""
        INSERT INTO ecg_logger_sessions
          (session_id, duration_s, sample_rate_hz, n_samples, n_rr,
           rmssd_ms, sdnn_ms, mean_hr_bpm, min_rr_ms, max_rr_ms, artifact_pct,
           afib_suspected, afib_score, afib_votes,
           poincare_ratio, sampen, turning_pt_ratio, cv_drr, cv_rr,
           tachy_sustained, brady_flag,
           device, tags, notes, source, person)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (session_id, round(duration_s, 1), sr, len(mv_list), len(rr),
          stats.get("rmssd_ms"), stats.get("sdnn_ms"), stats.get("mean_hr_bpm"),
          stats.get("min_rr_ms"), stats.get("max_rr_ms"), stats.get("artifact_pct", 0),
          flags["afib_suspected"], flags.get("afib_score"), flags.get("afib_votes"),
          flags.get("poincare_ratio"), flags.get("sampen"),
          flags.get("turning_pt_ratio"), flags.get("cv_drr"), flags.get("cv_rr"),
          flags["tachy_sustained"], flags["brady_flag"],
          device, tags or None, notes or None, "ecg_logger", person))

    # EKG-Samples: ts_ns (absolut) + ts_ms (relativ zur Session, für Plots)
    if ts_ns and mv_list:
        t0_ns = ts_ns[0]
        max_store_ns = 600_000_000_000  # 10 Minuten in ns
        ecg_rows = [
            (session_id, t, round((t - t0_ns) / 1_000_000, 3), round(m, 6))
            for t, m in zip(ts_ns, mv_list)
            if (t - t0_ns) <= max_store_ns
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO ecg_logger_ecg (session_id, ts_ns, ts_ms, mv) VALUES (?,?,?,?)",
            ecg_rows
        )
        if len(ts_ns) > len(ecg_rows):
            print(t(f"  ℹ EKG gespeichert: erste {len(ecg_rows)} von {len(ts_ns)} Samples (10-min-Limit)",
                    f"  ℹ ECG stored: first {len(ecg_rows)} of {len(ts_ns)} samples (10-min limit)"))

    # RR → ppi_raw
    if rr:
        base = datetime.fromisoformat(session_id).replace(tzinfo=timezone.utc)
        strap_device_id = (device_for_date("chest_strap", session_id[:10])
                            or DEVICE_CHEST_STRAP_FALLBACK)
        cum = 0
        ppi_rows = []
        for r in rr:
            ts = base + timedelta(milliseconds=cum)
            ppi_rows.append((ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3], r, strap_device_id, "ecg_logger", person))
            cum += r
        conn.executemany(
            "INSERT OR IGNORE INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?,?,?,?,?)",
            ppi_rows
        )

    conn.commit()
    print(t(f"  ✓ Gespeichert: {session_id[:16]}", f"  ✓ Saved: {session_id[:16]}"))

    # EKG-Strip-Plot (ts_ms relativ für Plot-Achse)
    if make_plot and ts_ns and mv_list:
        t0_ns = ts_ns[0]
        ts_ms_rel = [(t - t0_ns) / 1_000_000 for t in ts_ns]
        ts_str = session_id.replace(":", "").replace("-", "").replace("T", "_")
        plot_path = OUT_DIR / f"ecg_strip_{ts_str}.png"
        peak_ts = _qrs_detect(ts_ms_rel, mv_list, sr)
        _plot_ecg(session_id, ts_ms_rel, mv_list, peak_ts, stats, flags, plot_path)

    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def _ensure_tables(conn) -> None:
    """Legt ecg_logger_sessions/ecg_logger_ecg an (falls noetig) und migriert die
    person-Spalte einmalig (Alt-Zeilen ohne person -> OWN_PERSON_ID, historischer
    Backfill zum Zeitpunkt der Spalten-Einfuehrung, als es nur eine Person gab)."""
    for tbl in ("ecg_logger_sessions", "ecg_logger_ecg"):
        row = conn.execute(
            "SELECT type FROM sqlite_master WHERE name=?", (tbl,)
        ).fetchone()
        if row and row[0] == "view":
            conn.execute(f"DROP VIEW {tbl}")
    for stmt in (CREATE_SESSIONS, CREATE_ECG):
        conn.execute(stmt)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ecg_logger_sessions)")}
    if "person" not in cols:
        conn.execute("ALTER TABLE ecg_logger_sessions ADD COLUMN person TEXT NOT NULL DEFAULT 'unknown'")
        conn.execute("UPDATE ecg_logger_sessions SET person = ?", (resolve_person(),))
    conn.commit()


def _import_files(conn, paths: list[Path], person: str, tags: str = "", notes: str = "",
                   dry_run: bool = False, make_plot: bool = False) -> ImportResult:
    """Kernschleife: parst und speichert jede Datei in paths unter der gegebenen
    person. Von run() (Standard-Konvention, keine Extra-Flags) und main() (voller
    CLI-Funktionsumfang: --tags/--notes/--dry-run/--plot) gemeinsam genutzt, um
    die Logik nicht zu duplizieren."""
    result = ImportResult(source="ecg_logger")
    for p in paths:
        print(f"\n→ {p.name}")
        ts_ns: list[int]    = []
        mv_list: list[float] = []
        rr: list[int]        = []
        device = None
        sr = 130.0

        # Format erkennen: Header mit 'ecg' → CSV; sonst RR-TXT
        first_line = p.read_text(encoding="utf-8-sig", errors="replace").splitlines()[0].lower()
        is_ecg_csv = 'ecg' in first_line or ('time' in first_line and ',' in first_line)

        if is_ecg_csv:
            session_id, ts_ns, mv_list, rr, device, sr = _parse_ecg_csv(p)
            if not rr and mv_list:
                # Fallback: kein rr in CSV → QRS-Detektion (relative ms für Algorithmus)
                ts_ms_rel = [(t - ts_ns[0]) / 1_000_000 for t in ts_ns]
                peak_ts = _qrs_detect(ts_ms_rel, mv_list, sr)
                rr = _rr_aus_peaks(peak_ts)
                print(t(f"  QRS fallback: {len(peak_ts)} R-Peaks → {len(rr)} RR",
                        f"  QRS fallback: {len(peak_ts)} R-peaks → {len(rr)} RR"))
            else:
                print(t(f"  RR aus CSV:  {len(rr)} Intervalle",
                        f"  RR from CSV: {len(rr)} intervals"))
        else:
            session_id, rr, device = _parse_rr_txt(p)

        if _save(conn, session_id, ts_ns, mv_list, rr, device, sr,
                     tags, notes, person,
                     dry_run=dry_run, make_plot=make_plot):
            result.rows_inserted += 1
        else:
            result.rows_skipped += 1
    return result


def run(conn, data_path, lang: str = "de", person: str | None = None) -> ImportResult:
    """Modul-Interface (s. CLAUDE.md-Importer-Konvention). data_path kann eine
    einzelne Datei oder ein Ordner sein."""
    apply_lang_from_args(type("A", (), {"lang": lang})())
    person = resolve_person(person)
    _ensure_tables(conn)

    data_path = Path(data_path)
    if data_path.is_dir():
        paths: list[Path] = []
        for ext in ("*.csv", "*.txt", "*.hrm", "*.CSV", "*.TXT"):
            paths += sorted(data_path.glob(ext))
    else:
        paths = [data_path]

    if not paths:
        return ImportResult(source="ecg_logger")

    result = _import_files(conn, paths, person)
    log_import(conn, 'ecg_logger', str(data_path), result.rows_inserted, result.rows_skipped)
    conn.commit()
    return result


def main():
    """
    Hauptfunktion: Koordiniert den Import der ECGLogger-Daten.

    Command-Line-Argumente:
        --file: ECG CSV oder RR TXT-Datei
        --dir: Ordner mit Sessions
        --plot: EKG-Strip-Plot erzeugen
        --tags: Tags für die Session (z. B. "tachykardie,aufstehen")
        --dry-run: Testlauf ohne Import
        --person: Person-ID (Standard: eigene Person) — wichtig bei geteilten
                  Geraeten (z.B. Arztpraxis), wo die Geraete-ID allein nicht
                  verraet, wem die Aufzeichnung gehoert
    """
    parser = argparse.ArgumentParser(description="ECGLogger Daten importieren")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", metavar="DATEI",  help="ECG CSV or RR TXT")
    group.add_argument("--dir",  metavar="ORDNER", help="Folder with Sessions")
    parser.add_argument("--plot",    action="store_true", help="EKG-Strip-Plot erzeugen")
    parser.add_argument("--tags",    default="", metavar="TAGS",
                        help="e.g. orthostase,tachykardie,morgen")
    parser.add_argument("--notes",   default="", metavar="TEXT")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--person",  default=None, metavar="PERSON_ID",
                        help="Person-ID (Standard: eigene Person aus Config)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    paths: list[Path] = []
    if args.file:
        paths = [Path(args.file)]
    else:
        d = Path(args.dir)
        for ext in ("*.csv", "*.txt", "*.hrm", "*.CSV", "*.TXT"):
            paths += sorted(d.glob(ext))

    if not paths:
        print(t("Keine Dateien gefunden.", "No files found."))
        return

    conn = open_db()
    _ensure_tables(conn)

    result = _import_files(conn, paths, person, tags=args.tags, notes=args.notes,
                            dry_run=args.dry_run, make_plot=args.plot)
    neu = result.rows_inserted

    if not args.dry_run:
        log_import(conn, 'ecg_logger', str(paths[0].parent) if paths else '', neu, result.rows_skipped)
        conn.commit()
    conn.close()
    print(t(f"\n{neu} Session(s) importiert" + (" (DRY-RUN)" if args.dry_run else ""),
            f"\n{neu} session(s) imported" + (" (DRY-RUN)" if args.dry_run else "")))
    if neu > 0 and not args.dry_run:
        print(t("HRV:    python compute/compute_hrv_advanced.py",
                "HRV:    python compute/compute_hrv_advanced.py"))
        print(t("Bericht: python analyse/analyse_orthostatic.py --plot",
                "Report: python analyse/analyse_orthostatic.py --plot"))
        print(t(
            "  ℹ Erinnerung: analyse_ecg_session.py läuft nicht automatisch mit — "
            "für einen Einzelsession-Bericht: python3 scripts/analysis/manual/analyse_ecg_session.py --session <ID>",
            "  ℹ Reminder: analyse_ecg_session.py does not run automatically — "
            "for a single-session report: python3 scripts/analysis/manual/analyse_ecg_session.py --session <ID>"))


if __name__ == "__main__":
    main()
