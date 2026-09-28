#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
check_source_privacy — Source-Code- und Doku-Privacy-Compliance-Check für Kyoro-HealthHub

@tier        infrastructure
@purpose.de  Prüft Python-Quelldateien UND Doku/Config-Dateien (.md, .json) auf
              Datenschutz-Compliance-Verstöße. Identifiziert: verbotene Bezeichner aus
              privacy_check.forbidden_identifiers (alle Dateitypen), exakte
              Datenmengen-Statistiken über die eigene Nutzung (alle Dateitypen —
              Fund war eine archivierte OpenSpec-tasks.md, kein Skript), hardcodierte
              Person-IDs (Literale 'self' statt OWN_PERSON_ID), hardcodierte
              IANA-Zeitzonen-Strings, Fallback-Dicts mit Entity-IDs (nur .py — diese
              Kategorien sind Code-Konventionen, keine Doku-Fehler).
@purpose.en  Checks Python source files AND doc/config files (.md, .json) for privacy
              compliance violations. Identifies: forbidden identifiers from
              privacy_check.forbidden_identifiers (all file types), exact personal
              data-volume statistics about actual usage (all file types — the
              triggering find was an archived OpenSpec tasks.md, not a script),
              hardcoded person IDs (string literals 'self' instead of
              OWN_PERSON_ID), hardcoded IANA timezone strings, fallback dicts with
              entity IDs (.py only — these categories are code conventions, not
              documentation errors).
@method.de   Lädt verbotene Bezeichner aus ~/.config/kyoro/health_config.json → privacy_check.forbidden_identifiers.
              Scannt standardmäßig das gesamte Repo (.py, .md, .json) — genauer: alle
              git-getrackten Dateien mit diesen Endungen (git ls-files), d.h.
              gitignorte/private Verzeichnisse (intern/, data/, imports/, analyses/,
              exports/, logs/, medicine/, medizin/) fallen automatisch raus, ohne
              hier ein zweites Mal gepflegt werden zu müssen. Statische Checks:
              Hardcodierte Person-IDs in SQL und Zuweisungen, IANA-Zeitzonen-Strings
              (Africa/, America/, etc.), Fallback-Dicts mit Entity-IDs, hartkodierte
              Config-Pfade — alle vier Kategorien nur für .py, da sie Code-Antipatterns
              sind und in Doku-Beispielen (z.B. SQL-Snippets mit person='self' oder
              einer IANA-Zeitzone als dokumentiertem Schema-Default) falsch-positiv wären.
              Der Bezeichner-Check (forbidden_identifiers) läuft auf allen Dateitypen —
              das ist der Mechanismus, der personenbezogene Daten in Markdown/JSON fängt.
              Unterstützt rekursives Scannen von Verzeichnissen, JSON-Ausgabe und Strict-Modus.
              Überspringt eigene Datei (Selbst-Exclude) und spezifische Verzeichnisse.
              Exit-Code: 0 = sauber, 1 = Findings gefunden.
@method.en   Loads forbidden identifiers from ~/.config/kyoro/health_config.json → privacy_check.forbidden_identifiers.
              Scans the whole repo by default (.py, .md, .json) — more precisely,
              all git-tracked files with these extensions (git ls-files), so
              gitignored/private directories (intern/, data/, imports/, analyses/,
              exports/, logs/, medicine/, medizin/) fall out automatically without
              needing to be maintained here a second time. Static checks: hardcoded
              person IDs in SQL and assignments, IANA timezone strings (Africa/,
              America/, etc.), fallback dicts with entity IDs, hardcoded config
              paths — all four categories are .py-only, since they are code
              antipatterns and would false-positive on doc examples (e.g. SQL
              snippets showing person='self' or an IANA timezone as the documented
              schema default).
              The identifier check (forbidden_identifiers) runs on all file types —
              this is the mechanism that catches personal data embedded in
              Markdown/JSON.
              Supports recursive directory scanning, JSON output and strict mode.
              Skips own file (self-exclude) and specific directories.
              Exit code: 0 = clean, 1 = findings found.
