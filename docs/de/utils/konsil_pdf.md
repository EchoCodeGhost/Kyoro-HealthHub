# konsil_pdf.py — Konsil-Gutachten als PDF rendern

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/konsil_pdf.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Rendert die Markdown-Gutachten eines Konsil-Laufs zu druckfertigen PDFs: ein Sammelband mit Deckblatt und Inhaltsverzeichnis sowie ein Einzel-PDF je Gutachten.

## Relevanz

Ermöglicht die druckfertige Weitergabe von Konsil-Gutachten an Ärzte, essentiell für die Arztkommunikation

## Methode

Markdown -> HTML (python-markdown, Tabellen-Extension) -> PDF via Chrome im Headless-Modus (--print-to-pdf). Chrome ist auf macOS ohnehin vorhanden; damit entfaellt eine LaTeX-/wkhtmltopdf- Abhaengigkeit. Seitenumbrueche zwischen Gutachten per CSS.

## Datenfluss

- **Liest:** `analyses/<datum>/konsil/*.md`
- **Schreibt:** `analyses/<datum>/konsil/pdf/*.pdf`

## Grenzen

Braucht Google Chrome an einem der bekannten Pfade. Ohne Chrome wird das HTML trotzdem geschrieben und der Pfad gemeldet, damit manuell gedruckt werden kann.

## Aufruf

```bash
python3 scripts/utils/konsil_pdf.py analyses/2026-08-02/konsil
python3 scripts/utils/konsil_pdf.py analyses/2026-08-02/konsil --einzeln
```
