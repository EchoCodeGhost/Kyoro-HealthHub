#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_known_risk_exposures.py — Persönliche Dauerrisiko-Expositionen verwalten


@tier        infrastructure
@purpose.de  Erfasst chronische oder kumulative persönliche Risikoexpositionen
             (Tierhaltung, Beruf, Wohnort, Hobbys), die die Wahrscheinlichkeit
             bestimmter Infektionskrankheiten über den Populationsdurchschnitt heben.
             Wird von analyse_outbreak_exposure.py genutzt, um LLM-Gewichtungen anzupassen.
@purpose.en  Records chronic or cumulative personal risk exposures (animal husbandry,
             occupation, residence, hobbies) that raise the probability of specific
             infectious diseases above population average. Used by
             analyse_outbreak_exposure.py to adjust LLM weightings.
@method.de   Speichert unter ~/.config/kyoro/known_risk_exposures.json (lokal, nicht im Repo).
             Jeder Eintrag hat: slug (Erreger-Kürzel), description, level (high/medium/low),
             notes. Strg+C bricht jederzeit ohne Datenverlust ab.
@method.en   Stores in ~/.config/kyoro/known_risk_exposures.json (local only, not in repo).
             Each entry has: slug (pathogen key), description, level (high/medium/low),
             notes. Ctrl+C aborts at any time without data loss.
@reads       ~/.config/kyoro/known_risk_exposures.json
@writes      ~/.config/kyoro/known_risk_exposures.json
@limits.de   Slugs müssen mit den Syndrome-Slugs in analyse_outbreak_exposure.py übereinstimmen.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Slugs must match the syndrome slugs used in analyse_outbreak_exposure.py.
@usage
    python3 scripts/utils/manage/personal/manage_known_risk_exposures.py list
    python3 scripts/utils/manage/personal/manage_known_risk_exposures.py add
    python3 scripts/utils/manage/personal/manage_known_risk_exposures.py delete 2
    python3 scripts/utils/manage/personal/manage_known_risk_exposures.py edit 2
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.config_backup import backup_before_write, commit_config_change
from health_config import KYORO_CONFIG_DIR

RISK_FILE = KYORO_CONFIG_DIR / "known_risk_exposures.json"

# ── Wissensbasen ──────────────────────────────────────────────────────────────

RISK_LEVELS = ["high", "medium", "low"]

LEVEL_LABELS = {
    "high":   t("Hoch   — tägliche/regelmäßige Exposition, weit über Populationsschnitt",
                "High   — daily/regular exposure, far above population average"),
    "medium": t("Mittel — wiederkehrende Exposition, deutlich über Populationsschnitt",
                "Medium — recurring exposure, clearly above population average"),
    "low":    t("Niedrig— gelegentliche Exposition, leicht über Populationsschnitt",
                "Low    — occasional exposure, slightly above population average"),
}

