#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_treatments.py — Therapie-Einträge verwalten


@tier        infrastructure
@purpose.de  Verwaltet Therapie-Termine (Physiotherapie, Osteopathie, Massage, etc.).
             Ermöglicht das Erfassen von Einzelterminen mit Uhrzeit oder laufenden Kuren
             über mehrere Tage/Wochen. Daten können mit HRV/Symptomen korreliert werden.
@purpose.en  Manages session entries (physiotherapy, osteopathy, massage, etc.).
             Supports single appointments with time or ongoing courses over days/weeks.
             Data can be correlated with HRV/symptoms.
@method.de   Einzeltermine (z.B. Osteopathie 15:00-16:00) und laufende Kuren werden über
             date_from/date_to Feld erfasst. Uhrzeit ist optional. Speichert in
             ~/.config/kyoro/treatment_history.json (lokal, nicht im Repo).
@method.en   Single appointments (e.g., osteopathy 15:00-16:00) and ongoing courses are
             captured via date_from/date_to fields. Time is optional. Stores in
             ~/.config/kyoro/treatment_history.json (local only, not in repo).
@reads       ~/.config/kyoro/treatment_history.json
@writes      ~/.config/kyoro/treatment_history.json
@limits.de   Lokale Datei. Keine automatische Validierung.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Local file only. No automatic validation.
@usage
    python3 scripts/utils/manage/personal/manage_treatments.py list [--active]
    python3 scripts/utils/manage/personal/manage_treatments.py add
    python3 scripts/utils/manage/personal/manage_treatments.py edit 3
    python3 scripts/utils/manage/personal/manage_treatments.py stop 3
    python3 scripts/utils/manage/personal/manage_treatments.py delete 3
    python3 scripts/utils/manage/personal/manage_treatments.py export [--active]
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import KYORO_CONFIG_DIR
from modules.substance_cli import (
    load as _load_file,
    save as _save_file,
    is_active as _is_active,
    parse_date as _parse_date,
    prompt as _prompt,
    status_tag as _status_tag,
    fmt_period as _fmt_period,
    get_idx as _get_idx,
    add_person_arg as _add_person_arg,
    entry_person as _entry_person,
)
from modules.base import resolve_person as _resolve_person

TREATMENT_FILE = KYORO_CONFIG_DIR / "treatment_history.json"

# ── Wissensbasis für Vorschläge ───────────────────────────────────────────────

CATEGORIES = [
    "Physiotherapie",
    "Osteopathie",
    "Massage",
    "Chiropraktik",
    "Akupunktur",
    "Reiki / Energiearbeit",
    "Ergotherapie",
    "Logopädie",
    "Psychotherapie",
    "Heilpraktiker",
    "Sonstiges",
]

PRACTITIONERS = [
    "Physiotherapeut/in",
    "Osteopath/in",
    "Heilpraktiker/in",
    "Psychotherapeut/in",
    "Rheumatologe",
    "Kardiologe",
    "Hausarzt",
    "Selbst",
]


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    return _load_file(TREATMENT_FILE)


def save(entries: list[dict]) -> None:
    _save_file(TREATMENT_FILE, entries)


def _short_label(e: dict) -> str:
    return e.get("name", "")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(entries: list[dict], active_only: bool = False, person: str = "all") -> None:
    shown = [
        e for e in entries
        if (not active_only or _is_active(e))
        and (person == "all" or _entry_person(e) == person)
    ]
    if not shown:
        msg = (
            t("Keine aktiven Einträge.", "No active entries.")
            if active_only
            else t("Noch keine Einträge. Mit 'add' beginnen.", "No entries yet. Use 'add' to start.")
        )
        print(msg)
        return

    print(t(
        f"\n  {'#':>3}  {'Status':<10} {'Person':<12} {'Sitzung':<24} {'Kategorie':<20} {'Behandler':<20} {'Zeitraum'}",
        f"\n  {'#':>3}  {'Status':<10} {'Person':<12} {'Session':<24} {'Category':<20} {'Practitioner':<20} {'Period'}",
    ))
    print("  " + "─" * 110)

    orig_idx = 0
    for e in entries:
        orig_idx += 1
        if active_only and not _is_active(e):
            continue
        if person != "all" and _entry_person(e) != person:
            continue
        print(
            f"  {orig_idx:>3}  {_status_tag(e)}"
            f"{_entry_person(e):<12} "
            f"{_short_label(e):<24} "
            f"{e.get('kategorie',''):<20} "
            f"{e.get('behandler',''):<20} "
            f"{_fmt_period(e)}"
        )
        extra = []
        if e.get("indikation"):
            extra.append(f"Ind: {e['indikation']}")
        if e.get("notes"):
            extra.append(e["notes"])
        if extra:
            print(f"       ↳ {' | '.join(extra)}")
    print()


