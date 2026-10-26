#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
pseudonymize_providers.py — Arztpraxis- und Labornamen in der Datenbank pseudonymisieren

@tier        infrastructure
@purpose.de  Ersetzt echte Arztpraxis- und Labornamen in health.db und medicine.db durch stabile
             Pseudonyme (Labor-1A2B3C4D) und entfernt Postadressen aus
             Freitext-Spalten der Laborbefunde. Läuft vollständig lokal.
@purpose.en  Replaces real medical practice and laboratory names in health.db and medicine.db with
             stable pseudonyms (Labor-1A2B3C4D) and removes postal addresses from
             free-text columns of lab results. Runs entirely locally.
@method.de   Spalten laut Tabelle _SPECS (lab_manual.labor, lab_results.labor, …) werden Zeile
             für Zeile umgeschrieben. Das Pseudonym ist ein SHA-256-Kurzhash des normalisierten
             Namens, damit derselbe Name immer dasselbe Pseudonym bekommt. Die Zuordnung
             Pseudonym zu Klartext liegt nur in identity.db (provider_pseudonym_map), außerhalb
             der Gesundheitsdatenbank. Kollidiert ein umbenannter lab_manual-Schlüssel mit einer
             vorhandenen Zeile, bleibt die vorhandene Zeile bestehen. Bereits pseudonymisierte
             Werte werden übersprungen (idempotent).
@method.en   Columns listed in _SPECS (lab_manual.labor, lab_results.labor, …) are rewritten
             row by row. The pseudonym is a short SHA-256 hash of the normalised name so the
             same name always gets the same pseudonym. The pseudonym-to-cleartext mapping lives
             only in identity.db (provider_pseudonym_map), outside the health database. If a
             renamed lab_manual key collides with an existing row the existing row is kept.
             Already pseudonymised values are skipped (idempotent).
@reads       health.db, medicine.db (Tabellen aus _SPECS, sofern vorhanden)
@writes      health.db, medicine.db, identity.db (provider_pseudonym_map)
@limits.de   Nur die Spalten aus _SPECS. Arztpraxis- oder Labornamen in beliebigem Freitext werden
             nicht erkannt. Die Pseudonymisierung ist nicht umkehrbar ohne identity.db;
             wer identity.db verliert, kann Pseudonyme nicht mehr auflösen. Eine bereits
             exportierte oder gesicherte Datenbank bleibt unverändert.
@relevance.de  Verhindert, dass Arztpraxis- und Labornamen oder Adressen im Datenbestand
               stehen, der exportiert oder an externe Dienste gegeben wird
@relevance.en  Prevents medical practice and laboratory names or addresses from sitting in the
               data that is exported or passed to external services
@limits.en   Only the columns in _SPECS. Practice or lab names in arbitrary free text are not
             detected. Pseudonymisation is not reversible without identity.db; losing
             identity.db means pseudonyms can no longer be resolved. A database that was
             already exported or backed up is not changed.
@usage
    python -m utils.pseudonymize_providers --dry-run
    python -m utils.pseudonymize_providers
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.address_redaction import redact_addresses
from utils.anonymize import pseudonymize_provider

_PSEUDO_RE = re.compile(r"^(?:Praxis|Labor)-[0-9A-F]{8}$")

# (Tabelle, Spalte, Art) — Namensspalten
_SPECS: list[tuple[str, str, str]] = [
    ("lab_manual", "labor", "Labor"),
    ("lab_results", "labor", "Labor"),
    ("lab_results", "praxis", "Praxis"),
]

# (Tabelle, Spalte) — Freitext, aus dem nur Adressen entfernt werden
_TEXT_SPECS: list[tuple[str, str]] = [
    ("lab_manual", "kommentar"),
    ("lab_results", "hinweis"),
    ("lab_results", "ref_text"),
    ("lab_results", "observations"),
]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    except sqlite3.DatabaseError:
        return []


def _pk_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})") if r[5]}


def process(conn: sqlite3.Connection, dry_run: bool = False) -> dict[str, int]:
    """Verarbeitet eine geöffnete Datenbank. Gibt Zähler je Aktion zurück."""
    stats = {"names": 0, "texts": 0}
    for table, column, kind in _SPECS:
        if column not in _columns(conn, table):
            continue
        pk = column in _pk_columns(conn, table)
        rows = conn.execute(
            f"SELECT rowid, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != ''"
        ).fetchall()
        for rowid, value in rows:
            if _PSEUDO_RE.match(value.strip()):
                continue
            stats["names"] += 1
            if dry_run:
                continue
            pseudo = pseudonymize_provider(value, kind)
            if pseudo == value:
                stats["names"] -= 1
                continue
            verb = "UPDATE OR IGNORE" if pk else "UPDATE"
            conn.execute(f"{verb} {table} SET {column} = ? WHERE rowid = ?", (pseudo, rowid))
            if pk:
                # Konflikt: Zeile mit dem Pseudonym existiert schon; Original-Zeile entfernen
                conn.execute(f"DELETE FROM {table} WHERE rowid = ? AND {column} = ?", (rowid, value))
    for table, column in _TEXT_SPECS:
        if column not in _columns(conn, table):
            continue
        for rowid, text in conn.execute(
            f"SELECT rowid, {column} FROM {table} WHERE {column} IS NOT NULL"
        ).fetchall():
            new = redact_addresses(text)
            if new != text:
                if not dry_run:
                    conn.execute(f"UPDATE {table} SET {column} = ? WHERE rowid = ?", (new, rowid))
                stats["texts"] += 1
    if not dry_run:
        conn.commit()
    return stats


def run_all(dry_run: bool = False) -> dict[str, dict[str, int]]:
    """Health- und Medizin-DB bearbeiten; fehlende Datenbanken werden übersprungen."""
    from modules.db import open_db, open_medicine_db
    from health_config import Config

    out: dict[str, dict[str, int]] = {}
    cfg = Config()
    for label, opener, path in (
        ("health.db", open_db, getattr(cfg, "db_path", None)),
        ("medicine.db", open_medicine_db, getattr(cfg, "medicine_db_path", None)),
    ):
        if path is not None and not Path(str(path)).exists():
            continue
        conn = opener()
        try:
            out[label] = process(conn, dry_run)
        finally:
            conn.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--dry-run", action="store_true", help="Nur zählen, nichts ändern")
    args = parser.parse_args()
    for label, stats in run_all(args.dry_run).items():
        prefix = "würde ändern" if args.dry_run else "geändert"
        print(f"{label}: {stats['names']} Name(n), {stats['texts']} Freitext-Feld(er) {prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
