#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_risk_markers.py — Eigene Risikomarker und genetische Befunde verwalten

@tier        infrastructure
@purpose.de  Dokumentiert eigene genetische Varianten, Laborbefunde mit genetischer
             Bedeutung, erbliche Risiken (aus Familienanamnese abgeleitet) und klinische
             Phänotypen mit genetischer Komponente. Zeigt ausstehende Tests und
             Handlungsbedarfe auf einen Blick.
@purpose.en  Documents own genetic variants, lab findings with genetic significance,
             hereditary risks (derived from family history) and clinical phenotypes with
             genetic component. Shows pending tests and actions at a glance.
@method.de   Speichert unter KYORO_CONFIG_DIR/own_risk_markers.json (lokal, nicht im Repo).
             Kategorien: Laborbefund, genetische Variante, klinischer Phänotyp,
             erbliches Risiko, immunologisch. Status: bestätigt/vermutet/ausstehend.
             --pending zeigt nur Einträge mit offenem Handlungsbedarf.
@method.en   Stores in KYORO_CONFIG_DIR/own_risk_markers.json (local only, not in repo).
             Categories: lab finding, genetic variant, clinical phenotype, hereditary risk,
             immunological. Status: confirmed/suspected/pending.
             --pending shows only entries with open action items.
@reads       KYORO_CONFIG_DIR/own_risk_markers.json
@writes      KYORO_CONFIG_DIR/own_risk_markers.json
@limits.de   Kein Ersatz für genetische Beratung. Keine automatische Risikoberechnung.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Not a substitute for genetic counseling. No automatic risk calculation.
@usage
    python3 scripts/utils/manage/personal/manage_risk_markers.py list
    python3 scripts/utils/manage/personal/manage_risk_markers.py list --pending
    python3 scripts/utils/manage/personal/manage_risk_markers.py add
    python3 scripts/utils/manage/personal/manage_risk_markers.py edit 3
    python3 scripts/utils/manage/personal/manage_risk_markers.py delete 3
    python3 scripts/utils/manage/personal/manage_risk_markers.py export
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import KYORO_CONFIG_DIR

MARKERS_FILE = KYORO_CONFIG_DIR / "own_risk_markers.json"

# ── Wissensbasen ──────────────────────────────────────────────────────────────

CATEGORIES = [
    "laborbefund",
    "genetische_variante",
    "klinischer_phänotyp",
    "erbliches_risiko",
    "immunologisch",
    "pharmakokinetik",
]

CATEGORY_LABELS = {
    "laborbefund":         t("Laborbefund (genetisch relevant)",   "Lab finding (genetically relevant)"),
    "genetische_variante": t("Genetische Variante / Gentest",      "Genetic variant / gene test"),
    "klinischer_phänotyp": t("Klinischer Phänotyp (genetisch)",    "Clinical phenotype (genetic)"),
    "erbliches_risiko":    t("Erbliches Risiko (Familienanamnese)","Hereditary risk (family history)"),
    "immunologisch":       t("Immunologischer Befund",             "Immunological finding"),
    "pharmakokinetik":     t("Pharmakokinetik / Medikamenten-Gen", "Pharmacokinetics / drug gene"),
}

STATUSES = ["bestätigt", "vermutet", "ausstehend", "ausgeschlossen"]

STATUS_ICONS = {
    "bestätigt":    "✅",
    "vermutet":     "❓",
    "ausstehend":   "⏳",
    "ausgeschlossen": "❌",
}

