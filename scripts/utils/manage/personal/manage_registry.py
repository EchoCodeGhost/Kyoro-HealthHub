#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_registry.py — Geräte- und App-Registry verwalten


@tier        infrastructure
@purpose.de  Verwaltet die Registry von Geräten und Apps in einer lokalen JSON-Datei.
             Ermöglicht das Erfassen von Gerätetypen, Seriennummern, Kaufdaten und
             Deaktivierungsdaten für die Nachverfolgbarkeit.
             HINWEIS: device_id-Werte sind Pseudonyme (z.B. 'DEV-8abb425f'), keine
             semantischen Gerätenamen. Die Zuordnung zu echten Gerätenamen erfolgt
             über identity_resolver.
@purpose.en  Manages the registry of devices and apps in a local JSON file.
             Enables tracking of device types, serial numbers, purchase dates, and
             deactivation dates for traceability.
             NOTE: device_id values are pseudonyms (e.g. 'DEV-8abb425f'), not
             semantic device names. Mapping to real device names is handled by
             identity_resolver.
@method.de   Speichert unter ~/.config/kyoro/registry.json (lokal, nicht im Repo).
             Unterstützt separate Verwaltung für Geräte und Apps mit verschiedenen Attributen.
@method.en   Stores in ~/.config/kyoro/registry.json (local only, not in repo).
             Supports separate management for devices and apps with different attributes.
@reads       ~/.config/kyoro/registry.json
@writes      ~/.config/kyoro/registry.json
@limits.de   Lokale Datei. Keine automatische Validierung.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Local file only. No automatic validation.
@usage
    python3 scripts/utils/manage/personal/manage_registry.py device list
    python3 scripts/utils/manage/personal/manage_registry.py device add
    python3 scripts/utils/manage/personal/manage_registry.py device edit 3
    python3 scripts/utils/manage/personal/manage_registry.py device delete 3
    python3 scripts/utils/manage/personal/manage_registry.py device export
    python3 scripts/utils/manage/personal/manage_registry.py app list
    python3 scripts/utils/manage/personal/manage_registry.py app add
    python3 scripts/utils/manage/personal/manage_registry.py app edit 2
    python3 scripts/utils/manage/personal/manage_registry.py app delete 2
    python3 scripts/utils/manage/personal/manage_registry.py app export
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import KYORO_CONFIG_DIR

REGISTRY_FILE = KYORO_CONFIG_DIR / "registry.json"

# ── Wissensbasis ──────────────────────────────────────────────────────────────

SENSOR_TYPES = [
    "optical_wrist",
    "optical_wrist_gps",
    "ppg_sensor",
    "ecg_patch",
    "ecg_holter",
    "chest_strap",
    "blood_pressure",
    "cgm",
    "scale",
    "thermometer",
    "spirometer",
    "pulse_oximeter",
    "sleep_mat",
    "phone_optical",
    "camera",
    "multimodal",
    "other",
]

MDR_CLASSES = ["I", "IIa", "IIb", "III", "nicht zutreffend"]
GRADES      = ["consumer", "medical", "research"]
PLATFORMS   = ["iOS/Android", "iOS", "Android", "Web", "PC/Mac", "Embedded"]

APP_FUNCTIONS = [
    "AFib-Erkennung (PPG)",
    "EKG / ECG-Aufzeichnung",
    "Blutdruckmessung",
    "Schlafanalyse",
    "HRV-Analyse",
    "Pulsoximetrie",
    "Hautdiagnostik",
    "Symptomtagebuch",
    "Ernährungstracking",
    "Laborwert-Import",
    "Bewegungsanalyse",
    "Stressmonitoring",
    "Atemtraining",
    "Andere",
]

EXPORT_METHODS = [
    "CSV-Export",
    "JSON-Export",
    "PDF-Arztbericht",
    "Screenshot",
    "API",
    "Kein Export",
]


# ── I/O ───────────────────────────────────────────────────────────────────────

def load() -> dict:
    if REGISTRY_FILE.exists():
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    return {"device_registry": [], "app_registry": []}


def save(registry: dict) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(t(f"Gespeichert: {REGISTRY_FILE}", f"Saved: {REGISTRY_FILE}"))


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


def _parse_date(s: str) -> str:
    s = s.strip()
    if len(s) == 4:
        return f"{s}-01-01"
    return s


# ── Device commands ───────────────────────────────────────────────────────────

