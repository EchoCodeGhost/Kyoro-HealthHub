# Health Event Timeline Analysis — Systematic Biomarker Comparison

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/internal_medicine/analyse_health_timeline.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Vergleicht Biomarker (HRV, RHR, SpO₂, Aktivität) systematisch über N+1 konfigurierbare Zeitperioden, die aus clinical.events abgeleitet werden.

## Relevanz

Ermöglicht die umfassende zeitliche Analyse des Gesundheitsverlaufs, essentiell für die Identifikation von Mustern, Trends und kritischen Ereignissen in der individuellen Gesundheitsgeschichte

## Methode

Perioden-Mittelwerte und Trends aus dem Measurements-EAV-Schema; LLM-Kommentierung via SYSTEM_PROMPT; Plots als PNG-Zeitreihen.

## Berechnung

```
Period comparison: pre vs post-event trend analysis
Biomarker change: delta percentage from baseline
```

## Datenfluss

- **Liest:** `measurements`, `sessions`, `session_metrics`, `symptoms`
- **Schreibt:** `analyses/postinfectious/health_timeline_*.{md,png}`

## Grenzen

Heuristische Methode: Unvalidierter Periodenvergleich; Stichprobengröße je Periode variiert stark; keine Konfidenzintervalle; klinische Kausalität nicht ableitbar.

## Referenzen

- Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
- Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7

## Aufruf

```bash
python analyse_health_timeline.py
python analyse_health_timeline.py --help
python analyse_health_timeline.py --from 2024-01-01 --to 2024-12-31
```
