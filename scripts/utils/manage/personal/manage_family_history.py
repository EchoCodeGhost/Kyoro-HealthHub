#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_family_history.py — Familienanamnese und genetische Vorbelastungen erfassen


@tier        infrastructure
@purpose.de  Dokumentiert Erkrankungen und Auffälligkeiten bei Blutsverwandten,
             um genetische Prädispositionen und Vererbungsmuster sichtbar zu machen.
             Unterstützt zwei Ansichten: nach Verwandtem oder nach Erkrankung (Cluster).
@purpose.en  Documents conditions and findings in blood relatives to reveal genetic
             predispositions and inheritance patterns. Supports two views: by relative
             or by condition (cluster view).
@method.de   Speichert unter ~/.config/kyoro/family_history.json (lokal, nicht im Repo).
             Jeder Eintrag: Verwandter, Erkrankung, Status (bestätigt/vermutet),
             Seite (mütterlich/väterlich), Alter bei Beginn, Notizen.
             Strg+C bricht jederzeit ohne Datenverlust ab.
@method.en   Stores in ~/.config/kyoro/family_history.json (local only, not in repo).
             Each entry: relative, condition, status (confirmed/suspected), side
             (maternal/paternal), age at onset, notes. Ctrl+C aborts without data loss.
@reads       ~/.config/kyoro/family_history.json
@writes      ~/.config/kyoro/family_history.json
@limits.de   Keine genetische Datenbank — rein anamnestische Dokumentation.
             Nicht committed; nie als bestätigte Diagnose bei Dritten behandeln.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No genetic database — purely anamnetic documentation.
             Not committed; never treat as confirmed diagnosis in others.
@usage
    python3 scripts/utils/manage/personal/manage_family_history.py list
    python3 scripts/utils/manage/personal/manage_family_history.py list --by-condition
    python3 scripts/utils/manage/personal/manage_family_history.py add
    python3 scripts/utils/manage/personal/manage_family_history.py delete 3
    python3 scripts/utils/manage/personal/manage_family_history.py edit 3
    python3 scripts/utils/manage/personal/manage_family_history.py export
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.config_backup import backup_before_write, commit_config_change
from health_config import KYORO_CONFIG_DIR

HISTORY_FILE = KYORO_CONFIG_DIR / "family_history.json"

# ── Wissensbasen ──────────────────────────────────────────────────────────────

RELATIVES = [
    "Mutter",
    "Vater",
    "Großmutter mütterlicherseits",
    "Großvater mütterlicherseits",
    "Großmutter väterlicherseits",
    "Großvater väterlicherseits",
    "Schwester",
    "Bruder",
    "Tante mütterlicherseits",
    "Onkel mütterlicherseits",
    "Tante väterlicherseits",
    "Onkel väterlicherseits",
    "Urgroßmutter mütterlicherseits",
    "Urgroßvater mütterlicherseits",
    "Cousine / Cousin",
    "Kind (Tochter / Sohn)",
]

SIDES = ["mütterlicherseits", "väterlicherseits", "unbekannt"]

STATUSES = ["vermutet", "bestätigt", "ausgeschlossen"]

STATUS_ICONS = {
    "bestätigt":    "✅",
    "vermutet":     "❓",
    "ausgeschlossen": "❌",
}

