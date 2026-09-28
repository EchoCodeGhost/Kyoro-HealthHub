# Pacing-Modell & Tagesaktivitäts-Budget

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/psychology/analyse_pacing.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert das vollständige Tages-Aktivitätsprofil (Polar MET-Minuten, Sedentär/Leicht/Moderat/Intensiv) und korreliert es mit PEM-Ereignissen und Folgetag-HRV zur Ermittlung eines sicheren Aktivitätsbudgets.

## Relevanz

Ermöglicht die Bestimmung eines sicheren Aktivitätsbudgets für Patienten mit Post-Exertioneller Malaise (PEM), essentiell für das Pacing-Management bei ME/CFS und anderen chronischen Erkrankungen

## Methode

Tagesaggregat aus measurements (met_minutes, level_*_s); Lag-Korrelation Belastung × Folgetag-HRV; PEM-Ereignisse aus pem_correlation via pem_loader; eigene MET-Minuten-Schwellenwerte.

## Berechnung

```
Aktivitätsbudget-Klassifikation (heuristisch, projektintern):
Quintil-Einteilung der MET-Minuten-Tage; HRV-Drop >10% nach Q4/Q5-Tag = PEM-Warnung
Aktivitätsproxy (ohne Polar-Daten): (steps − 2000) × 0.05 kcal-Äquivalent (heuristisch)
Polar-MET-Kategorien im SYSTEM_PROMPT: Sedentär <1.5, Leicht 1.5–3.0, Moderat 3.0–6.0, Intensiv >6.0 MET
(orientiert an WHO/ACSM-Definitionen, Polar-Implementierung proprietär)
Basis: projektintern; WHO GAPA 2018 (<150 min/Woche moderat = insuffizient) als Hintergrundkontext.
```

## Datenfluss

- **Liest:** `measurements`, `pem_correlation`, `symptoms`
- **Schreibt:** `analyses/psychology/pacing_*.{md,png}`

## Grenzen

Heuristische Methode: MET-Schwellenwerte sind heuristisch (nicht aus Belastungstest kalibriert); Polar-Activity-Levels sind proprietär und können von WHO/ACSM-Definitionen abweichen; Steps-Proxy-Formel (steps−2000)×0.05 projektintern; Korrelation explorativ ohne Signifikanztests; PEM-Events erfordern vorheriges compute_pem.py.

## Referenzen

- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual Model for Physical Therapist Management of Chronic Fatigue Syndrome/Myalgic Encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047
- Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior. doi:10.1080/21641846.2012.733602

## Aufruf

```bash
python analyse_pacing.py
python analyse_pacing.py --help
python analyse_pacing.py --from 2024-01-01 --to 2024-12-31
```
