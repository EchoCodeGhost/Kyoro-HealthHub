#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Orthostase-Kandidaten-Erkennung aus Alltags-PPI-Daten.

@tier        heuristic
@purpose.de  Sucht in durchgehenden Alltags-Herzfrequenzaufzeichnungen (nicht nur
             bewussten Steh-Tests) nach Mustern, die zu einem Lage-/Haltungswechsel
             passen könnten (z. B. Liegen → Stehen), und speichert Kandidaten in
             sessions/session_metrics (type='orthostatic', source_app='ppi_detected')
             zur Auswertung durch analyse_orthostatic.py.
@purpose.en  Scans continuous everyday heart-rate recordings (not just deliberate
             stand tests) for patterns consistent with a position/posture change
             (e.g. lying → standing), storing candidates in sessions/session_metrics
             (type='orthostatic', source_app='ppi_detected') for
             analyse_orthostatic.py to evaluate.
@method.de   Kein Gerät in diesem Projekt exportiert rohe Lage-/Beschleunigungs-
             sensordaten (geprüft: alle imports/-Verzeichnisse + Apple-Health-
             Export.xml-Record-Typen — nichts gefunden, nur der unabhängige
             AppleWalkingSteadiness-Gang-Score, kein Lage-/Orientierungssignal).
             Ersatzweise: gleitendes HF-Fenster aus ppi_raw (device-/quellen-
             unabhängig — jedes Gerät, das Beat-zu-Beat-Daten liefert, auch PPG-
             Wearables wie der Polar Loop, fließt automatisch mit ein, s.
             @limits zur Genauigkeitseinschränkung bei PPG). HARTE EINSCHRÄNKUNG
             für die KONTINUIERLICHE Alltagsüberwachung: Garmin, Oura und die
             kontinuierliche Apple-Watch-HF liefern PER API gar keine Beat-zu-
             Beat-Rohdaten — nur bereits fertig berechnete RMSSD-Fensterwerte
             (Garmin: get_hrv_data(); Oura: hrv.items(), je 5-Minuten-Aggregat).
             Diese landen deshalb nie in ppi_raw und werden von diesem Skript
             unabhängig von device_registry-Einträgen NIE verarbeitet — eine
             Herstellerschnittstellen-Grenze, keine Design-Entscheidung. KEINE
             harte Grenze dagegen für EKG-Einzelaufnahmen (30-Sek.-Snapshots):
             die landen device-agnostisch in ecg_sessions/ecg_samples und werden
             von compute_ecg_rpeaks.py per R-Zacken-Erkennung automatisch in
             echte RR-Intervalle umgewandelt (source dynamisch aus
             ecg_sessions.source, z.B. 'ecg_apple', 'ecg_garmin' — nicht mehr
             Apple-exklusiv seit dem Fix des früheren Mislabeling-Bugs).
             Praktisch aber von der jeweiligen Gerätefähigkeit abhängig: nicht
             jedes Garmin-Modell hat EKG-Hardware (geprüft gegen device_registry
             und GDPR-Exportinhalt: bei reinen Fitness-/Outdoor-Modellen ohne
             EKG-App gibt es schlicht keine *ECG_Details*.json-Dateien) — der Weg
             im Skript existiert, liefert aber nur, wenn das Quellgerät auch
             tatsächlich EKG-Snapshots aufzeichnet. Ein Sprung
             ≥HR_JUMP_MIN bpm (15 bpm — Untergrenze von "grenzwertig" nach der
             Klassifikation in analyse_orthostatic.py, NICHT das
             Sheldon-2015-POTS-Kriterium von 30 bpm: eine eigene Kalibrierung gegen
             echte Steh-Tests zeigte, dass reale HF-Sprünge meist unter dieser
             Schwelle liegen — 30bpm direkt zu verlangen würde echte Episoden
             verpassen), der bereits innerhalb von ONSET_WINDOW_S nach dem
             REF_WINDOW_S-Referenzfenster erreicht wird UND mindestens
             SUSTAIN_MIN_S anhält, gilt als
             Kandidat — die fehlende Übergangslücke erzwingt einen SCHARFEN
             Anstieg (charakteristisch für einen echten Lagewechsel), ein
             langsamer Stress-/MCAS-Anstieg über mehrere Minuten fällt durch.
             RMSSD analog aus denselben Fenstern (chronologische Beat-Reihenfolge,
             nicht wertsortiert). Um Sport-Fehlalarme auszuschließen: wo intraday-
             aufgelöste Schrittdaten existieren (Apple minutengenau als 'steps';
             Polar ebenso minutengenau über die eigene Metrik 'steps_1min', aus den
             samples.steps-Feldern der activity-*.json-Exporte -- die separat
             importierte Tagessumme 'steps' von Polar erlaubt keine Fensterprüfung
             und wird hier bewusst nicht verwendet), muss die Schrittzahl im
             Bestätigungsfenster
             unter STEPS_MAX bleiben — ohne solche Daten wird der Kandidat mit
             einer entsprechenden Notiz statt Ablehnung markiert (fehlende
             Bestätigung ≠ Widerlegung). Zusätzlich: Blutdruckmessungen in einem
             ±BP_WINDOW_MIN-Fenster um den Sprung werden auf orthostatische
             Hypotonie geprüft (Sheldon 2015: SBP-Abfall ≥BP_SYS_DROP_MIN ODER
             DBP-Abfall ≥BP_DIA_DROP_MIN) — rein bestätigend, kein Filter, da nur
             ein Bruchteil der Kandidaten überhaupt eine zufällig nahe BP-Messung
             hat. Erkennt nur EINEN Kandidaten pro Tag (den mit dem größten ΔHR),
             um Überschwemmung durch benachbarte Teil-Treffer derselben echten
             Episode zu vermeiden.
