# md_to_pdf.py — Markdown-Dateien in PDF umwandeln (via pandoc + xelatex)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/md_to_pdf.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Konvertiert eine oder mehrere Markdown-Dateien zu druckbaren PDFs. Optimiert für medizinische Berichte: saubere Typografie, Titelblock, Datum, Seitenzahlen, Querverweise.

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

Ruft pandoc mit xelatex-Engine auf. Schriftart, Ränder und Metadaten werden per YAML-Frontmatter oder CLI-Flags gesetzt. Ohne --title wird der Dateiname als Titel verwendet.

## Datenfluss

- **Liest:** `Markdown-Datei(en)`, `(.md)`
- **Schreibt:** `PDF-Datei(en) (neben der Quelldatei oder in --out-dir)`

## Grenzen

Benötigt pandoc ≥ 2.x und xelatex (texlive). Sehr lange Tabellen können über Seitenränder laufen — ggf. --landscape nutzen.

## Aufruf

```bash
python3 scripts/utils/md_to_pdf.py bericht.md
python3 scripts/utils/md_to_pdf.py analyses/manual/lab_verlauf_*.md
python3 scripts/utils/md_to_pdf.py bericht.md --out-dir exports/
python3 scripts/utils/md_to_pdf.py bericht.md --title "Labor-Befunde" --author "Kyoro"
python3 scripts/utils/md_to_pdf.py bericht.md --landscape
python3 scripts/utils/md_to_pdf.py bericht.md --font-size 10
```
