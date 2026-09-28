# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Prompt Library CLI — `python3 -m modules.prompts`

@tier        infrastructure
@purpose.de  Ermöglicht den Aufruf der Prompt-Bibliothek als Modul
             (`python3 -m modules.prompts`), damit alle Prompt-Module vor
             `--list`/`--check` importiert (und damit registriert) werden.
@purpose.en  Allows invoking the prompt library as a module
             (`python3 -m modules.prompts`), so all prompt modules are
             imported (and thus registered) before `--list`/`--check` run.
@method.de   Importiert alle bekannten Prompt-Untermodule (aktuell nur
             `query`), ruft dann `modules.prompts.main()` auf.
@method.en   Imports all known prompt submodules (currently only `query`),
             then calls `modules.prompts.main()`.
@relevance.de  Reiner CLI-Einstiegspunkt, keine eigene Logik.
@relevance.en  Pure CLI entry point, no logic of its own.
@reads       keine
@writes      keine
@limits.de   Muss um jedes neue Prompt-Untermodul (z.B. `analysis_*`)
             manuell erweitert werden, sonst werden dessen Prompts bei
             `--list`/`--check` nicht erfasst.
@limits.en   Must be manually extended for every new prompt submodule
             (e.g. `analysis_*`), otherwise its prompts won't be picked up
             by `--list`/`--check`.
@usage
    python3 -m modules.prompts --list
    python3 -m modules.prompts --check
"""

# Import all prompt modules to ensure registration
from modules.prompts import query
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
from modules.prompts import main

if __name__ == "__main__":
    main()
