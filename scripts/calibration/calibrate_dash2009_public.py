#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Dash 2009 Schwellenwert-Kalibrierung gegen öffentlichen Wrist-PPG-AFib-Datensatz

@tier        calibrated
@purpose.de  Kalibriert die Dash-2009-Schwellenwerte (Shannon-Entropie, CV_RR) für
             optische Handgelenks-PPG-Quellen (Polar Vantage V3/Loop Gen 2/Ignite 2)
             gegen einen echten, klinisch annotierten Wrist-PPG-AFib-Datensatz —
             im Gegensatz zu MIT-BIH AFDB (nur ECG, kein PPG, s. calibrate_afib_thresholds.py)
             signaltyp-passend für Dash 2009.
@purpose.en  Calibrates the Dash 2009 thresholds (Shannon entropy, CV_RR) for optical
             wrist-PPG sources (Polar Vantage V3/Loop Gen 2/Ignite 2) against a real,
             clinically annotated wrist-PPG AFib dataset — unlike MIT-BIH AFDB (ECG
             only, no PPG, see calibrate_afib_thresholds.py) this is signal-type
             appropriate for Dash 2009.
@method.de   Liest MAT-v7.3/HDF5-Dateien aus data/calibration/zenodo_afib_ppg/extracted/
             (s. download_ppg_afib_zenodo.py) via h5py — scipy.io.loadmat unterstützt
             v7.3 nicht (verifiziert per --inspect). Pro Subjekt (01–08) liegt EINE
             durchgehende ECG-Referenzaufnahme (<subjekt>_ECG_01.mat: 500Hz-Rohsignal,
             beat-indizierte QRSindex + rr + AF_annotation) und mehrere kürzere,
             zeitversetzte PPG-Handgelenksaufnahmen (<subjekt>_PPG_NN.mat: 100Hz
             PPG_GREEN, EIGENE recording_starttime/-startday, KEINE eigene AFib-
             Annotation). Die AFib-Zuordnung für PPG-Beats kommt daher NICHT aus der
             PPG-Datei selbst, sondern über Zeit-Alignment: PPG-Segment-Startzeit
             minus ECG-Referenz-Startzeit (aus recording_starttime, ASCII "HH:MM:SS",
             plus Tag-des-Monats aus recording_startday — kein volles Datum in der
             Quelle, s. @limits) ergibt einen Offset in Sekunden relativ zum ECG-
             Start; jeder PPG-detektierte Beat-Zeitpunkt wird per Offset in die ECG-
             Zeitachse projiziert und per nächstgelegenem QRSindex-Beat (searchsorted)
             mit dessen AF_annotation-Wert gelabelt. PPG-Peaks werden aus PPG_GREEN
             per Bandpass (0,5–5Hz Pulswellenband) + Peak-Erkennung mit BLOCKWEISE
             (30s) adaptiver Prominenz-Schwelle gewonnen — ein einzelner globaler
             Schwellenwert versagt, da Handgelenks-PPG durch Bewegungsartefakte massive
             lokale Amplitudenschwankungen zeigt (empirisch: Bloecke desselben Files
             reichten von SD~4000 bis SD~285000 ADC-Einheiten). Zusaetzlich Bewegungs-
             Gate: dieselben Dateien liefern Accelerometer_X/Y/Z mit — Bloecke, deren
             Beschleunigungs-Magnitude-SD in den bewegungsreichsten ACCEL_QUANTILE_CUT
             (75%-Perzentil) DIESES Files liegt, werden komplett von der Peak-Suche
             ausgeschlossen statt trotzdem verrauschte Peaks zu liefern. RR-Intervalle,
             die eine ausgeschlossene Luecke ueberbruecken wuerden, werden verworfen
             (Block-Index-Kontinuitaetspruefung). Die verbleibende RR-Folge durchlaeuft
             danach zusaetzlich die lokale Median-Ausreisser-Filterung aus
             modules/rr_interval_algorithms.filter_beat_artifacts (dieselbe Funktion, die
             urspruenglich fuer compute_orthostatic_detection.py entwickelt wurde) —
             faengt einzelne Fehl-Peaks ab, die auch innerhalb eines "guten" Blocks
             auftreten. RR-Intervalle → 5-Min-Fenster → Shannon-Entropie
             (shannon_entropy_rr) + CV_RR pro Fenster → ROC/Youden-J. Gleiches
             Sliding-Window- und ROC-Muster wie calibrate_afib_thresholds.py.