# Bekannte Slugs mit Beschreibung
KNOWN_SLUGS: list[tuple[str, str]] = [
    ("ornithose",    t("C. psittaci — Vögel (Papageien, Wellensittiche, Enten, Gänse)",
                       "C. psittaci — birds (parrots, parakeets, ducks, geese)")),
    ("q_fieber",     t("C. burnetii — Rinder, Schafe, Ziegen, Pferde, Zecken",
                       "C. burnetii — cattle, sheep, goats, horses, ticks")),
    ("fsme",         t("FSME-Virus — Zecken in Endemiegebieten (Bayern, Österreich, ...)",
                       "TBE virus — ticks in endemic areas (Bavaria, Austria, ...)")),
    ("borreliose",   t("B. burgdorferi — Zecken in Wäldern/Wiesen",
                       "B. burgdorferi — ticks in forests/meadows")),
    ("rickettsia",   t("Rickettsia spp. — Zecken/Hundezecken Mittelmeer",
                       "Rickettsia spp. — ticks/dog ticks Mediterranean")),
    ("leishmaniose", t("Leishmania — Sandmücken Mittelmeer/Tropen",
                       "Leishmania — sandflies Mediterranean/tropics")),
    ("leptospirose", t("Leptospira — Süßwasser, Nagetiere, Nutztiere",
                       "Leptospira — freshwater, rodents, livestock")),
    ("tularaemie",   t("F. tularensis — Hasen, Nager, Zecken, Wasser",
                       "F. tularensis — hares, rodents, ticks, water")),
    ("hanta",        t("Hantavirus — Nagetiere (Rötelmaus), Staub",
                       "Hantavirus — rodents (voles), dust")),
    ("campylobacter",t("Campylobacter — Geflügel, Rohmilch, Haustiere",
                       "Campylobacter — poultry, raw milk, pets")),
    ("salmonella",   t("Salmonella — Geflügel, Reptilien, Roheier",
                       "Salmonella — poultry, reptiles, raw eggs")),
    ("hepatitis_e",  t("HEV — Schwein, Wild, Rohmilch",
                       "HEV — pork, game, raw milk")),
    ("brucellose",   t("Brucella — Rohmilch, Schafe, Ziegen, Rinder",
                       "Brucella — raw milk, sheep, goats, cattle")),
    ("toxoplasma",   t("T. gondii — Katzen, Rohfleisch, Erde",
                       "T. gondii — cats, raw meat, soil")),
    ("post_covid",   t("SARS-CoV-2 — Hochrisiko-Exposition (Gesundheitswesen etc.)",
                       "SARS-CoV-2 — high-risk exposure (healthcare etc.)")),
    ("ebv",          t("EBV — enge Kontakte, Immunsuppression",
                       "EBV — close contacts, immunosuppression")),
    ("generic",      t("Sonstiger Erreger / eigener Slug",
                       "Other pathogen / custom slug")),
]

EXPOSURE_SOURCES: list[str] = [
    t("Haustierhaltung (Vögel, Papageien, Wellensittiche)",
      "Pet ownership (birds, parrots, parakeets)"),
    t("Landwirtschaft / Stallarbeit (Rinder, Schweine, Schafe)",
      "Farming / stable work (cattle, pigs, sheep)"),
    t("Reiten / Pferdekontakt",
      "Horse riding / horse contact"),
    t("Wandern / Outdoor in Endemiegebieten",
      "Hiking / outdoor in endemic areas"),
    t("Dauerwohnsitz in Zecken-Endemiegebiet",
      "Permanent residence in tick-endemic area"),
    t("Berufliche Tierexposition (Tierarzt, Landwirt, Zoo)",
      "Occupational animal exposure (vet, farmer, zoo)"),
    t("Wildwasser / Süßwasserkontakt (Kanusport, Baden)",
      "Whitewater / freshwater contact (kayaking, swimming)"),
    t("Gartenarbeit in Endemiegebiet",
      "Gardening in endemic area"),
    t("Reisen in Tropen / Subtropen regelmäßig",
      "Regular travel to tropics / subtropics"),
    t("Feuchtgebiete / Vogelreservate (Ornithologie-Hobby)",
      "Wetlands / bird reserves (birdwatching hobby)"),
    t("Jagd / Wildtierkontakt",
      "Hunting / wildlife contact"),
]


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    if RISK_FILE.exists():
        return json.loads(RISK_FILE.read_text(encoding="utf-8"))
    return []


def save(entries: list[dict]) -> None:
    RISK_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup_before_write(RISK_FILE)
    RISK_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    commit_config_change(RISK_FILE, f"known_risk_exposures: {len(entries)} Einträge gespeichert")
    print(t(f"Gespeichert: {RISK_FILE}", f"Saved: {RISK_FILE}"))


def _prompt(label: str, default: str = "", choices: list[str] | None = None,
            required: bool = False) -> str:
    if choices:
        print(t(f"\n  Optionen für {label}:", f"\n  Options for {label}:"))
        for i, c in enumerate(choices[:16], 1):
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


