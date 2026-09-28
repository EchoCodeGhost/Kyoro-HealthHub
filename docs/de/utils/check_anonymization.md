# check_anonymization — Anonymisierungs-Compliance-Check für health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_anonymization.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft die health.db-Datenbank auf Anonymisierungs-Compliance. Identifiziert potenzielle Probleme wie: echte Namen in person_ids, GPS-Daten mit zu hoher Präzision (>5 Dezimalstellen), nicht-pseudonymisierte Geräte-Seriennummern und Klartest-Account-Informationen.

## Relevanz

Bietet Prüfungsfunktionen für Datenqualität und Datenschutz, essentiell für die Datenintegrität

## Methode

Nutzt die Funktionen aus utils.anonymize (check_anonymization_compliance, print_compliance_report, get_all_device_mappings) für die Datenbankprüfung. Kann zusätzlich Source-Code UND Doku (.py/.md/.json, ganzes Repo) auf Privacy-Verstöße prüfen (Bezeichner, Hardcoding) durch Aufruf von check_source_privacy.scan_directory. Unterstützt verschiedene Ausgabemodi: normal, JSON und Geräte-Mappings-Anzeige. Exit-Code: 0 = sauber, 1 = Probleme gefunden.

## Datenfluss

- **Liest:** `health.db`, `(alle`, `Tabellen)`, `identity.db.device_serial_map`
- **Schreibt:** `stdout (Berichte und JSON-Ausgabe)`

## Grenzen

Prüft nur die in health_config.json konfigurierte Datenbank, falls --db nicht angegeben. Source-Code-Check kann falsch-positive Ergebnisse liefern (z.B. in t()-Aufrufen).

## Aufruf

```bash
python scripts/utils/check_anonymization.py
python scripts/utils/check_anonymization.py --db /path/to/health.db
python scripts/utils/check_anonymization.py --show-mappings
python scripts/utils/check_anonymization.py --source-code --strict
python scripts/utils/check_anonymization.py --json
# --db: Pfad zur Datenbank angeben
# --show-mappings: Zeige alle Geräte-Pseudonymisierungs-Mappings
# --source-code: Prüfe zusätzlich Source-Code auf Privacy-Verstöße
# --strict: Wertet auch low-confidence Findings als Fehler
# --json: Ausgabe als JSON für automatische Verarbeitung
```
