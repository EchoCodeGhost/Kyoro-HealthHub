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
| **Vornamen** | `Max`, `Erika` | `Vorname-XXXXXX` |
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

### 4b. Medien-Scrubber (Bilder und PDFs, lokal)

**Zweck**: Meldet und entfernt Metadaten (EXIF inkl. GPS, PDF-Info/XMP, Anhänge, JavaScript)
und schwärzt Postadressen im sichtbaren Inhalt von Bildern und PDFs. Originale werden nie
überschrieben.

**Verwendung**:
```bash
python -m utils.scrub_media report befund.pdf foto.jpg [--show-values] [--json-out report.json]
python -m utils.scrub_media scrub befund.pdf sauber.pdf [--address "Musterstraße 12, 12345 Musterstadt"]
python -m utils.scrub_media scrub-dir eingang/ ausgang/ --strict
python -m utils.scrub_media check ordner/
```

Adress- und Namenserkennung sind heuristisch (`modules/address_redaction.py`, `modules/name_redaction.py`).
Namen werden mit Anrede/Titel (`Frau X`, `Dr. med. X`), Feldbezeichnern (`Name:`) oder aus den
bekannten Namen erkannt: `privacy_check.patient_names` in `health_config.json`, `person_name_map`
in `identity.db` und `--name`. Bekannte Adressen stehen unter `privacy_check.patient_addresses`.
Telefon-/Faxnummern (auch kurze Durchwahlen), Versichertennummern (Kranken- und Rentenversicherung),
Bankdaten (IBAN mit Prüfziffer, BIC, Kontonummer) und Kennnummern anderer Systeme (Patienten-, Fall-,
Auftrags-, Kassen- und Arztnummern sowie jede ungebrochene Ziffernfolge mit 7 bis 15 Ziffern ohne
Einheit) werden ebenfalls entfernt (`modules/identifier_redaction.py`). Mit `--no-redact-names`, `--no-redact-addresses`
oder `--no-redact-ids` lässt sich jedes davon abschalten.

GPS-Koordinaten im Text (Dezimalgrad, Grad/Minuten/Sekunden) und **persönliche Ortsnamen** werden
ebenfalls entfernt (`modules/location_redaction.py`, `--no-redact-places`). Ortsnamen kommen nur
aus deiner lokalen Konfiguration: `privacy_check.patient_places` in `health_config.json`, der Ort in
`privacy_check.patient_addresses` und `--place`. Ein allgemeines Ortsverzeichnis gibt es bewusst nicht,
damit Bundesländer, Länder, Reiseziele und Endemiegebiete für die Auswertung erhalten bleiben.
Koordinaten in Bild-Metadaten entfernt weiterhin das Metadaten-Scrubbing; die gerundeten
`photo_locations`-Einträge der Importer bleiben unverändert. Scans
werden per OCR geprüft (optional: `pytesseract` + `tesseract` mit Sprache `deu`; Textebene und
Rendering brauchen `poppler`). Betroffene PDF-Seiten werden durch Bildseiten ersetzt, sodass
keine Textebene zurückbleibt. Die PDF-Importer für Laborwerte und FibriCheck nutzen dieselbe
Funktion und fallen bei fehlenden Werkzeugen mit Warnung auf reine Metadaten-Bereinigung zurück.

### 4c. Praxis- und Labor-Pseudonymisierung

`post_import_sanitize` führt zusätzlich `utils/pseudonymize_providers.py` aus: Praxis- und
Labornamen (z. B. `lab_manual.labor`) werden zu stabilen Pseudonymen (`Labor-1A2B3C4D`); die
Zuordnung liegt nur in `identity.db` (`provider_pseudonym_map`). Postadressen werden aus
Laborfreitext entfernt. Probelauf: `python -m utils.pseudonymize_providers --dry-run`.

### 5. GPS-Präzisionsreduzierung

**Zweck**: Rundet nachträglich zu hochauflösende GPS-Punkte in `location.db::session_tracks`
(>5 Nachkommastellen) auf 5 Nachkommastellen (~1,1 m Raster) herab — für Altdaten, die vor
Einführung des automatischen Roundings importiert wurden. Neue Track-Importe runden bereits beim
Schreiben über `location_store.store_track_points()` (siehe Abschnitt 5c).

**Verwendung**:
```bash
python3 scripts/utils/reduce_gps_precision.py --dry-run
python3 scripts/utils/reduce_gps_precision.py
```

### 5b. Standort-Datenschutz und Vergröberung für externe Abfragen

**Zweck**: Steuert die Genauigkeit von Standortdaten, die an externe Dienste gesendet
werden, und speichert Regionsinformationen für die lokal-first-Analyse.

