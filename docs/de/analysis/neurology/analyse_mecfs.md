# ME/CFS Score — IOM 2015 / ICC 2011 Kriterien

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_mecfs.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Bewertet Wearable-Biomarker gegen die Kernsymptom-Domänen der IOM-2015- und ICC-2011-Kriterien (PEM, unrefreshing sleep, Fatigue, Kognition, Orthostatik) — ausschließlich objektive Biomarker, keine Einrichtung.

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Regelbasiertes Scoring mit zitierten Schwellenwerten (POTS ≥30 bpm, DFA α1=0.75, RMSSD <25 ms, Tiefschlaf <15 %, MET-Minuten); Status-Ampel (erfüllt/teilweise/nicht erfüllt/keine Daten).

## Berechnung

```
IOM 2015 criteria: PEM + unrefreshing sleep + fatigue + (cognition OR orthostatic intolerance)
ICC 2011 criteria: PENE + sleep + pain + neurology/autonomy/immunology
Traffic light status: green met | yellow partial | red not met | gray no data
```

## Datenfluss

- **Liest:** `measurements`, `sessions`, `session_metrics`, `symptoms`, `clinical_findings`
- **Schreibt:** `analyses/postinfectious/mecfs_*.{md,png}`

## Grenzen

Heuristische Methode: Biomarker-zu-Kriterien-Mapping ist heuristisch und nicht formal validiert; Langzeitmuster erfordern medizinische Bewertung; Ruhewerte für DFA α1 haben andere Normwerte als Belastungswerte; Schwergrad-Klassifikation ist orientierend.

## Referenzen

- Institute of Medicine (2015). Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome: Redefining an Illness. National Academies Press, Washington, DC. doi:10.17226/19012
- Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x (ICC 2011)
- NICE NG206 (2021): Myalgic encephalomyelitis/chronic fatigue syndrome — guidance; www.nice.org.uk/guidance/ng206 Davenport et al., Workwell Foundation (2-day CPET / ventilatory threshold; the MET-minute cut-offs in REF are heuristic, not Workwell's)
- Davis et al. 2023, Nature Reviews (PEM biomarkers) — UNVERIFIED, no DOI found; no threshold in REF relies on it any more
- Flatt & Esco 2016, Int J Sports Med (DOI ausstehend) (HRV night measurement)
- Rowe PC, Underhill RA, Friedman KJ et al. (2017). Myalgic Encephalomyelitis/Chronic Fatigue Syndrome Diagnosis and Management in Young People: A Primer. Frontiers in Pediatrics, 5:121. doi:10.3389/fped.2017.00121 (Orthostasis & POTS in ME/CFS)
- Ohayon et al. 2004, Sleep 27(7):1255-73 (Tiefschlafanteil altersabhängig)

## Aufruf

```bash
python analyse_mecfs.py
python analyse_mecfs.py --help
python analyse_mecfs.py --from 2024-01-01 --to 2024-12-31
```
