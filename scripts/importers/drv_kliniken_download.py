#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
DRV-Reha-Kliniken → HTML-Download

@tier        infrastructure
@purpose.de  Lädt die Standortübersicht der Reha-Kliniken der Deutschen
             Rentenversicherung (drv-reha.de/kliniken) als HTML-Datei herunter.
@purpose.en  Downloads the clinic location overview of the German pension
             insurance (drv-reha.de/kliniken) as an HTML file.
@method.de   Ruft die Seite per wget ab und speichert sie unverändert unter
             imports/drv-kliniken/kliniken. Enthält keine Parsing-Logik —
             das Auswerten der Klinikliste ist Aufgabe eines nachgelagerten
             Importers.
@method.en   Fetches the page via wget and stores it unchanged under
             imports/drv-kliniken/kliniken. Contains no parsing logic —
             turning the clinic list into structured data is the job of a
             downstream importer.
@reads       https://www.drv-reha.de/kliniken (online)
@writes      imports/drv-kliniken/kliniken (Roh-HTML)
@limits.de   Benötigt eine funktionierende wget-Installation und Internetzugang.
             Erkennt keine Layout-Änderungen der Zielseite.
@limits.en   Requires a working wget installation and internet access.
             Does not detect layout changes on the target page.

@relevance.de  Beschafft Rohdaten für die Reha-Planung, kein direkter Bezug zu
               persönlichen Gesundheitsdaten
@relevance.en  Fetches raw data for rehabilitation planning, no direct relevance
               to personal health data
@usage
    python3 drv_kliniken_download.py
    python3 drv_kliniken_download.py --help
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t

URL = "https://www.drv-reha.de/kliniken"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "imports" / "drv-kliniken"
OUTPUT_FILE = OUTPUT_DIR / "kliniken"


def main() -> int:
    if not shutil.which("wget"):
        print(t("wget ist nicht installiert.", "wget is not installed."))
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["wget", "-O", str(OUTPUT_FILE), URL])
    if result.returncode != 0:
        print(t(f"Download fehlgeschlagen (Exit-Code {result.returncode}).",
                f"Download failed (exit code {result.returncode})."))
        return result.returncode

    print(t(f"Gespeichert: {OUTPUT_FILE}", f"Saved: {OUTPUT_FILE}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
