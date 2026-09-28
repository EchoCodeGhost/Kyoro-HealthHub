#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
log_exposure.py — Manuelles Expositions-Log für Allergene und Reizstoffe

@tier        infrastructure
@purpose.de  Erfasst Expositionen gegenüber nicht-nahrungsmittelbasierten Allergenen und
             Reizstoffen für die spätere Analyse. Ermöglicht das Nachschlagen von Inhaltsstoffen
             über Open Beauty Facts und das Verknüpfen mit Symptomen.
@purpose.en  Logs exposure to non-food allergens and irritants for later analysis.
             Enables ingredient lookup via Open Beauty Facts and correlation with symptoms.
@method.de   Unterstützt verschiedene Kategorien: Medikamente, Kosmetik, Zahnpflege,
             Haushaltsmittel, Sonnenschutz, Nahrungsergänzung, Umweltallergene.
             Daten werden in der exposures Tabelle gespeichert. Substanz-Hinweise können
             pro Kategorie abgefragt werden. Analyse via analyse_product_exposures.py.
@method.en   Supports categories: medication, cosmetics, dental care, household products,
             sunscreen, supplements, environmental allergens. Data stored in exposures table.
             Substance hints can be queried by category. Analysis via analyse_product_exposures.py.
@reads       exposures Tabelle
@writes      exposures Tabelle
@limits.de   Keine Validierung der Kategorie-Codes. Expositionen ohne Datum werden uebersprungen.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No validation of category codes. Exposures without a date are skipped.
@usage
    python log_exposure.py lookup "Elmex Gelee"
    python log_exposure.py lookup "Dior Sauvage"
    python log_exposure.py add --category dental --product "Colgate Total" --lookup
    python log_exposure.py add --category medication --product "Ibuprofen 400" --substance "Ibuprofen"
    python log_exposure.py list
    python log_exposure.py list --days 14
    python log_exposure.py hints
    python log_exposure.py delete 42
