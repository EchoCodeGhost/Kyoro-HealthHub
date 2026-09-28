#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_exposure_history.py — Expositionsanamnese verwalten (Zoonosen, Beruf, Sexualanamnese)

@tier        infrastructure
@purpose.de  Dokumentiert Tierkontakte, berufliche Expositionen, Kindheitsumfeld und
             Sexualanamnese — wichtig für die Differenzialdiagnose ungeklärter Symptome
             (Zoonosen wie Q-Fieber, Brucella, Leptospira, Echinococcus, Toxoplasma;
             STI-Screening-Historie).
@purpose.en  Documents animal contacts, occupational exposures, childhood environment
             and sexual history — relevant context when working up unexplained
             symptoms (zoonoses such as Q fever, Brucella, Leptospira, Echinococcus,
             Toxoplasma; STI screening history).
@method.de   Speichert unter ~/.config/kyoro/exposure_history.json (lokal, nicht im
             Repo). Ein einzelnes verschachteltes Objekt statt einer Liste:
             {{childhood_environment, animal_contacts[], occupational_exposures[],
             sexual_history{{multiple_partners, hpv_vaccination, sti_screening[], known_stis[]}}}}.
             Strg+C bricht jederzeit ohne Datenverlust ab.
@method.en   Stores in ~/.config/kyoro/exposure_history.json (local only, not in
             repo). A single nested object rather than a list:
             {{childhood_environment, animal_contacts[], occupational_exposures[],
             sexual_history{{multiple_partners, hpv_vaccination, sti_screening[], known_stis[]}}}}.
             Ctrl+C aborts at any time without data loss.
