#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Klartext-Geräte-IDs nachträglich pseudonymisieren bzw. deduplizieren

@tier        infrastructure
@purpose.de  Räumt Zeilen auf, die trotz des Pseudonymisierungs-Triggers eine
             Klartext-Geräte-ID tragen. Solche Zeilen entstanden, solange der
             Trigger unter INSERT OR IGNORE stillschweigend wirkungslos blieb
             (behoben in modules/db.py) — sie legen das Geräte-Inventar offen
             und verdoppeln zugleich die betroffenen Messungen.
@purpose.en  Cleans up rows that carry a plaintext device id despite the
             pseudonymisation trigger. Such rows accumulated while the trigger
             was silently ineffective under INSERT OR IGNORE (fixed in
             modules/db.py) — they expose the device inventory and duplicate
             the affected measurements at the same time.
@method.de   Spiegelt die Trigger-Logik mengenweise: erst UPDATE OR IGNORE auf
             das Pseudonym; wo das am Primärschlüssel scheitert, existiert die
             pseudonymisierte Zeile bereits und die Klartext-Zeile ist ein
             Duplikat — sie wird gelöscht. Geräte, die sich NICHT auflösen
             lassen (pseudonymize_* gibt den Eingabewert zurück), bleiben
             unangetastet; ein Löschen wäre dort Datenverlust statt
             Deduplizierung.
@method.en   Mirrors the trigger logic set-wise: first UPDATE OR IGNORE to the
             pseudonym; where that fails on the primary key, the pseudonymised
             row already exists and the plaintext row is a duplicate — it gets
             deleted. Devices that do NOT resolve (pseudonymize_* returns its
             input) are left untouched; deleting those would be data loss
             rather than deduplication.
@reads       health.db (alle Tabellen mit device_id/device-Spalte)
@writes      health.db (device_id-Spalten, Löschung von Duplikat-Zeilen)
@relevance.de  Das Geräte-Inventar gilt in diesem Projekt als schützenswert
               (docs/PRIVACY_ARCHITECTURE.md). Klartext-Modellnamen neben
               pseudonymisierten IDs unterlaufen genau diesen Schutz.
@relevance.en  The device inventory is treated as sensitive in this project
               (docs/PRIVACY_ARCHITECTURE.md). Plaintext model names next to
               pseudonymised ids undermine exactly that protection.
@limits.de   Setzt voraus, dass identity.db erreichbar ist — ohne Mapping wird
             nichts geändert. Nicht auflösbare Geräte bleiben im Klartext
             stehen und werden am Ende gemeldet, damit sie nicht unbemerkt
             bleiben.
@limits.en   Requires identity.db to be reachable — without a mapping nothing
             is changed. Unresolvable devices remain in plaintext and are
             reported at the end so they do not pass unnoticed.
@usage
    python3 scripts/migrations/dedupe_plaintext_device_ids.py --dry-run
    python3 scripts/migrations/dedupe_plaintext_device_ids.py

Exit Codes:
    0: Lauf erfolgreich (auch wenn nichts zu tun war)
    1: Fehler beim Datenbankzugriff
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.base import log_import  # noqa: E402
from modules.db import open_db  # noqa: E402

DEVICE_COLUMNS = ("device_id", "device")


def _targets(conn) -> list[tuple[str, str]]:
    """(Tabelle, Spalte) für jede Tabelle mit einer Geräte-Spalte."""
    out = []
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for table in tables:
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        for col in DEVICE_COLUMNS:
            if col in cols:
                out.append((table, col))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Pseudonymisiert bzw. dedupliziert Klartext-Geräte-IDs")
    ap.add_argument("--dry-run", action="store_true",
                    help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    plain = "{c} NOT LIKE 'DEV-%' AND {c} NOT LIKE 'PER-%' AND {c} IS NOT NULL"
    total_upd = total_del = 0
    unresolved: dict[str, int] = {}

    for table, col in _targets(conn):
        cond = plain.format(c=col)
        before = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {cond}').fetchone()[0]
        if not before:
            continue

        # Nicht aufloesbare Geraete getrennt erfassen — sie bleiben stehen.
        for dev, n in conn.execute(
                f'SELECT {col}, COUNT(*) FROM "{table}" WHERE {cond} '
                f'AND pseudonymize_device({col}) = {col} GROUP BY 1'):
            unresolved[str(dev)] = unresolved.get(str(dev), 0) + n

        if args.dry_run:
            resolvable = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE {cond} '
                f'AND pseudonymize_device({col}) <> {col}').fetchone()[0]
            print(f"  {table}.{col}: {before} Klartext-Zeilen, davon {resolvable} auflösbar")
            continue

        conn.execute(f'UPDATE OR IGNORE "{table}" SET {col} = pseudonymize_device({col}) '
                     f'WHERE {cond}')
        after_update = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {cond}').fetchone()[0]
        # Was jetzt noch Klartext ist und ein Pseudonym haette, ist ein Duplikat.
        cur = conn.execute(f'DELETE FROM "{table}" WHERE {cond} '
                           f'AND pseudonymize_device({col}) <> {col}')
        deleted = cur.rowcount or 0
        updated = before - after_update
        total_upd += updated
        total_del += deleted
        if updated or deleted:
            print(f"  {table}.{col}: {updated} pseudonymisiert, {deleted} Duplikate gelöscht")

    if not args.dry_run:
        # person=None explizit, nicht weggelassen: dieses Skript normalisiert
        # device_id/device-Spalten systemweit ueber ALLE Personen, kein
        # Einzelziel — OWN_PERSON_ID einzutragen waere hier falsch, s.
        # add-provenance-logging design.md.
        log_import(conn, "dedupe_plaintext_device_ids", "device_id/device columns",
                   total_upd, total_del, person=None)
        conn.commit()
        print(f"\nGesamt: {total_upd} pseudonymisiert, {total_del} Duplikate gelöscht")

    if unresolved:
        print("\n⚠ Nicht auflösbar (unverändert gelassen — kein Mapping in identity.db):")
        for dev, n in sorted(unresolved.items(), key=lambda kv: -kv[1]):
            print(f"    {dev}: {n} Zeilen")

    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