"""

import argparse
import json
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
DB_PATH = _cfg.db_path

# ── Kategorien ────────────────────────────────────────────────────────────────

CATEGORIES = [
    "medication", "cosmetic", "dental", "household",
    "sunscreen", "supplement", "environment",
]

CAT_LABELS_DE = {
    "medication":  "Medikament",
    "cosmetic":    "Kosmetik",
    "dental":      "Zahnpflege",
    "household":   "Haushaltsmittel",
    "sunscreen":   "Sonnenschutz",
    "supplement":  "Nahrungsergänzung",
    "environment": "Umwelt/Kontakt",
}

# ── Bekannte Substanzen (Hinweise für --hints) ────────────────────────────────

SUBSTANCE_HINTS: dict[str, str] = {
    "dental": (
        "SLS (Natriumlaurylsulfat) · Menthol · Fluorid · Triclosan · Saccharin · "
        "Carrageen · Cetylpyridinium · Chlorhexidin · Natriumbenzoat"
    ),
    "cosmetic": (
        "EU-26 Duftstoffallergene: Linalool · Limonene · Geraniol · Eugenol · "
        "Citral · Cinnamal · Farnesol · Coumarin · Benzyl alcohol · "
        "Benzyl salicylate · Linalyl acetate\n"
        "  Konservierungsstoffe: Methylparaben · Propylparaben · "
        "Phenoxyethanol · Benzalkoniumchlorid\n"
        "  Tenside: SLS · SLES · Cocamidopropyl Betaine"
    ),
    "sunscreen": (
        "Chemische UV-Filter: Oxybenzon (BP-3) · Avobenzon · Octinoxat · "
        "Octocrylen · Homosalat · Bemotrizinol\n"
        "  Mineralische UV-Filter: Titandioxid (TiO₂) · Zinkoxid (ZnO)\n"
        "  Hilfsstoffe: Phenoxyethanol · Parabene · Duftstoffe"
    ),
    "household": (
        "Tenside: SLS · SLES · Natriumhypochlorit (Bleiche) · Ammoniak · Quartäre Ammoniumverb.\n"
        "  Enzyme: Protease · Amylase · Lipase (in Waschmitteln)\n"
        "  Duftstoffe: Linalool · Limonene · Citral\n"
        "  Konservierungsstoffe: Benzisothiazolinon (BIT) · MIT (Methylisothiazolinon)"
    ),
    "medication": (
        "NSAIDs: Ibuprofen · ASS (Aspirin) · Diclofenac · Naproxen\n"
        "  Antibiotika: Penicillin · Amoxicillin · Erythromycin · Doxycyclin\n"
        "  Antihistaminika: Cetirizin · Loratadin · Fexofenadin\n"
        "  Andere: Codein · Sulfamethoxazol · Metronidazol · Ramipril (ACE-Hemmer)\n"
        "  Hilfsstoffe: Laktose · Gelatine · Titandioxid · Parabene"
    ),
    "supplement": (
        "Träger/Hilfsstoffe: Gelatine · Titandioid (E171) · Carrageen (E407) · "
        "Magnesiumstearat\n"
        "  Allergene Inhaltsstoffe: Soja · Milchprotein · Gluten (in manchen Pulvern)\n"
        "  Süßungsmittel: Aspartam · Sucralose · Acesulfam-K"
    ),
    "environment": (
        "Kontaktallergene: Latex (Naturkautschuk) · Nickel · Kobalt · Chrom(VI) · "
        "Kolophonium\n"
        "  Chemische Reizstoffe: Formaldehyd · Glutaraldehyd · Isocyanate\n"
        "  Bioallergene: Schimmelsporen · Hausstaub (Dermatophagoides) · "
        "Tierepithelien (Katze, Hund, Pferd)\n"
        "  Physikalisch: UV-Licht (Sonnenallergie) · Kältekontakt · Druck"
    ),
}


# ── Ingredient Lookup (delegates to utils/lookup_ingredients.py) ──────────────

def _do_lookup(product_name: str, barcode: str | None = None,
               use_vision: bool = True) -> dict | None:
    try:
        sys.path.insert(0, str(Path(__file__).parent / "utils"))
        from lookup_ingredients import lookup
        result = lookup(query=product_name, barcode=barcode, use_vision=use_vision)
        return result
    except Exception as e:
        print(t(f"  [lookup] Fehler: {e}", f"  [lookup] Error: {e}"), file=sys.stderr)
        return None


# ── Open Beauty Facts Lookup (legacy, kept for reference) ────────────────────

_OBF_SEARCH = (
    "https://world.openbeautyfacts.org/cgi/search.pl"
    "?search_terms={query}&search_simple=1&action=process&json=1"
    "&fields=product_name,code,brands,ingredients_text,ingredients&page_size=8"
)
_OBF_PRODUCT = "https://world.openbeautyfacts.org/api/v2/product/{code}.json"


def _obf_fetch(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KyoroHealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(t(f"  [lookup] Netzwerkfehler: {e}", f"  [lookup] Network error: {e}"), file=sys.stderr)
        return None


def _parse_ingredients(product: dict) -> list[str]:
    """Extract a flat list of ingredient names from an Open Beauty Facts product dict."""
    # Prefer structured ingredients array
    structured = product.get("ingredients", [])
    if structured:
        names = []
        for ing in structured:
            name = ing.get("text") or ing.get("id") or ""
            name = name.strip()
            if name and not name.startswith("en:"):
                names.append(name)
            elif name.startswith("en:"):
                names.append(name[3:])
        if names:
            return names

    # Fallback: parse ingredients_text (comma/semicolon separated INCI string)
    raw = product.get("ingredients_text", "") or ""
    if raw:
        parts = [p.strip().rstrip(".").strip() for p in raw.replace(";", ",").split(",")]
        return [p for p in parts if p and len(p) > 1]

    return []


def lookup_product_obf(query: str) -> list[dict]:
    """
    Search Open Beauty Facts for a product by name.
    Returns list of matches: {name, code, brands, ingredients, ingredients_raw, found_ingr}
    """
    url = _OBF_SEARCH.format(query=urllib.parse.quote(query))
    data = _obf_fetch(url)
    if not data:
        return []

    results = []
    for p in data.get("products", []):
        ingr = _parse_ingredients(p)
        results.append({
            "name":           p.get("product_name", "?"),
            "code":           p.get("code", ""),
            "brands":         p.get("brands", ""),
            "ingredients":    ingr,
            "ingredients_raw": p.get("ingredients_text", ""),
            "found_ingr":     bool(ingr),
        })
    return results


def lookup_by_barcode(barcode: str) -> dict | None:
    """Fetch a single product by barcode from Open Beauty Facts."""
    url = _OBF_PRODUCT.format(code=barcode)
    data = _obf_fetch(url)
    if not data or data.get("status") != 1:
        return None
    p = data.get("product", {})
    ingr = _parse_ingredients(p)
    return {
        "name":           p.get("product_name", "?"),
        "code":           barcode,
        "brands":         p.get("brands", ""),
        "ingredients":    ingr,
        "ingredients_raw": p.get("ingredients_text", ""),
        "found_ingr":     bool(ingr),
    }


def print_lookup_result(result: dict, verbose: bool = True):
    ingr = result["ingredients"]
    brand = f" ({result['brands']})" if result.get("brands") else ""
    code_str = f"  Barcode: {result['code']}" if result.get("code") else ""
    print(t(f"\n  Produkt: {result['name']}{brand}", f"\n  Product: {result['name']}{brand}"))
    if code_str:
        print(t(f"  Barcode: {result['code']}", f"  Barcode: {result['code']}"))
    if ingr:
        print(t(f"  INCI-Inhaltsstoffe ({len(ingr)}):", f"  INCI ingredients ({len(ingr)}):"))
        # Split into known allergen groups for quick overview
        ingr_lower = [i.lower() for i in ingr]
        known_flags = {
            "SLS":       any("sodium lauryl sulfate" in x or "natriumlaurylsulfat" in x for x in ingr_lower),
            "Fluorid":   any("fluoride" in x or "fluorid" in x or "olaflur" in x or "dectaflur" in x for x in ingr_lower),
            "Parabene":  any("paraben" in x for x in ingr_lower),
            "Menthol":   any("menthol" in x for x in ingr_lower),
            "Saccharin": any("saccharin" in x for x in ingr_lower),
            "Linalool":  any("linalool" in x for x in ingr_lower),
            "Limonene":  any("limonene" in x or "limonène" in x for x in ingr_lower),
        }
        flags_found = [k for k, v in known_flags.items() if v]

        if verbose:
            for i, ing in enumerate(ingr, 1):
                print(f"    {i:2}. {ing}")
        else:
            print(f"    {', '.join(ingr[:8])}"
                  + (t(f" … +{len(ingr)-8} weitere", f" … +{len(ingr)-8} more") if len(ingr) > 8 else ""))

        if flags_found:
            print(t(f"\n  ⚠ Bekannte Allergene/Reizstoffe: {', '.join(flags_found)}",
                    f"\n  ⚠ Known allergens/irritants: {', '.join(flags_found)}"))
    else:
        print(t(
            "  Inhaltsstoffe nicht in Open Beauty Facts vorhanden.\n"
            "  Tipp: Foto der Inhaltsstoffliste hochladen → openbeautyfacts.org",
            "  Ingredients not found in Open Beauty Facts.\n"
            "  Tip: Upload an ingredient photo → openbeautyfacts.org",
        ))


# ── DB ────────────────────────────────────────────────────────────────────────

def setup_table(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS product_exposures (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts          TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
        date        TEXT NOT NULL,
        category    TEXT NOT NULL,
        product     TEXT NOT NULL,
        substance   TEXT,
        amount      TEXT,
        person      TEXT NOT NULL DEFAULT 'unknown',
        notes       TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_exp_date    ON product_exposures(date);
    CREATE INDEX IF NOT EXISTS idx_exp_cat     ON product_exposures(category);
    CREATE INDEX IF NOT EXISTS idx_exp_person  ON product_exposures(person);
    CREATE INDEX IF NOT EXISTS idx_exp_subst   ON product_exposures(substance);
    """)
    conn.commit()


