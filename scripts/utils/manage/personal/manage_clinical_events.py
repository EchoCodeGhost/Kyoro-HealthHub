#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_clinical_events.py — Gesundheitsereignisse verwalten


@tier        infrastructure
@purpose.de  Verwaltet Gesundheitsereignisse (z.B. Infektionen, Behandlungen, Eingriffe)
             in einer lokalen JSON-Datei. Ermöglicht das Hinzufügen, Bearbeiten, Löschen
             und Exportieren von Ereignissen für die Dokumentation.
@purpose.en  Manages health events (e.g., infections, treatments, procedures) in a local
             JSON file. Allows adding, editing, deleting, and exporting events for documentation.
@method.de   Speichert Ereignisse unter ~/.config/kyoro/clinical_events.json (lokal, wird nicht
             ins Repo committed). Unterstützt verschiedene Ereignistypen mit Datum, Beschreibung
             und Tags. Export als Markdown-Tabelle möglich.
@method.en   Stores events in ~/.config/kyoro/clinical_events.json (local only, not committed
             to repo). Supports various event types with date, description, and tags.
             Export as Markdown table available.
@reads       ~/.config/kyoro/clinical_events.json
@writes      ~/.config/kyoro/clinical_events.json
@limits.de   Lokale Datei, wird nicht in die Datenbank oder Versionierung aufgenommen.
             Keine automatische Validierung der Eingaben.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Local file only, not stored in database or version control.
             No automatic validation of inputs.
@usage
    python3 scripts/utils/manage/personal/manage_clinical_events.py list
    python3 scripts/utils/manage/personal/manage_clinical_events.py add
    python3 scripts/utils/manage/personal/manage_clinical_events.py edit 3
    python3 scripts/utils/manage/personal/manage_clinical_events.py delete 3
    python3 scripts/utils/manage/personal/manage_clinical_events.py export
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import KYORO_CONFIG_DIR

EVENTS_FILE = KYORO_CONFIG_DIR / "clinical_events.json"

# ── Typen ─────────────────────────────────────────────────────────────────────

EVENT_TYPES = [
    "infection",
    "reinfection",
    "diagnosis",
    "medication_start",
    "medication_stop",
    "relapse",
    "hospitalization",
    "surgery",
    "symptom_onset",
    "remission",
    "vaccination",
    "other",
]

TYPE_LABELS = {
    "infection":        t("Infektion",              "Infection"),
    "reinfection":      t("Reinfektion",            "Reinfection"),
    "diagnosis":        t("Diagnose",               "Diagnosis"),
    "medication_start": t("Medikament Start",       "Medication start"),
    "medication_stop":  t("Medikament Stop",        "Medication stop"),
    "relapse":          t("Rückfall / Schub",       "Relapse / flare"),
    "hospitalization":  t("Krankenhausaufenthalt",  "Hospitalization"),
    "surgery":          t("Operation",              "Surgery"),
    "symptom_onset":    t("Symptombeginn",          "Symptom onset"),
    "remission":        t("Remission",              "Remission"),
    "vaccination":      t("Impfung",                "Vaccination"),
    "other":            t("Sonstiges",              "Other"),
}

SPECIALTIES = [
    "Hausarzt",
    "Krankenhaus / Notaufnahme",
    "Rheumatologe",
    "Kardiologe",
    "Neurologe",
    "Psychiatrie",
    "Endokrinologe",
    "HNO",
    "Orthopäde",
    "Selbst / Eigendiagnose",
]

