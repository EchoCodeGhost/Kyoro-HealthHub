#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
remove_example_lab_rows.py — Entfernt Zeilen aus der Beispieldatei aus lab_manual.

@tier        infrastructure
@purpose.de  Findet und löscht Laborzeilen, die aus templates/labor.example.csv stammen. Diese
             synthetischen Werte dürfen nie in Auswertungen oder Arztbriefe gelangen.
@purpose.en  Finds and deletes lab rows that come from templates/labor.example.csv. These
             synthetic values must never reach analyses or letters to doctors.
@method.de   Vergleicht Datum, Parameter und Wert mit der Beispieldatei statt mit dem Laborname,
             weil dieser pseudonymisiert wird. Prüft health.db und medicine.db. Ohne --yes wird
             nur gezählt. Die Audit-Trigger aus open_db halten jede gelöschte Zeile fest.
@method.en   Compares date, parameter and value with the example file rather than the lab name,
             because that gets pseudonymised. Checks health.db and medicine.db. Without --yes
             it only counts. The audit triggers from open_db record each deleted row.
@reads       templates/labor.example.csv, lab_manual in health.db und medicine.db
@writes      lab_manual (DELETE), audit_log, import_log
@limits.de   Ein echter Befund mit identischem Datum, Parameter und Wert würde mitgelöscht; die
             Ausgabe nennt daher die Zahl pro Datum, und bei Abweichung von der Beispieldatei
             bricht das Skript nicht ab, sondern zählt nur exakte Treffer.
@limits.en   A real result with an identical date, parameter and value would be deleted too, so
             the output lists the count per date. Only exact matches count.

@relevance.de  Verhindert, dass erfundene Laborwerte als echte Befunde gelten
@relevance.en  Prevents made-up lab values from counting as real results
@usage
    python3 scripts/migrations/remove_example_lab_rows.py        # nur zählen
    python3 scripts/migrations/remove_example_lab_rows.py --yes  # löschen
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import log_import
from modules.db import open_db, open_medicine_db
from modules.i18n import add_lang_arg, apply_lang_from_args, t

EXAMPLE_FILE = Path(__file__).resolve().parents[2] / "templates" / "labor.example.csv"


def load_example_rows(path: Path = EXAMPLE_FILE) -> set[tuple[str, str, str]]:
    """Liest (Datum, Parameter, Wert) aus der Beispieldatei; Kommentarzeilen zählen nicht."""
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(line for line in fh if not line.startswith("#"))
        return {(row["datum"].strip(), row["parameter"].strip(), row["wert"].strip()) for row in reader}


def find_rows(conn, example: set[tuple[str, str, str]]) -> list[int]:
    return [rowid for rowid, day, parameter, value in conn.execute(
                "SELECT rowid, date, parameter, wert FROM lab_manual")
            if (str(day).strip(), str(parameter).strip(), str(value).strip()) in example]


def remove_rows(conn, example: set[tuple[str, str, str]], apply: bool) -> Counter:
    """Gibt die Treffer pro Datum zurück und löscht sie nur mit apply."""
    rowids = find_rows(conn, example)
    placeholders = ",".join("?" * len(rowids))
    per_date = Counter(row[0] for row in conn.execute(
        f"SELECT date FROM lab_manual WHERE rowid IN ({placeholders})", rowids))
    if apply and rowids:
        conn.execute(f"DELETE FROM lab_manual WHERE rowid IN ({placeholders})", rowids)
        log_import(conn, "remove_example_lab_rows", "lab_manual", 0, len(rowids))
        conn.commit()
    return per_date


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Entfernt Zeilen aus der Beispieldatei aus lab_manual",
        "Removes rows from the example file from lab_manual"))
    parser.add_argument("--yes", action="store_true",
                        help=t("Wirklich löschen; ohne nur zählen", "Really delete; only count without it"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    example = load_example_rows()
    for name, opener in (("health.db", open_db), ("medicine.db", open_medicine_db)):
        conn = opener()
        try:
            per_date = remove_rows(conn, example, args.yes)
        finally:
            conn.close()
        print(t(f"{name}: {sum(per_date.values())} Zeilen", f"{name}: {sum(per_date.values())} rows"), dict(sorted(per_date.items())))


if __name__ == "__main__":
    main()
