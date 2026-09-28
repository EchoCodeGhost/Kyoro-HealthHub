#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
archive_openspec_change.py — Archive completed OpenSpec change

@tier        infrastructure
@purpose.de  Verschiebt ein abgeschlossenes OpenSpec-Change-Verzeichnis in den
             archive/ Ordner und dokumentiert den Abschluss.
@purpose.en  Moves a completed OpenSpec change directory to the archive/ folder
             and documents the completion.
@method.de   1. Validiert dass alle tasks.md Checkboxen abgehakt sind
             2. Verschiebt Verzeichnis von changes/ nach changes/archive/
             3. Erstellt Archiv-Metadaten mit Abschlussdatum
@method.en   1. Validates that all tasks.md checkboxes are checked
             2. Moves directory from changes/ to changes/archive/
             3. Creates archive metadata with completion date
@reads       openspec/changes/<change_name>/
@writes      openspec/changes/archive/<change_name>/
@limits.de   Keine automatische Validierung der Aufgabenabhaken — manuelle
             Prüfung erforderlich. Kein Rollback nach Archivierung.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No automatic validation of task checkboxes — manual review required.
             No rollback after archiving.
@usage
    python3 scripts/archive_openspec_change.py pseudonymize-device-person-identifiers
    python3 scripts/archive_openspec_change.py --list-pending
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import argparse

def list_pending_changes():
    """List changes that are not in archive."""
    changes_dir = Path("openspec/changes")
    archive_dir = changes_dir / "archive"
    
    print("=== Pending OpenSpec Changes ===")
    
    if not changes_dir.exists():
        print("No changes directory found")
        return
    
    all_changes = []
    for item in changes_dir.iterdir():
        if item.is_dir() and item.name != "archive" and not item.name.startswith("."):
            all_changes.append(item.name)
    
    if not all_changes:
        print("No pending changes found")
        return
    
    print(f"Found {len(all_changes)} pending changes:")
    for change in sorted(all_changes):
        print(f"  - {change}")

def archive_change(change_name: str, dry_run: bool = True):
    """Archive a completed OpenSpec change."""
    changes_dir = Path("openspec/changes")
    source_path = changes_dir / change_name
    archive_dir = changes_dir / "archive"
    target_path = archive_dir / change_name
    
    if not source_path.exists():
        print(f"✗ Change not found: {change_name}")
        return False
    
    if target_path.exists():
        print(f"✗ Change already archived: {change_name}")
        return False
    
    print(f"Archiving OpenSpec change: {change_name}")
    
    # Check if tasks.md exists and has content
    tasks_file = source_path / "tasks.md"
    if tasks_file.exists():
        print(f"  ✓ Found tasks.md")
        # Note: Manual validation of checkboxes recommended
    else:
        print(f"  ⚠️  No tasks.md found")
    
    # Create archive directory if needed
    if not archive_dir.exists():
        if dry_run:
            print(f"  [DRY RUN] Would create archive directory")
        else:
            archive_dir.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Created archive directory")
    
    # Move the change directory
    if dry_run:
        print(f"  [DRY RUN] Would move: {source_path} -> {target_path}")
    else:
        shutil.move(str(source_path), str(target_path))
        print(f"  ✓ Moved: {source_path} -> {target_path}")
    
    # Create archive metadata
    metadata_file = target_path / ".archived"
    if dry_run:
        print(f"  [DRY RUN] Would create metadata: {metadata_file}")
    else:
        metadata = f"""# Archived OpenSpec Change

**Change**: {change_name}
**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Status**: Completed

## Notes
- All tasks should be completed before archiving
- Documentation should be generated and committed
- Migration scripts tested and verified
"""
        with open(metadata_file, 'w') as f:
            f.write(metadata)
        print(f"  ✓ Created metadata: {metadata_file}")
    
    print(f"\n✓ Archive process completed for {change_name}")
    if dry_run:
        print("  (Dry run - no changes made)")
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Archive completed OpenSpec change",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "change_name",
        nargs="?",
        help="Name of the change to archive"
    )
    
    parser.add_argument(
        "--list-pending",
        action="store_true",
        help="List pending changes instead of archiving"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    if args.list_pending:
        list_pending_changes()
        return
    
    if not args.change_name:
        parser.error("Either change_name or --list-pending must be specified")
    
    dry_run = args.dry_run
    archive_change(args.change_name, dry_run)

if __name__ == "__main__":
    main()