@method.en   No device in this project exports raw position/accelerometer sensor
             data (checked: all imports/ directories + Apple Health Export.xml
             record types — nothing found, only the unrelated AppleWalkingSteadiness
             gait score, no position/orientation signal). Substitute: a rolling HR
             window from ppi_raw (device-/source-agnostic — any device delivering
             beat-to-beat data, including PPG wearables like the Polar Loop, flows
             in automatically, see @limits for the PPG accuracy caveat). HARD
             LIMIT for CONTINUOUS everyday monitoring: Garmin, Oura, and
             continuous Apple Watch HR deliver NO beat-to-beat raw data via
             their APIs at all — only already-computed RMSSD window values
             (Garmin: get_hrv_data(); Oura: hrv.items(), both 5-minute
             aggregates). These therefore never reach ppi_raw and are NEVER
             processed by this script regardless of device_registry entries —
             a vendor API boundary, not a design choice. NO hard limit,
             however, for single ECG recordings (30-sec snapshots): those land
             device-agnostically in ecg_sessions/ecg_samples and are
             automatically converted to genuine RR intervals by
             compute_ecg_rpeaks.py's R-peak detection (source derived
             dynamically from ecg_sessions.source, e.g. 'ecg_apple',
             'ecg_garmin' — no longer Apple-exclusive since the earlier
             mislabeling bug there was fixed). In practice this still depends
             on the source device's own capability: not every model records
             on-device ECG snapshots at all (checked against device_registry
             and export content: fitness/outdoor-only models without an ECG
             app simply produce no *ECG_Details*.json files) — the pathway
             exists in the script but only delivers data if the source device
             actually records ECG snapshots. A jump
             ≥HR_JUMP_MIN bpm (15 bpm — the lower bound of "borderline" per the
             classification in analyse_orthostatic.py, NOT the Sheldon 2015 POTS
             criterion of 30 bpm: an own calibration against real stand tests
             showed genuine HR jumps mostly falling below that threshold —
             requiring 30bpm directly would miss real episodes) that is
             already reached within ONSET_WINDOW_S after the
             REF_WINDOW_S reference window AND sustained for at least
             SUSTAIN_MIN_S counts as a candidate — the
             absence of a transition gap forces a SHARP rise (characteristic of a
             genuine position change), a slow multi-minute stress/MCAS ramp fails
             this. RMSSD analogously from the same windows (chronological beat
             order, not value-sorted). To rule out exercise false alarms: where
             intraday-resolved step data exists (so far only Apple, other sources
             only provide daily totals), step count in the confirmation window
             must stay under STEPS_MAX — without such data the candidate is
             flagged with a note instead of rejected (missing confirmation ≠
             refutation). Additionally: blood pressure readings within a
             ±BP_WINDOW_MIN window around the jump are checked for orthostatic
             hypotension (Sheldon 2015: SBP drop ≥BP_SYS_DROP_MIN OR DBP drop
             ≥BP_DIA_DROP_MIN) — purely confirmatory, not a filter, since only a
             fraction of candidates happen to have a nearby BP reading at all.
             Detects only ONE candidate per day (the one with the largest ΔHR) to
             avoid flooding from adjacent partial hits on the same real episode.
@scoring
    detection (all must hold for a candidate):
      HR jump    >= HR_JUMP_MIN (15 bpm)   within ONSET_WINDOW_S of the reference window
      sustained  >= HR_JUMP_MIN * 0.7      for at least SUSTAIN_MIN_S afterwards
      steps      <= STEPS_MAX              in the confirmation window (if intraday step data exists)
    bp_confirmed (informational, not a filter):
      SBP drop >= BP_SYS_DROP_MIN (20 mmHg) OR DBP drop >= BP_DIA_DROP_MIN (10 mmHg)
      within ±BP_WINDOW_MIN of the candidate, per Sheldon 2015 orthostatic-hypotension criterion
