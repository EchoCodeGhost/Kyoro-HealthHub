#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_location_columns.py — Prüft, dass health.db und medicine.db keine persönlichen Koordinaten enthalten

@tier        infrastructure
@purpose.de  Prüft, dass Koordinaten nur in location.db liegen: Jede Spalte
             lat/lon/latitude/longitude (auch mit Präfix wie trip_lat) in
             health.db und medicine.db ist leer, mit zwei Ausnahmen:
             Umwelttabellen, deren Schlüssel der vergröberte Abfragepunkt für
             externe Dienste ist (höchstens 2 Nachkommastellen), und
             Ausbruchsmeldungen (öffentliche Orte, nicht die der Person).
@purpose.en  Checks that coordinates live only in location.db: every
             lat/lon/latitude/longitude column (also with a prefix such as
             trip_lat) in health.db and medicine.db is empty, with two
             exceptions: environment tables keyed by the coarsened query point
             for external services (at most 2 decimal places), and outbreak
             reports (public places, not the person's).
@method.de   Liest die Spalten aller Tabellen, zählt nicht-leere Werte und die
             höchste Zahl an Nachkommastellen. Zählt außerdem Audit-Log-Kopien
             von Zeilen aus Orts-Tabellen (sie enthalten Koordinaten als JSON). Gibt nur Tabellennamen und
             Anzahlen aus, nie Koordinaten. Exit 1 bei Befunden.
@method.en   Reads the columns of all tables, counts non-empty values and the
             highest number of decimal places. Also counts audit-log copies of
             rows from location tables (they hold coordinates as JSON). Prints only table names and
             counts, never coordinates. Exit 1 on findings.
@reads       health.db, medicine.db
@writes      (nichts)
@limits.de   Erkennt Koordinaten nur über Spaltennamen; Koordinaten in
             Freitext prüft check_anonymization.py.
@limits.en   Detects coordinates by column name only; coordinates in free text
             are checked by check_anonymization.py.

@relevance.de  Stellt sicher, dass persönliche Orte nur in location.db stehen
@relevance.en  Ensures personal locations exist only in location.db
@usage
    python3 scripts/utils/check_location_columns.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import open_db, open_medicine_db
from modules.i18n import add_lang_arg, apply_lang_from_args, t

# Umwelttabellen: Schlüssel ist der für externe Dienste vergröberte Abfragepunkt
COARSE_ENVIRONMENT_TABLES = {"air_quality", "pollen", "biometeo", "weather_station", "weather_remote"}
COARSE_MAX_DECIMALS = 2
# Öffentliche Orte (Ausbruchsmeldungen), keine persönlichen
PUBLIC_PLACE_TABLES = {"outbreak_events"}

# Audit-Log-Kopien dieser Tabellen enthalten Koordinaten (JSON in old_data/new_data)
LOCATION_AUDIT_TABLES = ("session_tracks", "location_stays", "location_history",
                         "photo_locations", "location_registry")

_GEO_COLUMN = re.compile(r"^(?:\w+_)?(lat|lon|lng|latitude|longitude)$", re.IGNORECASE)


def _decimals_sql(col: str) -> str:
    text = f'CAST("{col}" AS TEXT)'
    return f"CASE WHEN INSTR({text}, '.') > 0 THEN LENGTH({text}) - INSTR({text}, '.') ELSE 0 END"


def scan(conn) -> list[dict]:
    """Liefert je Tabelle mit Koordinatenspalten: Anzahl Werte, max. Nachkommastellen, Befund."""
    results = []
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for table in tables:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")') if _GEO_COLUMN.match(r[1])]
        if not cols:
            continue
        where = " OR ".join(f'"{c}" IS NOT NULL' for c in cols)
        n = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {where}').fetchone()[0]
        max_dec = 0
        for c in cols:
            v = conn.execute(f'SELECT MAX({_decimals_sql(c)}) FROM "{table}" WHERE "{c}" IS NOT NULL').fetchone()[0]
            max_dec = max(max_dec, v or 0)
        if table in PUBLIC_PLACE_TABLES:
            finding = False
        elif table in COARSE_ENVIRONMENT_TABLES:
            finding = n > 0 and max_dec > COARSE_MAX_DECIMALS
        else:
            finding = n > 0
        results.append({"table": table, "columns": cols, "rows": n,
                        "max_decimals": max_dec, "finding": finding})
    if "audit_log" in tables:
        n = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE table_name IN ({})".format(
                ",".join("?" * len(LOCATION_AUDIT_TABLES))), LOCATION_AUDIT_TABLES).fetchone()[0]
        results.append({"table": "audit_log", "columns": ["old_data", "new_data"], "rows": n,
                        "max_decimals": 0, "finding": n > 0})
    return results


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description=t("Prüft health.db und medicine.db auf persönliche Koordinaten",
                      "Check health.db and medicine.db for personal coordinates"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    findings = 0
    for label, opener in (("health.db", open_db), ("medicine.db", open_medicine_db)):
        conn = opener()
        try:
            for r in scan(conn):
                mark = "✗" if r["finding"] else "✓"
                findings += r["finding"]
                print(t(f"  {mark} {label}:{r['table']}: {r['rows']} Zeilen mit Koordinaten, "
                        f"max. {r['max_decimals']} Nachkommastellen",
                        f"  {mark} {label}:{r['table']}: {r['rows']} rows with coordinates, "
                        f"max {r['max_decimals']} decimal places"))
        finally:
            conn.close()
    if findings:
        print(t(f"{findings} Tabelle(n) mit persönlichen Koordinaten außerhalb von location.db.",
                f"{findings} table(s) with personal coordinates outside location.db."))
        return 1
    print(t("Keine persönlichen Koordinaten in health.db oder medicine.db.",
            "No personal coordinates in health.db or medicine.db."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
