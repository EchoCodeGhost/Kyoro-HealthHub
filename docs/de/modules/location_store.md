# location_store.py — Zentrale GPS/Ortsdaten-Registrierung und Policy-Enforcement

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/location_store.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Zentrale Speicherung und Abfrage von GPS-Koordinaten und Ortsdaten. Implementiert die location-privacy-Policy aus location_privacy.json. Jede GPS-Koordinate wird nur hier gespeichert, nie in health.db oder medicine.db.

## Relevanz

Kernmodul für Ortsdaten-Privatsphäre, essentiell für alle Importer

## Methode

resolve_policy liefert die geltende Policy für einen Importer/Dateityp. record speichert einen Ort im Registry (mit Precision-Anwendung und Zonen). region_of liefert das Bundesland/Land für Koordinaten. location_token generiert deterministische Tokens für Zellen. for_prompt und filter_prompt_text setzen die Outbound-Regeln durch.

## Datenfluss

- **Liest:** `location.db`, `location_privacy.json`, `identity.db`, `(für`, `Salt)`
- **Schreibt:** `location.db (INSERT OR IGNORE)`

## Grenzen

Keine Speicherung ohne gültige Policy. Precision wird IMMER vor dem Schreiben angewendet und ist irreversibel. Keine echten Daten in Tests.

## Aufruf

```bash
from modules.location_store import resolve_policy, record, file_sha256
from modules.location_store import location_token, for_prompt, filter_prompt_text
from modules.location_store import for_external_api, get_caller_name
```
