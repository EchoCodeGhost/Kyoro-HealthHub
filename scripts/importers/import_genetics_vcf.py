#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_genetics_vcf.py — Gemeinsamer VCF-Parser für Dante Labs, Nebula, Sequencing.com

@tier        infrastructure
@purpose.de  Interner VCF-Parser, der von den sourcespezifischen Importern
             (import_genetics_dante.py, import_genetics_nebula.py,
             import_genetics_sequencing.py) genutzt wird.
@purpose.en  Internal VCF parser used by source-specific importers
             (import_genetics_dante.py, import_genetics_nebula.py,
             import_genetics_sequencing.py).
@method.de   Parst VCF 4.x (plain oder gzip). Extrahiert rsid aus ID-Feld,
             Genotyp aus GT-Subfeld des SAMPLE-Feldes.
             Zygosität: 0/0 → homozygous_ref, 0/1 → heterozygous, 1/1 → homozygous_alt.
@method.en   Parses VCF 4.x (plain or gzip). Extracts rsid from ID field,
             genotype from GT subfield of SAMPLE field.
             Zygosity: 0/0 → homozygous_ref, 0/1 → heterozygous, 1/1 → homozygous_alt.
@reads       VCF-Datei (.vcf oder .vcf.gz)
@writes      health.db:genetic_variants, health.db:import_log
@limits.de   Nur diploide Genotypen (GT). Multi-allele ALT (A,G) wird als "multi_allelic"
             markiert. Strukturelle Varianten (SV) werden übersprungen.

@relevance.de  Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse
@relevance.en  Enables import of genetic data, essential for genetic analysis
@limits.en   Only diploid genotypes (GT). Multi-allele ALT (A,G) is marked "multi_allelic".
             Structural variants (SV) are skipped.
@usage
    # Nicht direkt aufrufen — wird von Dante/Nebula/Sequencing-Importern genutzt.
    python3 scripts/importers/import_genetics_vcf.py <file.vcf> --source dante
    python3 scripts/importers/import_genetics_vcf.py <file.vcf.gz> --source nebula --dry-run
    python3 scripts/importers/import_genetics_vcf.py <file.vcf> --source sequencing
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

VALID_SOURCES = {"dante", "nebula", "sequencing", "aniva"}
GENOME_BUILD_DEFAULT = "GRCh38"


def _zygosity_from_gt(gt: str) -> str:
    gt = gt.replace("|", "/")
    if "." in gt:
        return "no_call"
    alleles = gt.split("/")
    if len(alleles) != 2:
        return "unknown"
    a, b = alleles
    if a == b == "0":
        return "homozygous_ref"
    if a == b:
        return "homozygous_alt"
    return "heterozygous"


def _extract_gt(format_str: str, sample_str: str) -> str | None:
    fields = format_str.split(":")
    values = sample_str.split(":")
    try:
        gt_idx = fields.index("GT")
        return values[gt_idx]
    except (ValueError, IndexError):
        return None


def _is_sv(alt: str) -> bool:
    return alt.startswith("<") and alt.endswith(">")


def _open_vcf(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def import_vcf(path: Path, source: str, genome_build: str, dry_run: bool,
               person: str, pass_only: bool = True,
               limit: int | None = None) -> int:
    conn = open_db()
    inserted = skipped = 0

    with _open_vcf(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#"):
                continue
            if not line.strip():
                continue

            parts = line.split("\t")
            if len(parts) < 5:
                skipped += 1
                continue

            chrom   = parts[0].lstrip("chr")
            pos_str = parts[1]
            vcf_id  = parts[2]
            ref     = parts[3]
            alt     = parts[4]
            filt    = parts[6] if len(parts) > 6 else "."
            fmt     = parts[8] if len(parts) > 8 else ""
            sample  = parts[9] if len(parts) > 9 else ""

            if _is_sv(alt):
                skipped += 1
                continue

            if pass_only and filt not in ("PASS", ".", ""):
                skipped += 1
                continue

            rsid = vcf_id if vcf_id.startswith("rs") else None

            try:
                pos = int(pos_str)
            except ValueError:
                pos = None

            gt = _extract_gt(fmt, sample) if fmt and sample else None
            genotype = gt or "."
            zygosity = _zygosity_from_gt(gt) if gt else "unknown"

            if dry_run:
                if inserted < 5:
                    print(f"  [DRY] {rsid or vcf_id[:15]:15s} chr{chrom:3s} "
                          f"{pos_str:10s} {ref:3s}>{alt:3s} {genotype:5s} [{zygosity}]")
                elif inserted == 5:
                    print("  [DRY] ...")
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO genetic_variants
                      (person, rsid, chrom, pos, ref, alt, genotype,
                       zygosity, source, genome_build, imported_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (person, rsid, chrom, pos, ref, alt, genotype,
                      zygosity, source, genome_build, _NOW))

            inserted += 1
            if limit and inserted >= limit:
                break

    if not dry_run:
        log_import(conn, f"import_genetics_{source}", str(path), inserted)
        conn.commit()
    conn.close()

    print(t(f"{inserted} Varianten {'(DRY) ' if dry_run else ''}importiert, {skipped} übersprungen",
            f"{inserted} variants {'(DRY) ' if dry_run else ''}imported, {skipped} skipped"))
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("VCF-Datei importieren (Dante / Nebula / Sequencing.com)",
                       "Import VCF file (Dante / Nebula / Sequencing.com)")
    )
    parser.add_argument("file", type=Path, help="VCF oder VCF.gz Datei")
    parser.add_argument("--source", required=True, choices=list(VALID_SOURCES),
                        help="Datenquelle")
    parser.add_argument("--genome-build", default=GENOME_BUILD_DEFAULT,
                        help=f"Genomversion (Standard: {GENOME_BUILD_DEFAULT})")
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
        source=args.source,
        genome_build=args.genome_build,
        dry_run=args.dry_run,
        person=person,
        pass_only=not args.all_filters,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
