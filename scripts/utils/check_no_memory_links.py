#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
check_no_memory_links — Enforces that private memory-link syntax never reaches
the public repo

@tier        infrastructure
@purpose.de  Prüft alle .py- und .md-Dateien auf `[[...]]`-Wikilink-Syntax
             — das Referenzformat des privaten, projektexternen Memory-Systems
             (nicht Teil dieses Repos, nie eingecheckt). Ein solcher Link ist in
             einer öffentlich sichtbaren Datei immer ein Kopier-Artefakt: der
             Zielknoten existiert für Leser:innen des Repos nicht, und das Muster
             taucht ausschließlich auf, wenn privater Kontext ungefiltert in ein
             öffentliches Dokument übernommen wurde.
@purpose.en  Checks all .py and .md files for `[[...]]` wikilink syntax —
             the reference format of the private, project-external memory
             system (not part of this repo, never committed). Such a link in a
             publicly visible file is always a copy-paste artifact: the target
             node does not exist for readers of the repo, and the pattern only
             appears when private context was carried into a public document
             unfiltered.
@method.de   Regex `\\[\\[[a-zA-Z_][a-zA-Z0-9_]*\\]\\]` auf git-getrackten
             Dateien (git ls-files) — beschränkt auf identifier-artigen Inhalt
             (Buchstabe/Unterstrich am Anfang, dann alphanumerisch), weil ein
             naiver `\\[\\[[^\\[\\]]+\\]\\]`-Blindscan echten Python-Code
             falsch trifft: Fancy-Indexing wie `arr[0][[0, -1]]` oder
             `df.spines[['top','right']]` sieht syntaktisch wie ein Wikilink
             aus, ist aber doppeltes eckiges-Klammern-Indexing. Echte
             Memory-Notiznamen in diesem Projekt sind durchgehend snake_case
             (z.B. `project_mission`, `clinic_multi_patient`) und matchen das
             enge Muster; `[0, -1]` oder `'top','right'` nicht. private/
             gitignorte Verzeichnisse (intern/, data/, …) sind über
             git ls-files ohnehin nie enthalten.
             Exit-Code: 0 = sauber, 1 = Findings gefunden.
@method.en   Regex `\\[\\[[a-zA-Z_][a-zA-Z0-9_]*\\]\\]` over git-tracked files
             (git ls-files) — restricted to identifier-like content (letter/
             underscore first, then alphanumeric), because a naive
             `\\[\\[[^\\[\\]]+\\]\\]` blind scan false-positives on real
             Python code: fancy indexing like `arr[0][[0, -1]]` or
             `df.spines[['top','right']]` looks syntactically like a wikilink
             but is double square-bracket indexing. Real memory note names in
             this project are consistently snake_case (e.g.
             `project_mission`, `clinic_multi_patient`) and match the tight
             pattern; `[0, -1]` or `'top','right'` do not. Private/gitignored
             directories (intern/, data/, …) are never included via
             git ls-files in the first place.
             Exit code: 0 = clean, 1 = findings found.
@reads       all git-tracked .py/.md files in the scanned directory
@writes      stdout (report and JSON output)
@limits.de   Erkennt nur die `[[...]]`-Syntax selbst, nicht andere Formen von
             ungefiltert übernommenem privaten Kontext (z.B. Personenbezug in
             Fließtext wie "The user professionally is ...") — dafür gibt es
             keine zuverlässige, false-positive-arme Regel; das bleibt
             Review-Aufgabe.
@limits.en   Only detects the `[[...]]` syntax itself, not other forms of
             unfiltered private context (e.g. personal-profession statements
             in prose like "The user professionally is ...") — no reliable,
             low-false-positive rule exists for that; it remains a review task.

@relevance.de Verhindert, dass private Memory-Referenzen (Notiznamen, die auf
             ein projektexternes, nicht eingechecktes System verweisen) in ein
             öffentliches Repo durchsickern — ein wiederkehrendes Muster bei
             KI-unterstützter Dokumentationsarbeit, bei der privater Chat-
             Kontext und öffentlicher Dateiinhalt sich vermischen können.
@relevance.en Prevents private memory references (note names pointing at a
             project-external, never-committed system) from leaking into a
             public repo — a recurring failure mode in AI-assisted
             documentation work, where private chat context and public file
             content can bleed into each other.
@usage
    python scripts/utils/check_no_memory_links.py
    python scripts/utils/check_no_memory_links.py --dir docs
    python scripts/utils/check_no_memory_links.py --json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_WIKILINK_RE = re.compile(r"\[\[[a-zA-Z_][a-zA-Z0-9_]*\]\]")

_SELF_EXCLUDE = {"check_no_memory_links.py"}

_SKIP_DIRS = {
    "__pycache__", ".venv", "venv", ".git", "node_modules",
    "intern", "data", "imports", "medicine", "medizin",
}

_DEFAULT_EXTENSIONS = (".py", ".md")


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


def scan_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _WIKILINK_RE.finditer(line):
            findings.append({
                "file": str(path),
                "line": lineno,
                "label": "Wikilink-Syntax des privaten Memory-Systems in "
                         "öffentlicher Datei — Zielknoten existiert für "
                         "Leser:innen nicht (→ Bezug in normaler Prosa "
                         "auflösen oder ganz entfernen)",
                "text": line.strip()[:160],
                "match": match.group(0),
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
        all_findings.extend(scan_file(file))
    return all_findings


def print_report(findings: list[dict], root: Path) -> None:
    if not findings:
        print("✓ check_no_memory_links: keine Findings")
        return

    print(f"⚠ check_no_memory_links: {len(findings)} Finding(s)")
    print()

    def _rel(p: str) -> str:
        try:
            return str(Path(p).relative_to(root))
        except ValueError:
            return p

    for item in findings:
        loc = f"{_rel(item['file'])}:{item['line']}"
        print(f"  {loc}")
        print(f"    {item['label']}")
        print(f"    {item['text']}")
    print()

    print('Siehe docs/CONTRIBUTING.md. Findings beheben.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enforces that private memory-link syntax never reaches the public repo",
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
