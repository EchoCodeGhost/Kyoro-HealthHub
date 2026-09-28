# debug_page.py — Testlauf für einzelne PDF-Seite

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/medical/debug_page.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Testet die Tabellenextraktion für eine einzelne PDF-Seite mittels OpenVINO VLMPipeline oder LLM-Provider. Nützlich für Debugging und Entwicklung.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Extrahiere eine spezifizierte Seite aus einem PDF, konvertiert zu Bild und verarbeitet es durch die VLMPipeline. Unterstützt Sprach- und Provider-Auswahl.

## Datenfluss

- **Liest:** `PDF-Dateien`, `(z.B.`, `medicine/krankenakte/*.pdf)`
- **Schreibt:** `STDOUT (extrahierte Tabellen als Markdown)`

## Grenzen

Nur für eine Seite. Benötigt OpenVINO oder LLM-Provider.

## Aufruf

```bash
python medical/debug_page.py 1
python medical/debug_page.py 5 --lang de --provider openvino
```
