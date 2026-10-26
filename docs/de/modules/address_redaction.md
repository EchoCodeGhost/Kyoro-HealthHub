# address_redaction.py — Postadressen in Freitext erkennen und entfernen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/address_redaction.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erkennt deutsche Postanschriften in Text (Straße mit Hausnummer, Postleitzahl mit Ort, Postfach) und ersetzt sie durch einen Platzhalter. Zusätzlich lassen sich bekannte Adressen der betroffenen Person lokal hinterlegen, damit auch ungewöhnliche Schreibweisen sicher erfasst werden.

## Relevanz

Verhindert, dass Wohnadressen in Texten, PDFs und Bildern an externe Dienste oder in Exporte gelangen

## Methode

Reguläre Ausdrücke für drei Formen: zusammengesetzte Straßennamen mit Endung (…straße, …str., …weg, …allee, …gasse, …platz, …ring, …damm, …ufer, …steig, …pfad, …chaussee, …promenade) plus Hausnummer; Präpositionalstraßen (Am …, An der …, Im …, In der …, Auf dem …, Zum …, Zur …) plus Hausnummer; Postleitzahl (5 Ziffern, optional mit D-) plus Ortsname. Treffer, die nur durch Komma, Leerzeichen oder Zeilenumbruch getrennt sind, werden zu einem Platzhalter verschmolzen. Konfigurierte Adressen aus health_config.json (privacy_check.patient_addresses) werden zu toleranten Mustern (ß/ss, Str./Straße, Leerraum) umgebaut und zusätzlich geprüft. Mengenangaben (mg, ml, Tage, Schritte …) hinter Zahlen lösen keinen Treffer aus.

## Datenfluss

- **Liest:** `~/.config/kyoro/health_config.json`, `(privacy_check.patient_addresses`, `optional)`
- **Schreibt:** `Keine (reine Textfunktionen)`

## Grenzen

Heuristik, keine Garantie: Straßen ohne übliche Endung und ohne Präposition (z. B. "Hauptmarkt 3"), Adressen in Fremdsprachen und stark verstümmelter OCR-Text werden nur über konfigurierte Adressen sicher erfasst. Ortsnamen ohne Postleitzahl werden nicht entfernt. Eine fünfstellige Zahl vor einem großgeschriebenen Wort kann fälschlich als Postleitzahl gelten; häufige Einheiten und Mengenwörter sind ausgenommen. Entfernt Adressen von Praxen und Laboren ebenso wie private Adressen.

## Aufruf

```bash
from modules.address_redaction import redact_addresses, find_address_spans
redact_addresses("Musterstraße 12, 12345 Musterstadt")   # -> "[ADRESSE-ENTFERNT]"
find_address_spans("Am Mühlberg 5")                       # -> [Span(0, 14, 'street')]
```
