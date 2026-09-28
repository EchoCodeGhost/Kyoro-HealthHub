# pseudonymize_device_person_identifiers.py — Geräte-/Personen-Identifier pseudonymisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/pseudonymize_device_person_identifiers.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Aktualisiert bestehende semantische device_id- und person-Werte in health.db und medicine.db auf ihre Pseudonym-Äquivalente. Folgt dem Muster von pseudonymize_polar_device_serials.py, behandelt aber sowohl Geräte- als auch Personen-Identifikatoren.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

1. Öffnet health.db/medicine.db über modules.db.open_db()/open_medicine_db() (respektiert konfigurierten Pfad + SQLCipher-Verschlüsselung — NIE einen hartkodierten Dateinamen verwenden, siehe Lektion unten). 2. Findet alle Tabellen mit device_id/device/person-Spalten. 3. Für Spalten, die Teil des Primärschlüssels sind (z.B. ppi_raw (datetime, pulse_ms, device, person)): vor dem UPDATE wird per NOT EXISTS auf exakte Duplikate unter dem Ziel-Pseudonym geprüft (Muster: pseudonymize_polar_device_serials.py). Gefundene Duplikate werden gelöscht, keine anderen Zeilen. Für Spalten, die selbst der gesamte Primärschlüssel sind (z.B. devices.device_id): eine Kollision hieße echte Hash-Kollision, nicht Duplikat-Import — wird gemeldet und abgebrochen, nie automatisch aufgelöst. 4. Commit pro Tabelle (nicht eine große Transaktion über alle Tabellen), damit ein Fehler in einer späteren Tabelle nicht bereits committete Tabellen zurückrollt. 5. Verifikation über die GESAMTE Zeilenzahl der Tabelle vor/nach (abzüglich gemeldeter Duplikat-Löschungen) — ein reiner UPDATE kann die Zahl nicht-NULL-Werte einer Spalte nie ändern, das wäre keine echte Verifikation.

## Datenfluss

- **Liest:** `health.db`, `medicine.db`, `(alle`, `Tabellen`, `mit`, `Zielspalten`, `über`, `Config-Pfad)`, `~/.config/kyoro/identity.db`, `(für`, `Pseudonym-Lookup)`
- **Schreibt:** `health.db, medicine.db (aktualisierte device_id/device/person Werte)`

## Grenzen

Nur semantische Werte werden ersetzt; bestehende Pseudonyme bleiben unverändert. Keine automatische Schema-Anpassung — Zielspalten müssen bereits existieren. Erstellt KEIN Backup selbst — das ist Aufgabe 4.1 (separat, vor diesem Skript auszuführen).

## Aufruf

```bash
python3 scripts/migrations/pseudonymize_device_person_identifiers.py --dry-run
python3 scripts/migrations/pseudonymize_device_person_identifiers.py --execute
python3 scripts/migrations/pseudonymize_device_person_identifiers.py --database health --execute
```
