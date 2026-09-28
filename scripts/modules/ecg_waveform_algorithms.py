# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
ecg_waveform_algorithms.py — P/QRS-Wellen-Delineation aus EKG-Rohwellenform

@tier        research
@purpose.de  Bietet reine mathematische Funktionen zur Erkennung von P-Welle
             und QRS-Komplex in roher EKG-Wellenform (Einzelableitung) sowie
             zur Berechnung des PR-Intervalls und der QRS-Dauer. Arbeitet auf
             Spannungswerten (mV), nicht auf RR-Intervallen — Gegenstueck zu
             modules/rr_interval_algorithms.py, das ausschliesslich auf
             Intervall-Sequenzen arbeitet (s. dortiges @limits fuer die
             bewusste Trennung dieser beiden Module).
@purpose.en  Provides pure mathematical functions for detecting the P wave
             and QRS complex in raw single-lead ECG waveform, and for
             computing the PR interval and QRS duration. Operates on voltage
             samples (mV), not RR intervals — the counterpart to
             modules/rr_interval_algorithms.py, which operates exclusively
             on interval sequences (see that module's @limits for the
             deliberate separation between the two).
@method.de   Nutzt neurokit2 (Pflichtabhaengigkeit, s. requirements.txt) fuer
             die eigentliche Signalverarbeitung: nk.ecg_clean(method=
             "biosppy") zur Vorverarbeitung, nk.ecg_peaks() zur R-Zacken-
             Erkennung, dann nk.ecg_delineate(method="dwt") fuer die Wavelet-
             basierte Delineation (Martinez et al. 2004 — dieselbe
             Methodenfamilie, die neurokit2 intern implementiert). Aus den
             delinierten Fixpunkten je Beat werden berechnet:
               PR-Intervall  = R-Onset - P-Onset
               QRS-Dauer     = R-Offset - R-Onset
             QT-Intervall/QTc werden NICHT berechnet (s. @limits — die
             T-Wellen-Offset-Erkennung war empirisch nicht verlaesslich genug,
             um sie zu berichten).
             Wahl von method="biosppy" statt des neurokit2-Standard-Cleanings:
             empirisch gegen einen Withings-BPM-Core-Referenzwert (eigenes
             zertifiziertes Geraete-Ergebnis, PR=144ms/QRS=60ms fuer dieselbe
             Aufnahme) geprueft. Die Standard-Cleaning-Methode ergab
             durchgehend implausible QRS-Dauern (130-190ms, klinisch
             Schenkelblock-Territorium, aber auf praktisch jedem Beat) —
             biosppy+dwt traf den QRS-Referenzwert exakt und kam beim
             PR-Intervall deutlich naeher (122ms) als die Standardkombination
             (94ms), bei zugleich fast doppelt so hoher Beat-Abdeckung
             (106 statt 51 von 114 R-Zacken vollstaendig deliniert).
@method.en   Uses neurokit2 (required dependency, see requirements.txt) for
             the actual signal processing: nk.ecg_clean(method="biosppy")
             for preprocessing, nk.ecg_peaks() for R-peak detection, then
             nk.ecg_delineate(method="dwt") for wavelet-based delineation
             (Martinez et al. 2004 — the same method family neurokit2
             implements internally). From the delineated fiducial points
             per beat, the following are computed:
               PR interval  = R-Onset - P-Onset
               QRS duration = R-Offset - R-Onset
             QT interval/QTc are NOT computed (see @limits — T-wave offset
             detection was not empirically reliable enough to report).
             Choice of method="biosppy" over neurokit2's default cleaning:
             empirically checked against a Withings BPM Core reference value
             (its own certified device result, PR=144ms/QRS=60ms for the
             same recording). The default cleaning method consistently gave
             implausible QRS durations (130-190ms, clinically bundle-branch-
             block territory, but on practically every beat) — biosppy+dwt
             hit the QRS reference value exactly and came much closer on PR
             (122ms) than the default combination (94ms), while covering
             almost twice as many beats (106 vs. 51 of 114 R-peaks fully
             delineated).
@refs        Martinez JP, Almeida R, Olmos S, Rocha AP, Laguna P (2004). A wavelet-based ECG delineator: evaluation on standard databases. IEEE Transactions on Biomedical Engineering, 51(4):570-581. doi:10.1109/TBME.2003.821031
             Makowski D, Pham T, Lau ZJ et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. Behavior Research Methods, 53(4):1689-1696. doi:10.3758/s13428-020-01516-y
