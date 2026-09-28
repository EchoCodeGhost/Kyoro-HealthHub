#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_allergies.py — Allergien und Unverträglichkeiten verwalten

@tier        infrastructure
@purpose.de  Dokumentiert bekannte Allergien und Unverträglichkeiten (Arzneimittel,
             Insektengift, Inhalation, Kontakt, Nahrungsmittel, Autoimmun) für
             Arztbriefe und die KI-Anamnese.
@purpose.en  Documents known allergies and intolerances (drug, insect venom,
             inhalation, contact, food, autoimmune) for doctor's letters and
             AI-assisted history taking.
@method.de   Speichert unter ~/.config/kyoro/allergies.json (lokal, nicht im Repo).
             Jeder Eintrag: allergen, type, reaction, severity, diagnosed, notes.
             Strg+C bricht jederzeit ohne Datenverlust ab.
@method.en   Stores in ~/.config/kyoro/allergies.json (local only, not in repo).
             Each entry: allergen, type, reaction, severity, diagnosed, notes.
             Ctrl+C aborts at any time without data loss.
@reads       ~/.config/kyoro/allergies.json
@writes      ~/.config/kyoro/allergies.json
@limits.de   Keine klinische Validierung — reine Dokumentation. Arzneimittelallergien
             immer mit Kreuzreaktivität und Alternativen im notes-Feld dokumentieren.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No clinical validation — documentation only. Always note cross-reactivity
             and alternatives for drug allergies in the notes field.
@usage
    python3 scripts/utils/manage/personal/manage_allergies.py list
    python3 scripts/utils/manage/personal/manage_allergies.py add
    python3 scripts/utils/manage/personal/manage_allergies.py edit 3
    python3 scripts/utils/manage/personal/manage_allergies.py delete 3
    python3 scripts/utils/manage/personal/manage_allergies.py export
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import KYORO_CONFIG_DIR

ALLERGIES_FILE = KYORO_CONFIG_DIR / "allergies.json"

TYPES = [
    "Arzneimittel",
    "Insektengift",
    "Inhalationsallergie",
    "Kontaktallergie",
    "Nahrungsmittel",
    "Autoimmun",
]

SEVERITIES = ["leicht", "mittel", "schwer", "lebensbedrohlich"]