def device_list(entries: list[dict]) -> None:
    if not entries:
        print(t("Keine Geräte. Mit 'device add' anlegen.", "No devices. Use 'device add' to start."))
        return
    print(t(
        f"\n  {'#':>3}  {'device_id':<22}  {'Brand':<12}  {'Model':<20}  {'Sensor':<20}  {'Zeitraum'}",
        f"\n  {'#':>3}  {'device_id':<22}  {'Brand':<12}  {'Model':<20}  {'Sensor':<20}  {'Period'}",
    ))
    print("  " + "─" * 105)
    for i, d in enumerate(entries, 1):
        d1 = (d.get("date_from") or "")[:7]
        d2 = (d.get("date_to") or "")[:7]
        period = f"{d1} – {d2}" if d2 else (f"ab {d1}" if d1 else "—")
        reg = d.get("regulatory", {})
        grade = reg.get("grade", "")
        print(
            f"  {i:>3}  {d.get('device_id',''):<22}  {d.get('brand',''):<12}  "
            f"{d.get('model',''):<20}  {d.get('sensor_type',''):<20}  {period}"
        )
        extras = []
        if grade and grade != "consumer":
            extras.append(grade)
        if reg.get("mdr_class"):
            extras.append(f"MDR {reg['mdr_class']}")
        if d.get("serial"):
            extras.append(f"SN: {d['serial']}")
        if extras:
            print(f"       ↳ {' | '.join(extras)}")
    print()


def device_add(entries: list[dict]) -> list[dict]:
    print(t("\n── Neues Gerät ──────────────────────────────────────",
            "\n── New device ───────────────────────────────────────"))

    device_id = _prompt(t("device_id (z.B. 'polar_h10_2')", "device_id (e.g. 'polar_h10_2')"))
    if not device_id:
        print(t("Abgebrochen.", "Cancelled."))
        return entries

    brand       = _prompt(t("Hersteller (Brand)", "Brand"))
    model       = _prompt(t("Modell", "Model"))
    serial      = _prompt(t("Seriennummer (optional)", "Serial number (optional)"))
    sensor_type = _prompt(t("Sensor-Typ", "Sensor type"), choices=SENSOR_TYPES)
    person      = _prompt(t("Person (leer = self)", "Person (empty = self)")) or "self"

    date_from_raw = _prompt(t("Datum von (YYYY-MM-DD / YYYY)", "Date from (YYYY-MM-DD / YYYY)"))
    date_from     = _parse_date(date_from_raw) if date_from_raw else ""
    date_to_raw   = _prompt(t("Datum bis (leer = noch aktiv)", "Date to (empty = still active)"))
    date_to       = _parse_date(date_to_raw) if date_to_raw else ""

    grade     = _prompt(t("Produktklasse", "Grade"), choices=GRADES)
    ce_marked_raw = _prompt(t("CE-Kennzeichnung? [j/n]", "CE-marked? [y/n]"), default="j")
    ce_marked = ce_marked_raw.lower() in ("j", "y", "ja", "yes", "1", "true")
    mdr_class = _prompt(t("MDR-Klasse (leer = kein Medizinprodukt)", "MDR class (empty = not medical device)"),
                        choices=MDR_CLASSES)
    reg_notes = _prompt(t("Regulierungs-Hinweis (optional)", "Regulatory notes (optional)"))

    entry: dict = {
        "device_id":   device_id,
        "brand":       brand,
        "model":       model,
        "sensor_type": sensor_type,
        "person":      person,
        "date_from":   date_from,
        "date_to":     date_to,
        "regulatory": {
            "medical_device": bool(mdr_class and mdr_class not in ("nicht zutreffend", "")),
            "grade":          grade,
            "ce_marked":      ce_marked,
            "mdr_class":      mdr_class or None,
            "fda_510k":       None,
            "notes":          reg_notes or None,
        },
    }
    if serial:
        entry["serial"] = serial

    print(f"\n  → {device_id}  {brand} {model}  [{sensor_type}]  {date_from or '?'} – {date_to or 'heute'}")
    confirm = input(t("  Speichern? [J/n]: ", "  Save? [Y/n]: ")).strip().lower()
    if confirm in ("", "j", "y", "ja", "yes"):
        entries.append(entry)
        print(t(f"  Hinzugefügt (#{len(entries)})", f"  Added (#{len(entries)})"))
    else:
        print(t("  Abgebrochen.", "  Cancelled."))
    return entries


