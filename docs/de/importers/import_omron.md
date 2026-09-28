# Omron Connect → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_omron.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Blutdruckmessungen aus Omron Connect CSV-Exporten in die health.db. Ergänzt Apple Health um spezifische Omron-Daten wie IHB-Flag, mögliches Vorhofflimmern (AFib), TruRead und vollständige Messreihen.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest CSV-Dateien aus dem Omron-Verzeichnis und parst die Blutdruckmessungen. Unterstützt Omron AFib-fähige Blutdruckmessgeräte. Ergänzende Daten: IHB (Irregulärer Herzschlag), AFib-Erkennung, TruRead (mehrfache Messungen), vollständige Messreihe.

## Datenfluss

- **Liest:** `{imports/omron/}*.csv`, `(Omron`, `Connect`, `Export)`
- **Schreibt:** `health.db (blood_pressure)`

## Grenzen

Keine Validierung der Omron-Datenqualität. Abhängig von der Korrektheit des CSV-Exports. Keine medizinische Bewertung aus IHB/AFib.

## Aufruf

```bash
python3 import_omron.py                   # all CSVs in Omron/
python3 import_omron.py --update          # only neue Daten
python3 import_omron.py --file export.csv
```