@method.en   Reads MAT v7.3/HDF5 files from data/calibration/zenodo_afib_ppg/extracted/
             (see download_ppg_afib_zenodo.py) via h5py — scipy.io.loadmat doesn't
             support v7.3 (verified via --inspect). Per subject (01–08) there is ONE
             continuous ECG reference recording (<subject>_ECG_01.mat: 500Hz raw
             signal, beat-indexed QRSindex + rr + AF_annotation) and several shorter,
             time-shifted wrist PPG recordings (<subject>_PPG_NN.mat: 100Hz PPG_GREEN,
             its OWN recording_starttime/-startday, NO AFib annotation of its own).
             AFib labeling for PPG beats therefore does NOT come from the PPG file
             itself but via time alignment: PPG segment start time minus ECG
             reference start time (from recording_starttime, ASCII "HH:MM:SS", plus
             day-of-month from recording_startday — no full date in the source, see
             @limits) gives an offset in seconds relative to ECG start; each
             PPG-detected beat time is projected onto the ECG timeline via that
             offset and labeled with the AF_annotation value of the nearest preceding
             QRSindex beat (searchsorted). PPG peaks are extracted from PPG_GREEN via
             a bandpass (0.5–5Hz pulse-wave band) plus peak detection with a
             BLOCK-WISE (30s) adaptive prominence threshold — a single global
             threshold fails because wrist PPG shows massive local amplitude swings
             from motion artifact (empirically: blocks within the same file ranged
             from SD~4000 to SD~285000 ADC units). Additionally, a motion gate: the
             same files also carry Accelerometer_X/Y/Z — blocks whose acceleration-
             magnitude SD falls in the most motion-heavy ACCEL_QUANTILE_CUT (75th
             percentile) of THAT file are excluded from peak search entirely instead
             of still yielding noisy peaks. RR intervals that would bridge an excluded
             gap are dropped (block-index continuity check). The remaining RR sequence
             then also passes through the local-median outlier filter from
             modules/rr_interval_algorithms.filter_beat_artifacts (the same function
             originally built for compute_orthostatic_detection.py) — catches
             individual mis-detected peaks that occur even within an otherwise "good"
             block. RR intervals → 5-min windows → Shannon entropy (shannon_entropy_rr)
             + CV_RR per window → ROC/Youden's J. Same sliding-window and ROC pattern
             as calibrate_afib_thresholds.py.