@reads       Keine Tabellen (reine Mathematik)
@writes      Keine Tabellen (gibt Berechnungsergebnisse zurück)

@relevance.de  Ermoeglicht PR-/QRS-Zeitmessung aus konsumer-EKG-Rohdaten
               (Apple Watch, ECG Logger/H10), die diese Werte selbst nicht
               berechnen/liefern — Withings BPM Core liefert PR/QRS/QT/QTc
               bereits geraeteeigen zertifiziert und braucht dieses Modul
               nicht.
@relevance.en  Enables PR/QRS interval measurement from consumer ECG raw
               data (Apple Watch, ECG Logger/H10) that do not compute/report
               these values themselves — Withings BPM Core already reports
               PR/QRS/QT/QTc via its own certified on-device algorithm and
               does not need this module.
@limits.de   Weder die Delineation (neurokit2/DWT) noch die hier gezogenen
             Schlussfolgerungen sind an einem konsumer-Einzelableitungs-EKG
             klinisch validiert — Martinez et al. 2004 validierten auf
             klinischen 12-Kanal-Datenbanken (QT Database u.a.), nicht auf
             Apple-Watch-/H10-Einzelableitungssignalen. QT/QTc wurden bewusst
             AUS DEM UMFANG GENOMMEN: die T-Wellen-Offset-Erkennung erwies
             sich in einem Empirie-Test gegen eine Withings-BPM-Core-
             Referenzaufnahme als instabil (QT-Werte zwischen 102ms und
             386ms *innerhalb derselben 60-Sekunden-Aufnahme*, physiologisch
             nicht plausibel) — lieber PR/QRS zuverlaessig als PR/QRS/QT/QTc
             mit einer stillschweigend unzuverlaessigen QT-Komponente. Die
             P-Welle ist amplituden-schwach und schwerer zuverlaessig zu
             delinieren als der QRS-Komplex — PR-Intervall-Werte sind
             entsprechend unsicherer als die QRS-Dauer (P-Onset-Fehler wirkt
             sich direkt und ungedaempft auf PR aus). Einzelne Beats ohne
             vollstaendige Delineation (P- oder R-Onset/-Offset nicht
             erkannt) werden uebersprungen statt geraten — kein
             Interpolieren fehlender Fixpunkte. Kein Ersatz fuer ein
             klinisches 12-Kanal-EKG oder aerztliche Befundung.
@limits.en   Neither the delineation (neurokit2/DWT) nor the conclusions
             drawn here are clinically validated on consumer single-lead
             ECG — Martinez et al. 2004 validated on clinical 12-lead
             databases (QT Database etc.), not on Apple Watch/H10 single-
             lead signals. QT/QTc were deliberately dropped from scope:
             T-wave offset detection proved unstable in an empirical test
             against a Withings BPM Core reference recording (QT values
             ranging from 102ms to 386ms *within the same 60-second
             recording*, not physiologically plausible) — better a reliable
             PR/QRS than a PR/QRS/QT/QTc set with a silently unreliable QT
             component. The P wave is low-amplitude and harder to reliably
             delineate than the QRS complex — PR interval values are
             correspondingly less certain than QRS duration (P-onset error
             propagates directly and undamped into PR). Individual beats
             without complete delineation (P or R onset/offset not detected)
             are skipped, not guessed — no interpolating missing fiducial
             points. Not a replacement for a clinical 12-lead ECG or
             physician interpretation.
@usage
    from modules.ecg_waveform_algorithms import delineate_and_measure
    beats = delineate_and_measure(signal_mv, fs_hz=512)