Kyoro-HealthHub verwendet `location_privacy.json`, um zu konfigurieren, wie
Standortdaten behandelt werden:

- **`external_api.precision`**: Standardgenauigkeit für Koordinaten, die an externe
  Dienste gesendet werden (Standard: 1 Dezimalstelle, ~11 km Raster). Niedrigere
  Werte = gröbere Genauigkeit.
- **`external_api.place_precision`**: Genauigkeit für die Rückwärtsgeokodierung von
  Ortsnamen (Standard: 2 Dezimalstellen, ~1 km). Wird verwendet, wenn
  `place=True` an `for_external_api()` übergeben wird.
- **`external_api.services`**: Opt-in-Flags für Dienste, die API-Schlüssel
  erfordern. Aktuell: `google_pollen` (Standard: `false`). Muss explizit
  aktiviert werden, um Standortdaten an Google zu senden.

**Regionsspeicherung**: Standorte werden mit ISO-3166-2-Regionscodes (weltweit)
über `region_of()` aus `location_store.py` gespeichert. Für Einheiten, die
kleiner als die gespeicherte Genauigkeitszelle sind, wird nur der
Ländercode gespeichert. Dies ermöglicht lokal-first-Analysen ohne das
Senden von Koordinaten an externe Dienste.

**Konfigurationsdatei**: `~/.config/kyoro/location_privacy.json` (wird von
`onboard.py` aus `templates/location_privacy.example.json` erstellt).

**Beispielkonfiguration**:
```json
{
  "external_api": {
    "precision": 1,
    "place_precision": 2,
    "services": {
      "google_pollen": false
    }
  }
}
```

### 5c. Ortsregister und externe KI-Anbieter

**Zweck**: Hält Orte, die Importer finden (zum Beispiel GPS-Angaben in
Fotos), an einer Stelle fest, mit einer Genauigkeit, die Sie je Importer
festlegen, und steuert, welche Orte an einen externen KI-Anbieter oder in
einen Export gelangen dürfen.

**Ortsregister (`location.db`)**: Importer schreiben Orte über
`location_store.record()` in die Tabelle `location_registry` in
`data/location.db` (Pfad: `paths.location_db`). Die Datenbank ist wie
`health.db` mit SQLCipher verschlüsselt, wenn `db_key` gesetzt ist. Jeder
Eintrag enthält Importer und Dateityp, die relative Quelldatei, den
SHA-256-Hash der Originaldatei (vor dem Entfernen der Metadaten) und der
abgelegten Datei (danach), Datum, die gerundeten Koordinaten, die
angewendete Genauigkeit, die ISO-3166-Region, einen Verweis auf den
zugehörigen Datensatz (zum Beispiel eine Zeile in `imaging_files`) und das
Personen-Pseudonym. Die Genauigkeit wird vor dem Schreiben angewendet und
lässt sich nicht rückgängig machen. Duplikate werden übersprungen
(`INSERT OR IGNORE`). Foto-Orte landen nicht mehr in
`health.db::photo_locations`; vorhandene Zeilen lassen sich mit
`scripts/migrations/migrate_photo_locations_to_registry.py` übertragen
(zuerst `--dry-run`).

Sport-Tracks, Aufenthalte und Standortverlauf (`session_tracks`,
`location_stays`, `location_stays_geocoded`, `location_history`) sind
ebenfalls Tabellen in `location.db`. Importer schreiben sie über
`location_store.store_track_points()`, `store_stays()` und
`store_location_history()`, die Einstellung und Privatsphäre-Zonen anwenden.
Skripte, die sie mit `health.db`-Tabellen verknüpfen, hängen `location.db`
als `loc` an (`modules.db.attach_location_db()`) und fragen
`loc.session_tracks` usw. ab. Installationen, bei denen diese Tabellen noch
in `health.db` liegen, ziehen sie mit
`scripts/migrations/migrate_location_tables_to_location_db.py` um:
standardmäßig Trockenlauf; `--execute` legt ein Backup an (oder prüft eines,
das mit `--backup` angegeben wird), kopiert die Zeilen unverändert, gleicht
jede Zeile und eine Prüfsumme ab, verschiebt die Audit-Log-Kopien dieser
Zeilen (sie enthalten Koordinaten) und löscht die Tabellen erst danach aus
`health.db`. `scripts/utils/check_location_columns.py` bestätigt, dass
`health.db` und `medicine.db` keine persönlichen Koordinaten enthalten;
Ausnahmen sind Umwelttabellen mit dem vergröberten Abfragepunkt als
Schlüssel (höchstens 2 Nachkommastellen) und Ausbruchsmeldungen
(öffentliche Orte).

