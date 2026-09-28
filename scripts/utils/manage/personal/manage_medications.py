#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_medications.py — Medikamente und Ergänzungsmittel verwalten

@tier        infrastructure
@purpose.de  Verwaltet Medikamente, Nahrungsergänzungsmittel und pflanzliche Präparate
             in einer lokalen JSON-Datei. Ermöglicht das Erfassen von Einnahmezeiträumen
             und Dosierungen für die Korrelation mit Gesundheitsdaten.
@purpose.en  Manages medications, supplements, and herbal preparations in a local
             JSON file. Enables tracking of intake periods and dosages for correlation
             with health data.
@method.de   Speichert unter KYORO_CONFIG_DIR/medication_history.json (lokal, nicht im Repo).
             Unterstützt verschiedene Kategorien und Dosierungsangaben.
@method.en   Stores in KYORO_CONFIG_DIR/medication_history.json (local only, not in repo).
             Supports various categories and dosage specifications.
@reads       KYORO_CONFIG_DIR/medication_history.json
@writes      KYORO_CONFIG_DIR/medication_history.json
@limits.de   Lokale Datei. Keine automatische Validierung.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Local file only. No automatic validation.
@usage
    python3 scripts/utils/manage/personal/manage_medications.py list [--active]
    python3 scripts/utils/manage/personal/manage_medications.py add
    python3 scripts/utils/manage/personal/manage_medications.py edit 3
    python3 scripts/utils/manage/personal/manage_medications.py stop 3
    python3 scripts/utils/manage/personal/manage_medications.py delete 3
    python3 scripts/utils/manage/personal/manage_medications.py export [--active]
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

MED_FILE = KYORO_CONFIG_DIR / "medication_history.json"

# ── Wissensbasis für Vorschläge ───────────────────────────────────────────────

CATEGORIES = [
    "Medikament (Rx)",
    "Medikament (OTC)",
    "Nahrungsergänzungsmittel",
    "Pflanzliches Präparat",
    "Homöopathie",
    "Verhütungsmittel",
    "Impfstoff",
    "Notfallmedikament",
]

FREQUENCIES = [
    "1× täglich",
    "2× täglich",
    "3× täglich",
    "wöchentlich",
    "alle 2 Wochen",
    "monatlich",
    "bei Bedarf",
    "saisonal",
]

TIMINGS = [
    "morgens nüchtern",
    "morgens mit Mahlzeit",
    "abends",
    "mittags",
    "morgens + abends",
    "zu den Mahlzeiten",
    "vor dem Schlafen",
    "bei Bedarf",
    "subkutan (wöchentlich)",
]

INDICATIONS = [
    "Hypothyreose",
    "Diabetes / Insulinresistenz",
    "Depression / Schmerz",
    "Fatigue / Energie",
    "Autoimmun / Entzündung",
    "Eisenmangel",
    "Vitamin-D-Mangel",
    "Magnesium / Nerven",
    "Herzrhythmus",
    "Schlaf",
    "Darm / Dysbiose",
    "Prävention",
]

PRESCRIBERS = [
    "Rheumatologe",
    "Kardiologe",
    "Hausarzt",
    "Psychiatrie",
    "Neurologe",
    "Endokrinologe",
    "Selbst / OTC",
    "Apotheke",
]


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    return _load_file(MED_FILE)


def save(entries: list[dict]) -> None:
    _save_file(MED_FILE, entries)


