#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Umfassender Privacy- und Anonymisierungs-Check

@tier        infrastructure
@purpose.de  Führt umfassende Privacy- und Anonymisierungs-Checks aus
@purpose.en  Performs comprehensive privacy and anonymisation checks
@method.de   Führt nacheinander drei Checks aus:
             1. Quellcode- und Doku-Check mit check_source_privacy.py (.py/.md/.json, ganzes Repo)
             2. Datenbank-Anonymisierungs-Check mit check_anonymization.py
             3. PII-Scan mit scrub_pii.py --dry-run
             Zeigt standardmäßig nur Ergebnisse an. Mit --fix werden PII tatsächlich bereinigt (mit Backup).
@method.en   Sequentially executes three checks:
             1. Source code and doc check with check_source_privacy.py (.py/.md/.json, whole repo)
             2. Database anonymisation check with check_anonymization.py
             3. PII scan with scrub_pii.py --dry-run
             By default, only shows results. With --fix, PII is actually cleaned (with backup).
@reads       Alle Quellcode-Dateien und Datenbanktabellen
@writes      PII-Bereinigte Dateien (nur mit --fix)
@limits.de   Keine direkte Validierung. Abhängig von den einzelnen Check-Skripten.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No direct validation. Dependent on individual check scripts.
@usage
    python3 scripts/check_all.py
    python3 scripts/check_all.py --skip-db       # nur Quellcode
    python3 scripts/check_all.py --skip-source   # nur DB + PII
    python3 scripts/check_all.py --fix           # PII tatsächlich bereinigen (mit Backup)
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_SCRIPTS = Path(__file__).parent
_ROOT    = _SCRIPTS.parent
_PYTHON  = sys.executable


def _run(label: str, cmd: list[str]) -> int:
    width = 60
    print(f"\n{'─' * width}")
    print(f"  {label}")
    print(f"{'─' * width}", flush=True)
    result = subprocess.run(cmd)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Umfassender Privacy- und Anonymisierungs-Check",
                      "Comprehensive privacy and anonymisation check"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--skip-db",     action="store_true",
                        help=t("DB-Checks überspringen", "Skip database checks"))
    parser.add_argument("--skip-source", action="store_true",
                        help=t("Quellcode-Check überspringen", "Skip source-code check"))
    parser.add_argument("--skip-pii",    action="store_true",
                        help=t("PII-Scan überspringen", "Skip PII scan"))
    parser.add_argument("--fix",         action="store_true",
                        help=t("PII tatsächlich bereinigen statt nur anzeigen (mit Backup)",
                               "Actually scrub PII instead of just showing it (with backup)"))
    parser.add_argument("--strict",      action="store_true",
                        help=t("Auch low-confidence Findings im Quellcode als Fehler werten",
                               "Treat low-confidence source findings as errors too"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    results: dict[str, int] = {}

    # ── 1. Quellcode-Check ────────────────────────────────────────────────
    if not args.skip_source:
        cmd = [_PYTHON, str(_SCRIPTS / "utils" / "check_source_privacy.py"),
               "--dir", str(_ROOT)]
        if args.strict:
            cmd.append("--strict")
        results[t("Quellcode (Privacy)", "Source Code (Privacy)")] = _run(
            t("1/3  Quellcode — Privacy-Check", "1/3  Source Code — Privacy Check"), cmd)

    # ── 2. DB Anonymisierungs-Compliance ─────────────────────────────────
    if not args.skip_db:
        results[t("DB (Anonymisierung)", "DB (Anonymisation)")] = _run(
            t("2/3  Datenbank — Anonymisierungs-Compliance",
              "2/3  Database — Anonymisation Compliance"),
            [_PYTHON, str(_SCRIPTS / "utils" / "check_anonymization.py")],
        )

    # ── 3. PII-Scan ───────────────────────────────────────────────────────
    if not args.skip_pii:
        if args.fix:
            pii_cmd = [_PYTHON, str(_SCRIPTS / "utils" / "scrub_pii.py"), "--auto"]
            label   = t("3/3  PII-Bereinigung (--fix)", "3/3  PII Cleanup (--fix)")
        else:
            pii_cmd = [_PYTHON, str(_SCRIPTS / "utils" / "scrub_pii.py"), "--dry-run"]
            label   = t("3/3  PII-Scan (dry-run — kein Fix)", "3/3  PII Scan (dry-run — no fix)")
        results[t("PII-Scan", "PII Scan")] = _run(label, pii_cmd)

    # ── Zusammenfassung ───────────────────────────────────────────────────
    width = 60
    print(f"\n{'═' * width}")
    print(f"  {t('Ergebnis', 'Results')}")
    print(f"{'═' * width}")
    any_fail = False
    for name, code in results.items():
        status = "✓ OK" if code == 0 else t("✗ FEHLER", "✗ FAIL")
        print(f"  {status:10}  {name}")
        if code != 0:
            any_fail = True
    print(f"{'═' * width}")

    if any_fail:
        print(f"\n{t('✗ Mindestens ein Check hat Findings — bitte oben nachlesen.', '✗ At least one check has findings — see above.')}")
        sys.exit(1)
    else:
        print(f"\n{t('✓ Alle Checks bestanden.', '✓ All checks passed.')}")


if __name__ == "__main__":
    main()
