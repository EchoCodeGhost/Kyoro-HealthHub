#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fhir_mapping.py — FHIR Mapping Utilities

@tier        infrastructure
@purpose.de  Lädt LOINC/SNOMED-Mappings und verwaltet unmapped Metriken für FHIR-Export.
@purpose.en  Loads LOINC/SNOMED mappings and manages unmapped metrics for FHIR export.
@method.de  
  - load_metric_code(): Lädt LOINC-Mapping für eine Metrik
  - track_unmapped(): Verfolgt nicht gemappte Metriken für den Report
  - write_unmapped_report(): Schreibt Report-Datei
@method.en  
  - load_metric_code(): Loads LOINC mapping for a metric
  - track_unmapped(): Tracks unmapped metrics for report
  - write_unmapped_report(): Writes report file
@reads      
  - scripts/exporters/fhir_metric_codes.json
@writes     
  - fhir_export_unmapped_metrics.txt (Report-Datei)
@limits.de  
  - Keine Validierung der Eingabedaten
  - Report wird nur geschrieben, wenn unmapped Metriken vorhanden sind

@relevance.de  Bietet FHIR-Schnittstellen, essentiell für die standardisierte Datenübertragung
@relevance.en  Provides FHIR interfaces, essential for standardized data exchange
@limits.en  
  - No validation of input data
  - Report only written if unmapped metrics exist
@usage
    from scripts.exporters.fhir_mapping import load_metric_code, track_unmapped
    
    metric_code = load_metric_code("heart_rate")
    track_unmapped("unknown_metric", counts)
"""

import json
from pathlib import Path
from typing import Dict, Optional, Set
import sys

# Projektkonvention: Import-Pfad für lokale Module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import KYORO_MASTER_DIR

# Pfad zur Mapping-Datei
MAPPING_FILE = Path(__file__).parent / "fhir_metric_codes.json"

def load_metric_code(metric_name: str) -> Optional[Dict]:
    """
    Lädt das LOINC/SNOMED-Mapping für eine gegebene Metrik.
    
    Args:
        metric_name: Name der Metrik (z.B. "heart_rate")
        
    Returns:
        Mapping-Dict oder None, wenn keine Mapping existiert
    """
    try:
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("mappings", {}).get(metric_name)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load FHIR mappings: {e}")
        return None


def track_unmapped(metric_name: str, unmapped_set: Set[str]) -> None:
    """
    Verfolgt eine nicht gemappte Metrik in einem Set.
    
    Args:
        metric_name: Name der nicht gemappten Metrik
        unmapped_set: Set zum Sammeln unmappter Metriken
    """
    if metric_name and metric_name not in unmapped_set:
        unmapped_set.add(metric_name)


def write_unmapped_report(unmapped_set: Set[str], output_dir: Path) -> bool:
    """
    Schreibt den Report für unmapped Metriken.
    
    Args:
        unmapped_set: Set mit unmappten Metriken
        output_dir: Zielverzeichnis für die Report-Datei
        
    Returns:
        True, wenn Report geschrieben wurde, False wenn keine unmappten Metriken
    """
    if not unmapped_set:
        return False
    
    report_path = output_dir / "fhir_export_unmapped_metrics.txt"
    
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# FHIR Export - Unmapped Metrics Report\n")
            f.write(f"# Generated: {__import__('datetime').datetime.now()}\n")
            f.write("# These metrics were not mapped to LOINC/SNOMED codes in this export.\n")
            f.write("# To add them, verify appropriate codes and extend fhir_metric_codes.json\n\n")
            
            for metric in sorted(unmapped_set):
                f.write(f"- {metric}\n")
        
        print(f"Unmapped metrics report written to: {report_path}")
        return True
    except Exception as e:
        print(f"Error writing unmapped metrics report: {e}")
        return False


if __name__ == "__main__":
    # Beispielnutzung
    print("Testing FHIR Mapping Utilities...")
    
    # Test load_metric_code
    heart_rate_code = load_metric_code("heart_rate")
    print(f"heart_rate mapping: {heart_rate_code}")
    
    unknown_code = load_metric_code("unknown_metric")
    print(f"unknown_metric mapping: {unknown_code}")
    
    # Test track_unmapped
    unmapped = set()
    track_unmapped("unknown_metric", unmapped)
    track_unmapped("another_metric", unmapped)
    print(f"Unmapped metrics: {unmapped}")
    
    # Test write_unmapped_report
    test_dir = Path("/tmp")
    write_unmapped_report(unmapped, test_dir)
    
    print("All tests completed.")