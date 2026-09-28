#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
check_no_dates — Enforces the no-embedded-dates/versions convention (CONTRIBUTING.md)

@tier        infrastructure
@purpose.de  Prüft .py- und .md-Dateien auf hardcodierte Datums-/Versionsangaben, die
             *wann* etwas geändert wurde oder *welche* Revision es einführte markieren
             (Statuswort direkt vor einem Datum wie "Fixed <Datum>" oder "Bestellt
             (<Datum>)", "As of <Datum>", eine bloße "Version X.Y"-Revisionsmarke,
             dateibehaftete Dateinamen mit angehängtem Datum vor der Endung) —
             genau die Muster, die docs/CONTRIBUTING.md § "Versioning and changelogs"
             verbietet, weil Git-Historie diese Information bereits trägt und eine
             im Dateiinhalt duplizierte Angabe veraltet, ohne dass es auffällt.
@purpose.en  Checks .py and .md files for hardcoded date/version markers that record
             *when* something changed or *which* revision introduced it (a status
             word immediately before a date, like "Fixed <date>" or "Ordered
             (<date>)", "As of <date>", a bare "Version X.Y" revision marker, a
             filename with a date suffix before the extension) — exactly the
             patterns docs/CONTRIBUTING.md § "Versioning and changelogs" forbids,
             because git history already carries that information and a copy baked
             into file content goes stale without anyone noticing.
