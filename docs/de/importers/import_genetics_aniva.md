# import_genetics_aniva.py — Aniva Health Biomarker- und Genetik-Daten importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_genetics_aniva.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Aniva Health Daten in zwei Modi: 1. Biomarker-CSV (Standard-Mitgliedschaft): 100+ Blutmarker → lab_manual 2. Genetik-CSV (Genetik-Add-on): SNP-Panel → genetic_risk_markers Aniva ist eine Longevity-Plattform mit biologischer Altersbestimmung, personalisierten Empfehlungen und optionalem Genetik-Add-on.

## Relevanz

Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse

## Methode

Modus 1 (--mode biomarker): Liest Aniva-Biomarker-CSV (Template: templates/aniva_biomarker_template.csv) → lab_manual. Modus 2 (--mode genetics): Liest Aniva-Genetik-CSV (Template: templates/genetics_manual_template.csv) → genetic_risk_markers. Erkennt Modus automatisch anhand der CSV-Spaltenköpfe falls --mode fehlt.

## Datenfluss

- **Liest:** `CSV-Datei`, `(Aniva`, `Dashboard-Export`, `oder`, `manuell`, `ausgefüllt)`
- **Schreibt:**

  ```
  health.db:lab_manual (Biomarker), health.db:genetic_risk_markers (Genetik),
  health.db:import_log
  ```

## Grenzen

Aniva stellt keinen standardisierten Maschinenexport bereit (Stand 2026). Daten müssen manuell aus dem Dashboard in das Template übertragen werden. Für biologisches Alter: Wert in Jahren in lab_manual (parameter='Biologisches Alter').

## Aufruf

```bash
# Biomarker (Standard-Mitgliedschaft):
python3 scripts/importers/import_genetics_aniva.py aniva_biomarker_2026-01.csv
python3 scripts/importers/import_genetics_aniva.py aniva_biomarker.csv --mode biomarker --dry-run
```
