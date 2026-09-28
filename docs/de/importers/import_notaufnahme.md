# import_notaufnahme.py — RKI-Notaufnahmesurveillance → health.db (ed_syndromic_surveillance)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_notaufnahme.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert die RKI-Notaufnahmesurveillance (AKTIN-Infrastruktur/ Notaufnahmeregister) — tagesaktuelle Anteile von ARI-, ILI-, COVID-, SARI-, GI- und HEAT-Vorstellungen an allen Notaufnahme-Besuchen in Deutschland, inkl. Erwartungswert und Prädiktionsintervall.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Lädt die bundesweite Zeitreihen-TSV von GitHub (~330.000 Zeilen seit 2019, alle Notaufnahmetypen/Altersgruppen). Filtert standardmäßig auf ed_type='all' und age_group='00+' (Gesamtbevölkerung, alle Kliniktypen) — sonst würde die Alterskohorten-/Kliniktyp-Aufschlüsselung die Tabelle unnötig aufblähen. Rollierendes Zeitfenster wie bei GrippeWeb/ ARE-Konsultationsinzidenz/AMELAG — voller Verlauf seit 2019 via --full-history.

## Datenfluss

- **Liest:** `GitHub`, `(robert-koch-institut/Daten_der_Notaufnahmesurveillance`, `CC-BY`, `4.0)`
- **Schreibt:** `health.db:ed_syndromic_surveillance, health.db:import_log`

## Grenzen

Nur bundesweit aggregiert, keine Bundesland-/Landkreis-Ebene verfügbar. Keine medizinische Interpretation der Werte.

## Referenzen

- RKI Notaufnahmesurveillance: https://github.com/robert-koch-institut/Daten_der_Notaufnahmesurveillance

## Aufruf

```bash
python3 import_notaufnahme.py
python3 import_notaufnahme.py --ed-type all --age-group 00+
python3 import_notaufnahme.py --full-history
```
