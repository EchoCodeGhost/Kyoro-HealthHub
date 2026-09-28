#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_genetics_dante.py — Dante Labs WGS-Export importieren

@tier        infrastructure
@purpose.de  Importiert den Dante Labs WGS-VCF-Export (Whole Genome Sequencing, ~30× Coverage)
             in die genetic_variants-Tabelle.
@purpose.en  Imports the Dante Labs WGS VCF export (Whole Genome Sequencing, ~30× coverage)
             into the genetic_variants table.
@method.de   Delegiert an import_genetics_vcf.py. Dante liefert VCF 4.2 (GRCh38),
             FILTER=PASS für hochqualitative Varianten. Nur PASS-Varianten werden
             standardmäßig importiert (--all-filters für alle).
@method.en   Delegates to import_genetics_vcf.py. Dante delivers VCF 4.2 (GRCh38),
             FILTER=PASS for high-quality variants. Only PASS variants are imported
             by default (--all-filters for all).
@reads       <export>.vcf oder <export>.vcf.gz (Dante Labs WGS-Download)
@writes      health.db:genetic_variants, health.db:import_log
@limits.de   WGS ~4–6 Mio. Varianten. Import kann mehrere Minuten dauern.
             Nur rsid-annotierte Varianten werden mit rsid gespeichert.

@relevance.de  Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse
@relevance.en  Enables import of genetic data, essential for genetic analysis
@limits.en   WGS ~4–6 million variants. Import may take several minutes.
             Only rsid-annotated variants are stored with rsid.
@usage
    python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf.gz
    python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf --dry-run --limit 5000
    python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf.gz --all-filters
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import OWN_PERSON_ID
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import resolve_person
from importers.import_genetics_vcf import import_vcf


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Dante Labs WGS-VCF importieren", "Import Dante Labs WGS VCF")
    )
    parser.add_argument("file", type=Path, help="Dante Labs .vcf oder .vcf.gz")
    parser.add_argument("--genome-build", default="GRCh38")
    parser.add_argument("--all-filters", action="store_true",
                        help=t("Auch nicht-PASS Varianten", "Also import non-PASS variants"))
    parser.add_argument("--person",  default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit",   type=int, default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = resolve_person(args.person, OWN_PERSON_ID)

    if not args.file.exists():
        print(t(f"Datei nicht gefunden: {args.file}", f"File not found: {args.file}"),
              file=sys.stderr)
        sys.exit(1)

    import_vcf(
        path=args.file,
        source="dante",
        genome_build=args.genome_build,
        dry_run=args.dry_run,
        person=person,
        pass_only=not args.all_filters,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
