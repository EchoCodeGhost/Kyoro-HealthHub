# Orthostase-Kandidaten-Erkennung aus Alltags-PPI-Daten.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_orthostatic_detection.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Sucht in durchgehenden Alltags-Herzfrequenzaufzeichnungen (nicht nur bewussten Steh-Tests) nach Mustern, die zu einem Lage-/Haltungswechsel passen könnten (z. B. Liegen → Stehen), und speichert Kandidaten in sessions/session_metrics (type='orthostatic', source_app='ppi_detected') zur Auswertung durch analyse_orthostatic.py.

## Relevanz

Erschließt Orthostase-Verdachtsfälle aus vorhandenen Alltagsdaten statt nur aus den seltenen bewussten Tests

## Methode

Kein Gerät in diesem Projekt exportiert rohe Lage-/Beschleunigungs- sensordaten (geprüft: alle imports/-Verzeichnisse + Apple-Health- Export.xml-Record-Typen — nichts gefunden, nur der unabhängige AppleWalkingSteadiness-Gang-Score, kein Lage-/Orientierungssignal). Ersatzweise: gleitendes HF-Fenster aus ppi_raw (device-/quellen- unabhängig — jedes Gerät, das Beat-zu-Beat-Daten liefert, auch PPG- Wearables wie der Polar Loop, fließt automatisch mit ein, s. @limits zur Genauigkeitseinschränkung bei PPG). HARTE EINSCHRÄNKUNG für die KONTINUIERLICHE Alltagsüberwachung: Garmin, Oura und die kontinuierliche Apple-Watch-HF liefern PER API gar keine Beat-zu- Beat-Rohdaten — nur bereits fertig berechnete RMSSD-Fensterwerte (Garmin: get_hrv_data(); Oura: hrv.items(), je 5-Minuten-Aggregat). Diese landen deshalb nie in ppi_raw und werden von diesem Skript unabhängig von device_registry-Einträgen NIE verarbeitet — eine Herstellerschnittstellen-Grenze, keine Design-Entscheidung. KEINE harte Grenze dagegen für EKG-Einzelaufnahmen (30-Sek.-Snapshots): die landen device-agnostisch in ecg_sessions/ecg_samples und werden von compute_ecg_rpeaks.py per R-Zacken-Erkennung automatisch in echte RR-Intervalle umgewandelt (source dynamisch aus ecg_sessions.source, z.B. 'ecg_apple', 'ecg_garmin' — nicht mehr Apple-exklusiv seit dem Fix des früheren Mislabeling-Bugs). Praktisch aber von der jeweiligen Gerätefähigkeit abhängig: nicht jedes Garmin-Modell hat EKG-Hardware (geprüft gegen device_registry und GDPR-Exportinhalt: bei reinen Fitness-/Outdoor-Modellen ohne EKG-App gibt es schlicht keine *ECG_Details*.json-Dateien) — der Weg im Skript existiert, liefert aber nur, wenn das Quellgerät auch tatsächlich EKG-Snapshots aufzeichnet. Ein Sprung ≥HR_JUMP_MIN bpm (15 bpm — Untergrenze von "grenzwertig" nach der Klassifikation in analyse_orthostatic.py, NICHT das Sheldon-2015-POTS-Kriterium von 30 bpm: eine eigene Kalibrierung gegen echte Steh-Tests zeigte, dass reale HF-Sprünge meist unter dieser Schwelle liegen — 30bpm direkt zu verlangen würde echte Episoden verpassen), der bereits innerhalb von ONSET_WINDOW_S nach dem REF_WINDOW_S-Referenzfenster erreicht wird UND mindestens SUSTAIN_MIN_S anhält, gilt als Kandidat — die fehlende Übergangslücke erzwingt einen SCHARFEN Anstieg (charakteristisch für einen echten Lagewechsel), ein langsamer Stress-/MCAS-Anstieg über mehrere Minuten fällt durch. RMSSD analog aus denselben Fenstern (chronologische Beat-Reihenfolge, nicht wertsortiert). Um Sport-Fehlalarme auszuschließen: wo intraday- aufgelöste Schrittdaten existieren (Apple minutengenau als 'steps'; Polar ebenso minutengenau über die eigene Metrik 'steps_1min', aus den samples.steps-Feldern der activity-*.json-Exporte -- die separat importierte Tagessumme 'steps' von Polar erlaubt keine Fensterprüfung und wird hier bewusst nicht verwendet), muss die Schrittzahl im Bestätigungsfenster unter STEPS_MAX bleiben — ohne solche Daten wird der Kandidat mit einer entsprechenden Notiz statt Ablehnung markiert (fehlende Bestätigung ≠ Widerlegung). Zusätzlich: Blutdruckmessungen in einem ±BP_WINDOW_MIN-Fenster um den Sprung werden auf orthostatische Hypotonie geprüft (Sheldon 2015: SBP-Abfall ≥BP_SYS_DROP_MIN ODER DBP-Abfall ≥BP_DIA_DROP_MIN) — rein bestätigend, kein Filter, da nur ein Bruchteil der Kandidaten überhaupt eine zufällig nahe BP-Messung hat. Erkennt nur EINEN Kandidaten pro Tag (den mit dem größten ΔHR), um Überschwemmung durch benachbarte Teil-Treffer derselben echten Episode zu vermeiden.