# Erkrankungskategorien mit Vorschlägen
CONDITION_CATEGORIES: dict[str, list[str]] = {
    t("Autoimmun / Rheumatologisch", "Autoimmune / Rheumatological"): [
        "Rosacea", "Sjögren-Syndrom", "Hashimoto-Thyreoiditis", "Lupus erythematodes",
        "Rheumatoide Arthritis", "Psoriasis-Arthritis", "Morbus Bechterew",
        "Multiple Sklerose", "Zöliakie", "Typ-1-Diabetes",
        "MCAS (Mastzellaktivierungssyndrom)", "Hereditäre Alpha-Tryptasämie (HAT)",
        "Antiphospholipid-Syndrom (APS)", "Sjögren-assoziierte Neuropathie",
    ],
    t("Herz / Kreislauf", "Cardiovascular"): [
        "Vorhofflimmern", "Koronare Herzkrankheit (KHK)", "Herzinfarkt",
        "Schlaganfall / TIA", "Hypertonie", "Herzinsuffizienz",
        "Arrhythmie (sonstige)", "Kardiomyopathie", "Aortenstenose",
        "Tiefe Beinvenenthrombose (TVT)", "Lungenembolie",
    ],
    t("Neurologisch / Psychiatrisch", "Neurological / Psychiatric"): [
        "Migräne", "Epilepsie", "Parkinson", "Alzheimer / Demenz",
        "Depression", "Bipolare Störung", "Angststörung / Panikstörung",
        "Autismus-Spektrum (ASS)", "ADHS", "Schizophrenie",
        "Polyneuropathie", "Small Fiber Neuropathie (SFN)",
        "Chronisches Erschöpfungssyndrom (ME/CFS)",
    ],
    t("Stoffwechsel / Endokrin", "Metabolic / Endocrine"): [
        "Typ-2-Diabetes", "Hypothyreose", "Hyperthyreose",
        "Adipositas", "Metabolisches Syndrom", "Gicht",
        "Hämochromatose", "Phenylketonurie (PKU)",
    ],
    t("Dermatologisch", "Dermatological"): [
        "Rosacea", "Psoriasis / Schuppenflechte", "Neurodermitis / Atopisches Ekzem",
        "Urtikaria chronisch", "Vitiligo", "Alopezie",
        "Basalzellkarzinom", "Melanom",
    ],
    t("Allergien / Überempfindlichkeiten", "Allergies / Hypersensitivities"): [
        "Penicillin-Allergie", "Kontaktallergie (Kolophonium / Pflaster)",
        "Kosmetika-Überempfindlichkeit", "Textilchemikalien-Reaktion",
        "Pflanzenpollen-Allergie", "Nahrungsmittelallergien",
        "Insektengift-Allergie", "NSAID-Überempfindlichkeit",
        "Atemwegsreaktion auf Duftstoffe / Haarspray",
        "Nickelallergie", "Latexallergie",
    ],
    t("Bindegewebe / Skelett", "Connective Tissue / Skeletal"): [
        "Hypermobilitätssyndrom (HSD / hEDS)", "Ehlers-Danlos-Syndrom (EDS)",
        "Marfan-Syndrom", "Osteogenesis imperfecta",
        "Skoliose", "Osteoporose früh", "Gelenkinstabilität",
    ],
    t("Onkologisch", "Oncological"): [
        "Darmkrebs / Kolorektales Karzinom", "Brustkrebs",
        "Prostatakrebs", "Lungenkrebs", "Magenkrebs",
        "Pankreas-Karzinom", "Non-Hodgkin-Lymphom", "Leukämie",
        "Gebärmutterhalskrebs", "Nierenkrebs", "BRCA1/BRCA2-Mutation",
    ],
    t("Infektionsneigung / Immundefekt", "Infection susceptibility / Immunodeficiency"): [
        "Rezidivierende Infektionen (HNO)", "Primärer Immundefekt",
        "IgA-Mangel", "Hypogammaglobulinämie", "Chronische EBV-Reaktivierung",
        "Rezidivierende Pneumonien", "Tuberkulose", "HIV",
    ],
    t("Sonstiges", "Other"): [],
}

# Flache Liste aller Vorschläge für freie Suche
ALL_CONDITIONS: list[str] = [
    c for cats in CONDITION_CATEGORIES.values() for c in cats
]

