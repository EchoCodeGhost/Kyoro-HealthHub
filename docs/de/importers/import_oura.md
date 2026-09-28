# Oura Ring API → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_oura.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Daten vom Oura Ring 4 über die offizielle API in die health.db. Unterstützt Schlaf, Schlafbereitschaft, Aktivität, SpO2, HRV, Stress, kardiovaskuläre Metriken, kontinuierliche Herzfrequenz, Workouts (inkl. automatisch erkannter Alltagsaktivität wie 'houseWork') und Nutzer-Tags (Symptome/Kontext).

## Relevanz

Ermöglicht den Import von Schlaf- und Erholungsdaten aus Oura-Ringen, essentiell für die Schlafanalyse

## Methode

Ruft Daten von der Oura Cloud API ab. daily_sleep → sessions + session_metrics, sleep → sessions (korrigierte Zeistempel) + measurements (HRV RMSSD Zeitreihe), andere daily-* Daten → measurements. Workout/ enhanced_tag → oura_workouts/oura_tags/user_context — gleiche Zieltabellen wie import_oura_csv.py (GDPR-Export), INSERT OR IGNORE dedupliziert zwischen beiden Importpfaden. HRV-Zeitreihen werden als metric='hrv_rmssd' gespeichert.

## Datenfluss

- **Liest:** `Oura`, `Cloud`, `API`, `(https://cloud.ouraring.com)`
- **Schreibt:**

  ```
  health.db (sessions, session_metrics, measurements, oura_workouts,
  oura_tags, user_context)
  ```

## Grenzen

Abhängig von der Verfügbarkeit der Oura API und der Qualität der zurückgegebenen Daten. Keine medizinische Interpretation.

## Aufruf

```bash
python import_oura.py --setup
python import_oura.py             # Vollimport (ab 2024-01-01)
python import_oura.py --update    # Nur neue Daten
python import_oura.py --from 2024-06-01 --to 2024-12-31
python import_oura.py --no-hr     # Ohne kontinuierliche HR
```
