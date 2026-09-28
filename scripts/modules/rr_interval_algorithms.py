# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
rr_interval_algorithms.py — Gemeinsame RR-Intervall-Algorithmen (HRV-Metriken
+ Beat-Rhythmusklassifikation)

@tier        infrastructure
@purpose.de  Bietet reine mathematische Algorithmen auf RR-/Puls-Intervall-
             Sequenzen ohne DB-Zugriff oder Config — sowohl klassische HRV-
             Streuungsmasse (TPR, SampEn, Shannon-Entropie) als auch Beat-
             Ebenen-Rhythmusklassifikation (Bigeminie-Lauf-Erkennung,
             Einzel-PVC-Erkennung), die selbst keine Variabilitaetsmasse
             sind, aber denselben Eingabetyp (Intervall-Sequenz) und dieselbe
             DB-/Config-freie Architektur teilen. Importierbar von
             verschiedenen Analyse-Skripten.
@purpose.en  Provides pure mathematical algorithms on RR/pulse-interval
             sequences without DB access or config — both classic HRV
             dispersion metrics (TPR, SampEn, Shannon entropy) and beat-level
             rhythm classification (bigeminy-run detection, single-PVC
             detection), which are not variability metrics themselves but
             share the same input type (interval sequence) and the same
             DB-/config-free architecture. Importable from various analysis
             scripts.
@method.de   HRV-Metriken: turning_point_ratio (Anteil lokaler Extrema, TPR /
             Tateno & Glass), sample_entropy (SampEn nach Kubios-Standard),
             shannon_entropy_rr (normalisierte Shannon-Entropie).
             AFib-Detektion: detect_tateno_glass (ECG/Brustgurt),
             detect_sampentropy (optische Sensoren), detect_dash2009 (PPG).
             Hilfsfunktion: filter_beat_artifacts (lokale Median-Ausreisser-
             Filterung fuer einzelne Puls-Abstaende — s. Docstring der
             Funktion fuer die Herkunft: urspruenglich in
             compute_orthostatic_detection.py entwickelt, hierher verschoben,
             nachdem derselbe Boundary-Clipping-Artefakt [Geraete-/Import-
             Bodenwert bei sehr kurzen pulse_ms-Werten] auch in
             analyse_ecg_24h.py gefunden wurde).
             Beat-Rhythmusklassifikation (kein HRV-Streuungsmass, sondern
             Klassifikation einzelner Beat-Uebergaenge/Beats): classify_beat_pattern
             (Short/Normal/Long-Klassifikation je Beat-Uebergang ueber die
             momentane Herzfrequenz-Differenz, 5-BPM-Nullquadrant-Schwelle
             nach Han et al. 2020), detect_bigeminy_runs (erkennt anhaltende
             Short-Long-Alternanz als RR-Korrelat von Bigeminie — publizierte
             Schwellen: min. 5 S-L-Paare, Vektorwinkel-Standardabweichung
             <= 10 Grad), compute_prematurity_features/
             detect_premature_beats_cuesta (Prematurity/Compensatory-Pause
             je Einzelbeat und Klassifikation nach Cuesta et al. 2014 —
             erkennt isolierte vorzeitige Schlaege, komplementaer zu
             detect_bigeminy_runs, s. Docstring der Funktionen und @limits
             unten fuer den genauen Umfang der Replikation).
@method.en   HRV metrics: turning_point_ratio (local extrema ratio, TPR /
             Tateno & Glass), sample_entropy (SampEn per Kubios standard),
             shannon_entropy_rr (normalized Shannon entropy).
             AFib detection: detect_tateno_glass (ECG/chest strap),
             detect_sampentropy (optical sensors), detect_dash2009 (PPG).
             Helper: filter_beat_artifacts (local-median outlier filtering
             for individual pulse intervals — see the function's own
             docstring for provenance: originally developed in
             compute_orthostatic_detection.py, moved here after the same
             boundary-clipping artifact [a device/import floor value
             affecting very short pulse_ms values] was also found in
             analyse_ecg_24h.py).
             Beat-level rhythm classification (not an HRV dispersion metric,
             but classification of individual beat transitions/beats):
             classify_beat_pattern (per-beat-transition short/normal/long
             classification via instantaneous heart-rate difference, 5-BPM
             zero-quadrant threshold per Han et al. 2020), detect_bigeminy_runs
             (detects sustained short-long alternation as the RR correlate of
             bigeminy — published thresholds: min. 5 S-L pairs, vector-angle
             standard deviation <= 10 degrees), compute_prematurity_features/
             detect_premature_beats_cuesta (per-beat prematurity/compensatory
             pause and classification per Cuesta et al. 2014 — detects
             isolated premature beats, complementary to detect_bigeminy_runs,
             see the functions' own docstrings and @limits below for the
             exact scope of replication).
