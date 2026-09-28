# Compliance-Prüfskript für Docstrings im Kyoro-HealthHub

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/check_compliance.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft alle Docstrings auf Compliance-Verletzungen (medizinische Diagnosen, demografische Merkmale, Altersangaben, geografische Standorte)

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Durchsucht rekursiv Python-Dateien, extrahiert Modul-Docstrings via AST, prüft auf verbotene Inhalte: medizinische Diagnosen (ME/CFS, POTS, etc.), demografische Daten, Altersdaten, geografische Standorte. Bekannte Fehlalarme können per --review manuell als Baseline freigegeben werden (compliance_baseline.json, an einen Hash des jeweiligen Docstrings gebunden — ändert sich der Docstring, verfällt die Freigabe automatisch).

## Datenfluss

- **Liest:** `Alle`, `Python-Dateien`, `in`, `den`, `angegebenen`, `Verzeichnissen`, `compliance_baseline.json`
- **Schreibt:** `STDERR/STDOUT (Fehlermeldungen und Statistik), compliance_baseline.json (nur bei --review)`

## Grenzen

Erkennt nur offensichtliche Verstöße. Falsch-positive möglich. Keine semantische Analyse, nur Pattern-Matching. Die Baseline verhindert falsches Rot, ersetzt aber keine echte Pattern-Verbesserung — sie dokumentiert nur, dass ein Mensch den konkreten Treffer geprüft hat.

## Aufruf

```bash
python scripts/check_compliance.py
python scripts/check_compliance.py --path scripts/
python scripts/check_compliance.py --stats
python scripts/check_compliance.py --review
```
