# Gewicht aus measurements → body_composition — Brücke für Profil-Gewichtswerte.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_body_composition_from_measurements.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Überträgt weight_kg-Werte aus der measurements-Tabelle (aktuell: Polars physicalInformation-Profil-Snapshot, s. import_polar.py ::import_polar_activity) nach body_composition, damit Gewichtsverläufe/-analysen, die body_composition lesen, nicht auf die deutlich lückenhaftere Waagen-Historie (FDDB/Beurer/Renpho) beschränkt bleiben.

## Relevanz

Schließt Lücken in der Gewichts-Historie außerhalb der Waagen-Importe, relevant für Trend-Analysen und die Belastungs-/Kapazitäts-Einordnung

## Methode

Liest measurements WHERE metric='weight_kg', gruppiert nach source_app (nicht auf Polar hartkodiert — jede Quelle, die künftig weight_kg nach measurements schreibt, wird automatisch mitgenommen). Nutzt ts/date direkt aus measurements (Polar: {date}T00:00:00+00:00) statt eines eigenen Zeitstempels — bei Überschneidung mit einer bestehenden body_composition-Zeile zum exakt gleichen (ts, person) gewinnt die zuerst geschriebene (INSERT OR IGNORE), das ist unwahrscheinlich, da FDDB/Beurer/ Renpho bislang T12:00:00 nutzen, keine T00:00:00-Zeitstempel.

## Datenfluss

- **Liest:** `measurements`, `(metric='weight_kg')`
- **Schreibt:** `body_composition (nur weight_kg gesetzt, übrige Spalten NULL)`

## Grenzen

Nur weight_kg — die übrigen physicalInformation-Werte (VO2max, HFmax, Ruhepuls, aerobe/anaerobe Schwelle) bleiben bewusst in measurements, weil body_composition dafür keine Spalten hat und es sich um andere Konzepte handelt (Fitness-/HF-Kennwerte, keine Körperzusammensetzung). Kein Duplikat-Check gegen andere body_composition-Quellen am selben Tag — falls z.B. eine Waagen-Messung und ein Polar-Profil-Wert für denselben Tag abweichen, bleiben beide als separate Zeilen bestehen (andere Ruhr-Uhrzeit), keine Auflösung/Mittelung.

## Aufruf

```bash
python3 scripts/compute/compute_body_composition_from_measurements.py
python3 scripts/compute/compute_body_composition_from_measurements.py --lang en
```
