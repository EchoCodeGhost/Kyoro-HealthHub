#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Pan-Tompkins Re-Analyse einer gespeicherten ECG-Session

@tier        research
@purpose.de  Führt Pan-Tompkins Re-Analyse auf gespeicherten ECG-Sessions durch
@purpose.en  Performs Pan-Tompkins re-analysis on stored ECG sessions
@method.de   Lädt Roh-Samples aus ecg_samples, führt Pan-Tompkins QRS-Detektion durch,
             leitet RR-Intervalle ab und vergleicht Ergebnisse mit Geräte-Klassifikation.
@method.en   Loads raw samples from ecg_samples, runs Pan-Tompkins QRS detection,
             derives RR intervals, and compares results against device classification.
@reads       ecg_samples
@writes      rr_intervals_manual
@refs        Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@limits.de   Heuristische QRS-Detektion. Genauigkeit abhängig von Signalqualität.
@limits.en   Heuristic QRS detection. Accuracy depends on signal quality.
@usage
    python3 scripts/analysis/analyse_ecg_session.py --list
    python3 scripts/analysis/analyse_ecg_session.py --session "2025-05-13T08:42:00"
    python3 scripts/analysis/analyse_ecg_session.py --date 2025-05-13
    python3 scripts/analysis/analyse_ecg_session.py --session "..." --plot
"""

import argparse
import math
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, get_own_person_id
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.ecg_signal import pan_tompkins
from modules.device_registry import is_device_active

_cfg = Config()
_PERSON = get_own_person_id()


def _row_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def _open_db():
    conn = open_db()
    conn.row_factory = _row_factory
    return conn


def list_sessions(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT datetime, classification, sample_rate_hz, duration_s,
               device_id, source
        FROM ecg_sessions
        WHERE person = ?
        ORDER BY datetime DESC
        LIMIT 50
        """,
        (_PERSON,),
    ).fetchall()

    if not rows:
        print(t("Keine ECG-Sessions gefunden.", "No ECG sessions found."))
        return

    print(t(
        f"{'Datum/Zeit':<26} {'Klassifikation':<14} {'Hz':>4} {'Dauer':>7}  {'Gerät'}",
        f"{'Date/Time':<26} {'Classification':<14} {'Hz':>4} {'Dur':>7}  {'Device'}",
    ))
    print("-" * 72)
    for r in rows:
        dur = f"{r['duration_s']:.0f}s" if r["duration_s"] else "—"
        hz  = str(r["sample_rate_hz"]) if r["sample_rate_hz"] else "—"
        dev = r["device_id"] or r["source"] or "—"
        cls = r["classification"] or "—"
        warn = "" if is_device_active(r["device_id"], r["datetime"]) else "  ⚠ Gerät laut Registry zu dem Zeitpunkt nicht getragen"
        print(f"  {r['datetime']:<26} {cls:<14} {hz:>4} {dur:>7}  {dev}{warn}")


def load_session(conn: sqlite3.Connection, session_dt: str):
    meta = conn.execute(
        "SELECT * FROM ecg_sessions WHERE datetime = ? AND person = ?",
        (session_dt, _PERSON),
    ).fetchone()
    if meta is None:
        return None, None
    samples = conn.execute(
        """
        SELECT uv FROM ecg_samples
        WHERE session_dt = ? AND session_person = ?
        ORDER BY sample_index
        """,
        (session_dt, _PERSON),
    ).fetchall()
    return meta, [r["uv"] for r in samples]


# Physiologische Filtergrenzen je nach Kontext (min_ms, max_ms)
RR_LIMITS = {
    # ── Alltag ────────────────────────────────────────────────────────────
    "wake":        (250.0, 2000.0),  # 30–240 bpm  — Standard Wach
    "sleep":       (300.0, 2500.0),  # 24–200 bpm  — Schlaf, tiefere Bradykardie möglich
    "training":    (200.0, 1500.0),  # 40–300 bpm  — Belastung, Sprints
    "postexercise":(250.0, 2000.0),  # 30–240 bpm  — Erholung nach Sport (wie Wach)
    "orthostatic": (250.0, 1800.0),  # 33–240 bpm  — Kipptisch / Lagetest
    # ── Klinik ────────────────────────────────────────────────────────────
    "icu":         (200.0, 3000.0),  # 20–300 bpm  — Intensivstation
    "anesthesia":  (180.0, 3500.0),  # 17–333 bpm  — GA / Opioid-Bradykardie möglich
    "sepsis":      (200.0, 2500.0),  # 24–300 bpm  — Tachykardie dominant, Spät-Bradykardie
    # ── Pädiatrie ─────────────────────────────────────────────────────────
    "pediatric":   (150.0, 1500.0),  # 40–400 bpm  — Neugeborene bis Jugendliche
}
POSTEXERCISE_WINDOW_MIN = 30  # Minuten nach Trainingsende → postexercise-Kontext
QUALITY_THRESHOLD = 0.20      # > 20 % gefilterte Intervalle → schlechtes Signal