def add_entry(
    conn: sqlite3.Connection,
    date_str: str,
    category: str,
    product: str,
    substance: str | None,
    amount: str | None,
    person: str,
    notes: str | None,
) -> int:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO product_exposures "
        "(ts, date, category, product, substance, amount, person, notes) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (ts, date_str, category, product, substance, amount, person, notes),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_entries(conn: sqlite3.Connection, person: str, days: int):
    from_date = (date.today() - timedelta(days=days)).isoformat()
    return conn.execute("""
        SELECT id, date, category, product, substance, amount, notes
        FROM product_exposures
        WHERE person=? AND date >= ?
        ORDER BY date DESC, id DESC
    """, (person, from_date)).fetchall()


def delete_entry(conn: sqlite3.Connection, entry_id: int):
    n = conn.execute("DELETE FROM product_exposures WHERE id=?", (entry_id,)).rowcount
    conn.commit()
    return n


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Expositions-Log: Medikamente, Kosmetik, Haushalt, Umwelt",
            "Exposure log: medications, cosmetics, household products, environment",
        )
    )
    sub = parser.add_subparsers(dest="cmd")

    # ── add ──────────────────────────────────────────────────────────────────
    p_add = sub.add_parser("add", aliases=["a"],
                            help=t("Exposition eintragen", "Log an exposure"))
    p_add.add_argument("--category", "-c", required=True, choices=CATEGORIES,
                       metavar="CAT",
                       help=t(f"Kategorie: {', '.join(CATEGORIES)}", f"Category: {', '.join(CATEGORIES)}"))
    p_add.add_argument("--product", "-p", required=True,
                       help=t("Produktname (z.B. 'Colgate Total')", "Product name"))
    p_add.add_argument("--substance", "-s", default=None,
                       help=t("Substanz(en), kommagetrennt (z.B. 'SLS,Menthol')",
                               "Substance(s), comma-separated"))
    p_add.add_argument("--amount", "-a", default=None,
                       help=t("Menge/Dosis (z.B. '1 Tablette', 'wenig', 'viel')", "Amount/dose"))
    p_add.add_argument("--date", "-d", default=date.today().isoformat(),
                       help=t("Datum YYYY-MM-DD (default: heute)", "Date YYYY-MM-DD (default: today)"))
    p_add.add_argument("--person", default=OWN_PERSON_ID)
    p_add.add_argument("--notes", "-n", default=None,
                       help=t("Notiz (z.B. Reaktion beschreiben)", "Note (e.g. describe reaction)"))
    p_add.add_argument("--lookup", action="store_true",
                       help=t("Inhaltsstoffe automatisch via Open Beauty Facts + Vision nachschlagen",
                               "Auto-lookup ingredients via Open Beauty Facts + Vision"))
    p_add.add_argument("--no-vision", action="store_true",
                       help=t("Kein KI-Bildlesen (nur OBF-Textdaten)", "No AI vision (OBF text only)"))

    # ── list ─────────────────────────────────────────────────────────────────
    p_list = sub.add_parser("list", aliases=["ls"],
                             help=t("Einträge anzeigen", "List entries"))
    p_list.add_argument("--days", type=int, default=30,
                         help=t("Letzten N Tage (default: 30)", "Last N days (default: 30)"))
    p_list.add_argument("--person", default=OWN_PERSON_ID)
    p_list.add_argument("--category", "-c", choices=CATEGORIES, default=None,
                         help=t("Nur diese Kategorie", "Filter by category"))

    # ── delete ───────────────────────────────────────────────────────────────
    p_del = sub.add_parser("delete", aliases=["del", "rm"],
                            help=t("Eintrag löschen", "Delete entry"))
    p_del.add_argument("id", type=int, help="Entry ID (from list)")

    # ── lookup ───────────────────────────────────────────────────────────────
    p_lookup = sub.add_parser("lookup",
                               help=t("Inhaltsstoffe via Open Beauty Facts nachschlagen",
                                      "Look up ingredients via Open Beauty Facts"))
    p_lookup.add_argument("product", nargs="+",
                           help=t("Produktname (z.B. 'Elmex Gelee')", "Product name"))
    p_lookup.add_argument("--barcode", "-b", default=None,
                           help=t("Barcode (EAN) für direkten Abruf", "Barcode (EAN) for direct lookup"))
    p_lookup.add_argument("--short", action="store_true",
                           help=t("Nur erste 8 Inhaltsstoffe anzeigen", "Show only first 8 ingredients"))

    # ── hints ────────────────────────────────────────────────────────────────
    p_hints = sub.add_parser("hints",
                              help=t("Bekannte Substanzen/Allergene anzeigen",
                                     "Show known substances/allergens"))
    p_hints.add_argument("--category", "-c", choices=CATEGORIES, default=None,
                          help=t("Nur diese Kategorie", "Filter by category"))

    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.cmd is None:
        parser.print_help()
        return

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    setup_table(conn)

    cmd = args.cmd

    # ── lookup subcommand ─────────────────────────────────────────────────────
    if cmd == "lookup":
        sys.path.insert(0, str(Path(__file__).parent / "utils"))
        from lookup_ingredients import lookup as _lookup_fn, format_result
        query  = " ".join(args.product)
        bc     = getattr(args, "barcode", None)
        result = _lookup_fn(query=query, barcode=bc, use_vision=True)
        print()
        print(format_result(result))
        conn.close()
        return

    # ── add ──────────────────────────────────────────────────────────────────
    if cmd in ("add", "a"):
        subst = args.substance

        # Auto-lookup ingredients if --lookup given and no manual --substance
        if getattr(args, "lookup", False) and not subst:
            use_vis = not getattr(args, "no_vision", False)
            sys.path.insert(0, str(Path(__file__).parent / "utils"))
            from lookup_ingredients import lookup as _lookup_fn
            result = _lookup_fn(query=args.product, use_vision=use_vis)
            if result and result.get("ingredients"):
                ingr_list = result["ingredients"]
                subst = ", ".join(ingr_list[:20])
                print(t(
                    f"  Inhaltsstoffe gefunden ({result['source']}): "
                    f"{len(ingr_list)} Substanzen\n  → {subst[:120]}"
                    + ("…" if len(subst) > 120 else ""),
                    f"  Ingredients found ({result['source']}): "
                    f"{len(ingr_list)} substances\n  → {subst[:120]}"
                    + ("…" if len(subst) > 120 else ""),
                ))
            else:
                print(t(
                    "  ⚠ Keine Inhaltsstoffe gefunden — bitte --substance manuell angeben.",
                    "  ⚠ No ingredients found — please specify --substance manually.",
                ))

        row_id = add_entry(
            conn,
            date_str=args.date,
            category=args.category,
            product=args.product,
            substance=subst,
            amount=args.amount,
            person=args.person,
            notes=args.notes,
        )
        label = CAT_LABELS_DE.get(args.category, args.category)
        print(t(
            f"  ✓ Eintrag #{row_id} gespeichert ({args.date}):\n"
            f"    [{label}] {args.product}"
            + (f"\n    Substanzen: {subst}" if subst else "")
            + (f"\n    Menge: {args.amount}" if args.amount else ""),
            f"  ✓ Entry #{row_id} saved ({args.date}):\n"
            f"    [{label}] {args.product}"
            + (f"\n    Substances: {subst}"  if subst else "")
            + (f"\n    Amount: {args.amount}" if args.amount else ""),
        ))
        if args.category in SUBSTANCE_HINTS and not subst:
            hint_first_line = SUBSTANCE_HINTS[args.category].split("\n")[0]
            print(t(
                f"\n  Bekannte Substanzen ({label}): {hint_first_line}",
                f"\n  Known substances ({label}): {hint_first_line}",
            ))

    # ── list ─────────────────────────────────────────────────────────────────
    elif cmd in ("list", "ls"):
        rows = list_entries(conn, args.person, args.days)
        if hasattr(args, "category") and args.category:
            rows = [r for r in rows if r[2] == args.category]

        if not rows:
            print(t(f"  Keine Einträge in den letzten {args.days} Tagen.",
                    f"  No entries in the last {args.days} days."))
        else:
            print(t(
                f"  Expositions-Einträge — letzte {args.days} Tage ({args.person}): {len(rows)} Einträge",
                f"  Exposure entries — last {args.days} days ({args.person}): {len(rows)} entries",
            ))
            print(t(
                f"\n  {'ID':>4} {'Datum':<12} {'Kategorie':<18} {'Produkt':<28} Substanz",
                f"\n  {'ID':>4} {'Date':<12} {'Category':<18} {'Product':<28} Substance",
            ))
            print(f"  {'-'*4} {'-'*12} {'-'*18} {'-'*28} {'-'*30}")
            for rid, d, cat, prod, subst, amount, notes in rows:
                cat_label  = CAT_LABELS_DE.get(cat, cat)[:17]
                prod_short = prod[:27]
                subst_str  = (subst or "")[:29]
                amount_str = (t(f"  [Menge: {amount}]", f"  [Amount: {amount}]") if amount else "")
                note_str   = f"  ← {notes}" if notes else ""
                print(f"  {rid:>4} {d:<12} {cat_label:<18} {prod_short:<28} {subst_str}"
                      f"{amount_str}{note_str}")

    # ── delete ───────────────────────────────────────────────────────────────
    elif cmd in ("delete", "del", "rm"):
        n = delete_entry(conn, args.id)
        if n:
            print(t(f"  Eintrag #{args.id} gelöscht.", f"  Entry #{args.id} deleted."))
        else:
            print(t(f"  Eintrag #{args.id} nicht gefunden.", f"  Entry #{args.id} not found."))

    # ── hints ────────────────────────────────────────────────────────────────
    elif cmd == "hints":
        cats = [args.category] if args.category else CATEGORIES
        print(t("  Bekannte Substanzen nach Kategorie:",
                "  Known substances by category:"))
        for c in cats:
            label = CAT_LABELS_DE.get(c, c)
            hint  = SUBSTANCE_HINTS.get(c, "–")
            lines = hint.split("\n")
            print(t(f"\n  ── {label} ──", f"\n  ── {label} ──"))
            for line in lines:
                print(f"  {line.strip()}")

    conn.close()


if __name__ == "__main__":
    main()
