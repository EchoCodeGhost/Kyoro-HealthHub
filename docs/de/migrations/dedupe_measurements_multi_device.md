# dedupe_measurements_multi_device.py — Removes measurements rows that are the

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/dedupe_measurements_multi_device.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bereinigt `measurements`-Zeilen, die exakt dieselbe reale Messung sind, aber unter ZWEI verschiedenen device_id-Werten gespeichert wurden (identisches ts, metric, value/value_text, source_app, person -- nur device_id unterscheidet sich). Groesster Befund: ein erheblicher Anteil der heart_rate-Zeilen aus source_app='polar_connect' sind solche Zwillingspaare.

## Relevanz

Betrifft primaer heart_rate/polar_connect (hohe Duplikatrate) und fliesst in praktisch jede HF-basierte Auswertung im Projekt ein (Schlaf-/Tag-HF-Vergleich, Orthostase-Erkennung, PEM-Score, ...). Mittelwerte sind bei gleichmaessiger 2-fach-Duplizierung rechnerisch unveraendert, aber jede stichprobengroessen-abhaengige Logik (Mindest-n-Schwellen) zaehlte bislang doppelt.

## Methode

Ursachenanalyse (per identity_resolver.reverse_resolve + health_config.device_registry): die betroffenen device_ids sind ECHTE, unterschiedliche Geraete desselben Sensortyps (verschiedene, im device_registry gefuehrte Seriennummern) -- kein Pseudonymisierungs-Bug, der einem Geraet mehrere IDs zugewiesen haette. Ein betroffener device_registry-Eintrag dokumentiert bereits eigenstaendig zeitliche Ueberschneidungen mit anderen Handgelenksgeraeten ("date-basierte Einzelgeraete-Zuordnung zeitweise mehrdeutig"). Die Duplikate selbst (identischer Wert auf die Dezimalstelle, Sekunde fuer Sekunde ueber laengere Zeitraeume) sind fuer zwei unabhaengige optische Handgelenks- sensoren physikalisch nicht plausibel -- stattdessen wird ein und dieselbe zugrundeliegende Polar-API-Messung beim Import (oder bereits in Polars eigenem Export) zwei registrierten Geraeten gleichzeitig zugeordnet, vermutlich weil measurements' PRIMARY KEY (ts, metric, device_id, person) device_id explizit als Teil der Identitaet behandelt -- zwei verschiedene device_ids fuer denselben ts+metric sind also aus Schema-Sicht kein Konflikt, INSERT OR IGNORE greift nicht. Fix: gruppiert nach (person, metric, ts, value, value_text, source_app) -- bewusst OHNE device_id/unit in der Gruppierung, da genau device_id die Fehlerquelle ist. Aus jeder Gruppe (>1 Zeile) wird die Zeile mit dem kleinsten rowid behalten (device_id spielt fuer keine bekannte Auswertung in diesem Projekt eine Rolle -- nur source_app), die uebrigen werden gelöscht.

## Datenfluss

- **Liest:** `health.db`, `(measurements)`
- **Schreibt:** `health.db (DELETE auf measurements fuer Duplikat-Zeilen)`

## Grenzen

Betrifft nur die in METRICS_TO_CHECK gelisteten Metriken (dort wurde die Duplikation konkret nachgewiesen) -- kein globaler Scan ueber alle measurements-Metriken, um die Laufzeit auf einer 40+ Mio.-Zeilen-Tabelle uebersehbar zu halten. Nach dem Lauf sollten HF-abhaengige compute-/analyse-Skripte neu laufen (compute_orthostatic_detection.py, analyse_sleep_day_hr.py, compute_pem.py, ...).

## Aufruf

```bash
python3 scripts/migrations/dedupe_measurements_multi_device.py --dry-run
python3 scripts/migrations/dedupe_measurements_multi_device.py
```
