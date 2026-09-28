#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Symptom canonicalisation: symptoms -> symptoms_canonical.

@tier        infrastructure
@purpose.de  Normiert rohe Symptombezeichnungen (DE/EN, verschiedene Apps) auf ein
             einheitliches kanonisches Vokabular. Reines Vokabular-Mapping.
@purpose.en  Normalises raw symptom labels (DE/EN, various apps) onto a unified
             canonical vocabulary. Pure vocabulary mapping.
@method.de   Jede Bezeichnung wird über die Mapping-Datei auf kanonische DE/EN-
             Begriffe abgebildet. Nicht gemappte Einträge werden 1:1 übernommen
             (category='other').
@method.en   Each label is mapped via the mapping file to canonical DE/EN terms.
             Unmapped entries are carried over 1:1 (category='other').
@reads       symptoms
@writes      symptoms_canonical
@limits.de   Bewusst keine ICD-10-Kodierung — Symptom-Mapping-Dateien werden
             nicht als verifizierte Diagnose-Kodierungsquelle gepflegt (s.
             Commit-Historie). Nicht gemappte Symptome bleiben unkategorisiert.

@relevance.de  Ermöglicht die Symptomanalyse, essentiell für die klinische Diagnostik
@relevance.en  Enables symptom analysis, essential for clinical diagnostics
@limits.en   Deliberately no ICD-10 coding — symptom mapping files are not
             maintained as a verified diagnostic coding source (see commit
             history). Unmapped symptoms remain uncategorised.
@usage
    python3 compute_symptoms.py
    python3 compute_symptoms.py --update
    python3 compute_symptoms.py --list-unmapped
"""

import argparse
import json
from pathlib import Path
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg    = _Cfg()
DB_PATH = _cfg.db_path

_MAP_PATH_DEFAULT = Path(__file__).parent.parent.parent / "config" / "symptom_map.json"
_MAP_PATH_USER    = KYORO_CONFIG_DIR / "symptom_map.json"
_MAP_PATH = _MAP_PATH_USER if _MAP_PATH_USER.exists() else _MAP_PATH_DEFAULT

_SCHEMA = """
CREATE TABLE IF NOT EXISTS symptoms_canonical (
    date        TEXT NOT NULL,
    symptom_de  TEXT NOT NULL,
    symptom_en  TEXT,
    category    TEXT,
    value_num   REAL,
    value_text  TEXT,
    person      TEXT NOT NULL,
    source      TEXT,
    raw_name    TEXT,
    PRIMARY KEY (date, symptom_de, person, source)
);
CREATE INDEX IF NOT EXISTS idx_sc_date   ON symptoms_canonical(date);
CREATE INDEX IF NOT EXISTS idx_sc_sym    ON symptoms_canonical(symptom_de);
CREATE INDEX IF NOT EXISTS idx_sc_cat    ON symptoms_canonical(category);
"""


def _load_map() -> dict:
    raw = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _normalize_key(name: str) -> str:
    return name.strip().lower()


def compute(conn, update_only: bool = False) -> tuple[int, int, list[str]]:
    """Gibt (inserted, skipped, unmapped_names) zurück."""
    for stmt in _SCHEMA.strip().split(";"):
        s = stmt.strip()
        if s:
            conn.execute(s)
    conn.commit()

    symptom_map = _load_map()

    last_date = None
    if update_only:
        last_date = conn.execute(
            "SELECT MAX(date) FROM symptoms_canonical"
        ).fetchone()[0]

    if last_date:
        rows = conn.execute("""
            SELECT s.date, s.symptom, s.value_num, s.value_text, s.category,
                   s.person, s.source
            FROM symptoms s
            WHERE s.date > ?
            ORDER BY s.date
        """, (last_date,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT s.date, s.symptom, s.value_num, s.value_text, s.category,
                   s.person, s.source
            FROM symptoms s
            ORDER BY s.date
        """).fetchall()

    inserted = skipped = 0
    unmapped: set[str] = set()

    for date, raw_name, value_num, value_text, raw_cat, person, source in rows:
        key = _normalize_key(raw_name)
        entry = symptom_map.get(key)

        if entry:
            symptom_de = entry["de"]
            symptom_en = entry.get("en")
            category   = entry.get("category") or raw_cat or "other"
        else:
            unmapped.add(raw_name)
            symptom_de = raw_name
            symptom_en = None
            category   = raw_cat or "other"

        cur = conn.execute(
            "INSERT OR IGNORE INTO symptoms_canonical "
            "(date, symptom_de, symptom_en, category, "
            " value_num, value_text, person, source, raw_name) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (date, symptom_de, symptom_en, category,
             value_num, value_text, person, source, raw_name),
        )
        if cur.rowcount > 0:
            inserted += 1
        else:
            skipped += 1

    conn.commit()
    return inserted, skipped, sorted(unmapped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Symptom-Kanonisierung → symptoms_canonical",
                      "Symptom canonicalisation → symptoms_canonical")
    )
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Tage ergänzen", "Only add new days"))
    parser.add_argument("--list-unmapped", action="store_true",
                        help=t("Unmapped Symptome ausgeben", "List unmapped symptoms"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    print(t("\n── compute_symptoms ───────────────────────────────────",
            "\n── compute_symptoms ───────────────────────────────────"))

    inserted, skipped, unmapped = compute(conn, update_only=args.update)

    print(t(f"  {inserted} kanonisiert, {skipped} bereits vorhanden",
            f"  {inserted} canonicalised, {skipped} already present"))

    if unmapped:
        label = t("  Nicht gemappt (werden 1:1 übernommen):",
                  "  Not mapped (passed through as-is):")
        print(label)
        for name in unmapped:
            print(f"    {name!r}")
        if not args.list_unmapped:
            print(t("  → symptom_map.json erweitern um diese zu normieren.",
                    "  → Extend symptom_map.json to normalise these."))

    total = conn.execute("SELECT COUNT(*) FROM symptoms_canonical").fetchone()[0]
    print(t(f"  Gesamt in symptoms_canonical: {total}",
            f"  Total in symptoms_canonical: {total}"))

    conn.close()


if __name__ == "__main__":
    main()