def cmd_add(entries: list[dict], default_person: str) -> list[dict]:
    print(t(
        "\n── Neuer Eintrag ────────────────────────────────────",
        "\n── New entry ────────────────────────────────────────",
    ))

    name = _prompt(t("Behandlung (z.B. 'Osteopathie-Termin', '6 Wochen Physiotherapie')",
                     "Treatment (e.g. 'osteopathy session', '6 weeks physiotherapy')"))
    if not name:
        print(t("Abgebrochen.", "Cancelled."))
        return entries

    person = _prompt(t("Person-ID", "Person ID"), default=default_person)
    kategorie = _prompt(t("Kategorie", "Category"), choices=CATEGORIES)
    behandler = _prompt(t("Behandler/in", "Practitioner"), choices=PRACTITIONERS)
    indikation = _prompt(t("Indikation / Wofür (optional)", "Indication / Purpose (optional)"))

    date_from_raw = _prompt(t(
        "Beginn (YYYY-MM-DD [HH:MM] für Einzeltermin / YYYY-MM-DD für Kur / leer = heute)",
        "Start (YYYY-MM-DD [HH:MM] for a single session / YYYY-MM-DD for a course / empty = today)",
    ))
    date_from = _parse_date(date_from_raw) or date.today().isoformat()

    date_to_raw = _prompt(t(
        "Ende (YYYY-MM-DD [HH:MM] / leer = noch laufend)",
        "End (YYYY-MM-DD [HH:MM] / empty = still ongoing)",
    ))
    date_to = _parse_date(date_to_raw, end=True) or ""

    notes = _prompt(t("Notiz (optional)", "Notes (optional)")) or None

    entry: dict = {
        "person":     person,
        "name":       name,
        "kategorie":  kategorie,
        "behandler":  behandler,
        "indikation": indikation,
        "date_from":  date_from,
        "date_to":    date_to,
        "notes":      notes,
    }

    print(f"\n  → {_short_label(entry)}  {kategorie}  [{_fmt_period(entry)}]")
    confirm = input(t("  Speichern? [J/n]: ", "  Save? [Y/n]: ")).strip().lower()
    if confirm in ("", "j", "y", "ja", "yes"):
        entries.append(entry)
        print(t(f"  Hinzugefügt (Eintrag #{len(entries)})", f"  Added (entry #{len(entries)})"))
    else:
        print(t("  Abgebrochen.", "  Cancelled."))

    return entries


