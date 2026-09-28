#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Arrhythmia detection from all available sources.

@tier        research
@purpose.de  Erkennt Arrhythmie-Episoden aus mehreren Quellen und annotiert jede
             mit einer Konfidenzstufe entsprechend der Güte der Rohdatenquelle.
@purpose.en  Detects arrhythmia episodes from multiple sources, annotating each
             with a confidence level reflecting the quality of the source data.
@method.de   Quellenabhängige Konfidenz-Hierarchie. Verschiedene Geräte messen
             Verschiedenes: Apple 30-s-Snapshot-EKG (getriggert), ECG Logger
             Langzeit (1 h+), Polar H10 Brustgurt-RR (5-Min-Fenster), optische
             PPG (bei Arrhythmie systematisch ungenauer). ppi_raw → 5-Min-Fenster
             → ppi_windows → Episodenaggregation.
             Zusätzlich: Bigeminie-Erkennung über RR-Intervall-Alternanz
             (Short-Long-Short-Long, das Timing-Korrelat von vorzeitigem
             Schlag + kompensatorischer Pause) — geräteweise gestreamt über
             ppi_raw, Segmentierung bei Aufzeichnungslücken, mind. 3
             zusammenhängende S-L-Zyklen gelten als Episode (unterscheidet
             anhaltende Bigeminie von vereinzelten Extrasystolen). Anlass:
             ein Smartphone-PPG-Herzrhythmus-Scan (FibriCheck, s.
             import_fibricheck.py) markierte während des Schlafs eine
             mögliche Extrasystolen-Bigeminie-Episode — dieselbe
             Mustererkennung läuft jetzt kontinuierlich auf den eigenen
             Wearable-Rohdaten statt nur bei Einzelmessungen. FibriCheck-
             Berichte selbst fließen zusätzlich als eigene, vom Expertengremium
             gegengeprüfte Episodenquelle ein (fibricheck_sessions).
@method.en   Source-dependent confidence hierarchy. Devices measure different
             things: Apple 30 s snapshot ECG (triggered), ECG Logger long-term
             (1 h+), Polar H10 chest-strap RR (5-min windows), optical PPG
             (systematically less accurate under arrhythmia). ppi_raw → 5-min
             windows → ppi_windows → episode aggregation.
             Additionally: bigeminy detection via RR-interval alternation
             (short-long-short-long, the timing correlate of a premature beat
             + compensatory pause) — streamed per device over ppi_raw,
             segmented on recording gaps, at least 3 consecutive S-L cycles
             count as an episode (distinguishes sustained bigeminy from
             isolated extrasystoles). Motivation: a smartphone PPG heart-
             rhythm scan (FibriCheck, s. import_fibricheck.py) flagged a
             possible extrasystole/bigeminy episode during sleep — the same
             pattern recognition now runs continuously over the person's own
             wearable raw data instead of only at one-off spot checks.
             FibriCheck reports themselves are additionally ingested as their
             own expert-panel-reviewed episode source (fibricheck_sessions).
@thresholds
    high     :: de=Apple ECG (FDA, Perez 2019) / ECG Logger (TPR+SampEn Single-Lead) / FibriCheck mit Arzt-Gegenprüfung :: en=Apple ECG (FDA, Perez 2019) / ECG Logger (TPR+SampEn single-lead) / FibriCheck with physician review
    moderate :: de=Polar H10/H7 via ppi_raw, TPR AFDB-kalibriert (Schwelle 0.5743, AUC 0.882); Bigeminie-Alternanz-Heuristik auf EKG-Qualität; FibriCheck ohne Arzt-Gegenprüfung :: en=Polar H10/H7 via ppi_raw, TPR AFDB-calibrated (threshold 0.5743, AUC 0.882); bigeminy alternation heuristic on ECG-quality data; FibriCheck without physician review
    moderate :: de=Optische PPG via Dash 2009 (Shannon-Entropie+CV), nicht auf AFDB validiert :: en=Optical PPG via Dash 2009 (Shannon entropy+CV), not AFDB-validated
    low      :: de=Unbekannte Quellen (CV-Heuristik-Fallback, nicht validiert); Bigeminie-Alternanz-Heuristik auf optischer PPG :: en=Unknown sources (CV heuristic fallback, not validated); bigeminy alternation heuristic on optical PPG
@reads       ppi_raw, ecg_sessions, ecg_logger_sessions, fibricheck_sessions,
             devices, sessions, data/calibration/afdb_thresholds.json
             (tateno_glass/sampentropy), data/calibration/dash2009_thresholds.json
             (öffentlicher Datensatz, s. calibrate_dash2009_public.py),
             data/calibration/dash2009_self_thresholds.json (Geräte-Überlappung,
             s. calibrate_dash2009_overlap.py)
@writes      ppi_windows: 5-min statistics from ppi_raw; column sensor_mode
             ('ecg' | a device_registry sensor_type | NULL) is the effective
             measurement mode used for algorithm routing below, resolved via
             modules/ppi_provenance.py (data-derived, not device-derived — a
             device can have more than one measurement mode, e.g. a watch's
             continuous optical PPG vs. its own occasional ECG lead, both
             landing in ppi_raw under the same device_id)
             arrhythmie_episoden: contiguous abnormal periods; columns
             confidence ('high'|'moderate'|'low'), source (raw-data origin);
             detection_method 'bigeminy_rr_alternation' for the RR-alternation
             episodes, 'premature_beat_rr' for single/clustered premature-beat
             episodes (n_fenster reused as cluster size: 1=isolated, 2=couplet,
             3=triplet, >=3=run — no separate label column), 'fibricheck_
             <result_code>_<version>' for ingested FibriCheck reports
@refs        Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
             Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z
             Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
             Mannhart D, Lischer M, Knecht S et al. (2023). Clinical Validation of 5 Direct-to-Consumer Wearable Smart Devices to Detect Atrial Fibrillation: BASEL Wearable Study. JACC Clinical Electrophysiology, 9(2):232-242. doi:10.1016/j.jacep.2022.09.011
             Cuesta P, Lado MJ, Vila XA, Alonso R (2014). Detection of premature ventricular contractions using the RR-interval signal: a simple algorithm for mobile devices. Technology and Health Care, 22(4):651-656. doi:10.3233/THC-140818
             Han D, Bashar SK, Mohagheghian F et al. (2020). Premature Atrial and Ventricular Contraction Detection using Photoplethysmographic Data from a Smartwatch. Sensors (Basel), 20(19):5683. doi:10.3390/s20195683

@relevance.de  Ermöglicht die Erkennung von Herzrhythmusstörungen, essentiell für die kardiologische Überwachung
@relevance.en  Enables detection of cardiac arrhythmias, essential for cardiological monitoring
@limits.de   TPR setzt gleichmäßige HR voraus. Trainingsfenster (±15 min Puffer)
             werden mit arrhythmie_flag=0 gespeichert, da körperliche Belastung
             systematisch false positives erzeugt. Optische Quellen sind bei
             Arrhythmie unzuverlässig; Fallback-Heuristik ist nicht validiert.
             RMSSD-Bestätigungskriterium (rmssd >= RMSSD_CONFIRM) ist eine lokale
             Erweiterung und im Original Tateno & Glass 2001 nicht enthalten — das
             Original verwendet ausschließlich den TPR-Schwellwert. Die Erweiterung
             erhöht die Spezifität auf Kosten der Sensitivität; RMSSD_CONFIRM ist
             ein heuristischer Konfigurationsparameter ohne publizierte Validierung.
             Bigeminie-Erkennung: Die Schwellen (BIGEMINY_ZERO_BAND_BPM,
             BIGEMINY_MIN_PAIRS, BIGEMINY_ANGLE_SD_MAX_DEG) sind die publizierten
             Werte aus Han et al. 2020 (Sensors 20(19):5683, PPG-Bigeminie/
             Trigeminie-Erkennung, Smartwatch + MIMIC-III-Pulsoximetrie validiert,
             Spez. 97%/PPV 81%/NPV 94%/Genauigkeit 92%) — s. modules/rr_interval_algorithms.py
             detect_bigeminy_runs() fuer den genauen Umfang der Replikation (die
             drei Zahlenschwellen ja, das vollstaendige 9-Quadranten-Poincare-Raster
             und die beschleunigungsbasierte Bewegungsartefakt-Erkennung nein).
             Weil Han et al. 2020 ausschliesslich auf PPG validierten, ist die
             Uebertragung auf EKG-Brustgurt-RR (hier ebenfalls verwendet, da die
             Methode intervallbasiert und geraeteunabhaengig arbeitet) selbst nicht
             separat validiert — praeziser als PPG, aber ein unbestaetigter, wenn
             auch plausibler Transfer. Deshalb 'moderate', nicht 'high' Konfidenz
             fuer alle Quellenmodalitaeten (s. BIGEMINY_CONFIDENCE_BY_MODE), und
             keine aerztliche Gegenpruefung dieser Implementierung. Segmentierung
             bei Lücken >30s kann eine echte, ueber Mitternacht/Sensor-
             Kurzunterbrechung hinweg andauernde Alternanz künstlich in zwei
             Episoden aufteilen.
             Einzelschlag-PVC-Erkennung (premature_beat_rr): implementiert
             Cuesta et al. 2014 (Technology and Health Care 22(4):651-656,
             doi:10.3233/THC-140818, Praematuritaet+kompensatorische Pause,
             MIT-BIH-validiert, Sens. 90,13%/Spez. 82,52%, AUC 0,928) — s.
             modules/rr_interval_algorithms.py detect_premature_beats_cuesta()
             fuer den genauen Umfang der Replikation (Feature-Formeln exakt,
             Klassifikation ueber Naechster-Klassenschwerpunkt anstelle der
             nicht publizierten LDA-Koeffizienten). Komplementaer zu
             detect_bigeminy_runs — erkennt Einzelschlaege/kurze Cluster
             (Couplet/Triplet/Run), keine anhaltende Alternanz; die Autoren
             selbst nennen Bigeminie-Couplets als Versagensfall ihres
             Verfahrens. Cluster werden ausschliesslich ueber unmittelbar
             aufeinanderfolgende Beat-Indizes gebildet, nicht ueber zeitliche
             Naehe — zwei isolierte PVCs, die nur zufaellig kurz hintereinander
             auftreten, bleiben bewusst getrennte Episoden.
             Nur 'ecg'/'chest_strap'-Quellen werden ueberhaupt durch den
             Detektor geschickt (Geraeteklassen-Routing wie SENSOR_TYPE_ROUTING,
             nicht nur Konfidenz-Abstufung) — ein erster Testlauf gegen echte
             Daten zeigte, dass optische/PPG-Quellen eine Falsch-Positiv-
             Explosion erzeugen (>99% aller Funde stammten von 3 optischen
             Geraeten, EKG-Brustgurt lieferte eine plausible Groessenordnung).
             Synthetischer Test bestaetigt die Ursache: die Klassifikation
             wird ab ca. 50ms Beat-zu-Beat-Rauschen (SD) messbar falsch-
             positiv — PPG-Rohdaten unter Alltagsbedingungen ueberschreiten
             das regelmaessig, EKG-Brustgurt praktisch nie. Konsistent mit
             Cuesta et al.s eigenem Validierungsumfang (nur MIT-BIH/EKG).
             FibriCheck-Episoden: feste 60-s-Dauer angenommen (keine Beat-Statistik
             im Bericht verfügbar), result_code-Mapping deckt nur bisher bekannte
             Formulierungen ab (s. import_fibricheck.py @limits).