def _short_label(e: dict) -> str:
    name = e.get("name", "")
    wi = e.get("wirkstoff", "")
    if wi and wi.lower() != name.lower():
        return f"{name} ({wi})"
    return name


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
        f"\n  {'#':>3}  {'Status':<10} {'Person':<12} {'Name (Wirkstoff)':<30} {'Kategorie':<24} {'Dosis + Frequenz':<24} {'Zeitraum'}",
        f"\n  {'#':>3}  {'Status':<10} {'Person':<12} {'Name (substance)':<30} {'Category':<24} {'Dose + Frequency':<24} {'Period'}",
    ))
    print("  " + "─" * 110)

    orig_idx = 0
    for e in entries:
        orig_idx += 1
        if active_only and not _is_active(e):
            continue
        if person != "all" and _entry_person(e) != person:
            continue
        dosis_freq = f"{e.get('dosis','—')} / {e.get('frequenz','—')}"
        print(
            f"  {orig_idx:>3}  {_status_tag(e)}"
            f"{_entry_person(e):<12} "
            f"{_short_label(e):<30} "
            f"{e.get('kategorie',''):<24} "
            f"{dosis_freq:<24} "
            f"{_fmt_period(e)}"
        )
        extra = []
        if e.get("einnahme_zeitpunkt"):
            extra.append(e["einnahme_zeitpunkt"])
        if e.get("indikation"):
            extra.append(f"Ind: {e['indikation']}")
        if e.get("verordnet_von"):
            extra.append(f"Verordnet: {e['verordnet_von']}")
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

    name = _prompt(t("Name (Handelsname)", "Name (brand name)"))
    if not name:
        print(t("Abgebrochen.", "Cancelled."))
        return entries

    person = _prompt(t("Person-ID", "Person ID"), default=default_person)
    wirkstoff = _prompt(t("Wirkstoff(e)", "Active ingredient(s)"), default=name)
    kategorie = _prompt(t("Kategorie", "Category"), choices=CATEGORIES)
    dosis = _prompt(t("Dosis (z.B. '75 µg', '500 mg')", "Dose (e.g. '75 µg', '500 mg')"))
    frequenz = _prompt(t("Frequenz", "Frequency"), choices=FREQUENCIES)
    zeitpunkt = _prompt(t("Einnahme-Zeitpunkt", "Timing"), choices=TIMINGS)
    indikation = _prompt(t("Indikation / Wofür", "Indication / Purpose"), choices=INDICATIONS)
    verordnet = _prompt(t("Verordnet von", "Prescribed by"), choices=PRESCRIBERS)

    date_from_raw = _prompt(t("Beginn (YYYY-MM-DD [HH:MM] / YYYY-MM / leer = heute)", "Start (YYYY-MM-DD [HH:MM] / YYYY-MM / empty = today)"))
    date_from = _parse_date(date_from_raw) or date.today().isoformat()

    date_to_raw = _prompt(t("Ende (YYYY-MM-DD [HH:MM] / leer = noch aktiv)", "End date (YYYY-MM-DD [HH:MM] / empty = still active)"))
    date_to = _parse_date(date_to_raw, end=True) or ""

    notes = _prompt(t("Notiz (optional)", "Notes (optional)")) or None

    entry: dict = {
        "person":             person,
        "name":               name,
        "wirkstoff":          wirkstoff if wirkstoff != name else "",
        "kategorie":          kategorie,
        "dosis":              dosis,
        "frequenz":           frequenz,
        "einnahme_zeitpunkt": zeitpunkt,
        "indikation":         indikation,
        "verordnet_von":      verordnet,
        "date_from":          date_from,
        "date_to":            date_to,
        "notes":              notes,
    }

    print(f"\n  → {_short_label(entry)}  {dosis} / {frequenz}  [{_fmt_period(entry)}]")
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
    print(f"  {_short_label(e)}  {e.get('dosis','')}  [{_fmt_period(e)}]")

    fields = [
        ("person",             t("Person-ID", "Person ID"),               None),
        ("name",               t("Name", "Name"),                         None),
        ("wirkstoff",          t("Wirkstoff", "Active ingredient"),       None),
        ("kategorie",          t("Kategorie", "Category"),                CATEGORIES),
        ("dosis",              t("Dosis", "Dose"),                        None),
        ("frequenz",           t("Frequenz", "Frequency"),                FREQUENCIES),
        ("einnahme_zeitpunkt", t("Einnahme-Zeitpunkt", "Timing"),        TIMINGS),
        ("indikation",         t("Indikation", "Indication"),             INDICATIONS),
        ("verordnet_von",      t("Verordnet von", "Prescribed by"),      PRESCRIBERS),
        ("date_from",          t("Beginn", "Start"),                      None),
        ("date_to",            t("Ende (leer = noch aktiv)", "End date"), None),
        ("notes",              t("Notiz", "Notes"),                       None),
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
    """Setzt date_to = heute — Medikament als beendet markieren ohne zu löschen."""
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
        "| Person | Medikament | Wirkstoff | Kategorie | Dosis | Frequenz | Einnahme | Indikation | Verordnet von | Seit | Bis |",
        "| Person | Medication | Substance | Category | Dose | Frequency | Timing | Indication | Prescribed by | From | To |",
    )
    sep = "|---|---|---|---|---|---|---|---|---|---|---|"
    print(header)
    print(sep)
    for e in shown:
        cols = [
            _entry_person(e),
            e.get("name", ""),
            e.get("wirkstoff", ""),
            e.get("kategorie", ""),
            e.get("dosis", ""),
            e.get("frequenz", ""),
            e.get("einnahme_zeitpunkt", ""),
            e.get("indikation", ""),
            e.get("verordnet_von", ""),
            (e.get("date_from") or "")[:7],
            (e.get("date_to") or "")[:7] or "—",
        ]
        print("| " + " | ".join(cols) + " |")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t(
            "Medikamente und Nahrungsergänzungsmittel verwalten (~/.config/kyoro/medication_history.json)",
            "Manage medications and supplements (~/.config/kyoro/medication_history.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  list [--active]   Alle oder nur aktive Einträge anzeigen
  add               Interaktiv neuen Eintrag anlegen
  edit <nr>         Eintrag bearbeiten
  stop <nr>         Als beendet markieren (date_to = heute)
  delete <nr>       Eintrag löschen
  export [--active] Markdown-Tabelle für Arztbriefe ausgeben
""", """
Commands:
  list [--active]   Show all or only active entries
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
                    help=t("Nur aktive Einträge", "Only active entries"))
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
