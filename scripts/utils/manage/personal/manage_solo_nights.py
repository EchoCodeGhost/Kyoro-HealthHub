#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_solo_nights.py — Nächte ohne Partner (Bett geteilt ja/nein) verwalten

@tier        infrastructure
@purpose.de  Erfasst Nächte, in denen allein geschlafen wurde. Sleep-Cycle-Schnarchen
             und Somneo-Umgebungslärm sind nicht personenspezifisch (Mikrofon erfasst
             auch Partnerschnarchen/-geräusche) — dieses Verzeichnis erlaubt Analyse-
             Skripten, Nächte mit garantiert eindeutiger Zuordnung zu markieren.
@purpose.en  Tracks nights slept alone. Sleep Cycle snoring and Somneo ambient noise
             are not person-specific (microphone also picks up partner snoring/noise)
             — this registry lets analysis scripts flag nights with guaranteed
             unambiguous attribution.
@method.de   Speichert unter ~/.config/kyoro/solo_nights.json (lokal, nicht im Repo).
             Jeder Eintrag: date_from, date_to (gleich bei Einzelnacht), notes.
             is_solo_night(date) in modules/solo_nights.py prüft ein Datum gegen
             die Liste.
@method.en   Stores in ~/.config/kyoro/solo_nights.json (local only, not in repo).
             Each entry: date_from, date_to (same value for a single night), notes.
             is_solo_night(date) in modules/solo_nights.py checks a date against
             the list.
@reads       ~/.config/kyoro/solo_nights.json
@writes      ~/.config/kyoro/solo_nights.json
@limits.de   Rein manuelle Erfassung, keine automatische Ableitung aus Sensordaten.

@relevance.de  Ermöglicht personenspezifische Zuordnung von Mikrofon-/Umgebungsdaten, wichtig für Schnarch-/Lärmanalysen
@relevance.en  Enables person-specific attribution of microphone/ambient data, important for snoring/noise analyses
@limits.en   Purely manual entry, no automatic derivation from sensor data.
@usage
    python3 scripts/utils/manage/personal/manage_solo_nights.py list
    python3 scripts/utils/manage/personal/manage_solo_nights.py add
    python3 scripts/utils/manage/personal/manage_solo_nights.py add YYYY-MM-DD [YYYY-MM-DD]
    python3 scripts/utils/manage/personal/manage_solo_nights.py delete 3
    python3 scripts/utils/manage/personal/manage_solo_nights.py edit 2
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.config_backup import backup_before_write, commit_config_change
from health_config import KYORO_CONFIG_DIR

SOLO_NIGHTS_FILE = KYORO_CONFIG_DIR / "solo_nights.json"


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    if SOLO_NIGHTS_FILE.exists():
        return json.loads(SOLO_NIGHTS_FILE.read_text(encoding="utf-8"))
    return []


def save(entries: list[dict]) -> None:
    SOLO_NIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup_before_write(SOLO_NIGHTS_FILE)
    entries = sorted(entries, key=lambda e: e.get("date_from", ""))
    SOLO_NIGHTS_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    commit_config_change(SOLO_NIGHTS_FILE, f"solo_nights: {len(entries)} Einträge gespeichert")
    print(t(f"Gespeichert: {SOLO_NIGHTS_FILE}", f"Saved: {SOLO_NIGHTS_FILE}"))


def _prompt(label: str, default: str = "") -> str:
    dflt_str = f" [{default}]" if default else ""
    try:
        val = input(f"  {label}{dflt_str}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val or default


def _fmt_range(entry: dict) -> str:
    d1, d2 = entry.get("date_from", "?"), entry.get("date_to", "?")
    return d1 if d1 == d2 else f"{d1} – {d2}"


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(entries: list[dict]) -> None:
    if not entries:
        print(t("Noch keine Einträge. Mit 'add' beginnen.", "No entries yet. Use 'add' to start."))
        return
    print(t(f"\n  {'#':>3}  {'Zeitraum':<24} Notiz", f"\n  {'#':>3}  {'Period':<24} Note"))
    print("  " + "─" * 60)
    for i, e in enumerate(entries, 1):
        print(f"  {i:>3}  {_fmt_range(e):<24} {e.get('notes') or ''}")
    print()


def cmd_add(entries: list[dict], quick_args: list[str] | None = None) -> list[dict]:
    print(t("\n── Neue Nacht(-Serie) ohne Partner ─────────────────",
            "\n── New night(s) slept alone ────────────────────────"))

    date_from = quick_args[0] if quick_args else _prompt("Von (YYYY-MM-DD)")
    if not date_from:
        print(t("Abgebrochen.", "Cancelled."))
        return entries

    date_to = quick_args[1] if quick_args and len(quick_args) > 1 else _prompt("Bis (YYYY-MM-DD, leer = nur diese Nacht)", default=date_from)
    if not date_to:
        date_to = date_from

    notes = quick_args[2] if quick_args and len(quick_args) > 2 else _prompt("Notiz (optional)")

    entry = {"date_from": date_from, "date_to": date_to, "notes": notes or None}
    print(f"\n  → {_fmt_range(entry)}" + (f"  ({notes})" if notes else ""))
    confirm = input(t("  Speichern? [J/n]: ", "  Save? [Y/n]: ")).strip().lower()
    if confirm in ("", "j", "y", "ja", "yes"):
        entries.append(entry)
        print(t(f"  ✓ Hinzugefügt (Eintrag #{len(entries)})", f"  ✓ Added (entry #{len(entries)})"))
    else:
        print(t("  Abgebrochen.", "  Cancelled."))
    return entries


def cmd_delete(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}",
                f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    removed = entries.pop(idx - 1)
    print(t(f"Gelöscht: {_fmt_range(removed)}", f"Deleted: {_fmt_range(removed)}"))
    return entries


def cmd_edit(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}",
                f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    e = entries[idx - 1]
    print(t(f"\n── Eintrag #{idx} bearbeiten (Enter = unverändert) ──",
            f"\n── Edit entry #{idx} (Enter = keep unchanged) ──"))
    print(t(f"  Aktuell: {_fmt_range(e)}", f"  Current: {_fmt_range(e)}"))
    for key, label in (("date_from", "Von"), ("date_to", "Bis"), ("notes", "Notiz")):
        new_val = _prompt(label, default=e.get(key, "") or "")
        e[key] = new_val or (None if key == "notes" else e.get(key))
    entries[idx - 1] = e
    print(t("  ✓ Aktualisiert.", "  ✓ Updated."))
    return entries


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=t(
            "Nächte ohne Partner verwalten (~/.config/kyoro/solo_nights.json)",
            "Manage nights slept alone (~/.config/kyoro/solo_nights.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele / Examples:
  python3 scripts/utils/manage/personal/manage_solo_nights.py list
  python3 scripts/utils/manage/personal/manage_solo_nights.py add
  python3 scripts/utils/manage/personal/manage_solo_nights.py add 2026-06-15 2026-06-16
  python3 scripts/utils/manage/personal/manage_solo_nights.py delete 3
  python3 scripts/utils/manage/personal/manage_solo_nights.py edit 2
""",
    )
    ap.add_argument("command", choices=["list", "add", "delete", "edit"], help=t("Aktion", "Action"))
    ap.add_argument("args", nargs="*",
                    help=t("Zusatzargumente: add [von] [bis] [notiz] | delete/edit [nr]",
                           "Extra arguments: add [from] [to] [note] | delete/edit [nr]"))
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
