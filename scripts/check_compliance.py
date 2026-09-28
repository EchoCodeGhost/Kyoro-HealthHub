#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Compliance-Prüfskript für Docstrings im Kyoro-HealthHub

Prüft Docstrings auf Einhaltung von Datenschutz- und Compliance-Richtlinien:
- Keine medizinischen Diagnosen
- Keine demografischen Merkmale
- Keine Altersangaben
- Keine geografischen Standorte

Usage:
    python scripts/check_compliance.py
    python scripts/check_compliance.py --path scripts/    # Bestimmtes Verzeichnis
    python scripts/check_compliance.py --quiet           # Nur Fehler anzeigen
    python scripts/check_compliance.py --stats           # Statistik anzeigen
    python scripts/check_compliance.py --review          # Human-in-the-loop: neue Treffer einzeln freigeben

Exit Codes:
    0: Alle Docstrings sind compliant (oder alle Treffer per Baseline freigegeben)
    1: Compliance-Verstöße gefunden (mind. ein nicht freigegebener Treffer)
    2: kritischer Fehler (z.B. Verzeichnis nicht gefunden)

@tier        infrastructure
@purpose.de  Prüft alle Docstrings auf Compliance-Verletzungen (medizinische Diagnosen, demografische Merkmale, Altersangaben, geografische Standorte)
@purpose.en  Checks all docstrings for compliance violations (medical diagnoses, demographic data, age data, geographic locations)
@method.de   Durchsucht rekursiv Python-Dateien, extrahiert Modul-Docstrings via AST,
             prüft auf verbotene Inhalte: medizinische Diagnosen (ME/CFS, POTS, etc.),
             demografische Daten, Altersdaten, geografische Standorte. Bekannte
             Fehlalarme können per --review manuell als Baseline freigegeben werden
             (compliance_baseline.json, an einen Hash des jeweiligen Docstrings
             gebunden — ändert sich der Docstring, verfällt die Freigabe automatisch).
@method.en   Recursively scans Python files, extracts module docstrings via AST,
             checks for forbidden content: medical diagnoses (ME/CFS, POTS, etc.),
             demographic data, age data, geographic locations. Known false positives
             can be manually approved via --review into a baseline
             (compliance_baseline.json, bound to a hash of that docstring — if the
             docstring changes, the approval automatically expires).
@reads       Alle Python-Dateien in den angegebenen Verzeichnissen, compliance_baseline.json
@writes      STDERR/STDOUT (Fehlermeldungen und Statistik), compliance_baseline.json (nur bei --review)
@limits.de   Erkennt nur offensichtliche Verstöße. Falsch-positive möglich.
             Keine semantische Analyse, nur Pattern-Matching. Die Baseline verhindert
             falsches Rot, ersetzt aber keine echte Pattern-Verbesserung — sie
             dokumentiert nur, dass ein Mensch den konkreten Treffer geprüft hat.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Only detects obvious violations. False positives possible.
             No semantic analysis, only pattern matching. The baseline prevents
             false failures but does not replace actually improving the patterns —
             it only records that a human reviewed that specific match.
@usage
    python scripts/check_compliance.py
    python scripts/check_compliance.py --path scripts/
    python scripts/check_compliance.py --stats
    python scripts/check_compliance.py --review
