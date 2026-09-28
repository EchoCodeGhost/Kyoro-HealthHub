#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_travel_history.py — Reiseverlauf verwalten


@tier        infrastructure
@purpose.de  Erfasst besuchte Regionen und Zeiträume für die spätere Analyse.
             Ermöglicht die Korrelation von Reisen mit Gesundheitsdaten.
@purpose.en  Tracks visited regions and time periods for later analysis.
             Enables correlation of travel with health data.
@method.de   Speichert unter ~/.config/kyoro/travel_history.json (lokal, nicht im Repo).
             Unterstützt das Erfassen von Region, Land, Beginn, Ende und Kontext.
@method.en   Stores in ~/.config/kyoro/travel_history.json (local only, not in repo).
             Supports recording of region, country, start, end, and context.
@reads       ~/.config/kyoro/travel_history.json
@writes      ~/.config/kyoro/travel_history.json
@limits.de   Keine Validierung der Regionscodes. Datei liegt ausserhalb des Repos.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No validation of region codes. File is stored outside the repository.
@usage
    python3 scripts/utils/manage/personal/manage_travel_history.py list
    python3 scripts/utils/manage/personal/manage_travel_history.py add
    python3 scripts/utils/manage/personal/manage_travel_history.py add "Region Name" YYYY-MM YYYY-MM-DD
    python3 scripts/utils/manage/personal/manage_travel_history.py delete 3
    python3 scripts/utils/manage/personal/manage_travel_history.py edit 3
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.config_backup import backup_before_write, commit_config_change
from health_config import KYORO_CONFIG_DIR

TRAVEL_FILE = KYORO_CONFIG_DIR / "travel_history.json"

# ── Wissensbasis für Vorschläge ───────────────────────────────────────────────

COUNTRY_ISO = {
    "Spanien": "ES", "Deutschland": "DE", "Frankreich": "FR", "Italien": "IT",
    "Griechenland": "GR", "Türkei": "TR", "Portugal": "PT", "Kroatien": "HR",
    "Österreich": "AT", "Schweiz": "CH", "Niederlande": "NL", "Belgien": "BE",
    "Polen": "PL", "Tschechien": "CZ", "Ungarn": "HU", "Slowakei": "SK",
    "Slowenien": "SI", "Serbien": "RS", "Bosnien": "BA",
    "Montenegro": "ME", "Albanien": "AL", "Nordmazedonien": "MK",
    "Bulgarien": "BG", "Rumänien": "RO", "Schweden": "SE",
    "Norwegen": "NO", "Dänemark": "DK", "Finnland": "FI", "Irland": "IE",
    "Großbritannien": "GB", "Ägypten": "EG", "Marokko": "MA", "Tunesien": "TN",
    "Israel": "IL", "Jordanien": "JO", "Vereinigte Arabische Emirate": "AE",
    "Thailand": "TH", "Vietnam": "VN", "Indonesien": "ID", "Malaysia": "MY",
    "Philippinen": "PH", "Japan": "JP", "Indien": "IN", "Sri Lanka": "LK",
    "Mexiko": "MX", "Brasilien": "BR", "Argentinien": "AR", "Kolumbien": "CO",
    "Peru": "PE", "Kuba": "CU", "Dominikanische Republik": "DO",
    "USA": "US", "Kanada": "CA", "Australien": "AU", "Neuseeland": "NZ",
    "Kenia": "KE", "Tansania": "TZ", "Südafrika": "ZA",
}

