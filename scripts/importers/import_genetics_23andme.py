#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_genetics_23andme.py — 23andMe Rohdaten importieren

@tier        infrastructure
@purpose.de  Importiert den 23andMe SNP-Array-Rohdaten-Export (TSV) in die
             genetic_variants-Tabelle. Unterstützt plain-Text und gzip-komprimierte Dateien.
@purpose.en  Imports the 23andMe SNP array raw data export (TSV) into the
             genetic_variants table. Supports plain text and gzip-compressed files.
@method.de   Liest 23andMe-TSV (Spalten: rsid, chromosome, position, genotype).
             Kommentarzeilen (#) werden übersprungen. Zygosität wird aus dem Genotyp
             abgeleitet. No-Calls ("--", "II") werden als genotype gespeichert.
             Genomversion: GRCh37 (hg19) — 23andMe-Standard.
@method.en   Reads 23andMe TSV (columns: rsid, chromosome, position, genotype).
             Comment lines (#) are skipped. Zygosity is derived from genotype.
             No-calls ("--", "II") are stored as genotype.
             Genome build: GRCh37 (hg19) — 23andMe default.
@reads       <datei>.txt oder <datei>.txt.gz (23andMe Rohdaten-Export)
@writes      health.db:genetic_variants, health.db:import_log
@limits.de   ~600.000 SNPs je nach Chip-Version (v3/v4/v5). Kein WGS.
             Nur rsid-basierte Varianten; Indels ohne rs-Nummer werden übersprungen.

@relevance.de  Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse
@relevance.en  Enables import of genetic data, essential for genetic analysis
@limits.en   ~600,000 SNPs depending on chip version (v3/v4/v5). Not WGS.
             Only rsid-based variants; indels without rs number are skipped.
@usage
    python3 scripts/importers/import_genetics_23andme.py genome_export.txt
    python3 scripts/importers/import_genetics_23andme.py genome_export.txt.gz
    python3 scripts/importers/import_genetics_23andme.py genome_export.txt --dry-run --limit 1000
"""

import argparse
import gzip
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
SOURCE = "23andme"
GENOME_BUILD = "GRCh37"
NO_CALL = {"--", "II", "DI", "ID", "DD"}


def _zygosity(genotype: str, ref: str | None = None) -> str | None:
    if not genotype or genotype in NO_CALL:
        return "no_call"
    alleles = set(genotype)
    if len(alleles) == 1:
        return "homozygous"
    return "heterozygous"


def _open_file(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def import_file(path: Path, dry_run: bool, lang: str, person: str,
                limit: int | None = None) -> int:
    conn = open_db()
    inserted = skipped = 0

    with _open_file(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#") or not line.strip():
                continue

            parts = line.split("\t")
            if len(parts) < 4:
                skipped += 1
                continue

            rsid, chrom, pos_str, genotype = parts[0], parts[1], parts[2], parts[3]

            if not rsid.startswith("rs"):
                skipped += 1
                continue

            try:
                pos = int(pos_str)
            except ValueError:
                pos = None

            zygosity = _zygosity(genotype)

            if dry_run:
                if inserted < 5:
                    print(f"  [DRY] {rsid:15s} chr{chrom:3s} {pos_str:10s} {genotype:5s} [{zygosity}]")
                elif inserted == 5:
                    print("  [DRY] ...")
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO genetic_variants
                      (person, rsid, chrom, pos, ref, alt, genotype,
                       zygosity, source, genome_build, imported_at)
                    VALUES (?,?,?,?,NULL,NULL,?,?,?,?,?)
                """, (person, rsid, chrom, pos, genotype, zygosity,
                      SOURCE, GENOME_BUILD, _NOW))

            inserted += 1
            if limit and inserted >= limit:
                break

    if not dry_run:
        log_import(conn, "import_genetics_23andme", str(path), inserted)
        conn.commit()
    conn.close()

    print(t(f"{inserted} SNPs {'(DRY) ' if dry_run else ''}importiert, {skipped} übersprungen",
            f"{inserted} SNPs {'(DRY) ' if dry_run else ''}imported, {skipped} skipped"))
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("23andMe Rohdaten-Export importieren",
                       "Import 23andMe raw data export")
    )
    parser.add_argument("file", type=Path,
                        help=t("23andMe .txt oder .txt.gz Exportdatei",
                               "23andMe .txt or .txt.gz export file"))
    parser.add_argument("--person",  default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit",   type=int, default=None,
                        help=t("Maximale Anzahl SNPs (Test)", "Max SNPs to import (test)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = resolve_person(args.person, OWN_PERSON_ID)

    if not args.file.exists():
        print(t(f"Datei nicht gefunden: {args.file}", f"File not found: {args.file}"),
              file=sys.stderr)
        sys.exit(1)

    import_file(args.file, args.dry_run, args.lang, person, args.limit)


if __name__ == "__main__":
    main()
