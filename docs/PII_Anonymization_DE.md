# PII-Anonymisierungsinfrastruktur - Dokumentation

> **English version:** [PII_Anonymization.md](PII_Anonymization.md)

## Übersicht

Dieses Dokument beschreibt die umfassende PII (Personally Identifiable Information)-Anonymisierungsinfrastruktur für Gesundheitsdaten. Die Infrastruktur bietet Tools und Funktionen zum Erkennen, Pseudonymisieren und Entfernen sensibler personenbezogener Daten aus Gesundheitsdatenbanken.

### Abgrenzung zu anderen Privacy-Tools

Diese Infrastruktur befasst sich mit PII in **Datenbankinhalten** (Freitext aus importierten Dokumenten, Namen/Adressen/Kontaktdaten). Zwei separate, ebenfalls zentrale Tools decken andere Ebenen ab und sind nicht Teil dieses Dokuments:

- **`scripts/utils/check_source_privacy.py`** prüft den **Quellcode** des Repos (nicht die Datenbank) auf verbotene Identifier-Fragmente aus `privacy_check.forbidden_identifiers` — durchsetzt die Regeln in [`PRIVACY_ARCHITECTURE.md`](PRIVACY_ARCHITECTURE.md) und CLAUDE.md § "Privacy rules". Verpflichtend vor jedem Merge (`check_anonymization.py --source-only` ruft denselben Mechanismus aus dieser Datei auf).
- **`scripts/check_compliance.py`** verwaltet eine Review-Warteschlange für neu erkannte Verstöße (siehe `compliance_baseline.json`) — Teil der in `docs/CONTRIBUTING.md` beschriebenen Pre-PR-Checks.
- Die Geräte-/Personen-Pseudonymisierung selbst (`DEV-XXXXXXXX`/`PER-XXXXXXXX`, `identity_resolver`-Modul, DB-Trigger) ist in [`PRIVACY_ARCHITECTURE.md`](PRIVACY_ARCHITECTURE.md) dokumentiert — `pseudonymize_existing_devices.py` (unten) ist ein Migrationswerkzeug für Altdaten in diesem System, keine eigenständige Architektur.

## Architektur

### Kernmodule

1. **`utils/anonymize.py`** - Kernfunktionen für Pseudonymisierung
2. **`utils/check_anonymization.py`** - Compliance-Prüfung
3. **`utils/scrub_pii.py`** - Umfassende PII-Bereinigung
4. **`utils/scrub_emails.py`** - E-Mail-spezifische Bereinigung
5. **`utils/pseudonymize_existing_devices.py`** - Geräte-Pseudonymisierung

### Datenflüsse

```
Health-Daten → [Compliance-Check] → [PII-Erkennung] → [Pseudonymisierung] → Anonymisierte Daten
                       ↑
                   [Backup]
                       ↑
                   [Protokollierung]
```

## PII-Kategorien

### Erkannt und pseudonymisiert

| Kategorie | Beispiele | Pseudonymisierungsmuster |
|-----------|----------|------------------------|
| **E-Mail-Adressen** | `max.mustermann@example.com` | `user-XXXXXX@example.com` |
| **Telefonnummern** | `089/12345678` | `[TELEFON-XXXXXX]` |
| **Faxnummern** | `Fax: 030-98765432` | `Fax: [FAX-XXXXXX]` |
| **IP-Adressen** | `192.168.1.1` | `[IP-ENTFERNT]` |
| **Vollständige Namen** | `Max Mustermann` | `[NAME-ENTFERNT]` |
| **Vornamen** | `Max`, `Sandra` | `Vorname-XXXXXX` |
| **Nachnamen** | `Müller`, `Schmidt` | `Nachname-XXXXXX` |
| **Arzttitel + Namen** | `Dr. med. Müller` | `Arzt-XXXXXX` |
| **MVZ-Namen** | `MVZ München` | `MVZ-XXXXXX` |
| **PLZ** | `80331` | `PLZ-XXXXX` |
| **Straßennamen** | `Hauptstraße` | `[STRASSE-ENTFERNT]` |
| **Stadtnamen** | `München` | `[STADT-ENTFERNT]` |
| **Versicherungsnummern** | `123456789` | `INS-XXXXXX` |
| **Krankenkassen** | `AOK`, `TK` | `Krankenkasse` |
| **Geburtsdaten** | `15.05.1985` | `Alter: 38` |

### Erhalten (nicht pseudonymisiert)

- **Geschlecht**: `männlich`, `weiblich`, `divers`
- **Alter**: `38 Jahre`
- **Notrufnummern**: `112`
- **Medizinisch relevante Informationen**