@reads       ~/.config/kyoro/health_config.json, alle .py/.md/.json-Dateien im gescannten Verzeichnis
@writes      stdout (Berichte und JSON-Ausgabe)
@limits.de   Kann falsch-positive Ergebnisse liefern (z.B. in t()-Aufrufen oder Kommentaren).
              Dokstrings und Kommentare (.py) werden nicht gescannt. Freitext-Statistiken
              (z.B. "sechs EKG mit AFib") sind nicht mechanisch erkennbar — nur über
              privacy_check.forbidden_identifiers oder menschliches Review.

@relevance.de  Bietet Prüfungsfunktionen für Datenqualität und Datenschutz, essentiell für die Datenintegrität
@relevance.en  Provides verification functions for data quality and privacy, essential for data integrity
@limits.en   May produce false positives (e.g., in t() calls or comments).
              Docstrings and comments (.py) are not scanned. Free-text statistics
              (e.g. "six ECGs with AFib") aren't mechanically detectable — only via
              privacy_check.forbidden_identifiers or human review.
@usage
    python scripts/utils/check_source_privacy.py
    python scripts/utils/check_source_privacy.py --dir /path/to/scan
    python scripts/utils/check_source_privacy.py --json
    python scripts/utils/check_source_privacy.py --strict
    python scripts/utils/check_source_privacy.py --high-only
    python scripts/utils/check_source_privacy.py --ext .py .md .json
    # --dir: Verzeichnis zum Scannen angeben (Standard: Repo-Root)
    # --json: Ausgabe als JSON
    # --strict: Wertet auch low-confidence Findings als Fehler
    # --high-only: Nur high-confidence Findings ausgeben
    # --ext: Zu scannende Dateiendungen (Standard: .py .md .json)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent
_REPO_ROOT = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_SCRIPTS_DIR))
from health_config import KYORO_CONFIG_DIR
_CONFIG_PATH = KYORO_CONFIG_DIR / "health_config.json"

# ---------------------------------------------------------------------------
# Konfig-basierte Bezeichner laden
# ---------------------------------------------------------------------------

def _load_forbidden_identifier_checks() -> list[tuple[re.Pattern, str]]:
    """
    Liest privacy_check.forbidden_identifiers aus health_config.json
    und baut daraus Regex-Muster.

    Eintragsformat im JSON:
      "TERM"         -> Wortgrenze-Regex (exaktes Wort)
      "PREFIX_"      -> Konstanten-Prefix-Regex (z.B. "FOO_" findet FOO_BAR = ...)
    """
    try:
        raw = json.loads(_CONFIG_PATH.read_text())
        terms = raw.get("privacy_check", {}).get("forbidden_identifiers", [])
    except Exception:
        return []

    patterns = []
    for term in terms:
        if not isinstance(term, str) or not term:
            continue
        escaped = re.escape(term)
        if term.endswith("_"):
            # z.B. "FOO_" → findet FOO_BAR = ... (auch _FOO_BAR)
            rx = re.compile(r"(?<![a-zA-Z0-9])" + escaped + r"[A-Z_]*\s*=")
        else:
            # z.B. "LONGCOVID" → findet LONGCOVID, _LONGCOVID, TEST_LONGCOVID
            rx = re.compile(r"(?<![a-zA-Z0-9])" + escaped + r"(?![a-zA-Z0-9])")
        label = f"Unerwünschter Bezeichner: {term!r} (→ privacy_check.forbidden_identifiers)"
        patterns.append((rx, label))
    return patterns


# ---------------------------------------------------------------------------
# Statische (generische) Check-Kategorien
# ---------------------------------------------------------------------------

