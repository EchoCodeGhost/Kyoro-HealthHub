#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
context_query.py — user_context abfragen mit optionaler Verknuepfung

@tier        infrastructure
@purpose.de  Ermöglicht Abfragen von Kontextdaten (Notizen, Tags, Annotationen) aus der user_context Tabelle, optional verknüpft mit anderen Daten am gleichen Tag
@purpose.en  Enables querying of context data (notes, tags, annotations) from user_context table, optionally linked with other data on the same day
@method.de   Unterstuetzt verschiedene Filter: nach Datum (--from, --to), Quelle (--source), Tag (--tag), Freitextsuche (--search).
             Zwei Modi: Standard-Abfrage (user_context) und verknuepfte Abfrage (--tag).
             Bei --with-context werden Verknuepfungen am gleichen Tag angezeigt. Bei --sources werden verfuegbare Quellen aufgelistet.
             Ergebnisse werden nach Datum absteigend sortiert.
@method.en   Supports various filters: by date (--from, --to), source (--source), tag (--tag), free text search (--search).
             Two modes: standard query (user_context) and linked query (--tag).
             With --with-context, same-day entries are displayed. With --sources, available sources are listed.
             Results are sorted by date descending.
@reads       user_context, canonical Daten Tabellen
@writes      STDOUT (Abfrageergebnisse)
@limits.de   Abhaengig von Datenverfuegbarkeit in user_context. Keine Datenmanipulation.

@relevance.de  Bietet Kontextabfragen für Gesundheitsdaten, essentiell für die Datenanalyse
@relevance.en  Provides context queries for health data, essential for data analysis
@limits.en   Depends on data availability in user_context. No data manipulation.
@usage
    python3 context_query.py
    python3 context_query.py --from 2026-06-01
    python3 context_query.py --source hrv4training --symptoms
    python3 context_query.py --context "Erschoepfung" --threshold 2
    python3 context_query.py --tag mindful_session --from 2026-01-01
    python3 context_query.py --search "schlecht geschlafen"
    python3 context_query.py --sources
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()


def _trunc(s: str | None, n: int = 80) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def query_context(conn, date_from: str | None, date_to: str | None,
                  source: str | None, tag: str | None,
                  search: str | None, with_symptoms: bool,
                  person: str) -> list[dict]:
    params: list = [person]
    where = ["uc.person = ?"]

    if date_from:
        where.append("uc.date >= ?"); params.append(date_from)
    if date_to:
        where.append("uc.date <= ?"); params.append(date_to)
    if source:
        where.append("uc.source = ?"); params.append(source)
    if tag:
        where.append("uc.tag LIKE ?"); params.append(f"%{tag}%")
    if search:
        where.append("(uc.note LIKE ? OR uc.tag LIKE ?)"); params += [f"%{search}%", f"%{search}%"]

    where_sql = " AND ".join(where)

    if with_symptoms:
        sql = f"""
            SELECT uc.date, uc.source, uc.source_app, uc.tag, uc.note,
                   cws.symptoms_same_day
            FROM user_context uc
            LEFT JOIN context_with_symptoms cws
                ON cws.date = uc.date AND cws.person = uc.person
                AND cws.source = uc.source AND cws.tag IS uc.tag
                AND cws.note IS uc.note
            WHERE {where_sql}
            ORDER BY uc.date DESC, uc.source
        """
    else:
        sql = f"""
            SELECT uc.date, uc.source, uc.source_app, uc.tag, uc.note, NULL
            FROM user_context uc
            WHERE {where_sql}
            ORDER BY uc.date DESC, uc.source
        """

    rows = conn.execute(sql, params).fetchall()
    return [{"date": r[0], "source": r[1], "source_app": r[2],
             "tag": r[3], "note": r[4], "symptoms": r[5]} for r in rows]


def query_by_symptom(conn, symptom: str, threshold: float | None,
                     date_from: str | None, date_to: str | None,
                     person: str) -> list[dict]:
    params: list = [person, f"%{symptom}%"]
    where = ["sc.person = ?", "sc.symptom_de LIKE ?"]

    if threshold is not None:
        where.append("sc.value_num >= ?"); params.append(threshold)
    if date_from:
        where.append("sc.date >= ?"); params.append(date_from)
    if date_to:
        where.append("sc.date <= ?"); params.append(date_to)

    sql = f"""
        SELECT sc.date, sc.symptom_de, sc.value_num, swc.context_notes
        FROM symptoms_canonical sc
        LEFT JOIN symptoms_with_context swc
            ON swc.date = sc.date AND swc.symptom_de = sc.symptom_de
            AND swc.person = sc.person
        WHERE {" AND ".join(where)}
        ORDER BY sc.date DESC
    """
    rows = conn.execute(sql, params).fetchall()
    return [{"date": r[0], "symptom": r[1], "value": r[2], "context": r[3]}
            for r in rows]


