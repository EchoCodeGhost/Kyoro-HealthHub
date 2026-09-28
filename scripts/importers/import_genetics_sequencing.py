#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_genetics_sequencing.py — Sequencing.com WGS/WES-Export importieren

@tier        infrastructure
@purpose.de  Importiert WGS- oder WES-VCF-Exporte von Sequencing.com in die
             genetic_variants-Tabelle. Sequencing.com unterstützt mehrere
             Sequenzierungspläne (Whole Genome, Exome, Methylation).
@purpose.en  Imports WGS or WES VCF exports from Sequencing.com into the
             genetic_variants table. Sequencing.com supports multiple
             sequencing plans (Whole Genome, Exome, Methylation).
@method.de   Delegiert an import_genetics_vcf.py. Genomversion: GRCh38 (Standard)
             oder GRCh37 (ältere Exporte — mit --genome-build angeben).
             Sequencing.com-VCFs variieren je nach Labor-Partner; alle FILTER-Werte
             werden mit --all-filters importiert.
@method.en   Delegates to import_genetics_vcf.py. Genome build: GRCh38 (default)
             or GRCh37 (older exports — specify with --genome-build).
             Sequencing.com VCFs vary by lab partner; all FILTER values
             are imported with --all-filters.
@reads       <export>.vcf oder <export>.vcf.gz (Sequencing.com Download-Center)
@writes      health.db:genetic_variants, health.db:import_log
@limits.de   Format variiert je nach Sequenzierungsplan und Labor-Partner.
             Exome: ~60.000–80.000 Varianten; WGS: ~4–6 Mio. Varianten.

@relevance.de  Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse
@relevance.en  Enables import of genetic data, essential for genetic analysis
@limits.en   Format varies by sequencing plan and lab partner.
             Exome: ~60,000–80,000 variants; WGS: ~4–6M variants.
@usage
    python3 scripts/importers/import_genetics_sequencing.py sequencing_wgs.vcf.gz
    python3 scripts/importers/import_genetics_sequencing.py sequencing_exome.vcf --dry-run
    python3 scripts/importers/import_genetics_sequencing.py sequencing_wgs.vcf.gz \\
        --genome-build GRCh37 --all-filters
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
        description=t("Sequencing.com VCF-Export importieren",
                       "Import Sequencing.com VCF export")
    )
    parser.add_argument("file", type=Path, help="Sequencing.com .vcf oder .vcf.gz")
    parser.add_argument("--genome-build", default="GRCh38",
                        help="GRCh38 (Standard) oder GRCh37")
    parser.add_argument("--all-filters", action="store_true",
                        help=t("Auch nicht-PASS Varianten importieren",
                               "Also import non-PASS variants"))
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
        source="sequencing",
        genome_build=args.genome_build,
        dry_run=args.dry_run,
        person=person,
        pass_only=not args.all_filters,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