_STATIC_CHECKS = [
    {
        "category": "Hardcodierte Person-ID",
        "code_only": True,  # Doku zeigt 'self' oft bewusst als dokumentierten Schema-Default
        "description": (
            "OWN_PERSON_ID aus health_config verwenden statt Literal 'self'. "
            "Ausnahme: DEFAULT-Werte in CREATE TABLE."
        ),
        "patterns": [
            (re.compile(r"""(?<!\w)person\s*=\s*['"]self['"]"""),
             "person='self' als Literal (→ OWN_PERSON_ID verwenden)"),
            (re.compile(r"""AND\s+person\s*=\s*['"]self['"]""", re.IGNORECASE),
             "SQL AND person='self' (→ Parameter-Binding + OWN_PERSON_ID)"),
            (re.compile(r"""WHERE\s+person\s*=\s*['"]self['"]""", re.IGNORECASE),
             "SQL WHERE person='self' (→ Parameter-Binding + OWN_PERSON_ID)"),
            (re.compile(r"""(?<!\w)OWN_PERSON_ID\s*=\s*['"]self['"]"""),
             "OWN_PERSON_ID = 'self' — überschreibt den echten Import aus health_config "
             "mit dem Roh-Literal (→ 'from health_config import OWN_PERSON_ID' verwenden)"),
        ],
    },
    {
        "category": "Hardcodierte IANA-Zeitzone",
        "code_only": True,  # Doku/Templates zeigen "Europe/Berlin" bewusst als Beispielwert fürs Schema
        "description": (
            "Zeitzonen-Strings gehören nicht als Literal in den Code. "
            "resolve_timezone(conn, person) aus utils/base.py oder "
            "cfg.home_timezone aus health_config verwenden."
        ),
        "patterns": [
            (
                re.compile(
                    r"""['"](?:Africa|America|Antarctica|Asia|Atlantic|Australia|Europe|Indian|Pacific)/[A-Za-z_/]+['"]"""
                ),
                "IANA-Zeitzone hardcodiert (→ resolve_timezone() oder cfg.home_timezone)",
            ),
        ],
    },
    {
        "category": "Fallback-Dicts mit Entity-IDs",
        "code_only": True,  # Code-Antipattern, in Doku irrelevant
        "description": (
            "Private Dicts mit hardcodierten Entity-IDs oder Sensor-Namen "
            "als Fallback sind de-facto persönliche Daten im Code. "
            "Fehlende Config-Einträge → sys.exit mit Fehlermeldung."
        ),
        "patterns": [
            (re.compile(r"\b_[A-Z][A-Z_]*_DEFAULTS\s*=\s*\{"),
             "_*_DEFAULTS-Dict — prüfen ob Entity-IDs/persönliche Werte enthalten"),
            (re.compile(r"""['"]device_tracker\.[a-z]"""),
             "device_tracker.*-Entity als String-Literal (→ ha_config.json)"),
            (re.compile(r"""['"]person\.[a-z]"""),
             "person.*-Entity als String-Literal (→ ha_config.json)"),
        ],
    },
    {
        "category": "Datenmengen-Statistik (persönliche Nutzungsdaten)",
        # Kein code_only: läuft auf .py UND .md/.json — der eigentliche Fund
        # (37.323.378 Zeilen measurements) stand in einer archivierten
        # OpenSpec-tasks.md, keinem Skript.
        "description": (
            "Präzise Angaben zur tatsächlichen persönlichen Datenmenge (exakte "
            "Zeilen-/Datensatzzahlen, Anzahl getrackter Personen/Geräte) sind reale "
            "Fakten über die eigene Nutzung, auch ohne Namen oder Diagnose. In "
            "Migrations-/Abschlussnotizen eher verallgemeinern (\"~37 Mio.\" statt "
            "\"37.323.378\") oder ganz weglassen, wenn die Präzision für die "
            "Dokumentation nicht nötig ist."
        ),
        "patterns": [
            (re.compile(r"\b\d{1,3}(?:[.,]\d{3}){2,}\b\s*(?:Zeilen|rows|Datensätze|records)", re.IGNORECASE),
             "Exakte große Zeilenzahl mit Tausendertrennzeichen (→ verallgemeinern, z.B. '~X Mio. Zeilen')"),
            (re.compile(r"(?<![-–~>])(?<![-–~>]\s)(?<!in )\b\d{4,}\b(?:\s+\S+){0,1}\s*(?:Zeilen|rows|Datensätze|records|Duplikate|duplicates)\b", re.IGNORECASE),
             "Exakte Zeilen-/Datensatz-/Duplikat-Anzahl (→ verallgemeinern oder weglassen)"),
            (re.compile(r"(?<![-–~>])(?<![-–~>]\s)\b\d+(?:[.,]\d+)?\s*(?:Millionen|Mio\.?|million)\b", re.IGNORECASE),
             "Datenmenge in Millionen genannt (→ prüfen: generische Fachangabe oder echte persönliche Zahl?)"),
        ],
    },
    {
        "category": "Hardcodierter Config-Pfad",
        "code_only": True,  # Code-Antipattern, in Doku irrelevant
        "description": (
            "Alle Konfigurations- und Datenpfade MUSSEN über KYORO_CONFIG_DIR oder "
            "KYORO_MASTER_DIR aus health_config.py resolved werden, nie selbst "
            "mit Path.home() / .config / kyoro konstruiert werden. "
            "Ausnahme: health_config.py selbst."
        ),
        "patterns": [
            (re.compile(r'Path\.home\(\)\s*/\s*".config"\s*/\s*"kyoro"'),
             "Hardcodierter Pfad Path.home() / .config / kyoro (→ KYORO_CONFIG_DIR oder KYORO_MASTER_DIR importieren)"),
        ],
    },
]