def device_edit(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid. Range: 1–{len(entries)}"))
        return entries
    d = entries[idx - 1]
    print(t(f"\n── Gerät #{idx} bearbeiten (Enter = unverändert) ──",
            f"\n── Edit device #{idx} (Enter = keep) ──"))

    fields: list[tuple[str, str, list[str] | None]] = [
        ("device_id",   t("device_id", "device_id"),                    None),
        ("brand",       t("Hersteller", "Brand"),                       None),
        ("model",       t("Modell", "Model"),                           None),
        ("serial",      t("Seriennummer", "Serial"),                    None),
        ("sensor_type", t("Sensor-Typ", "Sensor type"),                 SENSOR_TYPES),
        ("person",      t("Person", "Person"),                          None),
        ("date_from",   t("Datum von", "Date from"),                    None),
        ("date_to",     t("Datum bis (leer = aktiv)", "Date to"),       None),
    ]
    for key, label, choices in fields:
        new_val = _prompt(label, default=d.get(key) or "", choices=choices)
        if key in ("date_from", "date_to") and new_val:
            new_val = _parse_date(new_val)
        if key == "date_to" and new_val == "":
            d[key] = ""
        elif new_val:
            d[key] = new_val

    # Regulatory shortcut
    reg = d.setdefault("regulatory", {})
    new_grade = _prompt(t("Produktklasse", "Grade"), default=reg.get("grade", ""), choices=GRADES)
    if new_grade:
        reg["grade"] = new_grade
    new_mdr = _prompt(t("MDR-Klasse (leer = unverändert)", "MDR class (empty = unchanged)"),
                      default=reg.get("mdr_class") or "")
    if new_mdr:
        reg["mdr_class"] = new_mdr if new_mdr not in ("nicht zutreffend", "") else None
        reg["medical_device"] = bool(reg["mdr_class"])

    entries[idx - 1] = d
    print(t("  Aktualisiert.", "  Updated."))
    return entries


def device_delete(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid. Range: 1–{len(entries)}"))
        return entries
    removed = entries.pop(idx - 1)
    print(t(f"Gelöscht: {removed.get('device_id', '')}", f"Deleted: {removed.get('device_id', '')}"))
    return entries


def device_export(entries: list[dict]) -> None:
    if not entries:
        print(t("Keine Geräte.", "No devices."))
        return
    print(t(
        "| device_id | Brand | Modell | Sensor | Person | Von | Bis | Klasse | MDR | CE |",
        "| device_id | Brand | Model | Sensor | Person | From | To | Grade | MDR | CE |",
    ))
    print("|---|---|---|---|---|---|---|---|---|---|")
    for d in entries:
        reg = d.get("regulatory", {})
        cols = [
            d.get("device_id", ""),
            d.get("brand", ""),
            d.get("model", ""),
            d.get("sensor_type", ""),
            d.get("person", ""),
            (d.get("date_from") or "")[:7],
            (d.get("date_to") or "")[:7] or "—",
            reg.get("grade", ""),
            reg.get("mdr_class") or "—",
            "✓" if reg.get("ce_marked") else "—",
        ]
        print("| " + " | ".join(cols) + " |")


# ── App commands ──────────────────────────────────────────────────────────────

def app_list(entries: list[dict]) -> None:
    if not entries:
        print(t("Keine Apps. Mit 'app add' anlegen.", "No apps. Use 'app add' to start."))
        return
    print(t(
        f"\n  {'#':>3}  {'app_id':<18}  {'Name':<22}  {'Funktion':<35}  {'MDR'}",
        f"\n  {'#':>3}  {'app_id':<18}  {'Name':<22}  {'Function':<35}  {'MDR'}",
    ))
    print("  " + "─" * 100)
    for i, a in enumerate(entries, 1):
        reg = a.get("regulatory", {})
        mdr = reg.get("mdr_class") or "—"
        print(
            f"  {i:>3}  {a.get('app_id',''):<18}  {a.get('name',''):<22}  "
            f"{(a.get('function') or '')[:34]:<35}  {mdr}"
        )
        extras = []
        if a.get("vendor"):
            extras.append(a["vendor"])
        if a.get("platform"):
            extras.append(a["platform"])
        de = a.get("data_export", {})
        if de.get("method"):
            extras.append(f"Export: {de['method']}")
        if a.get("kyoro_importer"):
            extras.append(f"Importer: {a['kyoro_importer']}")
        if extras:
            print(f"       ↳ {' | '.join(extras)}")
    print()


def app_add(entries: list[dict]) -> list[dict]:
    print(t("\n── Neue App ─────────────────────────────────────────",
            "\n── New app ──────────────────────────────────────────"))

    app_id = _prompt(t("app_id (z.B. 'fibricheck')", "app_id (e.g. 'fibricheck')"))
    if not app_id:
        print(t("Abgebrochen.", "Cancelled."))
        return entries

    name     = _prompt(t("Anzeigename", "Display name"))
    vendor   = _prompt(t("Hersteller / Anbieter", "Vendor"))
    platform = _prompt(t("Plattform", "Platform"), choices=PLATFORMS)
    sensor   = _prompt(t("Eingabe-Sensor", "Input sensor"), choices=SENSOR_TYPES + ["—"])
    function = _prompt(t("Funktion", "Function"), choices=APP_FUNCTIONS)

    grade     = _prompt(t("Produktklasse", "Grade"), choices=GRADES)
    mdr_class = _prompt(t("MDR-Klasse (leer = kein Medizinprodukt)", "MDR class (empty = not med device)"),
                        choices=MDR_CLASSES)
    ce_raw    = _prompt(t("CE-Kennzeichnung? [j/n]", "CE-marked? [y/n]"), default="j")
    ce_marked = ce_raw.lower() in ("j", "y", "ja", "yes", "1", "true")
    reg_notes = _prompt(t("Regulierungs-Hinweis (optional)", "Regulatory notes (optional)"))

    export_method = _prompt(t("Daten-Export-Methode", "Data export method"), choices=EXPORT_METHODS)
    export_notes  = _prompt(t("Export-Hinweis (optional)", "Export notes (optional)"))
    importer      = _prompt(t("Kyoro-Importer-Pfad (optional)", "Kyoro importer path (optional)")) or None

    entry: dict = {
        "app_id":       app_id,
        "name":         name,
        "vendor":       vendor,
        "platform":     platform,
        "input_sensor": sensor if sensor != "—" else None,
        "function":     function,
        "regulatory": {
            "medical_device": bool(mdr_class and mdr_class not in ("nicht zutreffend", "")),
            "grade":          grade,
            "ce_marked":      ce_marked,
            "mdr_class":      mdr_class or None,
            "fda_510k":       None,
            "notes":          reg_notes or None,
        },
        "data_export": {
            "method": export_method,
            "notes":  export_notes or None,
        },
        "kyoro_importer": importer,
    }

    print(f"\n  → {app_id}  {name}  [{function}]")
    confirm = input(t("  Speichern? [J/n]: ", "  Save? [Y/n]: ")).strip().lower()
    if confirm in ("", "j", "y", "ja", "yes"):
        entries.append(entry)
        print(t(f"  Hinzugefügt (#{len(entries)})", f"  Added (#{len(entries)})"))
    else:
        print(t("  Abgebrochen.", "  Cancelled."))
    return entries


def app_edit(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid. Range: 1–{len(entries)}"))
        return entries
    a = entries[idx - 1]
    print(t(f"\n── App #{idx} bearbeiten (Enter = unverändert) ──",
            f"\n── Edit app #{idx} (Enter = keep) ──"))

    simple_fields: list[tuple[str, str, list[str] | None]] = [
        ("app_id",       t("app_id", "app_id"),                          None),
        ("name",         t("Name", "Name"),                              None),
        ("vendor",       t("Hersteller", "Vendor"),                      None),
        ("platform",     t("Plattform", "Platform"),                     PLATFORMS),
        ("input_sensor", t("Eingabe-Sensor", "Input sensor"),            SENSOR_TYPES),
        ("function",     t("Funktion", "Function"),                      APP_FUNCTIONS),
        ("kyoro_importer", t("Importer-Pfad", "Importer path"),          None),
    ]
    for key, label, choices in simple_fields:
        new_val = _prompt(label, default=a.get(key) or "", choices=choices)
        if new_val:
            a[key] = new_val if new_val != "—" else None

    reg = a.setdefault("regulatory", {})
    new_grade = _prompt(t("Produktklasse", "Grade"), default=reg.get("grade", ""), choices=GRADES)
    if new_grade:
        reg["grade"] = new_grade
    new_mdr = _prompt(t("MDR-Klasse", "MDR class"), default=reg.get("mdr_class") or "")
    if new_mdr:
        reg["mdr_class"] = new_mdr if new_mdr not in ("nicht zutreffend", "") else None
        reg["medical_device"] = bool(reg["mdr_class"])

    de = a.setdefault("data_export", {})
    new_method = _prompt(t("Export-Methode", "Export method"), default=de.get("method", ""), choices=EXPORT_METHODS)
    if new_method:
        de["method"] = new_method

    entries[idx - 1] = a
    print(t("  Aktualisiert.", "  Updated."))
    return entries


def app_delete(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}", f"Invalid. Range: 1–{len(entries)}"))
        return entries
    removed = entries.pop(idx - 1)
    print(t(f"Gelöscht: {removed.get('app_id', '')}", f"Deleted: {removed.get('app_id', '')}"))
    return entries


def app_export(entries: list[dict]) -> None:
    if not entries:
        print(t("Keine Apps.", "No apps."))
        return
    print(t(
        "| app_id | Name | Vendor | Plattform | Funktion | MDR | CE | Export | Importer |",
        "| app_id | Name | Vendor | Platform | Function | MDR | CE | Export | Importer |",
    ))
    print("|---|---|---|---|---|---|---|---|---|")
    for a in entries:
        reg = a.get("regulatory", {})
        de  = a.get("data_export", {})
        cols = [
            a.get("app_id", ""),
            a.get("name", ""),
            a.get("vendor", ""),
            a.get("platform", ""),
            (a.get("function") or "")[:40],
            reg.get("mdr_class") or "—",
            "✓" if reg.get("ce_marked") else "—",
            de.get("method", "—"),
            a.get("kyoro_importer") or "—",
        ]
        print("| " + " | ".join(cols) + " |")


# ── Main ──────────────────────────────────────────────────────────────────────

def _get_idx(args_list: list[str], entries: list[dict], list_fn, prompt_text: str) -> int:
    if args_list and args_list[0].isdigit():
        return int(args_list[0])
    list_fn(entries)
    try:
        return int(input(f"  {prompt_text} ").strip())
    except (ValueError, EOFError, KeyboardInterrupt):
        sys.exit(0)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=t(
            "Geräte- und App-Registry verwalten (~/.config/kyoro/registry.json)",
            "Manage device and app registry (~/.config/kyoro/registry.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  device list           Alle Geräte anzeigen
  device add            Interaktiv neues Gerät anlegen
  device edit <nr>      Gerät bearbeiten
  device delete <nr>    Gerät löschen
  device export         Markdown-Tabelle ausgeben

  app list              Alle Apps anzeigen
  app add               Interaktiv neue App anlegen
  app edit <nr>         App bearbeiten
  app delete <nr>       App löschen
  app export            Markdown-Tabelle ausgeben
""", """
Commands:
  device list/add/edit/delete/export
  app    list/add/edit/delete/export
"""),
    )
    ap.add_argument("kind",    choices=["device", "app"],
                    help=t("'device' oder 'app'", "'device' or 'app'"))
    ap.add_argument("command", choices=["list", "add", "edit", "delete", "export"],
                    help=t("Aktion", "Action"))
    ap.add_argument("args",    nargs="*",
                    help=t("Eintragsnummer", "Entry number"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    registry = load()

    if args.kind == "device":
        entries = registry.setdefault("device_registry", [])
        list_fn = device_list

        if args.command == "list":
            device_list(entries)
        elif args.command == "add":
            registry["device_registry"] = device_add(entries)
            save(registry)
        elif args.command == "edit":
            idx = _get_idx(args.args, entries, list_fn, t("Welche Nummer?", "Which number?"))
            registry["device_registry"] = device_edit(entries, idx)
            save(registry)
        elif args.command == "delete":
            idx = _get_idx(args.args, entries, list_fn, t("Welche Nummer löschen?", "Which number to delete?"))
            registry["device_registry"] = device_delete(entries, idx)
            save(registry)
        elif args.command == "export":
            device_export(entries)

    else:  # app
        entries = registry.setdefault("app_registry", [])
        list_fn = app_list

        if args.command == "list":
            app_list(entries)
        elif args.command == "add":
            registry["app_registry"] = app_add(entries)
            save(registry)
        elif args.command == "edit":
            idx = _get_idx(args.args, entries, list_fn, t("Welche Nummer?", "Which number?"))
            registry["app_registry"] = app_edit(entries, idx)
            save(registry)
        elif args.command == "delete":
            idx = _get_idx(args.args, entries, list_fn, t("Welche Nummer löschen?", "Which number to delete?"))
            registry["app_registry"] = app_delete(entries, idx)
            save(registry)
        elif args.command == "export":
            app_export(entries)


if __name__ == "__main__":
    main()