@limits.en   TPR assumes stationary HR. Training windows (±15 min buffer) are
             stored with arrhythmie_flag=0 because physical exertion systematically
             produces false positives. Optical sources are unreliable under
             arrhythmia; the fallback heuristic is not validated.
             RMSSD confirmation guard (rmssd >= RMSSD_CONFIRM) is a local addition
             not present in the original Tateno & Glass 2001 paper — the original
             uses the TPR threshold alone. This addition increases specificity at
             the cost of sensitivity; RMSSD_CONFIRM is a heuristic configuration
             parameter without published validation. External comparison (Mannhart
             et al. 2023, BASEL Wearable Study): even well-funded, FDA-cleared
             consumer devices (Apple Watch 6, Samsung Galaxy Watch 3) reach only
             85%/75% sensitivity/specificity against a 12-lead ECG reference, with
             ~25% of recordings inconclusive — the AUC gap between this pipeline's
             moderate-confidence sources and the tateno_glass chest-strap reference
             (0.657-0.713 vs. 0.882) is consistent with that general order of
             magnitude for PPG-based detection, not a pipeline-specific failure.
             Bigeminy detection: the thresholds (BIGEMINY_ZERO_BAND_BPM,
             BIGEMINY_MIN_PAIRS, BIGEMINY_ANGLE_SD_MAX_DEG) are the published
             values from Han et al. 2020 (Sensors 20(19):5683, PPG bigeminy/
             trigeminy detection, validated on smartwatch + MIMIC-III pulse-
             oximetry data, Sp 97%/PPV 81%/NPV 94%/accuracy 92%) — see
             modules/rr_interval_algorithms.py detect_bigeminy_runs() for the exact
             scope of replication (the three numeric thresholds yes, the full
             9-quadrant Poincare grid and accelerometer-based motion-artifact
             rejection no). Because Han et al. 2020 validated exclusively on
             PPG, applying the method to chest-strap ECG RR (also used here,
             since the method itself is interval-based and device-agnostic)
             is not separately validated — more precise raw data than PPG, but
             an unconfirmed, if plausible, transfer. Hence 'moderate', not
             'high' confidence for every source modality (see
             BIGEMINY_CONFIDENCE_BY_MODE), and no physician review of this
             implementation. Segmenting on gaps >30s can artificially split a
             genuine alternation run that spans midnight or a brief sensor
             dropout into two episodes.
             Single-beat PVC detection (premature_beat_rr): implements Cuesta
             et al. 2014 (Technology and Health Care 22(4):651-656, doi:
             10.3233/THC-140818, prematurity + compensatory pause, MIT-BIH-
             validated, Se 90.13%/Sp 82.52%, AUC 0.928) — see
             modules/rr_interval_algorithms.py detect_premature_beats_cuesta()
             for the exact scope of replication (feature formulas exact,
             classification via nearest-class-centroid instead of the
             unpublished LDA coefficients). Complementary to
             detect_bigeminy_runs — detects single beats/short clusters
             (couplet/triplet/run), not sustained alternation; the authors
             themselves name bigeminy couplets as a failure case of their
             method. Clusters are formed only from immediately consecutive
             beat indices, not temporal proximity — two isolated PVCs that
             happen to occur close together in time remain deliberately
             separate episodes.
             Only 'ecg'/'chest_strap' sources are run through the detector at
             all (device-class routing like SENSOR_TYPE_ROUTING, not just a
             confidence downgrade) — an initial test run against real data
             showed optical/PPG sources produce a false-positive explosion
             (>99% of all findings came from 3 optical devices, chest-strap
             ECG produced a plausible order of magnitude). A synthetic test
             confirms the cause: classification turns measurably false-
             positive above roughly 50ms of beat-to-beat noise (SD) — PPG raw
             data routinely exceeds that under real-world conditions,
             chest-strap ECG practically never does. Consistent with Cuesta
             et al.'s own validation scope (MIT-BIH/ECG only).
             FibriCheck episodes: assumes a fixed 60-s duration (no beat-level
             statistics available in the report), result_code mapping only
             covers previously seen phrasings (s. import_fibricheck.py @limits).
@usage
    python compute_arrhythmia.py
    python compute_arrhythmia.py --person PER-XXXXXXXX
