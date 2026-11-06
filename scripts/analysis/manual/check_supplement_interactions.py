#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_supplement_interactions.py — Interaktions-Hinweise Supplement × aktuelle Medikamentenliste

@tier        experimental
@purpose.de  Listet die aktuellen chronischen Einträge aus medicine.db auf
             und lässt ein LLM bekannte, gut etablierte Interaktions-/
             Kontraindikationsbedenken mit einem oder mehreren erwogenen
             Nahrungsergänzungsmitteln benennen. KEINE Sicherheits-Freigabe —
             nur eine Diskussionsgrundlage für eine Fachperson.
@purpose.en  Lists current chronic entries from medicine.db and has an
             LLM name known, well-established interaction/contraindication
             concerns with one or more supplements under consideration. NOT
             a safety clearance — only a discussion basis for a
             professional.
@method.de   Liest medications (medicine.db), nimmt pro drug_name den
             neuesten Eintrag mit is_chronic=1. Baut daraus + den
             übergebenen Supplement-Namen einen Prompt an das konfigurierte
             LLM (Analyse-Tier, kein lokales-only-Zwang wie bei
             Rohdokument-Extraktion — analog zu analyse_lab_verlauf.py).
             Der System-Prompt verlangt explizit: nur etablierte Bedenken
             nennen, keine abschließende Sicherheitsbewertung, immer auf
             Rücksprache mit einer Fachperson verweisen. Grounding-Suffix
             und KI-Kennzeichnung laufen automatisch über modules.llm.call_llm.
             Kein numerischer Score — die Einordnung "etabliert/nicht
             etabliert" liegt allein beim konfigurierten LLM.
@method.en   Reads medications (medicine.db), takes the most recent entry
             per drug_name with is_chronic=1. Builds a prompt from that plus
             the given supplement names to the configured LLM (analysis
             tier, no local-only requirement like raw document extraction —
             same as analyse_lab_verlauf.py). The system prompt explicitly
             requires: name only well-established concerns, no final safety
             verdict, always refer to professional consultation.
             Grounding suffix and AI labeling run automatically via
             modules.llm.call_llm. No numeric score — the "established/not
             established" judgment rests entirely with the configured LLM.
@reads       medicine.db (medications)
@writes      Analyseergebnis als Markdown (analyses/manual/)
@limits.de   KEIN Ersatz für eine fachliche Prüfung. Die Qualität hängt vom
             Wissen des konfigurierten LLM ab — es kann etablierte
             Interaktionen übersehen oder unsicher formulieren. Keine
             strukturierte Interaktionsdatenbank beteiligt, da keine im
             Projekt vorhanden ist.
@limits.en   NOT a substitute for a professional review. Quality depends on
             the configured LLM's knowledge — it can miss established
             interactions or phrase things with false confidence. No
             structured interaction database involved, since none exists
             in this project.

@relevance.de  Liefert eine Diskussionsgrundlage für Supplement-Interaktionen, kein Ersatz für Fachpersonal
@relevance.en  Provides a discussion basis for supplement interactions, not a substitute for professionals
@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_PROMPT
@prompt.en    SYSTEM_PROMPT
@usage
    python3 check_supplement_interactions.py --supplement "Vitamin D3"
    python3 check_supplement_interactions.py --supplement "Magnesium" --supplement "Melatonin"
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_medicine_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import call_llm
from modules.prompts.analysis_manual import (
    SYSTEM_PROMPT_SUPPLEMENT_INTERACTIONS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_SUPPLEMENT_INTERACTIONS_EN as SYSTEM_PROMPT_EN,
)

cfg = Config()
OUT_DIR = cfg.analyses_dir / "manual"

_DISCLAIMER_DE = (
    "**Hinweis:** Das ist keine Sicherheitsfreigabe, sondern eine automatisiert "
    "erstellte Diskussionsgrundlage. Vor der Einnahme immer mit Apotheker oder "
    "Arzt besprechen — besonders bei bestehender Medikation."
)
_DISCLAIMER_EN = (
    "**Note:** This is not a safety clearance, just an automatically generated "
    "discussion basis. Always discuss with a pharmacist or doctor before taking "
    "anything — especially alongside existing medication."
)


def load_current_medications() -> list[dict]:
    """Neuester Eintrag je drug_name mit is_chronic=1."""
    conn = open_medicine_db()
    rows = conn.execute(
        """
        SELECT drug_name, dose_value, dose_unit, MAX(date) as last_date
        FROM medications
        WHERE person = ? AND is_chronic = 1 AND is_skipped = 0
        GROUP BY drug_name
        ORDER BY drug_name
        """,
        [OWN_PERSON_ID],
    ).fetchall()
    conn.close()
    return [{"drug_name": r[0], "dose_value": r[1], "dose_unit": r[2], "last_date": r[3]} for r in rows]


def build_prompt(medications: list[dict], supplements: list[str], lang: str) -> str:
    med_lines = "\n".join(
        f"- {m['drug_name']}" + (f" {m['dose_value']}{m['dose_unit']}" if m["dose_value"] else "")
        for m in medications
    ) or t("(keine aktuellen chronischen Medikamente in der DB erfasst)",
           "(no current chronic medications recorded in the DB)")
    supp_lines = "\n".join(f"- {s}" for s in supplements)
    return t(
        f"Aktuelle Medikamente:\n{med_lines}\n\nErwogene Nahrungsergänzungsmittel:\n{supp_lines}\n\n"
        "Nenne bekannte Interaktions-/Kontraindikationsbedenken.",
        f"Current medications:\n{med_lines}\n\nSupplements under consideration:\n{supp_lines}\n\n"
        "Name known interaction/contraindication concerns.",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=t(
        "Interaktions-Hinweise zwischen Supplementen und aktueller Medikation (keine Sicherheitsfreigabe)",
        "Interaction notes between supplements and current medication (not a safety clearance)",
    ))
    ap.add_argument("--supplement", metavar="NAME", action="append", required=True,
                     help=t("Erwogenes Supplement (wiederholbar)", "Supplement under consideration (repeatable)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de")

    medications = load_current_medications()
    prompt = build_prompt(medications, args.supplement, lang)
    system = t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN)

    print(t("Frage LLM nach Interaktionsbedenken …", "Asking LLM for interaction concerns …"))
    try:
        response = call_llm(prompt, system=system, max_tokens=1500)
    except Exception as e:
        print(t(f"LLM-Aufruf fehlgeschlagen: {e}", f"LLM call failed: {e}"))
        sys.exit(1)

    disclaimer = t(_DISCLAIMER_DE, _DISCLAIMER_EN)
    report = (
        f"{disclaimer}\n\n"
        f"# {t('Supplement-Interaktionscheck', 'Supplement Interaction Check')}: {', '.join(args.supplement)}\n\n"
        f"{response}\n\n---\n\n{disclaimer}\n"
    )
    print(report)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    safe_name = "_".join(args.supplement).replace(" ", "-")[:40]
    out_path = OUT_DIR / f"supplement_check_{safe_name}_{now.strftime('%Y%m%d_%H%M')}.md"
    out_path.write_text(report, encoding="utf-8")
    print(t(f"\n→ Bericht: {out_path}", f"\n→ Report: {out_path}"))


if __name__ == "__main__":
    main()