# Dateien, die nicht gescannt werden (enthalten Regex-Strings der Muster selbst,
# oder testen den alten Pfad absichtlich). health_config.py definiert
# KYORO_CONFIG_DIR selbst, muss dafür Path.home() nutzen. create_identity_schema.py
# stand hier fälschlich mit drin (Annahme aus Task 2a.6 war falsch) — die Datei
# wurde auf KYORO_CONFIG_DIR umgestellt und braucht die Ausnahme nicht mehr;
# drin lassen hätte eine künftige Regression wieder unsichtbar gemacht.
# test_regression_no_env.py vergleicht KYORO_CONFIG_DIR bewusst gegen den
# hartkodierten alten Standardpfad, um genau die Abwesenheit einer Regression
# nachzuweisen — der hartkodierte Pfad ist hier der Test-Zweck, kein Verstoß.
# test_research_cohort.py baut eine rein synthetische Dummy-Patient:innen-Fixture
# ("Test {pseudo}") zum Testen des k-Anonymität-Exports — die Zeitzone darin ist
# Testdaten, keine echte Konfiguration.
# test_orthostatic_test_spo2_bp.py testet _local_to_utc()/_utc_to_local() (DST-
# bewusste Lokal<->UTC-Konvertierung) — braucht dafuer eine echte, DST-fuehrende
# IANA-Zone als FakeCfg-Fixture; bewusst NICHT das plausible reale Projekt-
# Default gewaehlt, um auch zufaellige Uebereinstimmung mit einer echten
# Installation zu vermeiden.
_SELF_EXCLUDE = {
    "check_source_privacy.py", "check_anonymization.py", "health_config.py",
    "test_regression_no_env.py", "test_research_cohort.py",
    "test_orthostatic_test_spo2_bp.py",
}

# Verzeichnisse überspringen: Build-/VCS-Ordner sowie private/gitignorte
# Verzeichnisse (echte personenbezogene Rohdaten — Funde dort sind erwartet,
# kein Compliance-Fehler, würden aber echte Public-Repo-Funde in der Ausgabe ertränken)
_SKIP_DIRS = {
    "__pycache__", ".venv", "venv", ".git", "node_modules",
    "intern", "data", "imports", "medicine", "medizin",
}

# Standardmäßig gescannte Dateiendungen — deckt alle Endungen ab, die
# aktuell im getrackten Repo vorkommen (per `git ls-files`), damit jede
# Datei, die im öffentlichen Repo landet, dem Privacy-/Pre-Commit-Scan
# unterliegt. Ausgenommen: reine Binär-/Platzhalterdateien (.png,
# .gitkeep, .gitignore) ohne Freitext-Risiko.
_DEFAULT_EXTENSIONS = (
    ".py", ".md", ".json", ".yaml", ".yml", ".sh", ".csv", ".txt",
    ".ps1", ".ini", ".service", ".example",
)

