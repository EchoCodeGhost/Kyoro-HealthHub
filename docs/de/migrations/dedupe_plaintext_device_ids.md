# Klartext-Geräte-IDs nachträglich pseudonymisieren bzw. deduplizieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/dedupe_plaintext_device_ids.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Räumt Zeilen auf, die trotz des Pseudonymisierungs-Triggers eine Klartext-Geräte-ID tragen. Solche Zeilen entstanden, solange der Trigger unter INSERT OR IGNORE stillschweigend wirkungslos blieb (behoben in modules/db.py) — sie legen das Geräte-Inventar offen und verdoppeln zugleich die betroffenen Messungen.

## Relevanz

Das Geräte-Inventar gilt in diesem Projekt als schützenswert (docs/PRIVACY_ARCHITECTURE.md). Klartext-Modellnamen neben pseudonymisierten IDs unterlaufen genau diesen Schutz.

## Methode

Spiegelt die Trigger-Logik mengenweise: erst UPDATE OR IGNORE auf das Pseudonym; wo das am Primärschlüssel scheitert, existiert die pseudonymisierte Zeile bereits und die Klartext-Zeile ist ein Duplikat — sie wird gelöscht. Geräte, die sich NICHT auflösen lassen (pseudonymize_* gibt den Eingabewert zurück), bleiben unangetastet; ein Löschen wäre dort Datenverlust statt Deduplizierung.

## Datenfluss

- **Liest:** `health.db`, `(alle`, `Tabellen`, `mit`, `device_id/device-Spalte)`
- **Schreibt:** `health.db (device_id-Spalten, Löschung von Duplikat-Zeilen)`

## Grenzen

Setzt voraus, dass identity.db erreichbar ist — ohne Mapping wird nichts geändert. Nicht auflösbare Geräte bleiben im Klartext stehen und werden am Ende gemeldet, damit sie nicht unbemerkt bleiben.

## Aufruf

```bash
python3 scripts/migrations/dedupe_plaintext_device_ids.py --dry-run
python3 scripts/migrations/dedupe_plaintext_device_ids.py
```
