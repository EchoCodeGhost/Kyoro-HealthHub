#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
R-Peak-Erkennung aus EKG-Rohdaten beliebiger Quelle (Pan-Tompkins).

@tier        research
@purpose.de  Erkennt R-Zacken in EKG-Rohsignalen beliebiger Quelle via Pan-
             Tompkins-Algorithmus. Schreibt erkannte Peaks in ecg_rpeaks und
             die daraus berechneten RR-Intervalle in ppi_raw — Quelle
             device-agnostisch aus ecg_sessions.source abgeleitet (z.B.
             'apple_health' → 'ecg_apple'), sodass compute_arrhythmia und
             compute_ppi_dfa ECG-Sessions aus jeder Quelle, die Rohsignale in
             ecg_sessions/ecg_samples liefert, wie jeden anderen RR-
             Datenstrom verarbeiten können. Zusaetzlich: PR-/QRS-Delineation
             (s. modules/ecg_waveform_algorithms.py) fuer Quellen, die diese
             Werte nicht selbst berechnen (Apple Watch, ECG Logger/H10) —
             Withings BPM Core liefert PR/QRS/QT/QTc bereits geraeteeigen
             zertifiziert (import_withings.py) und wird hier ausgespart, um
             keine zwei konkurrierenden Werte unter demselben Metric-Namen zu
             erzeugen. ECG-Logger-Sessions (separates Tabellenschema
             ecg_logger_sessions/ecg_logger_ecg, s. import_ecg_logger.py)
             werden fuer die Delineation zusaetzlich eingelesen — bisher
             komplett ungenutzt fuer alles ausser der App-eigenen RR-
             Berechnung, die schon direkt in ppi_raw landet.
@purpose.en  Detects R-peaks in ECG raw signals from any source using the
             Pan-Tompkins algorithm. Writes detected peaks to ecg_rpeaks and
             derived RR intervals to ppi_raw — source label derived device-
             agnostically from ecg_sessions.source (e.g. 'apple_health' →
             'ecg_apple'), so that compute_arrhythmia and compute_ppi_dfa can
             process ECG sessions from any source that delivers raw signals
             into ecg_sessions/ecg_samples like any other RR data stream.
             Additionally: PR/QRS delineation (see
             modules/ecg_waveform_algorithms.py) for sources that do not
             compute these values themselves (Apple Watch, ECG Logger/H10) —
             Withings BPM Core already reports PR/QRS/QT/QTc via its own
             certified on-device algorithm (import_withings.py) and is
             skipped here to avoid two competing values under the same
             metric name. ECG Logger sessions (separate table schema
             ecg_logger_sessions/ecg_logger_ecg, see import_ecg_logger.py)
             are additionally read for delineation — previously entirely
             unused for anything beyond the app's own RR computation, which
             already lands directly in ppi_raw.
