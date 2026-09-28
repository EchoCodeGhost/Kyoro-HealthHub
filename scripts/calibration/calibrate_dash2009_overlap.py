#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Dash 2009 Selbst-Kalibrierung aus Geräte-Überlappungsfenstern

@tier        calibrated
@purpose.de  Kalibriert die Dash-2009-Schwellenwerte (Shannon-Entropie, CV_RR) aus
             Zeitfenstern, in denen eine validierte Quelle (Polar H10/H7 Brustgurt,
             tateno_glass-Algorithmus) UND eine optische Handgelenks-Quelle
             (Vantage V3/Loop Gen 2/Ignite 2) gleichzeitig Daten geliefert haben —
             personenspezifische Alternative/Ergänzung zur öffentlichen
             Datensatz-Kalibrierung (calibrate_dash2009_public.py).
@purpose.en  Calibrates the Dash 2009 thresholds (Shannon entropy, CV_RR) from time
             windows where a validated source (Polar H10/H7 chest strap,
             tateno_glass algorithm) AND an optical wrist source (Vantage V3/
             Loop Gen 2/Ignite 2) both delivered data simultaneously — a
             person-specific alternative/addition to the public-dataset
             calibration (calibrate_dash2009_public.py).
@method.de   Findet 5-Min-Fenster mit ppi_raw-Daten von beiden Gerätegruppen
             gleichzeitig (echtes paralleles Tragen). Geräte werden über
             modules/device_registry.sensor_type(device_id) klassifiziert
             (chest_strap vs. optical_wrist_gps) — NICHT über einen Vergleich der
             rohen device-Spalte gegen eine feste Menge semantischer Namen wie
             "polar_vantage" (ppi_raw.device enthält die pseudonymisierte device_id,
             z.B. "DEV-394bbcad", nie einen semantischen String; ein früherer
             Set-Vergleich griff deshalb NIE, unabhängig von tatsächlich
             vorhandenem Parallel-Tragen — 0 Fenster war ein Bug, nicht fehlende
             Daten, s. @limits). Nutzt den tateno_glass-Flag der validierten
             Quelle als Pseudo-Ground-Truth (KEINE ärztliche Diagnose!) und sucht
             per ROC/Youden-J die Dash-2009-Schwelle, die am besten mit dieser
             Referenz übereinstimmt.
@method.en   Finds 5-min windows with ppi_raw data from both device groups
             simultaneously (genuine parallel wear). Devices are classified via
             modules/device_registry.sensor_type(device_id) (chest_strap vs.
             optical_wrist_gps) — NOT by comparing the raw device column against a
             fixed set of semantic names like "polar_vantage" (ppi_raw.device
             holds the pseudonymized device_id, e.g. "DEV-394bbcad", never a
             semantic string; an earlier set-comparison therefore NEVER matched,
             regardless of actual parallel wear time present — 0 windows was a
             bug, not missing data, see @limits). Uses the validated source's
             tateno_glass flag as pseudo-ground-truth (NOT a clinical diagnosis!)
             and searches via ROC/Youden's J for the Dash 2009 threshold that best
             agrees with this reference.
@reads       ppi_raw
@writes      data/calibration/dash2009_self_thresholds.json
@refs        Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
             Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z

@relevance.de  Ermöglicht die Kalibrierung von Algorithmen und Schwellenwerten, essentiell für die Datenqualität
@relevance.en  Enables calibration of algorithms and thresholds, essential for data quality
@limits.de   Pseudo-Ground-Truth, keine echte Diagnose — tateno_glass selbst ist nur
             AFDB-kalibriert, nicht perfekt. n=1 (eine Person), Stichprobengröße
             hängt von tatsächlicher Parallel-Tragezeit ab und kann klein/null sein.
             Ohne echte AFib-Episoden in den Überlappungsfenstern kalibriert dieses
             Skript im Wesentlichen nur die Falsch-Positiv-Rate auf Normalrhythmus,
             nicht die Sensitivität für echtes Vorhofflimmern. Geräte-Klassifikation
             über sensor_type stammt aus der Registry-Konfiguration — ein Gerät ohne
             (korrekten) sensor_type-Eintrag fließt stillschweigend in kein Fenster
             ein (weder validated noch optical), statt einen Fehler zu werfen.