@reads       ~/.config/kyoro/exposure_history.json
@writes      ~/.config/kyoro/exposure_history.json
@limits.de   Keine automatische Risikoberechnung für dauerhafte/regelmäßige Kontakte
             — reine Dokumentation für Differenzialdiagnostik durch Ärzte. Ausnahme:
             bei einmaligem Tierkontakt (`exposure == "einmalig"`) gibt es sofort
             eine leichtgewichtige, heuristische Erreger-Hinweisliste (ANIMAL_SYNDROME_MAP
             gegen scripts/analysis/syndromes/*.json) direkt nach dem Speichern —
             kein Ersatz für die vollständige, geo-/zeitbasierte
             analyse_pathogen_exposure.py, sondern ein sofortiger erster Hinweis
             für akute Einzelereignisse (z. B. Tierunfall), die sonst bis zum
             nächsten manuellen Analyse-Lauf unbeachtet blieben.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No automatic risk calculation for ongoing/regular contacts — documentation
             only, for physicians to use during differential workup. Exception: for a
             one-time animal contact (`exposure == "einmalig"`), an immediate,
             lightweight heuristic pathogen hint (ANIMAL_SYNDROME_MAP matched against
             scripts/analysis/syndromes/*.json) is printed right after saving — not a
             replacement for the full geo-/time-matched analyse_pathogen_exposure.py,
             just an instant first pointer for acute single events (e.g. an animal
             accident) that would otherwise sit unnoticed until the next manual
             analysis run.
@usage
    python3 scripts/utils/manage/personal/manage_exposure_history.py show
    python3 scripts/utils/manage/personal/manage_exposure_history.py childhood
    python3 scripts/utils/manage/personal/manage_exposure_history.py animal add
    python3 scripts/utils/manage/personal/manage_exposure_history.py animal delete 2
    python3 scripts/utils/manage/personal/manage_exposure_history.py occupation add
    python3 scripts/utils/manage/personal/manage_exposure_history.py occupation delete 1
    python3 scripts/utils/manage/personal/manage_exposure_history.py sexual set
    python3 scripts/utils/manage/personal/manage_exposure_history.py sti add
    python3 scripts/utils/manage/personal/manage_exposure_history.py sti delete 1
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.config_backup import backup_before_write, commit_config_change
from health_config import KYORO_CONFIG_DIR

EXPOSURE_FILE = KYORO_CONFIG_DIR / "exposure_history.json"
SYNDROMES_DIR = Path(__file__).parent.parent.parent.parent / "analysis" / "syndromes"

ANIMALS = [
    "Rind", "Schaf/Ziege", "Pferd", "Hund", "Katze", "Geflügel",
    "Reh", "Hirsch", "Wildschwein", "Fuchs", "Nagetier (Maus/Ratte)",
    "Fledermaus", "Wildvogel", "Zecke (Zeckenstich)", "Wildtier (sonstig)",
    "Sonstiges",
]
EXPOSURE_LEVELS = ["dauerhaft", "regelmäßig", "saisonal", "einmalig"]

# Heuristische Tier→Erreger-Zuordnung (Syndrom-Slugs aus scripts/analysis/syndromes/).
# Wie die Expositionsanalyse (analyse_pathogen_exposure.py) rein projektintern und
# nicht epidemiologisch validiert — nur zur Hypothesengeneration fürs Arztgespräch.
ANIMAL_SYNDROME_MAP: dict[str, list[str]] = {
    "Rind":                     ["q_fieber", "brucellose", "leptospirose"],
    "Schaf/Ziege":              ["q_fieber", "brucellose"],
    "Pferd":                    ["leptospirose", "borreliose", "fsme", "rickettsia"],
    "Hund":                     ["leptospirose", "toxoplasmose", "borreliose"],
    "Katze":                    ["toxoplasmose", "bartonellose"],
    "Geflügel":                 ["ornithose", "influenza"],
    "Reh":                      ["tularaemie", "borreliose", "fsme", "anaplasmose",
                                  "babesiose", "rickettsia", "tick_coinfections"],
    "Hirsch":                   ["tularaemie", "borreliose", "fsme", "anaplasmose",
                                  "babesiose", "rickettsia", "tick_coinfections"],
    "Wildschwein":              ["brucellose", "toxoplasmose"],
    "Fuchs":                    ["tularaemie", "borreliose"],
    "Nagetier (Maus/Ratte)":    ["hantavirus", "leptospirose", "tularaemie", "yersiniose"],
    "Fledermaus":               [],  # kein passender Slug hinterlegt (z. B. Lyssavirus) — bewusst leer statt erraten
    "Wildvogel":                ["ornithose", "west_nile", "influenza"],
    "Zecke (Zeckenstich)":      ["borreliose", "neuroborreliose", "fsme", "anaplasmose",
                                  "babesiose", "rickettsia", "tick_coinfections"],
    "Wildtier (sonstig)":       ["tularaemie", "rickettsia"],
}


def _lookup_animal_syndromes(animal: str) -> list[dict]:
    """Load name_de + refs for the syndromes mapped to `animal`, skipping missing files."""
    results = []
    for slug in ANIMAL_SYNDROME_MAP.get(animal, []):
        f = SYNDROMES_DIR / f"{slug}.json"
        if not f.exists():
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        results.append({"slug": slug, "name_de": rec.get("name_de", slug),
                         "refs": rec.get("refs")})
    return results


def _print_immediate_exposure_hint(animal: str) -> None:
    """Print a lightweight, immediate pathogen hint for a freshly logged one-time contact.

    Not a replacement for analyse_pathogen_exposure.py's full geo/time-matched
    analysis — just an instant lookup against ANIMAL_SYNDROME_MAP so a single,
    unusual event (e.g. an accident) doesn't have to wait for a separate,
    manually-triggered analysis run to surface relevant pathogens.
    """
    hits = _lookup_animal_syndromes(animal)
    if not hits:
        return
    print(t(f"\n  ⚠ Bei einmaligem Kontakt mit '{animal}' relevante Erreger "
            "(heuristisch, keine Diagnose):",
            f"\n  ⚠ Pathogens potentially relevant for a one-time contact with "
            f"'{animal}' (heuristic, not a diagnosis):"))
    for h in hits:
        print(f"    - {h['name_de']}")
    print(t("  → Bei Symptomen (Fieber, Hautveränderung, Lymphknotenschwellung, "
            "Müdigkeit) zeitnah ärztlich abklären lassen und diesen Kontakt "
            "erwähnen.",
            "  → If symptoms develop (fever, skin changes, lymph node swelling, "
            "fatigue), see a doctor promptly and mention this contact."))


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> dict:
    if EXPOSURE_FILE.exists():
        return json.loads(EXPOSURE_FILE.read_text(encoding="utf-8"))
    return {}


def save(data: dict) -> None:
    EXPOSURE_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup_before_write(EXPOSURE_FILE)
    EXPOSURE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    commit_config_change(EXPOSURE_FILE, "exposure_history: aktualisiert")
    print(t(f"Gespeichert: {EXPOSURE_FILE}", f"Saved: {EXPOSURE_FILE}"))


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


def _confirm(label: str, default: bool = False) -> bool:
    dflt = t("J/n", "Y/n") if default else t("j/N", "y/N")
    try:
        raw = input(f"  {label} [{dflt}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(t("\n  Abgebrochen.", "\n  Cancelled."))
        sys.exit(0)
    if not raw:
        return default
    return raw in ("j", "y", "ja", "yes")


# ── show ──────────────────────────────────────────────────────────────────────

def cmd_show(data: dict) -> None:
    if not data:
        print(t("Noch keine Expositionsanamnese erfasst.",
                "No exposure history recorded yet."))
        return

    if data.get("childhood_environment"):
        print(t("\n# Kindheitsumfeld", "\n# Childhood environment"))
        print(f"  {data['childhood_environment']}")

    animals = data.get("animal_contacts", [])
    if animals:
        print(t("\n# Tierkontakte", "\n# Animal contacts"))
        for i, a in enumerate(animals, 1):
            ctx = f" — {a['context']}" if a.get("context") else ""
            print(f"  {i:>2}. {a.get('animal','')}: {a.get('exposure','')} "
                  f"({a.get('period','')}){ctx}")

    occ = data.get("occupational_exposures", [])
    if occ:
        print(t("\n# Berufliche Expositionen", "\n# Occupational exposures"))
        for i, o in enumerate(occ, 1):
            print(f"  {i:>2}. {o.get('occupation','')} ({o.get('period','')}): "
                  f"{o.get('exposure','')}")

    sh = data.get("sexual_history", {})
    if sh:
        print(t("\n# Sexualanamnese", "\n# Sexual history"))
        print(f"  {t('Wechselnde Partner', 'Multiple partners')}: "
              f"{'ja' if sh.get('multiple_partners') else 'nein'}")
        print(f"  {t('HPV-Impfung', 'HPV vaccination')}: "
              f"{'ja' if sh.get('hpv_vaccination') else 'nein'}")
        for i, sc in enumerate(sh.get("sti_screening", []), 1):
            panel = ", ".join(sc.get("panel", []))
            print(f"    {i:>2}. {sc.get('date','')}: {panel} → {sc.get('result','')}")
        known = sh.get("known_stis", [])
        if known:
            print(f"  {t('Bekannte STIs', 'Known STIs')}: {', '.join(known)}")
    print()


# ── childhood ─────────────────────────────────────────────────────────────────

def cmd_childhood(data: dict) -> dict:
    current = data.get("childhood_environment", "")
    value = _prompt(t("Kindheitsumfeld (z. B. ländlich/städtisch, Region, Kontext)",
                      "Childhood environment (e.g. rural/urban, region, context)"),
                    default=current)
    if value:
        data["childhood_environment"] = value
    return data


# ── animal contacts ───────────────────────────────────────────────────────────

def cmd_animal_add(data: dict) -> dict:
    print(t("\n── Neuer Tierkontakt ──────────────────────", "\n── New animal contact ──────────────────────"))
    animal   = _prompt(t("Tierart", "Animal"), choices=ANIMALS, required=True)
    exposure = _prompt(t("Expositionsgrad", "Exposure level"), choices=EXPOSURE_LEVELS,
                       required=True)
    period   = _prompt(t("Zeitraum (z. B. 1970–1985)", "Period (e.g. 1970-1985)"))
    context  = _prompt(t("Kontext (Ort, Zoonoserisiko, Anmerkung)",
                         "Context (place, zoonosis risk, note)"))

    entry: dict = {"animal": animal, "exposure": exposure}
    if period:
        entry["period"] = period
    if context:
        entry["context"] = context

    data.setdefault("animal_contacts", []).append(entry)
    print(t(f"  ✓ Hinzugefügt (Eintrag #{len(data['animal_contacts'])})",
            f"  ✓ Added (entry #{len(data['animal_contacts'])})"))
    if exposure == "einmalig":
        _print_immediate_exposure_hint(animal)
    return data


def add_animal_contact_noninteractive(entry: dict) -> dict:
    """Add an animal contact entry non-interactively, reusing existing validation."""
    data = load()
    
    # Validate required fields
    if "animal" not in entry or not entry["animal"]:
        raise ValueError(t("Tierart ist ein Pflichtfeld", "Animal is required"))
    if "exposure" not in entry or not entry["exposure"]:
        raise ValueError(t("Expositionsgrad ist ein Pflichtfeld", "Exposure level is required"))
    
    # Validate against choice lists
    animal = entry["animal"]
    if animal not in ANIMALS:
        raise ValueError(t(f"Ungültige Tierart: {animal}", f"Invalid animal: {animal}"))
    
    exposure = entry["exposure"]
    if exposure not in EXPOSURE_LEVELS:
        raise ValueError(t(f"Ungültiger Expositionsgrad: {exposure}", f"Invalid exposure level: {exposure}"))
    
    # Build validated entry
    validated_entry: dict = {
        "animal": animal,
        "exposure": exposure,
    }
    
    # Optional fields
    if "period" in entry and entry["period"]:
        validated_entry["period"] = entry["period"]
    if "context" in entry and entry["context"]:
        validated_entry["context"] = entry["context"]
    
    data.setdefault("animal_contacts", []).append(validated_entry)
    save(data)
    if exposure == "einmalig":
        _print_immediate_exposure_hint(animal)
    return data


def add_occupational_exposure_noninteractive(entry: dict) -> dict:
    """Add an occupational exposure entry non-interactively, reusing existing validation."""
    data = load()
    
    # Validate required fields
    if "occupation" not in entry or not entry["occupation"]:
        raise ValueError(t("Tätigkeit ist ein Pflichtfeld", "Occupation is required"))
    if "exposure" not in entry or not entry["exposure"]:
        raise ValueError(t("Exposition ist ein Pflichtfeld", "Exposure is required"))
    
    # Build validated entry
    validated_entry: dict = {
        "occupation": entry["occupation"],
        "exposure": entry["exposure"],
    }
    
    # Optional fields
    if "period" in entry and entry["period"]:
        validated_entry["period"] = entry["period"]
    
    data.setdefault("occupational_exposures", []).append(validated_entry)
    save(data)
    return data


def cmd_animal_delete(data: dict, idx: int) -> dict:
    animals = data.get("animal_contacts", [])
    if idx < 1 or idx > len(animals):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(animals)}",
                f"Invalid number. Available: 1–{len(animals)}"))
        return data
    removed = animals.pop(idx - 1)
    print(t(f"Gelöscht: {removed.get('animal','')}", f"Deleted: {removed.get('animal','')}"))
    return data


# ── occupational exposures ────────────────────────────────────────────────────

def cmd_occupation_add(data: dict) -> dict:
    print(t("\n── Neue berufliche Exposition ──────────────",
            "\n── New occupational exposure ────────────────"))
    occupation = _prompt(t("Tätigkeit / Einsatzort", "Occupation / assignment"), required=True)
    period     = _prompt(t("Zeitraum (z. B. 2001–2005)", "Period (e.g. 2001-2005)"))
    exposure   = _prompt(t("Exposition (Stäube, Chemikalien, Hitze, Höhe …)",
                           "Exposure (dusts, chemicals, heat, altitude …)"), required=True)

    entry: dict = {"occupation": occupation, "exposure": exposure}
    if period:
        entry["period"] = period

    data.setdefault("occupational_exposures", []).append(entry)
    print(t(f"  ✓ Hinzugefügt (Eintrag #{len(data['occupational_exposures'])})",
            f"  ✓ Added (entry #{len(data['occupational_exposures'])})"))
    return data


def cmd_occupation_delete(data: dict, idx: int) -> dict:
    occ = data.get("occupational_exposures", [])
    if idx < 1 or idx > len(occ):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(occ)}",
                f"Invalid number. Available: 1–{len(occ)}"))
        return data
    removed = occ.pop(idx - 1)
    print(t(f"Gelöscht: {removed.get('occupation','')}",
            f"Deleted: {removed.get('occupation','')}"))
    return data


# ── sexual history ────────────────────────────────────────────────────────────

def cmd_sexual_set(data: dict) -> dict:
    sh = data.setdefault("sexual_history", {})
    print(t("\n── Sexualanamnese ──────────────────────────", "\n── Sexual history ──────────────────────────"))
    sh["multiple_partners"] = _confirm(t("Häufig wechselnde Partner?", "Multiple partners?"),
                                       default=sh.get("multiple_partners", False))
    sh["hpv_vaccination"] = _confirm(t("HPV-Impfung erfolgt?", "HPV vaccination done?"),
                                     default=sh.get("hpv_vaccination", False))
    sh.setdefault("sti_screening", [])
    sh.setdefault("known_stis", [])
    print(t("  ✓ Aktualisiert.", "  ✓ Updated."))
    return data


def cmd_sti_add(data: dict) -> dict:
    sh = data.setdefault("sexual_history", {})
    print(t("\n── Neues STI-Screening ──────────────────────", "\n── New STI screening ────────────────────────"))
    date  = _prompt(t("Datum (YYYY-MM-DD)", "Date (YYYY-MM-DD)"), required=True)
    panel_raw = _prompt(t("Getestete Erreger (kommagetrennt)", "Pathogens tested (comma-separated)"),
                        required=True)
    panel  = [p.strip() for p in panel_raw.split(",") if p.strip()]
    result = _prompt(t("Ergebnis", "Result"), default="alle negativ", required=True)

    sh.setdefault("sti_screening", []).append({"date": date, "panel": panel, "result": result})
    print(t(f"  ✓ Hinzugefügt (Eintrag #{len(sh['sti_screening'])})",
            f"  ✓ Added (entry #{len(sh['sti_screening'])})"))
    return data


def cmd_sti_delete(data: dict, idx: int) -> dict:
    sh = data.get("sexual_history", {})
    screenings = sh.get("sti_screening", [])
    if idx < 1 or idx > len(screenings):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(screenings)}",
                f"Invalid number. Available: 1–{len(screenings)}"))
        return data
    removed = screenings.pop(idx - 1)
    print(t(f"Gelöscht: Screening {removed.get('date','')}",
            f"Deleted: screening {removed.get('date','')}"))
    return data


# ── Main ──────────────────────────────────────────────────────────────────────

def _get_idx(args_list: list[str], prompt_text: str) -> int:
    if args_list and args_list[0].isdigit():
        return int(args_list[0])
    try:
        return int(input(f"  {prompt_text} ").strip())
    except (ValueError, EOFError, KeyboardInterrupt):
        sys.exit(0)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=t(
            "Expositionsanamnese verwalten (~/.config/kyoro/exposure_history.json)",
            "Manage exposure history (~/.config/kyoro/exposure_history.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  show                       Vollständige Expositionsanamnese anzeigen
  childhood                  Kindheitsumfeld setzen/ändern
  animal add                 Tierkontakt hinzufügen
  animal delete <nr>         Tierkontakt löschen
  occupation add             Berufliche Exposition hinzufügen
  occupation delete <nr>     Berufliche Exposition löschen
  sexual set                 Sexualanamnese-Basisdaten setzen
  sti add                    STI-Screening-Ergebnis hinzufügen
  sti delete <nr>            STI-Screening-Ergebnis löschen
""", """
Commands:
  show                       Show the full exposure history
  childhood                  Set/change childhood environment
  animal add                 Add an animal contact
  animal delete <nr>         Delete an animal contact
  occupation add             Add an occupational exposure
  occupation delete <nr>     Delete an occupational exposure
  sexual set                 Set sexual history base data
  sti add                    Add an STI screening result
  sti delete <nr>            Delete an STI screening result
"""),
    )
    ap.add_argument("group", choices=["show", "childhood", "animal", "occupation", "sexual", "sti"],
                    help=t("Bereich", "Section"))
    ap.add_argument("action", nargs="?", default=None,
                    help=t("Unterbefehl (add/delete/set) oder Nummer", "Subcommand (add/delete/set) or number"))
    ap.add_argument("args", nargs="*", help=t("Zusatzargumente", "Extra arguments"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    data = load()

    if args.group == "show":
        cmd_show(data)
        return

    if args.group == "childhood":
        data = cmd_childhood(data)
        save(data)
        return

    if args.group == "animal":
        if args.action == "add":
            data = cmd_animal_add(data)
        elif args.action == "delete":
            idx = _get_idx(args.args, t("Welche Nummer löschen?", "Which number to delete?"))
            data = cmd_animal_delete(data, idx)
        else:
            cmd_show(data)
            return
        save(data)
        return

    if args.group == "occupation":
        if args.action == "add":
            data = cmd_occupation_add(data)
        elif args.action == "delete":
            idx = _get_idx(args.args, t("Welche Nummer löschen?", "Which number to delete?"))
            data = cmd_occupation_delete(data, idx)
        else:
            cmd_show(data)
            return
        save(data)
        return

    if args.group == "sexual":
        if args.action == "set":
            data = cmd_sexual_set(data)
            save(data)
        else:
            cmd_show(data)
        return

    if args.group == "sti":
        if args.action == "add":
            data = cmd_sti_add(data)
        elif args.action == "delete":
            idx = _get_idx(args.args, t("Welche Nummer löschen?", "Which number to delete?"))
            data = cmd_sti_delete(data, idx)
        else:
            cmd_show(data)
            return
        save(data)
        return


if __name__ == "__main__":
    main()