# Automatisch abgeleitete Seite je nach Verwandtem
_RELATIVE_SIDE: dict[str, str] = {
    "Mutter":                         "mütterlicherseits",
    "Großmutter mütterlicherseits":    "mütterlicherseits",
    "Großvater mütterlicherseits":     "mütterlicherseits",
    "Tante mütterlicherseits":         "mütterlicherseits",
    "Onkel mütterlicherseits":         "mütterlicherseits",
    "Urgroßmutter mütterlicherseits":  "mütterlicherseits",
    "Urgroßvater mütterlicherseits":   "mütterlicherseits",
    "Vater":                          "väterlicherseits",
    "Großmutter väterlicherseits":     "väterlicherseits",
    "Großvater väterlicherseits":      "väterlicherseits",
    "Tante väterlicherseits":          "väterlicherseits",
    "Onkel väterlicherseits":          "väterlicherseits",
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def save(entries: list[dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup_before_write(HISTORY_FILE)
    HISTORY_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    commit_config_change(HISTORY_FILE, f"family_history: {len(entries)} Einträge gespeichert")
    print(t(f"Gespeichert: {HISTORY_FILE}", f"Saved: {HISTORY_FILE}"))


def _prompt(label: str, default: str = "", choices: list[str] | None = None,
            required: bool = False) -> str:
    if choices:
        print(t(f"\n  Optionen für {label}:", f"\n  Options for {label}:"))
        for i, c in enumerate(choices[:18], 1):
            print(f"    {i:2}. {c}")
        if len(choices) > 18:
            print(t(f"    … ({len(choices) - 18} weitere — freie Eingabe möglich)",
                    f"    … ({len(choices) - 18} more — free text also accepted)"))
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


def _prompt_category_then_condition() -> str:
    """Zweistufige Auswahl: erst Kategorie, dann Erkrankung daraus."""
    cats = list(CONDITION_CATEGORIES.keys())
    cat_raw = _prompt(t("Kategorie (oder freie Eingabe)", "Category (or free text)"),
                      choices=cats)
    # Wenn Kategorie gewählt, Vorschläge aus der Kategorie zeigen
    suggestions = CONDITION_CATEGORIES.get(cat_raw, [])
    if suggestions:
        condition = _prompt(t("Erkrankung / Befund", "Condition / finding"),
                            choices=suggestions, required=True)
    else:
        # Freie Eingabe oder unbekannte Kategorie — direkt eingeben
        condition = cat_raw if cat_raw not in cats else _prompt(
            t("Erkrankung / Befund", "Condition / finding"), required=True)
    return condition


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(entries: list[dict]) -> None:
    if not entries:
        print(t("Noch keine Einträge. Mit 'add' beginnen.",
                "No entries yet. Use 'add' to start."))
        return

    sorted_entries = sorted(entries, key=lambda e: (
        e.get("side", "z"),
        e.get("relative", ""),
        e.get("condition", ""),
    ))

    print(t(f"\n  {'#':>3}  {'St.'}  {'Verwandter':<32} {'Erkrankung / Befund'}",
            f"\n  {'#':>3}  {'St.'}  {'Relative':<32} {'Condition / Finding'}"))
    print("  " + "─" * 90)

    current_side = None
    for i, e in enumerate(sorted_entries, 1):
        side = e.get("side", "")
        if side != current_side:
            current_side = side
            side_label = {
                "mütterlicherseits": t("── Mütterliche Linie ──────────────────────────",
                                       "── Maternal line ──────────────────────────────"),
                "väterlicherseits":  t("── Väterliche Linie ──────────────────────────",
                                       "── Paternal line ──────────────────────────────"),
                "unbekannt":         t("── Seite unbekannt ───────────────────────────",
                                       "── Side unknown ───────────────────────────────"),
            }.get(side, f"── {side} ────────────────────────────────────")
            print(f"\n  {side_label}")

        icon      = STATUS_ICONS.get(e.get("status", ""), "⚪")
        relative  = e.get("relative", "")
        condition = e.get("condition", "")
        onset     = e.get("age_onset", "")
        onset_str = f" (Onset ~{onset}J)" if onset else ""
        print(f"  {i:>3}  {icon}   {relative:<32} {condition}{onset_str}")
        if e.get("notes"):
            print(f"             ↳ {e['notes']}")
    print()


def cmd_list_by_condition(entries: list[dict]) -> None:
    """Cluster-Ansicht: gruppiert nach Erkrankung, zeigt Vererbungsmuster."""
    if not entries:
        print(t("Noch keine Einträge.", "No entries yet."))
        return

    clusters: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        clusters[e.get("condition", "?")].append(e)

    # Sortiert nach Anzahl Betroffener (absteigend)
    print(t("\n  Cluster-Ansicht: Erkrankungen nach Häufigkeit in der Familie",
            "\n  Cluster view: conditions by frequency in the family"))
    print("  " + "─" * 80)

    for condition, affected in sorted(clusters.items(), key=lambda x: -len(x[1])):
        icons = " ".join(STATUS_ICONS.get(e.get("status", ""), "⚪") for e in affected)
        sides = set(e.get("side", "") for e in affected)
        side_str = " + ".join(s for s in ["mütterlicherseits", "väterlicherseits"] if s in sides)
        print(f"\n  {condition}  [{side_str}]  {icons} {len(affected)}× betroffen")
        for e in sorted(affected, key=lambda x: x.get("relative", "")):
            icon   = STATUS_ICONS.get(e.get("status", ""), "⚪")
            onset  = f" (~{e['age_onset']}J)" if e.get("age_onset") else ""
            note   = f" — {e['notes']}" if e.get("notes") else ""
            print(f"    {icon} {e.get('relative','')}{onset}{note}")
    print()


def cmd_add(entries: list[dict]) -> list[dict]:
    print(t("\n── Neuer Familienanamneseeintrag ──────────────────────",
            "\n── New family history entry ────────────────────────────"))
    print(t("  (Strg+C jederzeit zum Abbrechen ohne Datenverlust)",
            "  (Ctrl+C at any time to cancel without data loss)"))
    print(t("  Tipp: 'vermutet' wählen wenn keine offizielle Diagnose vorliegt.",
            "  Tip: choose 'suspected' if no official diagnosis exists."))

    # Verwandter
    relative = _prompt(t("Verwandter", "Relative"),
                       choices=RELATIVES, required=True)

    # Seite automatisch ableiten, manuell überschreibbar
    side_default = _RELATIVE_SIDE.get(relative, "unbekannt")
    side_raw = _prompt(t("Seite (mütterlich/väterlich)", "Side (maternal/paternal)"),
                       default=side_default, choices=SIDES)
    side = side_raw if side_raw in SIDES else side_default

    # Erkrankung (zweistufig)
    print(t("\n  Schritt 2: Erkrankung — erst Kategorie wählen, dann Erkrankung.",
            "\n  Step 2: Condition — first choose category, then condition."))
    condition = _prompt_category_then_condition()

    # Status
    status_choices = [
        f"vermutet     — {t('keine offizielle Diagnose, anamnestische Beobachtung', 'no official diagnosis, anamnetic observation')}",
        f"bestätigt    — {t('ärztlich diagnostiziert', 'medically diagnosed')}",
        f"ausgeschlossen — {t('explizit getestet und negativ', 'explicitly tested and negative')}",
    ]
    status_raw = _prompt(t("Status", "Status"), choices=status_choices,
                         default="vermutet", required=True)
    status = status_raw.split()[0] if status_raw.split() else "vermutet"
    if status not in STATUSES:
        status = "vermutet"

    # Alter bei Erstmanifestation
    age_raw = _prompt(t("Alter bei Erstmanifestation (Jahre, optional, Enter überspringen)",
                        "Age at onset (years, optional, Enter to skip)"))
    age_onset = age_raw if age_raw.isdigit() else None

    # Notiz
    notes_raw = _prompt(t("Notiz — Kontext, Quelle, Einschränkungen (optional)",
                          "Notes — context, source, caveats (optional)"))
    notes = notes_raw or None

    entry: dict = {
        "relative":  relative,
        "side":      side,
        "condition": condition,
        "status":    status,
    }
    if age_onset:
        entry["age_onset"] = age_onset
    if notes:
        entry["notes"] = notes

    icon = STATUS_ICONS.get(status, "⚪")
    print(f"\n  → {icon} {relative} ({side}) — {condition} [{status}]")
    if age_onset:
        print(f"    Onset: ~{age_onset} Jahre")
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
    icon = STATUS_ICONS.get(removed.get("status", ""), "⚪")
    print(t(f"Gelöscht: {icon} {removed.get('relative','')} — {removed.get('condition','')}",
            f"Deleted: {icon} {removed.get('relative','')} — {removed.get('condition','')}"))
    return entries


def cmd_edit(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}",
                f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    e = entries[idx - 1]
    icon = STATUS_ICONS.get(e.get("status", ""), "⚪")
    print(t(f"\n── Eintrag #{idx} bearbeiten (Enter = unverändert) ──",
            f"\n── Edit entry #{idx} (Enter = keep unchanged) ──"))
    print(f"  {icon} {e.get('relative','')} ({e.get('side','')}) — {e.get('condition','')} [{e.get('status','')}]")

    relative = _prompt(t("Verwandter", "Relative"),
                       default=e.get("relative", ""), choices=RELATIVES)
    if relative:
        e["relative"] = relative

    side_raw = _prompt(t("Seite", "Side"), default=e.get("side", "unbekannt"),
                       choices=SIDES)
    if side_raw in SIDES:
        e["side"] = side_raw

    print(t("\n  Erkrankung ändern (Enter = unverändert, oder Kategorie wählen):",
            "\n  Change condition (Enter = keep, or choose category):"))
    new_cond = _prompt(t("Erkrankung / Befund", "Condition / finding"),
                       default=e.get("condition", ""))
    if new_cond and new_cond != e.get("condition"):
        e["condition"] = new_cond

    status_choices = [f"{s}  ({STATUS_ICONS[s]})" for s in STATUSES]
    status_raw = _prompt(t("Status", "Status"), default=e.get("status", "vermutet"),
                         choices=status_choices)
    new_status = status_raw.split()[0] if status_raw.split() else ""
    if new_status in STATUSES:
        e["status"] = new_status

    age_raw = _prompt(t("Alter bei Erstmanifestation", "Age at onset"),
                      default=e.get("age_onset", "") or "")
    e["age_onset"] = age_raw if age_raw.isdigit() else None

    notes_raw = _prompt(t("Notiz", "Notes"), default=e.get("notes", "") or "")
    e["notes"] = notes_raw or None

    entries[idx - 1] = e
    print(t("  ✓ Aktualisiert.", "  ✓ Updated."))
    return entries


def add_entry_noninteractive(entry: dict) -> None:
    """Add a family history entry non-interactively, reusing existing validation."""
    entries = load()
    
    # Validate required fields
    if "relative" not in entry or not entry["relative"]:
        raise ValueError(t("Verwandter ist ein Pflichtfeld", "Relative is required"))
    if "condition" not in entry or not entry["condition"]:
        raise ValueError(t("Erkrankung ist ein Pflichtfeld", "Condition is required"))
    
    # Validate against choice lists
    relative = entry["relative"]
    if relative not in RELATIVES:
        raise ValueError(t(f"Ungültiger Verwandter: {relative}", f"Invalid relative: {relative}"))
    
    side = entry.get("side", _RELATIVE_SIDE.get(relative, "unbekannt"))
    if side not in SIDES:
        raise ValueError(t(f"Ungültige Seite: {side}", f"Invalid side: {side}"))
    
    status = entry.get("status", "vermutet")
    if status not in STATUSES:
        raise ValueError(t(f"Ungültiger Status: {status}", f"Invalid status: {status}"))
    
    # Build validated entry
    validated_entry: dict = {
        "relative": relative,
        "side": side,
        "condition": entry["condition"],
        "status": status,
    }
    
    # Optional fields
    if "age_onset" in entry and entry["age_onset"]:
        validated_entry["age_onset"] = entry["age_onset"]
    if "notes" in entry and entry["notes"]:
        validated_entry["notes"] = entry["notes"]
    
    entries.append(validated_entry)
    save(entries)


def cmd_export(entries: list[dict]) -> None:
    """Markdown-Tabelle für Arztbriefe, chronologisch nach Seite + Verwandtem."""
    if not entries:
        print(t("Keine Einträge.", "No entries."))
        return

    sorted_entries = sorted(entries, key=lambda e: (
        e.get("side", "z"), e.get("relative", ""), e.get("condition", "")
    ))

    print(t(
        "| Verwandter | Seite | Erkrankung / Befund | Status | Onset | Notiz |",
        "| Relative | Side | Condition / Finding | Status | Onset | Notes |",
    ))
    print("|---|---|---|---|---|---|")
    for e in sorted_entries:
        icon = STATUS_ICONS.get(e.get("status", ""), "⚪")
        cols = [
            e.get("relative", ""),
            e.get("side", ""),
            e.get("condition", ""),
            f"{icon} {e.get('status','')}",
            f"~{e['age_onset']}J" if e.get("age_onset") else "—",
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
            "Familienanamnese verwalten (~/.config/kyoro/family_history.json)",
            "Manage family history (~/.config/kyoro/family_history.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  list                    Einträge nach Linie (mütterlich/väterlich) anzeigen
  list --by-condition     Cluster-Ansicht: welche Erkrankungen häufen sich?
  add                     Interaktiv neuen Eintrag anlegen
  edit <nr>               Eintrag bearbeiten
  delete <nr>             Eintrag löschen
  export                  Markdown-Tabelle für Arztbriefe ausgeben

Status-Icons:
  ✅  bestätigt    — ärztlich diagnostiziert
  ❓  vermutet     — anamnestische Beobachtung ohne Diagnose
  ❌  ausgeschlossen — explizit getestet und negativ

Hinweis: Einträge mit Status "vermutet" in Arztbriefen explizit als
"unbestätigte Familienanamnese" kennzeichnen.
""", """
Commands:
  list                    Show entries by line (maternal/paternal)
  list --by-condition     Cluster view: which conditions cluster in the family?
  add                     Interactively add a new entry
  edit <nr>               Edit an entry
  delete <nr>             Delete an entry
  export                  Output Markdown table for doctor's letters

Status icons:
  ✅  confirmed    — medically diagnosed
  ❓  suspected    — anamnetic observation without diagnosis
  ❌  excluded     — explicitly tested and negative

Note: entries with status "suspected" should be labelled as
"unconfirmed family history" in doctor's letters.
"""),
    )
    ap.add_argument("command", choices=["list", "add", "edit", "delete", "export"],
                    help=t("Aktion", "Action"))
    ap.add_argument("args", nargs="*",
                    help=t("Zusatzargumente: Eintragsnummer oder --by-condition",
                           "Extra arguments: entry number or --by-condition"))
    ap.add_argument("--by-condition", action="store_true",
                    help=t("Cluster-Ansicht: nach Erkrankung gruppieren",
                           "Cluster view: group by condition"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    entries = load()

    if args.command == "list":
        if args.by_condition:
            cmd_list_by_condition(entries)
        else:
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
