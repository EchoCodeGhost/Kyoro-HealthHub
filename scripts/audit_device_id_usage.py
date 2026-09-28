#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
audit_device_id_usage.py — Semantische Identifier-Nutzung prüfen

@tier        infrastructure
@purpose.de  Durchsucht den Quellcode nach direkten semantischen device_id- und
             person-Vergleichen, die für die Pseudonymisierung aktualisiert werden müssen.
@purpose.en  Scans source code for direct semantic device_id and person comparisons that
             need to be updated for pseudonymization.
@method.de   Regex-basierte Suche nach Mustern wie device_id=="polar_v3", 'self', 'partner'
             in Python-Dateien. Gibt Fundstellen mit Datei/Zeile aus.
@method.en   Regex-based search for patterns like device_id=="polar_v3", 'self', 'partner'
             in Python files. Reports findings with file/line.
@reads       scripts/compute/, scripts/importers/, scripts/analysis/, scripts/exporters/
@writes      Keine (nur Konsolenausgabe)
@limits.de   Falsch-positive bei Kommentaren/Dokumentation möglich. Keine automatische
             Korrektur — nur Berichterstellung.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   False positives possible in comments/documentation. No automatic fixes —
             reporting only.
@usage
    python3 scripts/audit_device_id_usage.py
    python3 scripts/audit_device_id_usage.py > audit_results.txt
"""

import os
import re
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories to search
SEARCH_DIRS = [
    "scripts/compute",
    "scripts/importers",
    "scripts/analysis",
    "scripts/exporters",
    "scripts/utils",
]

# Patterns to look for
PATTERNS = {
    "device_id_comparison": r'device_id\s*[!=]==\s*["\'].*["\']',
    "device_literal": r'["\'](polar_v3|polar_h10|polar_h7|polar_vantage|polar_loop|polar_m430|polar_ignite2|apple_watch|garmin_fenix|oura_4)["\']',
    "person_literal": r'["\'](self|partner)["\']',
    "algo_routing": r'ALGO_ROUTING',
    "device_timeline": r'_polar_device_for_date|DEVICE_H10|DEVICE_V3',
    "confidence_dict": r'CONFIDENCE\s*=',
}

def find_matches():
    """Find all matches for the patterns."""
    results = defaultdict(list)
    
    for search_dir in SEARCH_DIRS:
        full_dir = REPO_ROOT / search_dir
        if not full_dir.exists():
            continue
            
        for file_path in full_dir.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for pattern_name, pattern in PATTERNS.items():
                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            results[pattern_name].append({
                                'file': str(file_path.relative_to(REPO_ROOT)),
                                'line': line_num,
                                'content': line.strip()
                            })
            except (UnicodeDecodeError, PermissionError):
                continue
    
    return results

def print_results(results):
    """Print the audit results."""
    print("=== Device/Person Identifier Audit Results ===\n")
    
    for pattern_name, matches in results.items():
        if matches:
            print(f"\n{pattern_name.upper().replace('_', ' ')}:")
            print(f"Found {len(matches)} occurrences:")
            for match in matches:
                print(f"  {match['file']}:{match['line']}")
                print(f"    {match['content']}")
        else:
            print(f"\n{pattern_name.upper().replace('_', ' ')}: No matches found")
    
    print(f"\n=== Summary ===")
    total_matches = sum(len(matches) for matches in results.values())
    print(f"Total patterns found: {total_matches}")
    
    # Specific recommendations
    print(f"\n=== Migration Recommendations ===")
    
    if results['device_id_comparison']:
        print("✗ Found direct device_id string comparisons - these will break with pseudonyms")
        print("  → Replace with sensor_type lookup via identity_resolver")
    else:
        print("✓ No direct device_id string comparisons found")
    
    if results['device_literal']:
        print("✗ Found hardcoded device literals - these should use identity_resolver")
        print("  → Replace with resolve_device() calls")
    else:
        print("✓ No hardcoded device literals found")
    
    if results['person_literal']:
        print("✗ Found hardcoded person literals - these should use identity_resolver")
        print("  → Replace with resolve_person() calls")
    else:
        print("✓ No hardcoded person literals found")
    
    if results['algo_routing']:
        print("✓ ALGO_ROUTING found - this needs to be updated to use sensor_type instead of device_id")
    
    if results['device_timeline']:
        print("✓ Polar device timeline functions found - these need sensor_type updates")
    
    if results['confidence_dict']:
        print("✓ CONFIDENCE dict found - check if it uses device-specific keys that need updating")

if __name__ == "__main__":
    results = find_matches()
    print_results(results)