#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_icd_codes.py — ICD-10-GM-Code↔Text-Review-Checker für Kandidaten-JSON

@tier        infrastructure
@purpose.de  Scannt eine Kandidaten-JSON von import_billed_diagnoses.py
             (Stufe 1, vor --commit) und meldet pro diagnoses-Zeile, ob der
             icd_code real existiert UND ob description inhaltlich zum
             amtlichen Titel dieses Codes passt -- der eigentliche
             "ICD-Checker", der weder import_billed_diagnoses.py's
             ICD_RE (nur Format) noch dessen _looks_bundled() (nur
             Struktur-Signal "mehrere Diagnosen zusammengezogen") leisten
             kann: eine Code↔Text-Fehlzuordnung mit nur EINER (nicht
             mehreren) Diagnose bleibt sonst unsichtbar.
@purpose.en  Scans a candidate JSON from import_billed_diagnoses.py (stage
             1, before --commit) and reports per diagnoses row whether
             icd_code actually exists AND whether description content-wise
             matches that code's official title -- the actual "ICD
             checker" that neither import_billed_diagnoses.py's ICD_RE
             (format only) nor its _looks_bundled() (structural signal
             "several diagnoses merged together" only) can provide: a
             code↔text misassignment involving only ONE (not several)
             diagnosis would otherwise stay invisible.
@method.de   Pro diagnoses-Zeile (table=="diagnoses"): modules.icd10_catalog.is_known()/
             lookup()/.check_description_plausible()/.check_bundled_contamination().
             Fünf Ausgabekategorien: UNBEKANNTER CODE (Code existiert nicht
             im geladenen ICD-10-GM-Jahrgang -- fängt z.B. OCR-verwechselte
             Ziffern, die trotzdem das Regex-Format treffen), NICHT-
             TERMINALER CODE (Code existiert, aber nur als Kategorie-
             Überschrift ohne fünfte Stelle -- laut Metadaten-Feld 13/14
             nicht zur Verschlüsselung zugelassen, z.B. "F60.3" statt
             "F60.31"), GEBÜNDELT/KONTAMINIERT (geprüft VOR Text-Mismatch:
             description enthält die zum Code passende Diagnose, aber
             zusätzlich Text fremder Diagnosen -- check_description_plausible()
             allein würde das als "plausibel" werten, weil die passenden
             Wörter ja irgendwo in der Mitte des längeren Textes stehen),
             TEXT-MISMATCH (Code existiert, aber description teilt kein
             Inhaltswort mit dem amtlichen Titel -- Zeilen mit dem
             Platzhalter "(nicht automatisch zuordenbar)" werden
             übersprungen, da dort gar kein Text zum Vergleichen vorliegt),
             sowie, falls kein Katalog installiert ist, ein einmaliger
             Hinweis auf update_icd10_catalog.py statt stiller Null-
             Treffer. Ändert NICHTS an der Kandidaten-Datei -- reiner
             Report, die Entscheidung (Text korrigieren, Code korrigieren,
             als false positive ignorieren) bleibt bei der Nutzerin.