## Berechnung

```
detection (all must hold for a candidate):
  HR jump    >= HR_JUMP_MIN (15 bpm)   within ONSET_WINDOW_S of the reference window
  sustained  >= HR_JUMP_MIN * 0.7      for at least SUSTAIN_MIN_S afterwards
  steps      <= STEPS_MAX              in the confirmation window (if intraday step data exists)
bp_confirmed (informational, not a filter):
  SBP drop >= BP_SYS_DROP_MIN (20 mmHg) OR DBP drop >= BP_DIA_DROP_MIN (10 mmHg)
  within ±BP_WINDOW_MIN of the candidate, per Sheldon 2015 orthostatic-hypotension criterion
```

## Datenfluss

- **Liest:** `ppi_raw`, `measurements`, `(steps`, `steps_1min)`, `blood_pressure`
- **Schreibt:** `sessions, session_metrics (type='orthostatic', source_app='ppi_detected')`

## Grenzen

Heuristische Methode: eigener Erkennungsalgorithmus, keine publizierte Change-Point-Detection-Bibliothek verwendet (einfache gleitende Fenstervergleiche). Alltagsdaten sind unkontrollierter als ein echter Steh-Test (kein standardisiertes Vor-Verhalten, keine garantierte Ruhephase vor dem Sprung) — daher grundsätzlich niedrigere Beweiskraft als echte Polar-Steh-Tests (source_app='polar_connect' in derselben sessions-Tabelle), selbst bei gleichem ΔHR. Kann NICHT zwischen einem echten Lagewechsel und jeder anderen Ursache eines nicht- belastungsbedingten HF-Anstiegs unterscheiden (Angst, MCAS-Reaktion, Medikamentenwirkung sind ebenfalls plausible Ursachen); ein gefundener Kandidat ist "unerklärter scharfer HF-Anstieg ohne Bewegung", Orthostase ist eine plausible, aber nicht bewiesene Erklärung dafür. PPG-Quellen (Polar Loop, sensor_type optical_wrist_gps) sind bewegungsartefaktanfälliger und weniger präzise als Brustgurt-EKG (H7/H10) — Kandidaten von PPG-Geräten verdienen weniger Vertrauen als Brustgurt-Kandidaten, auch wenn beide gleich behandelt werden (Geräte-ID steht im device_id-Feld der Session, kann nachträglich gefiltert werden). HR_JUMP_MIN (15 bpm, s. @method), ONSET_WINDOW_S, SUSTAIN_MIN_S, STEPS_MAX, BP_SYS_DROP_MIN/BP_DIA_DROP_MIN sind eigene Schwellenwerte für die ERKENNUNG (BP-Schwellen selbst sind Sheldon 2015, aber ihre Anwendung auf unkontrollierte Alltagsdaten mit ±BP_WINDOW_MIN-Fenster statt eines exakten Test-Zeitpunkts ist eigene Naeherung). RMSSD-Werte nutzen eine einfache lokale Median-Ausreisser-Filterung (s. modules/rr_interval_algorithms.filter_beat_artifacts), NICHT die vollstaendige Kubios-Artefaktkorrektur aus compute_hrv_advanced.py — die RMSSD-Spalte ist informativ, die HF-basierte Erkennung selbst haengt nicht davon ab. hr_stand_peak (Aufsteh-Peak) ist die unzuverlaessigste Spalte: empirisch gefunden, dass sehr kurze pulse_ms-Werte (≙195-201 bpm) wiederholt, isoliert und ueber Jahre exakt-identisch verteilt in ppi_raw auftauchen — passt zu einem systematischen Geraete-/Import- Bodenwert, nicht zu echter Physiologie. Eine Anhebung des PULSE_MS_FLOOR verschiebt das Problem nur auf den neuen Grenzwert (die Verteilung reicht offenbar weiter als jeder gesetzte Boden), loest es aber nicht — ein einzelner Beat-Maximalwert ist inhaerent anfaelliger dafuer als ein Fensterschnitt. hr_stand (der Mittelwert im Sustain-Fenster, auf dem die Erkennung selbst beruht) hat dieses Problem nicht und ist der vertrauenswuerdigere Wert; hr_stand_peak nur als grobe, nicht belastbare Zusatzinformation lesen.

## Referenzen

- Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029 (orthostatische Hypotonie SBP-Abfall ≥20mmHg / DBP-Abfall ≥10mmHg — hier als BP-Bestätigungsschwelle verwendet, s. _bp_check. Das POTS-Kriterium ΔHR ≥30 bpm aus derselben Quelle wird NICHT als Erkennungsschwelle verwendet, s. HR_JUMP_MIN-Begründung in @method)

## Aufruf

```bash
python3 scripts/compute/compute_orthostatic_detection.py
python3 scripts/compute/compute_orthostatic_detection.py --date-from 2026-01-01
python3 scripts/compute/compute_orthostatic_detection.py --lang en
```
