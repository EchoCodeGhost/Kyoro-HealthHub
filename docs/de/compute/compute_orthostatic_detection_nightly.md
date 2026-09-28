# Naechtliche Orthostase-Kandidaten aus Oura-Bewegungs-/HF-Daten.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_orthostatic_detection_nightly.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Naechtliches Gegenstueck zu compute_orthostatic_detection.py: sucht in Oura-Schlafdaten (30-Sekunden-Bewegungsklassifikation + 5-Minuten-HF- Mittelwerte) nach Mustern, die zu einem naechtlichen Aufstehen passen koennten (z. B. Toilettengang), und speichert Kandidaten in sessions/session_metrics (type='orthostatic', source_app= 'oura_nightly_detected') zur Auswertung durch analyse_orthostatic.py.

## Relevanz

Erschliesst naechtliche Orthostase-Verdachtsfaelle (z. B. Toilettengaenge) aus Oura-Schlafdaten, die tagsueber gar nicht erfasst werden koennten

## Methode

Kein durchgehendes Beat-zu-Beat-Signal ist waehrend Oura-Schlaf verfuegbar (nur 5-Minuten-HF-/HRV-Mittelwerte, bereits als measurements(metric='oura_sleep_hr'/'hrv_rmssd', source_app= 'oura_app') importiert von import_oura.py — hier wiederverwendet statt erneut aus dem heart_rate_json/hrv_json der oura_sleep_model-Zeile geparst, da bereits verifiziert korrekt in UTC vorliegend). Statt eines HF-Sprungs (zu grob aufgeloest fuer den scharfen Onset-Test aus compute_orthostatic_detection.py) wird movement_30_sec ausgewertet: eine Ziffernfolge (eine Ziffer je 30-Sekunden-Epoche, hoehere Ziffer = mehr Bewegung laut Oura, genaue Bedeutung der einzelnen Ziffernwerte nicht offiziell dokumentiert verfuegbar — hier rein als relative Bewegungsintensitaet behandelt, s. @limits). Ein "Bewegungsschub" liegt vor, wenn nach mindestens MOVEMENT_QUIET_EPOCHS ruhigen Epochen (Ziffer <= MOVEMENT_QUIET_MAX) mindestens MOVEMENT_BURST_EPOCHS Epochen mit Ziffer >= MOVEMENT_BURST_MIN folgen. Fuer den Schub-Beginn wird die mittlere HF im NIGHT_BASELINE_MIN-Fenster davor mit der Spitzen-HF im NIGHT_ONSET_WINDOW_MIN-Fenster danach verglichen; ein Anstieg >= NIGHT_HR_JUMP_MIN gilt als Kandidat. Blutdruck-Gegencheck (_bp_check aus compute_orthostatic_detection, gleiche Sheldon-2015- Kriterien) wird wiederverwendet, findet aber praktisch nie eine Messung (Blutdruck wird nicht nachts im Schlaf gemessen) — rein zur Vollstaendigkeit der Datenstruktur, kein sinnvoller Bestaetigungskanal hier. Nur EIN Kandidat pro Nacht (der mit dem groessten ΔHR).

## Berechnung

```
detection (all must hold for a candidate):
  movement burst: >= MOVEMENT_BURST_EPOCHS epochs >= MOVEMENT_BURST_MIN,
                   preceded by >= MOVEMENT_QUIET_EPOCHS epochs <= MOVEMENT_QUIET_MAX
  hr jump:         peak HR in NIGHT_ONSET_WINDOW_MIN after burst onset
                    minus mean HR in NIGHT_BASELINE_MIN before >= NIGHT_HR_JUMP_MIN (10 bpm)
bp_confirmed (informational, not a filter, almost always None at night):
  see compute_orthostatic_detection._bp_check
```

## Datenfluss

- **Liest:** `oura_sleep_model`, `measurements`, `(oura_sleep_hr`, `hrv_rmssd)`, `sessions`, `(to`, `resolve`, `the`, `Oura`, `device`, `id)`, `blood_pressure`
- **Schreibt:**

  ```
  sessions, session_metrics (type='orthostatic',
  source_app='oura_nightly_detected')
  ```

## Grenzen

Deutlich spekulativer als das Tages-Pendant compute_orthostatic_ detection.py: (1) die 5-Minuten-HF-Mittelwerte verwaschen jeden kurzen Anstieg staerker als beat-zu-beat-Daten — ein echter, kurzer Toilettengang-HF-Anstieg kann durch die Mittelung unterschaetzt oder ganz verpasst werden; NIGHT_HR_JUMP_MIN (10 bpm) ist NICHT wie bei compute_orthostatic_detection.py gegen echte bestaetigte Tests kalibriert (es gibt keine echten naechtlichen Steh-Tests als Referenz) — reine eigene Setzung, deutlich unsicherer. (2) Die Bedeutung der movement_30_sec-Ziffernwerte ist nicht aus offizieller Oura- Dokumentation verifiziert, nur als "hoeher = mehr Bewegung" angenommen — ob ein erkannter Bewegungsschub tatsaechlich einem Aufstehen entspricht (statt z. B. Umdrehen im Bett, Kratzen, Partnerbewegung falls das Geraet am Handgelenk getragen wird) ist nicht verifizierbar. (3) Nur eine kleine Zahl an Naechten mit vollstaendigen Bewegungsdaten verfuegbar (Stand der Implementierung, kurzer Beobachtungszeitraum) — kleine Stichprobe. (4) BP- Gegencheck liefert praktisch nie eine Bestaetigung (kein Blutdruck im Schlaf gemessen) — anders als beim Tages-Skript kein sinnvoller zusaetzlicher Bestaetigungskanal. Ein Kandidat hier ist also deutlich schwaecheres Indiz als ein Tages-Kandidat, erst recht als ein echter Polar-Test.

## Referenzen

- Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029 (nur fuer den wiederverwendeten BP-Gegencheck relevant, s. @method; kein eigenes Referenzkriterium fuer die Bewegungserkennung selbst, da diese nicht auf publizierter Evidenz beruht, s. @limits)

## Aufruf

```bash
python3 scripts/compute/compute_orthostatic_detection_nightly.py
python3 scripts/compute/compute_orthostatic_detection_nightly.py --date-from 2026-01-01
python3 scripts/compute/compute_orthostatic_detection_nightly.py --lang en
```