"""

import argparse
import math
import sqlite3
import statistics
from collections import deque
from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import resolve_timezone
from modules.ppi_provenance import mode_from_sources
from modules.rr_interval_algorithms import (
    detect_tateno_glass, detect_sampentropy, detect_dash2009, detect_bigeminy_runs,
    detect_premature_beats_cuesta,
)
_cfg = _Cfg()

DB_PATH         = _cfg.db_path
FENSTER_S       = 300   # 5 Minuten
MIN_BEATS       = 20    # Mindest-Beats pro Fenster
MAX_GAP_S       = FENSTER_S * 2
MAX_EPISODE_MIN = 240

# Configurable thresholds — override in health_config.json: clinical.arrhythmia
MIN_FENSTER          = _cfg.arrhythmia_min_windows
TPR_THRESHOLD        = _cfg.arrhythmia_tpr_threshold
RMSSD_CONFIRM        = _cfg.arrhythmia_rmssd_confirm
DASH2009_H_THRESHOLD = _cfg.arrhythmia_dash2009_h_threshold
DASH2009_CV_THRESHOLD= _cfg.arrhythmia_dash2009_cv_threshold
SAMPEN_THRESHOLD     = _cfg.arrhythmia_sampen_threshold
SAMPEN_CV_THRESHOLD  = _cfg.arrhythmia_sampen_cv_threshold

# Kalibrierungsdatei überschreibt Config-Defaults (data/calibration/afdb_thresholds.json)
_calib_path = Path(_cfg.db_path).parent / "calibration" / "afdb_thresholds.json"
if _calib_path.exists():
    try:
        import json as _json
        _calib = _json.loads(_calib_path.read_text())
        TPR_THRESHOLD   = _calib.get("turning_pt_ratio", {}).get("threshold", TPR_THRESHOLD)
        SAMPEN_THRESHOLD= _calib.get("sampen", {}).get("threshold", SAMPEN_THRESHOLD)
        SAMPEN_CV_THRESHOLD = _calib.get("cv_rr", {}).get("threshold", SAMPEN_CV_THRESHOLD)
    except Exception:
        pass

# Dash-2009-Kalibrierung: zwei mögliche Quellen, per config wählbar.
#   public — calibrate_dash2009_public.py, öffentlicher Wrist-PPG-AFib-Datensatz (Zenodo 5815074)
#   self   — calibrate_dash2009_overlap.py, Geräte-Überlappungsfenster in den eigenen Daten
# Modus via clinical.arrhythmia.dash2009_calibration_mode:
#   'alternative' (Default) — self bevorzugt, falls genug Gesamtfenster (>= _DASH_MIN_SELF_WINDOWS)
#                              UND genug AFib-verdächtige Fenster (>= _DASH_MIN_SELF_AFIB_WINDOWS,
#                              sonst ist die ROC-Schwelle bei so wenigen Positivbeispielen reines
#                              Rauschen), sonst public, sonst Code-Default aus health_config.json
#   'additive'   — gewichteter Mittelwert aus public+self (Gewicht = n_windows)
#   'public' / 'self' — nur diese eine Quelle, sonst Code-Default
#   'off'        — Kalibrierungsdateien ignorieren, immer Code-Default
_DASH_MIN_SELF_WINDOWS = 20
_DASH_MIN_SELF_AFIB_WINDOWS = 20
_dash_calib_dir = Path(_cfg.db_path).parent / "calibration"


def _load_dash_calib(name: str) -> dict | None:
    p = _dash_calib_dir / name
    if not p.exists():
        return None
    try:
        d = _json.loads(p.read_text())
    except Exception:
        return None
    if d.get("dash2009_h_threshold") is None or d.get("dash2009_cv_threshold") is None:
        return None
    return d


_dash_mode   = _cfg.arrhythmia_dash2009_calibration_mode
_dash_public = _load_dash_calib("dash2009_thresholds.json")
_dash_self   = _load_dash_calib("dash2009_self_thresholds.json")
_dash_self_ok = bool(
    _dash_self
    and _dash_self.get("n_windows", 0) >= _DASH_MIN_SELF_WINDOWS
    and _dash_self.get("n_afib_windows", 0) >= _DASH_MIN_SELF_AFIB_WINDOWS
)

if _dash_mode == "public" and _dash_public:
    DASH2009_H_THRESHOLD  = _dash_public["dash2009_h_threshold"]
    DASH2009_CV_THRESHOLD = _dash_public["dash2009_cv_threshold"]
elif _dash_mode == "self" and _dash_self_ok:
    DASH2009_H_THRESHOLD  = _dash_self["dash2009_h_threshold"]
    DASH2009_CV_THRESHOLD = _dash_self["dash2009_cv_threshold"]
elif _dash_mode == "additive" and (_dash_public or _dash_self_ok):
    _entries = []
    if _dash_public:
        _entries.append((_dash_public["dash2009_h_threshold"], _dash_public["dash2009_cv_threshold"],
                          max(1, _dash_public.get("n_windows", 1))))
    if _dash_self_ok:
        _entries.append((_dash_self["dash2009_h_threshold"], _dash_self["dash2009_cv_threshold"],
                          _dash_self["n_windows"]))
    _w = sum(x[2] for x in _entries)
    DASH2009_H_THRESHOLD  = round(sum(h * w for h, _, w in _entries) / _w, 4)
    DASH2009_CV_THRESHOLD = round(sum(c * w for _, c, w in _entries) / _w, 4)
elif _dash_mode == "alternative":
    if _dash_self_ok:
        DASH2009_H_THRESHOLD  = _dash_self["dash2009_h_threshold"]
        DASH2009_CV_THRESHOLD = _dash_self["dash2009_cv_threshold"]
    elif _dash_public:
        DASH2009_H_THRESHOLD  = _dash_public["dash2009_h_threshold"]
        DASH2009_CV_THRESHOLD = _dash_public["dash2009_cv_threshold"]
# 'off' oder keine passende Kalibrierungsdatei → DASH2009_*_THRESHOLD bleibt Code-Default
# Adaptive, personenbezogene Belastungserkennung statt festem HF-Schwellwert.
# Grund: ein fester Absolut-Schwellwert (frueher HR_EXERCISE_MAX=110bpm)
# versagt bei Personen mit chronisch erhoehter, aber STABILER Ruhe-HF (z.B.
# POTS) — Belastungs- und Ruhe-HF-Verteilung koennen sich dann fast komplett
# ueberlappen (empirisch geprueft: Median 140 bpm waehrend geloggter
# Trainingseinheiten vs. 138 bpm ausserhalb, auf realen Daten dieser
# Nutzerin), wodurch entweder fast alle Schlaege als "Belastung" verworfen
# werden (zu hoher Informationsverlust) oder der Schwellwert gar nicht mehr
# trennt. Stattdessen: ein gleitender Basiswert (Median der letzten
# ADAPTIVE_BASELINE_WINDOW_S Sekunden) pro Geraet, ein Schlag zaehlt nur dann
# als Belastung, wenn er MEHR ALS ADAPTIVE_EXERCISE_ELEVATION_BPM ueber
# diesem eigenen, aktuellen Basiswert liegt — erkennt den ANSTIEG bei
# Belastungsbeginn, unabhaengig davon, auf welchem absoluten Niveau die
# Ruhe-HF der Person liegt. Ergaenzt (nicht ersetzt) die geloggten
# Trainingssession-Fenster (_in_training_window) fuer laengere Belastungen,
# bei denen der gleitende Basiswert selbst irgendwann nachzieht.
# Beide Schwellwerte (Fenstergroesse, Elevationsschwelle) sind eigene,
# NICHT literaturvalidierte Konfigurationsentscheidungen — s. Docstring von
# _RollingHRBaseline fuer die Einordnung.
ADAPTIVE_BASELINE_WINDOW_S    = 600   # 10 Minuten gleitender Kontext
ADAPTIVE_EXERCISE_ELEVATION_BPM = 25.0  # Anstieg ueber den eigenen Basiswert, der als Belastung zaehlt
ADAPTIVE_MIN_CONTEXT_S         = 120   # Mindest-Zeitspanne im Puffer, bevor der Basiswert als belastbar gilt


class _RollingHRBaseline:
    """Gleitender HF-Basiswert je Geraet fuer adaptive Belastungserkennung
    (s. Konstanten-Kommentar oben fuer die Begruendung). Nicht literatur-
    validiert — eine begruendete, aber selbst gewaehlte Heuristik, die einen
    nachweislich nicht funktionierenden festen HF-Schwellwert ersetzt.

    Verwendung: is_exercise(dt, hr) VOR dem Hinzufuegen des aktuellen Schlags
    aufrufen (der Schlag beeinflusst seinen eigenen Vergleichs-Basiswert
    nicht), dann update(dt, hr)."""

    def __init__(self, window_s: float = ADAPTIVE_BASELINE_WINDOW_S,
                 elevation_bpm: float = ADAPTIVE_EXERCISE_ELEVATION_BPM,
                 min_context_s: float = ADAPTIVE_MIN_CONTEXT_S):
        self.window_s = window_s
        self.elevation_bpm = elevation_bpm
        self.min_context_s = min_context_s
        self._buf: deque = deque()  # (datetime, hr)

    def _purge(self, dt: datetime) -> None:
        while self._buf and (dt - self._buf[0][0]).total_seconds() > self.window_s:
            self._buf.popleft()

    def is_exercise(self, dt: datetime, hr: float) -> bool:
        self._purge(dt)
        if not self._buf:
            return False
        span_s = (dt - self._buf[0][0]).total_seconds()
        if span_s < self.min_context_s:
            return False  # zu wenig Kontext fuer einen belastbaren Basiswert — konservativ: nicht ausschliessen
        baseline = statistics.median(h for _, h in self._buf)
        return hr > baseline + self.elevation_bpm

    def update(self, dt: datetime, hr: float) -> None:
        self._buf.append((dt, hr))
        self._purge(dt)

# ── Source/Device → Algorithmus-Routing ───────────────────────────────────────
# Lookup-Reihenfolge: device_id zuerst, dann source, dann ALGO_DEFAULT.
# Neue Quellen hier eintragen, sobald der Importer bereit ist.
def _load_serial_map() -> dict[str, str]:
    """Liest serial_real → device_id aus KYORO_CONFIG_DIR/identity.db."""
    db_path = KYORO_CONFIG_DIR / "identity.db"
    if not db_path.exists():
        return {}
    try:
        with sqlite3.connect(db_path) as c:
            return {s: d for s, d in c.execute(
                "SELECT serial_real, device_id FROM device_serial_map"
            ).fetchall()}
    except Exception:
        return {}

# Rohe Seriennummern / BT-MACs → standardisierter device_id (aus identity.db)
SERIAL_TO_DEVICE: dict[str, str] = _load_serial_map()

# Sensor-type-based algorithm routing (replaces device_id-based routing)
# This mapping uses sensor_type instead of specific device models for better
# abstraction and compatibility with pseudonymized device identifiers.
SENSOR_TYPE_ROUTING: dict[str, str] = {
    # Echte EKG-Ableitung (s. modules/ppi_provenance.py) — ob Brustgurt-EKG
    # (ECG Logger) oder ein Watch-EKG-Lead (compute_ecg_rpeaks.py): in beiden
    # Faellen sind die RR-Intervalle direkt aus der elektrischen Erregung
    # gewonnen, nicht aus dem Blutvolumenpuls. Dieselbe Kalibrierung wie
    # 'chest_strap' gilt daher unabhaengig davon, welchen sensor_type das
    # liefernde Geraet sonst in der Registry hat (z.B. eine optische Uhr mit
    # zusaetzlicher EKG-Funktion) → Tateno & Glass.
    'ecg':                'tateno_glass',
    # ECG-Qualität (Brustgurt) → Tateno & Glass
    'chest_strap':        'tateno_glass',
    # Optisch Handgelenk mit echten kontinuierlichen Beat-to-Beat-PPG-Daten
    # (bestätigt anhand realer ppi_raw-Exporte: Vantage V3, Loop Gen 2,
    # Ignite 2 liefern durchgehende ganztägige PPI-Aufzeichnung, nicht nur
    # Trainingsfenster) → Dash 2009, methodisch für PPG entwickelt (Shannon-
    # Entropie+CV, MIMIC-II-Pulsoximetrie)
    'optical_wrist_gps': 'dash2009',    # Polar Vantage V3, Loop Gen 2, Ignite 2
    'optical_wrist':     'dash2009',    # Optische Handgelenk-PPG mit bestätigten Rohdaten
    'ppg_sensor':        'dash2009',    # Polar Verity Sense (Armband/Clip) — optisches PPG, keine EKG-Ableitung
    # Optisch, aber (noch) ohne bestätigte durchgehende Beat-to-Beat-PPG-Rohdaten
    # → SampEn (Stub), niedrigere Konfidenz bis Gegenteil belegt ist.
    'ring':              'sampentropy',   # Oura Ring
    'smartphone':        'sampentropy',   # Kamera-PPG (z.B. CameraHRV)
    # Sonstige Sensoren - Fallback
    'handheld_gps':      'sampentropy',   # GPS-Handgeräte
    'hub':               'sampentropy',   # Smart-Home-Hubs
    'weather_station':   'sampentropy',   # Wetterstationen
    'scale':             'sampentropy',   # Körperanalysewaagen
    'bp_monitor':        'sampentropy',   # Blutdruckmessgeräte
    'glucometer':        'sampentropy',   # Blutzuckermessgeräte
    'cgm':               'sampentropy',   # CGM-Systeme
    'thermometer':      'sampentropy',   # Thermometer
}

# Legacy source-string routing — last-resort fallback, only reached when
# modules.ppi_provenance.mode_from_sources() found no registry entry at all
# (empty registry, brand-new unregistered device). Kept intentionally small
# and VERIFIED against what actually gets written (grep over every importer
# that INSERTs into ppi_raw, plus `SELECT DISTINCT source, device FROM
# ppi_raw` on the project DB, 2026-09) — not the earlier version's guessed
# model names, most of which could never match:
#   - device_id-keyed entries ('polar_h10', 'polar_m430', 'apple_heartbeat', …)
#     can NEVER match dev_key: the _pseudonymize_ppi_raw_device trigger
#     rewrites every ppi_raw.device to 'DEV-<hash>' on INSERT (s.
#     db-schema-conventions) — a semantic device name never reaches this
#     column. Removed.
#   - 'garmin_rr' / 'oura_rr' removed: no importer ever writes these source
#     strings into ppi_raw. Garmin-derived beats arrive via
#     compute_ecg_rpeaks.py labelled 'ecg_garmin'; Oura's API v2 does not
#     expose raw RR intervals at all, so no Oura path writes to ppi_raw.
#   - 'apple_heartbeat' removed: no importer uses this label; Apple-Watch
#     ECG-derived beats arrive via compute_ecg_rpeaks.py as 'ecg_apple'.
#   - 'polar_connect' kept: the real value of import_polar.py's SOURCE
#     constant.
# Every 'ecg_*'-prefixed source (compute_ecg_rpeaks.py, import_ecg_logger.py)
# is already routed to 'tateno_glass' above via SENSOR_TYPE_ROUTING['ecg'] —
# mode_from_sources() resolves that prefix before this fallback is ever
# reached, so no 'ecg_*' entry belongs in this dict (it would be dead code).
# Add a new source string here only once an importer actually writes it —
# verify via grep/SQL, don't guess (s. CLAUDE.md Regel 4).
ALGO_ROUTING: dict[str, str] = {
    'polar_connect': 'tateno_glass',   # import_polar.py SOURCE — Brustgurt-RR
}
ALGO_DEFAULT = 'tateno_glass'

# ── Bigeminie-Erkennung (Short-Long-RR-Alternanz) ─────────────────────────────
# Publizierte, validierte Schwellen aus Han D, Bashar SK, Mohagheghian F et al.
# (2020). Premature Atrial and Ventricular Contraction Detection using
# Photoplethysmographic Data from a Smartwatch. Sensors (Basel), 20(19):5683.
# doi:10.3390/s20195683 — s. Docstring von modules/rr_interval_algorithms.py
# detect_bigeminy_runs() fuer den genauen Umfang der Replikation (die drei
# Zahlenschwellen ja, das vollstaendige 9-Quadranten-Poincare-Raster nein).
BIGEMINY_ZERO_BAND_BPM  = 5.0   # "zeroth quadrant" Breite, Han et al. 2020
BIGEMINY_MIN_PAIRS      = 5     # bigeminie-spezifisches "2-4"/"4-2"-Kriterium, Han et al. 2020
BIGEMINY_ANGLE_SD_MAX_DEG = 10.0  # "vector resemblance"-Schwelle, Han et al. 2020
BIGEMINY_SEGMENT_GAP_S = 30    # groessere Luecke = Sensor ab/Session-Ende, neue Sequenz
BIGEMINY_MERGE_GAP_S   = 60    # nahe beieinanderliegende Laeufe zu einer Episode zusammenfassen
# Konfidenz nach Sensor-Modalitaet: Han et al. 2020 validierten ausschliesslich
# auf PPG (Smartwatch + MIMIC-III-Pulsoximetrie) — PPG ist hier also der
# eigentlich abgedeckte Anwendungsfall, nicht der schwaechere. EKG-Brustgurt-
# RR ist praeziser als PPG, aber die Uebertragung der PPG-validierten Methode
# darauf ist selbst nicht separat validiert — deshalb fuer BEIDE Modalitaeten
# 'moderate' (nicht 'high', da weder FDA-/CE-Zulassung noch aerztliche
# Gegenpruefung dieser Implementierung vorliegt), keine mehr auf 'low'
# gesetzt, weil der Algorithmus selbst jetzt literaturbasiert ist statt
# frei erfunden.
BIGEMINY_CONFIDENCE_BY_MODE = {
    'ecg': 'moderate', 'chest_strap': 'moderate',
    'optical_wrist_gps': 'moderate', 'optical_wrist': 'moderate', 'ppg_sensor': 'moderate',
}

# ── Einzelschlag-PVC-Erkennung (Prematurity/Compensatory Pause) ───────────────
# Publizierte Feature-Formeln aus Cuesta P, Lado MJ, Vila XA, Alonso R (2014).
# Detection of premature ventricular contractions using the RR-interval
# signal: a simple algorithm for mobile devices. Technology and Health Care,
# 22(4):651-656. doi:10.3233/THC-140818 — s. Docstring von
# modules/rr_interval_algorithms.py detect_premature_beats_cuesta() fuer den
# genauen Umfang der Replikation (Feature-Formeln ja, exakte trainierte
# LDA-Grenze nein, nur die publizierten Klassenmittel). Komplementaer zu
# detect_bigeminy_runs: erkennt isolierte Einzelschlaege statt anhaltender
# Alternanz-Laeufe.
CUESTA_WINDOW = 10   # "10 normal beats", experimentell festgelegt im Original
# Geraeteklassen-Routing statt Konfidenz-Abstufung (s. Docstring von
# _collect_cuesta_episodes fuer die empirische Begruendung): nur 'ecg'/
# 'chest_strap' werden ueberhaupt durch den Detektor geschickt, optische/
# PPG-Quellen erzeugten in einem ersten Testlauf auf echten Daten eine
# Falsch-Positiv-Explosion (>99% aller Funde bei nur 3 Geraeten) und wurden
# deshalb komplett ausgeschlossen statt nur niedriger konfidenzbewertet.
# 'moderate' statt 'high', da die hier verwendete Naechster-Klassenschwerpunkt-
# Klassifikation selbst nur eine Naeherung an die unveroeffentlichte
# LDA-Grenze ist (s. Docstring von detect_premature_beats_cuesta).
CUESTA_CONFIDENCE_BY_MODE = {
    'ecg': 'moderate', 'chest_strap': 'moderate',
}


def setup_staging_tables(conn):
    """Creates _new staging tables; existing production tables are left untouched."""
    conn.executescript("""
    DROP TABLE IF EXISTS ppi_windows_new;
    DROP TABLE IF EXISTS arrhythmie_episoden_new;

    CREATE TABLE ppi_windows_new (
        fenster_start    TEXT NOT NULL,
        person           TEXT NOT NULL DEFAULT 'unknown',
        n_beats          INT,
        rr_mean_ms       REAL,
        rr_sd_ms         REAL,
        cv_rr            REAL,
        rmssd_ms         REAL,
        hr_bpm           REAL,
        n_grosse_sprunge INT,
        tpr              REAL,
        arrhythmie_flag  INT,
        detection_method TEXT,
        -- Geraet, das die meisten Beats dieses Fensters lieferte (Pseudonym-ID
        -- dev_key, bereits fuer das Algorithmus-Routing oben ermittelt — hier
        -- nur zusaetzlich gespeichert). NULL wenn kein Beat des Fensters ein
        -- device trug. Grundlage fuer nachgelagerte Sensorklassen-Gewichtung
        -- (z.B. compute_af_evidence.py) statt einer Annahme "alles Brustgurt".
        device           TEXT,
        -- Effektiver Messmodus des Fensters: 'ecg' wenn die Mehrheit der Beats
        -- aus einer EKG-Ableitung stammt (modules/ppi_provenance.py, ppi_raw.
        -- source-Praefix 'ecg_'), sonst der sensor_type von `device` aus der
        -- Geraeteregistry, sonst NULL. Genauer als `device` allein: dasselbe
        -- Geraet (z.B. eine optische Uhr) kann Fenster in beiden Modi liefern.
        sensor_mode      TEXT,
        PRIMARY KEY (fenster_start, person)
    );

    CREATE TABLE arrhythmie_episoden_new (
        episode_start    TEXT,
        episode_end      TEXT,
        dauer_min        REAL,
        n_fenster        INT,
        cv_max           REAL,
        cv_mean          REAL,
        tpr_mean         REAL,
        hr_mean          REAL,
        time_of_day      TEXT,
        person           TEXT NOT NULL DEFAULT 'unknown',
        detection_method TEXT DEFAULT 'tateno_glass',
        source           TEXT DEFAULT 'polar_ppi',
        confidence       TEXT DEFAULT 'moderate'
    );
    """)
    conn.commit()
    print(t("Staging-Tabellen erstellt.", "Staging tables created."))


def swap_staging_tables(conn):
    """Replaces production tables with the freshly computed staging tables."""
    # Migrate confidence column into existing production table so any external readers
    # that hold a reference during the swap don't break on the new column.
    try:
        conn.execute("ALTER TABLE arrhythmie_episoden ADD COLUMN confidence TEXT DEFAULT 'moderate'")
        conn.commit()
    except Exception:
        pass  # column already exists or table doesn't exist yet — both are fine
    conn.executescript("""
    DROP TABLE IF EXISTS ppi_windows;
    ALTER TABLE ppi_windows_new RENAME TO ppi_windows;
    DROP TABLE IF EXISTS arrhythmie_episoden;
    ALTER TABLE arrhythmie_episoden_new RENAME TO arrhythmie_episoden;
    """)
    conn.commit()
    print(t("Tabellen-Swap abgeschlossen.", "Table swap complete."))


def time_of_day(dt_str: str, tz_name: str) -> str:
    dt_utc = datetime.fromisoformat(dt_str[:19]).replace(tzinfo=timezone.utc)
    h = dt_utc.astimezone(ZoneInfo(tz_name)).hour
    if 0  <= h < 6:  return "Night"
    if 6  <= h < 12: return "Morning"
    if 12 <= h < 18: return "Day"
    return "Evening"


def compute_stats(ppis: list, algorithm: str = 'tateno_glass') -> dict | None:
    n = len(ppis)
    if n < MIN_BEATS:
        return None
    mean  = sum(ppis) / n
    sd    = math.sqrt(sum((x - mean)**2 for x in ppis) / (n - 1))
    cv    = sd / mean if mean > 0 else 0
    diffs = [abs(ppis[i+1] - ppis[i]) for i in range(n-1)]
    rmssd = math.sqrt(sum(d*d for d in diffs) / len(diffs)) if diffs else 0
    grosse_sprunge = sum(1 for d in diffs if d > 200)
    hr    = 60000 / mean if mean > 0 else 0

    if algorithm == 'tateno_glass':
        flag, tpr, method = detect_tateno_glass(ppis, rmssd, TPR_THRESHOLD, RMSSD_CONFIRM)
    elif algorithm == 'sampentropy':
        flag, tpr, method = detect_sampentropy(ppis, rmssd, SAMPEN_THRESHOLD, SAMPEN_CV_THRESHOLD)
    elif algorithm == 'dash2009':
        flag, tpr, method = detect_dash2009(ppis, rmssd, DASH2009_H_THRESHOLD, DASH2009_CV_THRESHOLD)
    else:
        flag, tpr, method = detect_tateno_glass(ppis, rmssd, TPR_THRESHOLD, RMSSD_CONFIRM)

    return {
        "n": n, "mean": round(mean, 1), "sd": round(sd, 1),
        "cv": round(cv, 4), "rmssd": round(rmssd, 1),
        "hr": round(hr, 1), "sprunge": grosse_sprunge,
        "tpr": round(tpr, 4),
        "flag": flag,
        "method": method,
    }


def _method_to_confidence(method: str) -> str:
    if 'stub' in method or 'sampentropy' in method or 'heuristic' in method:
        return 'low'
    # tateno_glass auf ECG/Brustgurt: AFDB-kalibriert → moderate
    # dash2009 auf PPG: validierter Algorithmus, aber PPG-Messungenauigkeit → moderate
    return 'moderate'


def _collect_apple_ecg_episodes(conn, person: str, tz_name: str) -> list:
    """ecg_sessions (classification='atrial_fibrillation') → Episode-Tupel.

    Jede Apple-Watch-EKG-Aufnahme ist ein 30-s-Snapshot — kein kontinuierliches
    Monitoring. Keine Beat-to-Beat-Statistiken verfügbar; cv/tpr/hr bleiben NULL.
    Konfidenz 'high': FDA-cleared Klassifikation (Perez 2019 NEJM).
    """
    rows = conn.execute("""
        SELECT datetime, duration_s, device_id
        FROM ecg_sessions
        WHERE person=? AND classification='atrial_fibrillation'
        ORDER BY datetime
    """, (person,)).fetchall()

    episodes = []
    for dt_str, duration_s, device_id in rows:
        dur_s = float(duration_s or 30.0)
        try:
            dt_start = datetime.fromisoformat(dt_str[:19])
        except ValueError:
            continue
        dt_end = dt_start + timedelta(seconds=dur_s)
        episodes.append((
            dt_start.strftime("%Y-%m-%dT%H:%M:%S"),
            dt_end.strftime("%Y-%m-%dT%H:%M:%S"),
            round(dur_s / 60, 1),
            1,       # n_fenster
            None,    # cv_max — nicht verfügbar
            None,    # cv_mean
            None,    # tpr_mean
            None,    # hr_mean
            time_of_day(dt_start.strftime("%Y-%m-%dT%H:%M:%S"), tz_name),
            person,
            'apple_ecg_classifier',
            'apple_ecg',
            'high',
        ))
    return episodes


def _collect_ecg_logger_episodes(conn, person: str, tz_name: str) -> list:
    """ecg_logger_sessions (afib_suspected=1) → Episode-Tupel.

    ECG Logger berechnet afib_suspected/afib_score je Session bereits intern;
    Rohdaten werden daher nicht erneut analysiert. Session-ID ist der Start-Timestamp.
    Konfidenz 'high': validierter Algorithmus (TPR + SampEn) auf Single-Lead-EKG.
    """
    # ecg_logger_sessions hat keine person-Spalte — alle Sessions gehören zu person
    rows = conn.execute("""
        SELECT session_id, duration_s, mean_hr_bpm, cv_rr, turning_pt_ratio, afib_score
        FROM ecg_logger_sessions
        WHERE afib_suspected = 1
        ORDER BY session_id
    """).fetchall()

    episodes = []
    for session_id, duration_s, hr_bpm, cv_rr, tpr, afib_score in rows:
        dur_s = float(duration_s or 0.0)
        try:
            dt_start = datetime.fromisoformat(session_id[:19])
        except ValueError:
            continue
        dt_end = dt_start + timedelta(seconds=dur_s)
        dauer_min = round(dur_s / 60, 1)
        if dauer_min > MAX_EPISODE_MIN:
            continue
        score_str = f'{afib_score:.2f}' if afib_score is not None else ''
        episodes.append((
            dt_start.strftime("%Y-%m-%dT%H:%M:%S"),
            dt_end.strftime("%Y-%m-%dT%H:%M:%S"),
            dauer_min,
            max(1, int(dur_s / FENSTER_S)),
            cv_rr,   # cv_max
            cv_rr,   # cv_mean
            tpr,     # tpr_mean
            hr_bpm,  # hr_mean
            time_of_day(dt_start.strftime("%Y-%m-%dT%H:%M:%S"), tz_name),
            person,
            f'ecg_logger_afib_score{score_str}',
            'ecg_logger',
            'high',
        ))
    return episodes


def _parse_ppi_ts(dt_str: str) -> datetime:
    """UTC-naive datetime aus ppi_raw.datetime (tz-aware oder legacy naive)."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return datetime.fromisoformat(dt_str[:19])


