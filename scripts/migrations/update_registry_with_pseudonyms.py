#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
update_registry_with_pseudonyms.py — Geräte-Registry mit Pseudonymen aktualisieren

@tier        infrastructure
@purpose.de  Aktualisiert die device_registry in registry.json, um Pseudonyme statt
             semantischer device_ids und person-Werte zu verwenden. Sollte NACH der
             Datenbank-Migration ausgeführt werden, um Konsistenz sicherzustellen.
@purpose.en  Updates the device_registry in registry.json to use pseudonyms instead of
             semantic device_ids and person values. Should be run AFTER the database
             migration to ensure consistency.
@method.de   1. Liest registry.json
             2. Ersetzt alle semantischen device_id-Werte durch Pseudonyme
             3. Ersetzt alle semantischen person-Werte durch Pseudonyme
             4. Speichert aktualisierte Registry (nur bei --execute)
@method.en   1. Reads registry.json
             2. Replaces all semantic device_id values with pseudonyms
             3. Replaces all semantic person values with pseudonyms
             4. Saves updated registry (only with --execute)
@reads       ~/.config/kyoro/registry.json
@writes      ~/.config/kyoro/registry.json (aktualisierte device_registry)
@limits.de   Überschreibt bestehende Werte; keine automatische Sicherung. Vorhandene
             Pseudonyme (DEV-*, PER-*) werden ignoriert.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Overwrites existing values; no automatic backup. Existing pseudonyms
             (DEV-*, PER-*) are ignored.
@usage
    python3 scripts/migrations/update_registry_with_pseudonyms.py --dry-run
    python3 scripts/migrations/update_registry_with_pseudonyms.py --execute
"""

import json
import sys
from pathlib import Path
import argparse

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from modules.identity_resolver import resolve_device, resolve_person

def update_registry_with_pseudonyms(dry_run: bool = True) -> int:
    """Update registry.json with pseudonyms."""
    
    registry_path = Path("~/.config/kyoro/registry.json").expanduser()
    
    if not registry_path.exists():
        print(f"✗ Registry file not found: {registry_path}")
        return 0
    
    # Load registry
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    if 'device_registry' not in registry:
        print("✗ No device_registry found in registry.json")
        return 0
    
    updates_made = 0
    
    print(f"Updating device_registry in {registry_path}")
    print(f"Found {len(registry['device_registry'])} devices")
    
    for device in registry['device_registry']:
        original_device_id = device.get('device_id')
        
        if not original_device_id:
            continue
        
        # Skip if already a pseudonym
        if original_device_id.startswith('DEV-'):
            continue
        
        try:
            # Generate pseudonym
            pseudonym = resolve_device(original_device_id)
            
            if dry_run:
                print(f"  [DRY RUN] {original_device_id} -> {pseudonym}")
            else:
                device['device_id'] = pseudonym
                updates_made += 1
                print(f"  [UPDATED] {original_device_id} -> {pseudonym}")
                
        except Exception as e:
            print(f"  [ERROR] {original_device_id} -> {e}")
    
    # Update person fields if they exist
    for device in registry['device_registry']:
        person_value = device.get('person')
        
        if not person_value:
            continue
        
        # Skip if already a pseudonym
        if person_value.startswith('PER-'):
            continue
        
        try:
            # Generate pseudonym
            pseudonym = resolve_person(person_value)
            
            if dry_run:
                print(f"  [DRY RUN] person:{person_value} -> {pseudonym}")
            else:
                device['person'] = pseudonym
                updates_made += 1
                print(f"  [UPDATED] person:{person_value} -> {pseudonym}")
                
        except Exception as e:
            print(f"  [ERROR] person:{person_value} -> {e}")
    
    # Save if not dry run
    if not dry_run and updates_made > 0:
        with open(registry_path, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved updated registry to {registry_path}")
    
    return updates_made

def main():
    parser = argparse.ArgumentParser(
        description="Update registry.json with pseudonymized device_ids and person values",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/migrations/update_registry_with_pseudonyms.py --dry-run
  python3 scripts/migrations/update_registry_with_pseudonyms.py --execute
        """
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be changed without making changes"
    )
    
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the update (make actual changes)"
    )
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        parser.error("Either --dry-run or --execute must be specified")
    
    if args.dry_run and args.execute:
        parser.error("Cannot specify both --dry-run and --execute")
    
    dry_run = args.dry_run
    execute = args.execute
    
    print("=== Update Registry with Pseudonyms ===\n")
    
    updates = update_registry_with_pseudonyms(dry_run)
    
    print(f"\n=== Summary ===")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"Updates made: {updates}")
    
    if dry_run:
        print("\n✓ Dry run completed successfully. No changes were made.")
        print("  To execute the update, run with --execute")
    else:
        if updates > 0:
            print(f"\n✓ Registry updated with {updates} pseudonyms")
        else:
            print("\n✓ No updates needed (already using pseudonyms or no changes)")

if __name__ == "__main__":
    main()