def _level_icon(level: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(level, "⚪")


def _slug_choices() -> list[str]:
    return [f"{slug}  — {desc}" for slug, desc in KNOWN_SLUGS]


def _extract_slug(raw: str) -> str:
    return raw.split()[0] if raw.split() else raw


def _get_known_slugs() -> set[str]:
    """Get the set of currently known syndrome slugs."""
    return {slug for slug, _ in KNOWN_SLUGS}


def add_entry_noninteractive(entry: dict) -> None:
    """Add a known risk exposure entry non-interactively, validating slug against current known set."""
    entries = load()
    
    # Validate required fields
    if "slug" not in entry or not entry["slug"]:
        raise ValueError(t("Erreger-Slug ist ein Pflichtfeld", "Pathogen slug is required"))
    if "description" not in entry or not entry["description"]:
        raise ValueError(t("Beschreibung ist ein Pflichtfeld", "Description is required"))
    if "level" not in entry or not entry["level"]:
        raise ValueError(t("Risikolevel ist ein Pflichtfeld", "Risk level is required"))
    
    # Validate slug against current known set
    slug = _extract_slug(entry["slug"])
    known_slugs = _get_known_slugs()
    if slug not in known_slugs:
        raise ValueError(
            t(f"Unbekannter Slug: {slug}. Gültige Werte: {', '.join(known_slugs)}",
              f"Unknown slug: {slug}. Valid values: {', '.join(known_slugs)}")
        )
    
    # Validate level
    level = entry["level"]
    if level not in RISK_LEVELS:
        raise ValueError(t(f"Ungültiges Risikolevel: {level}", f"Invalid risk level: {level}"))
    
    # Build validated entry
    validated_entry: dict = {
        "slug": slug,
        "description": entry["description"],
        "level": level,
    }
    
    # Optional fields
    if "notes" in entry and entry["notes"]:
        validated_entry["notes"] = entry["notes"]
    
    entries.append(validated_entry)
    save(entries)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(entries: list[dict]) -> None:
    if not entries:
        print(t("Noch keine Einträge. Mit 'add' beginnen.",
                "No entries yet. Use 'add' to start."))
        return
    print(t(f"\n  {'#':>3}  {'Lvl'}  {'Slug':<16} {'Beschreibung'}",
            f"\n  {'#':>3}  {'Lvl'}  {'Slug':<16} {'Description'}"))
    print("  " + "─" * 80)
    for i, e in enumerate(entries, 1):
        icon  = _level_icon(e.get("level", ""))
        slug  = e.get("slug", "")
        desc  = e.get("description", "")
        print(f"  {i:>3}  {icon}   {slug:<16} {desc}")
        if e.get("notes"):
            print(f"             ↳ {e['notes']}")
    print()


def cmd_add(entries: list[dict]) -> list[dict]:
    print(t("\n── Neue Dauerrisiko-Exposition ─────────────────────────",
            "\n── New chronic risk exposure ────────────────────────────"))
    print(t("  (Strg+C jederzeit zum Abbrechen ohne Datenverlust)",
            "  (Ctrl+C at any time to cancel without data loss)"))

    # Slug
    slug_raw = _prompt(t("Erreger-Slug", "Pathogen slug"),
                       choices=_slug_choices(), required=True)
    slug = _extract_slug(slug_raw)

    # Beschreibung
    print(t("\n  Beschreibt die konkrete Expositionsquelle (Tierart, Dauer, Kontext).",
            "\n  Describe the specific exposure source (animal type, duration, context)."))
    source_choices = EXPOSURE_SOURCES
    desc_raw = _prompt(t("Beschreibung", "Description"),
                       choices=source_choices, required=True)
    # Wenn aus Vorschlägen gewählt, Freitext als Ergänzung anbieten
    if desc_raw in source_choices:
        extra = _prompt(t("Ergänzung / Präzisierung (optional, Enter überspringen)",
                          "Clarification (optional, Enter to skip)"))
        if extra:
            desc_raw = f"{desc_raw} — {extra}"
    description = desc_raw

    # Level
    level_choices = [f"{lvl}  ({LEVEL_LABELS[lvl]})" for lvl in RISK_LEVELS]
    level_raw = _prompt(t("Risikolevel", "Risk level"),
                        choices=level_choices, required=True)
    level = level_raw.split()[0] if level_raw.split() else "medium"
    if level not in RISK_LEVELS:
        level = "medium"

    # Notiz
    notes_raw = _prompt(t("Notiz — Anamnese-Details (optional, Enter überspringen)",
                          "Notes — anamnesis details (optional, Enter to skip)"))
    notes = notes_raw or None

    entry: dict = {"slug": slug, "description": description, "level": level}
    if notes:
        entry["notes"] = notes

    print(f"\n  → {_level_icon(level)} [{level}]  {slug}  —  {description}")
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
    print(t(f"Gelöscht: {removed.get('slug')} — {removed.get('description','')}",
            f"Deleted: {removed.get('slug')} — {removed.get('description','')}"))
    return entries


def cmd_edit(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}",
                f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    e = entries[idx - 1]
    print(t(f"\n── Eintrag #{idx} bearbeiten (Enter = unverändert) ──",
            f"\n── Edit entry #{idx} (Enter = keep unchanged) ──"))
    print(f"  {_level_icon(e.get('level',''))} {e.get('slug','')}  —  {e.get('description','')}")

    slug_raw = _prompt(t("Erreger-Slug", "Pathogen slug"),
                       default=_extract_slug(e.get("slug", "")),
                       choices=_slug_choices())
    if slug_raw:
        e["slug"] = _extract_slug(slug_raw)

    desc_raw = _prompt(t("Beschreibung", "Description"),
                       default=e.get("description", ""),
                       choices=EXPOSURE_SOURCES)
    if desc_raw:
        e["description"] = desc_raw

    level_choices = [f"{lvl}  ({LEVEL_LABELS[lvl]})" for lvl in RISK_LEVELS]
    level_raw = _prompt(t("Risikolevel", "Risk level"),
                        default=e.get("level", "medium"),
                        choices=level_choices)
    new_level = level_raw.split()[0] if level_raw.split() else ""
    if new_level in RISK_LEVELS:
        e["level"] = new_level

    notes_raw = _prompt(t("Notiz", "Notes"), default=e.get("notes", "") or "")
    e["notes"] = notes_raw or None

    entries[idx - 1] = e
    print(t("  ✓ Aktualisiert.", "  ✓ Updated."))
    return entries


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
            "Persönliche Dauerrisiko-Expositionen verwalten (~/.config/kyoro/known_risk_exposures.json)",
            "Manage personal chronic risk exposures (~/.config/kyoro/known_risk_exposures.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  list              Alle Einträge anzeigen
  add               Interaktiv neue Exposition erfassen
  edit <nr>         Eintrag bearbeiten
  delete <nr>       Eintrag löschen

Risikolevel:
  high    Tägliche/regelmäßige Exposition, weit über Populationsschnitt
  medium  Wiederkehrende Exposition, deutlich über Populationsschnitt
  low     Gelegentliche Exposition, leicht über Populationsschnitt

Slugs müssen mit den Syndrome-Slugs in analyse_outbreak_exposure.py übereinstimmen
(z.B. ornithose, q_fieber, fsme, borreliose, rickettsia, leishmaniose, ...).
""", """
Commands:
  list              Show all entries
  add               Interactively record a new exposure
  edit <nr>         Edit an entry
  delete <nr>       Delete an entry

Risk levels:
  high    Daily/regular exposure, far above population average
  medium  Recurring exposure, clearly above population average
  low     Occasional exposure, slightly above population average

Slugs must match the syndrome slugs in analyse_outbreak_exposure.py
(e.g. ornithose, q_fieber, fsme, borreliose, rickettsia, leishmaniose, ...).
"""),
    )
    ap.add_argument("command", choices=["list", "add", "edit", "delete"],
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
        idx = _get_idx(args.args, entries,
                       t("Welche Nummer bearbeiten?", "Which number to edit?"))
        entries = cmd_edit(entries, idx)
        save(entries)

    elif args.command == "delete":
        idx = _get_idx(args.args, entries,
                       t("Welche Nummer löschen?", "Which number to delete?"))
        entries = cmd_delete(entries, idx)
        save(entries)


if __name__ == "__main__":
    main()
