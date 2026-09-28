# analyse_skin.py — Hautlaesionen Verlaufsanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_skin.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Zeigt zeitlichen Verlauf von Hautläsionen mit LLM/VLM-Analyse

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Analysiert Hautläsionen und zeigt: - Übersicht aller Läsionen mit aktuellem Triage-Status - Zeitachse einer einzelnen Läsion (alle Fotos + VLM-Befunde) - VLM-Analyse aller noch nicht analysierten Fotos (--analyse) - LLM-Delta-Analyse: Veränderungen zwischen Aufnahmen

## Berechnung

```
Triage-Score basierend auf Läsionsgröße, Veränderungsrate und VLM-Klassifikation
```

## Datenfluss

- **Liest:** `lesion_photos`, `lesion_metadata`
- **Schreibt:** `Analyseergebnisse als Markdown`

## Grenzen

Heuristische Methode. VLM/LLM-Analyse kann ungenau sein.

## Referenzen

- Esteva A, Kuprel B, Novoa RA et al. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542(7639):115-118. doi:10.1038/nature21056
- Tschandl P, Codella N, Akay BN et al. (2019). Comparison of the accuracy of human readers versus machine-learning algorithms for pigmented skin lesion classification: an open, web-based, international, diagnostic study. The Lancet Oncology, 20(7):938-947. doi:10.1016/S1470-2045(19)30333-X

## Aufruf

```bash
python3 scripts/analysis/analyse_skin.py              # Uebersicht alle Laesionen
python3 scripts/analysis/analyse_skin.py --analyse    # VLM fuer alle neuen Fotos
python3 scripts/analysis/analyse_skin.py --lesion 3   # Verlauf Laesion 3
python3 scripts/analysis/analyse_skin.py --lesion 3 --compare  # LLM-Delta
python3 scripts/analysis/analyse_skin.py --watch-list  # Nur Laesionen mit Handlungsbedarf
```