_T_CALL_RE = re.compile(r"\bt\s*\(")


# ---------------------------------------------------------------------------
# Scan-Logik
# ---------------------------------------------------------------------------

def _build_checks(dynamic: list[tuple], is_code: bool = True) -> list[dict]:
    # Code-only-Kategorien (Antipatterns wie person='self', Fallback-Dicts) sind in
    # Doku-Dateien (.md/.json) fachlich falsch-positiv — z.B. zeigt CONTRIBUTING.md
    # bewusst 'self' als dokumentierten Schema-Default, keinen Code-Verstoß.
    checks = [c for c in _STATIC_CHECKS if is_code or not c.get("code_only")]
    if dynamic:
        checks.insert(0, {
            "category": "Konfigurierte Bezeichner (privacy_check.forbidden_identifiers)",
            "description": "Aus ~/.config/kyoro/health_config.json geladene Bezeichner.",
            "patterns": dynamic,
        })
    return checks


def _code_part(line: str) -> str:
    """Gibt den Code-Teil einer Zeile zurück (Inline-Kommentar abschneiden)."""
    in_str: str | None = None
    escape = False
    for i, ch in enumerate(line):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch in ('"', "'") and in_str is None:
            in_str = ch
        elif ch == in_str:
            in_str = None
        elif ch == "#" and in_str is None:
            return line[:i]
    return line


def scan_file(path: Path, checks: list[dict], strict: bool = False, is_code: bool = True) -> list[dict]:
    """Scannt eine einzelne Datei und gibt alle Findings zurück.

    is_code=False (.md/.json u.ä.): kein Docstring-/Kommentar-Tracking — Markdown
    kennt keine Python-Kommentare, und ein '#' ist dort eine Überschrift, kein
    Kommentarzeichen; ein Python-Docstring-Beispiel *innerhalb* eines Markdown-
    Codeblocks würde sonst die Zeilenerkennung fälschlich abschalten.
    """
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    lines = text.splitlines()
    in_docstring = False
    docstring_char: str | None = None

    for lineno, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()

        if is_code:
            # Docstring-Tracking (triple-quote)
            for delim in ('"""', "'''"):
                count = stripped.count(delim)
                if not in_docstring and count >= 1:
                    in_docstring = True
                    docstring_char = delim
                    if count >= 2:
                        in_docstring = False
                    break
                elif in_docstring and docstring_char == delim and count >= 1:
                    in_docstring = False
                    break

            if not stripped or stripped.startswith("#"):
                continue
            if in_docstring:
                continue

            code = _code_part(raw_line)
        else:
            if not stripped:
                continue
            code = raw_line

        for check in checks:
            for pattern, label in check["patterns"]:
                if not pattern.search(code):
                    continue

                in_t_call = bool(_T_CALL_RE.search(code))
                confidence = "low" if (in_t_call and not strict) else "high"

                findings.append({
                    "file": str(path),
                    "line": lineno,
                    "category": check["category"],
                    "label": label,
                    "text": raw_line.rstrip(),
                    "confidence": confidence,
                })

    return findings


def _tracked_files(root: Path, extensions: tuple[str, ...]) -> list[Path] | None:
    """Git-getrackte Dateien mit den angegebenen Endungen, oder None wenn `root`
    kein Git-Repo ist (dann rglob-Fallback in scan_directory).

    Bevorzugt gegenüber rglob + manueller Skip-Liste, weil es exakt widerspiegelt,
    was tatsächlich öffentlich wird — .gitignore-Verzeichnisse (intern/, data/,
    imports/, analyses/, exports/, logs/, ...) werden automatisch übersprungen,
    ohne sie hier ein zweites Mal pflegen zu müssen.
    """
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