_AUTO_CONTEXTS = ("orthostatic", "training", "postexercise", "sleep")  # Priorität


def _detect_context(conn, session_dt: str) -> str:
    """Auto-Erkennung: orthostatic > training > postexercise > sleep > wake.
    Nur Sessions mit bekanntem ts_end werden berücksichtigt."""
    from datetime import datetime, timedelta

    dt = session_dt[:19]  # YYYY-MM-DDTHH:MM:SS — Timezone abschneiden für Vergleich

    def _in_session(stype: str) -> bool:
        return conn.execute(
            """
            SELECT 1 FROM sessions
            WHERE person = ? AND type = ?
              AND ts_end IS NOT NULL
              AND substr(ts_start, 1, 19) <= ?
              AND substr(ts_end,   1, 19) >= ?
            LIMIT 1
            """,
            (_PERSON, stype, dt, dt),
        ).fetchone() is not None

    if _in_session("orthostatic"):
        return "orthostatic"
    if _in_session("training"):
        return "training"

    # Post-exercise: Trainingsende innerhalb der letzten POSTEXERCISE_WINDOW_MIN Minuten
    try:
        dt_obj = datetime.fromisoformat(dt)
        window_start = (dt_obj - timedelta(minutes=POSTEXERCISE_WINDOW_MIN)).strftime("%Y-%m-%dT%H:%M:%S")
        if conn.execute(
            """
            SELECT 1 FROM sessions
            WHERE person = ? AND type = 'training'
              AND ts_end IS NOT NULL
              AND substr(ts_end, 1, 19) > ?
              AND substr(ts_end, 1, 19) <= ?
            LIMIT 1
            """,
            (_PERSON, window_start, dt),
        ).fetchone():
            return "postexercise"
    except ValueError:
        pass

    if _in_session("sleep"):
        return "sleep"

    return "wake"


def _rr_from_peaks(peaks: list[int], fs: float) -> list[float]:
    return [(peaks[i + 1] - peaks[i]) / fs * 1000.0 for i in range(len(peaks) - 1)]


def _filter_rr(rr_ms: list[float], rr_min: float, rr_max: float) -> tuple[list[float], int]:
    """Entfernt physiologisch unmögliche RR-Intervalle. Gibt (gefiltert, n_entfernt) zurück."""
    filtered = [r for r in rr_ms if rr_min <= r <= rr_max]
    return filtered, len(rr_ms) - len(filtered)


def _basic_stats(rr_ms: list[float]) -> dict:
    if not rr_ms:
        return {}
    n = len(rr_ms)
    mean = sum(rr_ms) / n
    diffs = [abs(rr_ms[i + 1] - rr_ms[i]) for i in range(n - 1)]
    rmssd = math.sqrt(sum(d ** 2 for d in diffs) / len(diffs)) if diffs else 0.0
    cv = math.sqrt(sum((r - mean) ** 2 for r in rr_ms) / n) / mean if mean else 0.0
    return {
        "n_beats":  n + 1,
        "n_rr":     n,
        "mean_rr":  round(mean, 1),
        "mean_hr":  round(60000.0 / mean, 1) if mean else 0.0,
        "rmssd":    round(rmssd, 1),
        "cv_rr":    round(cv, 4),
        "min_rr":   round(min(rr_ms), 1),
        "max_rr":   round(max(rr_ms), 1),
    }


