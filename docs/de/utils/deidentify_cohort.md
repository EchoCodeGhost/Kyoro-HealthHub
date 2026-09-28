# deidentify_cohort.py — k-anonymity and date-shifting helper functions

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/deidentify_cohort.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet deterministische Datumsverschiebung pro Patient-Pseudonym, Altersbänderung und k-Anonymitätsprüfung für Forschungs-Kohorten-Exporte. Die Datumsverschiebung ist deterministisch (gleiche Person → gleicher Offset bei jedem Lauf), aber nicht aus der Ausgabe rekonstruierbar (Einweg-Hash, analog zu pseudonymize_device_serial).

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

- date_shift_offset_days: Berechnet Offset aus SHA-256-Hash des Pseudonyms - shift_date: Verschiebt Datumswerte um den Offset - age_band: Konvertiert Geburtsdatum zu Altersband (z.B. "30-34") - check_k_anonymity: Prüft Gruppengrößen auf Quasi-Identifikatoren

## Datenfluss

- **Liest:** `(none`, `—`, `pure`, `functions)`
- **Schreibt:** `(none — pure functions)`

## Grenzen

Datums-Verschiebung ist deterministisch pro Patient-Pseudonym, aber nicht aus der Ausgabe rekonstruierbar. k-Anonymität prüft nur die explizit übergebenen Spalten — keine automatische Erkennung identifizierender Felder. Altersbänderung verwendet immer volle Kalenderjahre, keine exakte Alterstage.

## Aufruf

```bash
from utils.deidentify_cohort import date_shift_offset_days, shift_date, age_band, check_k_anonymity
```
