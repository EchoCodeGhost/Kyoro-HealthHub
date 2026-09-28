#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fix_polar_wrist_device_attribution.py — Reassigns historical device_id='polar_vantage'
rows to the correct Polar wrist watch by date

@tier        infrastructure
@purpose.de  Korrigiert historische measurements/sessions-Zeilen, die fälschlich
             device_id='polar_vantage' zugeordnet wurden, obwohl zum jeweiligen
             Zeitpunkt ein anderes Polar-Wrist-Gerät getragen wurde. Grund:
             import_polar.py's _polar_device_for_date() fiel jahrelang auf das
             einzige registrierte Polar-Wrist-Gerät zurück, weil frühere/andere
             Wrist-Geräte nie in device_registry standen.
@purpose.en  Corrects historical measurements/sessions rows that were wrongly
             tagged device_id='polar_vantage', even though a different Polar
             wrist device was actually worn at the time. Cause:
             import_polar.py's _polar_device_for_date() fell back to the only
             registered Polar wrist device for years, because earlier/other
             wrist devices were never in device_registry.
@method.de   Reine UPDATE-Anweisungen anhand fester Datumsgrenzen aus
             clinical.polar_wrist_date_reassignments (lokale Config, s.u.),
             nicht im Repo hartcodiert. Rührt nur Zeilen mit
             device_id='polar_vantage' an; Zeilen im tatsächlichen
             Vantage-V3-Zeitraum bleiben unverändert. Kein DDL, keine Zeilen
             werden gelöscht.
@method.en   Plain UPDATE statements against fixed date boundaries from
             clinical.polar_wrist_date_reassignments (local config, see
             below), not hardcoded in the repo. Only touches rows with
             device_id='polar_vantage'; rows in the actual Vantage V3 period
             are left untouched. No DDL, no rows deleted.
@reads       measurements, sessions (device_id, date)
@writes      measurements, sessions (UPDATE device_id for polar_vantage-tagged
             rows outside the real Vantage V3 ownership window)
@limits.de   Datumsgrenzen sind größtenteils Nutzerangaben; nur einzelne
             Grenzen lassen sich exakt aus einem Hersteller-Export ableiten
             (z.B. Archivierungs-Zeitstempel), die übrigen bleiben Näherungen.
             Bei echtem Parallel-Tragen mehrerer Uhren ist exakte Zuordnung aus
             den Daten grundsätzlich nicht rekonstruierbar (Polar-Export
             liefert für Tageswerte/HF-Verlauf/HRV keine Geräte-ID pro
             Eintrag) — diese Migration ist eine bestmögliche Näherung, keine
             exakte Korrektur. Sicher wiederholt ausführbar (Grenzen sind
             exakt, kein Blast-Radius über die betroffenen Zeilen hinaus).

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Date boundaries are mostly user-provided estimates; only some can
             be derived exactly from a manufacturer export (e.g. an archive
             timestamp), the rest remain approximations. Under genuine
             simultaneous multi-watch wear, exact attribution isn't
             reconstructable from the data at all (Polar's export doesn't
             carry a per-entry device ID for daily activity/HR history/HRV) —
             this migration is a best-effort approximation, not an exact fix.
             Safe to re-run (boundaries are exact, no blast radius beyond the
             affected rows).
@usage
    python3 scripts/migrations/fix_polar_wrist_device_attribution.py
    python3 migrations/fix_polar_wrist_device_attribution.py  # from inside scripts/
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config
from modules.base import log_import, resolve_person
from modules.db import open_db

OLD_DEVICE_ID = "polar_vantage"

# Datumsgrenzen kommen aus clinical.polar_wrist_date_reassignments (lokale,
# gitignored Config) statt hartcodiert im Repo — die Grenzen spiegeln die
# reale Geräte-Trage-Zeitachse einer Person und sind damit personenbezogen.
# Reihenfolge egal, Bedingungen sollten disjunkt sein und den echten
# Vantage-V3-Zeitraum ausschließen. Leer = Migration ist No-Op.
#
# WICHTIGE EINSCHRAENKUNG (anders als fix_polar_247hr_device_ids.py /
# fix_polar_training_device_ids.py): polar_wrist_date_reassignments selbst
# ist im Config-SCHEMA nicht personen-gekeyt — Config().polar_wrist_date_reassignments
# liefert immer dieselbe, einzige Liste, unabhaengig vom --person-Flag. Ein
# --person hier filtert nur, WELCHE Zeilen die Umzuordnung trifft (echte
# Wirkung gegen Cross-Person-Kontamination), aendert aber nicht, WOHER die
# Umzuordnungsregeln selbst kommen — das waere eine Config-Schema-Aenderung
# (polar_wrist_date_reassignments pro Person statt einer flachen Liste),
# bewusst nicht Teil dieser Session, s. add-provenance-logging Folgeaufgaben.
REASSIGNMENTS = [
    (r["new_device_id"], r["date_condition"])
    for r in Config().polar_wrist_date_reassignments
]


def run(person: "str | None" = None):
    target_person = resolve_person(person)
    if not REASSIGNMENTS:
        print("Keine polar_wrist_date_reassignments in health_config.json konfiguriert — "
              "nichts zu tun. Siehe health_config.example.json für das Format.")
        return

    conn = open_db()
    cursor = conn.cursor()
    total_fixed = 0

    for table in ("measurements", "sessions"):
        print(f"\n{table}:")
        for new_device_id, condition in REASSIGNMENTS:
            cursor.execute(
                f"UPDATE {table} SET device_id=? "
                f"WHERE device_id=? AND person=? AND {condition}",
                (new_device_id, OLD_DEVICE_ID, target_person),
            )
            if cursor.rowcount:
                total_fixed += cursor.rowcount
                print(f"  → {cursor.rowcount} Zeile(n) → {new_device_id} ({condition})")

    log_import(conn, "fix_polar_wrist_device_attribution", "measurements,sessions",
              total_fixed, person=target_person)
    conn.commit()

    remaining = conn.execute(
        "SELECT COUNT(*) FROM measurements WHERE device_id=?", (OLD_DEVICE_ID,)
    ).fetchone()[0]
    print(f"\n✓ Migration abgeschlossen — {remaining} Zeile(n) bleiben "
          f"'{OLD_DEVICE_ID}' (echter Vantage-V3-Zeitraum 2023-10-01 bis 2025-10-19)")
    conn.close()


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="Korrigiert historische polar_vantage-Fehlzuordnungen")
    _ap.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    run(person=_ap.parse_args().person)
