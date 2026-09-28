#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
check_commit_message_privacy — Blocks personal data in commit messages

@tier        infrastructure
@purpose.de  Prüft eine Commit-Message auf konkrete, aus der echten Gesundheits-/
             Gerätedatenbank abgelesene persönliche Werte (Prozentsätze, Zeilenzahlen,
             Messwerte mit klinischer Einheit, exakte Daten, Monat+Jahr-Zeiträume) —
             Commit-Messages sind in diesem öffentlichen Repo genauso einsehbar wie
             Code, ein Bugfix-Kommentar darf den Mechanismus erklären, aber keine
             konkreten Zahlen aus der eigenen Krankengeschichte/Gerätehistorie zitieren.
@purpose.en  Checks a commit message for concrete personal values read from the real
             health/device database (percentages, row counts, clinical-unit
             measurements, exact dates, month+year timeframes) — commit messages are
             just as public as code in this repo; a bugfix message may explain the
             mechanism but must not cite specific figures from the user's own health
             history or device history.
@method.de   Wortnahe Regex-Muster, analog zu check_no_dates.py: Dezimal-Prozentsatz,
             Dezimalwert mit klinischer/technischer Einheit (mg/dl, mmol, ms, bpm, min,
             kg, km/h, dB, °C, ml/kg/min), "N Zeilen/rows/entries/Werte/Tage betroffen",
             exaktes ISO-Datum, Monatsname+Jahr. Zeilen mit Zitat-Signalwörtern (doi:,
             WHO, AWMF, guideline, Leitlinie, et al., …) sind ausgenommen — externe
             Referenzwerte aus medizinischer Literatur sind Domäneninhalt, kein
             personenbezogener Befund.
@method.en   Word-adjacent regex patterns, mirroring check_no_dates.py: decimal
             percentage, decimal value with a clinical/technical unit (mg/dl, mmol,
             ms, bpm, min, kg, km/h, dB, °C, ml/kg/min), "N rows/entries/values/days
             affected", exact ISO date, month name + year. Lines with citation signal
             words (doi:, WHO, AWMF, guideline, Leitlinie, et al., …) are exempt —
             external reference values from medical literature are domain content,
             not a personal finding.
@reads       commit message text (file path or stdin)
@writes      stdout (report), process exit code
@limits.de   Heuristisch, nicht erschöpfend — ungewöhnliche Formulierungen können
             durchrutschen oder legitime technische Werte (z.B. ein Schwellenwert im
             Code selbst) fälschlich anschlagen. Prüft nur die Message, nicht den
             Diff — ein Fund heißt nicht zwingend, dass der referenzierte Wert aus
             echten persönlichen Daten stammt, nur dass er verdächtig aussieht.
@limits.en   Heuristic, not exhaustive — unusual phrasing can slip through, or a
             legitimate technical value (e.g. a threshold constant in the code
             itself) can false-positive. Checks the message only, not the diff — a
             finding doesn't necessarily mean the cited value came from real
             personal data, only that it looks suspicious.

@relevance.de  Verhindert, dass konkrete persönliche Gesundheits-/Gerätewerte über Commit-Messages in die öffentliche Repo-Historie gelangen
@relevance.en  Prevents concrete personal health/device values from entering the public repo history via commit messages
@usage
    python scripts/utils/check_commit_message_privacy.py .git/COMMIT_EDITMSG
    echo "some message" | python scripts/utils/check_commit_message_privacy.py -
"""

import re
import sys
from pathlib import Path

_CITATION_MARKERS = re.compile(
    r"doi:|AWMF|RKI\b|ESC\b|ESH\b|WHO\b|ISO\s?3166|RFC\s?\d|USPSTF|"
    r"guideline|Leitlinie|et al\.?|Task Force",
    re.IGNORECASE,
)

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
)

_CHECKS = [
    {
        "category": "Dezimal-Prozentsatz",
        "pattern": re.compile(r"\d+[.,]\d+\s*%"),
        "label": "Konkreter Prozentwert — vermutlich aus echten Daten abgelesen, nicht als Konstante nötig",
    },
    {
        "category": "Messwert mit klinischer/technischer Einheit",
        "pattern": re.compile(
            r"\d+[.,]\d+\s*(mg/dl|mmol(?:/[lL])?|ms\b|bpm|min\b|kg\b|km/h|ml/kg/min|dB|°C|mL|µg/l|U/l)",
            re.IGNORECASE,
        ),
        "label": "Konkreter Messwert mit Einheit — vermutlich ein echter Befund/Messwert",
    },
    {
        "category": "Anzahl betroffener Datensätze",
        "pattern": re.compile(
            r"\b\d+\s+(Zeilen|rows|entries|Einträge|readings|Werte|Messungen|Tage|days|"
            r"nights|Nächte|records|samples|Datensätze)\b",
            re.IGNORECASE,
        ),
        "label": "Konkrete Anzahl betroffener Datensätze — gehört ins Gespräch, nicht in die Historie",
    },
    {
        "category": "Exaktes Datum",
        "pattern": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
        "label": "Exaktes Datum — Commit-Zeitstempel trägt das bereits, kein Grund es im Text zu wiederholen",
    },
    {
        "category": "Monatsname + Jahr (persönlicher Zeitraum)",
        "pattern": re.compile(rf"\b(?:{_MONTHS})[/\s]+\d{{4}}\b"),
        "label": "Monat+Jahr — riecht nach einem konkreten persönlichen Zeitraum aus der echten Historie",
    },
]


def scan_text(text: str) -> list[dict]:
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _CITATION_MARKERS.search(line):
            continue
        for check in _CHECKS:
            m = check["pattern"].search(line)
            if m:
                findings.append({
                    "line": lineno,
                    "category": check["category"],
                    "label": check["label"],
                    "text": stripped[:160],
                })
    return findings


def print_report(findings: list[dict]) -> None:
    if not findings:
        print("✓ check_commit_message_privacy: keine Findings")
        return
    print(f"⚠ check_commit_message_privacy: {len(findings)} Finding(s)")
    print()
    by_cat: dict[str, list[dict]] = {}
    for f in findings:
        by_cat.setdefault(f["category"], []).append(f)
    for cat, items in by_cat.items():
        print(f"── {cat} ({len(items)}) {'─' * max(0, 45 - len(cat))}")
        for item in items:
            print(f"  Zeile {item['line']}: {item['text']}")
            print(f"    {item['label']}")
        print()
    print("Commit-Message nur den Mechanismus beschreiben lassen, keine konkreten "
          "Werte aus echten Daten zitieren.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: check_commit_message_privacy.py <message-file>|-", file=sys.stderr)
        sys.exit(2)
    src = sys.argv[1]
    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8", errors="replace")
    findings = scan_text(text)
    print_report(findings)
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