# Vorschläge für den Ereignisnamen, je nach Typ
EVENT_SUGGESTIONS: dict[str, list[str]] = {
    "infection": [
        "COVID-19", "Influenza A", "Influenza B", "EBV-Mononukleose",
        "Borreliose", "FSME", "Ornithose", "Q-Fieber", "Windpocken",
        "Masern", "Mumps", "Röteln", "Scharlach", "Keuchhusten",
        "RSV", "Norovirus", "Campylobacter", "Pneumonie atypisch",
    ],
    "reinfection": [
        "COVID-19 Reinfektion", "Influenza A Reinfektion",
        "EBV-Reaktivierung", "HSV-Reaktivierung", "VZV-Zoster",
    ],
    "diagnosis": [
        "Long COVID / PQFS", "ME/CFS", "MCAS", "Sjögren-Syndrom",
        "Hashimoto-Thyreoiditis", "APS (Antiphospholipid-Syndrom)",
        "Fibromyalgie", "POTS", "Dysautonomie", "Borreliose (Post-Lyme)",
        "Q-Fieber chronisch", "Vorhofflimmern", "SFN (Small Fiber Neuropathie)",
        "Rosacea", "Zöliakie (Verdacht)", "SIBO",
    ],
    "medication_start": [
        "Hydroxychloroquin (HCQ)", "Naltrexon LDN", "Metformin", "Doxycyclin",
        "Azithromycin", "Antihistaminikum H1", "Antihistaminikum H2",
        "Vitamin D Hochdosis", "Prednisolon", "Ibuprofen", "Aspirin",
    ],
    "vaccination": [
        "FSME", "COVID-19 mRNA", "Influenza", "Pneumokokken",
        "Hepatitis A", "Hepatitis B", "Tetanus/Td", "Pertussis (Tdap)",
        "Meningokokken ACWY", "Meningokokken B", "Dengue (Qdenga)",
        "Gelbfieber", "Typhus oral", "Tollwut",
    ],
    "relapse":       ["ME/CFS-Schub", "MCAS-Schub", "PEM-Episode", "Vorhofflimmern-Episode"],
    "symptom_onset": ["Fatigue chronisch", "Brain Fog", "PEM", "POTS-Symptome", "Sicca", "Dyspnoe"],
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    if EVENTS_FILE.exists():
        return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    return []


def save(entries: list[dict]) -> None:
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    sorted_entries = sorted(entries, key=lambda e: e.get("date") or "")
    EVENTS_FILE.write_text(
        json.dumps(sorted_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(t(f"Gespeichert: {EVENTS_FILE}", f"Saved: {EVENTS_FILE}"))


def _parse_date(s: str, end: bool = False) -> str | None:
    s = s.strip()
    if not s:
        return None
    if len(s) == 7:  # YYYY-MM
        yr, mo = int(s[:4]), int(s[5:7])
        if end:
            import calendar
            day = calendar.monthrange(yr, mo)[1]
            return f"{yr:04d}-{mo:02d}-{day:02d}"
        return f"{yr:04d}-{mo:02d}-01"
    if len(s) == 4:
        return f"{s}-12-31" if end else f"{s}-01-01"
    return s


def _prompt(label: str, default: str = "", choices: list[str] | None = None) -> str:
    if choices:
        print(t(f"\n  Auswahl für {label}:", f"\n  Choices for {label}:"))
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


def _fmt_period(e: dict) -> str:
    d1 = (e.get("date") or "")[:10]
    d2 = (e.get("date_end") or "")[:10]
    if not d1:
        return "—"
    if not d2:
        return d1
    return f"{d1} – {d2}"


def _type_label(e: dict) -> str:
    return TYPE_LABELS.get(e.get("type", ""), e.get("type", "?"))


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(entries: list[dict]) -> None:
    sorted_entries = sorted(entries, key=lambda e: e.get("date") or "")
    if not sorted_entries:
        print(t("Noch keine Ereignisse. Mit 'add' beginnen.", "No events yet. Use 'add' to start."))
        return

    print(t(
        f"\n  {'#':>3}  {'Datum':<13}  {'Typ':<24}  {'Name'}",
        f"\n  {'#':>3}  {'Date':<13}  {'Type':<24}  {'Name'}",
    ))
    print("  " + "─" * 90)

    for orig_idx, e in enumerate(entries, 1):
        _sorted_pos = sorted_entries.index(e) + 1  # noqa: F841
        date_str = _fmt_period(e)
        typ = _type_label(e)
        name = e.get("name", "")
        print(f"  {orig_idx:>3}  {date_str:<13}  {typ:<24}  {name}")
        extras = []
        if e.get("ort"):
            extras.append(e["ort"])
        if e.get("notes"):
            extras.append(e["notes"])
        if extras:
            print(f"       ↳ {' | '.join(extras)}")
    print()


def cmd_add(entries: list[dict]) -> list[dict]:
    print(t(
        "\n── Neues Ereignis ───────────────────────────────────",
        "\n── New clinical event ───────────────────────────────",
    ))

    type_choices = [f"{k}  ({TYPE_LABELS[k]})" for k in EVENT_TYPES]
    raw_type = _prompt(t("Typ", "Type"), choices=type_choices)
    event_type = raw_type.split()[0] if raw_type.split() else raw_type

    suggestions = EVENT_SUGGESTIONS.get(event_type, [])
    name = _prompt(t("Name / Bezeichnung", "Name / label"),
                   choices=suggestions or None)
    if not name:
        print(t("Abgebrochen.", "Cancelled."))
        return entries

    date_raw = _prompt(t("Datum (YYYY-MM-DD / YYYY-MM / YYYY)", "Date (YYYY-MM-DD / YYYY-MM / YYYY)"))
    date_val = _parse_date(date_raw) or ""

    date_end_raw = _prompt(t("Enddatum (leer = Einzeldatum)", "End date (empty = single date)"))
    date_end = _parse_date(date_end_raw, end=True) or ""

    ort = _prompt(t("Ort / Einrichtung (optional)", "Location / facility (optional)"),
                  choices=SPECIALTIES)
    notes = _prompt(t("Notiz (optional)", "Notes (optional)")) or None

    entry: dict = {
        "name":     name,
        "date":     date_val,
        "type":     event_type,
    }
    if date_end:
        entry["date_end"] = date_end
    if ort:
        entry["ort"] = ort
    if notes:
        entry["notes"] = notes

    print(f"\n  → {_fmt_period(entry)}  [{_type_label(entry)}]  {name}")
    try:
        confirm = input(t("  Speichern? [J/n]: ", "  Save? [Y/n]: ")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(t("\n  Abgebrochen.", "\n  Cancelled."))
        sys.exit(0)
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
    print(f"  {_fmt_period(e)}  [{_type_label(e)}]  {e.get('name', '')}")

    type_choices = [f"{k}  ({TYPE_LABELS[k]})" for k in EVENT_TYPES]
    raw_type = _prompt(t("Typ", "Type"), default=e.get("type", ""), choices=type_choices)
    event_type = raw_type.split()[0] if raw_type.split() else raw_type
    if event_type:
        e["type"] = event_type

    fields: list[tuple[str, str, bool]] = [
        ("name",     t("Name / Bezeichnung", "Name / label"),         False),
        ("date",     t("Datum", "Date"),                              False),
        ("date_end", t("Enddatum (leer = entfernen)", "End date (empty = remove)"), True),
        ("ort",      t("Ort / Einrichtung", "Location / facility"),   False),
        ("notes",    t("Notiz", "Notes"),                             False),
    ]
    for key, label, removable in fields:
        new_val = _prompt(label, default=e.get(key) or "")
        if key in ("date", "date_end") and new_val:
            new_val = _parse_date(new_val, end=(key == "date_end")) or new_val
        if removable and new_val == "":
            e.pop(key, None)
        elif new_val:
            e[key] = new_val

    entries[idx - 1] = e
    print(t("  Aktualisiert.", "  Updated."))
    return entries


def cmd_delete(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    removed = entries.pop(idx - 1)
    print(t(f"Gelöscht: {removed.get('name', '')}", f"Deleted: {removed.get('name', '')}"))
    return entries


def cmd_export(entries: list[dict]) -> None:
    """Markdown-Tabelle in chronologischer Reihenfolge für Arztbriefe."""
    sorted_entries = sorted(entries, key=lambda e: e.get("date") or "")
    if not sorted_entries:
        print(t("Keine Ereignisse.", "No events."))
        return

    header = t(
        "| Datum | Enddatum | Typ | Ereignis | Ort / Einrichtung | Notiz |",
        "| Date | End date | Type | Event | Location | Notes |",
    )
    sep = "|---|---|---|---|---|---|"
    print(header)
    print(sep)
    for e in sorted_entries:
        cols = [
            (e.get("date") or "")[:10],
            (e.get("date_end") or "")[:10] or "—",
            _type_label(e),
            e.get("name", ""),
            e.get("ort", ""),
            e.get("notes", "") or "",
        ]
        print("| " + " | ".join(cols) + " |")


# ── Main ──────────────────────────────────────────────────────────────────────

def _get_idx(args_list: list[str], entries: list[dict], prompt_text: str) -> int:
    if args_list and args_list[0].isdigit():
        return int(args_list[0])
    cmd_list(entries)
    try:
        return int(input(f"  {prompt_text} ").strip())
    except (ValueError, EOFError, KeyboardInterrupt):
        sys.exit(0)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=t(
            "Klinische Ereignisse verwalten (~/.config/kyoro/clinical_events.json)",
            "Manage clinical events (~/.config/kyoro/clinical_events.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  list              Alle Ereignisse chronologisch anzeigen
  add               Interaktiv neues Ereignis anlegen
  edit <nr>         Ereignis bearbeiten
  delete <nr>       Ereignis löschen
  export            Markdown-Tabelle für Arztbriefe ausgeben
""", """
Commands:
  list              Show all events in chronological order
  add               Interactively add a new event
  edit <nr>         Edit an event
  delete <nr>       Delete an event
  export            Output Markdown table for doctor's letters
"""),
    )
    ap.add_argument("command",
                    choices=["list", "add", "edit", "delete", "export"],
                    help=t("Aktion", "Action"))
    ap.add_argument("args", nargs="*",
                    help=t("Zusatzargument: Eintragsnummer", "Extra argument: entry number"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    entries = load()

    if args.command == "list":
        cmd_list(entries)

    elif args.command == "add":
        entries = cmd_add(entries)
        save(entries)

    elif args.command == "edit":
        idx = _get_idx(args.args, entries, t("Welche Nummer bearbeiten?", "Which number to edit?"))
        entries = cmd_edit(entries, idx)
        save(entries)

    elif args.command == "delete":
        idx = _get_idx(args.args, entries, t("Welche Nummer löschen?", "Which number to delete?"))
        entries = cmd_delete(entries, idx)
        save(entries)

    elif args.command == "export":
        cmd_export(entries)


if __name__ == "__main__":
    main()
