# analyse_synthesis.py — LLM-basierte Synthese aller Einzelanalysen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_synthesis.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Erstellt LLM-basierte Synthese aller Einzelanalysen

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Liest die aktuellsten Markdown-Berichte aus analyses/ und laesst das LLM alle Einzelbefunde unvoreingenommen im Gesamtkontext bewerten: uebergreifende Muster, wahrscheinliche Zusammenhaenge, naechste Schritte, Prioritaeten. Das LLM erhaelt keine Vordiagnosen — es leitet alles aus den Daten ab. Optional: Mehr-Modell-Panel (Konsil-Modus) — mehrere LLMs bewerten unabhängig (jeweils mit dem vollen Analyse-Prompt). Der Vorsitz liest die Rohdaten danach kategorienweise (eine Runde pro medizinischer Kategorie unter scripts/analysis/, z.B. cardiovascular, sleep, infectious) statt alles auf einmal, um Kontextfenster- Grenzen einzuhalten; jede Kategorie-Runde bekommt alle vier vollständigen Panel-Meinungen plus alle bisherigen Kategorie-Notizen (unveraendert, nie ueberschrieben) und schreibt eine eigene, abgeschlossene Notiz. Eine Abschlussrunde liest alle Kategorie-Notizen + alle Panel-Meinungen nochmal und schreibt die finale Synthese. Alle Kategorie-Notizen bleiben als eigenstaendige Artefakte im Anhang erhalten (Chain of Custody). Aktiviert ueber synthesis_panel.enabled=true in health_config.json.

## Berechnung

```
Synthese-Score basierend auf Konsistenz, Schweregrad und zeitlicher Persistenz der Befunde
```

## Datenfluss

- **Liest:** `Alle`, `Analyse-Berichte`, `aus`, `analyses/`
- **Schreibt:** `Synthese-Bericht als Markdown (mit Anhang: Einzelmeinungen bei Panel-Modus)`

## Grenzen

Heuristische Methode: Heuristische LLM-Analyse. Keine medizinische Diagnose.

## Referenzen

- Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
- Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7
- Muneer A, Zhang K, Hamdi I, Qureshi R, Waqas M, Fouad S, Ali H, Anwar SM, Wu J (2026). Foundation models in biomedical imaging: turning hype into reality. Nature Biomedical Engineering, 10:1557-1575. doi:10.1038/s41551-026-01762-z (REAL-FM framework — Grundlage fuer Abschnitt "Konfidenz & Beleglage" und die Vorsitz-Gegenprüfung gegen die eigenen Kategorie-Notizen weiter unten)

## Aufruf

```bash
python3 scripts/analysis/analyse_synthesis.py
python3 scripts/analysis/analyse_synthesis.py --since 2026-06-01
python3 scripts/analysis/analyse_synthesis.py --top 25 --bottom 80
python3 scripts/analysis/analyse_synthesis.py --dry-run
python3 scripts/analysis/analyse_synthesis.py --lang en
python3 scripts/analysis/analyse_synthesis.py --no-panel
python3 scripts/analysis/analyse_synthesis.py --yes
```
