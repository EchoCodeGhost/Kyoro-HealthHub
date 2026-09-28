#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Docstring Validierungstool für Kyoro-HealthHub

Validiert alle Python-Skripte im Projekt gegen das definierte Docstring-Schema.
Das Tool prüft auf:
- Vorhandensein von Modul-Docstrings
- Erforderliche @-Tags basierend auf @tier
- Bilinguale Tags (@purpose.de/en, @method.de/en, @limits.de/en)
- Korrekte Formatierung von @refs mit DOI
- Mindestens 2 Beispiele in 
@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@usage

Usage:
    python scripts/check_docstrings.py
    python scripts/check_docstrings.py --path scripts/         # Bestimmtes Verzeichnis
    python scripts/check_docstrings.py --quiet                # Nur Fehler anzeigen
    python scripts/check_docstrings.py --fix                  # Automatische Korrekturen (geplant)
    python scripts/check_docstrings.py --stats                # Statistik anzeigen

Exit Codes:
    0: Alle Docstrings sind valide
    1: Fehler in Docstrings gefunden
    2: kritischer Fehler (z.B. Verzeichnis nicht gefunden)

@tier        infrastructure
@purpose.de  Validiert alle Docstrings im Projekt gegen das strukturierte Schema
@purpose.en  Validates all docstrings in the project against the structured schema
@method.de   Durchsucht rekursiv Python-Dateien, extrahiert Modul-Docstrings via AST,
             prüft auf erforderliche Tags basierend auf @tier-Klassifizierung,
             validiert bilinguale Tags und Referenzformatierung
@method.en   Recursively scans Python files, extracts module docstrings via AST,
             checks for required tags based on @tier classification,
             validates bilingual tags and reference formatting
@reads       Alle Python-Dateien in den angegebenen Verzeichnissen
@writes      STDERR/STDOUT (Fehlermeldungen und Statistik)
@limits.de   Erkennt nur Modul-Docstrings, nicht Funktions-Docstrings (geplant für v2).
             Automatische Korrekturen noch nicht implementiert.
@limits.en   Only detects module docstrings, not function docstrings (planned for v2).
             Automatic fixes not yet implemented.
@usage
    python scripts/check_docstrings.py
    python scripts/check_docstrings.py --path scripts/compute
    python scripts/check_docstrings.py --stats
