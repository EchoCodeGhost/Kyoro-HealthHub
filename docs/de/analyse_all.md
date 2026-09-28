# Master-Analyse — führt alle analyse_*.py-Skripte aus.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analyse_all.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Führt alle Analyse-Skripte zentral aus und verwaltet die Ausgabe

## Relevanz

Ermöglicht die umfassende Gesundheitsdatenanalyse, essentiell für die ganzheitliche Gesundheitsbewertung

## Methode

Durchsucht rekursiv alle analyse_*.py-Skripte im analysis/-Verzeichnis, erstellt für jedes Skript ein eigenes Ausgabeverzeichnis: <analyses_dir>/<YYYY-MM-DD>/<scriptname>/ Plots (PNG/PDF) und Text-Output (Markdown) werden dort gespeichert. stdout + stderr werden als <scriptname>.log gespeichert. Unterstützt Filterung nach Datum, Skriptnamen und Trockenlauf.

## Datenfluss

- **Liest:** `Alle`, `Tabellen`, `die`, `von`, `den`, `einzelnen`, `Analyse-Skripten`, `gelesen`, `werden`
- **Schreibt:** `Analyseergebnisse in <analyses_dir>/<YYYY-MM-DD>/<scriptname>/`

## Grenzen

Keine direkte Validierung der Ergebnisse. Abhängig von den einzelnen Analyse-Skripten.

## Aufruf

```bash
python analyse_all.py                        # alle Skripte, mit KI-Kommentaren (Standard)
python analyse_all.py --no-llm                # ohne KI-Kommentare
python analyse_all.py --from 2026-01-01      # Datums-Filter
python analyse_all.py --only afib,sleep      # nur bestimmte (Namensbestandteil)
python analyse_all.py --skip cgm,h7          # bestimmte überspringen
python analyse_all.py --date 2026-05-31      # wird an Skripte weitergegeben die --date kennen
python analyse_all.py --dry-run              # zeigt was laufen würde, ohne Ausführung
```