def _device_sensor_mode(conn, device_id: str) -> str | None:
    """sensor_type aus der Geraeteregistry; 'ecg' hat Vorrang wenn ppi_raw fuer
    dieses Geraet ueberwiegend aus einer 'ecg_'-praefigierten Quelle stammt
    (gleiche Logik wie modules/ppi_provenance.mode_from_sources, hier nur
    geraetegebunden statt fensterweise, da Bigeminie-Segmente ganze
    Beat-Sequenzen pro Geraet sind, nicht 5-Min-Fenster)."""
    row = conn.execute(
        "SELECT sensor_type FROM devices WHERE device_id=?", (device_id,)
    ).fetchone()
    return row[0] if row else None


def _in_training_window(dt: datetime, training_by_day: dict) -> bool:
    for tr_s, tr_e in training_by_day.get(dt.strftime('%Y-%m-%d'), []):
        if tr_s <= dt < tr_e:
            return True
    return False


def _collect_bigeminy_episodes(conn, person: str, tz_name: str, training_by_day: dict) -> list:
    """ppi_raw, geraeteweise, gestreamt (kein fetchall — einzelne Geraete haben
    zweistellige Millionen Zeilen) → Segmente bei Luecken > BIGEMINY_SEGMENT_GAP_S
    ODER bei Trainingsfenstern (±15 min Puffer, s. _load_training_by_day) ODER
    adaptiv erkannter Belastung (s. _RollingHRBaseline) → detect_bigeminy_runs()
    je Segment → nahe beieinanderliegende Laeufe (<= BIGEMINY_MERGE_GAP_S) zu
    Episoden zusammengefasst. Dieselbe Belastungsausschluss-Logik wie beim
    bestehenden AFib-Teil oben (Trainingsfenster/Belastung erzeugen
    systematisch falsche Kurz-Lang-Alternanz-Muster, kein Bigeminie-
    spezifisches Risiko).

    Gibt Episode-Tupel im selben Format wie die uebrigen _collect_*_episoden-
    Funktionen zurueck (episode_start, episode_end, dauer_min, n_fenster,
    cv_max, cv_mean, tpr_mean, hr_mean, time_of_day, person, detection_method,
    source, confidence) — cv/tpr-Spalten bleiben None (Bigeminie-Detektion
    misst kein CV/TPR), n_fenster traegt hier die Anzahl S-L-Zyklen."""
    devices = [r[0] for r in conn.execute(
        "SELECT DISTINCT device FROM ppi_raw WHERE person=? AND device IS NOT NULL",
        (person,)).fetchall()]

    all_runs_by_device: dict[str, list] = {}
    for device_id in devices:
        sensor_type = _device_sensor_mode(conn, device_id)
        # ecg_-praefigierte Quellen (ECGLogger/Watch-EKG) sind pro device_id
        # einheitlich, s. ALGO_ROUTING['polar_connect'] Kommentar oben.
        cur = conn.execute("""
            SELECT datetime, pulse_ms FROM ppi_raw
            WHERE person=? AND device=? AND pulse_ms BETWEEN 300 AND 1800
            ORDER BY datetime""", (person, device_id))

        runs: list = []
        seg_ts: list = []
        seg_ppi: list = []
        last_dt: datetime | None = None
        baseline = _RollingHRBaseline()

        def _flush_segment():
            if len(seg_ppi) < 2 * BIGEMINY_MIN_PAIRS:
                return
            for run in detect_bigeminy_runs(
                seg_ts, seg_ppi, min_pairs=BIGEMINY_MIN_PAIRS,
                zero_band_bpm=BIGEMINY_ZERO_BAND_BPM,
                angle_sd_max_deg=BIGEMINY_ANGLE_SD_MAX_DEG,
            ):
                runs.append(run)

        for dt_str, ppi in cur:
            dt = _parse_ppi_ts(dt_str)
            hr = 60000.0 / ppi if ppi > 0 else 0.0
            exercise_beat = baseline.is_exercise(dt, hr) or _in_training_window(dt, training_by_day)
            baseline.update(dt, hr)
            gap_too_large = last_dt is not None and (dt - last_dt).total_seconds() > BIGEMINY_SEGMENT_GAP_S
            if exercise_beat or gap_too_large:
                _flush_segment()
                seg_ts, seg_ppi = [], []
                if exercise_beat:
                    last_dt = dt
                    continue
            seg_ts.append(dt)
            seg_ppi.append(ppi)
            last_dt = dt
        _flush_segment()

        if runs:
            all_runs_by_device[device_id] = runs

    episodes = []
    for device_id, runs in all_runs_by_device.items():
        sensor_type = _device_sensor_mode(conn, device_id)
        confidence = BIGEMINY_CONFIDENCE_BY_MODE.get(sensor_type, 'low')
        runs.sort(key=lambda r: r["start_ts"])

        ep_start = runs[0]["start_ts"]
        ep_end   = runs[0]["end_ts"]
        ep_cycles = runs[0]["n_cycles"]
        ep_nruns  = 1
        for r in runs[1:]:
            gap = (r["start_ts"] - ep_end).total_seconds()
            if gap <= BIGEMINY_MERGE_GAP_S:
                ep_end = max(ep_end, r["end_ts"])
                ep_cycles += r["n_cycles"]
                ep_nruns += 1
            else:
                episodes.append((
                    ep_start.strftime("%Y-%m-%dT%H:%M:%S"),
                    ep_end.strftime("%Y-%m-%dT%H:%M:%S"),
                    round((ep_end - ep_start).total_seconds() / 60, 1),
                    ep_cycles, None, None, None, None,
                    time_of_day(ep_start.strftime("%Y-%m-%dT%H:%M:%S"), tz_name),
                    person, 'bigeminy_rr_alternation', device_id, confidence,
                ))
                ep_start, ep_end, ep_cycles, ep_nruns = r["start_ts"], r["end_ts"], r["n_cycles"], 1
        episodes.append((
            ep_start.strftime("%Y-%m-%dT%H:%M:%S"),
            ep_end.strftime("%Y-%m-%dT%H:%M:%S"),
            round((ep_end - ep_start).total_seconds() / 60, 1),
            ep_cycles, None, None, None, None,
            time_of_day(ep_start.strftime("%Y-%m-%dT%H:%M:%S"), tz_name),
            person, 'bigeminy_rr_alternation', device_id, confidence,
        ))
    return episodes


