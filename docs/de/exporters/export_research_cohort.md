# export_research_cohort.py — research cohort export with anonymization

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/exporters/export_research_cohort.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Exportiert anonymisierte Forschungs-Kohorten aus mehreren Patient:innen-Instanzen. Prüft Einwilligungen, wendet Datumsverschiebung und Altersbänderung an, und filtert kleine Gruppen per k-Anonymität. Ohne gültige Einwilligung für ALLE aktiven Patient:innen wird KEINE Ausgabe geschrieben (Abbruch vor jeglichem Schreiben).

## Relevanz

Ermöglicht den Export von Gesundheitsdaten, essentiell für die Datenweitergabe und Interoperabilität

## Methode

1. Liest patient_number_map aus master.db 2. Prüft research_consent für jeden Scope 3. Bricht ab, falls irgendeine aktive Instanz keine Einwilligung hat 4. Aktiviert jede Instanz nacheinander, führt Profil-Export durch 5. Wendet Datumsverschiebung pro Patient an 6. Wendet Altersbänderung an 7. Prüft k-Anonymität auf Quasi-Identifikatoren 8. Schreibt behaltene Daten + Manifest, unterdrückte Daten separat

## Datenfluss

- **Liest:** `~/.config/kyoro-master/master.db`, `patient`, `instance`, `health.db`, `files`
- **Schreibt:** `KYORO_MASTER_DIR/research_exports/<date>/...`

## Grenzen

Datumsverschiebung entfernt zeitliche Alignment zwischen Patient:innen. k-Anonymität prüft nur explizit angegebene Quasi-Identifikatoren. Keine automatische Erkennung von Identifikatoren.

## Aufruf

```bash
python3 scripts/exporters/export_research_cohort.py         --scope study-2026-hrv-cohort-a         --profile research         --quasi-identifiers age_band,timezone         --k 5 --age-band-width 5         --date-from 2020-01-01 --date-to 2026-12-31
python3 scripts/exporters/export_research_cohort.py --help
```