def scan_directory(
    scripts_dir: Path,
    strict: bool = False,
    extensions: tuple[str, ...] = _DEFAULT_EXTENSIONS,
) -> list[dict]:
    """Scannt alle Dateien mit den angegebenen Endungen im Verzeichnis rekursiv."""
    dynamic = _load_forbidden_identifier_checks()
    checks_by_ext = {ext: _build_checks(dynamic, is_code=(ext == ".py")) for ext in extensions}

    tracked = _tracked_files(scripts_dir, extensions)
    candidates = tracked if tracked is not None else [
        file for ext in extensions for file in scripts_dir.rglob(f"*{ext}")
    ]

    all_findings: list[dict] = []
    for file in sorted(candidates):
        if any(part in _SKIP_DIRS for part in file.parts):
            continue
        if file.name in _SELF_EXCLUDE:
            continue
        ext = file.suffix
        all_findings.extend(
            scan_file(file, checks_by_ext[ext], strict=strict, is_code=(ext == ".py"))
        )
    return all_findings


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------

def print_report(findings: list[dict], scripts_dir: Path | None = None) -> None:
    high = [f for f in findings if f["confidence"] == "high"]
    low  = [f for f in findings if f["confidence"] == "low"]

    if not findings:
        print("✓ Source-Code Privacy-Check: keine Findings")
        return

    base = scripts_dir or _SCRIPTS_DIR.parent

    def _rel(p: str) -> str:
        try:
            return str(Path(p).relative_to(base))
        except ValueError:
            return p

    print(f"⚠  Source-Code Privacy-Check: {len(high)} Finding(s)"
          + (f" + {len(low)} low-confidence (in t()-Labels)" if low else ""))
    print()

    by_cat: dict[str, list[dict]] = {}
    for f in findings:
        by_cat.setdefault(f["category"], []).append(f)

    for cat, items in by_cat.items():
        h = sum(1 for i in items if i["confidence"] == "high")
        l = sum(1 for i in items if i["confidence"] == "low")
        suffix = f" ({h} high" + (f", {l} low" if l else "") + ")"
        print(f"── {cat}{suffix} {'─' * max(0, 55 - len(cat))}")
        for item in items:
            conf_tag = "" if item["confidence"] == "high" else "  [low-confidence: evtl. t()-Label]"
            print(f"  {_rel(item['file'])}:{item['line']}{conf_tag}")
            print(f"    {item['label']}")
            print(f"    {item['text'].strip()[:120]}")
        print()

    if low:
        print("Hinweis: low-confidence Findings erscheinen in t(\"DE\",\"EN\")-Aufrufen.")
        print("         Prüfen ob der Match im Label oder als tatsächlicher Wert vorkommt.")
        print("         --strict flaggt auch diese als Fehler.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Source-Code- und Doku-Privacy-Compliance-Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=_REPO_ROOT,
        help=f"Verzeichnis zum Scannen (Standard: Repo-Root, {_REPO_ROOT})",
    )
    parser.add_argument(
        "--ext",
        nargs="+",
        default=list(_DEFAULT_EXTENSIONS),
        help=f"Zu scannende Dateiendungen (Standard: {' '.join(_DEFAULT_EXTENSIONS)})",
    )
    parser.add_argument("--json",      action="store_true", help="Ausgabe als JSON")
    parser.add_argument("--strict",    action="store_true",
                        help="Auch low-confidence Findings als Fehler werten")
    parser.add_argument("--high-only", action="store_true",
                        help="Nur high-confidence Findings ausgeben")
    args = parser.parse_args()

    extensions = tuple(e if e.startswith(".") else f".{e}" for e in args.ext)
    findings = scan_directory(args.dir, strict=args.strict, extensions=extensions)

    if args.high_only:
        findings = [f for f in findings if f["confidence"] == "high"]

    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    else:
        print_report(findings, scripts_dir=args.dir)

    high_count = sum(1 for f in findings if f["confidence"] == "high")
    sys.exit(1 if (high_count > 0 or (args.strict and findings)) else 0)


if __name__ == "__main__":
    main()
