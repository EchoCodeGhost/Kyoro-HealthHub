# RENPHO Smart-Maßband → health.db (body_composition)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_renpho_tape.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert CSV-Exporte der RENPHO-App (smartes Maßband) in die health.db. Speichert alle Körperumfänge (Hals, Schulter, Arm, Brust, Taille, Abdomen, Hüfte, Oberschenkel, Wade, Benutzerdefiniert) sowie den Taille-Hüfte-Quotienten in body_composition.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest CSV-Dateien aus imports/_inbox/ (RENPHO*.csv) oder einem expliziten Pfad. Jede Zeile enthält einen Datumsstempel (deutsches Format) und Key(unit):value-Paare. Fehlende Werte ('--') werden als NULL gespeichert. Neue Umfangs-Spalten werden automatisch zu body_composition ergänzt, falls noch nicht vorhanden.

## Datenfluss

- **Liest:** `imports/_inbox/RENPHO*.csv`
- **Schreibt:**

  ```
  health.db: body_composition (neck_cm, shoulder_cm, upper_arm_left_cm,
  upper_arm_right_cm, chest_cm, abdomen_cm, thigh_left_cm,
  thigh_right_cm, calf_left_cm, calf_right_cm, custom_1..6,
  waist_to_hip_ratio, waist_cm, hip_cm)
  ```

## Grenzen

RENPHO-App gibt "Benutzerdefinierter Teil 1" mit Einheit "inch" aus (App-Bug); der Wert wird unverändert gespeichert. Keine Validierung der Plausibilität einzelner Messwerte.

## Aufruf

```bash
python3 import_renpho_tape.py
python3 import_renpho_tape.py --inbox
python3 import_renpho_tape.py --file "RENPHO Health-Max.csv"
python3 import_renpho_tape.py --update
```