@reads       ppi_raw, measurements (steps, steps_1min), blood_pressure
@writes      sessions, session_metrics (type='orthostatic', source_app='ppi_detected')
@limits.de   Heuristische Methode: eigener Erkennungsalgorithmus, keine publizierte
             Change-Point-Detection-Bibliothek verwendet (einfache gleitende
             Fenstervergleiche). Alltagsdaten sind unkontrollierter als ein echter
             Steh-Test (kein standardisiertes Vor-Verhalten, keine garantierte
             Ruhephase vor dem Sprung) — daher grundsätzlich niedrigere Beweiskraft
             als echte Polar-Steh-Tests (source_app='polar_connect' in derselben
             sessions-Tabelle), selbst bei gleichem ΔHR. Kann NICHT zwischen einem
             echten Lagewechsel und jeder anderen Ursache eines nicht-
             belastungsbedingten HF-Anstiegs unterscheiden (Angst, MCAS-Reaktion,
             Medikamentenwirkung sind ebenfalls plausible Ursachen); ein gefundener
             Kandidat ist "unerklärter scharfer HF-Anstieg ohne Bewegung",
             Orthostase ist eine plausible, aber nicht bewiesene Erklärung dafür. PPG-Quellen (Polar Loop, sensor_type
             optical_wrist_gps) sind bewegungsartefaktanfälliger und weniger
             präzise als Brustgurt-EKG (H7/H10) — Kandidaten von PPG-Geräten
             verdienen weniger Vertrauen als Brustgurt-Kandidaten, auch wenn
             beide gleich behandelt werden (Geräte-ID steht im device_id-Feld
             der Session, kann nachträglich gefiltert werden). HR_JUMP_MIN
             (15 bpm, s. @method), ONSET_WINDOW_S, SUSTAIN_MIN_S, STEPS_MAX,
             BP_SYS_DROP_MIN/BP_DIA_DROP_MIN sind eigene Schwellenwerte für die
             ERKENNUNG (BP-Schwellen selbst sind Sheldon 2015, aber ihre Anwendung
             auf unkontrollierte Alltagsdaten mit ±BP_WINDOW_MIN-Fenster statt
             eines exakten Test-Zeitpunkts ist eigene Naeherung). RMSSD-Werte
             nutzen eine einfache lokale Median-Ausreisser-Filterung (s.
             modules/rr_interval_algorithms.filter_beat_artifacts), NICHT die vollstaendige
             Kubios-Artefaktkorrektur
             aus compute_hrv_advanced.py — die RMSSD-Spalte ist informativ, die
             HF-basierte Erkennung selbst haengt nicht davon ab.
             hr_stand_peak (Aufsteh-Peak) ist die unzuverlaessigste Spalte:
             empirisch gefunden, dass sehr kurze pulse_ms-Werte (≙195-201 bpm)
             wiederholt, isoliert und ueber Jahre exakt-identisch verteilt in
             ppi_raw auftauchen — passt zu einem systematischen Geraete-/Import-
             Bodenwert, nicht zu echter Physiologie. Eine Anhebung des
             PULSE_MS_FLOOR verschiebt das Problem nur auf den neuen Grenzwert
             (die Verteilung reicht offenbar weiter als jeder gesetzte Boden),
             loest es aber nicht — ein einzelner Beat-Maximalwert ist inhaerent
             anfaelliger dafuer als ein Fensterschnitt. hr_stand (der Mittelwert
             im Sustain-Fenster, auf dem die Erkennung selbst beruht) hat dieses
             Problem nicht und ist der vertrauenswuerdigere Wert; hr_stand_peak
             nur als grobe, nicht belastbare Zusatzinformation lesen.
@limits.en   Heuristic method: own detection algorithm, no published change-point
             detection library used (simple rolling-window comparison). Everyday
             data is less controlled than a real stand test (no standardized
             pre-behaviour, no guaranteed rest period before the jump) — so
             inherently lower evidentiary weight than real Polar stand tests
             (source_app='polar_connect' in the same sessions table), even at the
             same delta HR. Cannot distinguish a genuine position
             change from any other cause of non-exertional HR rise (anxiety, MCAS
             reaction, and medication effect are equally plausible causes); a
             found candidate is "unexplained sharp HR rise without movement",
             orthostatic change is a plausible but unproven explanation for it. PPG sources (Polar Loop, sensor_type
             optical_wrist_gps) are more motion-artifact-prone and less precise
             than chest-strap ECG (H7/H10) — candidates from PPG devices deserve
             less trust than chest-strap candidates, even though both are treated
             identically (the device id is in the session's device_id field and
             can be filtered afterwards). HR_JUMP_MIN (15 bpm, see @method), ONSET_WINDOW_S,
             SUSTAIN_MIN_S, STEPS_MAX, BP_SYS_DROP_MIN/BP_DIA_DROP_MIN are own
             thresholds for the DETECTION (the BP thresholds themselves are
             Sheldon 2015, but applying them to uncontrolled everyday data with a
             ±BP_WINDOW_MIN window instead of an exact test moment is an own
             approximation). RMSSD values use a simple local-median outlier
             filter (see modules/rr_interval_algorithms.filter_beat_artifacts), NOT the
             full Kubios artifact correction from compute_hrv_advanced.py — the
             RMSSD column is informational, the HR-based detection itself
             doesn't depend on it.