def analyse(session_dt: str, plot: bool = False, context: str = "auto") -> None:
    conn = _open_db()
    meta, samples = load_session(conn, session_dt)

    if meta is None:
        print(t(
            f"Session nicht gefunden: {session_dt}",
            f"Session not found: {session_dt}",
        ))
        sys.exit(1)

    fs = meta["sample_rate_hz"] or 300
    n_samples = len(samples)

    if context == "auto":
        context = _detect_context(conn, session_dt)

    rr_min, rr_max = RR_LIMITS.get(context, RR_LIMITS["wake"])
    _CONTEXT_LABEL = {
        "wake":        t("Wach",              "Wake"),
        "sleep":       t("Schlaf",            "Sleep"),
        "training":    t("Training",          "Training"),
        "postexercise":t("Nach Sport",        "Post-exercise"),
        "orthostatic": t("Orthostase-Test",   "Orthostatic test"),
        "icu":         t("Intensiv (ICU)",    "ICU"),
        "anesthesia":  t("Narkose",           "Anesthesia"),
        "sepsis":      t("Sepsis/Fieber",     "Sepsis/Fever"),
        "pediatric":   t("Pädiatrie",         "Pediatric"),
    }

    print(t("── ECG-Session ──────────────────────────────────", "── ECG Session ──────────────────────────────────"))
    print(f"  {t('Zeitpunkt', 'Timestamp')}      : {session_dt}")
    
    # Resolve device display name for human-readable output
    device_display = meta['device_id'] or meta['source'] or '—'
    try:
        from modules.identity_resolver import resolve_display_name
        if meta['device_id']:
            device_display = resolve_display_name(meta['device_id'])
    except Exception:
        pass  # Keep original value if resolution fails
    
    if meta["device_id"] and not is_device_active(meta["device_id"], session_dt):
        device_display += t("  ⚠ laut Registry zu diesem Zeitpunkt nicht getragen",
                             "  ⚠ registry says this device wasn't worn at this time")
    print(f"  {t('Gerät', 'Device')}         : {device_display}")
    print(f"  {t('Klassifikation', 'Classification')} : {meta['classification'] or '—'}  ({t('Gerät', 'device')})")
    print(f"  {t('Kontext', 'Context')}       : {_CONTEXT_LABEL.get(context, context)}  "
          f"(RR {rr_min:.0f}–{rr_max:.0f} ms)")
    print(f"  {t('Abtastrate', 'Sample rate')}   : {fs} Hz")
    print(f"  {t('Dauer', 'Duration')}        : {meta['duration_s']:.1f} s" if meta["duration_s"] else "  Dauer : —")
    print(f"  {t('Samples', 'Samples')}      : {n_samples}")
    print()

    if n_samples < int(0.5 * fs):
        print(t("Signal zu kurz für Pan-Tompkins (< 0.5 s).", "Signal too short for Pan-Tompkins (< 0.5 s)."))
        return

    print(t("Führe Pan-Tompkins QRS-Detektion durch …", "Running Pan-Tompkins QRS detection …"))
    peaks = pan_tompkins(samples, fs)
    rr_raw = _rr_from_peaks(peaks, fs)
    rr_ms, n_removed = _filter_rr(rr_raw, rr_min, rr_max)

    n_total = len(rr_raw)
    filter_rate = n_removed / n_total if n_total else 0.0
    poor_quality = filter_rate > QUALITY_THRESHOLD

    print(f"  {t('Erkannte R-Peaks', 'Detected R-peaks')}: {len(peaks)}")
    if n_removed:
        print(f"  {t('Artefakt-Intervalle entfernt', 'Artifact intervals removed')}: "
              f"{n_removed}/{n_total} ({filter_rate:.0%})")
    if poor_quality:
        print(t(
            "  ⚠  Schlechte Signalqualität — Klassifikation nicht zuverlässig.",
            "  ⚠  Poor signal quality — classification unreliable.",
        ))

    if len(rr_ms) < 2:
        print(t("Zu wenige verwertbare Schläge für RR-Analyse.", "Too few usable beats for RR analysis."))
        return

    stats = _basic_stats(rr_ms)
    print()
    print(t("── RR-Statistik (Pan-Tompkins) ──────────────────", "── RR Statistics (Pan-Tompkins) ─────────────────"))
    print(f"  {t('Schläge', 'Beats')}       : {stats['n_beats']}  ({t('nach Filterung', 'after filtering')})" if n_removed else
          f"  {t('Schläge', 'Beats')}       : {stats['n_beats']}")
    print(f"  {t('Mittl. RR', 'Mean RR')}   : {stats['mean_rr']} ms")
    print(f"  {t('Mittl. HR', 'Mean HR')}   : {stats['mean_hr']} bpm")
    print(f"  RMSSD      : {stats['rmssd']} ms")
    print(f"  CV_RR      : {stats['cv_rr']:.4f}")
    print(f"  {t('Min/Max RR', 'Min/Max RR')}: {stats['min_rr']} / {stats['max_rr']} ms")

    # Load calibrated thresholds if available
    calib_path = Path(_cfg.db_path).parent / "calibration" / "afdb_thresholds.json"
    tpr_thresh = 0.5743
    cv_thresh  = 0.1476
    if calib_path.exists():
        try:
            import json
            calib = json.loads(calib_path.read_text())
            tpr_thresh = calib.get("turning_pt_ratio", {}).get("threshold", tpr_thresh)
            cv_thresh  = calib.get("cv_rr", {}).get("threshold", cv_thresh)
        except Exception:
            pass

    from modules.rr_interval_algorithms import turning_point_ratio
    tpr = turning_point_ratio(rr_ms)
    cv  = stats["cv_rr"]

    afib_votes = 0
    if tpr is not None and tpr > tpr_thresh:
        afib_votes += 1
    if cv > cv_thresh:
        afib_votes += 1

    pt_classification = "POSSIBLE_AFIB" if afib_votes >= 2 else "SINUS"

    print()
    print(t("── Klassifikation ───────────────────────────────", "── Classification ───────────────────────────────"))
    print(f"  TPR         : {tpr:.4f}  ({t('Schwelle', 'threshold')} {tpr_thresh})")
    print(f"  CV_RR       : {cv:.4f}  ({t('Schwelle', 'threshold')} {cv_thresh})")
    pt_label = t("POSSIBLE_AFIB (unsicher — schlechtes Signal)", "POSSIBLE_AFIB (unreliable — poor signal)") \
               if pt_classification == "POSSIBLE_AFIB" and poor_quality else pt_classification
    print(f"  Pan-Tompkins: {pt_label}")
    print(f"  {t('Gerät', 'Device')}       : {meta['classification'] or '—'}")

    _DEVICE_AFIB = {"atrial_fibrillation", "possible_afib"}
    _DEVICE_SINUS = {"sinus_rhythm", "sinus"}
    dev_cls = (meta["classification"] or "").lower()
    pt_afib = pt_classification == "POSSIBLE_AFIB"
    dev_afib = dev_cls in _DEVICE_AFIB
    dev_sinus = dev_cls in _DEVICE_SINUS
    mismatch = (not poor_quality) and meta["classification"] \
               and ((pt_afib and dev_sinus) or (not pt_afib and dev_afib))
    if mismatch:
        print()
        print(t(
            "  ⚠  Klassifikation weicht ab — manuelle Prüfung empfohlen.",
            "  ⚠  Classifications differ — manual review recommended.",
        ))

    if plot:
        _plot(samples, peaks, fs, session_dt, meta["classification"], pt_classification)