# Bekannte Subregionen pro Land
KNOWN_SUBREGIONS = {
    "Spanien": [
        "Kanarische Inseln", "Balearen", "Mallorca", "Ibiza", "Menorca",
        "Fuerteventura", "Gran Canaria", "Teneriffa", "Lanzarote",
        "Katalonien", "Andalusien", "Valencia", "Costa del Azahar",
        "Costa Brava", "Costa del Sol", "Costa Blanca", "Galicien",
        "Baskenland", "Madrid", "Kastilien",
    ],
    "Italien": [
        "Sizilien", "Sardinien", "Toskana", "Venetien", "Ligurien",
        "Kalabrien", "Apulien", "Kampanien", "Südtirol",
    ],
    "Griechenland": [
        "Kreta", "Korfu", "Rhodos", "Santorini", "Mykonos", "Zakynthos",
        "Athen", "Thessaloniki", "Peloponnes", "Dodekanes", "Zypern",
    ],
    "Türkei": [
        "Ägäisküste", "Türkische Riviera", "Antalya", "Bodrum", "Marmaris",
        "Istanbul", "Kappadokien", "Schwarzmeerküste", "Alanya", "Side",
    ],
    "Deutschland": [
        "Bayern", "Baden-Württemberg", "Schwarzwald", "Allgäu",
        "Bayerischer Wald", "Brandenburg", "Thüringen", "Hessen",
        "Mecklenburg-Vorpommern", "Nordrhein-Westfalen",
    ],
    "Österreich": ["Tirol", "Salzburg", "Wien", "Steiermark", "Kärnten"],
    "Bulgarien": [
        "Schwarzmeerküste", "Sonnenstrand", "Goldstrand", "Nessebar",
        "Balkangebirge", "Rhodopen", "Sofia", "Plovdiv", "Varna", "Burgas",
    ],
    "Kroatien": [
        "Dalmatien", "Istrien", "Kvarner", "Split", "Dubrovnik",
        "Zagreb", "Hvar", "Brač", "Korčula",
    ],
    "Ägypten": ["Rotes Meer", "Hurghada", "Sharm el-Sheikh", "Luxor", "Kairo"],
    "Marokko": ["Marrakesch", "Agadir", "Fès", "Casablanca", "Sahara"],
    "Thailand": ["Bangkok", "Chiang Mai", "Phuket", "Koh Samui", "Koh Tao"],
    "Indonesien": ["Bali", "Java", "Lombok", "Komodo", "Sumatra"],
}

# Klimazonen pro Land/Region (Vorschlag)
CLIMATE_SUGGESTIONS = {
    "Kanarische Inseln": "subtropisch",
    "Fuerteventura": "subtropisch",
    "Gran Canaria": "subtropisch",
    "Teneriffa": "subtropisch",
    "Lanzarote": "subtropisch",
    "Balearen": "mediterran",
    "Mallorca": "mediterran",
    "Ibiza": "mediterran",
    "Menorca": "mediterran",
    "Costa del Azahar": "mediterran",
    "Costa Brava": "mediterran",
    "Costa del Sol": "mediterran",
    "Costa Blanca": "mediterran",
    "Sizilien": "mediterran",
    "Sardinien": "mediterran",
    "Kreta": "mediterran",
    "Rhodos": "mediterran",
    "Türkische Riviera": "mediterran",
    "Antalya": "mediterran",
    "Rotes Meer": "subtropisch",
    "Marokko": "mediterran",
    "Agadir": "subtropisch",
    "Bayern": "kontinental",
    "Baden-Württemberg": "kontinental",
    "Schwarzwald": "kontinental",
    "Schwarzmeerküste": "osteuropaeisch",
    "Sonnenstrand": "osteuropaeisch",
    "Goldstrand": "osteuropaeisch",
    "Bulgarien": "osteuropaeisch",
    "Dalmatien": "mediterran",
    "Istrien": "mediterran",
    "Dubrovnik": "mediterran",
    "Kroatien": "mediterran",
    "Thailand": "tropisch",
    "Bali": "tropisch",
    "Phuket": "tropisch",
    "Kuba": "tropisch",
    "Dominikanische Republik": "tropisch",
    "Kenia": "tropisch",
    "Tansania": "tropisch",
    "Brasilien": "tropisch",
    "Mexiko": "subtropisch",
}

CLIMATE_ZONES = [
    "tropisch", "subtropisch", "mediterran", "kontinental",
    "osteuropaeisch", "skandinavisch", "suedostasiatisch",
    "afrikanisch", "nordafrikanisch", "nahöstlich", "lateinamerikanisch",
]


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    if TRAVEL_FILE.exists():
        return json.loads(TRAVEL_FILE.read_text(encoding="utf-8"))
    return []


def save(entries: list[dict]) -> None:
    TRAVEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup_before_write(TRAVEL_FILE)
    TRAVEL_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    commit_config_change(TRAVEL_FILE, f"travel_history: {len(entries)} Einträge gespeichert")
    print(t(f"Gespeichert: {TRAVEL_FILE}", f"Saved: {TRAVEL_FILE}"))


def _parse_date(s: str, end: bool = False) -> str | None:
    """Parst YYYY-MM-DD, YYYY-MM (→ erster/letzter Tag), YYYY (→ Jan/Dez)."""
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
    if len(s) == 4:  # YYYY
        return f"{s}-12-31" if end else f"{s}-01-01"
    return s


