#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_environmental_substances.py — Umweltsubstanzen verwalten


@tier        infrastructure
@purpose.de  Verwaltet Umweltsubstanzen (Kosmetik, Haushaltsprodukte) für das Trigger-Tracking.
             Ermöglicht das Erfassen von Substanzen und deren Verwendung für die Korrelation
             mit Symptomen. Unterstützt automatischen INCI-Inhaltsstoff-Lookup via Open Beauty Facts.
@purpose.en  Manages environmental substances (cosmetics, household products) for trigger
             tracking. Enables recording of substances and their usage for correlation with symptoms.
             Supports automatic INCI ingredient lookup via Open Beauty Facts.
@method.de   Speichert unter ~/.config/kyoro/environmental_substances.json (lokal, nicht im Repo).
             Analog zu manage_medications.py, aber mit eigenen Feldern für Kosmetik und Haushaltsprodukte.
             Beim Hinzufügen wird automatisch nach INCI-Inhaltsstoffen gesucht (kann mit --no-lookup übersprungen werden).
             Bestehende Einträge können mit refresh-ingredients <nr> aktualisiert werden.
@method.en   Stores in ~/.config/kyoro/environmental_substances.json (local only, not in repo).
             Similar to manage_medications.py, but with custom fields for cosmetics and household products.
             Automatically looks up INCI ingredients when adding (can be skipped with --no-lookup).
             Existing entries can be updated with refresh-ingredients <nr>.
@reads       ~/.config/kyoro/environmental_substances.json, Open Beauty Facts API
@writes      ~/.config/kyoro/environmental_substances.json
@limits.de   Lokale Datei. Keine automatische Validierung. INCI-Lookup erfordert Netzwerkzugriff
             und kann fehlschlagen, wenn das Produkt nicht in Open Beauty Facts bekannt ist.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Local file only. No automatic validation. INCI lookup requires network access
             and may fail if the product is not known in Open Beauty Facts.
@usage
    python3 scripts/utils/manage/personal/manage_environmental_substances.py list [--active]
    python3 scripts/utils/manage/personal/manage_environmental_substances.py add [--no-lookup]
    python3 scripts/utils/manage/personal/manage_environmental_substances.py edit 3
    python3 scripts/utils/manage/personal/manage_environmental_substances.py stop 3
    python3 scripts/utils/manage/personal/manage_environmental_substances.py delete 3
    python3 scripts/utils/manage/personal/manage_environmental_substances.py refresh-ingredients 3
    python3 scripts/utils/manage/personal/manage_environmental_substances.py export [--active]
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

SUBSTANCE_FILE = KYORO_CONFIG_DIR / "environmental_substances.json"

# ── Wissensbasis für Vorschläge ───────────────────────────────────────────────
# Kategorien aus eigener Recherche, erweitert um Produkttypen anderer
# Haushaltsmitglieder (nicht nur eigene Kosmetik).

CATEGORIES = [
    "Zahnpasta",
    "Wimperntusche",
    "Gesichtscreme",
    "Duschgel",
    "Haarpflege",
    "Deo",
    "Sonnencreme",
    "Make-up",
    "Nagellack",
    "Rasur",
    "Parfüm",
    "Waschmittel",
    "Reinigungsmittel",
    "Raumduft",
    "Insektenschutz",
    "Sonstiges",
]


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    return _load_file(SUBSTANCE_FILE)


def save(entries: list[dict]) -> None:
    _save_file(SUBSTANCE_FILE, entries)


def _short_label(e: dict) -> str:
    return e.get("marke", "")


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
        f"\n  {'#':>3}  {'Status':<10} {'Person':<12} {'Marke':<25} {'Kategorie':<14} {'Verdachtssymptom':<20} {'INCI':>6} {'Quelle':<12} {'Zeitraum'}",
        f"\n  {'#':>3}  {'Status':<10} {'Person':<12} {'Brand':<25} {'Category':<14} {'Suspected symptom':<20} {'INCI':>6} {'Source':<12} {'Period'}",
    ))
    print("  " + "─" * 120)

    orig_idx = 0
    for e in entries:
        orig_idx += 1
        if active_only and not _is_active(e):
            continue
        if person != "all" and _entry_person(e) != person:
            continue
        ingr_count = len(e.get("ingredients", []))
        ingr_source = e.get("ingredients_source", "")[:12]
        print(
            f"  {orig_idx:>3}  {_status_tag(e)}"
            f"{_entry_person(e):<12} "
            f"{_short_label(e):<25} "
            f"{e.get('kategorie',''):<14} "
            f"{e.get('verdachtssymptom',''):<20} "
            f"{ingr_count:>6} "
            f"{ingr_source:<12} "
            f"{_fmt_period(e)}"
        )
        if e.get("notes"):
            print(f"       ↳ {e['notes']}")
    print()


