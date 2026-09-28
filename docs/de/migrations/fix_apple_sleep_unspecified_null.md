# fix_apple_sleep_unspecified_null.py — Backfills the numeric code for

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/fix_apple_sleep_unspecified_null.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

import_apple.py's CATEGORY_MAP kannte den String 'HKCategoryValueSleepAnalysisAsleepUnspecified' bisher nicht (nur 'HKCategoryValueSleepAnalysisAsleep', die semantisch identische, aeltere Bezeichnung desselben Rohwerts). float() auf den unbekannten String scheiterte, also wurde jede betroffene Zeile mit value=NULL importiert. Diese Migration traegt fuer bereits importierte Zeilen den Code nach, den import_apple.py (inzwischen korrigiert) fuer neue Importe verwendet.

## Relevanz

Behebt Datenverlust bei 2.561 Schlaf-Segmenten (2018–2023), deren Rohwert bisher stillschweigend als NULL importiert wurde -- Datenqualitaet, nicht Funktion.

## Methode

Ein gezieltes UPDATE auf measurements: metric='sleep_analysis' AND value IS NULL AND value_text='HKCategoryValueSleepAnalysisAsleepUnspecified' -> value=1.0. Der value_text-Filter ist die einzige verlaessliche Identifikation: eine Zeile mit value IS NULL koennte im Prinzip auch aus einem anderen Grund NULL sein (unbekannter zukuenftiger Kategoriewert); ohne exakten value_text-Treffer bleibt die Zeile unangetastet, statt geraten umgeschrieben zu werden. Code 1.0 ist bewusst identisch zum bestehenden Code fuer 'HKCategoryValueSleepAnalysisAsleep' (siehe CATEGORY_MAP in import_apple.py) -- beide bedeuten "hat geschlafen, keine Stadien-Information", keine Schlafphase. Code 1.0 ist in compute_sleep_hypnogram.APPLE_STAGE_MAP (kennt nur 2/3/4/5) und in dessen build_apple()-Query (WHERE value IN (2.0,3.0,4.0,5.0)) nicht enthalten, faellt also nicht faelschlich in eine WAKE/LIGHT/DEEP/REM-Klassifikation. Idempotent: der WHERE-Filter (value IS NULL) trifft nach dem ersten Lauf auf keine Zeile mehr.

## Datenfluss

- **Liest:** `health.db`, `(measurements:`, `metric`, `value`, `value_text)`
- **Schreibt:**

  ```
  health.db (measurements.value only for the matched rows --
  metric, value_text, ts, date, device_id, person, source_app
  untouched)
  ```

## Grenzen

Betrifft ausschliesslich bereits importierte Zeilen. Ein erneuter Lauf von import_apple.py (nach dem CATEGORY_MAP-Fix) haette denselben Effekt fuer diese Zeilen und macht diese Migration danach ueberfluessig -- sie existiert, damit die Korrektur nicht von einem vollstaendigen Re-Import des (grossen) Apple-Health-XML-Exports abhaengt.

## Aufruf

```bash
python3 scripts/migrations/fix_apple_sleep_unspecified_null.py --dry-run
python3 scripts/migrations/fix_apple_sleep_unspecified_null.py
```