## Tools und ihre Verwendung

### 1. Compliance-Check

**Zweck**: Überprüft die Datenbank auf PII-Verstöße

**Verwendung**:
```bash
python3 scripts/utils/check_anonymization.py
```

**Optionen**:
- `--db PATH`: Pfad zur Datenbank
- `--show-mappings`: Zeigt Geräte-Pseudonymisierungs-Mappings
- `--json`: JSON-Ausgabe für automatische Verarbeitung

**Beispielausgabe**:
```
=== Anonymisierungs-Compliance-Bericht ===
✅ Keine Probleme gefunden - Alle Daten sind korrekt anonymisiert!

⚠️  5 potenzielle Probleme gefunden:
  🚫 E-Mail-Adressen gefunden: 2
  🚫 Versicherungsdaten gefunden: 1
  🚫 Geburtsdaten gefunden: 3
  🚫 Nicht-pseudonymisierte Geräte: 1
  🚫 GPS mit hoher Präzision: 42277
```

### 2. Umfassende PII-Bereinigung

**Zweck**: Pseudonymisiert alle PII-Daten in der Datenbank

**Verwendung**:
```bash
python3 scripts/utils/scrub_pii.py [--dry-run] [--remove-all]
```

**Optionen**:
- `--dry-run`: Zeigt Änderungen ohne Durchführung
- `--remove-all`: Entfernt PII komplett (keine Pseudonymisierung)

**Beispiel**:
```bash
# Dry-Run (sicherer Test)
python3 scripts/utils/scrub_pii.py --dry-run

# Echte Bereinigung
python3 scripts/utils/scrub_pii.py
```

### 3. E-Mail-Bereinigung

**Zweck**: Spezifisch für E-Mail-Adressen

**Verwendung**:
```bash
python3 scripts/utils/scrub_emails.py [--dry-run] [--remove]
```

### 4. Geräte-Pseudonymisierung

**Zweck**: Pseudonymisiert Geräte-Seriennummern

**Verwendung**:
```bash
python3 scripts/utils/pseudonymize_existing_devices.py [--dry-run]
```

### 5. GPS-Präzisionsreduzierung

**Zweck**: Rundet nachträglich zu hochauflösende GPS-Punkte in `session_tracks` (>5 Nachkommastellen)
auf 5 Nachkommastellen (~1,1 m Raster) herab — für Altdaten, die vor Einführung des
automatischen Roundings importiert wurden. Neue Track-Importe runden bereits beim Schreiben
via `round_coords()` aus `utils/anonymize.py` (siehe `import_tracks.py`).

**Verwendung**:
```bash
python3 scripts/utils/reduce_gps_precision.py --dry-run
python3 scripts/utils/reduce_gps_precision.py
```

## Pseudonymisierungsfunktionen

### Einzelne Funktionen

```python
from utils.anonymize import (
    pseudonymize_email,
    pseudonymize_first_name,
    pseudonymize_last_name,
    pseudonymize_arzt_name,
    pseudonymize_mvz_name,
    pseudonymize_zip_code,
    pseudonymize_insurance_number,
    pseudonymize_birthdate
)

# Beispiele
print(pseudonymize_email("max@example.com"))  # user-ABC123@example.com
print(pseudonymize_first_name("Max"))        # Vorname-ABC123
print(pseudonymize_last_name("Müller"))      # Nachname-ABC123
print(pseudonymize_arzt_name("Dr. Müller"))  # Arzt-ABC123
print(pseudonymize_mvz_name("MVZ München")) # MVZ-ABC123
print(pseudonymize_zip_code("80331"))        # PLZ-ABC12
print(pseudonymize_insurance_number("123456789")) # INS-ABC123
print(pseudonymize_birthdate("15.05.1985"))  # Alter: 38
```

## Best Practices

### 1. Regelmäßige Compliance-Checks

Führen Sie nach jedem Datenimport einen Compliance-Check durch:
```bash
python3 scripts/utils/check_anonymization.py
```

### 2. Backup vor Änderungen

Alle Bereinigungstools erstellen automatisch Backups. Bewahren Sie diese für Audit-Zwecke auf.

### 3. Dry-Run für neue Tools

Testen Sie neue Tools immer zuerst im Dry-Run-Modus:
```bash
python3 scripts/utils/scrub_pii.py --dry-run
```

### 4. Geschlecht und Alter erhalten

Verwenden Sie immer `preserve_gender_age=True`, um medizinisch relevante Informationen zu bewahren:
```python
scrub_sensitive_health_data(text, preserve_gender_age=True)
```

