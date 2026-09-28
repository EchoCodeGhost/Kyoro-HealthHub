#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fix_apple_sleep_unspecified_null.py — Backfills the numeric code for
Apple Health's "AsleepUnspecified" sleep-analysis category value in
already-imported rows, so they carry a value instead of NULL.

@tier        infrastructure
@purpose.de  import_apple.py's CATEGORY_MAP kannte den String
             'HKCategoryValueSleepAnalysisAsleepUnspecified' bisher nicht
             (nur 'HKCategoryValueSleepAnalysisAsleep', die semantisch
             identische, aeltere Bezeichnung desselben Rohwerts). float()
             auf den unbekannten String scheiterte, also wurde jede
             betroffene Zeile mit value=NULL importiert. Diese Migration
             traegt fuer bereits importierte Zeilen den Code nach, den
             import_apple.py (inzwischen korrigiert) fuer neue Importe
             verwendet.
@purpose.en  import_apple.py's CATEGORY_MAP previously did not know the
             string 'HKCategoryValueSleepAnalysisAsleepUnspecified' (only
             'HKCategoryValueSleepAnalysisAsleep', the semantically
             identical, older name for the same raw value). float() on
             the unknown string failed, so every affected row was
             imported with value=NULL. This migration backfills the code
             for already-imported rows that import_apple.py (now fixed)
             uses for new imports.
@method.de   Ein gezieltes UPDATE auf measurements: metric='sleep_analysis'
             AND value IS NULL AND
             value_text='HKCategoryValueSleepAnalysisAsleepUnspecified'
             -> value=1.0. Der value_text-Filter ist die einzige
             verlaessliche Identifikation: eine Zeile mit value IS NULL
             koennte im Prinzip auch aus einem anderen Grund NULL sein
             (unbekannter zukuenftiger Kategoriewert); ohne exakten
             value_text-Treffer bleibt die Zeile unangetastet, statt
             geraten umgeschrieben zu werden. Code 1.0 ist bewusst
             identisch zum bestehenden Code fuer
             'HKCategoryValueSleepAnalysisAsleep' (siehe CATEGORY_MAP in
             import_apple.py) -- beide bedeuten "hat geschlafen, keine
             Stadien-Information", keine Schlafphase. Code 1.0 ist in
             compute_sleep_hypnogram.APPLE_STAGE_MAP (kennt nur 2/3/4/5)
             und in dessen build_apple()-Query (WHERE value IN
             (2.0,3.0,4.0,5.0)) nicht enthalten, faellt also nicht
             faelschlich in eine WAKE/LIGHT/DEEP/REM-Klassifikation.
             Idempotent: der WHERE-Filter (value IS NULL) trifft nach dem
             ersten Lauf auf keine Zeile mehr.
@method.en   One targeted UPDATE on measurements: metric='sleep_analysis'
             AND value IS NULL AND
             value_text='HKCategoryValueSleepAnalysisAsleepUnspecified'
             -> value=1.0. The value_text filter is the only reliable
             identification: a row with value IS NULL could in principle
             be NULL for a different reason (an unknown future category
             value); without an exact value_text match the row is left
             untouched rather than rewritten on a guess. Code 1.0 is
             deliberately identical to the existing code for
             'HKCategoryValueSleepAnalysisAsleep' (see CATEGORY_MAP in
             import_apple.py) -- both mean "was asleep, no stage
             information", not a sleep stage. Code 1.0 is absent from
             compute_sleep_hypnogram.APPLE_STAGE_MAP (only knows
             2/3/4/5) and from its build_apple() query (WHERE value IN
             (2.0,3.0,4.0,5.0)), so it does not get misclassified into a
             WAKE/LIGHT/DEEP/REM stage. Idempotent: after the first run,
             the WHERE filter (value IS NULL) no longer matches any row.
