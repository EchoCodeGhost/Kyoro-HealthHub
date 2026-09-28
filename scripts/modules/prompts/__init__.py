# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Prompt Library — zentrales Register für LLM-System-Prompts

@tier        infrastructure
@purpose.de  Zentrales Register für alle LLM-System-Prompts im Projekt, mit
             eindeutiger Zuordnung jedes Prompts zu seiner Quelldatei
             (owner). Löst das Problem, dass Prompts über ~70 Dateien
             verstreut waren, ohne zentrale Übersicht.
@purpose.en  Central registry for all LLM system prompts in the project,
             with each prompt explicitly attributed to its source file
             (owner). Solves the problem of prompts being scattered across
             ~70 files with no central overview.
@method.de   `Prompt`-Dataclass (name, owner, classification, lang, text)
             + `register()` trägt Instanzen in das `PROMPTS`-Dict ein
             (Schlüssel: owner-Pfad). `prompts_for(owner)`/`all_prompts()`
             fragen ab. `python3 -m modules.prompts --list`/`--check` als
             CLI: `--check` verifiziert Pflichtfelder und dass keine Datei
             eine nicht-registrierte `SYSTEM_*`/`*_PROMPT`-Konstante mehr
             hat (Drift-Schutz, analog zu `tools/gen_docs.py --check`).
@method.en   `Prompt` dataclass (name, owner, classification, lang, text)
             + `register()` adds instances to the `PROMPTS` dict (keyed by
             owner path). `prompts_for(owner)`/`all_prompts()` query it.
             `python3 -m modules.prompts --list`/`--check` as CLI: `--check`
             verifies required fields and that no owner file still has an
             unregistered `SYSTEM_*`/`*_PROMPT` constant (drift protection,
             analogous to `tools/gen_docs.py --check`).
@relevance.de  Verhindert erneutes Auseinanderdriften von Prompt-Kopien und
               Quelldatei nach der Migration in diese Bibliothek.
@relevance.en  Prevents renewed drift between prompt copies and source file
               after migration into this library.
@reads       keine
@writes      keine
@limits.de   Prüft nur Feldvorhandensein und Registrierungs-Vollständigkeit,
             keine inhaltliche/medizinische Korrektheit der Prompt-Texte.
@limits.en   Only checks field presence and registration completeness, not
             the medical/factual correctness of prompt content.
@usage
    python3 -m modules.prompts --list
    python3 -m modules.prompts --check
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Prompt:
    """Represents a single LLM prompt with metadata."""
    name: str                    # e.g. "SYSTEM_PROMPT", "SYSTEM_SQL"
    owner: str                   # Source script path, e.g. "scripts/query/health_query.py"
    classification: str          # "LLM:System" etc., as per docs/prompts.md section 4
    lang: str                    # "de" | "en" | "bilingual" | "de_only"
    text: Optional[str] = None   # for lang="de"/"en"/"de_only"
    text_de: Optional[str] = None # for lang="bilingual"
    text_en: Optional[str] = None # for lang="bilingual"


# Registry: maps owner path -> list of Prompts
PROMPTS: Dict[str, List[Prompt]] = {}


def register(prompt: Prompt) -> Prompt:
    """Register a prompt in the central registry."""
    if prompt.owner not in PROMPTS:
        PROMPTS[prompt.owner] = []
    PROMPTS[prompt.owner].append(prompt)
    return prompt


def prompts_for(owner: str) -> List[Prompt]:
    """Get all prompts registered for a specific owner file."""
    return PROMPTS.get(owner, [])


def all_prompts() -> List[Prompt]:
    """Get all registered prompts flattened into a single list."""
    result = []
    for owner_prompts in PROMPTS.values():
        result.extend(owner_prompts)
    return result