def list_sources(conn, person: str) -> None:
    rows = conn.execute("""
        SELECT source, source_app, COUNT(*) AS n,
               SUM(CASE WHEN note IS NOT NULL THEN 1 ELSE 0 END) AS with_note,
               SUM(CASE WHEN tag  IS NOT NULL THEN 1 ELSE 0 END) AS with_tag,
               MIN(date), MAX(date)
        FROM user_context
        WHERE person = ?
        GROUP BY source, source_app
        ORDER BY n DESC
    """, (person,)).fetchall()

    print(t(f"\n{'Quelle':<22} {'App':<22} {'Eintr.':<7} {'Notiz':<7} {'Tag':<7} {'Von':<12} {'Bis'}",
            f"\n{'Source':<22} {'App':<22} {'Entries':<7} {'Note':<7} {'Tag':<7} {'From':<12} {'To'}"))
    print("─" * 90)
    for src, app, n, wn, wt, d0, d1 in rows:
        print(f"  {(src or ''):<20} {(app or ''):<22} {n:<7} {wn:<7} {wt:<7} {d0 or '':<12} {d1 or ''}")
    print(f"\n  {t('Gesamt', 'Total')}: {sum(r[2] for r in rows)} {t('Einträge', 'entries')}")


def print_context_rows(rows: list[dict], with_symptoms: bool) -> None:
    if not rows:
        print(t("  Keine Einträge gefunden.", "  No entries found."))
        return

    print(f"\n  {'Datum':<12} {'Quelle':<18} {'Tag':<22} {'Notiz'}")
    if with_symptoms:
        print(f"  {'':12} {'':18} {'Symptome am gleichen Tag':}")
    print("  " + "─" * 88)

    for r in rows:
        tag  = _trunc(r["tag"], 22)
        note = _trunc(r["note"], 50)
        print(f"  {r['date']:<12} {(r['source'] or ''):<18} {tag:<22} {note}")
        if with_symptoms and r.get("symptoms"):
            print(f"  {'':12} {'':18} → {_trunc(r['symptoms'], 70)}")

    print(f"\n  {t('Gesamt', 'Total')}: {len(rows)} {t('Einträge', 'entries')}")


def print_symptom_rows(rows: list[dict], symptom: str) -> None:
    if not rows:
        print(t(f"  Keine Tage mit '{symptom}' gefunden.", f"  No days with '{symptom}' found."))
        return

    print(f"\n  {'Datum':<12} {'Symptom':<28} {'Wert':<6} {'Kontext-Notizen'}")
    print("  " + "─" * 88)
    for r in rows:
        val = f"{r['value']:.0f}" if r["value"] is not None else "–"
        ctx = _trunc(r["context"], 55) if r["context"] else ""
        print(f"  {r['date']:<12} {r['symptom']:<28} {val:<6} {ctx}")

    print(f"\n  {t('Gesamt', 'Total')}: {len(rows)} {t('Tage', 'days')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("user_context abfragen", "Query user_context"))
    parser.add_argument("--from",     dest="date_from", metavar="DATUM")
    parser.add_argument("--to",       dest="date_to",   metavar="DATUM")
    parser.add_argument("--source",   metavar="QUELLE",
                        help=t("Filter nach Quelle (z.B. hrv4training)",
                               "Filter by source (e.g. hrv4training)"))
    parser.add_argument("--tag",      metavar="TAG",
                        help=t("Filter nach Tag (Teilstring)", "Filter by tag (substring)"))
    parser.add_argument("--search",   metavar="TEXT",
                        help=t("Freitextsuche in Notizen + Tags", "Free-text search in notes + tags"))
    parser.add_argument("--symptoms", action="store_true",
                        help=t("Symptome am gleichen Tag anzeigen", "Show same-day symptoms"))
    parser.add_argument("--symptom",  metavar="SYMPTOM",
                        help=t("Kontext-Einträge an Tagen mit diesem Symptom",
                               "Show context entries on days with this symptom"))
    parser.add_argument("--threshold", type=float, metavar="N",
                        help=t("Mindestschwere für --symptom (0–3)", "Min severity for --symptom (0–3)"))
    parser.add_argument("--sources",  action="store_true",
                        help=t("Verfügbare Quellen auflisten", "List available sources"))
    parser.add_argument("--person",   default=OWN_PERSON_ID)
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA query_only=ON")

    print(t("\n── context_query ──────────────────────────────────────",
            "\n── context_query ──────────────────────────────────────"))

    if args.sources:
        list_sources(conn, args.person)
    elif args.symptom:
        rows = query_by_symptom(conn, args.symptom, args.threshold,
                                args.date_from, args.date_to, args.person)
        print(t(f"  Kontext an Tagen mit '{args.symptom}'",
                f"  Context on days with '{args.symptom}'")
              + (f" ≥{args.threshold:.0f}" if args.threshold else ""))
        print_symptom_rows(rows, args.symptom)
    else:
        rows = query_context(conn, args.date_from, args.date_to,
                             args.source, args.tag, args.search,
                             args.symptoms, args.person)
        print_context_rows(rows, args.symptoms)

    conn.close()


if __name__ == "__main__":
    main()
