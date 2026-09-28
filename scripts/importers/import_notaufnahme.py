#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_notaufnahme.py — RKI-Notaufnahmesurveillance → health.db (ed_syndromic_surveillance)

@tier        infrastructure
@purpose.de  Importiert die RKI-Notaufnahmesurveillance (AKTIN-Infrastruktur/
             Notaufnahmeregister) — tagesaktuelle Anteile von ARI-, ILI-, COVID-,
             SARI-, GI- und HEAT-Vorstellungen an allen Notaufnahme-Besuchen in
             Deutschland, inkl. Erwartungswert und Prädiktionsintervall.
@purpose.en  Imports the RKI emergency-department syndromic surveillance (AKTIN
             infrastructure/emergency department register) — daily shares of
             ARI, ILI, COVID, SARI, GI, and HEAT presentations among all
             emergency department visits in Germany, including expected value
             and prediction interval.
@method.de   Lädt die bundesweite Zeitreihen-TSV von GitHub (~330.000 Zeilen seit
             2019, alle Notaufnahmetypen/Altersgruppen). Filtert standardmäßig auf
             ed_type='all' und age_group='00+' (Gesamtbevölkerung, alle Kliniktypen)
             — sonst würde die Alterskohorten-/Kliniktyp-Aufschlüsselung die Tabelle
             unnötig aufblähen. Rollierendes Zeitfenster wie bei GrippeWeb/
             ARE-Konsultationsinzidenz/AMELAG — voller Verlauf seit 2019 via
             --full-history.
@method.en   Downloads the nationwide time-series TSV from GitHub (~330,000 rows
             since 2019, all ED types/age groups). Filters by default to
             ed_type='all' and age_group='00+' (total population, all hospital
             types) — otherwise the age-cohort/ED-type breakdown would needlessly
             bloat the table. Rolling time window like GrippeWeb/ARE consultation
             incidence/AMELAG (import_outbreak_data.py, import_amelag.py) — full
             history since 2019 via --full-history.
@reads       GitHub (robert-koch-institut/Daten_der_Notaufnahmesurveillance, CC-BY 4.0)
@writes      health.db:ed_syndromic_surveillance, health.db:import_log
@limits.de   Nur bundesweit aggregiert, keine Bundesland-/Landkreis-Ebene verfügbar.
             Keine medizinische Interpretation der Werte.
@limits.en   Nationwide aggregate only, no federal-state/district level available.
             No medical interpretation of the values.
@usage
    python3 import_notaufnahme.py
    python3 import_notaufnahme.py --ed-type all --age-group 00+
    python3 import_notaufnahme.py --full-history
@refs RKI Notaufnahmesurveillance: https://github.com/robert-koch-institut/Daten_der_Notaufnahmesurveillance