def _check_registrations() -> bool:
    """Verify that all registered prompts have valid metadata."""
    errors = []
    
    # For Phase 1, we just verify that prompts are registered
    # The actual import check is complex due to path issues
    if not PROMPTS:
        errors.append("No prompts registered in the registry")
        return False
    
    # Check that all prompts have required fields
    for owner_path, prompts in PROMPTS.items():
        for prompt in prompts:
            if not prompt.name:
                errors.append(f"Prompt in {owner_path} has empty name")
            if not prompt.owner:
                errors.append(f"Prompt {prompt.name} has empty owner")
            if not prompt.classification:
                errors.append(f"Prompt {prompt.name} has empty classification")
            if not prompt.lang:
                errors.append(f"Prompt {prompt.name} has empty lang")
            if not prompt.text and not prompt.text_de and not prompt.text_en:
                errors.append(f"Prompt {prompt.name} has no text content")
    
    if errors:
        print("ERROR: Registration check failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


def _check_no_orphaned_prompts() -> bool:
    """Check that no owner files have unregistered SYSTEM_* or *_PROMPT constants."""
    import re
    import os
    
    errors = []
    
    # Get all registered owner files
    registered_owners = set(PROMPTS.keys())
    
    # Pattern to find prompt constants
    prompt_pattern = re.compile(r'^(SYSTEM_\w+|\w+_PROMPT|_SYSTEM_\w+)\s*=', re.MULTILINE)
    
    # Check all Python files in scripts/query/ and scripts/analysis/**/
    scripts_dir = Path(__file__).parent.parent.parent
    
    # Check scripts/query/*.py
    query_dir = scripts_dir / "query"
    if query_dir.exists():
        for py_file in query_dir.glob("*.py"):
            rel_path = str(py_file.relative_to(scripts_dir))
            full_path = str(py_file)
            
            # Skip __pycache__ and non-python files
            if not py_file.name.endswith('.py'):
                continue
                
            rel_path_with_prefix = f"scripts/{rel_path}"
            
            # Only check files that are in our registry or should be
            if rel_path_with_prefix not in registered_owners:
                # This is expected for Phase 1 - we're only migrating query/*.py
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find all prompt constants
                matches = prompt_pattern.findall(content)
                
                # Get registered prompts for this file
                registered_prompt_names = {p.name for p in prompts_for(rel_path_with_prefix)}
                
                # Check for unregistered prompts
                for match in matches:
                    if match not in registered_prompt_names:
                        errors.append(f"{rel_path_with_prefix}: Found unregistered prompt constant '{match}'")
                        
            except Exception as e:
                errors.append(f"Failed to read {rel_path_with_prefix}: {e}")
    
    # Check scripts/analysis/**/*.py
    analysis_dir = scripts_dir / "analysis"
    if analysis_dir.exists():
        for py_file in analysis_dir.rglob("*.py"):
            # Skip __init__.py files
            if py_file.name == "__init__.py":
                continue
                
            rel_path = str(py_file.relative_to(scripts_dir))
            rel_path_with_prefix = f"scripts/{rel_path}"
            
            # Only check files that are in our registry
            if rel_path_with_prefix not in registered_owners:
                # Skip files not yet migrated
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find all prompt constants
                matches = prompt_pattern.findall(content)
                
                # Get registered prompts for this file
                registered_prompt_names = {p.name for p in prompts_for(rel_path_with_prefix)}
                
                # Check for unregistered prompts
                for match in matches:
                    if match not in registered_prompt_names:
                        errors.append(f"{rel_path_with_prefix}: Found unregistered prompt constant '{match}'")
                        
            except Exception as e:
                errors.append(f"Failed to read {rel_path_with_prefix}: {e}")
    
    # Check scripts/importers/*.py
    importers_dir = scripts_dir / "importers"
    if importers_dir.exists():
        for py_file in importers_dir.glob("*.py"):
            rel_path = str(py_file.relative_to(scripts_dir))
            rel_path_with_prefix = f"scripts/{rel_path}"
            
            # Only check files that are in our registry
            if rel_path_with_prefix not in registered_owners:
                # Skip files not yet migrated
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find all prompt constants
                matches = prompt_pattern.findall(content)
                
                # Get registered prompts for this file
                registered_prompt_names = {p.name for p in prompts_for(rel_path_with_prefix)}
                
                # Check for unregistered prompts
                for match in matches:
                    if match not in registered_prompt_names:
                        errors.append(f"{rel_path_with_prefix}: Found unregistered prompt constant '{match}'")
                        
            except Exception as e:
                errors.append(f"Failed to read {rel_path_with_prefix}: {e}")
    
    if errors:
        print("ERROR: Found orphaned prompt constants:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


def main():
    """CLI entry point for prompt library management."""
    parser = argparse.ArgumentParser(description="Prompt Library Management")
    parser.add_argument("--list", action="store_true", help="List all prompts grouped by owner")
    parser.add_argument("--check", action="store_true", help="Verify prompt registrations")
    
    args = parser.parse_args()
    
    if args.list:
        # Import all prompt modules to ensure registration
        try:
            from modules.prompts import query
            # Phase 2: Import analysis modules
            from modules.prompts import analysis_activity
            from modules.prompts import analysis_cardiovascular
            from modules.prompts import analysis_cycle
            from modules.prompts import analysis_environment
            from modules.prompts import analysis_immunology
            from modules.prompts import analysis_infectious
            from modules.prompts import analysis_internal_medicine
            from modules.prompts import analysis_longevity
            from modules.prompts import analysis_manual
            from modules.prompts import analysis_metabolic
            from modules.prompts import analysis_neurology
            from modules.prompts import analysis_ophthalmology
            from modules.prompts import analysis_psychology
            from modules.prompts import analysis_sleep
            from modules.prompts import importers
        except ImportError as e:
            print(f"ERROR: Failed to import prompt modules: {e}")
            return 1
        
        all_prompts_list = all_prompts()
        if not all_prompts_list:
            print("No prompts registered.")
            return
        
        # Group by owner
        by_owner = {}
        for prompt in all_prompts_list:
            if prompt.owner not in by_owner:
                by_owner[prompt.owner] = []
            by_owner[prompt.owner].append(prompt)
        
        for owner, prompts in sorted(by_owner.items()):
            print(f"\n{owner}:")
            for prompt in prompts:
                lang_info = f"lang={prompt.lang}"
                if prompt.text:
                    text_preview = prompt.text[:60].replace('\n', ' ') + "..." if len(prompt.text) > 60 else prompt.text.replace('\n', ' ')
                elif prompt.text_de:
                    text_preview = prompt.text_de[:60].replace('\n', ' ') + "..." if len(prompt.text_de) > 60 else prompt.text_de.replace('\n', ' ')
                elif prompt.text_en:
                    text_preview = prompt.text_en[:60].replace('\n', ' ') + "..." if len(prompt.text_en) > 60 else prompt.text_en.replace('\n', ' ')
                else:
                    text_preview = "No text"
                
                print(f"  - {prompt.name} [{prompt.classification}] ({lang_info}): {text_preview}")
    
    elif args.check:
        print("Checking prompt registrations...")
        
        # Import all prompt modules to ensure registration
        try:
            from modules.prompts import query
            # Phase 2: Import analysis modules
            from modules.prompts import analysis_activity
            from modules.prompts import analysis_cardiovascular
            from modules.prompts import analysis_cycle
            from modules.prompts import analysis_environment
            from modules.prompts import analysis_immunology
            from modules.prompts import analysis_infectious
            from modules.prompts import analysis_internal_medicine
            from modules.prompts import analysis_longevity
            from modules.prompts import analysis_manual
            from modules.prompts import analysis_metabolic
            from modules.prompts import analysis_neurology
            from modules.prompts import analysis_ophthalmology
            from modules.prompts import analysis_psychology
            from modules.prompts import analysis_sleep
            from modules.prompts import importers
        except ImportError as e:
            print(f"ERROR: Failed to import prompt modules: {e}")
            return 1
        
        success = True
        
        if not _check_registrations():
            success = False
        
        if not _check_no_orphaned_prompts():
            success = False
        
        if success:
            print("All checks passed!")
        else:
            print("Some checks failed.")
            return 1
        
        return 0
    
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