def _collect_cuesta_episodes(conn, person: str, tz_name: str, training_by_day: dict) -> list:
    """ppi_raw, geraeteweise, gestreamt → Segmente bei Luecken > BIGEMINY_SEGMENT_GAP_S
    ODER Belastung (dieselbe Ausschlusslogik wie _collect_bigeminy_episodes,
    s. dort) → detect_premature_beats_cuesta() je Segment → als premature
    geflaggte Beats werden zu Episoden gruppiert, indem UNMITTELBAR
    AUFEINANDERFOLGENDE Beat-Indizes (nicht: zeitliche Naehe) zusammengefasst
    werden — das entspricht der kardiologischen Standardterminologie fuer
    Couplet (2 konsekutive Ektopien)/Triplet (3)/Run (>=3): zwei isolierte
    Einzelschlaege, die nur zeitlich nah beieinanderliegen aber nicht
    unmittelbar aufeinanderfolgen, bleiben bewusst getrennte Episoden statt
    faelschlich zu einem Cluster verschmolzen zu werden.

    n_fenster traegt hier die Cluster-Groesse (1 = isolierte PVC, 2 = Couplet,
    3 = Triplet, >=3 = Run) — dieselbe Spalten-Wiederverwendung wie bei
    _collect_bigeminy_episodes (dort: Zyklenzahl). Export-Profile/Berichte
    leiten die kardiologische Bezeichnung aus n_fenster ab (s. Docstring
    oben), es gibt keine eigene Label-Spalte.

    Geraeteklassen-Routing (dieselbe Philosophie wie SENSOR_TYPE_ROUTING oben):
    nur 'ecg'/'chest_strap'-Sensortypen werden ueberhaupt durch den Detektor
    geschickt, NICHT nur niedriger konfidenzbewertet. Grund: empirisch
    getestet (echte Datenbasis) erzeugt die Naechster-Klassenschwerpunkt-
    Naeherung auf optischem/PPG-RR-Rauschen eine Falsch-Positiv-Explosion
    (>99% aller Funde bei einem ersten Testlauf stammten von 3 optischen
    Geraeten, waehrend EKG-Brustgurt-Quellen eine plausible Groessenordnung
    lieferten) — konsistent mit dem synthetischen Befund, dass die
    Klassifikation ab ca. 50ms Beat-zu-Beat-Rauschen (SD) messbar falsch-
    positiv wird, was optische/PPG-Rohdaten unter Alltagsbedingungen
    regelmaessig ueberschreiten, EKG-Brustgurt-Rauschen praktisch nie.
    Cuesta et al. validierten ohnehin ausschliesslich auf MIT-BIH (echtes
    EKG) — der Ausschluss optischer Quellen ist also keine willkuerliche
    Geraetepraeferenz, sondern die direkte Konsequenz aus dem tatsaechlichen
    Validierungsumfang der Methode."""
    devices = [r[0] for r in conn.execute(
        "SELECT DISTINCT device FROM ppi_raw WHERE person=? AND device IS NOT NULL",
        (person,)).fetchall()]
    devices = [d for d in devices if _device_sensor_mode(conn, d) in ('ecg', 'chest_strap')]

    all_clusters_by_device: dict[str, list] = {}
    for device_id in devices:
        cur = conn.execute("""
            SELECT datetime, pulse_ms FROM ppi_raw
            WHERE person=? AND device=? AND pulse_ms BETWEEN 300 AND 1800
            ORDER BY datetime""", (person, device_id))

        clusters: list = []
        seg_ts: list = []
        seg_ppi: list = []
        last_dt: datetime | None = None
        baseline = _RollingHRBaseline()

        def _flush_segment():
            if len(seg_ppi) < 2 * CUESTA_WINDOW:
                return
            flagged = sorted(
                r["idx"] for r in detect_premature_beats_cuesta(seg_ppi, window=CUESTA_WINDOW)
                if r["is_premature"]
            )
            i = 0
            while i < len(flagged):
                j = i
                while j + 1 < len(flagged) and flagged[j + 1] == flagged[j] + 1:
                    j += 1
                start_idx, end_idx = flagged[i], flagged[j] + 1  # +1: Beat der Compensatory Pause
                clusters.append({
                    "start_ts": seg_ts[start_idx], "end_ts": seg_ts[min(end_idx, len(seg_ts) - 1)],
                    "cluster_size": j - i + 1,
                })
                i = j + 1

        for dt_str, ppi in cur:
            dt = _parse_ppi_ts(dt_str)
            hr = 60000.0 / ppi if ppi > 0 else 0.0
            exercise_beat = baseline.is_exercise(dt, hr) or _in_training_window(dt, training_by_day)
            baseline.update(dt, hr)
            gap_too_large = last_dt is not None and (dt - last_dt).total_seconds() > BIGEMINY_SEGMENT_GAP_S
            if exercise_beat or gap_too_large:
                _flush_segment()
                seg_ts, seg_ppi = [], []
                if exercise_beat:
                    last_dt = dt
                    continue
            seg_ts.append(dt)
            seg_ppi.append(ppi)
            last_dt = dt
        _flush_segment()

        if clusters:
            all_clusters_by_device[device_id] = clusters

    episodes = []
    for device_id, clusters in all_clusters_by_device.items():
        sensor_type = _device_sensor_mode(conn, device_id)
        confidence = CUESTA_CONFIDENCE_BY_MODE.get(sensor_type, 'low')
        for c in clusters:
            episodes.append((
                c["start_ts"].strftime("%Y-%m-%dT%H:%M:%S"),
                c["end_ts"].strftime("%Y-%m-%dT%H:%M:%S"),
                round((c["end_ts"] - c["start_ts"]).total_seconds() / 60, 1),
                c["cluster_size"], None, None, None, None,
                time_of_day(c["start_ts"].strftime("%Y-%m-%dT%H:%M:%S"), tz_name),
                person, 'premature_beat_rr', device_id, confidence,
            ))
    return episodes