@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
"""

import argparse
import sqlite3
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import OWN_PERSON_ID as _OWN_PERSON_ID
from modules.db import open_db, DB_ERRORS
from modules.base import log_import
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_TSV_URL = (
    "https://raw.githubusercontent.com/robert-koch-institut/"
    "Daten_der_Notaufnahmesurveillance/main/Notaufnahmesurveillance_Zeitreihen_Syndrome.tsv"
)

DEFAULT_ED_TYPE = "all"
DEFAULT_AGE_GROUP = "00+"


def _fetch_tsv() -> str | None:
    """Rohtext-Download der Notaufnahmesurveillance-TSV von GitHub."""
    try:
        req = urllib.request.Request(_TSV_URL, headers={"User-Agent": "Kyoro-HealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(t(f"    Notaufnahmesurveillance Fehler: {e}",
                f"    ED surveillance error: {e}"))
        return None


def _parse_float(s: str | None) -> float | None:
    """RKI kodiert fehlende Werte als 'NA' — als None behandeln."""
    if s is None:
        return None
    s = s.strip()
    if s in ("", "NA", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _cutoff_date(weeks_back: int) -> str:
    return (date.today() - timedelta(weeks=weeks_back)).isoformat()


def import_notaufnahme_from_raw(
    conn: sqlite3.Connection, tsv: str,
    ed_type: str = DEFAULT_ED_TYPE, age_group: str = DEFAULT_AGE_GROUP,
    weeks_back: int = 52,
) -> int:
    """Notaufnahmesurveillance-TSV → ed_syndromic_surveillance, gefiltert auf
    einen ed_type/age_group (Standard: Gesamtbevölkerung, alle Kliniktypen)."""
    lines = tsv.strip().split("\n")
    if len(lines) < 2:
        return 0
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    required = ("date", "ed_type", "age_group", "syndrome", "relative_cases",
                "relative_cases_7day_ma", "expected_value", "expected_lowerbound",
                "expected_upperbound", "ed_count")
    if not all(name in idx for name in required):
        print(t("    Notaufnahmesurveillance: unerwartetes TSV-Format, übersprungen",
                "    ED surveillance: unexpected TSV format, skipped"))
        return 0

    cutoff = _cutoff_date(weeks_back)
    inserted = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        r = line.split("\t")
        if len(r) <= max(idx.values()):
            continue
        if r[idx["ed_type"]] != ed_type or r[idx["age_group"]] != age_group:
            continue
        d = r[idx["date"]]
        if d < cutoff:
            continue

        ed_count_raw = r[idx["ed_count"]].strip()
        ed_count = int(ed_count_raw) if ed_count_raw.isdigit() else None

        try:
            conn.execute("""
                INSERT OR IGNORE INTO ed_syndromic_surveillance
                (date, ed_type, age_group, syndrome, relative_cases,
                 relative_cases_7day_ma, expected_value, expected_lowerbound,
                 expected_upperbound, ed_count, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (d, r[idx["ed_type"]], r[idx["age_group"]], r[idx["syndrome"]],
                  _parse_float(r[idx["relative_cases"]]),
                  _parse_float(r[idx["relative_cases_7day_ma"]]),
                  _parse_float(r[idx["expected_value"]]),
                  _parse_float(r[idx["expected_lowerbound"]]),
                  _parse_float(r[idx["expected_upperbound"]]),
                  ed_count, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"    DB-Fehler: {e}", f"    DB error: {e}"))

    conn.commit()
    return inserted


def import_notaufnahme(
    conn: sqlite3.Connection, ed_type: str = DEFAULT_ED_TYPE,
    age_group: str = DEFAULT_AGE_GROUP, weeks_back: int = 52,
) -> int:
    """TSV holen und importieren."""
    tsv = _fetch_tsv()
    if not tsv:
        return 0
    n = import_notaufnahme_from_raw(conn, tsv, ed_type, age_group, weeks_back)
    print(t(f"    Notaufnahmesurveillance: {n} neue Einträge",
            f"    ED surveillance: {n} new entries"))
    # person=None explizit: bevoelkerungsbezogene RKI-Notaufnahmesurveillance, keine Personendaten (s. add-importer-person-parameterization-remaining)

    log_import(conn, 'ed_syndromic_surveillance', '', n, person=None)
    conn.commit()
    return n


def main():
    parser = argparse.ArgumentParser(
        description=t("RKI-Notaufnahmesurveillance → health.db",
                       "RKI emergency-department syndromic surveillance → health.db")
    )
    parser.add_argument("--ed-type", default=DEFAULT_ED_TYPE,
                        choices=["all", "central", "pediatric"],
                        help=t(f"Notaufnahmetyp (Standard: {DEFAULT_ED_TYPE})",
                               f"ED type (default: {DEFAULT_ED_TYPE})"))
    parser.add_argument("--age-group", default=DEFAULT_AGE_GROUP,
                        help=t(f"Altersgruppe (Standard: {DEFAULT_AGE_GROUP})",
                               f"Age group (default: {DEFAULT_AGE_GROUP})"))
    parser.add_argument("--full-history", action="store_true",
                        help=t("Einmaliger Backfill seit 2019 statt rollierendem "
                               "52-Wochen-Fenster. Idempotent, beliebig wiederholbar.",
                               "One-time backfill since 2019 instead of the rolling "
                               "52-week window. Idempotent, safe to re-run."))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    weeks_back = 100_000 if args.full_history else 52
    print(t(f"Notaufnahmesurveillance-Import ({args.ed_type}/{args.age_group}) ...",
            f"ED surveillance import ({args.ed_type}/{args.age_group}) ..."))
    conn = open_db()
    n = import_notaufnahme(conn, args.ed_type, args.age_group, weeks_back)
    conn.close()
    print(t(f"\n{n} neue Einträge importiert.", f"\n{n} new entries imported."))


if __name__ == "__main__":
    main()
