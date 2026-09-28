#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
scrub_apple_xml — Apple Health Export.xml PII-Bereinigung

@tier        infrastructure
@purpose.de  Entfernt persönlich identifizierbare Informationen (PII) aus Apple Health Export.xml Dateien.
              Überschreibt die Datei in-place oder schreibt in eine angegebene Ausgabedatei.
              Entfernt: persönliche Namen aus sourceName Attributen und weitere PII aus dem <Me> Element.
@purpose.en  Removes personally identifiable information (PII) from Apple Health Export.xml files.
              Rewrites the file in-place or writes to a specified output path.
              Removes: personal names from sourceName attributes and other PII from the <Me> element.
@method.de   Verwendet schnelle regex-basierte Zeilenverarbeitung (kein vollständiges XML-Parsing),
              um Dateien beliebiger Größe ohne Laden in den Speicher zu verarbeiten.
              spezifische Regex-Muster für: sourceName-Attribute, <Me>-Element-Attribute
              (HKCharacteristicTypeIdentifierDateOfBirth, HKCharacteristicTypeIdentifierBiologicalSex,
              etc.). Ersetzt Werte durch neutrale Standardwerte oder leere Strings.
              Unterstützt Dry-Run-Modus (--check) zur Vorschau ohne Änderungen.
@method.en   Uses fast regex-based line processing (no full XML parsing) to
              handle files of any size without loading them into memory.
              Specific regex patterns for: sourceName attributes, <Me> element attributes
              (HKCharacteristicTypeIdentifierDateOfBirth, HKCharacteristicTypeIdentifierBiologicalSex,
              etc.). Replaces values with neutral default values or empty strings.
              Supports dry-run mode (--check) for preview without changes.
@reads       Apple Health Export.xml (Standardpfad aus health_config.json)
@writes      Apple Health Export.xml (in-place) oder angegebene Ausgabedatei
@limits.de   Verarbeitet Dateien zeilenweise - sehr groß Dateien können länger dauern.
              Ersetzt nur bekannte PII-Muster - unbekannte Muster werden nicht erkannt.
              Originaldatei wird überschrieben (Backup empfohlen).

@relevance.de  Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz
@relevance.en  Provides data cleaning and anonymization functions, essential for data privacy
@limits.en   Processes files line by line - very large files may take longer.
              Only replaces known PII patterns - unknown patterns are not detected.
              Original file is overwritten (backup recommended).
@usage
    python scripts/utils/scrub_apple_xml.py
    python scripts/utils/scrub_apple_xml.py --check
    python scripts/utils/scrub_apple_xml.py --out /path/to/clean.xml
    python scripts/utils/scrub_apple_xml.py --xml /path/to/Export.xml --check
    # --check: Probelauf — keine Änderungen (zählt nur Treffer)
    # --out: Ausgabedatei (Standard: in-place Überschreiben)
    # --xml: Pfad zur Export.xml (Standard: aus health_config.json)
"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from utils.anonymize import scrub_apple_source_name
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
DEFAULT_XML = _cfg.apple_xml


# ── Regex patterns ────────────────────────────────────────────────────────────

# Match sourceName="..." attribute value (may contain escaped quotes)
_SOURCE_NAME_RE = re.compile(r'sourceName="([^"]*)"')

# Match individual <Me ...> attributes we want to neutralise
_ME_ATTR_RES = {
    key: re.compile(rf'{re.escape(key)}="([^"]*)"')
    for key in (
        "HKCharacteristicTypeIdentifierDateOfBirth",
        "HKCharacteristicTypeIdentifierBiologicalSex",
        "HKCharacteristicTypeIdentifierBloodType",
        "HKCharacteristicTypeIdentifierFitzpatrickSkinType",
        "HKCharacteristicTypeIdentifierCardioFitnessMedicationsUse",
    )
}

_ME_NEUTRAL = {
    "HKCharacteristicTypeIdentifierDateOfBirth":         "",
    "HKCharacteristicTypeIdentifierBiologicalSex":       "HKBiologicalSexNotSet",
    "HKCharacteristicTypeIdentifierBloodType":           "HKBloodTypeNotSet",
    "HKCharacteristicTypeIdentifierFitzpatrickSkinType": "HKFitzpatrickSkinTypeNotSet",
    "HKCharacteristicTypeIdentifierCardioFitnessMedicationsUse": "",
}


