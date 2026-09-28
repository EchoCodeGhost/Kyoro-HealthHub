# identity_resolver.py — Zentrales Identifier-Pseudonym-Resolver-Modul

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/identity_resolver.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Zentralisierte Pseudonym-Auflösung für Geräte- und Personen-Identifikatoren. Erweitert das bestehende Seriennummern-Pseudonymisierungsmuster auf device_id und person. Einziger Zugriffspunkt für alle Identitätsauflösungen.

## Relevanz

Bietet Identitätsauflösungsfunktionen, essentiell für die Datenintegration

## Methode

Deterministische SHA-256-basierte Pseudonym-Generierung mit Präfixen: - DEV-XXXXXXXX für Geräte-IDs - PER-XXXXXXXX für Personen-IDs Der Hash wird mit einem zufälligen, einmalig erzeugten, lokal in identity.db gespeicherten Salt kombiniert (salt:kind:real_value). Ohne Salt wären device_id/person Wörterbuch-Angriffen ausgesetzt: beide Spalten haben extrem geringe Kardinalität (ein paar Dutzend bekannte Gerätemodell-Strings, 'self'/'partner'), sodass ein unsalted Hash von jedem mit Zugriff auf health.db (explizit auch ein extern angebundenes KI-Tool, siehe proposal.md) durch simples Durchprobieren aller bekannten Kandidatenwerte gebrochen werden könnte — genau die Bedrohung, die dieser Change verhindern soll. Speichert Zuordnungen in ~/.config/kyoro/identity.db und bietet Vorwärts- (real→pseudo) und Rückwärtsauflösung (pseudo→real) sowie menschenlesbare Anzeigenamen für Reports.

## Datenfluss

- **Liest:** `~/.config/kyoro/identity.db`, `(device_id_map`, `person_map`, `device_serial_map)`, `~/.config/kyoro/registry.json`, `(für`, `sensor_type`, `Lookup`, `in`, `resolve_display_name)`
- **Schreibt:** `~/.config/kyoro/identity.db (neue Einträge in device_id_map, person_map)`

## Grenzen

Nur lokale Auflösung; keine Netzwerkzugriffe. Pseudonyme sind deterministisch aber nicht kryptografisch sicher — für Datenschutz, nicht für Sicherheit ausgelegt.

## Aufruf

```bash
from modules.identity_resolver import resolve_device, resolve_person, reverse_resolve, resolve_display_name
dev_pseudo = resolve_device("polar_v3")  # -> "DEV-8abb425f"
person_pseudo = resolve_person("self")   # -> "PER-6173fec1"
real_value = reverse_resolve(dev_pseudo) # -> "polar_v3"
display_name = resolve_display_name(dev_pseudo) # -> "polar_v3 (optical_wrist_gps)"
```