def _prompt(label: str, default: str = "", choices: list[str] = None) -> str:
    """Fragt nach Eingabe; zeigt Optionen wenn choices gegeben."""
    if choices:
        print(t(f"\n  Vorschläge für {label}:", f"\n  Suggestions for {label}:"))
        for i, c in enumerate(choices[:12], 1):
            print(f"    {i:2}. {c}")
        print(t("    (oder freie Eingabe)", "    (or free text input)"))

    dflt_str = f" [{default}]" if default else ""
    try:
        sys.stdout.write(f"  {label}{dflt_str}: ")
        sys.stdout.flush()
        raw = sys.stdin.buffer.readline()
        val = raw.decode("utf-8", errors="replace").rstrip("\n").strip()
    except (EOFError, KeyboardInterrupt, AttributeError):
        # Fallback auf input() wenn stdin kein Buffer hat
        try:
            val = input(f"  {label}{dflt_str}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

    # Zahl → Auswahl aus choices
    if choices and val.isdigit():
        idx = int(val) - 1
        if 0 <= idx < len(choices):
            return choices[idx]

    return val or default


def _fmt_date_range(entry: dict) -> str:
    d1 = entry.get("date_from", "?")[:7]
    d2 = entry.get("date_to", "?")[:7]
    return d1 if d1 == d2 else f"{d1} – {d2}"


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(entries: list[dict]) -> None:
    if not entries:
        print(t("Noch keine Einträge. Mit 'add' beginnen.", "No entries yet. Use 'add' to start."))
        return

    print(t(
        f"\n  {'#':>3}  {'Ort':<22} {'Land':<14} {'Subregion':<22} {'Klima':<14} {'Zeitraum'}",
        f"\n  {'#':>3}  {'Place':<22} {'Country':<14} {'Subregion':<22} {'Climate':<14} {'Period'}",
    ))
    print("  " + "─" * 90)
    for i, e in enumerate(entries, 1):
        print(
            f"  {i:>3}  {e.get('name',''):<22} {e.get('country',''):<14} "
            f"{e.get('subregion',''):<22} {e.get('climate_zone',''):<14} "
            f"{_fmt_date_range(e)}"
        )
        if e.get("notes"):
            print(f"       ↳ {e['notes']}")
    print()


def cmd_add(entries: list[dict], quick_args: list[str] = None) -> list[dict]:
    """Interaktiver Add. quick_args: [name, date_from, date_to] für Schnelleingabe."""
    print(t("\n── Neuer Reiseeintrag ──────────────────────────────",
            "\n── New travel entry ────────────────────────────────"))

    # Name
    default_name = quick_args[0] if quick_args else ""
    name = _prompt("Ort / Name", default=default_name)
    if not name:
        print(t("Abgebrochen.", "Cancelled."))
        return entries

    # Land
    country_choices = list(COUNTRY_ISO.keys())
    country = _prompt("Land", choices=country_choices[:20])
    if not country:
        country = "Deutschland"
    iso = COUNTRY_ISO.get(country, "")

    # Subregion
    sub_choices = KNOWN_SUBREGIONS.get(country, [])
    # Wenn Name schon eine bekannte Subregion ist, vorschlagen
    name_as_sub = name if name in sum(KNOWN_SUBREGIONS.values(), []) else ""
    subregion = _prompt("Subregion", default=name_as_sub or "", choices=sub_choices or None)

    # Klimazone
    climate_default = (
        CLIMATE_SUGGESTIONS.get(subregion)
        or CLIMATE_SUGGESTIONS.get(name)
        or CLIMATE_SUGGESTIONS.get(country)
        or ""
    )
    climate = _prompt("Klimazone", default=climate_default, choices=CLIMATE_ZONES)

    # Datum von
    raw_from = quick_args[1] if quick_args and len(quick_args) > 1 else ""
    date_from_raw = _prompt("Von (YYYY-MM-DD / YYYY-MM / YYYY)", default=raw_from)
    date_from = _parse_date(date_from_raw, end=False)

    # Datum bis
    raw_to = quick_args[2] if quick_args and len(quick_args) > 2 else ""
    date_to_raw = _prompt("Bis  (YYYY-MM-DD / YYYY-MM / YYYY)", default=raw_to)
    date_to = _parse_date(date_to_raw, end=True)

    # Notiz
    notes_raw = _prompt("Notiz (optional, Enter überspringen)")
    notes = notes_raw or None

    entry = {
        "name":         name,
        "country":      country,
        "country_iso":  iso,
        "subregion":    subregion,
        "climate_zone": climate,
        "date_from":    date_from or "",
        "date_to":      date_to or "",
        "notes":        notes,
    }

    print(f"\n  → {name}, {subregion}, {country}  [{_fmt_date_range(entry)}]")
    confirm = input(t("  Speichern? [J/n]: ", "  Save? [Y/n]: ")).strip().lower()
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
    print(t(f"Gelöscht: {removed.get('name')} ({removed.get('country')})",
            f"Deleted: {removed.get('name')} ({removed.get('country')})"))
    return entries


def add_entry_noninteractive(entry: dict) -> None:
    """Add a travel history entry non-interactively, reusing existing validation."""
    entries = load()
    
    # Validate required fields
    if "name" not in entry or not entry["name"]:
        raise ValueError(t("Ort / Name ist ein Pflichtfeld", "Place / Name is required"))
    if "country" not in entry or not entry["country"]:
        raise ValueError(t("Land ist ein Pflichtfeld", "Country is required"))
    if "date_from" not in entry or not entry["date_from"]:
        raise ValueError(t("Von-Datum ist ein Pflichtfeld", "From date is required"))
    
    # Build validated entry
    validated_entry: dict = {
        "name": entry["name"],
        "country": entry["country"],
        "country_iso": COUNTRY_ISO.get(entry["country"], ""),
        "subregion": entry.get("subregion", ""),
        "climate_zone": entry.get("climate_zone", ""),
        "date_from": _parse_date(entry["date_from"], end=False) or "",
        "date_to": _parse_date(entry.get("date_to"), end=True) or "",
        "notes": entry.get("notes") or None,
    }
    
    entries.append(validated_entry)
    save(entries)


def cmd_edit(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}",
                f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    e = entries[idx - 1]
    print(t(f"\n── Eintrag #{idx} bearbeiten (Enter = unverändert) ──",
            f"\n── Edit entry #{idx} (Enter = keep unchanged) ──"))
    print(t(f"  Aktuell: {e.get('name')}, {e.get('subregion')}, {e.get('country')}  [{_fmt_date_range(e)}]",
            f"  Current: {e.get('name')}, {e.get('subregion')}, {e.get('country')}  [{_fmt_date_range(e)}]"))

    fields = [
        ("name",         "Ort / Name",    None),
        ("country",      "Land",          list(COUNTRY_ISO.keys())[:20]),
        ("subregion",    "Subregion",     KNOWN_SUBREGIONS.get(e.get("country", ""), None)),
        ("climate_zone", "Klimazone",     CLIMATE_ZONES),
        ("date_from",    "Von",           None),
        ("date_to",      "Bis",           None),
        ("notes",        "Notiz",         None),
    ]
    for key, label, choices in fields:
        new_val = _prompt(label, default=e.get(key, "") or "", choices=choices)
        if key in ("date_from", "date_to") and new_val:
            new_val = _parse_date(new_val, end=(key == "date_to"))
        if new_val is not None:
            e[key] = new_val or None if key == "notes" else new_val

    if e.get("country") in COUNTRY_ISO:
        e["country_iso"] = COUNTRY_ISO[e["country"]]

    entries[idx - 1] = e
    print(t("  ✓ Aktualisiert.", "  ✓ Updated."))
    return entries


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=t(
            "Reiseverlauf verwalten (~/.config/kyoro/travel_history.json)",
            "Manage travel history (~/.config/kyoro/travel_history.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele / Examples:
  python3 scripts/utils/manage/personal/manage_travel_history.py list
  python3 scripts/utils/manage/personal/manage_travel_history.py add
  python3 scripts/utils/manage/personal/manage_travel_history.py add "Region Name" YYYY-MM YYYY-MM-DD
  python3 scripts/utils/manage/personal/manage_travel_history.py delete 3
  python3 scripts/utils/manage/personal/manage_travel_history.py edit 2
""",
    )
    ap.add_argument("command", choices=["list", "add", "delete", "edit"],
                    help=t("Aktion", "Action"))
    ap.add_argument("args", nargs="*",
                    help=t("Zusatzargumente: add [name] [von] [bis] | delete/edit [nr]",
                           "Extra arguments: add [name] [from] [to] | delete/edit [nr]"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    entries = load()

    if args.command == "list":
        cmd_list(entries)

    elif args.command == "add":
        entries = cmd_add(entries, quick_args=args.args or None)
        save(entries)

    elif args.command == "delete":
        if not args.args or not args.args[0].isdigit():
            cmd_list(entries)
            try:
                nr = int(input("  Welche Nummer löschen? ").strip())
            except (ValueError, EOFError, KeyboardInterrupt):
                sys.exit(0)
        else:
            nr = int(args.args[0])
        entries = cmd_delete(entries, nr)
        save(entries)

    elif args.command == "edit":
        cmd_list(entries)
        if not args.args or not args.args[0].isdigit():
            try:
                nr = int(input("  Welche Nummer bearbeiten? ").strip())
            except (ValueError, EOFError, KeyboardInterrupt):
                sys.exit(0)
        else:
            nr = int(args.args[0])
        entries = cmd_edit(entries, nr)
        save(entries)


if __name__ == "__main__":
    main()