@limits.en   Pseudo-ground-truth, not a clinical diagnosis — tateno_glass itself is
             only AFDB-calibrated, not perfect. n=1 (single person), sample size
             depends on actual parallel wear time and may be small/zero. Without
             real AFib episodes in the overlap windows, this script essentially
             only calibrates the false-positive rate on normal rhythm, not
             sensitivity to genuine atrial fibrillation. Device classification via
             sensor_type comes from the registry configuration — a device without
             a (correct) sensor_type entry silently contributes to neither bucket
             (validated or optical) rather than raising an error.
@usage
    python3 scripts/calibration/calibrate_dash2009_overlap.py
    python3 scripts/calibration/calibrate_dash2009_overlap.py --person max
"""
import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import open_db
from modules.device_registry import sensor_type as _sensor_type
from modules.rr_interval_algorithms import detect_tateno_glass, shannon_entropy_rr
from health_config import Config, get_own_person_id

_cfg = Config()

OUT_DIR = Path(__file__).parent.parent.parent / "data" / "calibration"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Klassifikation ueber den Geraete-Registry-sensor_type (device_registry.sensor_type),
# NICHT ueber eine feste Menge semantischer Namen — ppi_raw.device enthaelt die
# pseudonymisierte device_id (z.B. "DEV-394bbcad"), keine semantischen Strings wie
# "polar_vantage". Ein frueherer Set-Vergleich gegen {"polar_h10", "polar_vantage", ...}
# hat deshalb NIE gegriffen (0 Fenster, unabhaengig von echtem Parallel-Tragen) — s.
# @limits/@method fuer die Korrektur.
VALIDATED_SENSOR_TYPES = {"chest_strap"}
OPTICAL_SENSOR_TYPES   = {"optical_wrist_gps"}

TPR_THRESHOLD  = _cfg.arrhythmia_tpr_threshold
RMSSD_CONFIRM  = _cfg.arrhythmia_rmssd_confirm

WINDOW_MIN = 5
MIN_BEATS  = 30


def _rr_stats(ppis: list[float]) -> tuple[float, float]:
    n = len(ppis)
    mean = sum(ppis) / n
    diffs = [abs(ppis[i + 1] - ppis[i]) for i in range(n - 1)]
    rmssd = math.sqrt(sum(d * d for d in diffs) / len(diffs)) if diffs else 0.0
    return mean, rmssd


def find_overlap_windows(conn, person: str) -> list[dict]:
    """5-Min-Fenster, in denen sowohl eine validierte als auch eine optische
    Quelle gleichzeitig Beat-to-Beat-Daten haben (echtes Parallel-Tragen)."""
    rows = conn.execute(
        "SELECT datetime, pulse_ms, device FROM ppi_raw "
        "WHERE person=? AND pulse_ms BETWEEN 300 AND 1800 ORDER BY datetime",
        (person,),
    ).fetchall()
    if not rows:
        return []

    buckets: dict[datetime, dict[str, list[float]]] = {}
    for dt_str, pulse_ms, device in rows:
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            dt = datetime.fromisoformat(dt_str[:19])
        bucket = dt.replace(second=0, microsecond=0, minute=(dt.minute // WINDOW_MIN) * WINDOW_MIN)
        st = _sensor_type(device)
        group = "validated" if st in VALIDATED_SENSOR_TYPES else ("optical" if st in OPTICAL_SENSOR_TYPES else None)
        if group is None:
            continue
        buckets.setdefault(bucket, {"validated": [], "optical": []})[group].append(pulse_ms)

    windows = []
    for bucket, groups in sorted(buckets.items()):
        val_rr, opt_rr = groups["validated"], groups["optical"]
        if len(val_rr) < MIN_BEATS or len(opt_rr) < MIN_BEATS:
            continue
        _, val_rmssd = _rr_stats(val_rr)
        flag, tpr, _ = detect_tateno_glass(val_rr, val_rmssd, TPR_THRESHOLD, RMSSD_CONFIRM)
        h_norm = shannon_entropy_rr(opt_rr)
        opt_mean, _ = _rr_stats(opt_rr)
        opt_sd = math.sqrt(sum((x - opt_mean) ** 2 for x in opt_rr) / len(opt_rr))
        cv_rr = opt_sd / opt_mean if opt_mean > 0 else float("nan")
        windows.append({
            "bucket": bucket.isoformat(),
            "label": flag,
            "tpr_reference": round(tpr, 4),
            "h_norm": h_norm,
            "cv_rr": round(cv_rr, 4),
        })
    return windows


def roc_youden(labels: list[int], scores: list[float]) -> dict | None:
    pairs = [(s, lb) for s, lb in zip(scores, labels) if not math.isnan(s)]
    pairs.sort(key=lambda x: x[0], reverse=True)
    n_pos = sum(lb for _, lb in pairs)
    n_neg = len(pairs) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    tp = fp = 0
    prev_s, best_j, best_thresh = None, -1.0, pairs[0][0]
    tprs, fprs = [], []
    for score, label in pairs:
        if score != prev_s and prev_s is not None:
            tpr, fpr = tp / n_pos, fp / n_neg
            tprs.append(tpr); fprs.append(fpr)
            j = tpr - fpr
            if j > best_j:
                best_j, best_thresh = j, prev_s
        if label == 1:
            tp += 1
        else:
            fp += 1
        prev_s = score
    tprs.append(tp / n_pos); fprs.append(fp / n_neg)
    auc = sum((fprs[i] - fprs[i-1]) * (tprs[i] + tprs[i-1]) / 2 for i in range(1, len(tprs)))
    return {"auc": round(abs(auc), 4), "best_threshold": round(best_thresh, 4), "best_j": round(best_j, 4)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--person", default=None)
    args = ap.parse_args()

    conn = open_db()
    person = args.person or get_own_person_id()

    windows = find_overlap_windows(conn, person)
    n_afib = sum(w["label"] for w in windows)
    print(f"{len(windows)} Überlappungsfenster gefunden ({n_afib} mit tateno_glass-Verdachts-Flag)")

    if len(windows) < 20:
        print("Zu wenige Überlappungsfenster für eine belastbare Selbst-Kalibrierung "
              "(< 20). Ergebnis wird trotzdem geschrieben, aber mit Warnhinweis.",
              file=sys.stderr)

    result = {
        "n_windows": len(windows),
        "n_afib_windows": n_afib,
        "person": person,
        "calibrated": datetime.now().date().isoformat(),
        "source": "self_overlap_pseudo_groundtruth",
        "warning": "Pseudo-Ground-Truth aus tateno_glass, keine klinische Diagnose. "
                   "n=1 Person. Bei n_afib_windows=0 kalibriert dies nur die "
                   "Falsch-Positiv-Rate, nicht die Sensitivität.",
    }

    if not windows:
        result["dash2009_h_threshold"] = None
        result["dash2009_cv_threshold"] = None
    else:
        labels = [w["label"] for w in windows]
        roc_h  = roc_youden(labels, [w["h_norm"] for w in windows])
        roc_cv = roc_youden(labels, [w["cv_rr"] for w in windows])
        result["dash2009_h_threshold"]  = roc_h["best_threshold"] if roc_h else None
        result["dash2009_cv_threshold"] = roc_cv["best_threshold"] if roc_cv else None
        result["auc_h"]  = roc_h["auc"] if roc_h else None
        result["auc_cv"] = roc_cv["auc"] if roc_cv else None

    out_path = OUT_DIR / "dash2009_self_thresholds.json"
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)
    print(f"→ {out_path}")
    if windows:
        print(f"  H-Schwelle:  {result.get('dash2009_h_threshold')}  (AUC={result.get('auc_h')})")
        print(f"  CV-Schwelle: {result.get('dash2009_cv_threshold')}  (AUC={result.get('auc_cv')})")

    conn.close()


if __name__ == "__main__":
    main()