def cmd_add(entries: list[dict], default_person: str, no_lookup: bool = False) -> list[dict]:
    print(t(
        "\n── Neuer Eintrag ────────────────────────────────────",
        "\n── New entry ────────────────────────────────────────",
    ))

    marke = _prompt(t("Marke / Produktname", "Brand / product name"))
    if not marke:
        print(t("Abgebrochen.", "Cancelled."))
        return entries

    person = _prompt(t("Person-ID", "Person ID"), default=default_person)
    kategorie = _prompt(t("Kategorie", "Category"), choices=CATEGORIES)
    verdachtssymptom = _prompt(t("Verdachtssymptom (z.B. 'Rosacea-Schub')", "Suspected symptom (e.g. 'rosacea flare')"))

    date_from_raw = _prompt(t("Beginn (YYYY-MM-DD [HH:MM] / YYYY-MM / leer = heute)", "Start (YYYY-MM-DD [HH:MM] / YYYY-MM / empty = today)"))
    date_from = _parse_date(date_from_raw) or date.today().isoformat()

    date_to_raw = _prompt(t("Ende (YYYY-MM-DD [HH:MM] / leer = noch aktiv)", "End date (YYYY-MM-DD [HH:MM] / empty = still active)"))
    date_to = _parse_date(date_to_raw, end=True) or ""

    notes = _prompt(t("Notiz (optional)", "Notes (optional)")) or None

    # INCI-Lookup
    ingredients = []
    ingredients_source = "not_found"
    if not no_lookup:
        try:
            from utils.lookup_ingredients import lookup
            result = lookup(query=marke, use_vision=False, verbose=False)
            if result and result.get("ingredients"):
                ingredients = result["ingredients"]
                ingredients_source = result.get("source", "not_found")
        except Exception as e:
            print(f"[INGREDIENTS] Lookup nicht verfügbar: {e}", file=sys.stderr)

    entry: dict = {
        "person":           person,
        "marke":            marke,
        "kategorie":        kategorie,
        "verdachtssymptom": verdachtssymptom,
        "date_from":        date_from,
        "date_to":          date_to,
        "notes":            notes,
        "ingredients":      ingredients,
        "ingredients_source": ingredients_source,
    }

    print(f"\n  → {_short_label(entry)}  {kategorie}  [{_fmt_period(entry)}]")
    if ingredients:
        print(f"     INCI: {len(ingredients)} Inhaltsstoffe ({ingredients_source})")
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
        ("person",           t("Person-ID", "Person ID"),            None),
        ("marke",            t("Marke", "Brand"),                    None),
        ("kategorie",        t("Kategorie", "Category"),             CATEGORIES),
        ("verdachtssymptom", t("Verdachtssymptom", "Suspected symptom"), None),
        ("date_from",        t("Beginn", "Start"),                   None),
        ("date_to",          t("Ende (leer = noch aktiv)", "End date"), None),
        ("notes",            t("Notiz", "Notes"),                    None),
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

    # Behalte ingredients und ingredients_source Felder
    if "ingredients" not in e:
        e["ingredients"] = []
    if "ingredients_source" not in e:
        e["ingredients_source"] = "not_found"

    entries[idx - 1] = e
    print(t("  Aktualisiert.", "  Updated."))
    return entries


def cmd_stop(entries: list[dict], idx: int) -> list[dict]:
    """Setzt date_to = heute — Substanz als beendet markieren ohne zu löschen."""
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


