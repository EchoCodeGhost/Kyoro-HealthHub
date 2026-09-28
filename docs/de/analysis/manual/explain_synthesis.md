# Konsil-Synthese in Alltagssprache — Patientenversion des Vorsitz-Berichts.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/explain_synthesis.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Übersetzt den fachsprachlichen Abschlussbericht des Konsil-Vorsitzes (analyse_synthesis.py) in allgemeinverständliche Sprache und ergänzt ihn um konkrete Handlungsempfehlungen für die Patientin.

## Relevanz

Macht den Konsil-Abschlussbericht ohne Fachvokabular verständlich und ergänzt konkrete nächste Schritte für die Patientin

## Methode

Liest die neueste (oder per --file angegebene) Synthese-Datei, entfernt die Arbeitsanhänge (Kategorie-Notizen, Einzelmeinungen — das sind Zwischenstände, nicht das Endergebnis) und lässt nur den finalen Vorsitz-Text von einem LLM in Alltagssprache übertragen. Konfidenz-/Wahrscheinlichkeitsangaben müssen dabei erhalten bleiben (siehe openspec/specs/documentation-conventions). Die beiden Standardempfehlungen (zuerst Hausarzt, Arztberichte zwischen allen Behandelnden austauschen) werden NICHT dem LLM überlassen, sondern als fester Abschnitt angehängt. Erwähnt der Quellbericht PEM, wird zusätzlich ein fester Hinweis angehängt, dass PEM-Scores aus diesem Projekt ein nicht klinisch validierter Heuristik-Score sind (s. compute_pem.py @tier heuristic).

## Datenfluss

- **Liest:** `analyses/synthesis/synthesis_*.md`
- **Schreibt:** `analyses/synthesis/<name>_patientenversion.md (Markdown, lokal)`

## Grenzen

Heuristische Methode: LLM-Übersetzung, keine medizinische Beratung. Ersetzt kein Arztgespräch. Es werden keine neuen medizinischen Aussagen erzeugt — nur eine Übertragung des Vorsitz-Textes.

## Aufruf

```bash
python3 scripts/analysis/manual/explain_synthesis.py
python3 scripts/analysis/manual/explain_synthesis.py --file analyses/synthesis/synthesis_20260808_1704.md
python3 scripts/analysis/manual/explain_synthesis.py --lang en
```
