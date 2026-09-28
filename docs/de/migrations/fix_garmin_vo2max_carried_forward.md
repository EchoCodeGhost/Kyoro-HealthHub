# fix_garmin_vo2max_carried_forward.py — Separates carried-forward Garmin

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/fix_garmin_vo2max_carried_forward.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

import_garmin.py schrieb mostRecentVO2Max (den zuletzt ermittelten Schaetzwert) taeglich mit dem Abrufdatum. Jeder Tag ohne neue Schaetzung erschien dadurch als eigene Messung: ein unveraenderter Wert wirkte wie eine dichte Messreihe, und Zeilen spaeterer Abruftage trugen ein Datum, an dem Garmin nichts ermittelt hatte. Der Importer ist korrigiert (Datum aus calendarDate); diese Migration zieht bestehende Datenbanken nach.

## Relevanz

Verhindert, dass abgeleitete VO2max-Verlaeufe fortgeschriebene Werte als neue Messungen zaehlen — Datenqualitaet.

## Methode

Je Person und Geraet werden die Zeilen metric='vo2max', source_app='garmin_connect' nach Datum sortiert. Die erste Zeile jeder Folge identischer Werte bleibt 'vo2max' (fruehester Tag, an dem der Wert sichtbar war); alle Folgezeilen derselben Folge werden in 'vo2max_carried_forward' umbenannt. Keine Werte geaendert, keine Zeilen geloescht. Einmalig: ein vorhandener import_log-Eintrag dieser Migration beendet jeden weiteren Lauf ohne Aenderung.

## Datenfluss

- **Liest:** `health.db`, `(measurements)`
- **Schreibt:** `health.db (measurements.metric only)`

## Grenzen

Das Datum der verbleibenden Zeile ist eine Obergrenze: Garmin kann den Wert schon vor dem ersten Abruftag ermittelt haben. Ein Wertwechsel auf denselben Wert (z. B. neue Schaetzung = bisheriger Wert) ist nicht von einer Fortschreibung unterscheidbar und wird als Fortschreibung behandelt. Garmin-Datenschutz-Export (garmin_gdpr, biometricVo2Max) ist eine andere Schaetzung und bleibt unberuehrt.

## Aufruf

```bash
python3 scripts/migrations/fix_garmin_vo2max_carried_forward.py --dry-run
python3 scripts/migrations/fix_garmin_vo2max_carried_forward.py
```
