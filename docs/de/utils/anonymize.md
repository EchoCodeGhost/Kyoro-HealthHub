# anonymize — Zentrale Anonymisierungs- und Pseudonymisierungs-Hilfsfunktionen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/anonymize.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Zentrales Modul für alle Anonymisierungs- und Pseudonymisierungsfunktionen. Alle Funktionen, die extern übertragene oder gespeicherte Standort- oder Identitätsdaten berühren, sollten dieses Modul verwenden, um eine zentrale Stelle für Anpassungen von Präzision oder Scrubbing-Regeln zu haben.

## Relevanz

Ermöglicht die Anonymisierung von Gesundheitsdaten, essentiell für den Datenschutz und die Einhaltung von Compliance-Anforderungen

## Methode

Bietet Funktionen für: GPS-Koordinaten-Rundung (Standard: 2 Dezimalstellen ≈ 1,1 km Raster), Geräte-Seriennummern-Pseudonymisierung (SN-XXXXXXXX Format mit SHA-256 Hash in identity.db), E-Mail-Adressen-Ersetzung, Telefon/Fax-Nummern-Erkennung und Pseudonymisierung, Versicherungsnummern und -namen Pseudonymisierung, Geburtsdaten-Ersetzung, Namen-Pseudonymisierung (Vorname, Nachname), Adressen- und Stadtnamen-Ersetzung, Compliance-Checks für die Datenbank, Apple Health sourceName-Bereinigung und HealthKit <Me> Attribut-Scrubbing. Speichert alle Pseudonymisierungen in einer separaten identity.db für Konsistenz.

## Datenfluss

- **Liest:** `identity.db.device_serial_map`
- **Schreibt:** `identity.db.device_serial_map`

## Grenzen

GPS-Präzision auf 2 Dezimalstellen begrenzt (ca. 1,1 km Genauigkeit) - kann bei Bedarf angepasst werden. Pseudonymisierung ist deterministisch (gleiche Eingabe → gleiche Ausgabe) aber nicht umkehrbar. Identitätsdatenbank (identity.db) wird mit restriktiven Berechtigungen (600) angelegt. Compliance-Checks können falsch-positive Ergebnisse liefern, die manuelle Überprüfung erfordern.

## Aufruf

```bash
from utils.anonymize import round_coords, pseudonymize_device_serial, scrub_text_field
from utils.anonymize import check_anonymization_compliance, print_compliance_report
# GPS-Koordinaten rundet
lat_rounded, lon_rounded = round_coords(52.5200, 13.4050)
# Geräte-Seriennummer pseudonymisieren
pseudo = pseudonymize_device_serial('ABC123XYZ', 'polar_m430')
# Compliance-Check durchführen
issues = check_anonymization_compliance('data/health.db')
print_compliance_report(issues)
```