def _scrub_line(line: str) -> tuple[str, int, int]:
    """Scrub one line. Returns (scrubbed_line, source_name_changes, me_changes)."""
    sn_count = 0
    me_count = 0

    def replace_source_name(m: re.Match) -> str:
        nonlocal sn_count
        original = m.group(1)
        cleaned  = scrub_apple_source_name(original)
        if cleaned != original:
            sn_count += 1
        return f'sourceName="{cleaned}"'

    line = _SOURCE_NAME_RE.sub(replace_source_name, line)

    # Only process <Me ...> lines (rare — usually just one in the whole file)
    if "<Me " in line:
        for attr, pattern in _ME_ATTR_RES.items():
            neutral = _ME_NEUTRAL[attr]
            def replace_me(m: re.Match, _neutral=neutral) -> str:
                nonlocal me_count
                if m.group(1) != _neutral:
                    me_count += 1
                return f'{attr}="{_neutral}"'
            line = pattern.sub(replace_me, line)

    return line, sn_count, me_count


def scrub_file(xml_path: Path, out_path: Path | None = None,
               dry_run: bool = False, verbose: bool = True) -> dict:
    """Scrub the XML file. Returns stats dict."""
    if not xml_path.exists():
        print(t(f"Datei nicht gefunden: {xml_path}",
                f"File not found: {xml_path}"), file=sys.stderr)
        return {}

    size_mb = xml_path.stat().st_size / 1e6
    if verbose:
        print(t(f"Lese {size_mb:.0f} MB {xml_path.name} ...",
                f"Reading {size_mb:.0f} MB {xml_path.name} ..."))

    total_sn = 0
    total_me = 0
    lines_written = 0

    in_place = out_path is None
    write_target = xml_path if in_place else out_path

    if dry_run:
        with xml_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                _, sn, me = _scrub_line(line)
                total_sn += sn
                total_me += me
    else:
        # Write to a temp file in the same directory, then replace atomically
        tmp = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8",
            dir=xml_path.parent, suffix=".tmp", delete=False)
        tmp_path = Path(tmp.name)
        try:
            with xml_path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    scrubbed, sn, me = _scrub_line(line)
                    tmp.write(scrubbed)
                    total_sn += sn
                    total_me += me
                    lines_written += 1
            tmp.close()
            tmp_path.replace(write_target)
        except Exception:
            tmp.close()
            tmp_path.unlink(missing_ok=True)
            raise

    stats = {"source_name_changes": total_sn, "me_changes": total_me,
             "lines": lines_written, "dry_run": dry_run}

    if verbose:
        mode = t("(Probelauf)", "(dry-run)") if dry_run else ""
        print(t(
            f"  sourceName-Korrekturen: {total_sn} {mode}",
            f"  sourceName fixes: {total_sn} {mode}"))
        print(t(
            f"  <Me>-Attribute bereinigt: {total_me} {mode}",
            f"  <Me> attributes scrubbed: {total_me} {mode}"))
        if not dry_run:
            print(t(f"  Geschrieben: {write_target}",
                    f"  Written: {write_target}"))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description=t("Apple Health XML PII-Bereinigung",
                      "Apple Health XML PII scrubber"))
    parser.add_argument("--xml",   default=str(DEFAULT_XML),
                        help=t("Pfad zur Export.xml", "Path to Export.xml"))
    parser.add_argument("--out",   default=None,
                        help=t("Ausgabedatei (Standard: in-place)", "Output file (default: in-place)"))
    parser.add_argument("--check", action="store_true",
                        help=t("Probelauf — keine Änderungen", "Dry-run — no changes"))
    parser.add_argument("--quiet", action="store_true")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    stats = scrub_file(
        xml_path=Path(args.xml),
        out_path=Path(args.out) if args.out else None,
        dry_run=args.check,
        verbose=not args.quiet,
    )
    if not stats:
        sys.exit(1)


if __name__ == "__main__":
    main()
