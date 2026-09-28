# 6-Minuten-Gehtest (6MWT) → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_6mwt.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Ergebnisse des 6-Minuten-Gehtests (6MWT) als standardisiertes Outcome-Maß für ME/CFS, Long COVID und Herzinsuffizienz. Monatliche Durchführung zeigt funktionale Kapazität im Verlauf.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Protokoll nach ATS 2002 Standard (modifiziert für Heimgebrauch): 1) 10 min Sitzen → Ruhe-HR, SpO2, Borg messen 2) 6 Minuten gehen (flacher Untergrund) 3) Pausen erlaubt (Zeit läuft weiter, Stopps dokumentieren) 4) Nach 6 min: Distanz, HR, SpO2, Borg erfassen 5) 1 min Sitzen: Erholungs-HR messen CSV-Format: ts,distance_m,hr_rest,hr_peak,hr_recovery,spo2_pre, spo2_post,borg_pre,borg_post,stops,notes

## Datenfluss

- **Liest:** `{imports/6mwt/}*.csv`, `(6MWT`, `Ergebnisse)`
- **Schreibt:** `health.db (functional_tests)`

## Grenzen

Keine automatische Bewertung der 6MWT-Ergebnisse. Referenzwerte dienen nur zur Orientierung. Keine medizinische Diagnose.

## Referenzen

- American Thoracic Society (2002). ATS Statement: Guidelines for the Six-Minute Walk Test. American Journal of Respiratory and Critical Care Medicine, 166(1):111-117. doi:10.1164/ajrccm.166.1.at1102

## Aufruf

```bash
python3 import_6mwt.py                    # alle CSVs
python3 import_6mwt.py --manual           # interaktive Eingabe
python3 import_6mwt.py --template         # CSV-Vorlage ausgeben
python3 import_6mwt.py --file test.csv    # einzelne Datei
```