"""

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from check_compliance import (
    validate_file as _compliance_validate_file,
    load_baseline as _load_compliance_baseline,
    DEFAULT_BASELINE_PATH as _COMPLIANCE_BASELINE_PATH,
)


@dataclass
class ValidationResult:
    """Ergebnis der Validierung einer Datei."""
    filepath: Path
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        status = "✅" if self.is_valid else "❌"
        return f"{status} {self.filepath.relative_to(self.filepath.cwd())}: {len(self.errors)} errors, {len(self.warnings)} warnings"


@dataclass
class DocstringInfo:
    """Extrahierte Informationen aus einem Docstring."""
    raw: str
    tier: Optional[str] = None
    has_purpose_de: bool = False
    has_purpose_en: bool = False
    has_method_de: bool = False
    has_method_en: bool = False
    has_limits_de: bool = False
    has_limits_en: bool = False
    has_relevance_de: bool = False
    has_relevance_en: bool = False
    has_reads: bool = False
    has_writes: bool = False
    has_refs: bool = False
    has_usage: bool = False
    has_scoring: bool = False
    has_prompt_classification: bool = False
    has_prompt_de: bool = False
    has_prompt_en: bool = False
    prompt_classifications: List[str] = field(default_factory=list)
    refs_count: int = 0
    usage_lines: int = 0


# Pflicht-Tags für verschiedene Skript-Typen
# @usage, @scoring und @refs sind in den jeweiligen Kategorien verpflichtend;
# @relevance.de/@relevance.en sind für alle Tiers verpflichtend, ohne Ausnahme.
REQUIRED_TAGS: Dict[str, List[str]] = {
    "validated": [
        "@tier", "@purpose.de", "@purpose.en",
        "@method.de", "@method.en", "@refs", "@relevance.de", "@relevance.en", "@limits.de", "@limits.en", "@usage"
    ],
    "calibrated": [
        "@tier", "@purpose.de", "@purpose.en",
        "@method.de", "@method.en", "@refs", "@relevance.de", "@relevance.en", "@limits.de", "@limits.en", "@usage"
    ],
    "research": [
        "@tier", "@purpose.de", "@purpose.en", 
        "@method.de", "@method.en", "@refs", "@relevance.de", "@relevance.en", "@usage"
    ],
    "heuristic": [
        "@tier", "@purpose.de", "@purpose.en",
        "@method.de", "@method.en", "@relevance.de", "@relevance.en", "@limits.de", "@limits.en", "@usage", "@scoring"
    ],
    "experimental": [
        "@tier", "@purpose.de", "@purpose.en",
        "@method.de", "@method.en", "@relevance.de", "@relevance.en", "@limits.de", "@limits.en", "@usage"
    ],
    "infrastructure": [
        "@tier", "@purpose.de", "@purpose.en",
        "@method.de", "@method.en", "@relevance.de", "@relevance.en"
    ],
}

# Empfohlene Tags (nur Tags, die nicht bereits Pflicht sind)
RECOMMENDED_TAGS: Dict[str, List[str]] = {
    "validated": ["@reads", "@writes"],
    "calibrated": ["@reads", "@writes"],
    "research": ["@reads", "@writes", "@limits.de", "@limits.en"],
    "heuristic": ["@reads", "@writes", "@refs"],
    "experimental": ["@reads", "@writes", "@refs"],
    "infrastructure": ["@reads", "@writes", "@limits.de", "@limits.en", "@usage"],
}

# Bilinguale Tag-Paare
BILINGUAL_TAGS: List[str] = ["purpose", "method", "limits", "relevance"]


class DocstringValidator:
    """Validiert Docstrings gegen das Kyoro-HealthHub-Schema."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.cwd()
        self.scripts_dir = self.base_path / "scripts"
        self.compliance_baseline = _load_compliance_baseline(
            self.base_path / _COMPLIANCE_BASELINE_PATH)
        
    def extract_docstring(self, source: str) -> Optional[str]:
        """Extrahiert den Modul-Docstring aus Python-Quellcode."""
        try:
            tree = ast.parse(source, filename=str(self.base_path))
            # Extrahiere Docstring - kompatibel mit allen Python-Versionen
            if tree.body and isinstance(tree.body[0], ast.Expr):
                value = tree.body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    return value.value
                elif hasattr(ast, 'Str') and isinstance(value, ast.Str):
                    # Python < 3.8 compatibility
                    return value.s
            # Alternative: ast.get_docstring (für Python 3.8+)
            if hasattr(ast, 'get_docstring'):
                docstring = ast.get_docstring(tree)
                if docstring:
                    return docstring
        except SyntaxError:
            # Syntaxfehler ignorieren, da wir nur Docstrings prüfen
            pass
        return None
    
    def parse_docstring(self, docstring: str) -> DocstringInfo:
        """Parsed einen Docstring und extrahiert Tags."""
        info = DocstringInfo(raw=docstring)
        
        # Extrahiere @tier
        tier_match = re.search(r'@tier\s+(\w+)', docstring)
        if tier_match:
            info.tier = tier_match.group(1)
        
        # Prüfe auf bilinguale Tags
        for tag in BILINGUAL_TAGS:
            de_tag = f"@{tag}.de"
            en_tag = f"@{tag}.en"
            if tag == "purpose":
                info.has_purpose_de = de_tag in docstring
                info.has_purpose_en = en_tag in docstring
            elif tag == "method":
                info.has_method_de = de_tag in docstring
                info.has_method_en = en_tag in docstring
            elif tag == "limits":
                info.has_limits_de = de_tag in docstring
                info.has_limits_en = en_tag in docstring
            elif tag == "relevance":
                info.has_relevance_de = de_tag in docstring
                info.has_relevance_en = en_tag in docstring
        
        # Prüfe auf einzelne Tags
        info.has_reads = "@reads" in docstring
        info.has_writes = "@writes" in docstring
        info.has_refs = "@refs" in docstring
        info.has_usage = "@usage" in docstring
        info.has_scoring = "@scoring" in docstring
        
        # Prüfe auf Prompt-Tags
        info.has_prompt_classification = "@prompt-classification" in docstring
        info.has_prompt_de = "@prompt.de" in docstring
        info.has_prompt_en = "@prompt.en" in docstring
        
        # Extrahiere Prompt-Klassifizierungen
        prompt_class_match = re.search(r'@prompt-classification\s+(.+?)(?=\n@\w+|\n\s*"""|$)', docstring, re.DOTALL)
        if prompt_class_match:
            classifications = prompt_class_match.group(1).strip()
            info.prompt_classifications = [c.strip() for c in classifications.split(',')]
        
        # Zähle Referenzen
        if info.has_refs:
            refs_section = re.search(r'@refs(.*?)(?=@\w+|$)', docstring, re.DOTALL)
            if refs_section:
                refs_content = refs_section.group(1)
                info.refs_count = len([line for line in refs_content.split('\n') if line.strip() and not line.startswith('@')])
        
        # Zähle Zeilen in @usage
        if info.has_usage:
            usage_section = re.search(r'@usage(.*?)(?=@\w+|$)', docstring, re.DOTALL)
            if usage_section:
                usage_content = usage_section.group(1).strip()
                info.usage_lines = len([line for line in usage_content.split('\n') if line.strip()])
        
        return info
    
    def get_required_tags(self, tier: Optional[str]) -> List[str]:
        """Gibt die erforderlichen Tags für einen gegebenen Tier zurück."""
        if tier in REQUIRED_TAGS:
            return REQUIRED_TAGS[tier]
        return REQUIRED_TAGS["infrastructure"]
    
    def get_recommended_tags(self, tier: Optional[str]) -> List[str]:
        """Gibt die empfohlenen Tags für einen gegebenen Tier zurück."""
        if tier in RECOMMENDED_TAGS:
            return RECOMMENDED_TAGS[tier]
        return []
    
    def validate_docstring(self, docstring: str, filepath: Path) -> Tuple[List[str], List[str]]:
        """
        Validiert einen Docstring gegen die Anforderungen.
        
        Returns:
            Tuple von (errors, warnings)
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        if not docstring or docstring.strip() == '"""' or docstring.strip() == "'''":
            errors.append("Missing or empty module docstring")
            return errors, warnings
        
        # Parsen des Docstrings
        info = self.parse_docstring(docstring)
        
        # Prüfe auf @tier
        if not info.tier:
            errors.append("Missing @tier tag (must be: validated|calibrated|research|heuristic|experimental|infrastructure)")
            return errors, warnings
        
        # Prüfe auf erforderliche Tags
        required_tags = self.get_required_tags(info.tier)
        for tag in required_tags:
            tag_found = False
            if tag == "@tier":
                tag_found = info.tier is not None
            elif tag == "@purpose.de":
                tag_found = info.has_purpose_de
            elif tag == "@purpose.en":
                tag_found = info.has_purpose_en
            elif tag == "@method.de":
                tag_found = info.has_method_de
            elif tag == "@method.en":
                tag_found = info.has_method_en
            elif tag == "@limits.de":
                tag_found = info.has_limits_de
            elif tag == "@limits.en":
                tag_found = info.has_limits_en
            elif tag == "@reads":
                tag_found = info.has_reads
            elif tag == "@writes":
                tag_found = info.has_writes
            elif tag == "@refs":
                tag_found = info.has_refs
            elif tag == "@usage":
                tag_found = info.has_usage
            elif tag == "@scoring":
                tag_found = info.has_scoring
            elif tag == "@relevance.de":
                tag_found = info.has_relevance_de
            elif tag == "@relevance.en":
                tag_found = info.has_relevance_en
            
            if not tag_found:
                errors.append(f"Missing required tag: {tag}")
        
        # Prüfe auf bilinguale Tags
        for tag in BILINGUAL_TAGS:
            de_tag = f"@{tag}.de"
            en_tag = f"@{tag}.en"
            
            has_de = getattr(info, f'has_{tag}_de', False)
            has_en = getattr(info, f'has_{tag}_en', False)
            
            if has_de and not has_en:
                errors.append(f"Missing bilingual tag: {en_tag} (has {de_tag})")
            elif has_en and not has_de:
                errors.append(f"Missing bilingual tag: {de_tag} (has {en_tag})")
        
        # Prüfe auf @usage mit Beispielen (Pflicht für validated, calibrated, research, heuristic, experimental)
        required_tags_set = set(self.get_required_tags(info.tier))
        if "@usage" in required_tags_set:
            if not info.has_usage:
                errors.append("Missing @usage section with examples")
            elif info.usage_lines < 2:
                errors.append("@usage section should contain at least 2 examples")
        else:
            if info.has_usage and info.usage_lines < 2:
                warnings.append("@usage section should contain at least 2 examples")
            elif not info.has_usage:
                warnings.append("Missing @usage section with examples")
        
        # Prüfe auf @refs mit DOI (Pflicht für validated, calibrated, research, heuristic)
        if "@refs" in required_tags_set:
            if not info.has_refs:
                errors.append("Missing @refs with DOI references")
            elif info.refs_count == 0:
                errors.append("@refs section is empty - add DOI references")
            elif "doi:" not in docstring:
                errors.append("@refs should contain DOI links (format: doi:xxx)")
        else:
            # Empfohlene Prüfung für andere Tier-Typen
            if info.tier in ["research", "heuristic"]:
                if not info.has_refs:
                    warnings.append(f"{info.tier} scripts should have @refs with DOI references")
                elif info.refs_count == 0:
                    warnings.append("@refs section is empty - add DOI references")
                elif "doi:" not in docstring:
                    warnings.append("@refs should contain DOI links (format: doi:xxx)")
        
        # Prüfe auf @scoring (Pflicht für heuristic)
        if "@scoring" in required_tags_set:
            if "@scoring" not in docstring:
                errors.append("Missing required tag: @scoring")
        
        # Prüfe auf empfohlene Tags
        recommended_tags = self.get_recommended_tags(info.tier)
        for tag in recommended_tags:
            if tag not in docstring:
                warnings.append(f"Recommended tag missing: {tag}")
        
        # Prüfe auf Prompt-Tags
        if info.has_prompt_classification:
            # Wenn Prompt-Klassifizierung vorhanden, prüfe auf bilinguale Prompts
            if info.has_prompt_classification and not (info.has_prompt_de or info.has_prompt_en):
                warnings.append("Prompt classification present but no @prompt.de or @prompt.en found")
            
            # Prüfe auf gültige Klassifizierungsformate
            for classification in info.prompt_classifications:
                if classification and ':' not in classification:
                    warnings.append(f"Invalid prompt classification format: '{classification}' (expected 'Type:Subtype')")
            
            # Prüfe auf bekannte Haupttypen
            valid_main_types = ['LLM', 'VLM', 'SQL', 'Hybrid', 'Template']
            for classification in info.prompt_classifications:
                if classification:
                    main_type = classification.split(':')[0] if ':' in classification else classification
                    if main_type not in valid_main_types:
                        warnings.append(f"Unknown prompt main type: '{main_type}' (valid: {', '.join(valid_main_types)})")
        
        # Compliance-Pruefung: Datenschutz -- delegiert an check_compliance.py statt
        # eine zweite, abweichende Erkennungslogik zu pflegen. Frueher hatte dieses
        # Modul einen eigenen, einfacheren Regex-Block mit eigenem Fehlerformat
        # ("Contains medical diagnosis"), der die per --review freigegebene
        # compliance_baseline.json gar nicht kannte -- ein per Baseline bestaetigter
        # Fehlalarm blockierte den Commit trotzdem, weil dieser (und nicht
        # check_compliance.py) das tatsaechliche Pre-Commit-Gate ist. Jetzt: eine
        # einzige Erkennung, eine einzige Baseline.
        compliance_result = _compliance_validate_file(
            filepath, self.compliance_baseline, self.base_path)
        if compliance_result.new_violations:
            errors.append(
                f"Compliance violations: {', '.join(compliance_result.new_violations)}")

        return errors, warnings
    
    def validate_file(self, filepath: Path) -> ValidationResult:
        """Validiert eine einzelne Python-Datei."""
        if not filepath.suffix.lower() == ".py":
            return ValidationResult(filepath=filepath, is_valid=True)
        
        try:
            source = filepath.read_text(encoding='utf-8')
        except (UnicodeDecodeError, PermissionError, OSError) as e:
            return ValidationResult(
                filepath=filepath,
                is_valid=False,
                errors=[f"Cannot read file: {e}"]
            )
        
        docstring = self.extract_docstring(source)
        
        if docstring is None:
            return ValidationResult(
                filepath=filepath,
                is_valid=False,
                errors=["No module docstring found"]
            )
        
        errors, warnings = self.validate_docstring(docstring, filepath)
        
        return ValidationResult(
            filepath=filepath,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def scan_directory(self, directory: Path) -> List[ValidationResult]:
        """Durchsucht ein Verzeichnis nach Python-Dateien und validiert sie."""
        results = []
        
        if not directory.exists():
            print(f"Warning: Directory does not exist: {directory}", file=sys.stderr)
            return results
        
        for py_file in directory.rglob("*.py"):
            result = self.validate_file(py_file)
            results.append(result)
        
        return results
    
    def print_results(self, results: List[ValidationResult], quiet: bool = False, stats_only: bool = False) -> int:
        """
        Druckt die Validierungsergebnisse.
        
        Returns:
            Anzahl der Dateien mit Fehlern
        """
        total_files = len(results)
        valid_files = sum(1 for r in results if r.is_valid)
        files_with_errors = sum(1 for r in results if len(r.errors) > 0)
        files_with_warnings = sum(1 for r in results if len(r.warnings) > 0)
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)
        
        # Statistik anzeigen
        if not quiet or stats_only:
            print("=" * 80)
            print("📊 DOCSTRING VALIDATION REPORT")
            print("=" * 80)
            print(f"📁 Scanned: {total_files} files")
            print(f"✅ Valid: {valid_files}/{total_files} ({valid_files/total_files*100:.1f}%)")
            print(f"❌ With errors: {files_with_errors}/{total_files} ({files_with_errors/total_files*100:.1f}%)")
            print(f"⚠️  With warnings: {files_with_warnings}/{total_files} ({files_with_warnings/total_files*100:.1f}%)")
            print(f"📝 Total errors: {total_errors}")
            print(f"📝 Total warnings: {total_warnings}")
            print("-" * 80)
        
        # Fehler und Warnungen anzeigen (wenn nicht stats_only)
        if not stats_only:
            # Fehler nach Datei gruppiert
            if files_with_errors > 0:
                print("\n🚨 ERRORS:")
                print("-" * 80)
                for result in sorted(results, key=lambda r: str(r.filepath)):
                    if result.errors:
                        rel_path = str(result.filepath.relative_to(self.base_path))
                        print(f"\n{rel_path}:")
                        for error in result.errors:
                            print(f"  ❌ {error}")
            
            # Warnungen nach Datei gruppiert
            if files_with_warnings > 0:
                print("\n⚠️  WARNINGS:")
                print("-" * 80)
                for result in sorted(results, key=lambda r: str(r.filepath)):
                    if result.warnings:
                        rel_path = str(result.filepath.relative_to(self.base_path))
                        print(f"\n{rel_path}:")
                        for warning in result.warnings:
                            print(f"  ⚠️  {warning}")
        
        if files_with_errors > 0:
            print("\n" + "=" * 80)
            print("❌ VALIDATION FAILED")
            print("=" * 80)
            return 1
        else:
            print("\n" + "=" * 80)
            print("✅ ALL DOCSTRINGS ARE VALID!")
            print("=" * 80)
            return 0
    
    def print_stats_by_tier(self, results: List[ValidationResult]) -> None:
        """Zeigt Statistiken nach @tier-Klassifizierung an."""
        tier_stats: Dict[str, Dict[str, int]] = {}
        
        for result in results:
            if result.errors or result.warnings:
                continue
            
            try:
                source = result.filepath.read_text(encoding='utf-8')
                docstring = self.extract_docstring(source)
                if docstring:
                    info = self.parse_docstring(docstring)
                    tier = info.tier or "unknown"
                    
                    if tier not in tier_stats:
                        tier_stats[tier] = {"total": 0, "valid": 0, "with_errors": 0}
                    
                    tier_stats[tier]["total"] += 1
                    if result.is_valid:
                        tier_stats[tier]["valid"] += 1
                    else:
                        tier_stats[tier]["with_errors"] += 1
            except Exception:
                pass
        
        print("\n📈 STATISTICS BY TIER:")
        print("-" * 80)
        for tier, stats in sorted(tier_stats.items()):
            total = stats["total"]
            valid = stats["valid"]
            errors = stats["with_errors"]
            print(f"  {tier:15} {valid:4}/{total:4} valid ({valid/total*100:5.1f}%) | {errors:4} with errors")
    
    def print_stats_by_category(self, results: List[ValidationResult]) -> None:
        """Zeigt Statistiken nach Verzeichnis an."""
        from collections import defaultdict
        
        category_stats = defaultdict(lambda: {"total": 0, "valid": 0, "with_errors": 0})
        
        for result in results:
            # Extrahiere Kategorie aus Pfad
            rel_path = str(result.filepath.relative_to(self.scripts_dir))
            if rel_path.startswith("compute/"):
                category = "compute"
            elif rel_path.startswith("query/"):
                category = "query"
            elif rel_path.startswith("importers/"):
                category = "importers"
            elif rel_path.startswith("modules/"):
                category = "modules"
            elif rel_path.startswith("utils/"):
                category = "utils"
            else:
                category = "root"
            
            category_stats[category]["total"] += 1
            if result.is_valid:
                category_stats[category]["valid"] += 1
            else:
                category_stats[category]["with_errors"] += 1
        
        print("\n📁 STATISTICS BY CATEGORY:")
        print("-" * 80)
        for category, stats in sorted(category_stats.items()):
            total = stats["total"]
            valid = stats["valid"]
            errors = stats["with_errors"]
            print(f"  {category:15} {valid:4}/{total:4} valid ({valid/total*100:5.1f}%) | {errors:4} with errors")