def _plot(samples, peaks, fs, session_dt, device_cls, pt_cls):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        time = np.arange(len(samples)) / fs
        peak_times = [p / fs for p in peaks]
        peak_vals  = [samples[p] for p in peaks]

        out_dir = Path(_cfg.analyses_dir) / "manual"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_dt = session_dt.replace(":", "-").replace(" ", "_")
        out_path = out_dir / f"ecg_pt_{safe_dt}.png"

        fig, ax = plt.subplots(figsize=(14, 4))
        ax.plot(time, samples, lw=0.6, color="#2c7bb6", label="ECG (µV)")
        ax.scatter(peak_times, peak_vals, color="#d7191c", s=20, zorder=5,
                   label=f"R-Peaks (n={len(peaks)})")
        ax.set_xlabel(t("Zeit (s)", "Time (s)"))
        ax.set_ylabel("µV")
        ax.set_title(
            f"ECG  {session_dt}\n"
            f"{t('Gerät', 'Device')}: {device_cls or '—'}  |  Pan-Tompkins: {pt_cls}"
        )
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"\n  → {out_path}")
    except ImportError:
        print(t("  (matplotlib nicht verfügbar, kein Plot)", "  (matplotlib not available, no plot)"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--list",    action="store_true", help=t("Alle Sessions auflisten", "List all sessions"))
    parser.add_argument("--session", metavar="DATETIME",  help=t("Session-Zeitstempel", "Session datetime"))
    parser.add_argument("--date",    metavar="YYYY-MM-DD", help=t("Alle Sessions dieses Tages", "All sessions on date"))
    parser.add_argument("--plot",    action="store_true", help=t("EKG-Plot speichern", "Save ECG plot"))
    parser.add_argument(
        "--context",
        choices=["auto", "wake", "sleep", "training", "postexercise",
                 "orthostatic", "icu", "anesthesia", "sepsis", "pediatric"],
        default="auto",
        help=t("RR-Filterkontext (Standard: auto)", "RR filter context (default: auto)"),
    )
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.list or (not args.session and not args.date):
        conn = _open_db()
        list_sessions(conn)
        return

    conn = _open_db()

    if args.date:
        rows = conn.execute(
            "SELECT datetime FROM ecg_sessions WHERE person = ? AND datetime LIKE ? ORDER BY datetime",
            (_PERSON, f"{args.date}%"),
        ).fetchall()
        if not rows:
            print(t(f"Keine Sessions am {args.date}.", f"No sessions on {args.date}."))
            sys.exit(1)
        for row in rows:
            analyse(row["datetime"], plot=args.plot, context=args.context)
            print()
    else:
        analyse(args.session, plot=args.plot, context=args.context)


if __name__ == "__main__":
    main()