@reads       Keine Tabellen (reine Mathematik)
@writes      Keine Tabellen (gibt Berechnungsergebnisse zurück)
@refs        Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
             Han D, Bashar SK, Mohagheghian F et al. (2020). Premature Atrial and Ventricular Contraction Detection using Photoplethysmographic Data from a Smartwatch. Sensors (Basel), 20(19):5683. doi:10.3390/s20195683
             Cuesta P, Lado MJ, Vila XA, Alonso R (2014). Detection of premature ventricular contractions using the RR-interval signal: a simple algorithm for mobile devices. Technology and Health Care, 22(4):651-656. doi:10.3233/THC-140818


@relevance.de  Bietet RR-Intervall-Algorithmen (HRV + Rhythmusklassifikation),
               essentiell für die autonome Gesundheitsüberwachung
@relevance.en  Provides RR-interval algorithms (HRV + rhythm classification),
               essential for autonomic health monitoring
@limits.de   Reine Mathematik ohne klinische Validierung. Keine Diagnose-Funktion.
             detect_bigeminy_runs/classify_beat_pattern: Die drei publizierten
             Zahlenschwellen aus Han et al. 2020 (5-BPM-Nullquadrant, min. 5
             S-L-Paare, Vektorwinkel-SD <= 10 Grad) werden repliziert — NICHT
             repliziert wird deren vollstaendiges 9-Quadranten-Poincare-Raster
             (Zugriff nur auf den Volltext, nicht auf die Original-Abbildung
             mit der exakten Quadranten-Nummerierung), deren AF/NSR-Vorstufe
             (die Methode wird bei Han et al. NUR auf Segmente angewandt, die
             zuvor als AF oder NSR klassifiziert wurden) und deren
             Bewegungsartefakt-Erkennung per Beschleunigungssensor. Validiert
             wurde die Originalmethode auf Smartwatch-PPG (Samsung Simband/
             Gear S3) und MIMIC-III-Pulsoximetrie-PPG — nicht auf Polar-H10/
             H7-Brustgurt-EKG-RR, wie es hier zusaetzlich verwendet wird;
             die Uebertragung auf EKG-Qualitaets-RR ist plausibel (RR-
             Praezision dort hoeher als bei PPG), aber selbst nicht
             separat validiert.
             detect_premature_beats_cuesta/compute_prematurity_features: Die
             Feature-Formeln (Prematurity/Compensatory Pause, 10-Beat-Fenster)
             sind exakt nach Cuesta et al. 2014 (Abschnitt 2.2.1) repliziert.
             NICHT repliziert ist die tatsaechlich trainierte LDA-Entscheidungs-
             grenze — das Paper veroeffentlicht nur die empirischen Klassen-
             mittel (Normal: -0,048/-0,027, PVC: 0,265/0,203), nicht die
             LDA-Koeffizienten oder Kovarianzmatrix. Die hier verwendete
             Naechster-Klassenschwerpunkt-Klassifikation ist die korrekte
             Reduktion einer LDA unter der Annahme gleicher/isotroper
             Kovarianz beider Klassen — eine dokumentierte Naeherung mit den
             einzigen tatsaechlich publizierten Zahlen, nicht die byte-genaue
             Original-Entscheidungsgrenze. Ausserdem mittelt das Original ueber
             die 10 vorangehenden, bereits als normal ANNOTIERTEN Beats
             (Ground-Truth im MIT-BIH verfuegbar); hier wird ueber die 10
             unmittelbar vorangehenden Beats unabhaengig von ihrer
             Klassifikation gemittelt, da online keine Ground-Truth-Labels
             vorliegen. Das Verfahren selbst versagt laut den Autoren bei
             anhaltenden Mustern wie Bigeminie-Couplets — es ist komplementaer
             zu detect_bigeminy_runs (Einzelschlag- vs. Lauf-Erkennung), kein
             Ersatz dafuer.
