# Yearly Fetch — lädt Referenzdaten von externen Quellen und speichert sie lokal.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/fetch_yearly.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt ECHA-SVHC-Kandidatenliste (chronische Risikostoffe: Karzinogene, Mutagene, Reproduktionstoxizität, endokrine Disruptoren) und CosIng-Annex-Daten (in der EU verbotene/beschränkte Kosmetik-Inhaltsstoffe) als lokale CSV-Dateien. Ermöglicht Allergen-Matching ohne wiederholte Netzwerkabfragen und hält die Referenzdaten aktuell durch jährlichen Refresh.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

1. Lädt ECHA-SVHC-Kandidatenliste von ECHA-Website (CSV/Excel → CSV) 2. Lädt CosIng Annex II (verbotene Substanzen) und Annex III (beschränkte Substanzen) von EU-Kommissions-Website 3. Speichert alle Daten in data/reference/ (echa_svhc.csv, cosing_annex_ii.csv, cosing_annex_iii.csv) 4. Aktualisiert manifest.json mit Datum des letzten Abrufs pro Quelle 5. Jede Quelle wird unabhängig versucht; Fehler in einer Quelle brechen nicht den gesamten Prozess ab

## Datenfluss

- **Liest:** `ECHA-Website`, `(https://echa.europa.eu)`, `EU-Kommission`, `CosIng-Daten`
- **Schreibt:**

  ```
  data/reference/echa_svhc.csv, data/reference/cosing_annex_ii.csv,
  data/reference/cosing_annex_iii.csv, data/reference/manifest.json
  ```

## Grenzen

Abhängig von der Verfügbarkeit und dem Format der Downloadquellen. Quellen können ihr Format ändern; manuelle Anpassung der Parser nötig. Kein Live-Update — Referenzdaten werden nur durch erneuten Aufruf aktualisiert.

## Aufruf

```bash
python scripts/fetch_yearly.py
python scripts/fetch_yearly.py --force
python scripts/fetch_yearly.py --check
```
