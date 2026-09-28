# Docstring Validierungstool für Kyoro-HealthHub

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/check_docstrings.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Validiert alle Docstrings im Projekt gegen das strukturierte Schema

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Durchsucht rekursiv Python-Dateien, extrahiert Modul-Docstrings via AST, prüft auf erforderliche Tags basierend auf @tier-Klassifizierung, validiert bilinguale Tags und Referenzformatierung

## Datenfluss

- **Liest:** `Alle`, `Python-Dateien`, `in`, `den`, `angegebenen`, `Verzeichnissen`
- **Schreibt:** `STDERR/STDOUT (Fehlermeldungen und Statistik)`

## Grenzen

Erkennt nur Modul-Docstrings, nicht Funktions-Docstrings (geplant für v2). Automatische Korrekturen noch nicht implementiert.

## Aufruf

```bash
python scripts/check_docstrings.py
python scripts/check_docstrings.py --path scripts/compute
python scripts/check_docstrings.py --stats
```
