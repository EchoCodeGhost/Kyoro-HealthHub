#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
migrate_photo_locations_to_registry.py — Einmalige Migration von
health.db::photo_locations nach location.db

@tier        infrastructure
@purpose.de  Überführt bestehende photo_locations-Einträge in das Ortsregister
             (location.db) und entfernt sie danach aus health.db, damit dort
             keine Koordinaten zurückbleiben.
@purpose.en  Moves existing photo_locations rows into the location registry
             (location.db) and then removes them from health.db so that no
             coordinates remain there.
@method.de   Zeilen aus import_lab_results werden verworfen (Laborberichte
             speichern keinen Ort). Für alle anderen gilt die Policy aus
             location_privacy.json: erlaubt sie das Speichern, schreibt
             location_store.record() den Eintrag mit migrated_from=
             'photo_locations' (Quelldatei, Hashes, Verweis und ts bleiben
             NULL); sonst wird die Zeile verworfen. Mit --execute werden
             übernommene und verworfene Zeilen aus photo_locations gelöscht;
             Zeilen, deren Schreiben fehlschlug, bleiben stehen. Der
             Audit-Trigger wird für dieses Löschen umgangen, damit er die
             Koordinaten nicht nach audit_log kopiert; stattdessen ein
             Eintrag nur mit Anzahlen.
@method.en   Rows from import_lab_results are discarded (lab reports store no
             location). All others follow the policy in location_privacy.json:
             if it allows storage, location_store.record() writes the entry
             with migrated_from='photo_locations' (source file, hashes,
             reference and ts stay NULL); otherwise the row is discarded. With
             --execute, migrated and discarded rows are deleted from
             photo_locations; rows that failed to write are kept. The audit
             trigger is bypassed for this delete so that it does not copy
             the coordinates into audit_log; one count-only entry is written
             instead.
@reads       health.db::photo_locations, location_privacy.json
@writes      location.db::location_registry, health.db::photo_locations (DELETE),
             health.db::audit_log (ein Eintrag ohne Koordinaten)
@limits.de   Einmalig. Standard ist ein Trockenlauf, der nur Anzahlen nennt,
             nie Koordinaten.
@limits.en   One-off. Defaults to a dry run that reports counts only, never
             coordinates.

@relevance.de  Schließt Stufe 1 ab: photo_locations wird nicht mehr beschrieben
@relevance.en  Completes stage 1: photo_locations is no longer written
@usage
    # Trockenlauf (Standard)
    python3 scripts/migrations/migrate_photo_locations_to_registry.py
    # Ausführen
    python3 scripts/migrations/migrate_photo_locations_to_registry.py --execute
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import OWN_PERSON_ID  # noqa: E402
from modules.db import open_db  # noqa: E402
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402
from modules.location_store import record, resolve_policy  # noqa: E402

MIGRATION_MARKER = "photo_locations"
# Importer, deren Orte grundsätzlich verworfen werden (spec: lab-report PDFs)
DISCARD_SOURCES = {"import_lab_results"}


def _policy_allows_storage(importer: str) -> bool:
    policy = resolve_policy(importer, None)
    store = policy.get("store")
    if store in ("none", "region"):
        return False
    return store is not None or "precision" in policy


def _delete_without_coordinate_copies(conn, rowids: list[int], stats: Counter) -> None:
    """Löscht die Zeilen, ohne dass der Audit-Trigger ihre Koordinaten kopiert.

    Der DELETE-Trigger aus modules.db schreibt sonst jede gelöschte Zeile als
    JSON nach health.db::audit_log, die Koordinaten blieben also in
    health.db. Stattdessen ein Audit-Eintrag nur mit Anzahlen; der Trigger
    wird beim nächsten Öffnen der Datenbank wieder angelegt.
    """
    conn.execute("DROP TRIGGER IF EXISTS _audit_photo_locations_delete")
    conn.executemany("DELETE FROM photo_locations WHERE rowid = ?", [(r,) for r in rowids])
    has_audit = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone()
    if has_audit:
        conn.execute(
            "INSERT INTO audit_log (ts, table_name, operation, old_data, new_data) "
            "VALUES (strftime('%Y-%m-%dT%H:%M:%fZ','now'), 'photo_locations', 'DELETE', "
            "json_object('rows', ?, 'migrated', ?, 'discarded', ?, 'target', 'location.db'), NULL)",
            (len(rowids), stats["migrated"], stats["discarded"]),
        )
    conn.commit()


def migrate(execute: bool = False) -> Counter:
    """Führt die Migration aus (oder zählt nur, wenn execute False ist).

    Returns:
        Counter mit total, migrated, discarded, failed und je Quelle
        "source:<importer>"
    """
    stats: Counter = Counter()
    conn = open_db()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='photo_locations'"
        ).fetchone()
        if not exists:
            return stats
        rows = conn.execute(
            "SELECT rowid, date, lat, lon, source, person FROM photo_locations"
        ).fetchall()
        stats["total"] = len(rows)

        done_rowids = []
        for rowid, date_str, lat, lon, source, person in rows:
            stats[f"source:{source}"] += 1
            if source in DISCARD_SOURCES or not _policy_allows_storage(source):
                stats["discarded"] += 1
                done_rowids.append(rowid)
                continue
            if not execute:
                stats["migrated"] += 1
                continue
            ok = record(
                importer=source,
                file_type=None,
                lat=lat,
                lon=lon,
                ts=None,
                date=date_str,
                person=person if person and person != "unknown" else OWN_PERSON_ID,
                migrated_from=MIGRATION_MARKER,
            )
            if ok:
                stats["migrated"] += 1
                done_rowids.append(rowid)
            else:
                stats["failed"] += 1

        if execute and done_rowids:
            _delete_without_coordinate_copies(conn, done_rowids, stats)
    finally:
        conn.close()
    return stats


def main():
    ap = argparse.ArgumentParser(
        description=t("Überführt photo_locations aus health.db in location.db",
                      "Move photo_locations from health.db to location.db"))
    ap.add_argument("--execute", action="store_true",
                    help=t("Ausführen (ohne: nur Trockenlauf mit Anzahlen)",
                           "Execute (without: dry run with counts only)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    stats = migrate(execute=args.execute)
    if not stats["total"]:
        print(t("photo_locations ist leer oder fehlt – nichts zu tun.",
                "photo_locations is empty or missing – nothing to do."))
        return

    mode = t("AUSGEFÜHRT", "EXECUTED") if args.execute else t("TROCKENLAUF", "DRY RUN")
    print(f"{mode}: photo_locations → location.db")
    print(t(f"  Einträge gesamt:   {stats['total']}",
            f"  Rows total:        {stats['total']}"))
    for key in sorted(k for k in stats if k.startswith("source:")):
        print(f"    {key[len('source:'):]}: {stats[key]}")
    print(t(f"  übernommen:        {stats['migrated']}",
            f"  migrated:          {stats['migrated']}"))
    print(t(f"  verworfen:         {stats['discarded']}",
            f"  discarded:         {stats['discarded']}"))
    if args.execute:
        print(t(f"  fehlgeschlagen:    {stats['failed']} (bleiben in health.db)",
                f"  failed:            {stats['failed']} (kept in health.db)"))
    else:
        print(t("Nichts geschrieben. Mit --execute ausführen.",
                "Nothing written. Run with --execute."))


if __name__ == "__main__":
    main()
