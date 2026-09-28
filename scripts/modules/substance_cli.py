#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
substance_cli.py — CLI-Helfer für Substanz-Tracker

@tier        infrastructure
@purpose.de  Bietet gemeinsame CLI-Funktionen für Substanz-Tracker (Medikamente,
             Umweltsubstanzen, Behandlungen). Jeder Tracker hat eigene Felder und
             eine eigene JSON-Datei unter ~/.config/kyoro/.
@purpose.en  Provides common CLI functions for substance trackers (medications,
             environmental substances, treatments). Each tracker has its own fields
             and a separate JSON file under ~/.config/kyoro/.
@method.de   Dieses Modul stellt die wiederkehrende Mechanik bereit: Prompt mit
             Vorschlägen, Datumsparsing, Laden/Speichern, Status/Zeitraum-Formatierung
             für die Tabellenansicht, Person-Auswahl.
@method.en   This module provides recurring mechanics: prompt with suggestions, date
             parsing, loading/saving, status/period formatting for table view,
             person selection.
@reads       ~/.config/kyoro/*.json (verschiedene Tracker-Dateien)
@writes      ~/.config/kyoro/*.json (verschiedene Tracker-Dateien)

@limits.de   Internes Hilfsmodul. Direkte Nutzung nur ueber Substanz-Tracker-Skripte vorgesehen.

@relevance.de  Bietet Substanzverarbeitungsfunktionen, essentiell für die pharmazeutische Analyse
@relevance.en  Provides substance processing functions, essential for pharmaceutical analysis
@limits.en   Internal helper module. Intended for use through substance tracker scripts only.
@usage
    python substance_cli.py
    python substance_cli.py --help
    python substance_cli.py --from 2024-01-01 --to 2024-12-31
"""
import json
import sys
from datetime import date
from pathlib import Path

from modules.base import resolve_person
from modules.i18n import t


def load(file_path: Path) -> list[dict]:
    if file_path.exists():
        return json.loads(file_path.read_text(encoding="utf-8"))
    return []


def save(file_path: Path, entries: list[dict]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(t(f"Gespeichert: {file_path}", f"Saved: {file_path}"))


def add_person_arg(ap) -> None:
    """--person Flag registrieren (Standard: eigene Person; 'all' zeigt bei list/export alle)."""
    ap.add_argument(
        "--person", metavar="ID", default=None,
        help=t(
            "Person-ID (Standard: eigene). 'all' bei list/export zeigt alle Personen.",
            "Person ID (default: own). Use 'all' with list/export to show every person.",
        ),
    )


def entry_person(e: dict) -> str:
    """Person-ID eines Eintrags — Alteinträge ohne 'person'-Feld gelten als eigene."""
    return e.get("person") or resolve_person(None)


def is_active(e: dict) -> bool:
    date_to = e.get("date_to", "")
    if not date_to:
        return True
    try:
        return date.fromisoformat(date_to[:10]) >= date.today()
    except ValueError:
        return True


def parse_date(s: str, end: bool = False) -> str | None:
    """Parses date or date+time input into stored ISO form.

    Accepts YYYY, YYYY-MM, YYYY-MM-DD, or YYYY-MM-DD HH:MM (also 'T' separator).
    A time component only makes sense together with a full day — year/month-only
    input ignores any trailing time.
    """
    s = s.strip()
    if not s:
        return None

    date_part, time_part = s, ""
    for sep in ("T", " "):
        if sep in s:
            head, _, tail = s.partition(sep)
            if ":" in tail:
                date_part, time_part = head.strip(), tail.strip()
            break

    if len(date_part) == 7:  # YYYY-MM
        yr, mo = int(date_part[:4]), int(date_part[5:7])
        if end:
            import calendar
            day = calendar.monthrange(yr, mo)[1]
            return f"{yr:04d}-{mo:02d}-{day:02d}"
        return f"{yr:04d}-{mo:02d}-01"
    if len(date_part) == 4:
        return f"{date_part}-12-31" if end else f"{date_part}-01-01"
    if time_part:
        return f"{date_part}T{time_part}"
    return date_part


def prompt(label: str, default: str = "", choices: list[str] | None = None) -> str:
    if choices:
        print(t(f"\n  Vorschläge für {label}:", f"\n  Suggestions for {label}:"))
        for i, c in enumerate(choices, 1):
            print(f"    {i:2}. {c}")
        print(t("    (oder freie Eingabe)", "    (or free text)"))

    dflt_str = f" [{default}]" if default else ""
    try:
        sys.stdout.write(f"  {label}{dflt_str}: ")
        sys.stdout.flush()
        raw = sys.stdin.buffer.readline()
        val = raw.decode("utf-8", errors="replace").rstrip("\n").strip()
    except (EOFError, KeyboardInterrupt, AttributeError):
        try:
            val = input(f"  {label}{dflt_str}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

    if choices and val.isdigit():
        idx = int(val) - 1
        if 0 <= idx < len(choices):
            return choices[idx]

    return val or default


def status_tag(e: dict) -> str:
    return t("[AKTIV]   ", "[ACTIVE]  ") if is_active(e) else t("[BEENDET] ", "[ENDED]   ")


def fmt_period(e: dict) -> str:
    """Full precision (day, plus HH:MM if the entry recorded a time)."""
    d1 = e.get("date_from") or ""
    d2 = e.get("date_to") or ""
    if not d1 and not d2:
        return "—"
    if not d2:
        return f"ab {d1}"
    return f"{d1} – {d2}"


def get_idx(args_list: list[str], entries: list[dict], prompt_text: str, list_fn) -> int:
    if args_list and args_list[0].isdigit():
        return int(args_list[0])
    list_fn(entries)
    try:
        return int(input(f"  {prompt_text} ").strip())
    except (ValueError, EOFError, KeyboardInterrupt):
        sys.exit(0)