@limits.en   Pure mathematics without clinical validation. No diagnostic function.
             detect_bigeminy_runs/classify_beat_pattern: the three published
             numeric thresholds from Han et al. 2020 (5-BPM zero-quadrant,
             min. 5 S-L pairs, vector-angle SD <= 10 degrees) are replicated —
             NOT replicated is their full 9-quadrant Poincare grid (only
             full-text access available, not the original figure with the
             exact quadrant numbering), their AF/NSR pre-classification step
             (in Han et al. the method is only applied to segments already
             classified as AF or NSR), or their accelerometer-based motion-
             artifact rejection. The original method was validated on
             smartwatch PPG (Samsung Simband/Gear S3) and MIMIC-III pulse-
             oximetry PPG — not on Polar H10/H7 chest-strap ECG-derived RR,
             which is additionally used here; extrapolating to ECG-quality RR
             is plausible (RR precision there is higher than PPG) but not
             itself separately validated.
             detect_premature_beats_cuesta/compute_prematurity_features: the
             feature formulas (prematurity/compensatory pause, 10-beat window)
             are replicated exactly per Cuesta et al. 2014 (section 2.2.1).
             NOT replicated is the actually trained LDA decision boundary —
             the paper only publishes the empirical class means (normal:
             -0.048/-0.027, PVC: 0.265/0.203), not the LDA coefficients or
             covariance matrix. The nearest-class-centroid classification used
             here is the correct reduction of an LDA under the assumption of
             equal/isotropic covariance between classes — a documented
             approximation using the only actually published numbers, not the
             byte-exact original decision boundary. The original also averages
             over the 10 preceding beats already ANNOTATED as normal
             (ground truth available in MIT-BIH); here the 10 immediately
             preceding beats are averaged regardless of their classification,
             since no ground-truth labels are available online. The authors
             themselves state the method fails for sustained patterns such as
             bigeminy couplets — it is complementary to detect_bigeminy_runs
             (single-beat vs. run detection), not a replacement for it.
@usage
    from modules.rr_interval_algorithms import turning_point_ratio, detect_bigeminy_runs
    from modules.rr_interval_algorithms import detect_premature_beats_cuesta
