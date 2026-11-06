#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
apply_icd_corrections.py — ICD-10-GM-Text-Mismatches in einer Kandidaten-JSON automatisch korrigieren (neue Datei)

@tier        infrastructure
@purpose.de  Wendet die von check_icd_codes.py gefundenen Text-Mismatches
             automatisch an: description wird durch den amtlichen
             ICD-10-GM-Klassentitel ersetzt, der alte Wert bleibt in notes
             erhalten. Schreibt NIE die Eingabedatei, sondern immer eine
             neue Ausgabedatei -- die Korrektur ist ein Vorschlag, der vor
             --commit noch durchgesehen werden soll (die ersetzten/
             markierten Zeilen bleiben als solche erkennbar, siehe
             icd_catalog_flag).
@purpose.en  Applies the text mismatches found by check_icd_codes.py
             automatically: description is replaced with the official
             ICD-10-GM class title, the old value is kept in notes. NEVER
             writes the input file, always a new output file -- the
             correction is a proposal meant to still be reviewed before
             --commit (the replaced/flagged rows stay identifiable, see
             icd_catalog_flag).
@method.de   Pro diagnoses-Zeile: unbekannter Code oder nicht-terminaler
             Code werden NICHT automatisch korrigiert (es gibt keine
             sichere automatische Lösung -- der richtige Code bzw. die
             fünfte Stelle ist unbekannt), sondern nur mit
             icd_catalog_flag="unknown_code"/"non_terminal" markiert und ein
             Warnhinweis an notes angehängt, damit sie beim Review in der
             neuen Datei trotzdem auffindbar sind (z.B. "grep
             icd_catalog_flag"). Zwei Fälle werden automatisch korrigiert,
             jeweils description durch lookup(code)["title"] ersetzt und
             der alte Wert an notes angehängt (NICHTS geht verloren, nur
             überschrieben wirkt es auf den ersten Blick): Text-Mismatches
             (Code bekannt und terminal, aber description teilt kein
             Inhaltswort mit dem amtlichen Titel -- icd_catalog_flag=
             "text_mismatch_corrected") UND gebündelte/kontaminierte
             Zeilen (description enthält die passende Diagnose PLUS Text
             fremder Diagnosen -- icd_catalog_flag="bundled_corrected";
             wird VOR dem Text-Mismatch-Check geprüft, weil
             check_description_plausible() so einen Fall fälschlich als
             plausibel werten würde). Zeilen mit dem
             Platzhalter "(nicht automatisch zuordenbar)" werden
             übersprungen (kein Text zum Ersetzen vorhanden). medications-
             Zeilen werden unverändert durchkopiert (ICD-Katalog gilt nur
             für Diagnosen). JEDE markierte Zeile wird zusätzlich auf
             status="needs_review" zurückgestuft, auch wenn sie vorher
             certainty=0.9/confirmed war -- gefunden an einem echten Fall:
             zwei L70.0-Zeilen mit einer Praxisadresse statt Diagnosetext
             waren "confirmed", weil die Original-Heuristik (Datum+Text+
             kein Nachbar-Code) für genau diese Fehlerart blind ist; ohne
             das Zurückstufen hätte die Korrektur den Fehler nur versteckt
             (Text wirkt stimmig), statt ihn zur Prüfung vorzulegen.
@method.en   Per diagnoses row: an unknown or non-terminal code is NOT
             auto-corrected (there is no safe automatic fix -- the correct
             code resp. fifth digit is unknown), only flagged with
             icd_catalog_flag="unknown_code"/"non_terminal" and a warning
             appended to notes, so they're still findable while reviewing
             the new file (e.g. "grep icd_catalog_flag"). Two cases are
             auto-corrected, each replacing description with
             lookup(code)["title"] and appending the old value to notes
             (nothing is lost, it only looks overwritten at first glance):
             text mismatches (code known and terminal, but description
             shares no content word with the official title --
             icd_catalog_flag="text_mismatch_corrected") AND bundled/
             contaminated rows (description contains the matching
             diagnosis PLUS text from unrelated diagnoses --
             icd_catalog_flag="bundled_corrected"; checked BEFORE the text-
             mismatch check, since check_description_plausible() would
             wrongly call such a case plausible). Rows with the "(nicht
             automatisch zuordenbar)" placeholder are skipped (no text to
             replace). medications rows are copied through unchanged (the
             ICD catalog only applies to diagnoses). EVERY flagged row is
             also downgraded to status="needs_review", even if it was
             certainty=0.9/confirmed before -- found in a real case: two
             L70.0 rows with a practice address instead of diagnosis text
             were "confirmed", because the original heuristic (date+text+
             no neighboring code) is blind to exactly this type of error;
             without this downgrade, the correction would just hide the
             error (the text now looks consistent) instead of surfacing it
             for review.