@method.en   Per diagnoses row (table=="diagnoses"): modules.icd10_catalog.is_known()/
             lookup()/.check_description_plausible()/.check_bundled_contamination().
             Five report categories: UNKNOWN CODE (code doesn't exist in
             the loaded ICD-10-GM year -- catches e.g. OCR-confused digits
             that still match the regex shape), NON-TERMINAL CODE (code
             exists but only as a category header without a fifth digit --
             per metadata field 13/14 not valid for encoding, e.g. "F60.3"
             instead of "F60.31"), BUNDLED/CONTAMINATED (checked BEFORE
             text mismatch: description contains the diagnosis matching the
             code, but also text from unrelated diagnoses --
             check_description_plausible() alone would call this
             "plausible", since the matching words do sit somewhere in the
             middle of the longer text), TEXT MISMATCH (code exists, but
             description shares no content word with the official title --
             rows with the "(nicht automatisch zuordenbar)" placeholder are
             skipped, since there's no text to compare at all), and, if no
             catalog is installed, a single pointer to
             update_icd10_catalog.py instead of silent zero hits. Changes
             NOTHING in the candidate file -- pure report, the decision
             (fix the text, fix the code, ignore as a false positive) stays
             with the user.
@reads       imports/manual/billed_diagnoses_candidates.json (Default, oder
             --file); data/reference/icd10gm/ (über modules.icd10_catalog)
@writes      keine Tabellen (reiner Report nach stdout)
@limits.de   Erkennt nur, was modules.icd10_catalog erkennen kann -- siehe
             dessen @limits (Wortüberlappungs-Heuristik, kein semantischer
             Vergleich; nur Codes der installierten Jahresversion). Ein
             Mismatch-Report ist ein Hinweis, keine automatische Korrektur
             -- manche echten Diagnosetexte (z.B. ein vollständiger
             Arztbrief-Satz statt des knappen amtlichen Kurztitels) teilen
             zufällig kein Inhaltswort und werden als False Positive
             gemeldet.
@limits.en   Only detects what modules.icd10_catalog can detect -- see its
             @limits (word-overlap heuristic, not a semantic comparison;
             only codes from the installed year). A mismatch report is a
             hint, not an automatic correction -- some genuine diagnosis
             texts (e.g. a full doctor's-letter sentence instead of the
             terse official short title) can share no content word by
             chance and get reported as a false positive.

@relevance.de  Macht Code↔Text-Fehlzuordnungen sichtbar, die sonst erst beim zufälligen Drüberlesen auffallen (wie im F32.9-Fall), essentiell vor --commit
@relevance.en  Surfaces code↔text misassignments that would otherwise only be caught by chance while skimming (as in the F32.9 case), essential before --commit
@usage
    python3 check_icd_codes.py
    python3 check_icd_codes.py --file imports/manual/andere_kandidaten.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from health_config import Config as _Cfg  # noqa: E402
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402
from modules.icd10_catalog import (  # noqa: E402
    is_available, is_known, lookup, check_description_plausible, check_bundled_contamination,
)

_cfg = _Cfg()
DEFAULT_CANDIDATES_PATH = _cfg.data_root / "manual" / "billed_diagnoses_candidates.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "ICD-10-GM-Code↔Text-Plausibilität einer Kandidaten-JSON prüfen",
        "Check ICD-10-GM code↔text plausibility of a candidate JSON",
    ))
    parser.add_argument("--file", type=Path, default=DEFAULT_CANDIDATES_PATH,
                        help=t("Kandidaten-JSON (Default: billed_diagnoses_candidates.json)",
                               "Candidate JSON (default: billed_diagnoses_candidates.json)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if not is_available():
        print(t(
            "Kein lokaler ICD-10-GM-Katalog installiert. Erst ausführen:\n"
            "  python3 update_icd10_catalog.py --download --accept-terms\n"
            "oder:\n"
            "  python3 update_icd10_catalog.py --from-zip <pfad-zur-zip>",
            "No local ICD-10-GM catalog installed. Run first:\n"
            "  python3 update_icd10_catalog.py --download --accept-terms\n"
            "or:\n"
            "  python3 update_icd10_catalog.py --from-zip <path-to-zip>",
        ))
        sys.exit(1)

    if not args.file.exists():
        print(t(f"Nicht gefunden: {args.file}", f"Not found: {args.file}"))
        sys.exit(1)
    rows = json.loads(args.file.read_text(encoding="utf-8"))

    # Literal wie in import_billed_diagnoses.py -- dort kein benannter
    # Platzhalter, nur zweifach dasselbe Literal, siehe dort "description"/
    # "drug_name". Ohne Ausschluss waere jede description-lose Zeile ein
    # Text-Mismatch-"Treffer" ohne jeden Erkenntniswert (kein Text da, nicht
    # falscher Text).
    NO_TEXT_PLACEHOLDER = "(nicht automatisch zuordenbar)"

    unknown, non_terminal, mismatch, bundled, ok = [], [], [], [], 0
    for r in rows:
        if r.get("table") != "diagnoses":
            continue
        code = r.get("icd_code")
        if not code:
            continue
        known = is_known(code)
        if not known:
            unknown.append(r)
            continue
        if not lookup(code)["terminal"]:
            non_terminal.append(r)
        description = r.get("description") or ""
        if description == NO_TEXT_PLACEHOLDER:
            continue
        is_bundled, official_title = check_bundled_contamination(code, description)
        if is_bundled:
            bundled.append((r, official_title))
            continue
        plausible, official_title = check_description_plausible(code, description)
        if plausible is False:
            mismatch.append((r, official_title))
        else:
            ok += 1

    print(t(f"{ok} Codes plausibel, {len(unknown)} unbekannt, {len(non_terminal)} nicht-terminal, "
            f"{len(mismatch)} Text-Mismatch, {len(bundled)} gebündelt/kontaminiert\n",
            f"{ok} codes plausible, {len(unknown)} unknown, {len(non_terminal)} non-terminal, "
            f"{len(mismatch)} text mismatches, {len(bundled)} bundled/contaminated\n"))

    if unknown:
        print(t("UNBEKANNTER CODE (existiert nicht im geladenen ICD-10-GM-Jahrgang):",
                "UNKNOWN CODE (doesn't exist in the loaded ICD-10-GM year):"))
        for r in unknown:
            print(f"  {r.get('icd_code')} · {t('Zeile', 'line')} {r.get('source_line')} "
                  f"({r.get('source_file')}) · {r.get('description', '')[:80]}")
        print()

    if non_terminal:
        print(t("NICHT-TERMINALER CODE (Code existiert nur als Kategorie-Überschrift, "
                "eigentlich nicht zur Abrechnung zugelassen -- ggf. fehlt eine fünfte Stelle):",
                "NON-TERMINAL CODE (code exists only as a category header, not actually "
                "valid for billing -- a fifth digit may be missing):"))
        for r in non_terminal:
            print(f"  {r.get('icd_code')} · {t('Zeile', 'line')} {r.get('source_line')} "
                  f"({r.get('source_file')}) · {r.get('description', '')[:80]}")
        print()

    if mismatch:
        print(t("TEXT-MISMATCH (Code existiert, description passt inhaltlich nicht):",
                "TEXT MISMATCH (code exists, description doesn't match content-wise):"))
        for r, official_title in mismatch:
            print(f"  {r.get('icd_code')} · {t('Zeile', 'line')} {r.get('source_line')} "
                  f"({r.get('source_file')})")
            print(f"    {t('amtlich', 'official')}: {official_title}")
            print(f"    {t('gefunden', 'found')}:  {r.get('description', '')[:120]}")
        print()

    if bundled:
        print(t("GEBÜNDELT/KONTAMINIERT (description enthält die passende Diagnose, "
                "aber zusätzlich Text fremder Diagnosen):",
                "BUNDLED/CONTAMINATED (description contains the matching diagnosis, "
                "but also text from unrelated diagnoses):"))
        for r, official_title in bundled:
            print(f"  {r.get('icd_code')} · {t('Zeile', 'line')} {r.get('source_line')} "
                  f"({r.get('source_file')})")
            print(f"    {t('amtlich', 'official')}: {official_title}")
            print(f"    {t('gefunden', 'found')}:  {r.get('description', '')[:160]}")


if __name__ == "__main__":
    main()