### 5. Protokollierung

Alle Änderungen werden automatisch in der `import_log`-Tabelle protokolliert.

## Datenschutzkonzept

### Pseudonymisierungsstrategie

- **Deterministisch**: Gleiche Eingabe → gleiches Pseudonym (SHA-256)
- **Konsistent**: Über alle Tools und Importe hinweg
- **Irreversibel**: Keine Rückführung auf Originaldaten möglich
- **Auditierbar**: Alle Änderungen werden protokolliert

### Datenkategorien

| Kategorie | Strategie | Beispiel |
|-----------|-----------|----------|
| **Identifizierende Daten** | Vollständige Pseudonymisierung | Namen, Adressen, Telefonnummern |
| **Medizinisch relevant** | Erhalten | Geschlecht, Alter, Diagnosen |
| **Technische Daten** | Teilweise Pseudonymisierung | Geräte-Seriennummern (SN-XXXX) |
| **Geodaten** | Präzisionsreduzierung | GPS auf ~1m, PLZ auf Stadt-Ebene |

### Compliance

- **DSGVO**: Artikel 25 (Datenschutz durch Technikgestaltung)
- **BDSG**: §§ 64 ff. (Pseudonymisierung)
- **Krankenhausgesetze**: Landesrechtliche Vorgaben
- **ISO 27001**: Informationssicherheitsmanagement

## Fehlerbehebung

### Häufige Probleme

**Problem**: Falsche Positivmeldungen bei Namen
**Lösung**: Passen Sie die `get_common_german_first_names()` und `get_common_german_last_names()` Listen an

**Problem**: Telefonnummern werden nicht erkannt
**Lösung**: Verwenden Sie das Format `Tel: 089/12345678` oder `Telefon: 089-12345678`

**Problem**: E-Mail-Adressen in JSON-Daten
**Lösung**: Parsen Sie JSON zuerst, dann bereinigen Sie die Textfelder

### Debugging

```python
# Detaillierte PII-Erkennung testen
from utils.scrub_pii import find_pii_in_database
from modules.db import open_db

conn = open_db()
pii_data = find_pii_in_database(conn)
for item in pii_data:
    print(f"Table: {item[0]}.{item[1]}, Types: {item[4]}, Text: {item[3]}")
conn.close()
```

## Wartung

### Listen aktualisieren

Erweitern Sie die Listen in `utils/anonymize.py`:

```python
def get_common_german_first_names() -> list[str]:
    return [
        # Aktuelle Liste
        'Max', 'Leon', 'Ben',  # Neue Namen hinzufügen
    ]
```

### Neue PII-Kategorien hinzufügen

1. Neue Pseudonymisierungsfunktion erstellen
2. Muster in `scrub_pii.py` hinzufügen
3. Compliance-Check in `check_anonymization.py` erweitern

## Beispiel-Workflows

### Workflow 1: Neue Daten importieren

```bash
# 1. Daten importieren (z.B. Garmin)
python3 scripts/importers/import_garmin.py

# 2. Compliance prüfen
python3 scripts/utils/check_anonymization.py

# 3. Bei Problemen bereinigen
python3 scripts/utils/scrub_pii.py

# 4. Erneut prüfen
python3 scripts/utils/check_anonymization.py
```

### Workflow 2: Bestehende Daten bereinigen

```bash
# 1. Compliance-Status prüfen
python3 scripts/utils/check_anonymization.py

# 2. Spezifische Tools für gefundene Probleme:
#    - GPS: python3 scripts/utils/reduce_gps_precision.py
#    - Geräte: python3 scripts/utils/pseudonymize_existing_devices.py
#    - E-Mails: python3 scripts/utils/scrub_emails.py
#    - Alle PII: python3 scripts/utils/scrub_pii.py

# 3. Finaler Check
python3 scripts/utils/check_anonymization.py
```

## Zusammenfassung

Diese Dokumentation beschreibt die umfassende PII-Anonymisierungsinfrastruktur, die:

- ✅ **Alle PII-Kategorien** erkennt und pseudonymisiert
- ✅ **Medizinisch relevante Daten** (Geschlecht, Alter) erhält
- ✅ **Deterministische Pseudonymisierung** für Konsistenz bietet
- ✅ **Compliance-Checks** für regelmäßige Überprüfung bereitstellt
- ✅ **Sichere Tools** mit Backup und Protokollierung umfasst

Die Infrastruktur ist **produktionsbereit** und bietet umfassenden Datenschutz für Gesundheitsdaten gemäß DSGVO und anderen Vorschriften.
