# scrub_apple_xml — Apple Health Export.xml PII-Bereinigung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/scrub_apple_xml.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Entfernt persönlich identifizierbare Informationen (PII) aus Apple Health Export.xml Dateien. Überschreibt die Datei in-place oder schreibt in eine angegebene Ausgabedatei. Entfernt: persönliche Namen aus sourceName Attributen und weitere PII aus dem <Me> Element.

## Relevanz

Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz

## Methode

Verwendet schnelle regex-basierte Zeilenverarbeitung (kein vollständiges XML-Parsing), um Dateien beliebiger Größe ohne Laden in den Speicher zu verarbeiten. spezifische Regex-Muster für: sourceName-Attribute, <Me>-Element-Attribute (HKCharacteristicTypeIdentifierDateOfBirth, HKCharacteristicTypeIdentifierBiologicalSex, etc.). Ersetzt Werte durch neutrale Standardwerte oder leere Strings. Unterstützt Dry-Run-Modus (--check) zur Vorschau ohne Änderungen.

## Datenfluss

- **Liest:** `Apple`, `Health`, `Export.xml`, `(Standardpfad`, `aus`, `health_config.json)`
- **Schreibt:** `Apple Health Export.xml (in-place) oder angegebene Ausgabedatei`

## Grenzen

Verarbeitet Dateien zeilenweise - sehr groß Dateien können länger dauern. Ersetzt nur bekannte PII-Muster - unbekannte Muster werden nicht erkannt. Originaldatei wird überschrieben (Backup empfohlen).

## Aufruf

```bash
python scripts/utils/scrub_apple_xml.py
python scripts/utils/scrub_apple_xml.py --check
python scripts/utils/scrub_apple_xml.py --out /path/to/clean.xml
python scripts/utils/scrub_apple_xml.py --xml /path/to/Export.xml --check
# --check: Probelauf — keine Änderungen (zählt nur Treffer)
# --out: Ausgabedatei (Standard: in-place Überschreiben)
# --xml: Pfad zur Export.xml (Standard: aus health_config.json)
```