**Einstellung je Importer und Dateityp** (`importers` und `default` in
`location_privacy.json`): Die Einstellung wird in der Reihenfolge Importer +
Dateityp → Importer `"*"` → `default` aufgelöst. Möglich sind:

- `precision` 0–5: Nachkommastellen von Breite/Länge (0 ≈ 111 km,
  1 ≈ 11 km, 2 ≈ 1,1 km, 3 ≈ 110 m, 4 ≈ 11 m, 5 ≈ 1 m)
- `store: "region"`: nur die ISO-3166-Region, keine Koordinaten
- `store: "none"`: es wird nichts gespeichert

Importer ohne Eintrag und eine fehlende `location_privacy.json` speichern
keinen Ort. Ein Foto-Ort wird nur mit echtem Aufnahmedatum gespeichert
(EXIF-Datum oder `--date`).

**Privatsphäre-Zonen** (`zones`), wie bei Strava: Mit `enabled` true werden
Punkte innerhalb von `radius_m` (Standard 500 m) um eine Zone nicht
gespeichert (`inside: "hide"`, Standard) oder mit `zone_precision`
gespeichert (`"coarsen"`). Das gilt nur für Importer, deren Genauigkeit
feiner als `zone_precision` ist (Standard 2, etwa 1 km).
Zonen-Mittelpunkte sind die Wohnposition (`location.lat`/`lon` in
`health_config.json`) und die Einträge in `zones.centres` (Koordinaten je
Ortsname: ein Ort aus `privacy_check.patient_places` über seinen Namen,
eine Adresse aus `privacy_check.patient_addresses` über die ganze Adresse
oder ihren Ort). Jeder Mittelpunkt wird fest um bis zu den halben Radius
verschoben, berechnet aus dem Salz in `identity.db`, damit der Rand, an dem
Tracks abgeschnitten werden, den Ort nicht verrät; der echte Mittelpunkt
liegt immer in der Zone. Konfigurierte Orte ohne Eintrag bekommen keine
Zone; jeder Lauf meldet, wie viele es sind, ohne Namen. Es gibt keine
Online-Geokodierung, und Zonen-Mittelpunkte werden nie gespeichert. Auf
Einträge, die vor dem Einrichten einer Zone gespeichert wurden, lassen sich
die Zonen mit `scripts/migrations/apply_privacy_zones.py` anwenden:
Registereinträge und Trackpunkte in einer Zone werden gelöscht (mit
`"coarsen"` vergröbert), Aufenthalte und Standortverlauf nur vergröbert,
nie gelöscht, damit Wohnzeiträume und die Wohnort-Erkennung erhalten
bleiben (standardmäßig Trockenlauf, `--execute` zum Ausführen;
unumkehrbar, es werden keine Koordinaten ins Audit-Log kopiert).

**Externe KI-Anbieter** (`llm`): Bevor ein Prompt an einen externen Anbieter
geht (`is_local` false), schickt `modules/llm.py::call_llm` Prompt und
Systemtext durch `location_store.filter_prompt_text()`. Die Stufe kommt aus
`llm.allow` für das aufrufende Skript (Skriptname ohne `.py` oder ein
ausdrückliches `caller=`), sonst aus `llm.default` (`none`):

| Stufe | Koordinaten im Text | Konfigurierte Ortsnamen |
|---|---|---|
| `none` (Standard) | entfernt | entfernt |
| `region` | entfernt | entfernt |
| N (0–5) | auf N Nachkommastellen gerundet | entfernt |
| `token` | durch ein Ort-Token ersetzt | entfernt |

Das Ort-Token ist ein HMAC der Rasterzelle mit dem Salz aus `identity.db`;
ohne Salz gibt es kein Token, und die Koordinaten werden entfernt. Skripte,
die Ortsdaten im Prompt brauchen, lesen sie über
`location_store.for_prompt()`, das dieselbe Freigabeliste anwendet. Bilder
werden vor dem Senden an einen externen Anbieter ohne Metadaten neu
kodiert; lässt sich ein Bild nicht bereinigen, wird es nicht gesendet.
Lokale Anbieter werden nicht gefiltert.

**Exporte** (`exports.allow`): `export_health.py` entfernt Ortsspalten, außer
das Exportprofil steht mit einer Stufe (`region` oder eine Genauigkeit) in
`exports.allow`.

**Beispiel**:
```json
{
  "default": {"store": "none"},
  "importers": {
    "import_skin": {"*": {"precision": 2}},
    "import_lab_results": {"*": {"store": "none"}}
  },
  "llm": {"default": "none", "allow": {"analyse_travel": "region"}},
  "exports": {"allow": {"travel_analysis": "region"}}
}
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
