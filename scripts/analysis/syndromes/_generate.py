#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Syndrom-Konfiguration Generator

@tier        infrastructure
@purpose.de  Generiert Syndrom-Konfigurationsdateien aus der Quelldatei
@purpose.en  Generates syndrome configuration files from source file
@method.de   Einmaliges Migrationsskript: Liest SYNDROME_CONFIG, SYNDROME_CODES, SYNDROME_SERO
             und _AFES_CONTEXT aus dem Elternskript (ohne Import, um Nebenwirkungen zu vermeiden),
             und schreibt eine JSON-Datei pro Syndrom plus _afes_context.txt.
@method.en   One-shot migration script: reads SYNDROME_CONFIG, SYNDROME_CODES, SYNDROME_SERO
             and _AFES_CONTEXT from the parent script (without importing it, to avoid side-effects),
             then writes one JSON file per syndrome plus _afes_context.txt.
@reads       analyse_postinfectious_diagnose.py (Quelldatei)
@writes      JSON-Dateien pro Syndrom in scripts/analysis/syndromes/
@limits.de   Einmalige Ausfuehrung. Keine automatische Aktualisierung. Bereits
             durchgeführt — die JSON-Dateien in diesem Ordner sind seither die
             Quelle der Wahrheit, `analyse_postinfectious_diagnose.py` liest sie
             zur Laufzeit ein (`_load_syndromes()`) statt sie hartzucodieren.
             Erneutes Ausführen würde versuchen, aus der (nicht mehr vorhandenen)
             literalen Dict-Zuweisung zu lesen und bricht deshalb absichtlich mit
             einer klaren Fehlermeldung ab, statt die JSON-Dateien stillschweigend
             zu überschreiben oder zu beschädigen.

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@limits.en   One-time execution. No automatic updates. Already performed — the
             JSON files in this folder are the source of truth since the
             migration; `analyse_postinfectious_diagnose.py` loads them at
             runtime (`_load_syndromes()`) instead of hardcoding them. Running
             this again would try to read the (no longer present) literal dict
             assignment and therefore aborts deliberately with a clear error
             instead of silently overwriting or corrupting the JSON files.
@usage
    python3 scripts/analysis/syndromes/_generate.py
    python3 _generate.py  # from scripts/analysis/syndromes/ directory
"""

import json
import re
import sys
from pathlib import Path

# ── Locate files ─────────────────────────────────────────────────────────────
HERE    = Path(__file__).parent          # scripts/analysis/syndromes/
SRC     = HERE.parent / "infectious" / "analyse_postinfectious_diagnose.py"
OUT_DIR = HERE

# Migration already happened: the JSON files below are now the source of
# truth (analyse_postinfectious_diagnose.py loads them via _load_syndromes()
# at runtime). Running this generator again would try to extract a literal
# SYNDROME_CONFIG = {...} assignment that no longer exists in the source —
# refuse explicitly, checked BEFORE the source-file lookup below so this
# message always wins over an unrelated "source not found" (e.g. after the
# source file moves to a new subfolder), rather than being masked by it.
_existing = sorted(p.name for p in OUT_DIR.glob("*.json"))
if _existing:
    sys.exit(
        "Migration already done — refusing to run again.\n"
        f"{len(_existing)} syndrome JSON file(s) already exist in {OUT_DIR}, "
        "and analyse_postinfectious_diagnose.py now loads syndrome data FROM "
        "these files (_load_syndromes()), not the other way around. They are "
        "the source of truth; edit them directly instead of regenerating.\n"
        "If you really need to redo the migration (e.g. restoring from an "
        "older commit that still has the hardcoded dicts), delete or move "
        "the existing JSON files first, deliberately."
    )

if not SRC.exists():
    sys.exit(f"Source not found: {SRC}")

source = SRC.read_text(encoding="utf-8")

# ── Extract the four blocks via exec() in a sandboxed namespace ───────────────
# Strategy: extract each top-level assignment by scanning from the variable name
# to the line where bracket depth returns to zero.

def extract_block(src: str, varname: str) -> str:
    """Return the complete assignment statement for `varname = ...` from src."""
    pattern = re.compile(r'^' + re.escape(varname) + r'\s*=\s*', re.MULTILINE)
    m = pattern.search(src)
    if not m:
        raise ValueError(f"Variable {varname!r} not found in source")
    start = m.start()
    rest = src[start:]
    lines = rest.split('\n')
    depth_curly  = 0
    depth_triple = False
    result_lines = []
    first = True
    for line in lines:
        result_lines.append(line)
        # Track triple-quote strings (toggle)
        tq_count = line.count('"""')
        if tq_count % 2 == 1:
            depth_triple = not depth_triple
        if not depth_triple:
            depth_curly += line.count('{') - line.count('}')
        if not first and depth_curly <= 0 and not depth_triple:
            break
        first = False
    return '\n'.join(result_lines)


ns: dict = {}

afes_block   = extract_block(source, "_AFES_CONTEXT")
config_block = extract_block(source, "SYNDROME_CONFIG")
codes_block  = extract_block(source, "SYNDROME_CODES")
sero_block   = extract_block(source, "SYNDROME_SERO")

combined = "\n".join([afes_block, config_block, codes_block, sero_block])
exec(compile(combined, "<generated>", "exec"), ns)  # noqa: S102

_AFES_CONTEXT: str  = ns["_AFES_CONTEXT"]
SYNDROME_CONFIG: dict = ns["SYNDROME_CONFIG"]
SYNDROME_CODES:  dict = ns["SYNDROME_CODES"]
SYNDROME_SERO:   dict = ns["SYNDROME_SERO"]

# Sanity check
all_slugs = sorted(SYNDROME_CONFIG.keys())
print(f"Found {len(all_slugs)} syndromes: {', '.join(all_slugs)}")

# ── Write _afes_context.txt ───────────────────────────────────────────────────
afes_path = OUT_DIR / "_afes_context.txt"
afes_path.write_text(_AFES_CONTEXT, encoding="utf-8")
print(f"Wrote {afes_path}")

# ── Write one JSON per syndrome ───────────────────────────────────────────────
# Replace the literal AFES_CONTEXT text with the placeholder {AFES_CONTEXT}
# so the loader can substitute it at runtime.

for slug, cfg in SYNDROME_CONFIG.items():
    codes = SYNDROME_CODES.get(slug, {})
    sero  = SYNDROME_SERO.get(slug, {})

    system_prompt_raw = cfg.get("system_prompt", "")
    # The f-string already ran — replace the actual text with the placeholder
    system_prompt_clean = system_prompt_raw.replace(_AFES_CONTEXT, "{AFES_CONTEXT}")

    record = {
        "slug":              cfg.get("slug", slug),
        "name_de":           cfg.get("name_de", slug),
        "lag_weeks":         cfg.get("lag_weeks", 0),
        "refs":              cfg.get("refs", None),
        "system_prompt":     system_prompt_clean,
        "icd10_gm":          codes.get("icd10_gm", []),
        "meldepflicht_de":   codes.get("meldepflicht_de", False),
        "guidelines":        codes.get("guidelines", {}),
        "symptoms":          codes.get("symptoms", []),
        "seroprevalence_de": sero.get("seroprevalence_de", None),
        "sero_category":     sero.get("sero_category", None),
        "endemic_regions":   sero.get("endemic_regions", []),
    }

    out = OUT_DIR / f"{slug}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote {out.name}")

print(f"\nDone — {len(all_slugs)} JSON files + _afes_context.txt in {OUT_DIR}")