def _collect_fibricheck_episodes(conn, person: str, tz_name: str) -> list:
    """fibricheck_sessions (result_code != 'normal') → Episode-Tupel.

    FibriCheck-Aufnahmen sind ca. 60-s-Einzelmessungen (Smartphone-Kamera-
    PPG) — wie bei den Apple-EKG-Snapshots keine fortlaufende Beat-to-Beat-
    Statistik verfuegbar, cv/tpr bleiben NULL. Konfidenz 'high' NUR wenn
    panel_reviewed=1 (die Messung wurde von einem Mediziner im FibriCheck-
    Expertengremium gegengeprueft, nicht nur automatisiert klassifiziert),
    sonst 'moderate' (reine PPG-Algorithmus-Klassifikation, ungeprueft)."""
    rows = conn.execute("""
        SELECT ts, result_code, hr_avg_bpm, panel_reviewed, algorithm_version
        FROM fibricheck_sessions
        WHERE person=? AND result_code IS NOT NULL AND result_code != 'normal'
        ORDER BY ts
    """, (person,)).fetchall()

    episodes = []
    for ts_str, result_code, hr_avg, panel_reviewed, algo_version in rows:
        try:
            dt_start = datetime.fromisoformat(ts_str[:19])
        except ValueError:
            continue
        dt_end = dt_start + timedelta(seconds=60)
        confidence = 'high' if panel_reviewed else 'moderate'
        episodes.append((
            dt_start.strftime("%Y-%m-%dT%H:%M:%S"),
            dt_end.strftime("%Y-%m-%dT%H:%M:%S"),
            1.0,     # dauer_min — feste ~60s-Einzelmessung
            1,       # n_fenster
            None, None, None,   # cv_max, cv_mean, tpr_mean — nicht verfuegbar
            hr_avg,
            time_of_day(dt_start.strftime("%Y-%m-%dT%H:%M:%S"), tz_name),
            person,
            f'fibricheck_{result_code}_{algo_version or "unknown"}',
            'fibricheck',
            confidence,
        ))
    return episodes


