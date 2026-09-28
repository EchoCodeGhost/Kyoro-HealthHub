#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
recalibrate.py — Source-Confidence-Scores manuell neu kalibrieren

@tier        infrastructure
@purpose.de  Koordiniert die Neukalibrierung der Source-Confidence-Scores durch
             Ausführung von compute_calibrate_sources.py und compute_canonical.py.
             Ermöglicht die interaktive Prüfung der Kalibrierungsergebnisse vor der Anwendung.
@purpose.en  Coordinates recalibration of source confidence scores by running
             compute_calibrate_sources.py and compute_canonical.py.
             Allows interactive review of calibration results before applying.
@method.de   Führt zwei Schritte aus: 1) compute_calibrate_sources.py (Pearson-r vs. Anker,
             Blend mit Literatur-Score), 2) compute_canonical.py (Golden Records neu berechnen).
             Bewusst nicht in compute_all.py integriert, da Kalibrierung eine Designentscheidung ist.
@method.en   Executes two steps: 1) compute_calibrate_sources.py (Pearson-r vs anchor,
             blend with literature score), 2) compute_canonical.py (recompute golden records).
             Intentionally not integrated in compute_all.py as calibration is a design decision.
@reads       Keine direkten Tabellen (koordiniert andere Skripte)
@writes      Quelle: source_confidence (über compute_calibrate_sources.py),
             sessions, measurements, canonical Daten (über compute_canonical.py)
@limits.de   Kalibrierung ist eine Designentscheidung. Ergebnisse sollten vor der Anwendung
             manuell geprüft werden. Keine automatische Validierung.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Calibration is a design decision. Results should be manually reviewed before
             applying. No automatic validation.
@usage
    python3 scripts/recalibrate.py             # interaktiv: Report zeigen, dann fragen
    python3 scripts/recalibrate.py --yes       # direkt durchlaufen ohne Bestätigung
    python3 scripts/recalibrate.py --dry-run   # nur Report, keine Änderungen
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent


def run(cmd: list[str]) -> int:
    result = subprocess.run(cmd, cwd=SCRIPTS.parent)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Source-Confidence neu kalibrieren")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Ohne Bestätigungsprompt durchlaufen")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur Report, keine DB-Änderungen")
    args = parser.parse_args()

    calibrate_cmd = [sys.executable, str(SCRIPTS / "compute/compute_calibrate_sources.py")]
    canonical_cmd = [sys.executable, str(SCRIPTS / "compute/compute_canonical.py")]

    if args.dry_run:
        print("DRY-RUN — keine Änderungen\n")
        run(calibrate_cmd + ["--dry-run"])
        return

    print("── Schritt 1: Kalibrierung ─────────────────────────────────")
    run(calibrate_cmd + ["--dry-run"])

    if not args.yes:
        print("\nScores übernehmen und health_canonical neu berechnen? [j/N] ", end="", flush=True)
        antwort = input().strip().lower()
        if antwort not in ("j", "ja", "y", "yes"):
            print("Abgebrochen.")
            return

    print("\n── Schritt 2: Kalibrierung schreiben ──────────────────────")
    rc = run(calibrate_cmd)
    if rc != 0:
        print(f"Fehler in compute_calibrate_sources (exit {rc}). Abbruch.")
        sys.exit(rc)

    print("\n── Schritt 3: health_canonical neu berechnen ───────────────")
    rc = run(canonical_cmd)
    if rc != 0:
        print(f"Fehler in compute_canonical (exit {rc}).")
        sys.exit(rc)

    print("\nFertig. health_canonical enthält jetzt die kalibrierten Scores.")


if __name__ == "__main__":
    main()
