#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_amelag.py — RKI/UBA Abwassersurveillance AMELAG → health.db (wastewater_amelag)

@tier        infrastructure
@purpose.de  Importiert die AMELAG-Abwasserüberwachung (SARS-CoV-2, Influenza A/B, RSV)
             des RKI und Umweltbundesamts — bundesweite aggregierte Kurve sowie
             Einzelstandorte für ein wählbares Bundesland (Standard: aus der
             konfigurierten Heimatkoordinate abgeleitet, s. modules/geo_bundesland.py —
             kein hartkodiertes Bundesland, funktioniert für jede Installation).
@purpose.en  Imports the AMELAG wastewater surveillance (SARS-CoV-2, Influenza A/B, RSV)
             from RKI and the Federal Environment Agency — nationwide aggregated curve
             plus individual sites for a selectable federal state (default: derived
             from the configured home coordinate, see modules/geo_bundesland.py — no
             hardcoded federal state, works for any installation).
@method.de   Lädt zwei TSV-Dateien von GitHub: die bundesweite aggregierte Kurve
             (klein, ~1000 Zeilen) und die Einzelstandort-Datei (bundesweit ~460.000
             Zeilen, wird lokal auf ein Bundesland gefiltert, da keine serverseitige
             Filterung existiert). Speichert beides in wastewater_amelag mit
             INSERT OR IGNORE. Rollierendes Zeitfenster wie bei GrippeWeb/
             ARE-Konsultationsinzidenz (import_outbreak_data.py) — voller Verlauf
             seit Beginn der Erhebung (Feb. 2022) via --full-history.
@method.en   Downloads two TSV files from GitHub: the nationwide aggregated curve
             (small, ~1000 rows) and the per-site file (nationwide ~460,000 rows,
             filtered locally to one federal state — no server-side filtering exists).
             Stores both in wastewater_amelag with INSERT OR IGNORE. Rolling time
             window like GrippeWeb/ARE consultation incidence (import_outbreak_data.py)
             — full history since data collection began (Feb 2022) via --full-history.
@reads       GitHub (robert-koch-institut/Abwassersurveillance_AMELAG, CC-BY 4.0)
@writes      health.db:wastewater_amelag, health.db:import_log
@limits.de   Einzelstandort-Datei ist ~50 MB (bundesweit), wird komplett heruntergeladen
             und lokal gefiltert — keine serverseitige Bundesland-Filterung verfügbar.
             Keine medizinische Interpretation der Viruslast-Werte.
@limits.en   Per-site file is ~50 MB (nationwide), downloaded in full and filtered
             locally — no server-side federal-state filtering available.
             No medical interpretation of viral-load values.
@usage
    python3 import_amelag.py
    python3 import_amelag.py --bundesland BY
    python3 import_amelag.py --full-history
@refs RKI/UBA AMELAG: https://github.com/robert-koch-institut/Abwassersurveillance_AMELAG


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
from health_config import Config as _Cfg, OWN_PERSON_ID as _OWN_PERSON_ID
from modules.db import open_db, DB_ERRORS
from modules.base import log_import
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.geo_bundesland import nearest_bundesland

_NATIONAL_URL = (
    "https://raw.githubusercontent.com/robert-koch-institut/"
    "Abwassersurveillance_AMELAG/main/amelag_aggregierte_kurve.tsv"
)
_SITES_URL = (
    "https://raw.githubusercontent.com/robert-koch-institut/"
    "Abwassersurveillance_AMELAG/main/amelag_einzelstandorte.tsv"
)


def _default_bundesland() -> str | None:
    """Bundesland aus der Heimatkoordinate ableiten (kein Hardcoding auf ein
    bestimmtes Bundesland) — None, wenn keine Heimatkoordinate konfiguriert ist."""
    cfg = _Cfg()
    if cfg.home_lat is None or cfg.home_lon is None:
        return None
    _, code = nearest_bundesland(cfg.home_lat, cfg.home_lon)
    return code