def _load_training_by_day(conn, person: str) -> dict[str, list[tuple[datetime, datetime]]]:
    """Training-Session-Intervalle nach Datum gruppiert (15-min Puffer vor/nach).

    Gibt {date_str: [(utc_start, utc_end)]} zurück — UTCnaive datetimes.
    Fenster die in einem Intervall liegen werden nicht als Arrhythmie geflaggt.
    """
    rows = conn.execute("""
        SELECT ts_start, ts_end FROM sessions
        WHERE type='training' AND person=?
          AND ts_start IS NOT NULL AND ts_end IS NOT NULL
    """, (person,)).fetchall()
    by_day: dict[str, list] = {}
    for ts_s, ts_e in rows:
        try:
            s = datetime.fromisoformat(ts_s[:19]) - timedelta(minutes=15)
            e = datetime.fromisoformat(ts_e[:19]) + timedelta(minutes=15)
        except ValueError:
            continue
        for day in {s.strftime('%Y-%m-%d'), e.strftime('%Y-%m-%d')}:
            by_day.setdefault(day, []).append((s, e))
    return by_day


def main():
    parser = argparse.ArgumentParser(
        description=t("Arrhythmie-Detektion aus allen Quellen",
                      "Arrhythmia detection from all sources"))
    parser.add_argument("--person", default=None,
                        help=t("Person (default: self)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person or OWN_PERSON_ID

    conn = open_db()
    tz_name = resolve_timezone(conn, person)
    setup_staging_tables(conn)

    training_by_day = _load_training_by_day(conn, person)
    print(t(f"{len(training_by_day)} Trainingstage geladen — Fenster darin werden nicht geflaggt.",
            f"{len(training_by_day)} training days loaded — windows within are not flagged."))

    tage = [r[0] for r in conn.execute("""
        SELECT DISTINCT substr(datetime, 1, 10) d
        FROM ppi_raw WHERE pulse_ms BETWEEN 300 AND 1800
        AND person = ?
        ORDER BY d""", (person,)).fetchall()]

    print(t(f"{len(tage)} Tage mit PPI-Daten werden analysiert ...",
            f"Analysing {len(tage)} days of PPI data ..."))
    total_fenster = 0
    total_flag    = 0
    window_rows   = []
    # Persistente Pro-Geraet-Baseline ueber alle Tage hinweg (nicht pro Tag neu),
    # sonst wuerde der gleitende Kontext an jeder Tagesgrenze verloren gehen.
    # S. Konstanten-Kommentar bei ADAPTIVE_BASELINE_WINDOW_S fuer die Begruendung.
    window_baselines: dict[str, _RollingHRBaseline] = {}

    for tag_idx, tag in enumerate(tage):
        rows = conn.execute("""
            SELECT datetime, pulse_ms, source, device FROM ppi_raw
            WHERE substr(datetime, 1, 10) = ? AND pulse_ms BETWEEN 300 AND 1800
            AND person = ?
            ORDER BY datetime""", (tag, person)).fetchall()
        if not rows:
            continue

        # Normalize to UTC-naive by stripping timezone info after converting.
        # Handles both "+00:00"-suffixed and legacy naive timestamps.
        raw0 = rows[0][0]
        try:
            ts0 = datetime.fromisoformat(raw0.replace("Z", "+00:00"))
            if ts0.tzinfo is not None:
                ts0 = ts0.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            ts0 = datetime.fromisoformat(raw0[:19])
        t0 = ts0.replace(second=0, microsecond=0, minute=(ts0.minute // 5) * 5)

        fenster_ppis    = []
        fenster_routing = []  # (source, device) tuples for algorithm selection
        fenster_start   = t0

        def flush():
            nonlocal total_fenster, total_flag
            if not fenster_ppis:
                return
            # Device-ID beats source for algo routing (optical wrist ≠ chest strap)
            dev_key = max(set(d for _, d in fenster_routing), key=lambda d: sum(1 for _, x in fenster_routing if x == d)) if fenster_routing else ''
            src_key = max(set(s for s, _ in fenster_routing), key=lambda s: sum(1 for x, _ in fenster_routing if x == s)) if fenster_routing else 'unknown'
            # Rohe Seriennummer / BT-MAC → standardisierter device_id (identity.db)
            dev_key = SERIAL_TO_DEVICE.get(dev_key, dev_key)

            # Effektiver Messmodus des Fensters, aus den bereits geladenen
            # ppi_raw.source-Werten (fenster_routing) — nicht allein aus dem
            # Geraet: dasselbe device_id kann sowohl durchgehend optisch als
            # auch (z.B. bei einer Watch mit EKG-Funktion) EKG-abgeleitet
            # liefern, s. modules/ppi_provenance.py.
            sensor_mode = mode_from_sources((src for src, _ in fenster_routing), dev_key)
            if sensor_mode and sensor_mode in SENSOR_TYPE_ROUTING:
                algo = SENSOR_TYPE_ROUTING[sensor_mode]
            else:
                # Fallback to legacy device_id/source routing (registry has no
                # entry at all — empty registry or brand-new unregistered device)
                algo = ALGO_ROUTING.get(dev_key) or ALGO_ROUTING.get(src_key, ALGO_DEFAULT)
            s = compute_stats(fenster_ppis, algo)
            if s:
                total_fenster += 1
                # Suppress flag during training sessions or at exercise HR
                # (adaptive, geraete-eigene Baseline statt festem Schwellwert,
                # s. _RollingHRBaseline — ein Fenster hat idR eine dominante
                # Datenquelle, deshalb genuegt ein Baseline-Objekt je dev_key).
                bkey = dev_key or src_key or 'unknown'
                bl = window_baselines.setdefault(bkey, _RollingHRBaseline())
                if s["flag"]:
                    if bl.is_exercise(fenster_start, s["hr"]):
                        s["flag"] = 0
                    else:
                        fs_day = fenster_start.strftime('%Y-%m-%d')
                        for tr_s, tr_e in training_by_day.get(fs_day, []):
                            if tr_s <= fenster_start < tr_e:
                                s["flag"] = 0
                                break
                bl.update(fenster_start, s["hr"])
                total_flag    += s["flag"]
                window_rows.append((
                    fenster_start.strftime("%Y-%m-%dT%H:%M:%S"),
                    person,
                    s["n"], s["mean"], s["sd"], s["cv"],
                    s["rmssd"], s["hr"], s["sprunge"],
                    s["tpr"],
                    s["flag"],
                    s["method"],
                    dev_key or None,  # gleiches Geraet, das oben schon das Routing entschied
                    sensor_mode,      # 'ecg' | sensor_type | None, s. modules/ppi_provenance.py
                ))

        for dt_str, ppi, src, dev in rows:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                dt = datetime.fromisoformat(dt_str[:19])
            if dt >= fenster_start + timedelta(seconds=FENSTER_S):
                flush()
                fenster_ppis    = []
                fenster_routing = []
                fenster_start   = fenster_start + timedelta(seconds=FENSTER_S)
                while dt >= fenster_start + timedelta(seconds=FENSTER_S):
                    fenster_start += timedelta(seconds=FENSTER_S)
            fenster_ppis.append(ppi)
            fenster_routing.append((src, dev or ''))
        flush()

        if len(window_rows) >= 5000:
            conn.executemany("""INSERT INTO ppi_windows_new
                (fenster_start,person,n_beats,rr_mean_ms,rr_sd_ms,cv_rr,rmssd_ms,hr_bpm,
                 n_grosse_sprunge,tpr,arrhythmie_flag,detection_method,device,sensor_mode)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", window_rows)
            conn.commit()
            window_rows.clear()

        if (tag_idx + 1) % 20 == 0:
            print(t(f"  {tag_idx+1}/{len(tage)} Tage | {total_fenster} Fenster | {total_flag} auffällig",
                    f"  {tag_idx+1}/{len(tage)} days | {total_fenster} windows | {total_flag} flagged"),
                  end="\r", flush=True)

    if window_rows:
        conn.executemany("""INSERT INTO ppi_windows_new
            (fenster_start,person,n_beats,rr_mean_ms,rr_sd_ms,cv_rr,rmssd_ms,hr_bpm,
             n_grosse_sprunge,tpr,arrhythmie_flag,detection_method,device,sensor_mode)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", window_rows)
        conn.commit()
    print(t(f"\n{total_fenster} Fenster gespeichert | {total_flag} auffällig ({total_flag/total_fenster*100:.1f}%)",
            f"\n{total_fenster} windows saved | {total_flag} flagged ({total_flag/total_fenster*100:.1f}%)")
          if total_fenster else "")

    print(t("Erkenne Episoden ...", "Detecting episodes ..."))
    flagged = conn.execute("""
        SELECT fenster_start, cv_rr, hr_bpm, tpr, detection_method, device
        FROM ppi_windows_new WHERE arrhythmie_flag = 1 AND person = ?
        ORDER BY fenster_start""", (person,)).fetchall()

    episoden = []
    if flagged:
        ep_start   = flagged[0][0]
        ep_end     = flagged[0][0]
        ep_cvs     = [flagged[0][1]]
        ep_hrs     = [flagged[0][2]]
        ep_tprs    = [flagged[0][3]]
        ep_methods = [flagged[0][4]]
        ep_devices = [flagged[0][5]]
        ep_count   = 1

        def _finalize_episode(ep_start, ep_end, ep_count, ep_cvs, ep_hrs, ep_tprs,
                               ep_methods, ep_devices):
            dauer = (datetime.fromisoformat(ep_end) -
                     datetime.fromisoformat(ep_start)).total_seconds() / 60
            if dauer > MAX_EPISODE_MIN:
                print(t(f"  Artefakt verworfen: {ep_start[:16]} Dauer {dauer:.0f} min",
                        f"  Artefact discarded: {ep_start[:16]} duration {dauer:.0f} min"))
                return None
            method = max(set(ep_methods), key=ep_methods.count)
            # Tatsaechliche Quelle statt hartcodiertem 'polar_ppi': das Geraet
            # (Pseudonym-ID), das die meisten Fenster dieser Episode lieferte —
            # dieselbe Mehrheitslogik wie beim Fenster-Routing in flush() oben.
            # 'ppi_raw' als Fallback nur wenn wirklich kein Fenster ein device
            # trug (aeltere Zeilen vor dieser Spalte) — kein Ratewert.
            known_devices = [d for d in ep_devices if d]
            source = (max(set(known_devices), key=known_devices.count)
                       if known_devices else 'ppi_raw')
            return (
                ep_start, ep_end, round(dauer, 1), ep_count,
                round(max(ep_cvs), 4),
                round(sum(ep_cvs) / len(ep_cvs), 4),
                round(sum(ep_tprs) / len(ep_tprs), 4),
                round(sum(ep_hrs) / len(ep_hrs), 1),
                time_of_day(ep_start, tz_name),
                person,
                method,
                source,
                _method_to_confidence(method),
            )

        for i in range(1, len(flagged)):
            prev_dt = datetime.fromisoformat(flagged[i-1][0])
            curr_dt = datetime.fromisoformat(flagged[i][0])
            gap     = (curr_dt - prev_dt).total_seconds()

            if gap <= MAX_GAP_S:
                ep_end    = flagged[i][0]
                ep_cvs.append(flagged[i][1])
                ep_hrs.append(flagged[i][2])
                ep_tprs.append(flagged[i][3])
                ep_methods.append(flagged[i][4])
                ep_devices.append(flagged[i][5])
                ep_count += 1
            else:
                if ep_count >= MIN_FENSTER:
                    ep = _finalize_episode(ep_start, ep_end, ep_count,
                                           ep_cvs, ep_hrs, ep_tprs, ep_methods, ep_devices)
                    if ep: episoden.append(ep)
                ep_start   = flagged[i][0]
                ep_end     = flagged[i][0]
                ep_cvs     = [flagged[i][1]]
                ep_hrs     = [flagged[i][2]]
                ep_tprs    = [flagged[i][3]]
                ep_methods = [flagged[i][4]]
                ep_devices = [flagged[i][5]]
                ep_count   = 1

        if ep_count >= MIN_FENSTER:
            ep = _finalize_episode(ep_start, ep_end, ep_count,
                                   ep_cvs, ep_hrs, ep_tprs, ep_methods, ep_devices)
            if ep: episoden.append(ep)

    conn.executemany("""INSERT INTO arrhythmie_episoden_new
        (episode_start,episode_end,dauer_min,n_fenster,cv_max,cv_mean,tpr_mean,
         hr_mean,time_of_day,person,detection_method,source,confidence)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", episoden)
    conn.commit()

    # ── Externe Quellen ───────────────────────────────────────────────────────
    apple_eps      = _collect_apple_ecg_episodes(conn, person, tz_name)
    logger_eps     = _collect_ecg_logger_episodes(conn, person, tz_name)
    bigeminy_eps   = _collect_bigeminy_episodes(conn, person, tz_name, training_by_day)
    cuesta_eps     = _collect_cuesta_episodes(conn, person, tz_name, training_by_day)
    fibricheck_eps = _collect_fibricheck_episodes(conn, person, tz_name)

    if apple_eps:
        conn.executemany("""INSERT OR IGNORE INTO arrhythmie_episoden_new
            (episode_start,episode_end,dauer_min,n_fenster,cv_max,cv_mean,tpr_mean,
             hr_mean,time_of_day,person,detection_method,source,confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", apple_eps)
        conn.commit()
        print(t(f"{len(apple_eps)} Apple-EKG-AFib-Episoden hinzugefügt.",
                f"{len(apple_eps)} Apple ECG AFib episodes added."))

    if logger_eps:
        conn.executemany("""INSERT OR IGNORE INTO arrhythmie_episoden_new
            (episode_start,episode_end,dauer_min,n_fenster,cv_max,cv_mean,tpr_mean,
             hr_mean,time_of_day,person,detection_method,source,confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", logger_eps)
        conn.commit()
        print(t(f"{len(logger_eps)} ECG-Logger-AFib-Episoden hinzugefügt.",
                f"{len(logger_eps)} ECG Logger AFib episodes added."))

    if bigeminy_eps:
        conn.executemany("""INSERT OR IGNORE INTO arrhythmie_episoden_new
            (episode_start,episode_end,dauer_min,n_fenster,cv_max,cv_mean,tpr_mean,
             hr_mean,time_of_day,person,detection_method,source,confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", bigeminy_eps)
        conn.commit()
        print(t(f"{len(bigeminy_eps)} Bigeminie-Episoden (RR-Alternanz) hinzugefügt.",
                f"{len(bigeminy_eps)} bigeminy episodes (RR alternation) added."))

    if cuesta_eps:
        conn.executemany("""INSERT OR IGNORE INTO arrhythmie_episoden_new
            (episode_start,episode_end,dauer_min,n_fenster,cv_max,cv_mean,tpr_mean,
             hr_mean,time_of_day,person,detection_method,source,confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", cuesta_eps)
        conn.commit()
        print(t(f"{len(cuesta_eps)} Einzelschlag-PVC-Episoden (Cuesta) hinzugefügt.",
                f"{len(cuesta_eps)} single-beat PVC episodes (Cuesta) added."))

    if fibricheck_eps:
        conn.executemany("""INSERT OR IGNORE INTO arrhythmie_episoden_new
            (episode_start,episode_end,dauer_min,n_fenster,cv_max,cv_mean,tpr_mean,
             hr_mean,time_of_day,person,detection_method,source,confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", fibricheck_eps)
        conn.commit()
        print(t(f"{len(fibricheck_eps)} FibriCheck-Episoden hinzugefügt.",
                f"{len(fibricheck_eps)} FibriCheck episodes added."))

    swap_staging_tables(conn)

    n_total = (len(episoden) + len(apple_eps) + len(logger_eps) + len(bigeminy_eps)
               + len(cuesta_eps) + len(fibricheck_eps))
    print(t(f"{n_total} Arrhythmie-Episoden gesamt "
            f"(PPI:{len(episoden)} | Apple-EKG:{len(apple_eps)} | ECG-Logger:{len(logger_eps)} | "
            f"Bigeminie:{len(bigeminy_eps)} | Cuesta-PVC:{len(cuesta_eps)} | "
            f"FibriCheck:{len(fibricheck_eps)}).\n",
            f"{n_total} arrhythmia episodes total "
            f"(PPI:{len(episoden)} | Apple-ECG:{len(apple_eps)} | ECG-Logger:{len(logger_eps)} | "
            f"Bigeminy:{len(bigeminy_eps)} | Cuesta-PVC:{len(cuesta_eps)} | "
            f"FibriCheck:{len(fibricheck_eps)}).\n"))

    print(t("── Episoden nach Quelle ───────────────────────────────",
            "── Episodes by source ─────────────────────────────────"))
    for r in conn.execute("""
        SELECT source, confidence, COUNT(*), ROUND(AVG(dauer_min),1),
               ROUND(MAX(dauer_min),1)
        FROM arrhythmie_episoden WHERE person = ?
        GROUP BY source, confidence ORDER BY COUNT(*) DESC""", (person,)):
        print(f"  {r[0]:<14} [{r[1]:<8}]: {r[2]:>4} " +
              t(f"Episoden | ∅{r[3]}min | Max {r[4]}min",
                f"episodes | avg {r[3]}min | max {r[4]}min"))

    print(t("\n── Episoden nach Tageszeit ────────────────────────────",
            "\n── Episodes by time of day ────────────────────────────"))
    for r in conn.execute("""
        SELECT time_of_day, COUNT(*), ROUND(AVG(dauer_min),1),
               ROUND(MAX(dauer_min),1), ROUND(AVG(tpr_mean),3)
        FROM arrhythmie_episoden WHERE person = ?
        GROUP BY time_of_day ORDER BY 2 DESC""", (person,)):
        print(f"  {r[0]:<8}: {r[1]:>4} " +
              t(f"Episoden | ∅{r[2]}min | Max {r[3]}min | ∅TPR {r[4]}",
                f"episodes | avg {r[2]}min | max {r[3]}min | avg TPR {r[4]}"))

    print(t("\n── Längste Episoden ───────────────────────────────────",
            "\n── Longest episodes ───────────────────────────────────"))
    for r in conn.execute("""
        SELECT episode_start, episode_end, dauer_min, tpr_mean, hr_mean,
               time_of_day, detection_method, source, confidence
        FROM arrhythmie_episoden WHERE person = ?
        ORDER BY dauer_min DESC LIMIT 10""", (person,)):
        print(f"  {r[0][:16]} – {r[1][11:16]} | {r[2]}min | "
              f"TPR∅ {r[3]} | HR∅ {r[4]} bpm | {r[5]} | {r[7]} [{r[8]}]")

    conn.close()
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))


if __name__ == "__main__":
    main()
