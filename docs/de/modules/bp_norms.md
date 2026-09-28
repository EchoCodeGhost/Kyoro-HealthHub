# bp_norms.py — Einheitliche Blutdruck-Einstufung nach ESC/ESH

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/bp_norms.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Stellt EINE gemeinsame, zitierte Einstufung des in der Sprechstunde bzw. zuhause gemessenen Blutdrucks bereit und verhindert, dass aus zu wenigen oder nicht standardisierten Messungen ein Schweregrad abgeleitet wird.

## Relevanz

Eine Bluthochdruck-Einstufung ist eine folgenreiche Aussage. Sie aus einer Einzelmessung oder mit verschobenen Grenzen zu erzeugen, erzeugt entweder falsche Sorge oder falsche Entwarnung.

## Methode

Reine Nachschlagelogik, keine Berechnung. Grenzwerte nach ESC/ESH (Messung in der Sprechstunde): optimal <120, normal 120-129, hoch-normal 130-139, Grad 1 140-159, Grad 2 160-179, Grad 3 ab 180 systolisch; ein diastolischer Wert ab 90 hebt ebenfalls in Grad 1. Fuer die haeusliche Selbstmessung gilt die niedrigere Schwelle 135/85. Zusaetzlich eine Mindestanzahl: Unterhalb davon wird KEIN Grad vergeben, sondern der Messwert als Einzelbefund ausgewiesen. Zwei Skripte dieses Projekts trugen zuvor gegeneinander verschobene Grenzen (eines stufte ab 140 als "Grad 2" ein) und vergaben einen Grad auch bei einer einzigen Messung.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Die Einstufung ersetzt keine aerztliche Beurteilung — sie setzt standardisierte Messbedingungen voraus (Ruhe, kein Koffein/Nikotin davor, korrekte Manschette, Mittel aus mehreren Messungen an mehreren Tagen). Ob diese Bedingungen eingehalten wurden, weiss dieses Modul nicht — Aufrufer sollten dokumentierte Stoerfaktoren aus der Datenquelle mit ausgeben.

## Referenzen

- Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH Guidelines for the management of arterial hypertension. European Heart Journal 39(33):3021-3104. doi:10.1093/eurheartj/ehy339

## Aufruf

```bash
from modules.bp_norms import classify, MIN_READINGS_FOR_GRADE
classify(142.0, 89.0, n_readings=1)
# -> ("Einzelmessung, keine Einstufung", False)
classify(142.0, 89.0, n_readings=12)
# -> ("Grad 1 Hypertonie", True)
```
