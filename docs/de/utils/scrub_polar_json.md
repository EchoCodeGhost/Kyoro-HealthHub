# scrub_polar_json — PII aus Polar JSON-Rohdaten entfernen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/scrub_polar_json.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bereinigt Polar JSON-Rohdaten im imports/polar/ Verzeichnis von persönlich identifizierbaren Informationen. Ersetzt: echte Geräte-Seriennummern durch Pseudonyme (SN-XXXXXXXX), Polar Account-Owner-IDs durch Pseudo-UIDs (UID-XXXXXXXX). Entfernt: Name/E-Mail aus account-data Dateien, sensible Daten aus fitness-test. Benennt Dateinamen um, die die echte Owner-ID enthalten.

## Relevanz

Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz

## Methode

Lädt Pseudonymisierungs-Mappings aus identity.db (device_serial_map und account_pseudo_map). Verarbeitet alle JSON-Dateien im Polar-Verzeichnis rekursiv. Ersetzt Werte rekursiv in der JSON-Struktur. Entfernt spezifische Felder (account-data username/firstName/ lastName/email, sensitive fitness-test Felder). Benennt Dateien um, die echte IDs enthalten. Idempotent: bereits pseudonymisierte Werte bleiben unverändert. Dry-Run-Modus verfügbar.

## Datenfluss

- **Liest:** `imports/polar/*.json`, `identity.db.device_serial_map`, `identity.db.account_pseudo_map`
- **Schreibt:** `imports/polar/*.json (bereinigte Dateien und umbenannte Dateinamen)`

## Grenzen

Verarbeitet nur JSON-Dateien im angegebenen Polar-Verzeichnis. Ersetzt nur Werte, die in den Mappings gefunden werden.

## Aufruf

```bash
python -m utils.scrub_polar_json
python -m utils.scrub_polar_json --dry-run
python -m utils.scrub_polar_json --polar-dir /path/to/polar
# --dry-run: Zeigt Änderungen ohne sie durchzuführen
# --polar-dir: Pfad zum Polar-Import-Verzeichnis angeben
# Standard: imports/polar/
```
