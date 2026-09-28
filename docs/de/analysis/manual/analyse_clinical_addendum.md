# analyse_clinical_addendum.py — Klinisches Addendum zur Daten-Synthese

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_clinical_addendum.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Generiert ein klinisches Addendum zur Daten-Synthese

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Liest den aktuellsten Synthese-Bericht und klinische Beobachtungen aus der Config (clinical.observations) und generiert ein Addendum, das strukturelle Datenlücken adressiert. Typische Lücken: - Unterschätzung von Mustern mangels Messdaten - Pharmakologische Ansprechmuster aus klinischer Beobachtung - Methodische Verzerrungen (z.B. Deckeneffekt beim Orthostase-Test)

## Berechnung

```
Gewichtung basierend auf Datenverfügbarkeit und Beobachtungsqualität
```

## Datenfluss

- **Liest:** `Synthese-Berichte`, `aus`, `analyses/synthesis/`, `Config`, `clinical.observations`
- **Schreibt:** `Addendum als Markdown-Datei`

## Grenzen

Heuristische Methode. Abhängig von Qualität der klinischen Beobachtungen.

## Referenzen

- Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7
- Moor M, Banerjee O, Abad ZSH, Krumholz HM, Leskovec J, Topol EJ, Rajpurkar P (2023). Foundation models for generalist medical artificial intelligence. Nature, 616(7956):259-265. doi:10.1038/s41586-023-05881-4

## Aufruf

```bash
python3 scripts/analysis/manual/analyse_clinical_addendum.py
python3 scripts/analysis/manual/analyse_clinical_addendum.py --synthesis analyses/synthesis/synthesis_20260704_2140.md
python3 scripts/analysis/manual/analyse_clinical_addendum.py --lang en
```