def cmd_edit(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    e = entries[idx - 1]
    print(t(f"\n── Eintrag #{idx} bearbeiten (Enter = unverändert) ──",
            f"\n── Edit entry #{idx} (Enter = keep unchanged) ──"))
    print(f"  {_short_label(e)}  [{_fmt_period(e)}]")

    fields = [
        ("person",     t("Person-ID", "Person ID"),        None),
        ("name",       t("Behandlung", "Treatment"),       None),
        ("kategorie",  t("Kategorie", "Category"),          CATEGORIES),
        ("behandler",  t("Behandler/in", "Practitioner"),  PRACTITIONERS),
        ("indikation", t("Indikation", "Indication"),       None),
        ("date_from",  t("Beginn", "Start"),                None),
        ("date_to",    t("Ende (leer = noch laufend)", "End date"), None),
        ("notes",      t("Notiz", "Notes"),                 None),
    ]
    for key, label, choices in fields:
        default = _entry_person(e) if key == "person" else (e.get(key) or "")
        new_val = _prompt(label, default=default, choices=choices)
        if key in ("date_from", "date_to") and new_val:
            new_val = _parse_date(new_val, end=(key == "date_to")) or new_val
        if key == "date_to" and new_val == "":
            e[key] = ""
        elif new_val:
            e[key] = new_val

    entries[idx - 1] = e
    print(t("  Aktualisiert.", "  Updated."))
    return entries


def cmd_stop(entries: list[dict], idx: int) -> list[dict]:
    """Setzt date_to = heute — Behandlung als beendet markieren ohne zu löschen."""
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    e = entries[idx - 1]
    today = date.today().isoformat()
    e["date_to"] = today
    entries[idx - 1] = e
    print(t(f"  Beendet: {_short_label(e)} — date_to = {today}",
            f"  Stopped: {_short_label(e)} — date_to = {today}"))
    return entries


def cmd_delete(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    removed = entries.pop(idx - 1)
    print(t(f"Gelöscht: {_short_label(removed)}", f"Deleted: {_short_label(removed)}"))
    return entries


def cmd_export(entries: list[dict], active_only: bool = False, person: str = "all") -> None:
    """Gibt eine Markdown-Tabelle für Arztbriefe aus."""
    shown = [
        e for e in entries
        if (not active_only or _is_active(e))
        and (person == "all" or _entry_person(e) == person)
    ]
    if not shown:
        print(t("Keine Einträge.", "No entries."))
        return

    header = t(
        "| Person | Behandlung | Kategorie | Behandler | Indikation | Seit | Bis |",
        "| Person | Treatment | Category | Practitioner | Indication | From | To |",
    )
    sep = "|---|---|---|---|---|---|---|"
    print(header)
    print(sep)
    for e in shown:
        cols = [
            _entry_person(e),
            e.get("name", ""),
            e.get("kategorie", ""),
            e.get("behandler", ""),
            e.get("indikation", ""),
            e.get("date_from") or "",
            e.get("date_to") or "—",
        ]
        print("| " + " | ".join(cols) + " |")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t(
            "Sitzungen verwalten (~/.config/kyoro/treatment_history.json)",
            "Manage sessions (~/.config/kyoro/treatment_history.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  list [--active]   Alle oder nur aktive/laufende Einträge anzeigen
  add               Interaktiv neuen Eintrag anlegen
  edit <nr>         Eintrag bearbeiten
  stop <nr>         Als beendet markieren (date_to = heute)
  delete <nr>       Eintrag löschen
  export [--active] Markdown-Tabelle für Arztbriefe ausgeben
""", """
Commands:
  list [--active]   Show all or only active/ongoing entries
  add               Interactively add a new entry
  edit <nr>         Edit an entry
  stop <nr>         Mark as stopped (date_to = today)
  delete <nr>       Delete an entry
  export [--active] Output Markdown table for doctor's letters
"""),
    )
    ap.add_argument("command",
                    choices=["list", "add", "edit", "stop", "delete", "export"],
                    help=t("Aktion", "Action"))
    ap.add_argument("args", nargs="*",
                    help=t("Zusatzargument: Eintragsnummer", "Extra argument: entry number"))
    ap.add_argument("--active", action="store_true",
                    help=t("Nur aktive/laufende Sitzungen", "Only active/ongoing sessions"))
    _add_person_arg(ap)
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    entries = load()
    person = _resolve_person(args.person)

    if args.command == "list":
        cmd_list(entries, active_only=args.active, person=person)

    elif args.command == "add":
        entries = cmd_add(entries, default_person=person)
        save(entries)

    elif args.command == "edit":
        idx = _get_idx(args.args, entries, t("Welche Nummer bearbeiten?", "Which number to edit?"), cmd_list)
        entries = cmd_edit(entries, idx)
        save(entries)

    elif args.command == "stop":
        idx = _get_idx(args.args, entries, t("Welche Nummer beenden?", "Which number to stop?"), cmd_list)
        entries = cmd_stop(entries, idx)
        save(entries)

    elif args.command == "delete":
        idx = _get_idx(args.args, entries, t("Welche Nummer löschen?", "Which number to delete?"), cmd_list)
        entries = cmd_delete(entries, idx)
        save(entries)

    elif args.command == "export":
        cmd_export(entries, active_only=args.active, person=person)


if __name__ == "__main__":
    main()
