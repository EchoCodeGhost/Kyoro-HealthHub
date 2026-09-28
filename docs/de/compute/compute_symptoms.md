# Symptom canonicalisation: symptoms -> symptoms_canonical.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_symptoms.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Normiert rohe Symptombezeichnungen (DE/EN, verschiedene Apps) auf ein einheitliches kanonisches Vokabular. Reines Vokabular-Mapping.

## Relevanz

Ermöglicht die Symptomanalyse, essentiell für die klinische Diagnostik

## Methode

Jede Bezeichnung wird über die Mapping-Datei auf kanonische DE/EN- Begriffe abgebildet. Nicht gemappte Einträge werden 1:1 übernommen (category='other').

## Datenfluss

- **Liest:** `symptoms`
- **Schreibt:** `symptoms_canonical`

## Grenzen

Bewusst keine ICD-10-Kodierung — Symptom-Mapping-Dateien werden nicht als verifizierte Diagnose-Kodierungsquelle gepflegt (s. Commit-Historie). Nicht gemappte Symptome bleiben unkategorisiert.

## Aufruf

```bash
python3 compute_symptoms.py
python3 compute_symptoms.py --update
python3 compute_symptoms.py --list-unmapped
```