@method.de   R-Zacken: Pan-Tompkins 1985 (Bandpassfilter 5-15 Hz → 5-Punkt-
             Ableitung → Quadrierung → gleitendes Fenster-Integral 150ms →
             Peak-Suche mit 200ms Refraktaerperiode). Aussortiert: poor_
             recording-Sessions. PR/QRS-Delineation: s. modules/
             ecg_waveform_algorithms.py fuer Methode/Grenzen (neurokit2,
             DWT-Delineation) — je Session wird der MEDIAN ueber alle
             erfolgreich delinierten Beats geschrieben (ein Wert je Aufnahme,
             analog zu Withings' geraeteeigenem Ein-Wert-pro-Aufnahme-Muster),
             nicht ein Wert je Einzelbeat.
@method.en   R-peaks: Pan-Tompkins 1985 (bandpass filter 5-15 Hz → 5-point
             derivative → squaring → 150ms moving window integration → peak
             search with 200ms refractory period). Excluded: poor_recording
             sessions. PR/QRS delineation: see modules/
             ecg_waveform_algorithms.py for method/limits (neurokit2, DWT
             delineation) — per session, the MEDIAN across all successfully
             delineated beats is written (one value per recording, mirroring
             Withings' own one-value-per-recording pattern), not one value
             per individual beat.
@thresholds
    ok          :: de=Erkannte HR 30–200 bpm; RR-Plausibilitätsfenster 300–2000 ms :: en=Detected HR 30–200 bpm; RR plausibility window 300–2000 ms
    suspicious  :: de=poor_recording-Sessions werden übersprungen :: en=poor_recording sessions are skipped
@reads       ecg_sessions, ecg_samples, ecg_logger_sessions, ecg_logger_ecg
@writes      ecg_rpeaks: R-Peak-Indizes pro ECG-Session
             ppi_raw: RR-Intervalle (source device-agnostisch abgeleitet, s. @purpose)
             measurements: ecg_pr_duration_ms, ecg_qrs_duration_ms (Median je Session,
             source_app='ecg_delineation_<quelle>' bzw. 'ecg_delineation_ecg_logger')
@refs        Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532
             Martinez JP, Almeida R, Olmos S, Rocha AP, Laguna P (2004). A wavelet-based ECG delineator: evaluation on standard databases. IEEE Transactions on Biomedical Engineering, 51(4):570-581. doi:10.1109/TBME.2003.821031
             Makowski D, Pham T, Lau ZJ et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. Behavior Research Methods, 53(4):1689-1696. doi:10.3758/s13428-020-01516-y

@relevance.de  Ermöglicht die Analyse von EKG-Daten, essentiell für die kardiologische Diagnostik
@relevance.en  Enables ECG data analysis, essential for cardiological diagnostics
@limits.de   Adaptiver Schwellwert vereinfacht: 0,25 × 98. Perzentile des MWI (robust
             gegen Ausreißer). Das Original Pan-Tompkins nutzt einen adaptiven
             Lernalgorithmus mit laufenden Signal-/Rauschen-Peak-Schätzwerten; diese
             Vereinfachung ist für 30-s-Segmente praktisch, kann aber bei stark
             verrauschten oder artefaktbehafteten Signalen abweichen.
             30-s-Fenster (≈30–38 Schläge) zu kurz für DFA alpha1 (braucht ≥100 Schläge).
             Tateno-Glass und Arrhythmie-Detektion funktionieren ab n≥3 Schlägen.
             Kein Ersatz für klinisches EKG; die Geräte-EKG-Klassifikation
             (ecg_sessions.classification, gerätespezifisch berechnet) bleibt
             primäre Quelle für AFES-Direktevidenz. PR/QRS-Delineation: s.
             modules/ecg_waveform_algorithms.py @limits fuer den vollstaendigen
             Umfang (u.a. QT/QTc bewusst nicht berechnet — T-Wellen-Erkennung
             empirisch instabil, s. dort).
@limits.en   Adaptive threshold simplified: 0.25 × 98th percentile of MWI (robust
             against outlier artifacts). The original Pan-Tompkins uses an adaptive
             learning algorithm with running signal/noise peak estimates; this
             simplification is practical for 30-s segments but may deviate for
             heavily noisy or artefact-laden signals.
             30-second windows (≈30–38 beats) too short for DFA alpha1 (needs ≥100 beats).
             Tateno-Glass and arrhythmia detection work from n≥3 beats.
             Not a replacement for clinical ECG; the device's own ECG classification
             (ecg_sessions.classification, computed per device) remains the
             primary source for AFES direct evidence. PR/QRS delineation: see
             modules/ecg_waveform_algorithms.py @limits for the full scope
             (among others, QT/QTc deliberately not computed — T-wave
             detection empirically unstable, see there).
@usage
    python compute_ecg_rpeaks.py
    python compute_ecg_rpeaks.py --recompute
"""

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.base import resolve_timezone, local_date
from modules.db import open_db
from modules.ecg_waveform_algorithms import delineate_and_measure
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()

FS           = 512          # Hz
RR_MIN_MS    = 300          # physiological lower bound (200 bpm)
RR_MAX_MS    = 2000         # physiological upper bound (30 bpm)
REFRACTORY_S = 0.200        # Pan-Tompkins refractory period
BANDPASS_LO  = 5.0          # Hz
BANDPASS_HI  = 15.0         # Hz
MWI_WIN_S    = 0.150        # moving window integration window
SEARCH_S     = 0.100        # ±100 ms search window for true R-peak
METHOD       = "pan_tompkins"

# ecg_sessions.source -> ppi_raw.source label. Unmapped sources fall back to a
# generic ecg_<source> label instead of being silently mislabeled (device-agnostic
# fallback, s. cross-cutting-conventions spec — kein Hartcodieren auf eine Marke).
ECG_SOURCE_LABELS = {
    "apple_health": "ecg_apple",
    "garmin_gdpr":  "ecg_garmin",
}


def _ppi_source_label(ecg_source: str | None) -> str:
    if not ecg_source:
        return "ecg_unknown"
    return ECG_SOURCE_LABELS.get(ecg_source, f"ecg_{ecg_source}")


# ── Signal Processing ────────────────────────────────────────────────────────

def _detect_rpeaks(signal_uv: np.ndarray, fs: int = FS) -> list[int]:
    """Pan-Tompkins R-peak detection. Returns sample indices."""
    n = len(signal_uv)
    if n < fs:  # need at least 1 second
        return []

    sig = signal_uv.astype(float)

    # Artifact rejection: Winsorize at max(4 × robust_std, 500 µV).
    # IQR-based scale is insensitive to QRS spikes (brief relative to baseline).
    # Minimum 500 µV protects QRS peaks in low-amplitude signals.
    q25, q75 = np.percentile(sig, [25, 75])
    robust_scale = max((q75 - q25) / 1.35, 1.0)
    clip_val = max(robust_scale * 4.0, 500.0)
    sig = np.clip(sig, -clip_val, clip_val)

    # Bandpass filter (QRS energy: 5–15 Hz)
    nyq = fs / 2.0
    b, a = butter(2, [BANDPASS_LO / nyq, BANDPASS_HI / nyq], btype="band")
    sig_bp = filtfilt(b, a, sig)

    # 5-point derivative (Pan-Tompkins eq. 3), vectorised:
    # y[i] = (fs/8) × (−x[i−2] − 2x[i−1] + 2x[i+1] + x[i+2])
    sig_d = np.zeros(n)
    sig_d[2:n - 2] = (
        2 * sig_bp[3:n - 1] + sig_bp[4:n]
        - sig_bp[0:n - 4] - 2 * sig_bp[1:n - 3]
    ) * (fs / 8.0)

    # Square
    sig_sq = sig_d ** 2

    # Moving window integration (150 ms)
    win = max(1, int(MWI_WIN_S * fs))
    sig_mwi = np.convolve(sig_sq, np.ones(win) / win, mode="same")

    # Adaptive threshold: 0.25 × 98th percentile of MWI (robust against outlier artifacts)
    refractory = int(REFRACTORY_S * fs)
    p98 = float(np.percentile(sig_mwi, 98))
    threshold = 0.25 * p98 if p98 > 0 else 1.0
    peaks_mwi, _ = find_peaks(sig_mwi, height=threshold, distance=refractory)
    if len(peaks_mwi) == 0:
        return []

    # Find true R-peak in original (clipped) signal within ±100 ms of each MWI peak
    search_half = int(SEARCH_S * fs)
    r_peaks = []
    for p in peaks_mwi:
        lo = max(0, p - search_half)
        hi = min(n, p + search_half + 1)
        r_peaks.append(int(lo + int(np.argmax(np.abs(sig[lo:hi])))))

    # Deduplicate within refractory period
    r_peaks.sort()
    deduped: list[int] = [r_peaks[0]]
    for rp in r_peaks[1:]:
        if rp - deduped[-1] >= refractory:
            deduped.append(rp)

    return deduped


def _rpeaks_to_rr(peaks: list[int], fs: int = FS) -> list[float]:
    """Convert R-peak sample indices to RR intervals in milliseconds."""
    return [(peaks[i + 1] - peaks[i]) / fs * 1000.0 for i in range(len(peaks) - 1)]


# ── Database ─────────────────────────────────────────────────────────────────

def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ecg_rpeaks (
            session_dt     TEXT NOT NULL,
            session_person TEXT NOT NULL,
            sample_index   INTEGER NOT NULL,
            peak_ms        REAL,
            method         TEXT DEFAULT 'pan_tompkins',
            PRIMARY KEY (session_dt, session_person, sample_index),
            FOREIGN KEY (session_dt, session_person)
                REFERENCES ecg_sessions(datetime, person)
        );
        CREATE INDEX IF NOT EXISTS idx_ecg_rpeaks_session
            ON ecg_rpeaks(session_dt, session_person);
    """)


def _already_done(conn: sqlite3.Connection, session_dt: str, person: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM ecg_rpeaks WHERE session_dt=? AND session_person=? LIMIT 1",
        (session_dt, person),
    ).fetchone()
    return row is not None


def _load_signal(conn: sqlite3.Connection, session_dt: str, person: str) -> np.ndarray:
    rows = conn.execute(
        "SELECT uv FROM ecg_samples WHERE session_dt=? AND session_person=? ORDER BY sample_index",
        (session_dt, person),
    ).fetchall()
    return np.array([r[0] for r in rows], dtype=float)


def _write_wave_intervals(conn: sqlite3.Connection, signal_mv, fs: int, t0: datetime,
                           device_id: str | None, person: str, source_app: str) -> int:
    """Delineiert P/QRS (s. modules/ecg_waveform_algorithms.py) und schreibt
    EINEN Median-Wert je Metrik (pr/qrs) pro Session in measurements — nicht
    je Beat, um dieselbe Granularitaet wie Withings' geraeteeigen berichtete
    PR/QRS/QT/QTc-Werte zu spiegeln (ein Wert je Aufnahme), statt Zehntausende
    Beat-Zeilen in die EAV-Tabelle zu schreiben. Median statt Mittelwert:
    robuster gegen die wenigen verbleibenden Ausreisser, die das
    Plausibilitaets-Gate in delineate_and_measure durchrutschen."""
    beats = delineate_and_measure(signal_mv, fs)
    if len(beats) < 5:  # zu wenige valide Beats fuer einen belastbaren Median
        return 0
    prs = [b["pr_ms"] for b in beats]
    qrss = [b["qrs_ms"] for b in beats]
    ts = t0.strftime("%Y-%m-%dT%H:%M:%S")
    tz_name = resolve_timezone(conn, person, ts=ts)
    date = local_date(ts, tz_name)
    rows = [
        (ts, date, "ecg_pr_duration_ms", round(float(np.median(prs)), 1), "ms", device_id, person, source_app),
        (ts, date, "ecg_qrs_duration_ms", round(float(np.median(qrss)), 1), "ms", device_id, person, source_app),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO measurements(ts, date, metric, value, unit, device_id, person, source_app)"
        " VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _process_session(conn: sqlite3.Connection, session: tuple, recompute: bool) -> dict:
    """Process one ECG session. Returns stats dict."""
    session_dt, classification, sample_rate_hz, person, device_id, ecg_source = session
    fs = int(sample_rate_hz or FS)
    ppi_source = _ppi_source_label(ecg_source)

    if not recompute and _already_done(conn, session_dt, person):
        return {"status": "skip"}

    if classification == "poor_recording":
        return {"status": "poor_recording"}

    signal = _load_signal(conn, session_dt, person)
    if len(signal) < fs:
        return {"status": "too_short", "n": len(signal)}

    peaks = _detect_rpeaks(signal, fs)
    if len(peaks) < 2:
        return {"status": "no_peaks", "n_peaks": len(peaks)}

    # --- ecg_rpeaks ---
    conn.executemany(
        "INSERT OR IGNORE INTO ecg_rpeaks(session_dt, session_person, sample_index, peak_ms, method)"
        " VALUES (?,?,?,?,?)",
        [
            (session_dt, person, int(idx), round(idx / fs * 1000, 3), METHOD)
            for idx in peaks
        ],
    )

    # --- ppi_raw ---
    # datetime for each beat = session_dt + (sample_index / fs) seconds
    try:
        t0 = datetime.fromisoformat(session_dt).replace(tzinfo=timezone.utc)
    except ValueError:
        return {"status": "bad_dt", "session_dt": session_dt}

    rr_rows: list[tuple] = []
    for i in range(len(peaks) - 1):
        beat_dt = t0 + timedelta(seconds=peaks[i] / fs)
        rr_ms = round((peaks[i + 1] - peaks[i]) / fs * 1000.0)
        if RR_MIN_MS <= rr_ms <= RR_MAX_MS:
            rr_rows.append((
                beat_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
                rr_ms,
                device_id or ecg_source or "unknown_device",
                ppi_source,
                person,
            ))

    conn.executemany(
        "INSERT OR IGNORE INTO ppi_raw(datetime, pulse_ms, device, source, person) VALUES(?,?,?,?,?)",
        rr_rows,
    )

    # --- PR/QRS-Delineation ---
    # Withings BPM Core liefert PR/QRS/QT/QTc bereits geraeteeigen zertifiziert
    # (import_withings.py) — hier NICHT zusaetzlich berechnen, das wuerde zwei
    # konkurrierende Werte unter demselben Metric-Namen erzeugen.
    n_wave = 0
    if ecg_source != "withings":
        n_wave = _write_wave_intervals(
            conn, signal / 1000.0, fs, t0, device_id, person, f"ecg_delineation_{ecg_source or 'unknown'}",
        )

    return {"status": "ok", "n_peaks": len(peaks), "n_rr": len(rr_rows), "n_wave": n_wave}


def _process_ecg_logger_session(conn: sqlite3.Connection, session: tuple, recompute: bool) -> dict:
    """PR/QRS-Delineation fuer eine ECG-Logger-Session (separates Tabellenschema,
    s. Docstring @purpose — bisher komplett ungenutzt fuer Delineation). Keine
    R-Zacken-/ppi_raw-Schreibung hier: import_ecg_logger.py schreibt die vom
    App-eigenen Algorithmus berechneten RR-Intervalle bereits direkt in
    ppi_raw, das duplizieren wir nicht."""
    session_id, sample_rate_hz, device, person, source = session
    fs = int(sample_rate_hz or 130)
    device_id = device or source or "unknown_device"

    rows = conn.execute(
        "SELECT ts_ns, mv FROM ecg_logger_ecg WHERE session_id=? ORDER BY ts_ns", (session_id,)
    ).fetchall()
    if len(rows) < fs * 2:
        return {"status": "too_short", "n": len(rows)}

    t0 = datetime.fromtimestamp(rows[0][0] / 1e9, tz=timezone.utc)
    ts = t0.strftime("%Y-%m-%dT%H:%M:%S")

    if not recompute:
        existing = conn.execute(
            "SELECT 1 FROM measurements WHERE ts=? AND person=? AND metric='ecg_pr_duration_ms'"
            " AND source_app='ecg_delineation_ecg_logger' LIMIT 1",
            (ts, person),
        ).fetchone()
        if existing:
            return {"status": "skip"}

    signal_mv = np.array([r[1] for r in rows], dtype=float)
    n_wave = _write_wave_intervals(conn, signal_mv, fs, t0, device_id, person, "ecg_delineation_ecg_logger")
    return {"status": "ok" if n_wave else "no_peaks", "n_wave": n_wave}


def _run(conn: sqlite3.Connection, recompute: bool = False) -> None:
    _ensure_table(conn)

    sessions = conn.execute("""
        SELECT datetime, classification, sample_rate_hz, person, device_id, source
        FROM ecg_sessions
        ORDER BY datetime
    """).fetchall()

    if recompute:
        labels = {_ppi_source_label(s[5]) for s in sessions}
        wave_labels = {f"ecg_delineation_{s[5] or 'unknown'}" for s in sessions if s[5] != "withings"}
        conn.execute("DELETE FROM ecg_rpeaks")
        if labels:
            conn.executemany("DELETE FROM ppi_raw WHERE source=?", [(l,) for l in labels])
        if wave_labels:
            conn.executemany(
                "DELETE FROM measurements WHERE source_app=? AND metric IN"
                " ('ecg_pr_duration_ms','ecg_qrs_duration_ms')",
                [(l,) for l in wave_labels],
            )
        conn.execute(
            "DELETE FROM measurements WHERE source_app='ecg_delineation_ecg_logger'"
            " AND metric IN ('ecg_pr_duration_ms','ecg_qrs_duration_ms')"
        )
        conn.commit()

    n_ok = n_skip = n_poor = n_err = 0
    for session in sessions:
        res = _process_session(conn, session, recompute)
        status = res.get("status")
        if status == "ok":
            n_ok += 1
        elif status == "skip":
            n_skip += 1
        elif status == "poor_recording":
            n_poor += 1
        else:
            n_err += 1

    conn.commit()
    print(t(
        f"ECG R-Peaks: {n_ok} Sessions verarbeitet, {n_skip} übersprungen"
        f" (bereits vorhanden), {n_poor} poor_recording, {n_err} Fehler",
        f"ECG R-peaks: {n_ok} sessions processed, {n_skip} skipped"
        f" (already present), {n_poor} poor_recording, {n_err} errors",
    ))

    logger_sessions = conn.execute("""
        SELECT session_id, sample_rate_hz, device, person, source
        FROM ecg_logger_sessions
        ORDER BY session_id
    """).fetchall()

    nl_ok = nl_skip = nl_err = 0
    for session in logger_sessions:
        res = _process_ecg_logger_session(conn, session, recompute)
        status = res.get("status")
        if status == "ok":
            nl_ok += 1
        elif status == "skip":
            nl_skip += 1
        else:
            nl_err += 1

    conn.commit()
    print(t(
        f"ECG-Logger-Delineation: {nl_ok} Sessions verarbeitet, {nl_skip} übersprungen"
        f" (bereits vorhanden), {nl_err} ohne verwertbares Ergebnis",
        f"ECG Logger delineation: {nl_ok} sessions processed, {nl_skip} skipped"
        f" (already present), {nl_err} without usable result",
    ))


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "R-Peak-Erkennung aus EKG-Rohdaten beliebiger Quelle",
        "R-peak detection from ECG raw data from any source",
    ))
    parser.add_argument("--recompute", action="store_true",
                        help=t("Bestehende Ergebnisse neu berechnen",
                               "Recompute existing results"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    try:
        _run(conn, recompute=args.recompute)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