@reads       health.db (measurements: metric, value, value_text)
@writes      health.db (measurements.value only for the matched rows --
             metric, value_text, ts, date, device_id, person, source_app
             untouched)
@limits.de   Betrifft ausschliesslich bereits importierte Zeilen. Ein
             erneuter Lauf von import_apple.py (nach dem CATEGORY_MAP-Fix)
             haette denselben Effekt fuer diese Zeilen und macht diese
             Migration danach ueberfluessig -- sie existiert, damit die
             Korrektur nicht von einem vollstaendigen Re-Import des
             (grossen) Apple-Health-XML-Exports abhaengt.
@limits.en   Only affects already-imported rows. A fresh run of
             import_apple.py (after the CATEGORY_MAP fix) would have the
             same effect on these rows and would make this migration
             unnecessary afterwards -- it exists so the fix does not
             depend on a full re-import of the (large) Apple Health XML
             export.
@relevance.de  Behebt Datenverlust bei 2.561 Schlaf-Segmenten (2018–2023),
               deren Rohwert bisher stillschweigend als NULL importiert
               wurde -- Datenqualitaet, nicht Funktion.
@relevance.en  Fixes data loss for 2,561 sleep segments (2018-2023) whose
               raw value was previously silently imported as NULL --
               data quality, not a feature.
@usage
    python3 scripts/migrations/fix_apple_sleep_unspecified_null.py --dry-run
    python3 scripts/migrations/fix_apple_sleep_unspecified_null.py

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
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402

METRIC = "sleep_analysis"
VALUE_TEXT = "HKCategoryValueSleepAnalysisAsleepUnspecified"
NEW_VALUE = 1.0  # identisch zu CATEGORY_MAP["HKCategoryValueSleepAnalysisAsleep"]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=t(
            "Traegt fehlenden value-Code fuer Apple 'AsleepUnspecified'-Zeilen nach",
            "Backfills the missing value code for Apple 'AsleepUnspecified' rows",
        )
    )
    ap.add_argument("--dry-run", action="store_true",
                     help=t("Nur anzeigen, nichts ändern", "Show only, change nothing"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    try:
        conn = open_db()
    except Exception as exc:
        print(t(f"Fehler beim Öffnen der Datenbank: {exc}",
                f"Error opening database: {exc}"), file=sys.stderr)
        sys.exit(1)

    n = conn.execute(
        "SELECT COUNT(*) FROM measurements "
        "WHERE metric=? AND value IS NULL AND value_text=?",
        (METRIC, VALUE_TEXT),
    ).fetchone()[0]

    if not n:
        print(t(f"Keine Zeilen mit metric='{METRIC}', value IS NULL, "
                f"value_text='{VALUE_TEXT}' — nichts zu tun.",
                f"No rows with metric='{METRIC}', value IS NULL, "
                f"value_text='{VALUE_TEXT}' — nothing to do."))
        conn.close()
        sys.exit(0)

    print(t(f"  {'Würde nachtragen' if args.dry_run else 'Nachtragen'}: "
            f"{n} Zeile(n) metric='{METRIC}' value_text='{VALUE_TEXT}' → value={NEW_VALUE}",
            f"  {'Would backfill' if args.dry_run else 'Backfilling'}: "
            f"{n} row(s) metric='{METRIC}' value_text='{VALUE_TEXT}' → value={NEW_VALUE}"))

    if not args.dry_run:
        conn.execute(
            "UPDATE measurements SET value=? "
            "WHERE metric=? AND value IS NULL AND value_text=?",
            (NEW_VALUE, METRIC, VALUE_TEXT),
        )
        log_import(conn, "fix_apple_sleep_unspecified_null", "measurements",
                   n, person=None)
        conn.commit()

    print(t(f"{'Würden' if args.dry_run else ''} insgesamt {n} Zeile(n) nachgetragen.",
            f"Would backfill {n} row(s) in total." if args.dry_run
            else f"Backfilled {n} row(s) in total."))
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