@reads       Kandidaten-JSON (Default: imports/manual/billed_diagnoses_candidates.json);
             data/reference/icd10gm/ (über modules.icd10_catalog)
@writes      Neue Kandidaten-JSON (Default: <eingabe>_icd_corrected.json) --
             NIE die Eingabedatei
@limits.de   Korrigiert NUR description, NIE icd_code selbst -- wenn der
             eigentliche Fehler der Code war (nicht der Text), bleibt der
             falsche Code stehen und description wird auf dessen (dann
             ebenfalls falschen) amtlichen Titel "korrigiert". Das Ergebnis
             sieht dann konsistent aus, ist aber trotzdem falsch -- daher
             weiterhin "reviewbar", nicht automatisch committen.
@limits.en   Only corrects description, NEVER icd_code itself -- if the
             actual error was the code (not the text), the wrong code
             stays and description gets "corrected" to that code's
             (equally wrong) official title. The result then looks
             consistent but is still wrong -- hence still "reviewable", not
             meant for automatic commit.

@relevance.de  Automatisiert den mechanischen Teil der ICD-Review-Arbeit (Text-Ersetzung), hält aber jede Änderung nachvollziehbar, essentiell um die Masse an Text-Mismatches handhabbar zu machen
@relevance.en  Automates the mechanical part of the ICD review work (text replacement), while keeping every change traceable, essential for making the volume of text mismatches manageable
@usage
    python3 apply_icd_corrections.py
    python3 apply_icd_corrections.py --file imports/manual/andere_kandidaten.json --out imports/manual/andere_korrigiert.json
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
    is_available, is_known, lookup, check_description_plausible, check_bundled_contamination, catalog_version,
)

_cfg = _Cfg()
DEFAULT_CANDIDATES_PATH = _cfg.data_root / "manual" / "billed_diagnoses_candidates.json"
NO_TEXT_PLACEHOLDER = "(nicht automatisch zuordenbar)"  # siehe check_icd_codes.py


def _default_out_path(in_path: Path) -> Path:
    return in_path.with_name(in_path.stem + "_icd_corrected" + in_path.suffix)