"""

import math

PR_PLAUSIBLE_MS  = (80.0, 300.0)   # weit gefasstes Plausibilitaets-Gate, s. Docstring unten
QRS_PLAUSIBLE_MS = (40.0, 200.0)   # weit gefasstes Plausibilitaets-Gate, s. Docstring unten
MIN_DELINEATION_FS_HZ = 100.0
# Praktischer, nicht literaturbasierter Mindestwert (s. @limits): darunter
# (z.B. die 50-Hz-Withings-Sessions) sind zu wenige Samples pro QRS-Komplex
# (~80-120ms Dauer) fuer eine sinnvolle Onset-/Offset-Lokalisierung vorhanden
# (<=6 Samples) — bewusst ausgeschlossen statt mit unsicheren Werten
# weiterverarbeitet, analog zur Geraeteklassen-Entscheidung bei der Cuesta-
# PVC-Erkennung in compute_arrhythmia.py.


def delineate_and_measure(signal_mv, fs_hz: float) -> list[dict]:
    """Delineiert P/QRS-Fixpunkte und berechnet PR/QRS je Beat.

    signal_mv: Liste/Array von Spannungswerten in mV (nicht µV — Aufrufer
    ist fuer die Einheitenumrechnung verantwortlich, s. compute_ecg_rpeaks.py).

    Gibt eine Liste von Dicts zurueck, ein Eintrag je Beat MIT vollstaendiger
    Delineation (P-Onset, R-Onset, R-Offset alle gefunden):
    {"r_peak_idx", "pr_ms", "qrs_ms", "rr_ms"}. Beats ohne vollstaendige
    Delineation werden ausgelassen (kein Raten fehlender Fixpunkte, s.
    @limits). QT/QTc werden NICHT berechnet — s. @limits fuer den Grund
    (T-Wellen-Offset-Erkennung empirisch instabil auf dieser Signalqualitaet,
    gegen Withings-BPM-Core-Referenzwerte geprueft)."""
    if fs_hz < MIN_DELINEATION_FS_HZ:
        return []

    import neurokit2 as nk
    import numpy as np

    signal = np.asarray(signal_mv, dtype=float)
    if len(signal) < fs_hz * 2:  # mindestens ~2s für eine sinnvolle Delineation
        return []

    try:
        # method="biosppy" statt des neurokit2-Standard-Cleanings: empirisch
        # gegen Withings-BPM-Core-Referenzwerte (eigenes zertifiziertes
        # Geraete-Ergebnis) geprueft — biosppy+dwt traf den QRS-Referenzwert
        # exakt (60ms) und lag beim PR-Intervall deutlich naeher am
        # Referenzwert als die Standard-Kombination (neurokit-Cleaning
        # ergab durchgehend implausible QRS-Dauern >130ms).
        cleaned = nk.ecg_clean(signal, sampling_rate=fs_hz, method="biosppy")
        _, rpeak_info = nk.ecg_peaks(cleaned, sampling_rate=fs_hz)
        rpeaks = rpeak_info["ECG_R_Peaks"]
        if len(rpeaks) < 3:
            return []
        _, waves = nk.ecg_delineate(cleaned, rpeaks, sampling_rate=fs_hz, method="dwt")
    except Exception:
        # neurokit2 wirft bei zu kurzen/verrauschten Segmenten diverse interne
        # Exceptions (u.a. aus scipy) — kein Ergebnis fuer dieses Segment statt Crash.
        return []

    p_onsets = waves.get("ECG_P_Onsets", [])
    r_onsets = waves.get("ECG_R_Onsets", [])
    r_offsets = waves.get("ECG_R_Offsets", [])

    n = len(rpeaks)
    results = []
    for i in range(1, n):  # ab Beat 1: RR-Intervall zum Vorgaenger benoetigt
        def _val(arr, idx):
            if idx >= len(arr):
                return None
            v = arr[idx]
            return None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v)

        p_on = _val(p_onsets, i)
        r_on = _val(r_onsets, i)
        r_off = _val(r_offsets, i)
        if p_on is None or r_on is None or r_off is None:
            continue

        rr_ms = (rpeaks[i] - rpeaks[i - 1]) / fs_hz * 1000.0
        pr_ms = (r_on - p_on) / fs_hz * 1000.0
        qrs_ms = (r_off - r_on) / fs_hz * 1000.0
        # Plausibilitaets-Gate, kein klinischer Normwert-Filter: verwirft nur
        # Werte ausserhalb jeder physiologischen Moeglichkeit (Delineations-
        # Artefakte wie z.B. ein einzelner 320ms-QRS-Ausreisser, der in einem
        # Testlauf beobachtet wurde) — deutlich weiter gefasst als der
        # klinische Normbereich (PR 120-200ms, QRS 80-100ms), damit echte
        # Pathologien (AV-Block, Schenkelblock) nicht mitverworfen werden.
        if not (PR_PLAUSIBLE_MS[0] <= pr_ms <= PR_PLAUSIBLE_MS[1]):
            continue
        if not (QRS_PLAUSIBLE_MS[0] <= qrs_ms <= QRS_PLAUSIBLE_MS[1]):
            continue

        results.append({
            "r_peak_idx": int(rpeaks[i]),
            "rr_ms": round(rr_ms, 1),
            "pr_ms": round(pr_ms, 1),
            "qrs_ms": round(qrs_ms, 1),
        })

    return results