@reads       data/calibration/zenodo_afib_ppg/extracted/*.mat
@writes      data/calibration/dash2009_thresholds.json,
             data/calibration/dash2009_public_calibration.csv
@refs        Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z
             Bacevičius J, Abramikas Ž, Badaras I et al. (2022). Long-term electrocardiogram and wrist-based photoplethysmogram recordings with annotated atrial fibrillation episodes [Data set]. Zenodo. doi:10.5281/zenodo.5815074
             (dataset: 8 subjects, one continuous multi-day ECG reference + several
             wrist-PPG segments per subject, beat-to-beat AFib annotation on the ECG)

@relevance.de  Ermöglicht die Kalibrierung von Algorithmen und Schwellenwerten, essentiell für die Datenqualität
@relevance.en  Enables calibration of algorithms and thresholds, essential for data quality
@limits.de   Zeit-Alignment zwischen PPG-Segment und ECG-Referenz beruht auf
             Tag-des-Monats OHNE Monat/Jahr (Quelldateien liefern kein volles Datum) —
             ein Monatswechsel innerhalb der Aufnahmedauer eines Subjekts wird per
             Heuristik erkannt (Tagesdifferenz >20 → Wraparound angenommen), kann aber
             ±1 Tag ungenau sein; betrifft nur Subjekte, deren Aufnahme sehr nah an
             einem Monatsende beginnt. PPG-Peak-Erkennung ist eigene, nicht klinisch
             validierte Bandpass+Prominenz-Heuristik, kein Referenzalgorithmus —
             Handgelenks-PPG ist inhärent bewegungsartefaktanfälliger als Brustgurt-
             EKG, ein Teil der erkannten "Beats" sind vermutlich Artefakte (grobe
             Plausibilitätsfilterung nur über RR-Bereich 200–3000ms, plus Bewegungs-
             Gate + lokale Ausreisser-Filterung, s. @method). Der resultierende
             AUC-Wert spiegelt daher sowohl die Guete der Dash-2009-Schwellenwerte ALS
             AUCH die Guete dieser eigenen Peak-Erkennung wider — beides ist nicht
             getrennt auswertbar. Das Bewegungs-Gate schliesst die bewegungsreichsten
             Abschnitte pro Datei komplett aus — falls AFib-Episoden bei dieser Person
             systematisch waehrend Ruhe ODER systematisch waehrend Aktivitaet auftreten
             (unbekannt, nicht geprueft), koennte das Gate eine Klassen-Selektions-
             verzerrung einfuehren statt nur Rauschen zu entfernen; nicht quantifiziert.
             Datensatz-Lizenz: "Other (Non-Commercial)" — nur für nicht-kommerzielle
             Kalibrierung, Rohdaten bleiben ungetrackt (.gitignore).
@limits.en   Time alignment between PPG segment and ECG reference relies on
             day-of-month WITHOUT month/year (source files carry no full date) — a
             month rollover within a subject's recording span is detected heuristically
             (day difference >20 → assumed wraparound) but can be off by ±1 day;
             affects only subjects whose recording starts very close to a month
             boundary. PPG peak detection is an own, not clinically validated
             bandpass+prominence heuristic, not a reference algorithm — wrist PPG is
             inherently more motion-artifact-prone than chest-strap ECG, some detected
             "beats" are likely artifacts (only a coarse RR-range plausibility filter,
             200–3000ms, plus the motion gate + local outlier filter, see @method, is
             applied). The resulting AUC therefore reflects both the quality of the
             Dash 2009 thresholds AND the quality of this own peak detection — the two
             cannot be evaluated separately. The motion gate excludes the most
             motion-heavy portions of each file entirely — if this person's AFib
             episodes systematically occur during rest OR systematically during
             activity (unknown, not checked), the gate could introduce a class
             selection bias rather than only removing noise; not quantified. Dataset
             license: "Other (Non-Commercial)" — non-commercial calibration use only,
             raw data stays untracked (.gitignore).
@usage
    python3 scripts/calibration/download_ppg_afib_zenodo.py   # once, ~7 GB
    python3 scripts/calibration/calibrate_dash2009_public.py --inspect <file.mat>
    python3 scripts/calibration/calibrate_dash2009_public.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.rr_interval_algorithms import filter_beat_artifacts, shannon_entropy_rr

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "calibration" / "zenodo_afib_ppg" / "extracted"
OUT_DIR  = Path(__file__).parent.parent.parent / "data" / "calibration"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_S = 300   # 5-Minuten-Fenster, konsistent mit calibrate_afib_thresholds.py
MIN_BEATS = 30
PPG_BAND_HZ = (0.5, 5.0)     # Pulswellenband, ~30-300 bpm
PEAK_MIN_DISTANCE_S = 0.3    # min. 200 bpm Beat-Abstand
PEAK_BLOCK_S = 30            # Blockbreite fuer adaptive Prominenz-Schwelle + Motion-Gate
PEAK_PROMINENCE_FACTOR = 0.3
RR_MIN_MS, RR_MAX_MS = 200, 3000
ACCEL_QUANTILE_CUT = 0.75    # je Datei die bewegungsreichsten 25% der Bloecke ausschliessen
ARTIFACT_PCT_MAX = 0.20      # s. modules.rr_interval_algorithms.filter_beat_artifacts


def _h5_ascii(arr) -> str:
    """Dekodiert ein MAT-v7.3-char-Array (als ASCII-Codepoints in uint16 gespeichert)."""
    return "".join(chr(int(c)) for c in np.asarray(arr).flatten())


def _deref_strings(f, ref_array) -> list:
    """Loest HDF5-Objektreferenzen auf (MAT-v7.3 speichert String-Cell-Arrays als
    Referenzen in die '#refs#'-Gruppe) und dekodiert sie als ASCII."""
    return [_h5_ascii(f[r][()]) for r in np.asarray(ref_array).flatten()]


def _read_signal_header(f) -> dict:
    """Liest signalHeader/{signal_labels,samples_in_record} (beide referenz-indiziert)
    und gibt {label: samples_per_record} zurueck — samples_in_record entspricht bei
    diesem Datensatz direkt der Abtastrate in Hz (1 Record = 1 Sekunde, EDF-Konvention,
    verifiziert: samples_in_record[ECG]=500 * num_data_records stimmt exakt mit der
    ECG-Signallaenge ueberein, analog fuer PPG_GREEN)."""
    sh = f["signalHeader"]
    labels = _deref_strings(f, sh["signal_labels"][()])
    sir = [float(f[r][()].flatten()[0]) for r in np.asarray(sh["samples_in_record"][()]).flatten()]
    return dict(zip(labels, sir))


def inspect(path: Path) -> None:
    """Gibt die Top-Level-Struktur einer MAT-v7.3-Datei aus (via h5py, da
    scipy.io.loadmat v7.3/HDF5-Dateien nicht liest) — vor dem echten Lauf einmal
    gegen mindestens eine ECG- und eine PPG-Datei ausfuehren."""
    with h5py.File(path, "r") as f:
        print(f"Keys in {path.name}:")
        for k in f.keys():
            if k == "#refs#":
                continue
            obj = f[k]
            if isinstance(obj, h5py.Dataset):
                print(f"  {k}: shape={obj.shape} dtype={obj.dtype}")
            else:
                print(f"  {k}/ (group): {list(obj.keys())}")
        if "signalHeader" in f:
            print("  signalHeader ->", _read_signal_header(f))
        if "recording_starttime" in f:
            print("  recording_starttime:", _h5_ascii(f["recording_starttime"][()]))
        if "recording_startday" in f:
            print("  recording_startday:", _h5_ascii(f["recording_startday"][()]))


def _time_of_day_s(f) -> float:
    hh, mm, ss = (int(x) for x in _h5_ascii(f["recording_starttime"][()]).split(":"))
    return hh * 3600 + mm * 60 + ss


def _day_of_month(f) -> int:
    return int(_h5_ascii(f["recording_startday"][()]))


def _day_diff(day_ppg: int, day_ecg: int) -> int:
    """Vorzeichenbehaftete Tagesdifferenz aus reinen Tag-des-Monats-Werten (die
    Quelldateien speichern kein volles Datum). Ein scheinbar grosser Ruecksprung
    (z.B. Tag 02 nach Tag 29) wird als Monatswechsel interpretiert, nicht als
    echter Ruecksprung in der Zeit — s. @limits fuer die Praezisions-Einschraenkung."""
    diff = day_ppg - day_ecg
    if diff < -20:
        diff += 30
    elif diff > 20:
        diff -= 30
    return diff


def _load_ecg_reference(path: Path) -> dict:
    """Laedt nur die fuer das Alignment noetigen Felder (QRSindex, AF_annotation,
    Start-Zeit) — NICHT das rohe 500Hz-ECG-Signal selbst (wird hier nicht gebraucht,
    ~2.4GB pro Subjekt unnoetig)."""
    with h5py.File(path, "r") as f:
        af = f["AF_annotation"][()].flatten().astype(bool)
        qrs = f["QRSindex"][()].flatten()
        fs = _read_signal_header(f)["ECG"]
        return {
            "beat_times_s": qrs[:-1] / fs,  # Start jedes RR-Intervalls; len == len(af)
            "af": af,
            "start_day": _day_of_month(f),
            "start_time_s": _time_of_day_s(f),
            "duration_s": qrs[-1] / fs,
        }


def _block_motion_scores(accel_mag: np.ndarray, fs_accel: float, n_blocks: int) -> np.ndarray:
    """Bewegungs-Score (Standardabweichung der Beschleunigungs-Betrag-Magnitude)
    je PEAK_BLOCK_S-Block, an denselben Blockindizes wie die PPG-Peak-Erkennung
    ausgerichtet — trotz unterschiedlicher Abtastrate (Accel meist 50Hz, PPG 100Hz
    bei diesem Datensatz)."""
    block_a = int(fs_accel * PEAK_BLOCK_S)
    scores = np.zeros(n_blocks)
    for bi in range(n_blocks):
        seg = accel_mag[bi * block_a:(bi + 1) * block_a]
        scores[bi] = seg.std() if len(seg) else np.inf
    return scores


def _detect_ppg_peaks(ppg: np.ndarray, fs: float,
                       accel_mag: "np.ndarray | None" = None, fs_accel: float = 50.0
                       ) -> "tuple[np.ndarray, np.ndarray]":
    """Bandpass (Pulswellenband) + blockweise adaptive Prominenz-Schwelle statt eines
    globalen Schwellenwerts — Handgelenks-PPG zeigt massive lokale Amplituden-
    schwankungen durch Bewegungsartefakte (s. @method). Zusaetzlich: Bloecke mit den
    ACCEL_QUANTILE_CUT staerksten Bewegungs-Scores (aus Accelerometer_X/Y/Z-Magnitude,
    die in denselben Dateien mitgeliefert wird) werden komplett von der Peak-Suche
    ausgeschlossen statt trotzdem verrauschte Peaks zu erzeugen — Peak-Erkennung
    waehrend Bewegung ist bei optischem Handgelenks-PPG unzuverlaessig unabhaengig
    von der Prominenz-Schwelle.

    Gibt (peak_sample_idx, peak_block_idx) zurueck — der Block-Index pro Peak
    erlaubt es load_ppg_record(), RR-Intervalle zu verwerfen, die eine ausgeschlossene
    Bewegungs-Luecke ueberbruecken wuerden."""
    b, a = butter(3, PPG_BAND_HZ, btype="band", fs=fs)
    filt = filtfilt(b, a, ppg)
    block = int(fs * PEAK_BLOCK_S)
    n_blocks = len(filt) // block

    good_block = np.ones(n_blocks, dtype=bool)
    if accel_mag is not None and len(accel_mag) > 0:
        motion = _block_motion_scores(accel_mag, fs_accel, n_blocks)
        cutoff = np.quantile(motion, ACCEL_QUANTILE_CUT)
        good_block = motion <= cutoff

    peaks: list = []
    block_idx: list = []
    for bi in range(n_blocks):
        if not good_block[bi]:
            continue
        start = bi * block
        seg = filt[start:start + block]
        local_std = seg.std()
        if local_std < 1e-9:
            continue
        pk, _ = find_peaks(seg, distance=int(fs * PEAK_MIN_DISTANCE_S), prominence=local_std * PEAK_PROMINENCE_FACTOR)
        peaks.extend((pk + start).tolist())
        block_idx.extend([bi] * len(pk))
    return np.asarray(peaks, dtype=float), np.asarray(block_idx, dtype=int)


def load_ppg_record(ecg_ref: dict, ppg_path: Path) -> "tuple[list[float], list[bool]] | None":
    """Liest ein PPG-Segment, erkennt Pulswellen-Peaks (mit Bewegungs-Gate + lokaler
    Artefaktfilterung, s. @method), und ordnet jedem daraus gewonnenen RR-Intervall
    ein AFib-Label ueber die zeitliche Ausrichtung zum ECG-Referenzfile desselben
    Subjekts zu (PPG-Segmente tragen selbst KEINE AFib-Annotation, s. @method)."""
    with h5py.File(ppg_path, "r") as f:
        ppg = f["PPG_GREEN"][()].flatten().astype(float)
        header = _read_signal_header(f)
        fs = header["PPG_GREEN"]
        ppg_day = _day_of_month(f)
        ppg_time_s = _time_of_day_s(f)
        accel_mag = None
        fs_accel = 50.0
        if {"Accelerometer_X", "Accelerometer_Y", "Accelerometer_Z"} <= f.keys():
            ax = f["Accelerometer_X"][()].flatten()
            ay = f["Accelerometer_Y"][()].flatten()
            az = f["Accelerometer_Z"][()].flatten()
            accel_mag = np.sqrt(ax**2 + ay**2 + az**2)
            fs_accel = header.get("Accelerometer_X", fs_accel)

    offset_s = _day_diff(ppg_day, ecg_ref["start_day"]) * 86400 + (ppg_time_s - ecg_ref["start_time_s"])
    if offset_s + len(ppg) / fs < 0 or offset_s > ecg_ref["duration_s"]:
        return None  # kein zeitlicher Ueberlapp mit der ECG-Referenz

    peaks, block_idx = _detect_ppg_peaks(ppg, fs, accel_mag, fs_accel)
    if len(peaks) < 2:
        return None

    # RR nur zwischen Peaks aus demselben oder unmittelbar benachbarten Bloecken
    # bilden — sonst wuerde eine ausgeschlossene Bewegungs-Luecke (s. _detect_ppg_peaks)
    # als ein einzelnes, fälschlich langes RR-Intervall durchschlagen.
    contiguous = np.diff(block_idx) <= 1

    peak_times_ecg_rel = offset_s + peaks / fs
    rr_ms = np.diff(peak_times_ecg_rel) * 1000.0
    mid_times = (peak_times_ecg_rel[:-1] + peak_times_ecg_rel[1:]) / 2.0

    in_range = (mid_times >= 0) & (mid_times <= ecg_ref["duration_s"])
    idx = np.searchsorted(ecg_ref["beat_times_s"], mid_times, side="right") - 1
    idx = np.clip(idx, 0, len(ecg_ref["af"]) - 1)
    is_afib = ecg_ref["af"][idx]

    plausible = contiguous & in_range & (rr_ms >= RR_MIN_MS) & (rr_ms <= RR_MAX_MS)
    if not plausible.any():
        return None
    rr_ms_list = rr_ms[plausible].tolist()
    is_afib_list = is_afib[plausible].tolist()

    # Lokale Median-Ausreisser-Filterung (s. modules.rr_interval_algorithms.filter_beat_artifacts)
    # auf die verbleibende, chronologische RR-Folge — faengt einzelne falsch erkannte
    # Peaks ab, die auch innerhalb eines bewegungsarmen, "guten" Blocks auftreten
    # koennen und vom Motion-Gate allein nicht ausgeschlossen werden.
    filtered_rr, keep_mask = filter_beat_artifacts(rr_ms_list, ARTIFACT_PCT_MAX, return_mask=True)
    filtered_afib = [a for a, k in zip(is_afib_list, keep_mask) if k]
    if len(filtered_rr) < 2:
        return None
    return filtered_rr, filtered_afib


def extract_windows(rr_ms: list, is_afib: list,
                     window_beats: int = 150, step_beats: int = 75) -> list:
    rows = []
    for start in range(0, len(rr_ms) - window_beats, step_beats):
        chunk_rr   = rr_ms[start:start + window_beats]
        chunk_afib = is_afib[start:start + window_beats]
        if len(chunk_rr) < MIN_BEATS:
            continue
        afib_frac = sum(chunk_afib) / len(chunk_afib)
        if 0.1 < afib_frac < 0.9:
            continue  # ambige Fenster überspringen
        h_norm = shannon_entropy_rr(chunk_rr)
        mean = sum(chunk_rr) / len(chunk_rr)
        sd = (sum((r - mean) ** 2 for r in chunk_rr) / len(chunk_rr)) ** 0.5
        cv_rr = sd / mean if mean > 0 else float("nan")
        rows.append({"label": int(afib_frac >= 0.9), "h_norm": h_norm, "cv_rr": round(cv_rr, 4)})
    return rows


def roc_analysis(labels: list, scores: list):
    """Identisches ROC/Youden-J-Verfahren wie calibrate_afib_thresholds.py."""
    import math
    pairs = [(s, lb) for s, lb in zip(scores, labels) if not math.isnan(s)]
    pairs.sort(key=lambda x: x[0], reverse=True)
    n_pos = sum(lb for _, lb in pairs)
    n_neg = len(pairs) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None

    thresholds, tprs, fprs = [], [], []
    tp = fp = 0
    prev_s = None
    for score, label in pairs:
        if score != prev_s and prev_s is not None:
            thresholds.append(prev_s)
            tprs.append(tp / n_pos)
            fprs.append(fp / n_neg)
        if label == 1:
            tp += 1
        else:
            fp += 1
        prev_s = score
    thresholds.append(prev_s)
    tprs.append(tp / n_pos)
    fprs.append(fp / n_neg)

    auc = sum((fprs[i] - fprs[i-1]) * (tprs[i] + tprs[i-1]) / 2 for i in range(1, len(tprs)))

    best_j, best_thresh = -1.0, thresholds[0]
    for thresh, tpr, fpr in zip(thresholds, tprs, fprs):
        j = tpr - fpr  # Youden's J
        if j > best_j:
            best_j, best_thresh = j, thresh

    return {"auc": round(auc, 4), "best_threshold": round(best_thresh, 4), "best_j": round(best_j, 4)}


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--inspect":
        inspect(Path(sys.argv[2]))
        return

    ecg_files = sorted(DATA_DIR.glob("*_ECG_*.mat"))
    if not ecg_files:
        print(f"Keine ECG-Referenzdateien in {DATA_DIR}. Bitte zuerst download_ppg_afib_zenodo.py ausführen.")
        sys.exit(1)

    print(f"Dash-2009-Kalibrierung: {len(ecg_files)} Subjekt(e) in {DATA_DIR}")
    all_windows: list = []
    for ecg_path in ecg_files:
        subject = ecg_path.name.split("_ECG_")[0]
        ppg_files = sorted(DATA_DIR.glob(f"{subject}_PPG_*.mat"))
        ecg_ref = _load_ecg_reference(ecg_path)
        print(f"  Subjekt {subject}: ECG-Referenz ({ecg_ref['duration_s']/3600:.1f}h, "
              f"AF-Anteil {ecg_ref['af'].mean():.1%}) + {len(ppg_files)} PPG-Segment(e)")
        n_subject_windows = 0
        for ppg_path in ppg_files:
            result = load_ppg_record(ecg_ref, ppg_path)
            if result is None:
                print(f"    [{ppg_path.name}] kein Überlapp / kein Signal — übersprungen")
                continue
            rr_ms, is_afib = result
            windows = extract_windows(rr_ms, is_afib)
            all_windows.extend(windows)
            n_subject_windows += len(windows)
            print(f"    [{ppg_path.name}] {len(rr_ms)} RR, {len(windows)} Fenster")
        print(f"    → {n_subject_windows} Fenster für Subjekt {subject}")

    if not all_windows:
        print("Keine auswertbaren Fenster.", file=sys.stderr)
        sys.exit(1)

    import csv
    csv_path = OUT_DIR / "dash2009_public_calibration.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["label", "h_norm", "cv_rr"])
        writer.writeheader()
        writer.writerows(all_windows)
    print(f"  → {csv_path}")

    labels = [w["label"] for w in all_windows]
    roc_h  = roc_analysis(labels, [w["h_norm"] for w in all_windows])
    roc_cv = roc_analysis(labels, [w["cv_rr"] for w in all_windows])

    if not roc_h or not roc_cv:
        print("ROC-Analyse fehlgeschlagen (keine positiven/negativen Fenster).", file=sys.stderr)
        sys.exit(1)

    result = {
        "dash2009_h_threshold":  roc_h["best_threshold"],
        "dash2009_cv_threshold": roc_cv["best_threshold"],
        "auc_h":  roc_h["auc"],
        "auc_cv": roc_cv["auc"],
        "n_windows": len(all_windows),
        "n_afib_windows": sum(labels),
        "source": "zenodo_5815074_public",
        "calibrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    out_path = OUT_DIR / "dash2009_thresholds.json"
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)
    print(f"\n  → {out_path}")
    print(f"  H-Schwelle:  {roc_h['best_threshold']}  (AUC={roc_h['auc']})")
    print(f"  CV-Schwelle: {roc_cv['best_threshold']}  (AUC={roc_cv['auc']})")


if __name__ == "__main__":
    main()
