# generate_pseudonyms_for_existing_data.py — Pseudonyme für bestehende Daten generieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/generate_pseudonyms_for_existing_data.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Durchsucht health.db und medicine.db nach allen eindeutigen Geräte- und Personen-Identifikatoren und generiert deterministische Pseudonyme dafür mithilfe des identity_resolver-Moduls. Reiner Backfill-Schritt (Aufgabe 4.2) — die eigentliche Datenmigration (Aufgabe 4.3, pseudonymize_device_person_identifiers.py) legt beim Auflösen ohnehin automatisch neue identity.db-Einträge an; dieses Skript erlaubt es, die Pseudonyme VOR der Migration einzusehen (z.B. für einen Report).

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

1. Liest alle eindeutigen Werte aus den Zielspalten — pro Spaltenname bekannt (device_id/device → Gerät, person → Person), KEINE Heuristik auf den Wert selbst (eine frühere Version riet anhand von Substrings wie 'polar'/'apple' im Wert, ob es ein Gerät oder eine Person ist — das kann bei unbekannten Gerätenamen falsch pseudonymisieren, ohne dass es auffällt). 2. Generiert Pseudonyme mit resolve_device() / resolve_person(). 3. Speichert die Zuordnungen in identity.db (Seiteneffekt von resolve()).

## Datenfluss

- **Liest:** `health.db`, `medicine.db`, `(über`, `Config-Pfad`, `alle`, `Tabellen`, `mit`, `device_id/device/person-Spalten)`
- **Schreibt:** `~/.config/kyoro/identity.db (device_id_map, person_map Tabellen)`

## Grenzen

Nur semantische Werte werden pseudonymisiert; bereits vorhandene Pseudonyme (DEV-*, PER-*) werden ignoriert.

## Aufruf

```bash
python3 scripts/migrations/generate_pseudonyms_for_existing_data.py
python3 migrations/generate_pseudonyms_for_existing_data.py  # from inside scripts/
```