@method.de   Wortnahe Regex-Muster statt eines pauschalen Datums-Scans: ein blindes
             "\\d{4}-\\d{2}-\\d{2}"-Muster würde auf jedes legitime Datenfeld anschlagen
             (clinical.events, `--from 2024-01-01`-Beispiele in @usage-Blöcken,
             "birthdate" im Config-Template) — Tausende Fehlalarme. Stattdessen: (1)
             Statuswort (Fixed/Resolved/Ordered/Bestellt/Behoben/Gefunden/Repariert/
             Dead/Benchmarked/Flagged/Befund/Finding/Korrigiert/Corrected/
             Ergänzt/…) vor oder nach einem Datum (Volldatum ODER
             Monatsdatum YYYY-MM), case-insensitive, mit bis zu 4 Füllwörtern
             dazwischen erlaubt — fängt sowohl "Fixed 2026-07-18" als auch "Found in
             production data 2026-07-20" oder "2026-07-22 live verifiziert"; (2) "As
             of"/"Stand:"/"seit"/"since" vor einem Datum; (3) Dateiname mit
             angehängtem Datum vor der Endung; (4) "Version X.Y" als bloße
             Revisionsmarke; (5) "commit `<hash>`" als Erzähl-Referenz (nicht "git
             commit -m", da dort kein Hex-String folgt); (6) eine Datensatz-Zahl
             direkt vor einem Mengen-Substantiv (Zeilen/rows/Messungen/Datensätze/…)
             KOMBINIERT MIT einem Datum auf derselben Zeile — beide Teilmuster müssen
             treffen, damit z.B. CSV-Beispielzeilen oder ISO-Zeitstempel mit
             Millisekunden (".000") nicht anschlagen. Zeilen mit Zitat-Signalwörtern
             (doi:, AWMF, RKI, WHO, guideline, Leitlinie, …) sind von Kategorie 4
             ausgenommen, da CONTRIBUTING.md Literaturangaben (Leitlinien-Versionen,
             Publikationsjahre, DOIs) explizit als Domäneninhalt erlaubt, nicht als
             Projekt-Changelog. "ab"/"bis" vor einem Datum wird bewusst NICHT
             geprüft — zu viele legitime Domänenfakten (Geräte-Verfügbarkeit ab
             Datum X, Datenquelle deckt Zeitraum bis Y ab) hätten sonst
             Fehlalarme ausgelöst. Scannt git-getrackte Dateien (git ls-files) —
             private/gitignorte Verzeichnisse (intern/, data/, …) fallen automatisch
             raus. Exit-Code: 0 = sauber, 1 = Findings gefunden.
@method.en   Word-adjacent regex patterns instead of a blanket date scan: a bare
             "\\d{4}-\\d{2}-\\d{2}" pattern would match every legitimate data field
             (clinical.events, `--from 2024-01-01` examples in @usage blocks,
             "birthdate" in the config template) — thousands of false positives.
             Instead: (1) a status word (Fixed/Resolved/Ordered/Bestellt/Behoben/
             Found/Repaired/Dead/Benchmarked/Flagged/Befund/Finding/Korrigiert/
             Corrected/Ergänzt/…) before or after a date (full
             date OR month-only YYYY-MM), case-insensitive, with up to 4 filler
             words allowed in between — catches "Fixed 2026-07-18" as well as
             "Found in production data 2026-07-20" or "2026-07-22 live verified";
             (2) "As of"/"Stand:"/"seit"/"since" immediately before a date; (3) a
             filename with a date suffix before the extension; (4) a bare "Version
             X.Y" revision marker; (5) "commit `<hash>`" cited as narrative prose
             (not "git commit -m", since no hex string follows there); (6) a record
             count directly before a quantity noun (rows/Zeilen/Messungen/records/…)
             COMBINED WITH a date on the same line — both sub-patterns must match, so
             CSV example rows or ISO timestamps with milliseconds (".000") don't
             trigger it. Lines containing citation signal words (doi:, AWMF, RKI,
             WHO, guideline, Leitlinie, …) are exempt from category 4, since
             CONTRIBUTING.md explicitly allows citations (guideline versions,
             publication years, DOIs) as domain content, not project changelog.
             "ab"/"bis"/"until" immediately before a date is deliberately NOT
             checked — too many legitimate domain facts (device data available
             from date X, a data source covering a period up to date Y) would have
             false-positived. Scans git-tracked files (git ls-files) — private/
             gitignored directories (intern/, data/, …) fall out automatically.
             Exit code: 0 = clean, 1 = findings found.
@reads       all git-tracked .py/.md files in the scanned directory
@writes      stdout (report and JSON output)
@limits.de   Wortliste (Statuswörter, Zitat-Signalwörter, Mengen-Substantive) ist
             nicht erschöpfend — ungewöhnliche Formulierungen können durchrutschen.
             Zeilenbasiert: ein Statuswort und ein Datum, die über zwei Kommentar-
             /Docstring-Zeilen verteilt sind (z.B. "...(N rows, back to\n#
             YYYY-MM-DD)"), werden NICHT erkannt. Kategorie 6 (Zahl+Datum) verlangt
             ein explizites Mengen-Substantiv direkt nach der Zahl — ein Datensatz-
             Fakt ohne ein solches Substantiv auf derselben Zeile wie das Datum (z.B.
             "gemessen: N Zeilen über mehrere Geräte-IDs" ohne Datum in der Zeile)
             bleibt unentdeckt. Kann in seltenen Fällen falsch-positiv sein (z.B. ein
             Statuswort und ein unabhängiges Datumsfeld zufällig in derselben Zeile
             ohne Kausalbezug). Prüft nicht, ob ein gefundenes Datum tatsächlich
             stimmt/veraltet ist — nur ob eines der Muster überhaupt vorkommt.
@limits.en   Word list (status words, citation signal words, quantity nouns) is not
             exhaustive — unusual phrasings can slip through. Line-based: a status
             word and a date split across two comment/docstring lines (e.g.
             "...(N rows, back to\n# YYYY-MM-DD)") are NOT detected. Category 6
             (count+date) requires an explicit quantity noun right after the number —
             a record-count fact with no such noun on the same line as the date
             (e.g. "measured: N rows across several device IDs" with no date on
             that line) goes undetected. Can rarely false-positive (e.g. a status word and
             an unrelated date field coincidentally on the same line with no causal
             link). Does not check whether a found date is actually correct/stale —
             only whether one of the patterns occurs at all.

@relevance.de  Setzt die Datums-/Versionskonvention aus CONTRIBUTING.md technisch durch, verhindert stillschweigend veraltende Changelog-Reste im Dateiinhalt
@relevance.en  Technically enforces the date/version convention from CONTRIBUTING.md, prevents silently-staling changelog remnants in file content
@usage
    python scripts/utils/check_no_dates.py
    python scripts/utils/check_no_dates.py --dir docs
    python scripts/utils/check_no_dates.py --json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_DATE_RE = r"\d{4}-\d{2}-\d{2}"
# Monatsdatum (YYYY-MM) ohne Tag, z.B. "2026-07" — negative Lookahead auf "-DD"
# verhindert Doppel-Treffer auf einem vollen Datum (das faengt schon _DATE_RE).
_DATE_MONTH_RE = r"\d{4}-(?:0[1-9]|1[0-2])(?!-\d{2})"
_DATE_ANY_RE = rf"(?:{_DATE_RE}|{_DATE_MONTH_RE})"

_STATUS_WORDS = [
    # English
    "Fixed", "Resolved", "Added", "Updated", "Changed", "Removed", "Deprecated",
    "Implemented", "Completed", "Done", "Ordered", "Received", "Published",
    "Released", "Merged", "Reviewed", "Verified", "Confirmed", "Tested", "Started",
    "Migrated", "Renamed", "Introduced", "Found", "Repaired", "Dead",
    "Benchmarked", "Benchmark", "Flagged", "Finding", "Corrected",
    # Deutsch
    "Behoben", "Gelöst", "Hinzugefügt", "Aktualisiert", "Geändert", "Entfernt",
    "Implementiert", "Abgeschlossen", "Fertig", "Bestellt", "Erhalten",
    "Veröffentlicht", "Gemergt", "Geprüft", "Verifiziert", "Bestätigt", "Getestet",
    "Begonnen", "Migriert", "Umbenannt", "Eingeführt", "Gefunden", "Repariert",
    "Markiert", "Befund", "Korrigiert", "Ergänzt",
]
_status_alt = "|".join(re.escape(w) for w in _STATUS_WORDS)
# Bis zu 4 Fuellwoerter zwischen Statuswort und Datum, in beide Richtungen
# ("Fixed 2026-07-18" ebenso wie "Found in production data 2026-07-20" oder
# "2026-07-22 live gegen X verifiziert").
_FILLER = r"(?:[\wäöüÄÖÜß'’/.-]+\s+){0,4}"

_CITATION_MARKERS = re.compile(
    r"doi:|AWMF|RKI\b|ESC\b|ESH\b|WHO\b|ISO\s?3166|RFC\s?\d|USPSTF|"
    r"guideline|Leitlinie|et al\.?|Task Force",
    re.IGNORECASE,
)

_STATIC_CHECKS = [
    {
        "category": "Statuswort + Datum (Changelog-Muster im Dateiinhalt)",
        "patterns": [
            (re.compile(rf"\b(?:{_status_alt})\b\s*:?\s*{_FILLER}\(?{_DATE_ANY_RE}\)?",
                        re.IGNORECASE),
             "Statuswort vor Datum (auch mit Fuellwoertern dazwischen) — Git-Historie "
             "trägt das schon (→ Datum entfernen, Statuswort ggf. ohne Datum stehen lassen)"),
            (re.compile(rf"\(?{_DATE_ANY_RE}\)?\s*{_FILLER}\b(?:{_status_alt})\b",
                        re.IGNORECASE),
             "Datum vor Statuswort (auch mit Fuellwoertern dazwischen) — Git-Historie "
             "trägt das schon (→ Datum entfernen, Statuswort ggf. ohne Datum stehen lassen)"),
        ],
    },
    {
        "category": '"As of" / "Stand" / "seit" + Datum',
        "patterns": [
            (re.compile(rf"\b[Aa]s of\s+{_DATE_ANY_RE}\b"),
             '"As of <Datum>" — Git-Historie trägt das schon'),
            (re.compile(rf"\bStand:?\s+{_DATE_ANY_RE}\b"),
             '"Stand: <Datum>" — Git-Historie trägt das schon'),
            # Negative Lookbehind auf "-": --since/--seit sind CLI-Flag-Namen in
            # @usage-Beispielen (z.B. "--since 2026-06-01"), kein Prosa-Hinweis.
            (re.compile(rf"(?<!-)\bseit\s+{_DATE_ANY_RE}\b"),
             '"seit <Datum>" — Git-Historie trägt das schon (Ausnahme: echtes Datenfeld, kein Changelog-Hinweis)'),
            (re.compile(rf"(?<!-)\b[Ss]ince\s+{_DATE_ANY_RE}\b"),
             '"since <Datum>" — Git-Historie trägt das schon (Ausnahme: echtes Datenfeld, kein Changelog-Hinweis)'),
        ],
    },
    {
        "category": '"Version X.Y" als Revisionsmarke',
        "exempt_citations": True,
        "patterns": [
            (re.compile(r"\bVersion\s+\d+\.\d+\b"),
             'Bloße "Version X.Y"-Angabe ohne Zitat-Kontext — Git-Tags/Releases tragen das (Ausnahme: Zitat einer externen Quelle, z.B. Leitlinien-Version)'),
        ],
    },
    {
        "category": "Commit-Hash als Prosa-Verweis",
        "patterns": [
            # "commit `<hash>`" / "commit abc1234" / "commit message of `<hash>`"
            # als Erzaehl-Referenz, NICHT "git commit -m ..." (dort folgt kein
            # Hex-String auf "commit", auch nicht nach ein paar Fuellwoertern).
            (re.compile(rf"\bcommit\b\s*{_FILLER}`?[0-9a-f]{{7,40}}`?\b", re.IGNORECASE),
             'Commit-Hash als Erzaehltext ("in commit <hash> ...") — Git-Historie ist schon die '
             "Quelle dafuer, ein Funktions-/Dateiname ist ein stabilerer Verweis als ein Hash"),
        ],
    },
    {
        # Zwei UNABHAENGIGE Muster, beide muessen auf derselben Zeile treffen (siehe
        # "requires_all" in scan_file): eine Zahl direkt vor einem Mengen-Substantiv
        # (Zeilen/rows/Messungen/...) UND ein Datum irgendwo in der Zeile. Nur die
        # Kombination ist das Signal — eine Zahl+Substantiv allein (z.B. "14 total
        # importers", eine strukturelle Aufzaehlung) oder ein Datum allein (z.B. eine
        # CSV-Beispielzeile, ein ISO-Zeitstempel mit Millisekunden ".000") sind beides
        # fuer sich genommen legitim und sollen NICHT anschlagen.
        "category": "Datensatz-Zahl + Datum in derselben Zeile (Snapshot-Fakt)",
        "requires_all": [
            re.compile(
                r"\d[\d.,]{2,}\s*(?:\w+-)?"
                r"(?:Zeilen|Datens[äa]tze|Messungen|Werte|Meldef[äa]lle|rows?|records?|entries)\b",
                re.IGNORECASE,
            ),
            re.compile(_DATE_ANY_RE),
        ],
        "label": 'Zahl+Mengen-Substantiv (z.B. "13.677 Messungen") kombiniert mit einem Datum '
                 'auf derselben Zeile — typisches "Stand X am Datum Y"-Snapshot-Muster, das mit '
                 "dem naechsten Import veraltet (→ qualitativ umformulieren statt Zahl/Datum "
                 "hardzucoden)",
    },
]

# Eigene Datei + Dateien, die die verbotenen Muster als Beispiel zitieren, um
# die Regel selbst zu erklären (CONTRIBUTING.md, die generierte Doku dieser
# Datei), keine echten Verstöße.
_SELF_EXCLUDE = {
    "check_no_dates.py", "CONTRIBUTING.md", "CONTRIBUTING_DE.md",
    "check_no_dates.md",
}

_SKIP_DIRS = {
    "__pycache__", ".venv", "venv", ".git", "node_modules",
    "intern", "data", "imports", "medicine", "medizin",
}

_SKIP_PATH_PREFIXES: tuple[str, ...] = ()

_DEFAULT_EXTENSIONS = (".py", ".md")

# Dateiname mit Datum vor der Endung, z.B. "plan_x_2026-07-14.md"
_DATED_FILENAME_RE = re.compile(r"[-_]\d{4}-\d{2}-\d{2}(?=\.[A-Za-z0-9]+$)")


def _tracked_files(root: Path, extensions: tuple[str, ...]) -> list[Path] | None:
    """Git-getrackte Dateien mit den angegebenen Endungen, oder None wenn `root`
    kein Git-Repo ist (dann rglob-Fallback in scan_directory)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    files = []
    for line in result.stdout.splitlines():
        if line and Path(line).suffix in extensions:
            files.append(root / line)
    return files


def scan_filename(path: Path) -> list[dict]:
    if _DATED_FILENAME_RE.search(path.name):
        return [{
            "file": str(path),
            "line": 0,
            "category": "Datierter Dateiname",
            "label": "Dateiname enthält ein Datum (→ Git-Historie trägt das schon, umbenennen)",
            "text": path.name,
        }]
    return []


def scan_file(path: Path) -> list[dict]:
    findings = scan_filename(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        for check in _STATIC_CHECKS:
            if check.get("exempt_citations") and _CITATION_MARKERS.search(line):
                continue
            if "requires_all" in check:
                if all(p.search(line) for p in check["requires_all"]):
                    findings.append({
                        "file": str(path),
                        "line": lineno,
                        "category": check["category"],
                        "label": check["label"],
                        "text": stripped[:160],
                    })
                continue
            for pattern, label in check["patterns"]:
                if pattern.search(line):
                    findings.append({
                        "file": str(path),
                        "line": lineno,
                        "category": check["category"],
                        "label": label,
                        "text": stripped[:160],
                    })
    return findings


def scan_directory(root: Path, extensions: tuple[str, ...] = _DEFAULT_EXTENSIONS) -> list[dict]:
    tracked = _tracked_files(root, extensions)
    candidates = tracked if tracked is not None else [
        f for ext in extensions for f in root.rglob(f"*{ext}")
    ]
    all_findings: list[dict] = []
    for file in sorted(candidates):
        if any(part in _SKIP_DIRS for part in file.parts):
            continue
        if file.name in _SELF_EXCLUDE:
            continue
        try:
            rel_posix = file.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_posix = file.as_posix()
        if any(rel_posix.startswith(p) for p in _SKIP_PATH_PREFIXES):
            continue
        all_findings.extend(scan_file(file))
    return all_findings


def print_report(findings: list[dict], root: Path) -> None:
    if not findings:
        print("✓ check_no_dates: keine Findings")
        return

    print(f"⚠ check_no_dates: {len(findings)} Finding(s)")
    print()

    by_cat: dict[str, list[dict]] = {}
    for f in findings:
        by_cat.setdefault(f["category"], []).append(f)

    def _rel(p: str) -> str:
        try:
            return str(Path(p).relative_to(root))
        except ValueError:
            return p

    for cat, items in by_cat.items():
        print(f"── {cat} ({len(items)}) {'─' * max(0, 45 - len(cat))}")
        for item in items:
            loc = f"{_rel(item['file'])}" + (f":{item['line']}" if item["line"] else "")
            print(f"  {loc}")
            print(f"    {item['label']}")
            print(f"    {item['text']}")
        print()

    print('Siehe docs/CONTRIBUTING.md § "Versioning and changelogs". Findings beheben.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enforces the no-embedded-dates/versions convention (CONTRIBUTING.md)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dir", type=Path, default=_REPO_ROOT,
                        help=f"Verzeichnis zum Scannen (Standard: Repo-Root, {_REPO_ROOT})")
    parser.add_argument("--ext", nargs="+", default=list(_DEFAULT_EXTENSIONS),
                        help=f"Zu scannende Dateiendungen (Standard: {' '.join(_DEFAULT_EXTENSIONS)})")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    args = parser.parse_args()

    extensions = tuple(e if e.startswith(".") else f".{e}" for e in args.ext)
    findings = scan_directory(args.dir, extensions=extensions)

    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    else:
        print_report(findings, args.dir)

    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
