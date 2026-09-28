#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_genetics_nebula.py — Nebula Genomics WGS-Export importieren

@tier        infrastructure
@purpose.de  Importiert den Nebula Genomics WGS-VCF-Export (30× WGS + Imputation)
             in die genetic_variants-Tabelle. Nebula ergänzt Sequenzierungs-Calls
             mit imputierten Varianten (INFO-Feld enthält IMPUTED-Flag).
@purpose.en  Imports the Nebula Genomics WGS VCF export (30× WGS + imputation)
             into the genetic_variants table. Nebula augments sequenced calls
             with imputed variants (INFO field contains IMPUTED flag).
@method.de   Delegiert an import_genetics_vcf.py. Genomversion: GRCh38.
             Nebula-VCFs enthalten ggf. IMPUTED-Marker im INFO-Feld — diese werden
             mit Genotyp "imputed" importiert, falls --include-imputed angegeben.
@method.en   Delegates to import_genetics_vcf.py. Genome build: GRCh38.
             Nebula VCFs may contain IMPUTED markers in the INFO field — these are
             imported with genotype "imputed" if --include-imputed is specified.
@reads       <export>.vcf oder <export>.vcf.gz (Nebula Genomics Download)
@writes      health.db:genetic_variants, health.db:import_log
@limits.de   WGS-Teil ~4–6 Mio. Varianten, Imputation kann auf >10 Mio. anwachsen.
             Imputierte Varianten haben niedrigere Konfidenz.

@relevance.de  Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse
@relevance.en  Enables import of genetic data, essential for genetic analysis
@limits.en   WGS part ~4–6M variants, imputation can grow to >10M.
             Imputed variants have lower confidence.
@usage
    python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf.gz
    python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf.gz --include-imputed
    python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf --dry-run --limit 5000
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
        description=t("Nebula Genomics WGS-VCF importieren",
                       "Import Nebula Genomics WGS VCF")
    )
    parser.add_argument("file", type=Path, help="Nebula .vcf oder .vcf.gz")
    parser.add_argument("--genome-build", default="GRCh38")
    parser.add_argument("--include-imputed", action="store_true",
                        help=t("Imputierte Varianten einschließen",
                               "Include imputed variants"))
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

    # Nebula: PASS + optional imputed (FILTER kann "." oder leer sein bei imputierten)
    import_vcf(
        path=args.file,
        source="nebula",
        genome_build=args.genome_build,
        dry_run=args.dry_run,
        person=person,
        pass_only=not args.include_imputed,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