# Bekannte Marker-Vorschläge je Kategorie
MARKER_SUGGESTIONS: dict[str, list[str]] = {
    "laborbefund": [
        "Lipoprotein(a) [Lp(a)] ↑",
        "von-Willebrand-Faktor (vWF) ↑",
        "Faktor XII (FXII) ↑",
        "Faktor VII (FVII) ↑",
        "Fibrinogen ↑",
        "Thrombozyten ↑",
        "aPTT verkürzt",
        "Eosinophilie",
        "Basaltryptase ↑",
        "Homocystein ↑",
        "Ferritin ↓ (chronisch)",
        "Vitamin D ↓ (chronisch)",
        "HbA1c (Grenzbereich)",
        "TSH (Grenzbereich)",
    ],
    "genetische_variante": [
        "TPSAB1 — Hereditäre Alpha-Tryptasämie (HAT)",
        "BRCA1 / BRCA2 — Brust-/Ovarialkrebs-Risiko",
        "APOE ε4 — Alzheimer-Risiko",
        "F5 (Faktor-V-Leiden) — Thromboserisiko",
        "F2 (Prothrombin G20210A) — Thromboserisiko",
        "MTHFR C677T — Folsäure-Stoffwechsel",
        "HFE (C282Y/H63D) — Hämochromatose",
        "COL3A1 / COL5A1 — EDS",
        "FBN1 / FBN2 — Marfan-Syndrom",
        "SCN5A — Herzrhythmusstörungen",
        "KCNQ1 / KCNH2 — Long-QT-Syndrom",
        "Lynch-Syndrom (MLH1/MSH2/...)",
    ],
    "klinischer_phänotyp": [
        "Hypermobilität / hEDS / HSD",
        "Lipödem (kongenital)",
        "Sensorische Hypersensitivität (Licht, Lärm, taktil)",
        "MCAS-Phänotyp (Mastzellaktivierung)",
        "Autismus-Spektrum (ASS)",
        "ADHS",
        "Dysautonomie / POTS",
        "Rosacea (familiär gehäuft)",
        "Sicca-Syndrom (Sjögren-Phänotyp)",
        "Small Fiber Neuropathie (SFN)",
        "Frühe Osteoporose",
        "Aneurysma-Disposition",
    ],
    "erbliches_risiko": [
        "Vorhofflimmern (väterlich) → eigene AF-Prädisposition",
        "MCAS / HAT (mütterlicherseits, 3 Generationen)",
        "Rosacea (mütterlicherseits, 3 Generationen)",
        "Koronare Herzkrankheit (familiär früh)",
        "Schlaganfall (familiär)",
        "Typ-2-Diabetes (familiär)",
        "Brustkrebs / Darmkrebs (familiär)",
        "Schilddrüsenerkrankung (familiär)",
        "Demenz / Alzheimer (familiär früh)",
    ],
    "immunologisch": [
        "Thiomersal-/Quecksilberallergie (formal bestätigt)",
        "Phenylquecksilberacetat-Allergie",
        "Kolophonium-Allergie",
        "Penicillin-Allergie",
        "Nickel-Allergie",
        "Latex-Allergie",
        "NSAID-Überempfindlichkeit",
        "Kontrastallergie",
        "Hymenoptera-Giftallergie (Biene/Wespe)",
        "IgA-Mangel",
        "Erhöhtes Gesamt-IgE",
    ],
    "pharmakokinetik": [
        "CYP2D6 — Poor/Ultra-Metabolizer",
        "CYP2C19 — Poor/Ultra-Metabolizer",
        "CYP3A4/3A5 — Variante",
        "DPYD — 5-FU-Toxizitätsrisiko",
        "TPMT — Azathioprin-Toxizitätsrisiko",
        "UGT1A1 — Irinotecan-Toxizität",
        "G6PD-Mangel — Hämolyserisiko",
    ],
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load() -> list[dict]:
    if MARKERS_FILE.exists():
        return json.loads(MARKERS_FILE.read_text(encoding="utf-8"))
    return []


def save(entries: list[dict]) -> None:
    MARKERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MARKERS_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(t(f"Gespeichert: {MARKERS_FILE}", f"Saved: {MARKERS_FILE}"))


def _prompt(label: str, default: str = "", choices: list[str] | None = None,
            required: bool = False) -> str:
    if choices:
        print(t(f"\n  Optionen für {label}:", f"\n  Options for {label}:"))
        for i, c in enumerate(choices[:16], 1):
            print(f"    {i:2}. {c}")
        if len(choices) > 16:
            print(t(f"    … ({len(choices) - 16} weitere — freie Eingabe möglich)",
                    f"    … ({len(choices) - 16} more — free text also accepted)"))
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


def _cat_label(cat: str) -> str:
    return CATEGORY_LABELS.get(cat, cat)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(entries: list[dict], pending_only: bool = False) -> None:
    if not entries:
        print(t("Noch keine Einträge. Mit 'add' beginnen.",
                "No entries yet. Use 'add' to start."))
        return

    filtered = [e for e in entries
                if not pending_only or e.get("status") == "ausstehend"
                or bool(e.get("action_needed"))]

    if not filtered:
        print(t("Keine ausstehenden Einträge.", "No pending entries."))
        return

    current_cat = None
    for i, e in enumerate(entries, 1):
        if pending_only and e not in filtered:
            continue
        cat = e.get("category", "")
        if cat != current_cat:
            current_cat = cat
            print(f"\n  ── {_cat_label(cat)} {'─' * max(0, 50 - len(_cat_label(cat)))}")

        icon    = STATUS_ICONS.get(e.get("status", ""), "⚪")
        marker  = e.get("marker", "")
        gene    = e.get("gene", "")
        gene_str = f"  [{gene}]" if gene else ""
        val     = e.get("lab_value", "")
        val_str = f"  = {val}" if val else ""
        print(f"  {i:>3}  {icon}  {marker}{gene_str}{val_str}")

        if e.get("clinical_relevance"):
            print(f"          → {e['clinical_relevance']}")
        if e.get("action_needed"):
            print(f"          ⚡ {e['action_needed']}")
        if e.get("notes"):
            print(f"          ↳ {e['notes']}")
    print()


def cmd_add(entries: list[dict]) -> list[dict]:
    print(t("\n── Neuer Risikomarker / Genetik-Eintrag ──────────────",
            "\n── New risk marker / genetic entry ────────────────────"))
    print(t("  (Strg+C jederzeit zum Abbrechen ohne Datenverlust)",
            "  (Ctrl+C at any time to cancel without data loss)"))

    # Kategorie
    cat_choices = [f"{k}  — {_cat_label(k)}" for k in CATEGORIES]
    cat_raw = _prompt(t("Kategorie", "Category"), choices=cat_choices, required=True)
    category = cat_raw.split()[0] if cat_raw.split() else "laborbefund"
    if category not in CATEGORIES:
        category = "laborbefund"

    # Marker-Name
    suggestions = MARKER_SUGGESTIONS.get(category, [])
    marker = _prompt(t("Marker / Name", "Marker / name"),
                     choices=suggestions or None, required=True)

    # Gen (optional)
    gene = _prompt(t("Gen-Symbol (optional, z.B. TPSAB1, F12, LPA)",
                     "Gene symbol (optional, e.g. TPSAB1, F12, LPA)"))

    # Status
    status_choices = [
        f"bestätigt    {STATUS_ICONS['bestätigt']}  — {t('laborbestätigt / diagnostiziert', 'lab-confirmed / diagnosed')}",
        f"vermutet     {STATUS_ICONS['vermutet']}  — {t('klinisches Muster, nicht formal getestet', 'clinical pattern, not formally tested')}",
        f"ausstehend   {STATUS_ICONS['ausstehend']}  — {t('Test beauftragt oder dringend empfohlen', 'test ordered or urgently recommended')}",
        f"ausgeschlossen {STATUS_ICONS['ausgeschlossen']} — {t('explizit getestet und negativ', 'explicitly tested and negative')}",
    ]
    status_raw = _prompt(t("Status", "Status"), choices=status_choices,
                         default="vermutet", required=True)
    status = status_raw.split()[0] if status_raw.split() else "vermutet"
    if status not in STATUSES:
        status = "vermutet"

    # Laborwert (optional)
    lab_value = _prompt(t("Laborwert (optional, z.B. '87 nmol/L', '↑ 2,1 mg/L')",
                          "Lab value (optional, e.g. '87 nmol/L', '↑ 2.1 mg/L')"))
    lab_date  = _prompt(t("Datum des Laborbefunds (YYYY-MM-DD / YYYY-MM, optional)",
                          "Lab date (YYYY-MM-DD / YYYY-MM, optional)"))

    # Klinische Relevanz
    relevance = _prompt(t("Klinische Relevanz (Kurzfassung)",
                          "Clinical relevance (brief summary)"))

    # Handlungsbedarf
    action = _prompt(t("Handlungsbedarf / ausstehende Tests (optional)",
                       "Action needed / pending tests (optional)"))

    # Notiz
    notes = _prompt(t("Notiz — Details, Quellen, Einschränkungen (optional)",
                      "Notes — details, sources, caveats (optional)"))

    entry: dict = {
        "marker":   marker,
        "category": category,
        "status":   status,
    }
    if gene:
        entry["gene"] = gene
    if lab_value:
        entry["lab_value"] = lab_value
    if lab_date:
        entry["lab_date"] = lab_date
    if relevance:
        entry["clinical_relevance"] = relevance
    if action:
        entry["action_needed"] = action
    if notes:
        entry["notes"] = notes

    icon = STATUS_ICONS.get(status, "⚪")
    print(f"\n  → {icon} [{_cat_label(category)}]  {marker}")
    if relevance:
        print(f"    → {relevance}")
    if action:
        print(f"    ⚡ {action}")

    try:
        confirm = input(t("  Speichern? [J/n]: ", "  Save? [Y/n]: ")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(t("\n  Abgebrochen.", "\n  Cancelled."))
        sys.exit(0)

    if confirm in ("", "j", "y", "ja", "yes"):
        entries.append(entry)
        print(t(f"  ✓ Hinzugefügt (#{len(entries)})", f"  ✓ Added (#{len(entries)})"))
    else:
        print(t("  Abgebrochen.", "  Cancelled."))
    return entries


def cmd_delete(entries: list[dict], idx: int) -> list[dict]:
    if idx < 1 or idx > len(entries):
        print(t(f"Ungültige Nummer. Verfügbar: 1–{len(entries)}",
                f"Invalid number. Available: 1–{len(entries)}"))
        return entries
    removed = entries.pop(idx - 1)
    print(t(f"Gelöscht: {removed.get('marker','')}",
            f"Deleted: {removed.get('marker','')}"))
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
    print(f"  {icon}  {e.get('marker','')}  [{_cat_label(e.get('category',''))}]")

    cat_choices = [f"{k}  — {_cat_label(k)}" for k in CATEGORIES]
    cat_raw = _prompt(t("Kategorie", "Category"),
                      default=e.get("category", ""), choices=cat_choices)
    new_cat = cat_raw.split()[0] if cat_raw.split() else ""
    if new_cat in CATEGORIES:
        e["category"] = new_cat

    suggestions = MARKER_SUGGESTIONS.get(e.get("category", ""), [])
    new_marker = _prompt(t("Marker / Name", "Marker / name"),
                         default=e.get("marker", ""), choices=suggestions or None)
    if new_marker:
        e["marker"] = new_marker

    for key, label in [
        ("gene",               t("Gen-Symbol", "Gene symbol")),
        ("lab_value",          t("Laborwert", "Lab value")),
        ("lab_date",           t("Labordatum", "Lab date")),
        ("clinical_relevance", t("Klinische Relevanz", "Clinical relevance")),
        ("action_needed",      t("Handlungsbedarf", "Action needed")),
        ("notes",              t("Notiz", "Notes")),
    ]:
        val = _prompt(label, default=e.get(key, "") or "")
        e[key] = val or None

    status_choices = [f"{s}  {STATUS_ICONS[s]}" for s in STATUSES]
    status_raw = _prompt(t("Status", "Status"),
                         default=e.get("status", "vermutet"),
                         choices=status_choices)
    new_status = status_raw.split()[0] if status_raw.split() else ""
    if new_status in STATUSES:
        e["status"] = new_status

    entries[idx - 1] = e
    print(t("  ✓ Aktualisiert.", "  ✓ Updated."))
    return entries


def cmd_export(entries: list[dict]) -> None:
    """Markdown-Tabelle für genetische Beratung / Kardiologen / Rheumatologen."""
    if not entries:
        print(t("Keine Einträge.", "No entries."))
        return

    by_cat: dict[str, list[dict]] = {}
    for e in entries:
        cat = e.get("category", "sonstiges")
        by_cat.setdefault(cat, []).append(e)

    for cat, items in by_cat.items():
        print(f"\n### {_cat_label(cat)}\n")
        print(t("| Status | Marker | Gen | Wert | Relevanz | Handlungsbedarf |",
                "| Status | Marker | Gene | Value | Relevance | Action needed |"))
        print("|---|---|---|---|---|---|")
        for e in items:
            icon = STATUS_ICONS.get(e.get("status", ""), "⚪")
            cols = [
                f"{icon} {e.get('status','')}",
                e.get("marker", ""),
                e.get("gene", "") or "—",
                e.get("lab_value", "") or "—",
                e.get("clinical_relevance", "") or "",
                e.get("action_needed", "") or "",
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
            "Eigene Risikomarker und Genetik-Befunde verwalten (~/.config/kyoro/own_risk_markers.json)",
            "Manage own risk markers and genetic findings (~/.config/kyoro/own_risk_markers.json)",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("""
Befehle:
  list               Alle Einträge nach Kategorie
  list --pending     Nur Einträge mit offenem Handlungsbedarf / Status ausstehend
  add                Interaktiv neuen Eintrag anlegen
  edit <nr>          Eintrag bearbeiten
  delete <nr>        Eintrag löschen
  export             Markdown-Tabelle für Arztbriefe / genetische Beratung

Status:
  ✅ bestätigt    — laborbestätigt oder formal diagnostiziert
  ❓ vermutet     — klinisches Muster, kein Testnachweis
  ⏳ ausstehend   — Test beauftragt oder dringend empfohlen
  ❌ ausgeschlossen — explizit getestet, negativ
""", """
Commands:
  list               All entries by category
  list --pending     Only entries with open action items / status pending
  add                Interactively add a new entry
  edit <nr>          Edit an entry
  delete <nr>        Delete an entry
  export             Markdown table for doctor's letters / genetic counseling

Status:
  ✅ confirmed    — lab-confirmed or formally diagnosed
  ❓ suspected    — clinical pattern, no test confirmation
  ⏳ pending      — test ordered or urgently recommended
  ❌ excluded     — explicitly tested, negative
"""),
    )
    ap.add_argument("command", choices=["list", "add", "edit", "delete", "export"],
                    help=t("Aktion", "Action"))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--pending", action="store_true",
                    help=t("Nur ausstehende Einträge anzeigen",
                           "Show only pending entries"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    entries = load()

    if args.command == "list":
        cmd_list(entries, pending_only=args.pending)
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
