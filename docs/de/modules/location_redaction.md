# location_redaction.py — GPS-Koordinaten und persönliche Ortsnamen in Text erkennen und entfernen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/location_redaction.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erkennt GPS-Koordinaten im Text (Dezimalgrad, Grad/Minuten/Sekunden, Koordinaten mit Bezeichner) sowie persönliche Ortsnamen (Wohnort, Arbeitsort, weitere hinterlegte Orte) und ersetzt sie durch Platzhalter. Ergänzt address_redaction, name_redaction und identifier_redaction für Bilder, PDFs und Cloud-Aufrufe.

## Relevanz

Verhindert, dass Aufenthaltsorte und Standortdaten aus Befunden, Berichten und Fotos in Ablage, Exporte oder an externe Dienste gelangen

## Methode

Koordinaten: Dezimalgradpaare mit mindestens fünf Nachkommastellen (48.13514, 11.58198) bzw. vier mit Himmelsrichtung (N 48.1351 E 11.5820), Grad/Minuten/Sekunden mit Himmelsrichtung (48°08'06"N 11°34'55"E) und Zahlen hinter Bezeichnern wie GPS, Koordinaten, Lat, Lon, Breitengrad. Ortsnamen: nur Orte aus der lokalen Konfiguration (health_config.json: privacy_check.patient_places), Orte aus den hinterlegten Adressen (der Ort hinter der Postleitzahl in privacy_check.patient_addresses) und Orte, die der Aufrufer angibt. Es wird kein allgemeines Ortsverzeichnis benutzt, damit Bundesländer, Länder, Reiseziele und Endemiegebiete für die Auswertung erhalten bleiben.

## Datenfluss

- **Liest:** `~/.config/kyoro/health_config.json`, `(privacy_check.patient_places`, `privacy_check.patient_addresses`, `optional)`
- **Schreibt:** `Keine (reine Textfunktionen)`

## Grenzen

Heuristik, keine Garantie: Ortsnamen, die weder konfiguriert noch aus einer Adresse abgeleitet sind, bleiben stehen (z. B. Urlaubsorte, Arbeitgeberstandorte). Orte, die zugleich normale Wörter sind, entfernen auch diese Wörter. Koordinaten ohne Bezeichner und Himmelsrichtung mit weniger als fünf Nachkommastellen oder in ungewöhnlichen Formaten (UTM, Geohash, Plus Codes) werden nicht erkannt. Koordinaten in Bild-Metadaten entfernt scrub_pdf_metadata/imaging_utils; dieses Modul betrifft sichtbaren und gesendeten Text.

## Aufruf

```bash
from modules.location_redaction import redact_locations
redact_locations("Aufnahme bei 48.13514, 11.58198 in Musterstadt", extra_places=["Musterstadt"])
```