SEVERITY_ICONS = {
    "leicht":            "🟢",
    "mittel":            "🟡",
    "schwer":            "🟠",
    "lebensbedrohlich":  "🔴",
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    if ALLERGIES_FILE.exists():
        return json.loads(ALLERGIES_FILE.read_text(encoding="utf-8"))
    return []


def save(entries: list[dict]) -> None:
    ALLERGIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALLERGIES_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(t(f"Gespeichert: {ALLERGIES_FILE}", f"Saved: {ALLERGIES_FILE}"))


def _prompt(label: str, default: str = "", choices: list[str] | None = None,
            required: bool = False) -> str:
    if choices:
        print(t(f"\n  Optionen für {label}:", f"\n  Options for {label}:"))
        for i, c in enumerate(choices, 1):
            print(f"    {i:2}. {c}")
        print(t("    (Nummer oder freie Eingabe / Enter = Standard)",
                "    (number or free text / Enter = default)"))

    dflt_str = f" [{default}]" if default else ""
    req_str  = " *" if required else ""
    while True:
        try:
            sys.stdout.write(f"  {label}{req_str}{dflt_str}: ")
            sys.stdout.flush()
            try:
                raw = sys.stdin.buffer.readline()
                val = raw.decode("utf-8", errors="replace").rstrip("\n").strip()
            except AttributeError:
                val = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(t("\n  Abgebrochen (Strg+C).", "\n  Cancelled (Ctrl+C)."))
            sys.exit(0)

        if choices and val.isdigit():
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                val = choices[idx]

        result = val or default
        if required and not result:
            print(t("  (Pflichtfeld)", "  (Required field)"))
            continue
        return result


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(entries: list[dict]) -> None:
    if not entries:
        print(t("Noch keine Einträge. Mit 'add' beginnen.",
                "No entries yet. Use 'add' to start."))
        return

    sorted_entries = sorted(entries, key=lambda e: (e.get("type", ""), e.get("allergen", "")))

    print(t(f"\n  {'#':>3}  {'Sev.'}  {'Allergen':<45} {'Typ'}",
            f"\n  {'#':>3}  {'Sev.'}  {'Allergen':<45} {'Type'}"))
    print("  " + "─" * 90)

    current_type = None
    for i, e in enumerate(sorted_entries, 1):
        etype = e.get("type", "")
        if etype != current_type:
            current_type = etype
            print(f"\n  ── {etype} " + "─" * max(1, 60 - len(etype)))

        icon     = SEVERITY_ICONS.get(e.get("severity", ""), "⚪")
        allergen = e.get("allergen", "")
        diag     = e.get("diagnosed", "")
        diag_str = f" (seit {diag})" if diag else ""
        print(f"  {i:>3}  {icon}    {allergen:<45}{diag_str}")
        if e.get("reaction"):
            print(f"              ↳ Reaktion: {e['reaction']}")
        if e.get("notes"):
            print(f"              ↳ {e['notes']}")
    print()


def cmd_add(entries: list[dict]) -> list[dict]:
    print(t("\n── Neue Allergie / Unverträglichkeit ──────────────────",
            "\n── New allergy / intolerance ───────────────────────────"))
    print(t("  (Strg+C jederzeit zum Abbrechen ohne Datenverlust)",
            "  (Ctrl+C at any time to cancel without data loss)"))

    allergen = _prompt(t("Allergen / Auslöser", "Allergen / trigger"), required=True)
    etype    = _prompt(t("Typ", "Type"), choices=TYPES, required=True)
    reaction = _prompt(t("Reaktion (Symptome)", "Reaction (symptoms)"))
    severity = _prompt(t("Schweregrad", "Severity"), choices=SEVERITIES,
                       default="mittel", required=True)
    if severity not in SEVERITIES:
        severity = "mittel"
    diagnosed = _prompt(t("Diagnosedatum (YYYY-MM-DD, optional)",
                          "Date diagnosed (YYYY-MM-DD, optional)"))
    notes = _prompt(t("Notiz — Kreuzreaktivität, Alternativen, Kontext (optional)",
                      "Notes — cross-reactivity, alternatives, context (optional)"))

    entry: dict = {"allergen": allergen, "type": etype, "severity": severity}
    if reaction:
        entry["reaction"] = reaction
    if diagnosed:
        entry["diagnosed"] = diagnosed
    if notes:
        entry["notes"] = notes

    icon = SEVERITY_ICONS.get(severity, "⚪")
    print(f"\n  → {icon} {allergen} [{etype}, {severity}]")
    if reaction:
        print(f"    Reaktion: {reaction}")
    if notes:
        print(f"    ↳ {notes}")

    try:
        confirm = input(t("  Speichern? [J/n]: ", "  Save? [Y/n]: ")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(t("\n  Abgebrochen.", "\n  Cancelled."))
        sys.exit(0)

    if confirm in ("", "j", "y", "ja", "yes"):
        entries.append(entry)
        print(t(f"  ✓ Hinzugefügt (Eintrag #{len(entries)})",
                f"  ✓ Added (entry #{len(entries)})"))
    else:
        print(t("  Abgebrochen.", "  Cancelled."))
    return entries


def cmd_delete(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}",
                f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    removed = entries.pop(idx - 1)
    print(t(f"Gelöscht: {removed.get('allergen','')}",
            f"Deleted: {removed.get('allergen','')}"))
    return entries


def cmd_edit(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}",
                f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    e = entries[idx - 1]
    print(t(f"\n── Eintrag #{idx} bearbeiten (Enter = unverändert) ──",
            f"\n── Edit entry #{idx} (Enter = keep unchanged) ──"))
    print(f"  {e.get('allergen','')} [{e.get('type','')}, {e.get('severity','')}]")

    allergen = _prompt(t("Allergen / Auslöser", "Allergen / trigger"), default=e.get("allergen", ""))
    if allergen:
        e["allergen"] = allergen

    etype = _prompt(t("Typ", "Type"), default=e.get("type", ""), choices=TYPES)
    if etype:
        e["type"] = etype

    reaction = _prompt(t("Reaktion", "Reaction"), default=e.get("reaction", "") or "")
    e["reaction"] = reaction or None

    severity = _prompt(t("Schweregrad", "Severity"), default=e.get("severity", "mittel"),
                       choices=SEVERITIES)
    if severity in SEVERITIES:
        e["severity"] = severity

    diagnosed = _prompt(t("Diagnosedatum", "Date diagnosed"), default=e.get("diagnosed", "") or "")
    e["diagnosed"] = diagnosed or None

    notes = _prompt(t("Notiz", "Notes"), default=e.get("notes", "") or "")
    e["notes"] = notes or None

    e = {k: v for k, v in e.items() if v is not None}
    entries[idx - 1] = e
    print(t("  ✓ Aktualisiert.", "  ✓ Updated."))
    return entries


def cmd_export(entries: list[dict]) -> None:
    """Markdown-Tabelle für Arztbriefe."""
    if not entries:
        print(t("Keine Einträge.", "No entries."))
        return

    sorted_entries = sorted(entries, key=lambda e: (e.get("type", ""), e.get("allergen", "")))

    print(t(
        "| Allergen | Typ | Reaktion | Schweregrad | Diagnostiziert | Notiz |",
        "| Allergen | Type | Reaction | Severity | Diagnosed | Notes |",
    ))
    print("|---|---|---|---|---|---|")
    for e in sorted_entries:
        icon = SEVERITY_ICONS.get(e.get("severity", ""), "⚪")
        cols = [
            e.get("allergen", ""),
            e.get("type", ""),
            e.get("reaction", "") or "",
            f"{icon} {e.get('severity','')}",
            e.get("diagnosed", "") or "—",
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
            "Allergien und Unverträglichkeiten verwalten (~/.config/kyoro/allergies.json)",
            "Manage allergies and intolerances (~/.config/kyoro/allergies.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  list                    Einträge nach Typ gruppiert anzeigen
  add                     Interaktiv neuen Eintrag anlegen
  edit <nr>               Eintrag bearbeiten
  delete <nr>             Eintrag löschen
  export                  Markdown-Tabelle für Arztbriefe ausgeben

Schweregrad-Icons:
  🟢 leicht   🟡 mittel   🟠 schwer   🔴 lebensbedrohlich

Hinweis: Arzneimittelallergien immer mit Kreuzreaktivität und Alternativen
im Notiz-Feld dokumentieren.
""", """
Commands:
  list                    Show entries grouped by type
  add                     Interactively add a new entry
  edit <nr>               Edit an entry
  delete <nr>             Delete an entry
  export                  Output Markdown table for doctor's letters

Severity icons:
  🟢 mild   🟡 moderate   🟠 severe   🔴 life-threatening

Note: always document cross-reactivity and alternatives for drug allergies
in the notes field.
"""),
    )
    ap.add_argument("command", choices=["list", "add", "edit", "delete", "export"],
                    help=t("Aktion", "Action"))
    ap.add_argument("args", nargs="*",
                    help=t("Zusatzargumente: Eintragsnummer", "Extra arguments: entry number"))
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
        idx = _get_idx(args.args, entries,
                       t("Welche Nummer bearbeiten?", "Which number to edit?"))
        entries = cmd_edit(entries, idx)
        save(entries)

    elif args.command == "delete":
        idx = _get_idx(args.args, entries,
                       t("Welche Nummer löschen?", "Which number to delete?"))
        entries = cmd_delete(entries, idx)
        save(entries)

    elif args.command == "export":
        cmd_export(entries)


if __name__ == "__main__":
    main()
