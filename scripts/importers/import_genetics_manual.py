#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_genetics_manual.py — Manuelle genetische Marker aus Lab-Befunden importieren

@tier        infrastructure
@purpose.de  Importiert einzelne genetische Varianten und Risikomarker, die aus
             ärztlichen Laborbefunden, Genetik-Konsilen oder Eigenrecherche bekannt sind,
             in die genetic_risk_markers-Tabelle. Kein WGS/SNP-Array erforderlich.
@purpose.en  Imports individual genetic variants and risk markers known from medical
             lab reports, genetics consultations, or own research into the
             genetic_risk_markers table. No WGS/SNP array required.
@method.de   Liest CSV (Template: templates/genetics_manual_template.csv) und schreibt
             jeden Marker mit UNIQUE(person, rsid, category) via INSERT OR IGNORE.
             Unterstützt auch --inline für Einzeleinträge ohne CSV.
@method.en   Reads CSV (template: templates/genetics_manual_template.csv) and writes
             each marker with UNIQUE(person, rsid, category) via INSERT OR IGNORE.
             Also supports --inline for single entries without CSV.
@reads       CSV-Datei (Template-Format)
@writes      health.db:genetic_risk_markers, health.db:import_log
@limits.de   Kein Ersatz für genetische Beratung. Keine automatische Risikoberechnung.
             Duplikate (gleiche Person + rsid + Kategorie) werden stillschweigend ignoriert.

@relevance.de  Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse
@relevance.en  Enables import of genetic data, essential for genetic analysis
@limits.en   Not a substitute for genetic counseling. No automatic risk calculation.
             Duplicates (same person + rsid + category) are silently ignored.
@usage
    python3 scripts/importers/import_genetics_manual.py templates/genetics_manual_template.csv
    python3 scripts/importers/import_genetics_manual.py meine_marker.csv --dry-run
    python3 scripts/importers/import_genetics_manual.py --inline \\
        --rsid rs1801133 --gene MTHFR --variant "MTHFR C677T" \\
        --genotype CT --category pharmacogenomics --phenotype "Homocystein-Stoffwechsel"
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = Config()
_NOW = datetime.now(timezone.utc).isoformat()

VALID_CATEGORIES = {
    "pharmacogenomics", "disease_risk", "carrier",
    "longevity", "nutrition", "other",
}
VALID_EFFECT = {"low", "moderate", "high", ""}
VALID_CLINSIG = {
    "benign", "likely_benign", "uncertain",
    "likely_pathogenic", "pathogenic", "",
}


def _insert(conn, person: str, row: dict, source: str, dry_run: bool) -> bool:
    rsid      = row.get("rsid", "").strip()
    gene      = row.get("gene", "").strip()
    variant   = row.get("variant_name", "").strip()
    genotype  = row.get("genotype", "").strip()
    category  = row.get("category", "other").strip() or "other"
    risk_al   = row.get("risk_allele", "").strip()
    effect    = row.get("effect_size", "").strip()
    clinsig   = row.get("clinical_significance", "").strip()
    phenotype = row.get("phenotype", "").strip()
    pmid      = row.get("pmid", "").strip()
    clinvar   = row.get("clinvar_id", "").strip()
    notes     = row.get("notes", "").strip()

    if not rsid and not gene:
        return False
    if category not in VALID_CATEGORIES:
        print(t(f"  Warnung: unbekannte Kategorie '{category}' → 'other'",
                f"  Warning: unknown category '{category}' → 'other'"), file=sys.stderr)
        category = "other"

    if dry_run:
        print(f"  [DRY] {rsid or '—':15s} {gene:8s} {variant:20s} {genotype:5s} [{category}]")
        return True

    conn.execute("""
        INSERT OR IGNORE INTO genetic_risk_markers
          (person, rsid, gene, variant_name, category, genotype,
           risk_allele, effect_size, clinical_significance, phenotype,
           pmid, clinvar_id, source, imported_at, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (person, rsid or None, gene or None, variant or None, category,
          genotype or None, risk_al or None, effect or None, clinsig or None,
          phenotype or None, pmid or None, clinvar or None,
          source, _NOW, notes or None))
    return True


def import_file(path: Path, dry_run: bool, lang: str, person: str) -> int:
    conn = open_db()
    inserted = 0
    source = f"manual:{path.name}"

    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row or list(row.values())[0].startswith("#"):
                continue
            if _insert(conn, person, row, source, dry_run):
                inserted += 1

    if not dry_run:
        log_import(conn, "import_genetics_manual", str(path), inserted)
        conn.commit()
    conn.close()
    print(t(f"{inserted} Marker {'(DRY) ' if dry_run else ''}importiert aus {path.name}",
            f"{inserted} markers {'(DRY) ' if dry_run else ''}imported from {path.name}"))
    return inserted


def import_inline(args, dry_run: bool, lang: str, person: str) -> int:
    conn = open_db()
    row = {
        "rsid":                   args.rsid or "",
        "gene":                   args.gene or "",
        "variant_name":           args.variant or "",
        "genotype":               args.genotype or "",
        "category":               args.category or "other",
        "risk_allele":            args.risk_allele or "",
        "effect_size":            args.effect or "",
        "clinical_significance":  args.clinsig or "",
        "phenotype":              args.phenotype or "",
        "pmid":                   args.pmid or "",
        "clinvar_id":             args.clinvar or "",
        "notes":                  args.notes or "",
    }
    ok = _insert(conn, person, row, "manual:inline", dry_run)
    if ok and not dry_run:
        log_import(conn, "import_genetics_manual", "inline", 1)
        conn.commit()
    conn.close()
    return 1 if ok else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Manuelle genetische Marker importieren",
                       "Import manual genetic markers")
    )
    parser.add_argument("file", nargs="?", type=Path,
                        help=t("CSV-Datei (Template: templates/genetics_manual_template.csv)",
                               "CSV file (template: templates/genetics_manual_template.csv)"))
    parser.add_argument("--inline",    action="store_true", help="Einzeleintrag ohne CSV")
    parser.add_argument("--rsid",      help="rs-Nummer")
    parser.add_argument("--gene",      help="Gen-Symbol")
    parser.add_argument("--variant",   help="Variantenname (z.B. 'MTHFR C677T')")
    parser.add_argument("--genotype",  help="Genotyp (z.B. CT, AA, 0/1)")
    parser.add_argument("--category",  default="other",
                        choices=list(VALID_CATEGORIES), help="Kategorie")
    parser.add_argument("--risk-allele", dest="risk_allele", help="Risikoallel")
    parser.add_argument("--effect",    choices=["low", "moderate", "high"], help="Effektstärke")
    parser.add_argument("--clinsig",   help="Klinische Signifikanz")
    parser.add_argument("--phenotype", help="Betroffener Phänotyp")
    parser.add_argument("--pmid",      help="PubMed-ID(s), kommasepariert")
    parser.add_argument("--clinvar",   help="ClinVar-Varianten-ID")
    parser.add_argument("--notes",     help="Freitext-Anmerkungen")
    parser.add_argument("--person",    default=None, help="Personen-ID")
    parser.add_argument("--dry-run",   action="store_true")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = resolve_person(args.person, OWN_PERSON_ID)

    if args.inline:
        import_inline(args, args.dry_run, args.lang, person)
    elif args.file:
        import_file(args.file, args.dry_run, args.lang, person)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