@relevance.de  Erschließt Orthostase-Verdachtsfälle aus vorhandenen Alltagsdaten
               statt nur aus den seltenen bewussten Tests
@relevance.en  Surfaces suspected orthostatic episodes from existing everyday data
               instead of only the rare deliberate tests
@refs        Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029
               (orthostatische Hypotonie SBP-Abfall ≥20mmHg / DBP-Abfall ≥10mmHg —
               hier als BP-Bestätigungsschwelle verwendet, s. _bp_check. Das
               POTS-Kriterium ΔHR ≥30 bpm aus derselben Quelle wird NICHT als
               Erkennungsschwelle verwendet, s. HR_JUMP_MIN-Begründung in @method)
@usage
    python3 scripts/compute/compute_orthostatic_detection.py
    python3 scripts/compute/compute_orthostatic_detection.py --date-from 2026-01-01
    python3 scripts/compute/compute_orthostatic_detection.py --lang en
"""

import sys
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.rr_interval_algorithms import filter_beat_artifacts
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
_PEM_CFG = getattr(_cfg, "pem_config", {}) or {}

HR_JUMP_MIN     = float(_PEM_CFG.get("ortho_hr_jump_min", 15))  # "grenzwertig"-Untergrenze nach
                                                                  # analyse_orthostatic.py-Klassifikation — nicht
                                                                  # Sheldon-2015-POTS (30bpm): eigene Kalibrierung
                                                                  # gegen echte Steh-Tests zeigte, dass 30bpm direkt
                                                                  # reale Episoden verpassen wuerde.
REF_WINDOW_S    = int(_PEM_CFG.get("ortho_ref_window_s", 180))
ONSET_WINDOW_S  = int(_PEM_CFG.get("ortho_onset_window_s", 45))
SUSTAIN_MIN_S   = int(_PEM_CFG.get("ortho_sustain_min_s", 180))
STEPS_MAX       = int(_PEM_CFG.get("ortho_steps_max", 30))
MIN_BEATS       = int(_PEM_CFG.get("ortho_min_beats", 15))
BIN_S           = 15  # Bin-Breite für die gleitende HF-Serie


ARTIFACT_PCT_MAX = float(_PEM_CFG.get("ortho_artifact_pct_max", 0.20))
# Hoehere Untergrenze als die projektweit uebliche 300ms (siehe z.B.
# compute_stress.py) — empirisch gefunden: Werte im 299-310ms-Bereich
# (≙196-201 bpm) tauchen wiederholt, isoliert und exakt-identisch verteilt in
# ppi_raw auf — ein Muster, das zu einem systematischen Geraete-/Import-
# Bodenwert passt, nicht zu echter Physiologie (eine echte Tachykardie trifft
# nicht wiederholt exakt denselben Dezimalwert an unabhaengigen Tagen ueber
# mehrere Jahre). Ein lokaler Median-Filter
# (s. modules/rr_interval_algorithms.filter_beat_artifacts) allein reicht nicht, wenn
# der Ausreisser waehrend einer bereits erhoehten Phase auftritt. Nur fuer
# DIESES Skript erhoeht — andere Skripte, die ppi_raw mit dem 300ms-
# Standardfilter lesen, koennten denselben blinden Fleck haben; in
# analyse_ecg_24h.py (hr_max = 60000/min(pulse_ms) ueber den ganzen Tag,
# dasselbe MAX-ueber-Einzelbeat-Muster) wurde er gefunden und mit derselben
# geteilten Filterfunktion behoben. Nicht jedes Skript mit dem 300ms-Filter ist
# betroffen — nur MAX/MIN-artige Statistiken ueber einzelne Beats, nicht
# Mittelwerte (ein Ausreisser verschiebt einen Mittelwert kaum, ein Maximum
# aber vollstaendig).
PULSE_MS_FLOOR = int(_PEM_CFG.get("ortho_pulse_ms_floor", 315))


def _rmssd(pulses_ms: list) -> "float | None":
    # Lokale Median-Ausreisser-Filterung, s. modules/rr_interval_algorithms.filter_beat_artifacts
    # (urspruenglich hier entwickelt, dorthin verschoben, nachdem derselbe
    # Boundary-Clipping-Artefakt auch in analyse_ecg_24h.py gefunden wurde).
    pulses_ms = filter_beat_artifacts(pulses_ms, ARTIFACT_PCT_MAX)
    if len(pulses_ms) < 3:
        return None
    diffs = [(pulses_ms[i + 1] - pulses_ms[i]) ** 2 for i in range(len(pulses_ms) - 1)]
    return (sum(diffs) / len(diffs)) ** 0.5


def _detect_day(beats: list, steps_intervals: "list | None",
                 source: str = "ppi_raw") -> "dict | None":
    """beats: sortierte Liste (datetime, pulse_ms). Gibt den staerksten Kandidaten
    des Tages zurueck, oder None. source='hr_fallback' unterdrueckt RMSSD (s.
    Aufrufstelle in run())."""
    if len(beats) < 2 * MIN_BEATS:
        return None

    t0 = beats[0][0]
    t_end = beats[-1][0]
    bins: dict[int, list] = defaultdict(list)
    for dt, pulse in beats:
        idx = int((dt - t0).total_seconds() // BIN_S)
        bins[idx].append((dt, pulse))

    max_idx = int((t_end - t0).total_seconds() // BIN_S)
    ref_bins = REF_WINDOW_S // BIN_S
    onset_bins = max(1, ONSET_WINDOW_S // BIN_S)
    sustain_bins = SUSTAIN_MIN_S // BIN_S

    def _mean_hr(idx_range) -> "float | None":
        pulses = [p for i in idx_range for _, p in bins.get(i, [])]
        if len(pulses) < MIN_BEATS // 3:
            return None
        return statistics.mean(60000.0 / p for p in pulses)

    best = None
    idx = ref_bins
    while idx < max_idx - onset_bins - sustain_bins:
        ref_hr = _mean_hr(range(idx - ref_bins, idx))
        if ref_hr is None:
            idx += 1
            continue
        # Scharfer Anstieg: KEINE Uebergangsluecke — der volle Sprung muss schon
        # im ONSET_WINDOW_S direkt nach dem Referenzfenster da sein. Ein
        # langsamer Stress-/MCAS-Anstieg ueber mehrere Minuten faellt damit
        # durch, ein echter Lagewechsel (Sekunden bis wenige zehn Sekunden) nicht.
        onset_hr = _mean_hr(range(idx, idx + onset_bins))
        if onset_hr is None or onset_hr - ref_hr < HR_JUMP_MIN:
            idx += 1
            continue

        sustain_hr = _mean_hr(range(idx, idx + sustain_bins))
        if sustain_hr is None or sustain_hr - ref_hr < HR_JUMP_MIN * 0.7:
            idx += 1
            continue

        # Kandidat gefunden — Kennwerte berechnen
        ref_pulses  = [p for i in range(idx - ref_bins, idx) for _, p in bins.get(i, [])]
        peak_pulses = [p for i in range(idx, idx + onset_bins + 4) for _, p in bins.get(i, [])]
        stand_pulses = [p for i in range(idx, idx + sustain_bins) for _, p in bins.get(i, [])]
        if len(ref_pulses) < MIN_BEATS or len(stand_pulses) < MIN_BEATS:
            idx += 1 + sustain_bins
            continue

        jump_dt = t0 + timedelta(seconds=idx * BIN_S)
        hr_supine = 60000.0 / statistics.mean(ref_pulses)
        # Gleicher Artefaktfilter wie bei RMSSD: ein einzelner falsch kurzer
        # Puls-Abstand wuerde sonst als physiologisch unplausibler "Peak"
        # durchschlagen — hier besonders wichtig, da max() auf EINZELNE Beats
        # geht, nicht auf einen Mittelwert.
        peak_pulses_f = filter_beat_artifacts(peak_pulses, ARTIFACT_PCT_MAX)
        hr_peak   = max(60000.0 / p for p in peak_pulses_f) if peak_pulses_f else None
        hr_stand  = 60000.0 / statistics.mean(stand_pulses)
        # WICHTIG: chronologische Reihenfolge, NICHT nach Wert sortieren — RMSSD
        # braucht echte Schlag-zu-Schlag-Differenzen. ref_pulses/stand_pulses sind
        # bereits chronologisch (aus den nach Zeit-Index sortierten Bins gebaut).
        # Bei source='hr_fallback' sind es aber keine echten aufeinanderfolgenden
        # Schlaege, sondern unregelmaessig beabstandete Einzel-BPM-Werte in
        # synthetische pulse_ms umgerechnet -- RMSSD daraus waere Zahlensalat,
        # deshalb hier explizit unterdrueckt statt berechnet.
        if source == "ppi_raw":
            rmssd_supine = _rmssd(ref_pulses)
            rmssd_stand  = _rmssd(stand_pulses)
        else:
            rmssd_supine = None
            rmssd_stand  = None

        steps_note = "keine intraday-Schrittdaten — nicht gegengeprueft"
        steps_ok = True
        if steps_intervals is not None:
            window_start = jump_dt
            window_end = window_start + timedelta(seconds=SUSTAIN_MIN_S)
            steps_in_window = sum(v for ts, v in steps_intervals if window_start <= ts <= window_end)
            steps_ok = steps_in_window <= STEPS_MAX
            steps_note = f"Schritte im Fenster: {steps_in_window:.0f}"

        cand = {
            "datetime": jump_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "hr_supine": round(hr_supine, 1),
            "hr_stand_peak": round(hr_peak, 1) if hr_peak else None,
            "hr_stand": round(hr_stand, 1),
            "hr_delta": round(hr_stand - hr_supine, 1),
            "rmssd_supine": round(rmssd_supine, 2) if rmssd_supine else None,
            "rmssd_stand": round(rmssd_stand, 2) if rmssd_stand else None,
            "rmssd_delta": round(rmssd_stand - rmssd_supine, 2) if (rmssd_supine and rmssd_stand) else None,
            "n_supine": len(ref_pulses),
            "n_standing": len(stand_pulses),
            "steps_ok": steps_ok,
            "notes": steps_note,
            "beat_source": source,
        }
        if steps_ok and (best is None or cand["hr_delta"] > best["hr_delta"]):
            best = cand
        idx += 1 + sustain_bins

    return best


BP_WINDOW_MIN   = int(_PEM_CFG.get("ortho_bp_window_min", 45))
BP_SYS_DROP_MIN = float(_PEM_CFG.get("ortho_bp_sys_drop_min", 20))  # Sheldon 2015 OH-Kriterium
BP_DIA_DROP_MIN = float(_PEM_CFG.get("ortho_bp_dia_drop_min", 10))  # Sheldon 2015 OH-Kriterium


def _bp_check(conn, person: str, jump_dt: datetime) -> dict:
    """Sucht Blutdruckmessungen in einem Fenster um jump_dt und prueft auf
    orthostatische Hypotonie (Sheldon 2015: SBP-Abfall >=20mmHg ODER
    DBP-Abfall >=10mmHg). Rein informativ/bestaetigend — kein Ausschlusskriterium,
    da nur ein Bruchteil der Kandidaten ueberhaupt eine zufaellig nahe BP-Messung
    hat (best-effort, s. Docstring @limits von compute_pem.py fuer denselben
    Blutdruck-Datenlagen-Vorbehalt)."""
    win_start = (jump_dt - timedelta(minutes=BP_WINDOW_MIN)).isoformat()
    win_end   = (jump_dt + timedelta(minutes=BP_WINDOW_MIN)).isoformat()
    jump_iso  = jump_dt.isoformat()
    rows = conn.execute("""
        SELECT ts, systolic, diastolic FROM blood_pressure
        WHERE person=? AND ts BETWEEN ? AND ? AND systolic > 0
        ORDER BY ts
    """, (person, win_start, win_end)).fetchall()
    if not rows:
        return {"bp_sys_before": None, "bp_sys_after": None,
                "bp_dia_before": None, "bp_dia_after": None,
                "bp_confirmed": None, "bp_note": "keine BP-Messung in der Naehe"}

    before = [(s, d) for ts, s, d in rows if ts < jump_iso]
    after  = [(s, d) for ts, s, d in rows if ts >= jump_iso]
    if not before or not after:
        return {"bp_sys_before": None, "bp_sys_after": None,
                "bp_dia_before": None, "bp_dia_after": None,
                "bp_confirmed": None,
                "bp_note": f"BP-Messung(en) nur auf einer Seite des Sprungs ({len(rows)})"}

    sys_before = statistics.mean(s for s, _ in before)
    dia_before = statistics.mean(d for _, d in before)
    sys_after  = statistics.mean(s for s, _ in after)
    dia_after  = statistics.mean(d for _, d in after)
    sys_drop = sys_before - sys_after
    dia_drop = dia_before - dia_after
    confirmed = sys_drop >= BP_SYS_DROP_MIN or dia_drop >= BP_DIA_DROP_MIN
    return {
        "bp_sys_before": round(sys_before, 1), "bp_sys_after": round(sys_after, 1),
        "bp_dia_before": round(dia_before, 1), "bp_dia_after": round(dia_after, 1),
        "bp_confirmed": confirmed,
        "bp_note": (f"BP-bestaetigt: {sys_before:.0f}/{dia_before:.0f} -> "
                    f"{sys_after:.0f}/{dia_after:.0f} mmHg" if confirmed
                    else f"BP vorhanden, kein Abfall: {sys_before:.0f}/{dia_before:.0f} -> "
                         f"{sys_after:.0f}/{dia_after:.0f} mmHg"),
    }


def run(conn, date_from: "str | None", date_to: "str | None") -> int:
    person = OWN_PERSON_ID
    where_date = ""
    params: list = [person]
    if date_from:
        where_date += " AND date(datetime) >= ?"
        params.append(date_from)
    if date_to:
        where_date += " AND date(datetime) <= ?"
        params.append(date_to)

    rows = conn.execute(f"""
        SELECT datetime, pulse_ms, device, source FROM ppi_raw
        WHERE person=? AND pulse_ms BETWEEN {PULSE_MS_FLOOR} AND 1500 {where_date}
        ORDER BY datetime
    """, params).fetchall()

    by_day: dict[str, list] = defaultdict(list)
    device_by_day: dict[str, tuple] = {}
    for dt_str, pulse, device, source in rows:
        dt = datetime.fromisoformat(dt_str)
        d = dt.strftime("%Y-%m-%d")
        by_day[d].append((dt, pulse))
        device_by_day.setdefault(d, (device, source))

    # Fallback-Quelle fuer Tage ohne (ausreichend) ppi_raw: einzelne BPM-Werte
    # aus measurements (metric='heart_rate', alle source_apps -- Oura, Garmin,
    # Apple Watch usw. liefern hierueber durchaus haeufige Einzelwerte per API,
    # nur eben keine echten Schlag-zu-Schlag-Intervalle wie ppi_raw). In
    # synthetische pulse_ms umgerechnet (60000/bpm), damit dieselbe Bin-/
    # Sprung-Erkennung wie bei ppi_raw laeuft. RMSSD daraus waere aber Unsinn
    # (die Werte sind nicht wirklich aufeinanderfolgende Schlaege, sondern
    # unregelmaessig beabstandete Einzelmessungen) -- deshalb wird RMSSD fuer
    # aus dieser Quelle stammende Kandidaten unten explizit unterdrueckt statt
    # berechnet, s. _detect_day(source=...).
    hr_rows = conn.execute(f"""
        SELECT ts, value, device_id, source_app FROM measurements
        WHERE person=? AND metric='heart_rate' AND value > 0 {where_date.replace('datetime', 'ts')}
        ORDER BY ts
    """, params).fetchall()
    hr_fallback_by_day: dict[str, list] = defaultdict(list)
    hr_device_by_day: dict[str, tuple] = {}
    for ts_str, bpm, device, source_app in hr_rows:
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
        d = dt.strftime("%Y-%m-%d")
        hr_fallback_by_day[d].append((dt, 60000.0 / bpm))
        hr_device_by_day.setdefault(d, (device, source_app))

    step_rows = conn.execute("""
        SELECT ts, date, value FROM measurements
        WHERE person=? AND (
            (metric='steps' AND source_app='apple_health')
            OR (metric='steps_1min' AND source_app='polar_connect')
        )
    """, (person,)).fetchall()
    steps_by_day: dict[str, list] = defaultdict(list)
    for ts, d, value in step_rows:
        try:
            steps_by_day[d].append((datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None), value))
        except ValueError:
            continue

    # analyse_orthostatic.py liest tatsaechlich aus sessions/session_metrics
    # (type='orthostatic'), NICHT aus der eigenstaendigen orthostatic_tests-
    # Tabelle, die dessen eigener (veralteter) Docstring behauptet — per
    # Testlauf verifiziert. Dieselbe Zielstruktur wird hier verwendet, damit
    # die Kandidaten in der bereits funktionierenden Auswertung ankommen
    # statt in einer toten Tabelle.
    existing_dates = {r[0] for r in conn.execute("""
        SELECT s.date FROM sessions s
        WHERE s.type='orthostatic' AND s.person=? AND s.source_app='ppi_detected'
    """, (person,))}

    inserted = 0
    all_dates = set(by_day) | set(hr_fallback_by_day)
    for date in all_dates:
        if date in existing_dates:
            continue
        beats = by_day.get(date, [])
        beats.sort(key=lambda b: b[0])
        if len(beats) >= 2 * MIN_BEATS:
            source = "ppi_raw"
            device, _source = device_by_day.get(date, (None, None))
        else:
            beats = sorted(hr_fallback_by_day.get(date, []), key=lambda b: b[0])
            source = "hr_fallback"
            device, _source = hr_device_by_day.get(date, (None, None))
        cand = _detect_day(beats, steps_by_day.get(date), source=source)
        if not cand:
            continue
        sid = f"ppi_detected_ortho_{date}_{person}"
        bp = _bp_check(conn, person, datetime.fromisoformat(cand["datetime"]))
        conn.execute("""
            INSERT OR IGNORE INTO sessions
            (id, type, ts_start, ts_end, date, device_id, person, source_app)
            VALUES (?, 'orthostatic', ?, NULL, ?, ?, ?, 'ppi_detected')
        """, (sid, cand["datetime"], date, device, person))
        metric_pairs = [
            ("hr_supine",      cand["hr_supine"],     "bpm"),
            ("hr_standup_min", cand["hr_stand_peak"], "bpm"),
            ("hr_stand",       cand["hr_stand"],       "bpm"),
            ("hr_delta",       cand["hr_delta"],       "bpm"),
            ("rmssd_supine",   cand["rmssd_supine"],   "ms"),
            ("rmssd_stand",    cand["rmssd_stand"],    "ms"),
            ("rmssd_delta",    cand["rmssd_delta"],    "ms"),
            ("n_supine",       cand["n_supine"],       None),
            ("n_standing",     cand["n_standing"],     None),
            ("bp_sys_before",  bp["bp_sys_before"],    "mmHg"),
            ("bp_sys_after",   bp["bp_sys_after"],     "mmHg"),
            ("bp_dia_before",  bp["bp_dia_before"],    "mmHg"),
            ("bp_dia_after",   bp["bp_dia_after"],     "mmHg"),
            ("bp_confirmed",   1.0 if bp["bp_confirmed"] else (0.0 if bp["bp_confirmed"] is False else None), None),
        ]
        for metric, value, unit in metric_pairs:
            if value is None:
                continue
            conn.execute("""
                INSERT OR IGNORE INTO session_metrics (session_id, metric, value, value_text, unit)
                VALUES (?,?,?,?,?)
            """, (sid, metric, value, cand["notes"] if metric == "hr_delta" else None, unit))
        conn.execute("""
            INSERT OR IGNORE INTO session_metrics (session_id, metric, value, value_text, unit)
            VALUES (?, 'bp_note', NULL, ?, NULL)
        """, (sid, bp["bp_note"]))
        # beat_source: 'ppi_raw' (echte Schlag-zu-Schlag-Daten, RMSSD verlaesslich)
        # oder 'hr_fallback' (Einzel-BPM-Werte z.B. Oura/Garmin/Apple Watch,
        # RMSSD oben bewusst unterdrueckt) -- fuer die Auswertung wichtig, um
        # HF-Sprung-Kandidaten ohne HRV-Bestaetigung nicht mit echten RMSSD-
        # bestaetigten Kandidaten zu verwechseln.
        conn.execute("""
            INSERT OR IGNORE INTO session_metrics (session_id, metric, value, value_text, unit)
            VALUES (?, 'beat_source', NULL, ?, NULL)
        """, (sid, cand["beat_source"]))
        inserted += 1
    conn.commit()
    return inserted


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description=t("Orthostase-Kandidaten aus Alltags-PPI-Daten erkennen",
                       "Detect orthostatic candidates from everyday PPI data"))
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    n = run(conn, args.date_from, args.date_to)
    print(t(f"{n} Kandidaten-Tag(e) gefunden und gespeichert.",
            f"{n} candidate day(s) found and saved."))

    # Haeufigkeits-Trend: einzelne Kandidaten sind nur Alltagsdaten-Hinweise
    # (s. @limits), aber die RATE ueber die Zeit ist ein eigenstaendiges Signal,
    # unabhaengig davon ob jeder Einzelfall wirklich orthostatisch war.
    person = OWN_PERSON_ID
    rows = conn.execute("""
        SELECT strftime('%Y', date), COUNT(*) FROM sessions
        WHERE type='orthostatic' AND source_app='ppi_detected' AND person=?
        GROUP BY strftime('%Y', date) ORDER BY 1
    """, (person,)).fetchall()
    if rows:
        print(t("\n── Häufigkeit pro Jahr (alle Kandidaten, unabhängig von BP-Bestätigung) ──",
                "\n── Frequency per year (all candidates, regardless of BP confirmation) ──"))
        for yr, cnt in rows:
            print(f"  {yr}: {cnt}")

    bp_rows = conn.execute("""
        SELECT sm.value FROM sessions s JOIN session_metrics sm ON sm.session_id=s.id
        WHERE s.type='orthostatic' AND s.source_app='ppi_detected' AND s.person=?
          AND sm.metric='bp_confirmed'
    """, (person,)).fetchall()
    if bp_rows:
        confirmed = sum(1 for r in bp_rows if r[0] == 1.0)
        print(t(f"\n  Kandidaten mit nahegelegener Blutdruckmessung: {len(bp_rows)}, davon "
                f"BP-bestätigt (SBP≥{BP_SYS_DROP_MIN:.0f}/DBP≥{BP_DIA_DROP_MIN:.0f}mmHg-Abfall): {confirmed}",
                f"\n  Candidates with a nearby blood pressure reading: {len(bp_rows)}, of which "
                f"BP-confirmed (SBP≥{BP_SYS_DROP_MIN:.0f}/DBP≥{BP_DIA_DROP_MIN:.0f}mmHg drop): {confirmed}"))


if __name__ == "__main__":
    main()