def correct_row(r: dict, lang: str) -> tuple[dict, str | None]:
    """(neue_zeile, kategorie). kategorie ist None, wenn nichts zu
    vermerken war (Code plausibel oder keine Diagnose-Zeile)."""
    if r.get("table") != "diagnoses":
        return r, None
    code = r.get("icd_code")
    if not code:
        return r, None

    r = dict(r)  # Kopie -- Original-dict der Aufruferin nie mutieren

    def _force_review(max_certainty: float | None = None) -> None:
        """Jede vom Katalog markierte Zeile MUSS auf needs_review zurück,
        auch wenn sie vorher certainty=0.9/confirmed war -- gefunden beim
        ersten echten Testlauf: zwei L70.0-Zeilen mit einer Praxisadresse
        statt Diagnosetext als description waren "confirmed", weil die
        Original-Heuristik (Datum+Text+kein Nachbar-Code) blind fuer genau
        diese Art Fehler ist. Ohne dieses Zurueckstufen wuerde die
        Korrektur den Fehler verstecken (Text wird stimmig), statt ihn zur
        Pruefung vorzulegen."""
        r["status"] = "needs_review"
        if max_certainty is not None:
            r["certainty"] = min(r.get("certainty", max_certainty), max_certainty)

    if not is_known(code):
        r["icd_catalog_flag"] = "unknown_code"
        r["notes"] = t(
            f"{r.get('notes') or ''} ⚠ ICD-Code '{code}' nicht im installierten "
            f"ICD-10-GM-{catalog_version()}-Katalog gefunden -- bitte prüfen.",
            f"{r.get('notes') or ''} ⚠ ICD code '{code}' not found in the installed "
            f"ICD-10-GM-{catalog_version()} catalog -- please check.",
        ).strip()
        _force_review()
        return r, "unknown_code"

    entry = lookup(code)
    if not entry["terminal"]:
        r["icd_catalog_flag"] = "non_terminal"
        r["notes"] = t(
            f"{r.get('notes') or ''} ⚠ Code '{code}' ist nicht-terminal (Kategorie "
            f"ohne 5. Stelle, amtlicher Titel: '{entry['title']}') -- zur Abrechnung "
            f"eigentlich nicht zugelassen, ggf. fehlt eine genauere Schlüsselnummer.",
            f"{r.get('notes') or ''} ⚠ Code '{code}' is non-terminal (category "
            f"without a 5th digit, official title: '{entry['title']}') -- not "
            f"actually valid for billing, a more specific code may be missing.",
        ).strip()
        _force_review()
        return r, "non_terminal"

    description = r.get("description") or ""
    if description == NO_TEXT_PLACEHOLDER:
        return r, None

    is_bundled, official_title = check_bundled_contamination(code, description)
    if is_bundled:
        r["notes"] = t(
            f"{r.get('notes') or ''} ⚠ description wirkte mit Text fremder Diagnosen "
            f"kontaminiert, automatisch durch amtlichen ICD-10-GM-Titel ersetzt. "
            f"Vorheriger Text: '{description}'.",
            f"{r.get('notes') or ''} ⚠ description looked contaminated with text from "
            f"unrelated diagnoses, automatically replaced with the official ICD-10-GM "
            f"title. Previous text: '{description}'.",
        ).strip()
        r["description"] = official_title
        r["icd_catalog_flag"] = "bundled_corrected"
        _force_review(max_certainty=0.5)
        return r, "bundled_corrected"

    plausible, official_title = check_description_plausible(code, description)
    if plausible is not False:
        return r, None

    r["notes"] = t(
        f"{r.get('notes') or ''} ⚠ description automatisch durch amtlichen "
        f"ICD-10-GM-Titel ersetzt. Vorheriger Text: '{description}'.",
        f"{r.get('notes') or ''} ⚠ description automatically replaced with the "
        f"official ICD-10-GM title. Previous text: '{description}'.",
    ).strip()
    r["description"] = official_title
    r["icd_catalog_flag"] = "text_mismatch_corrected"
    _force_review(max_certainty=0.5)
    return r, "text_mismatch_corrected"


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "ICD-10-GM-Text-Mismatches in einer Kandidaten-JSON korrigieren (neue Datei)",
        "Correct ICD-10-GM text mismatches in a candidate JSON (new file)",
    ))
    parser.add_argument("--file", type=Path, default=DEFAULT_CANDIDATES_PATH,
                        help=t("Eingabe-Kandidaten-JSON", "Input candidate JSON"))
    parser.add_argument("--out", type=Path, default=None,
                        help=t("Ausgabedatei (Default: <eingabe>_icd_corrected.json)",
                               "Output file (default: <input>_icd_corrected.json)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de") or "de"

    if not is_available():
        print(t(
            "Kein lokaler ICD-10-GM-Katalog installiert. Erst ausführen:\n"
            "  python3 update_icd10_catalog.py --download --accept-terms",
            "No local ICD-10-GM catalog installed. Run first:\n"
            "  python3 update_icd10_catalog.py --download --accept-terms",
        ))
        sys.exit(1)
    if not args.file.exists():
        print(t(f"Nicht gefunden: {args.file}", f"Not found: {args.file}"))
        sys.exit(1)

    rows = json.loads(args.file.read_text(encoding="utf-8"))
    out_path = args.out or _default_out_path(args.file)

    counts: dict[str, int] = {}
    new_rows = []
    for r in rows:
        new_r, category = correct_row(r, lang)
        new_rows.append(new_r)
        if category:
            counts[category] = counts.get(category, 0) + 1

    out_path.write_text(json.dumps(new_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(t(
        f"{len(new_rows)} Zeilen geschrieben nach {out_path}\n"
        f"  {counts.get('text_mismatch_corrected', 0)} description automatisch korrigiert (Text-Mismatch)\n"
        f"  {counts.get('bundled_corrected', 0)} description automatisch korrigiert (gebündelt/kontaminiert)\n"
        f"  {counts.get('unknown_code', 0)} unbekannter Code markiert (NICHT korrigiert)\n"
        f"  {counts.get('non_terminal', 0)} nicht-terminaler Code markiert (NICHT korrigiert)\n"
        f"\nDas ist ein VORSCHLAG, keine fertige Korrektur -- bitte vor --commit "
        f"durchsehen (z.B. grep -c icd_catalog_flag {out_path}).",
        f"{len(new_rows)} rows written to {out_path}\n"
        f"  {counts.get('text_mismatch_corrected', 0)} description auto-corrected (text mismatch)\n"
        f"  {counts.get('bundled_corrected', 0)} description auto-corrected (bundled/contaminated)\n"
        f"  {counts.get('unknown_code', 0)} unknown code flagged (NOT corrected)\n"
        f"  {counts.get('non_terminal', 0)} non-terminal code flagged (NOT corrected)\n"
        f"\nThis is a PROPOSAL, not a finished correction -- please review before "
        f"--commit (e.g. grep -c icd_catalog_flag {out_path}).",
    ))


if __name__ == "__main__":
    main()