def cmd_refresh_ingredients(entries: list[dict], idx: int) -> list[dict]:
    """Aktualisiert die INCI-Inhaltsstoffe für einen bestehenden Eintrag."""
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    
    e = entries[idx - 1]
    marke = e.get("marke", "")
    if not marke:
        print(t("Keine Marke für diesen Eintrag, kann nicht nachschlagen.", 
                "No brand for this entry, cannot look up."))
        return entries
    
    print(t(f"\n── INCI-Update für Eintrag #{idx}: {marke} ──",
            f"\n── INCI update for entry #{idx}: {marke} ──"))
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
        from utils.lookup_ingredients import lookup
        result = lookup(query=marke, use_vision=False, verbose=False)
        if result and result.get("ingredients"):
            e["ingredients"] = result["ingredients"]
            e["ingredients_source"] = result.get("source", "not_found")
            print(t(f"  Aktualisiert: {len(e['ingredients'])} Inhaltsstoffe ({e['ingredients_source']})",
                    f"  Updated: {len(e['ingredients'])} ingredients ({e['ingredients_source']})"))
        else:
            e["ingredients"] = []
            e["ingredients_source"] = "not_found"
            print(t("  Keine Inhaltsstoffe gefunden.", "  No ingredients found."))
    except Exception as ex:
        print(f"[INGREDIENTS] Lookup fehlgeschlagen: {ex}", file=sys.stderr)
        return entries
    
    entries[idx - 1] = e
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
        "| Person | Marke | Kategorie | Verdachtssymptom | Seit | Bis |",
        "| Person | Brand | Category | Suspected symptom | From | To |",
    )
    sep = "|---|---|---|---|---|---|"
    print(header)
    print(sep)
    for e in shown:
        cols = [
            _entry_person(e),
            e.get("marke", ""),
            e.get("kategorie", ""),
            e.get("verdachtssymptom", ""),
            (e.get("date_from") or "")[:7],
            (e.get("date_to") or "")[:7] or "—",
        ]
        print("| " + " | ".join(cols) + " |")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t(
            "Umweltsubstanzen (Kosmetik/Haushalt) verwalten (~/.config/kyoro/environmental_substances.json)",
            "Manage environmental substances (cosmetics/household) (~/.config/kyoro/environmental_substances.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  list [--active]   Alle oder nur aktive Einträge anzeigen
  add [--no-lookup] Interaktiv neuen Eintrag anlegen (ohne INCI-Nachschlagen mit --no-lookup)
  edit <nr>         Eintrag bearbeiten
  stop <nr>         Als beendet markieren (date_to = heute)
  delete <nr>       Eintrag löschen
  refresh-ingredients <nr>  INCI-Inhaltsstoffe für Eintrag <nr> neu laden
  export [--active] Markdown-Tabelle für Arztbriefe ausgeben
""", """
Commands:
  list [--active]   Show all or only active entries
  add [--no-lookup] Interactively add a new entry (skip INCI lookup with --no-lookup)
  edit <nr>         Edit an entry
  stop <nr>         Mark as stopped (date_to = today)
  delete <nr>       Delete an entry
  refresh-ingredients <nr>  Refresh INCI ingredients for entry <nr>
  export [--active] Output Markdown table for doctor's letters
"""),
    )
    ap.add_argument("command",
                    choices=["list", "add", "edit", "stop", "delete", "refresh-ingredients", "export"],
                    help=t("Aktion", "Action"))
    ap.add_argument("args", nargs="*",
                    help=t("Zusatzargument: Eintragsnummer", "Extra argument: entry number"))
    ap.add_argument("--active", action="store_true",
                    help=t("Nur aktive Einträge", "Only active entries"))
    ap.add_argument("--no-lookup", action="store_true",
                    help=t("Kein automatischer INCI-Lookup beim Hinzufügen", 
                          "Skip automatic INCI lookup when adding"))
    _add_person_arg(ap)
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    entries = load()
    person = _resolve_person(args.person)

    if args.command == "list":
        cmd_list(entries, active_only=args.active, person=person)

    elif args.command == "add":
        entries = cmd_add(entries, default_person=person, no_lookup=args.no_lookup)
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

    elif args.command == "refresh-ingredients":
        idx = _get_idx(args.args, entries, t("Welche Nummer aktualisieren?", "Which number to refresh?"), cmd_list)
        entries = cmd_refresh_ingredients(entries, idx)
        save(entries)

    elif args.command == "export":
        cmd_export(entries, active_only=args.active, person=person)


if __name__ == "__main__":
    main()