def main():
    """Hauptfunktion."""
    parser = argparse.ArgumentParser(
        description="Validiert Docstrings in Python-Skripten gegen das Kyoro-HealthHub-Schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python scripts/check_docstrings.py                  # Alle Skripte in scripts/
  python scripts/check_docstrings.py --path scripts/compute  # Nur compute-Skripte
  python scripts/check_docstrings.py --stats         # Nur Statistik anzeigen
  python scripts/check_docstrings.py --quiet         # Nur Fehlerzusammenfassung
        """
    )
    parser.add_argument(
        "--path", "-p",
        type=str,
        default="scripts",
        help="Verzeichnis oder Datei zum Scannen (default: scripts/)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Nur Fehlerzusammenfassung anzeigen"
    )
    parser.add_argument(
        "--stats", "-s",
        action="store_true",
        help="Nur Statistik anzeigen"
    )
    parser.add_argument(
        "--by-tier",
        action="store_true",
        help="Statistik nach @tier anzeigen"
    )
    parser.add_argument(
        "--by-category",
        action="store_true",
        help="Statistik nach Verzeichnis anzeigen"
    )
    
    args = parser.parse_args()
    
    # Initialisiere Validator
    base_path = Path.cwd()
    validator = DocstringValidator(base_path)
    
    # Scanne das angegebene Verzeichnis oder Datei
    scan_path = base_path / args.path
    
    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}", file=sys.stderr)
        sys.exit(2)
    
    # Prüfe ob es eine Datei oder ein Verzeichnis ist
    if scan_path.is_file():
        result = validator.validate_file(scan_path)
        results = [result]
    else:
        results = validator.scan_directory(scan_path)
    
    if not results:
        print(f"No Python files found in: {scan_path}", file=sys.stderr)
        sys.exit(2)
    
    # Sortiere Ergebnisse nach Dateinamen
    results.sort(key=lambda r: str(r.filepath))
    
    # Zeige Ergebnisse an
    exit_code = validator.print_results(results, quiet=args.quiet, stats_only=args.stats)
    
    # Zusätzliche Statistiken
    if args.by_tier and (not args.quiet or args.stats):
        validator.print_stats_by_tier(results)
    
    if args.by_category and (not args.quiet or args.stats):
        validator.print_stats_by_category(results)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
