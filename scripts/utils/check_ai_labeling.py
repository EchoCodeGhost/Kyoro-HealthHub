#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
KI-Kennzeichnungs-Compliance-Check

@tier        infrastructure
@purpose.de  Prüft automatisiert, dass kein Skript einen eigenen, handgestrickten
             LLM-Chat-Completion-Aufruf implementiert, ohne die zentrale KI-Kennzeichnung
             (modules.llm.ai_label()) zu verwenden. openspec/specs/ethics-enforcement/spec.md
             ("Labeling of AI-generated output") war bisher nur durch manuelle PR-Review
             durchgesetzt — ein Audit fand die meisten call_llm()-Aufrufer ohne Kennzeichnung,
             plus zwei Skripte (analyse_synthesis.py, analyse_clinical_addendum.py), die
             modules.llm.call_llm() komplett umgehen und daher auch dessen automatische
             Kennzeichnung (call_llm(..., label_output=True), seit diesem Fix Standard) nie
             erreicht hätten.
@purpose.en  Automatically checks that no script implements its own hand-rolled LLM
             chat-completion call without using the shared AI-generated label
             (modules.llm.ai_label()). openspec/specs/ethics-enforcement/spec.md ("Labeling
             of AI-generated output") was previously enforced only by manual PR review — an
             audit found most call_llm() callers without any labeling, plus two scripts
             (analyse_synthesis.py, analyse_clinical_addendum.py) that bypass
             modules.llm.call_llm() entirely and would therefore never reach its automatic
             labeling (call_llm(..., label_output=True), the default since this fix) either.
@method.de   Durchsucht scripts/**/*.py nach dem OpenAI-kompatiblen Chat-Message-Muster
             ("role": "system" UND "role": "user" im selben File — die Signatur eines
             selbstgebauten Chat-Completion-Requests). Trifft das zu, muss dieselbe Datei
             auch ai_label( aufrufen. modules/llm.py und utils/llm_provider.py sind die
             kanonische Implementierung (dort entsteht die Kennzeichnung) und ausgenommen;
             llm_benchmark.py ist ein Entwickler-Werkzeug zum Modellvergleich, keine für
             Endnutzer angezeigte klinische Ausgabe, und dokumentiert ausgenommen.
@method.en   Scans scripts/**/*.py for the OpenAI-compatible chat message pattern
             ("role": "system" AND "role": "user" in the same file — the signature of a
             hand-rolled chat-completion request). Where that matches, the same file must
             also call ai_label(. modules/llm.py and utils/llm_provider.py are the canonical
             implementation (labeling originates there) and are exempt; llm_benchmark.py is a
             developer tool for comparing models, not end-user-facing clinical output, and is
             documented as exempt.
@reads       scripts/**/*.py
@writes      STDOUT/STDERR (Fehlermeldungen)
@relevance.de  Technische Durchsetzung der KI-Kennzeichnungspflicht (s. docs/ETHICS.md
               §6, openspec/specs/ethics-enforcement/spec.md) — ohne diesen Check kann eine
               neue Umgehung von call_llm() unbemerkt unmarkierte Ausgaben erzeugen.
@relevance.en  Technical enforcement of the AI-labeling requirement (see docs/ETHICS.md
               §6, openspec/specs/ethics-enforcement/spec.md) — without this check, a new
               bypass of call_llm() could silently produce unlabeled output.
@limits.de   Heuristik über Quelltext-Substrings (kein AST/Datenfluss-Tracking) — erkennt
             keine dynamisch aus Strings zusammengesetzten Chat-Payloads und keine
             Kennzeichnung über Aliase/Re-Exports von ai_label.
@limits.en   Source-text heuristic (no AST/data-flow tracking) — does not detect chat
             payloads assembled dynamically from strings, nor labeling via aliases/
             re-exports of ai_label.
@usage
    python3 scripts/utils/check_ai_labeling.py
    python3 scripts/utils/check_ai_labeling.py --path scripts

Exit Codes:
    0: Kein handgestrickter LLM-Aufruf ohne Kennzeichnung gefunden
    1: Mindestens ein Fund ohne ai_label(-Aufruf
    2: kritischer Fehler (z.B. Verzeichnis nicht gefunden)
"""

import argparse
import re
import sys
from pathlib import Path

CHAT_SYSTEM_ROLE_PATTERN = re.compile(r'"role"\s*:\s*"system"')
CHAT_USER_ROLE_PATTERN = re.compile(r'"role"\s*:\s*"user"')
AI_LABEL_PATTERN = re.compile(r"\bai_label\s*\(")

# Ausgenommene Dateien mit Begründung (kanonische Implementierung oder
# dokumentiert kein Endnutzer-Anzeigepfad), damit Ausnahmen nicht
# stillschweigend wachsen.
EXEMPT_SUFFIXES = {
    "modules/llm.py": "kanonische Implementierung — hier entsteht ai_label() selbst",
    "utils/llm_provider.py": "kanonische Provider-Implementierung, von call_llm() delegiert",
    "llm_benchmark.py": "Entwickler-Werkzeug zum Modellvergleich, keine Endnutzer-Anzeige",
}


def _is_exempt(rel_path: str) -> bool:
    return any(rel_path.endswith(suffix) for suffix in EXEMPT_SUFFIXES)


def check_file(path: Path) -> str | None:
    """Gibt eine Fehlermeldung zurück, falls die Datei einen handgestrickten
    Chat-Completion-Aufruf enthält, aber ai_label(...) nicht aufruft."""
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, OSError) as e:
        return f"Datei nicht lesbar: {e}"

    if not (CHAT_SYSTEM_ROLE_PATTERN.search(source) and CHAT_USER_ROLE_PATTERN.search(source)):
        return None  # kein handgestricktes Chat-Message-Payload erkennbar
    if AI_LABEL_PATTERN.search(source):
        return None

    return (
        "Enthält ein handgestricktes LLM-Chat-Payload (\"role\": \"system\"/\"user\"), "
        "ruft aber ai_label(...) nicht auf — umgeht modules.llm.call_llm()'s automatische "
        "KI-Kennzeichnung (openspec/specs/ethics-enforcement/spec.md)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prüft, ob handgestrickte LLM-Aufrufe die KI-Kennzeichnung umgehen"
    )
    parser.add_argument(
        "--path", "-p", type=str, default="scripts",
        help="Verzeichnis mit Skripten (default: scripts)",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Nur Fehlerzusammenfassung anzeigen",
    )
    args = parser.parse_args()

    base_path = Path.cwd()
    scan_path = base_path / args.path
    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}", file=sys.stderr)
        sys.exit(2)

    py_files = sorted(scan_path.rglob("*.py"))
    if not py_files:
        print(f"No Python files found in: {scan_path}", file=sys.stderr)
        sys.exit(2)

    findings: dict[str, str] = {}
    for path in py_files:
        try:
            rel_path = str(path.relative_to(base_path))
        except ValueError:
            rel_path = str(path)
        if _is_exempt(rel_path):
            continue
        error = check_file(path)
        if error:
            findings[rel_path] = error

    if not args.quiet:
        print("=" * 80)
        print("📊 AI-LABELING COMPLIANCE REPORT")
        print("=" * 80)
        print(f"📁 Scanned: {len(py_files)} files in {args.path}")
        print(f"✅ Compliant: {len(py_files) - len(findings)}/{len(py_files)}")
        print(f"❌ Unlabeled hand-rolled LLM calls: {len(findings)}/{len(py_files)}")
        print("-" * 80)

    if findings:
        print("\n🚨 ERRORS:")
        print("-" * 80)
        for rel_path, error in sorted(findings.items()):
            print(f"\n{rel_path}:")
            print(f"  ❌ {error}")
        print("\n" + "=" * 80)
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        sys.exit(1)

    print("\n" + "=" * 80)
    print("✅ NO UNLABELED HAND-ROLLED LLM CALLS!")
    print("=" * 80)
    sys.exit(0)


if __name__ == "__main__":
    main()