"""

import math
import statistics

import numpy as np

try:
    import neurokit2 as nk
    _NK = True
except ImportError:
    _NK = False


# ── Basisfunktionen ───────────────────────────────────────────────────────────

def turning_point_ratio(rr) -> float | None:
    """
    Anteil lokaler Extrema in der RR-Zeitreihe: turns / (n - 2).

    Referenz: Tateno & Glass 2001, doi:10.1007/BF02345439 (adaptiert auf Raw-RR).
    AFDB-Kalibrierung: Sinus 0.10–0.45, AFib > 0.57, Threshold 0.5743, AUC 0.882.
    Wichtig: Roh-RR verwenden — Artefakt-Interpolation senkt TPR künstlich auf ~0.

    Akzeptiert list oder np.ndarray; gibt None zurück wenn n < 3.
    """
    rr_l = list(rr) if not isinstance(rr, list) else rr
    n = len(rr_l)
    if n < 3:
        return None
    turns = sum(
        1 for i in range(1, n - 1)
        if (rr_l[i] > rr_l[i-1] and rr_l[i] > rr_l[i+1])
        or (rr_l[i] < rr_l[i-1] and rr_l[i] < rr_l[i+1])
    )
    return turns / (n - 2)


def filter_beat_artifacts(pulses_ms, pct_max: float = 0.20, return_mask: bool = False):
    """Verwirft einzelne Puls-Abstaende, die um mehr als pct_max vom Median ihrer
    LOKALEN NACHBARSCHAFT (je bis zu 3 Beats davor/danach) abweichen. Lokaler
    Median statt Vergleich nur mit dem letzten gueltigen Beat, da Letzteres
    Artefakte uebersieht, die direkt auf einen echten schnellen Beat folgen.

    Urspruenglich fuer compute_orthostatic_detection.py entwickelt: dort wurde
    empirisch gefunden, dass sehr kurze Puls-Abstaende (nahe der ueblichen
    300ms-Untergrenze bei ppi_raw-Abfragen) wiederholt, isoliert und ueber Jahre
    hinweg exakt-identisch verteilt auftauchen — ein Muster, das zu einem
    systematischen Geraete-/Import-Bodenwert passt, nicht zu echter Physiologie
    (eine echte Tachykardie trifft nicht ueber Jahre wiederholt exakt denselben
    Dezimalwert). Besonders wichtig fuer jede MAX-artige Statistik ueber einzelne
    Beats (z.B. Spitzenherzfrequenz aus 60000/min(pulse_ms)) — ein Mittelwert
    ueber viele Beats wird von einem einzelnen Ausreisser kaum verschoben, ein
    Maximum/Minimum dagegen direkt und vollstaendig getroffen.

    Ein echter, ANHALTENDER schneller Abschnitt bleibt erhalten, weil dort auch
    die Nachbarn schnell sind und der lokale Median mitsteigt — nur einzelne
    Ausreisser relativ zu ihrer eigenen Umgebung fliegen raus.

    Erwartet chronologisch sortierte Puls-Abstaende in Millisekunden.

    return_mask=True gibt zusaetzlich eine bool-Liste (gleiche Laenge wie die
    Eingabe) zurueck, die markiert, welche Beats behalten wurden — damit
    parallele Arrays (z.B. Beat-weise Labels) konsistent mitgefiltert werden
    koennen, ohne die gefilterten Werte gegen die Eingabe zurueck-matchen zu
    muessen (unsicher bei wiederholten Werten)."""
    pulses_ms = list(pulses_ms)
    n = len(pulses_ms)
    if n < 5:
        return (pulses_ms, [True] * n) if return_mask else pulses_ms
    filtered = []
    keep = []
    for i in range(n):
        neighbors = pulses_ms[max(0, i - 3):i] + pulses_ms[i + 1:i + 4]
        if not neighbors:
            filtered.append(pulses_ms[i])
            keep.append(True)
            continue
        local_median = statistics.median(neighbors)
        ok = local_median > 0 and abs(pulses_ms[i] - local_median) / local_median <= pct_max
        keep.append(ok)
        if ok:
            filtered.append(pulses_ms[i])
    return (filtered, keep) if return_mask else filtered


def classify_beat_pattern(pulses_ms, zero_band_bpm: float = 5.0) -> list:
    """Klassifiziert jeden Beat-zu-Beat-Uebergang ueber die momentane
    Herzfrequenz-Differenz (BPM) zwischen aufeinanderfolgenden Beats — 'S'
    (short/vorzeitig, HF steigt um mehr als zero_band_bpm), 'L' (long/
    kompensatorische Pause, HF faellt um mehr als zero_band_bpm), sonst 'N'
    (normal, innerhalb der "Nullquadrant"-Bandbreite).

    zero_band_bpm=5.0 (Default) ist NICHT frei erfunden, sondern die
    publizierte "zeroth quadrant"-Breite (+/-5 BPM, 10 BPM Gesamtbreite) aus
    Han D, Bashar SK, Mohagheghian F et al. (2020). Premature Atrial and
    Ventricular Contraction Detection using Photoplethysmographic Data from
    a Smartwatch. Sensors (Basel), 20(19):5683. doi:10.3390/s20195683 —
    empirisch optimiert (+/-3 BPM getestet, 5 BPM blieb bestes Ergebnis),
    auf 3 unabhaengigen Datensaetzen validiert (Simband/Gear S3/MIMIC-III,
    >92% Accuracy). Diese Funktion reproduziert den Schwellenwert der
    publizierten Methode, nicht deren vollstaendiges 9-Quadranten-Poincare-
    Raster (s. Docstring von detect_bigeminy_runs @limits fuer die genaue
    Abgrenzung, was hier repliziert wird und was nicht).

    Grundlage fuer detect_bigeminy_runs() unten. Erwartet chronologisch
    sortierte Puls-Abstaende in Millisekunden; gibt eine Liste der Laenge
    n-1 zurueck (ein Label pro Uebergang, nicht pro Beat)."""
    pulses_ms = list(pulses_ms)
    hrs = [60000.0 / p if p and p > 0 else None for p in pulses_ms]
    labels = []
    for i in range(1, len(hrs)):
        if hrs[i] is None or hrs[i - 1] is None:
            labels.append('N')
            continue
        delta_bpm = hrs[i] - hrs[i - 1]
        if delta_bpm > zero_band_bpm:
            labels.append('S')
        elif delta_bpm < -zero_band_bpm:
            labels.append('L')
        else:
            labels.append('N')
    return labels


def detect_bigeminy_runs(timestamps, pulses_ms, min_pairs: int = 5,
                          zero_band_bpm: float = 5.0, angle_sd_max_deg: float = 10.0) -> list:
    """Erkennt anhaltende Short-Long-Alternanz (S-L-S-L-...) — das RR-
    Intervall-Korrelat von Bigeminie (vorzeitiger Schlag + kompensatorische
    Pause, wiederholt jeden zweiten Schlag).

    Implementiert die publizierten, validierten Schwellenwerte aus Han et
    al. 2020 (Sensors 20(19):5683, doi:10.3390/s20195683) fuer genau das
    "2-4"/"4-2"-Bigeminie-Muster ihres Poincare-Plot-Verfahrens:
      - Beat-Klassifikation ueber die 5-BPM-Nullquadrant-Schwelle (s.
        classify_beat_pattern oben)
      - min_pairs=5: die Publikation verlangt fuer das bigeminie-spezifische
        "2-4"/"4-2"-Muster (Algorithm 2, NSR-Pfad) "more than 5 pairs" —
        strenger als ihr allgemeines PAC/PVC-Kriterium (>3 Wiederholungen
        fuer die "1-2-3"/"6-4-5"-Muster, die andere Arrhythmien abdecken)
      - angle_sd_max_deg=10.0: die "vector resemblance"-Pruefung — pro S-L-
        Zyklus wird ein Vektor (delta_HF_short, delta_HF_long) gebildet, sein
        Winkel per atan2 bestimmt; die Standardabweichung der Winkel ueber
        alle Zyklen einer Episode muss <= 10 Grad bleiben, sonst wird der
        Fund verworfen. Genau dieser Schwellenwert wurde in der Publikation
        gegen 5/10/15/20 Grad getestet, 10 Grad war optimal (s. @limits
        dieses Moduls fuer die Abgrenzung ggue. dem Original).

    Erwartet gleich lange, chronologisch sortierte Listen von Timestamps
    (beliebiger, vergleichbarer Typ) und Puls-Abstaenden in Millisekunden.

    Gibt eine Liste von Dicts zurueck: start_idx, end_idx (inklusive, in den
    Eingabelisten), start_ts, end_ts, n_cycles, angle_sd_deg."""
    labels = classify_beat_pattern(pulses_ms, zero_band_bpm)  # length n-1, index i = transition i->i+1
    hrs = [60000.0 / p if p and p > 0 else None for p in pulses_ms]
    n = len(labels)
    runs = []
    i = 0
    while i < n - 1:
        if labels[i] == 'S' and labels[i + 1] == 'L':
            start_label_idx = i
            angles = []
            j = i
            while j + 1 < n and labels[j] == 'S' and labels[j + 1] == 'L':
                h_prev, h_s, h_l = hrs[j], hrs[j + 1], hrs[j + 2] if j + 2 < len(hrs) else None
                if h_prev is not None and h_s is not None and h_l is not None:
                    d_short = h_s - h_prev
                    d_long  = h_l - h_s
                    angles.append(math.degrees(math.atan2(d_long, d_short)))
                j += 2
            cycles = (j - start_label_idx) // 2
            if cycles >= min_pairs:
                angle_sd = statistics.pstdev(angles) if len(angles) > 1 else 0.0
                if angle_sd <= angle_sd_max_deg:
                    # Beat-Indizes: Uebergang k liegt zwischen Beat k und Beat k+1
                    start_beat = start_label_idx
                    end_beat   = j  # letzter Beat des letzten vollstaendigen L-Uebergangs
                    runs.append({
                        "start_idx": start_beat, "end_idx": end_beat,
                        "start_ts": timestamps[start_beat], "end_ts": timestamps[end_beat],
                        "n_cycles": cycles, "angle_sd_deg": round(angle_sd, 1),
                    })
            i = j
        else:
            i += 1
    return runs


# Cuesta et al. 2014 (Technology and Health Care 22(4):651-656, doi:10.3233/THC-140818):
# empirische Klassenmittel aus Tabelle/Text des Papers (MIT-BIH, 4-fach kreuzvalidiert,
# LDA), NICHT die (unveröffentlichten) trainierten LDA-Koeffizienten selbst — s.
# Docstring von detect_premature_beats_cuesta() fuer die Konsequenz daraus.
_CUESTA_MEAN_NORMAL = (-0.048, -0.027)   # (Prematurity, Compensatory Pause)
_CUESTA_MEAN_PVC    = (0.265, 0.203)


def compute_prematurity_features(pulses_ms, window: int = 10):
    """Prematurity/Compensatory-Pause je Beat nach Cuesta et al. 2014, Abschnitt 2.2.1.

    avgRRdist = Mittelwert der `window` unmittelbar vorangehenden Puls-Abstaende
    (Paper: "10 normal beats ... previous to the occurrence of a specific beat",
    experimentell auf 10 festgelegt). Publizierte Formeln:
      Prematurity        = (avgRRdist - RRbeat)   / avgRRdist
      Compensatory Pause = (RRbeat+1  - avgRRdist) / avgRRdist

    Abweichung vom Original: das Paper mittelt ueber die vorangehenden 10 bereits
    als NORMAL re-klassifizierten Beats (Ground-Truth-Annotation im MIT-BIH
    verfuegbar); hier wird stattdessen ueber die 10 unmittelbar vorangehenden
    Beats unabhaengig von ihrer Klassifikation gemittelt, da online keine
    Ground-Truth-Labels vorliegen — eine im Kontext gaengige, vom Original-Paper
    aber nicht selbst gepruefte Vereinfachung (s. @limits des Moduls).

    Gibt zwei gleich lange Listen zurueck (Prematurity, Compensatory Pause),
    Werte sind None, wo kein vollstaendiges Fenster (window Beats davor UND
    ein Beat danach) verfuegbar ist."""
    n = len(pulses_ms)
    prematurity = [None] * n
    compensatory_pause = [None] * n
    for i in range(window, n - 1):
        preceding = pulses_ms[i - window:i]
        if any(p is None or p <= 0 for p in preceding):
            continue
        if pulses_ms[i] is None or pulses_ms[i + 1] is None:
            continue
        avg = sum(preceding) / window
        if avg <= 0:
            continue
        prematurity[i] = (avg - pulses_ms[i]) / avg
        compensatory_pause[i] = (pulses_ms[i + 1] - avg) / avg
    return prematurity, compensatory_pause


def detect_premature_beats_cuesta(pulses_ms, window: int = 10) -> list:
    """Erkennt einzelne vorzeitige Schlaege (PVC-artig) nach Cuesta et al. 2014
    (Technology and Health Care 22(4):651-656, doi:10.3233/THC-140818),
    RR-Intervall-only, MIT-BIH-validiert (Sens. 90,13%/Spez. 82,52%, AUC 0,928).

    Nutzt compute_prematurity_features() fuer die publizierten Merkmale, dann
    Klassifikation ueber Naechster-Klassenschwerpunkt (minimum-distance-to-means):
    das Paper veroeffentlicht nur die empirischen Klassenmittel fuer Prematurity/
    Compensatory Pause (Normal: -0,048/-0,027, PVC: 0,265/0,203, s. Text Abschnitt
    2.2.1), nicht die tatsaechlich trainierten LDA-Koeffizienten oder die
    Kovarianzmatrix (Tabelle 1 zeigt nur AUC/Sensitivitaet/Spezifitaet je Fold).
    Ein Schwerpunkt-Klassifikator ist die mathematisch korrekte Reduktion einer
    LDA auf eine isotrope/gleiche Kovarianz beider Klassen — eine dokumentierte,
    mit den einzigen tatsaechlich publizierten Zahlen begruendete Naeherung an
    die (unveroeffentlichte) Original-Entscheidungsgrenze, keine erfundene.

    Explizit NICHT dasselbe Problem wie detect_bigeminy_runs(): Cuesta et al.
    schreiben selbst im Fazit, ihr Verfahren "fails when more complex patterns
    are present, such as the case of bigeminal couplets or ventricular
    tachycardia" — es erkennt isolierte vorzeitige Einzelschlaege, keine
    anhaltende Short-Long-Alternanz. Komplementaer, kein Ersatz.

    Gibt eine Liste von Dicts zurueck (ein Eintrag je Beat mit vollstaendigem
    Fenster): idx, prematurity, compensatory_pause, is_premature (bool)."""
    prematurity, compensatory_pause = compute_prematurity_features(pulses_ms, window)
    mid = ((_CUESTA_MEAN_NORMAL[0] + _CUESTA_MEAN_PVC[0]) / 2.0,
           (_CUESTA_MEAN_NORMAL[1] + _CUESTA_MEAN_PVC[1]) / 2.0)
    direction = (_CUESTA_MEAN_PVC[0] - _CUESTA_MEAN_NORMAL[0],
                 _CUESTA_MEAN_PVC[1] - _CUESTA_MEAN_NORMAL[1])
    results = []
    for i, (p, c) in enumerate(zip(prematurity, compensatory_pause)):
        if p is None or c is None:
            continue
        score = (p - mid[0]) * direction[0] + (c - mid[1]) * direction[1]
        results.append({
            "idx": i, "prematurity": round(p, 4), "compensatory_pause": round(c, 4),
            "is_premature": score > 0,
        })
    return results


def sample_entropy(rr, m: int = 2, r_factor: float = 0.2) -> float | None:
    """
    Sample Entropy nach Kubios-Standardparametern: m=2, r=0.2×SD.

    Beschleunigt via neurokit2 (wenn installiert), sonst numpy, sonst pure Python.
    Eingabe wird auf 300 Beats begrenzt (Rechenzeit; Kubios-Standard: ≤300).

    Gibt None zurück wenn n < 50 oder Berechnung fehlschlägt.
    """
    rr_arr = np.asarray(rr, dtype=float)
    n = len(rr_arr)
    if n < 50:
        return None
    rr_s = rr_arr[:300]
    try:
        r = r_factor * float(np.std(rr_s, ddof=1))
        if r <= 0:
            return None

        if _NK:
            en, _ = nk.entropy_sample(rr_s, dimension=m, tolerance=r)
            return float(en) if np.isfinite(en) else None

        # numpy-Fallback
        N = len(rr_s)
        def _count(length: int) -> int:
            c = 0
            for i in range(N - length):
                for j in range(i + 1, N - length + 1):
                    if np.max(np.abs(rr_s[i:i+length] - rr_s[j:j+length])) < r:
                        c += 1
            return c
        B = _count(m)
        A = _count(m + 1)
        return float(-np.log(A / B)) if B > 0 and A > 0 else None
    except Exception:
        return None


def shannon_entropy_rr(ppis, bin_width_ms: float = 50.0) -> float:
    """
    Normalisierte Shannon-Entropie des RR-Intervall-Histogramms (0–1).

    RR-Bereich 300–1800 ms, Binbreite 50 ms = 30 Bins.
    Normalisierung: H / log2(n_bins) → 1.0 = maximale Unordnung.
    AFib erzeugt flache Verteilung (hohe Entropie), Sinus konzentriert
    sich auf wenige Bins (niedrige Entropie).

    Ref: Dash et al. 2009, doi:10.1007/s10439-009-9740-z
    """
    min_rr, max_rr = 300, 1800
    n_bins = int((max_rr - min_rr) / bin_width_ms)
    counts = [0] * n_bins
    for rr in ppis:
        idx = int((rr - min_rr) / bin_width_ms)
        idx = max(0, min(n_bins - 1, idx))
        counts[idx] += 1
    n = len(ppis)
    h = sum(-c / n * math.log2(c / n) for c in counts if c > 0)
    h_max = math.log2(n_bins)
    return round(h / h_max, 4) if h_max > 0 else 0.0


# ── AFib-Detektionsfunktionen ─────────────────────────────────────────────────
# Rückgabe: (flag: int, metric: float, method: str)
#   flag   — 1 = Arrhythmie-Verdacht, 0 = unauffällig
#   metric — Hauptmetrik des Algorithmus (TPR, SampEn, Shannon-H)
#   method — lesbarer Bezeichner für detection_method-Spalte

def detect_tateno_glass(ppis: list, rmssd: float,
                        tpr_threshold: float, rmssd_confirm: float
                        ) -> tuple[int, float, str]:
    """
    Tateno & Glass 2001: TPR + RMSSD-Bestätigung.

    Validiert auf MIT-BIH AF Database (24 Records, AFDB-kalibriert).
    Geeignet für ECG und Brustgurt-RR; nicht validiert für optisches PPG.
    """
    tpr = turning_point_ratio(ppis) or 0.0
    flag = 1 if (tpr > tpr_threshold and rmssd >= rmssd_confirm) else 0
    return flag, round(tpr, 4), f'tateno_glass_tpr{tpr_threshold}'


def detect_sampentropy(ppis: list, rmssd: float,
                       sampen_threshold: float = 1.0,
                       cv_threshold: float = 0.10
                       ) -> tuple[int, float, str]:
    """
    SampEn-basierte AFib-Detektion für optische Sensoren.

    Kombination aus Sample Entropy (m=2, r=0.2×SD) und CV:
      AFib wenn: SampEn > sampen_threshold  UND  CV_RR > cv_threshold

    Thresholds sind gerätespezifisch und müssen kalibriert werden.
    Konfigurierbar via clinical.arrhythmia.sampen_threshold / sampen_cv_threshold.

    Wenn SampEn nicht berechenbar (zu wenig Beats): fällt auf CV-Heuristik zurück.
    """
    rr = np.asarray(ppis, dtype=float)
    n = len(ppis)
    mean = float(np.mean(rr)) if n > 0 else 1.0
    sd = float(np.std(rr, ddof=1)) if n > 1 else 0.0
    cv = sd / mean if mean > 0 else 0.0

    se = sample_entropy(rr)
    if se is None:
        flag = 1 if cv > cv_threshold * 1.5 else 0
        return flag, 0.0, 'cv_heuristic_sampen_fallback'

    flag = 1 if (se > sampen_threshold and cv > cv_threshold) else 0
    return flag, round(se, 4), f'sampentropy_H{sampen_threshold}_CV{cv_threshold}'


def detect_dash2009(ppis: list, rmssd: float,
                    h_threshold: float, cv_threshold: float
                    ) -> tuple[int, float, str]:
    """
    Dash et al. 2009: Shannon-Entropie + CV für PPG-Sensoren.

    Ref: Dash S, Chon KH, Lu S, Raeder EA.
         Automatic real time detection of atrial fibrillation.
         Ann Biomed Eng. 2009;37(9):1701-9. doi:10.1007/s10439-009-9740-z
    """
    h_norm = shannon_entropy_rr(ppis)
    n = len(ppis)
    mean = sum(ppis) / n
    sd = math.sqrt(sum((x - mean)**2 for x in ppis) / (n - 1))
    cv = round(sd / mean, 4) if mean > 0 else 0.0
    flag = 1 if (h_norm > h_threshold and cv > cv_threshold) else 0
    return flag, h_norm, f'dash2009_H{h_threshold}_CV{cv_threshold}'
