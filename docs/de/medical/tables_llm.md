# tables_llm.py — Tabellenextraktion via Vision Language Model

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/medical/tables_llm.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Extrahiere Tabellen aus gescannten PDF-Dokumenten mittels Vision Language Model (VLM). Nutzt die zentrale call_llm()-Funktion mit Bildunterstützung.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Ablauf: 1) PDF-Seiten zu Bildern konvertieren, 2) Jedes Bild via call_llm() mit image_b64 Parameter verarbeiten, 3) LLM liefert Tabellen als Markdown, 4) Nach jeder Seite Zwischenspeicherung. Provider-Wahl kommt aus health_config.json.

## Datenfluss

- **Liest:** `PDF-Dateien`, `(z.B.`, `medicine/krankenakte/*.pdf)`
- **Schreibt:** `exports/tables/ Verzeichnis (Markdown/CSV-Dateien)`

## Grenzen

Abhängig von VLM-Genauigkeit. Für komplexe Layouts kann manuelle Nachbearbeitung nötig sein.

## Aufruf

```bash
python medical/tables_llm.py
python medical/tables_llm.py --lang en
```