def _fetch_tsv(url: str) -> str | None:
    """Rohtext-Download einer AMELAG-TSV-Datei von GitHub."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Kyoro-HealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(t(f"    AMELAG Fehler: {e}", f"    AMELAG error: {e}"))
        return None


def _parse_float(s: str | None) -> float | None:
    """AMELAG kodiert fehlende Werte als 'NA' — als None behandeln."""
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


def import_amelag_national_from_raw(
    conn: sqlite3.Connection, tsv: str, weeks_back: int = 52
) -> int:
    """Bundesweite aggregierte AMELAG-Kurve → wastewater_amelag (level='national')."""
    lines = tsv.strip().split("\n")
    if len(lines) < 2:
        return 0
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    required = ("datum", "anteil_bev", "viruslast", "viruslast_normalisiert",
                "vorhersage", "obere_schranke", "untere_schranke", "typ")
    if not all(name in idx for name in required):
        print(t("    AMELAG bundesweit: unerwartetes TSV-Format, übersprungen",
                "    AMELAG nationwide: unexpected TSV format, skipped"))
        return 0

    cutoff = _cutoff_date(weeks_back)
    inserted = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        r = line.split("\t")
        if len(r) <= max(idx.values()):
            continue
        d = r[idx["datum"]]
        if d < cutoff:
            continue
        try:
            conn.execute("""
                INSERT OR IGNORE INTO wastewater_amelag
                (date, level, site, bundesland, virus, viral_load, viral_load_normalized,
                 forecast, upper_bound, lower_bound, population_share, person)
                VALUES (?,'national',NULL,NULL,?,?,?,?,?,?,?,?)
            """, (d, r[idx["typ"]],
                  _parse_float(r[idx["viruslast"]]), _parse_float(r[idx["viruslast_normalisiert"]]),
                  _parse_float(r[idx["vorhersage"]]), _parse_float(r[idx["obere_schranke"]]),
                  _parse_float(r[idx["untere_schranke"]]), _parse_float(r[idx["anteil_bev"]]),
                  _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"    DB-Fehler: {e}", f"    DB error: {e}"))
    conn.commit()
    return inserted


def import_amelag_sites_from_raw(
    conn: sqlite3.Connection, tsv: str, bundesland: str, weeks_back: int = 52,
) -> int:
    """Einzelstandort-AMELAG-Daten, gefiltert auf ein Bundesland → wastewater_amelag."""
    lines = tsv.strip().split("\n")
    if len(lines) < 2:
        return 0
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    required = ("standort", "bundesland", "datum", "viruslast", "viruslast_normalisiert",
                "vorhersage", "obere_schranke", "untere_schranke", "einwohner",
                "typ", "unter_bg")
    if not all(name in idx for name in required):
        print(t("    AMELAG Standorte: unerwartetes TSV-Format, übersprungen",
                "    AMELAG sites: unexpected TSV format, skipped"))
        return 0

    cutoff = _cutoff_date(weeks_back)
    inserted = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        r = line.split("\t")
        if len(r) <= max(idx.values()):
            continue
        if r[idx["bundesland"]] != bundesland:
            continue
        d = r[idx["datum"]]
        if d < cutoff:
            continue

        below_bg_raw = r[idx["unter_bg"]].strip()
        below_bg = 1 if below_bg_raw == "ja" else 0 if below_bg_raw == "nein" else None
        einwohner_raw = r[idx["einwohner"]].strip()
        einwohner = int(einwohner_raw) if einwohner_raw.isdigit() else None

        try:
            conn.execute("""
                INSERT OR IGNORE INTO wastewater_amelag
                (date, level, site, bundesland, virus, viral_load, viral_load_normalized,
                 forecast, upper_bound, lower_bound, population_covered,
                 below_detection_limit, person)
                VALUES (?,'site',?,?,?,?,?,?,?,?,?,?,?)
            """, (d, r[idx["standort"]], r[idx["bundesland"]], r[idx["typ"]],
                  _parse_float(r[idx["viruslast"]]), _parse_float(r[idx["viruslast_normalisiert"]]),
                  _parse_float(r[idx["vorhersage"]]), _parse_float(r[idx["obere_schranke"]]),
                  _parse_float(r[idx["untere_schranke"]]), einwohner, below_bg, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"    DB-Fehler: {e}", f"    DB error: {e}"))
    conn.commit()
    return inserted


def import_amelag(
    conn: sqlite3.Connection, bundesland: str | None = None, weeks_back: int = 52
) -> int:
    """Beide AMELAG-Dateien holen und importieren (bundesweite Kurve + ein Bundesland).

    bundesland=None: aus der Heimatkoordinate ableiten (kein hartkodiertes
    Bundesland — funktioniert für jede Installation); ohne Heimatkoordinate
    wird nur die bundesweite Kurve importiert, Standort-Import übersprungen.
    """
    national_tsv = _fetch_tsv(_NATIONAL_URL)
    n_national = import_amelag_national_from_raw(conn, national_tsv, weeks_back) if national_tsv else 0
    print(t(f"    AMELAG bundesweit: {n_national} neue Einträge",
            f"    AMELAG nationwide: {n_national} new entries"))

    if bundesland is None:
        bundesland = _default_bundesland()
    if bundesland is None:
        print(t("    AMELAG Standorte: übersprungen (keine Heimatkoordinate "
                "konfiguriert — --bundesland explizit angeben oder "
                "location.lat/lon in health_config.json setzen)",
                "    AMELAG sites: skipped (no home coordinate configured — "
                "pass --bundesland explicitly or set location.lat/lon in "
                "health_config.json)"))
        n_sites = 0
    else:
        sites_tsv = _fetch_tsv(_SITES_URL)
        n_sites = (
            import_amelag_sites_from_raw(conn, sites_tsv, bundesland, weeks_back)
            if sites_tsv else 0
        )
        print(t(f"    AMELAG Standorte ({bundesland}): {n_sites} neue Einträge",
                f"    AMELAG sites ({bundesland}): {n_sites} new entries"))

    total = n_national + n_sites
    # person=None explizit: bundesweite/regionale Abwasser-Viruslast ist
    # keine personenbezogene Messung — "person" in der Tabelle ist nur ein
    # Relevanz-Tag auf sonst voellig allgemeinen Daten, dieselbe Einordnung
    # wie bei import_outbreak_data.py (s. add-importer-person-override-
    # convention, Punkt 5). OWN_PERSON_ID bleibt als Spaltenwert bestehen
    # (Schema-Vorgabe), aber der Log-Eintrag soll das nicht als "fuer eine
    # Person" ausweisen.
    log_import(conn, 'wastewater_amelag', '', total, person=None)
    conn.commit()
    return total


def main():
    parser = argparse.ArgumentParser(
        description=t("RKI/UBA AMELAG Abwassersurveillance → health.db",
                       "RKI/UBA AMELAG wastewater surveillance → health.db")
    )
    parser.add_argument(
        "--bundesland", default=None,
        help=t("Bundesland-Code für Einzelstandorte (Standard: aus "
               "Heimatkoordinate abgeleitet, s. location.lat/lon in "
               "health_config.json)",
               "Federal-state code for per-site data (default: derived from "
               "home coordinate, see location.lat/lon in health_config.json)")
    )
    parser.add_argument(
        "--full-history", action="store_true",
        help=t("Einmaliger Backfill seit Beginn der Erhebung (Feb. 2022) statt "
               "rollierendem 52-Wochen-Fenster. Idempotent, beliebig wiederholbar.",
               "One-time backfill since data collection began (Feb 2022) instead "
               "of the rolling 52-week window. Idempotent, safe to re-run.")
    )
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    weeks_back = 100_000 if args.full_history else 52
    print(t(f"AMELAG-Import ({args.bundesland or 'aus Heimatkoordinate'}) ...",
            f"AMELAG import ({args.bundesland or 'from home coordinate'}) ..."))
    conn = open_db()
    total = import_amelag(conn, args.bundesland, weeks_back)
    conn.close()
    print(t(f"\nGesamt: {total} neue Einträge importiert",
            f"\nTotal: {total} new entries imported"))


if __name__ == "__main__":
    main()