"""

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_BASELINE_PATH = Path("compliance_baseline.json")


@dataclass
class ComplianceResult:
    """Ergebnis der Compliance-Prüfung einer Datei."""
    filepath: Path
    is_compliant: bool
    violations: List[str] = field(default_factory=list)
    docstring_hash: Optional[str] = None
    new_violations: List[str] = field(default_factory=list)
    approved_violations: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        status = "✅" if self.is_compliant else "❌"
        return f"{status} {self.filepath.relative_to(self.filepath.cwd())}: {len(self.violations)} violations"


def _docstring_hash(docstring: str) -> str:
    return hashlib.sha256(docstring.encode("utf-8")).hexdigest()


def load_baseline(baseline_path: Path) -> Dict[str, dict]:
    """Lädt die Baseline manuell freigegebener Treffer. Fehlt die Datei, leere Baseline."""
    if not baseline_path.exists():
        return {}
    try:
        return json.loads(baseline_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(f"Warnung: {baseline_path} ist beschädigt, ignoriere sie.", file=sys.stderr)
        return {}


def save_baseline(baseline_path: Path, baseline: Dict[str, dict]) -> None:
    baseline_path.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def approved_for_file(baseline: Dict[str, dict], rel_path: str, docstring_hash: str) -> set:
    """Gibt die Menge freigegebener Violation-Strings für eine Datei zurück —
    nur wenn der Docstring seit der Freigabe unverändert ist (Hash-Match).
    Sonst (Datei neu in Baseline, oder Docstring seither geändert) leere Menge:
    die Freigabe ist verfallen und muss erneut geprüft werden."""
    entry = baseline.get(rel_path)
    if not entry or entry.get("docstring_hash") != docstring_hash:
        return set()
    return set(entry.get("approved", []))


# Verbotenes: Medizinische Diagnosen (nur spezifische Diagnosen, nicht allgemeine Begriffe)
MEDICAL_DIAGNOSES: List[str] = [
    r'Diagnose\s*[:\s]',
    r'Diagnosis\s*[:\s]',
    r'Patient\s',
    r'Patientin\s',
    r'Patienten\s',
    r'[Dd]iagnostiziert',
    r'diagnosed with',
    r'leidet an',
    r'suffers from',
    r'Erkrankung\s',
    r'disease\s',
    r'Krankheit\s',
    r'illness\s',
    r'Klinik\s',
    r'Krankenhaus\s',
    r'Hospital\s',
    r'Arzt\s',
    r'Doctor\s',
    r'Ärzte\s',
    r'Doctors\s',
    r'Therapie\s',
    r'therapy\s',
    r'Behandlung\s',
    r'treatment\s',
    r'Medikation\s',
]

# Verbotenes: Demografische Merkmale (Geschlecht)
GENDER_TERMS: List[str] = [
    r'\bMann\b|\bMänner\b',
    r'\bFrau\b|\bFrauen\b',
    r'\bweiblich\b',
    r'\bmännlich\b',
    r'\bfemale\b',
    r'\bmale\b',
    r'\bgender\b',
    r'\bGeschlecht\b',
]

# Verbotenes: Altersangaben
AGE_TERMS: List[str] = [
    r'\b\d+\s*(Jahre|Jahr|years|year)\b',
    r'\b\d+\s*Jahre alt\b',
    r'\b\d+\s*years old\b',
    r'\bAlter\b',
    r'\bage\b',
    r'\b\d+\s*Jährig\b',
    r'\b\d+\-\d+\s*(Jahre|Jahr)\b',
    r'\bAltersbereich\b',
    r'\bage range\b',
    r'\bKind\b|\bKinder\b',
    r'\bErwachsene\b|\bErwachsener\b',
    r'\badult\b',
    r'\bchild\b|\bchildren\b',
    r'\bÄltere\b|\bSenioren\b',
    r'\belderly\b|\bsenior\b',
]

# Verbotenes: Geographische Orte (nur wenn nicht in technische Kontexte wie Zeitzonen)
# Erlaubt: Europe/Berlin in Zeitzonen-Kontext (z.B. "Europe/Berlin timezone")
# Verboten: geographische Orte in medizinischem Kontext
LOCATION_TERMS: List[str] = [
    r'\bKrankenhaus\b',
    r'\bKlinik\b',
    r'\bPraxis\b',
    # Landes- und Stadtnamen nur wenn sie nicht in technical paths/variablen vorkommen
    # Wir prüfen den Kontext in der check_compliance Funktion
]

# Alle verbotenen Patterns
FORBIDDEN_PATTERNS: Dict[str, List[str]] = {
    "Medical Diagnoses": MEDICAL_DIAGNOSES,
    "Gender Information": GENDER_TERMS,
    "Age Information": AGE_TERMS,
    "Geographic Locations": LOCATION_TERMS,
}


def extract_docstring(source: str) -> Optional[str]:
    """Extrahiert den Modul-Docstring aus einer Python-Datei."""
    try:
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree)
        if docstring:
            return docstring
    except SyntaxError:
        pass
    return None


def check_compliance(docstring: str, filepath: Path) -> List[str]:
    """Prüft einen Docstring auf Compliance-Verletzungen."""
    violations = []
    
    if not docstring:
        return violations
    
    # Konvertiere zu Lowercase für Kontextprüfungen
    docstring_lower = docstring.lower()
    
    for category, patterns in FORBIDDEN_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, docstring, re.IGNORECASE)
            for match in matches:
                match_str = str(match)
                # Filtere leere Matches
                if not match_str.strip():
                    continue
                
                # Spezielle Behandlung für medizinische Begriffe wie POTS, PEM, ME/CFS
                # Diese sind in technischen Kontexten erlaubt
                if category == "Medical Diagnoses" and match_str.upper() in ['POTS', 'PEM', 'ME/CFS']:
                    # Prüfe, ob es in einem medizinischen Diagnose-Kontext steht
                    # Erlaubt: "@purpose.de Erkennt POTS-Kriterium"
                    # Verboten: "Diagnose: POTS bei Patienten"
                    if 'diagnose' in docstring_lower or 'diagnosis' in docstring_lower:
                        violations.append(f"{category}: '{match_str}' (found in diagnosis context)")
                    elif 'patient' in docstring_lower:
                        violations.append(f"{category}: '{match_str}' (found with patient context)")
                    # Sonst ist es OK (technischer Begriff)
                    continue
                
                # Prüfe auf falsch-positive für technische Kontexte
                # 1. Zeitzonen (Europe/Berlin, UTC, etc.)
                if any(tz in docstring_lower for tz in ['timezone', 'utc+', 'utc-', 'gmt', 'cet', 'cest']):
                    # Wenn der Treffer in einer Zeitzonen-Definition ist, ignorieren
                    if match_str in ['Europe', 'Berlin', 'Germany', 'Deutschland', 'USA', 'America']:
                        continue
                
                # 2. Technische Einheiten (J = Joule, nicht Jahr)
                if match_str.endswith('J') and len(match_str) <= 3:
                    # Prüfe Kontext: ist es eine Einheit?
                    # Erlaubt: "5 J" (Joule), "10 J/m"
                    # Verboten: "18 J" (18 Jahre)
                    import re as re_module
                    # Suche nach Pattern wie "\d+ J" ohne "Jahre"
                    if re_module.search(r'\b\d+\s*' + re_module.escape(match_str) + r'\b', docstring):
                        # Prüfe ob es "Jahre" oder "year" in der Nähe gibt
                        # Wenn nicht, könnte es Joule sein
                        lines = docstring.split('\n')
                        found_age_context = False
                        for line in lines:
                            if match_str in line and ('jahr' in line.lower() or 'year' in line.lower()):
                                found_age_context = True
                                break
                        if not found_age_context:
                            continue  # Wahrscheinlich Joule, nicht Jahr
                
                # 3. Pfade und Dateinamen (scripts/, /home/, etc.)
                if '/' in docstring or '\\' in docstring:
                    # Prüfe ob der Treffer Teil eines Pfades ist
                    if match_str in ['Europe', 'Berlin', 'Germany']:
                        # Erlaubt in Pfaden wie "zoneinfo/Europe/Berlin"
                        if f'europe/{match_str.lower()}' in docstring_lower or \
                           f'zoneinfo/{match_str.lower()}' in docstring_lower or \
                           match_str.lower() in ['europe/berlin', 'europe/berlin']:
                            continue
                
                # Standardmäßig hinzufügen
                violations.append(f"{category}: '{match_str}'")
    
    return violations


def validate_file(filepath: Path, baseline: Dict[str, dict], repo_root: Path) -> ComplianceResult:
    """Validiert eine Python-Datei auf Compliance und trennt Treffer in
    'approved' (per Baseline freigegeben, Docstring seither unverändert)
    und 'new' (muss geprüft werden, zählt für den Exit-Code)."""
    if not filepath.suffix == ".py":
        return ComplianceResult(filepath=filepath, is_compliant=True)

    # Skip self-check to avoid false positives from pattern definitions
    if filepath.name == "check_compliance.py":
        return ComplianceResult(filepath=filepath, is_compliant=True)

    try:
        source = filepath.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return ComplianceResult(filepath=filepath, is_compliant=True, violations=[f"Cannot read file: {filepath}"])

    docstring = extract_docstring(source) or ""
    violations = check_compliance(docstring, filepath)

    if not violations:
        return ComplianceResult(filepath=filepath, is_compliant=True)

    doc_hash = _docstring_hash(docstring)
    try:
        rel_path = str(filepath.resolve().relative_to(repo_root))
    except ValueError:
        rel_path = str(filepath)

    approved = approved_for_file(baseline, rel_path, doc_hash)
    new_violations = [v for v in violations if v not in approved]
    approved_violations = [v for v in violations if v in approved]

    return ComplianceResult(
        filepath=filepath,
        is_compliant=len(new_violations) == 0,
        violations=violations,
        docstring_hash=doc_hash,
        new_violations=new_violations,
        approved_violations=approved_violations,
    )


def _match_context_lines(docstring: str, match_str: str) -> List[str]:
    """Gibt die Docstring-Zeilen zurück, die den Treffer enthalten (für --review)."""
    return [ln.strip() for ln in docstring.splitlines() if match_str in ln]


def run_review(all_results: List[ComplianceResult], baseline: Dict[str, dict],
              baseline_path: Path, repo_root: Path) -> None:
    """Human-in-the-loop: geht jeden noch nicht freigegebenen Treffer einzeln
    durch und lässt ihn interaktiv als Fehlalarm freigeben oder offen lassen.
    Speichert die Baseline nach jeder Entscheidung (kein Datenverlust bei
    Abbruch mitten im Review)."""
    to_review = [r for r in all_results if r.new_violations]
    if not to_review:
        print("Keine neuen (noch nicht freigegebenen) Treffer — nichts zu reviewen.")
        return

    total = sum(len(r.new_violations) for r in to_review)
    print(f"\n{total} neue(r) Treffer in {len(to_review)} Datei(en) zum Review.\n"
          "Für jeden Treffer: [j]a freigeben (Fehlalarm) / [n]ein (Skript muss noch angepasst werden) / "
          "[q]uit (Rest überspringen, bisherige Entscheidungen bleiben gespeichert)\n")

    quit_early = False
    for result in to_review:
        if quit_early:
            break
        try:
            rel_path = str(result.filepath.resolve().relative_to(repo_root))
        except ValueError:
            rel_path = str(result.filepath)
        docstring = extract_docstring(result.filepath.read_text(encoding="utf-8")) or ""

        for violation in list(result.new_violations):
            print(f"\n{rel_path}")
            print(f"  ❌ {violation}")
            match_str = violation.split("'", 1)[1].rsplit("'", 1)[0] if "'" in violation else ""
            for ctx in _match_context_lines(docstring, match_str)[:3]:
                print(f"    │ {ctx}")

            ans = input("  Fehlalarm, freigeben? [j/n/q]: ").strip().lower()
            if ans in ("q", "quit"):
                quit_early = True
                break
            if ans in ("j", "ja", "y", "yes"):
                entry = baseline.setdefault(rel_path, {"docstring_hash": result.docstring_hash, "approved": []})
                entry["docstring_hash"] = result.docstring_hash
                if violation not in entry["approved"]:
                    entry["approved"].append(violation)
                save_baseline(baseline_path, baseline)  # sofort speichern, kein Verlust bei Abbruch
                result.new_violations.remove(violation)
                result.approved_violations.append(violation)

    print(f"\nBaseline gespeichert: {baseline_path}")


def main():
    """Hauptfunktion für die Compliance-Prüfung."""
    parser = argparse.ArgumentParser(description='Compliance check for docstrings')
    parser.add_argument('--path', type=str, default='scripts', help='Verzeichnis zum Prüfen (default: scripts)')
    parser.add_argument('--quiet', action='store_true', help='Nur Fehler anzeigen')
    parser.add_argument('--stats', action='store_true', help='Statistik anzeigen')
    parser.add_argument('--baseline', type=str, default=str(DEFAULT_BASELINE_PATH),
                        help=f'Pfad zur Baseline-Datei (default: {DEFAULT_BASELINE_PATH})')
    parser.add_argument('--review', action='store_true',
                        help='Human-in-the-loop: neue Treffer einzeln interaktiv freigeben')
    args = parser.parse_args()

    base_dir = Path(args.path)
    if not base_dir.exists():
        print(f"Error: {base_dir} does not exist", file=sys.stderr)
        sys.exit(2)

    repo_root = Path.cwd()
    baseline_path = Path(args.baseline)
    baseline = load_baseline(baseline_path)

    all_results = []
    total_files = 0
    compliant_files = 0

    print("Checking compliance...")

    for py_file in base_dir.rglob("*.py"):
        total_files += 1
        result = validate_file(py_file, baseline, repo_root)
        all_results.append(result)
        if result.is_compliant:
            compliant_files += 1

    if args.review:
        run_review(all_results, baseline, baseline_path, repo_root)
        # Nach dem Review neu auswerten (approved_violations wurden live umgehängt)
        compliant_files = sum(1 for r in all_results if not r.new_violations)

    new_violations_total = sum(len(r.new_violations) for r in all_results)
    approved_total = sum(len(r.approved_violations) for r in all_results)
    violations_by_category: Dict[str, int] = {cat: 0 for cat in FORBIDDEN_PATTERNS.keys()}
    for result in all_results:
        for violation in result.new_violations:
            for category in FORBIDDEN_PATTERNS.keys():
                if violation.startswith(category):
                    violations_by_category[category] += 1
                    break

    # Ausgabe
    print(f"\n{'='*80}")
    print("📊 COMPLIANCE REPORT")
    print(f"{'='*80}")
    print(f"📁 Scanned: {total_files} files")
    print(f"✅ Compliant: {compliant_files}/{total_files} ({compliant_files/total_files*100:.1f}%)")
    print(f"❌ Non-compliant (new): {total_files-compliant_files}/{total_files} ({(total_files-compliant_files)/total_files*100:.1f}%)")
    print(f"📝 New violations: {new_violations_total}")
    if approved_total:
        print(f"✔️  Freigegeben via Baseline: {approved_total} (siehe {baseline_path})")

    if violations_by_category:
        print("\n📊 New violations by category:")
        for category, count in violations_by_category.items():
            if count > 0:
                print(f"  {category}: {count}")

    if not args.quiet:
        if not args.stats:
            print(f"\n{'='*80}")
            print("🚨 NEW VIOLATIONS (nicht in der Baseline):")
            print(f"{'='*80}")

            for result in all_results:
                if result.new_violations:
                    try:
                        rel_path = result.filepath.relative_to(Path.cwd())
                    except ValueError:
                        rel_path = result.filepath
                    print(f"\n{rel_path}:")
                    for violation in result.new_violations:
                        print(f"  ❌ {violation}")

    if new_violations_total > 0:
        print(f"\n⚠️  {new_violations_total} neue(r) Compliance-Verstoß/Verstöße gefunden! "
              f"Mit --review einzeln pruefen und freigeben.")
        sys.exit(1)
    else:
        print("\n✅ All docstrings are compliant (nach Baseline)!")
        sys.exit(0)


if __name__ == "__main__":
    main()
