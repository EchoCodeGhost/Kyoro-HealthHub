#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Konsil-Synthese in Alltagssprache — Patientenversion des Vorsitz-Berichts.

@tier        infrastructure
@purpose.de  Übersetzt den fachsprachlichen Abschlussbericht des Konsil-Vorsitzes
             (analyse_synthesis.py) in allgemeinverständliche Sprache und ergänzt
             ihn um konkrete Handlungsempfehlungen für die Patientin.
@purpose.en  Translates the consult chair's technical final report
             (analyse_synthesis.py) into plain language and adds concrete
             action guidance for the patient.
@method.de   Liest die neueste (oder per --file angegebene) Synthese-Datei,
             entfernt die Arbeitsanhänge (Kategorie-Notizen, Einzelmeinungen —
             das sind Zwischenstände, nicht das Endergebnis) und lässt nur den
             finalen Vorsitz-Text von einem LLM in Alltagssprache übertragen.
             Konfidenz-/Wahrscheinlichkeitsangaben müssen dabei erhalten
             bleiben (siehe openspec/specs/documentation-conventions). Die
             beiden Standardempfehlungen (zuerst Hausarzt, Arztberichte
             zwischen allen Behandelnden austauschen) werden NICHT dem LLM
             überlassen, sondern als fester Abschnitt angehängt. Erwähnt der
             Quellbericht PEM, wird zusätzlich ein fester Hinweis angehängt,
             dass PEM-Scores aus diesem Projekt ein nicht klinisch validierter
             Heuristik-Score sind (s. compute_pem.py @tier heuristic).
@method.en   Reads the latest (or --file-specified) synthesis file, strips the
             working appendices (category notes, individual opinions — those
             are intermediate work product, not the final result), and has
             only the chair's final text translated into plain language by an
             LLM. Confidence/probability qualifiers must be preserved (see
             openspec/specs/documentation-conventions). The two standing
             recommendations (GP first, share reports between all treating
             doctors) are not left to the LLM — they are appended as a fixed
             section. If the source report mentions PEM, a fixed note is also
             appended clarifying that this project's PEM scores are a
             non-clinically-validated heuristic (see compute_pem.py @tier
             heuristic).
@reads       analyses/synthesis/synthesis_*.md
@writes      analyses/synthesis/<name>_patientenversion.md (Markdown, lokal)
@limits.de   Heuristische Methode: LLM-Übersetzung, keine medizinische Beratung.
             Ersetzt kein Arztgespräch. Es werden keine neuen medizinischen
             Aussagen erzeugt — nur eine Übertragung des Vorsitz-Textes.
@limits.en   Heuristic method: LLM translation, not medical advice. Does not
             replace talking to a doctor. No new medical claims are
             generated — only a rewording of the chair's existing text.

@relevance.de  Macht den Konsil-Abschlussbericht ohne Fachvokabular verständlich und
               ergänzt konkrete nächste Schritte für die Patientin
@relevance.en  Makes the consult's final report understandable without jargon and
               adds concrete next steps for the patient
@usage
    python3 scripts/analysis/manual/explain_synthesis.py
    python3 scripts/analysis/manual/explain_synthesis.py --file analyses/synthesis/synthesis_20260808_1704.md
    python3 scripts/analysis/manual/explain_synthesis.py --lang en
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config
from modules.llm import call_llm
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = Config()
SYNTHESIS_DIR = _cfg.analyses_dir / "synthesis"

# Trennt den finalen Vorsitz-Text von den Arbeitsanhängen (Kategorie-Notizen /
# Einzelmeinungen) — siehe analyse_synthesis.py::run(). Beide Sprachvarianten,
# da der Zieltext je nach --lang der Erzeugung DE oder EN ist.
_APPENDIX_RE = re.compile(
    r"\n##\s*(Anhang|Appendix)\s*:",
    re.IGNORECASE,
)

_OUTPUT_SUFFIX = {"de": "_patientenversion", "en": "_plain_language"}

# Nicht vom LLM abhaengig, s. _pem_caveat() unten.
_PEM_MENTION_RE = re.compile(r"\bPEM\b|post-?exertionell|post-?exertional", re.IGNORECASE)


def _mentions_pem(text: str) -> bool:
    return bool(_PEM_MENTION_RE.search(text))


def _latest_synthesis_file() -> "Path | None":
    candidates = sorted(
        (p for p in SYNTHESIS_DIR.glob("synthesis_*.md")
         if not any(p.stem.endswith(s) for s in _OUTPUT_SUFFIX.values())),
        key=lambda p: p.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def _strip_appendices(content: str) -> str:
    match = _APPENDIX_RE.search(content)
    return content[:match.start()].rstrip() if match else content.rstrip()


def _standing_recommendations(lang: str) -> str:
    """Fester, nicht vom LLM abhängiger Abschnitt — siehe @method oben."""
    if lang == "en":
        return (
            "\n\n---\n\n## Always true, regardless of the report above\n\n"
            "1. **Talk to your GP (Hausarzt) first.** They coordinate everything "
            "else and can judge urgency — start there before contacting any "
            "specialist directly.\n"
            "2. **Make sure every doctor gets every other doctor's reports.** "
            "Ask each treating doctor to send their findings to your GP (and "
            "to each other where relevant), and bring copies of everything "
            "to new specialist appointments. Fragmented records are a "
            "recurring problem in your case — this is the single most "
            "effective thing you can do about it.\n"
        )
    return (
        "\n\n---\n\n## Was in jedem Fall gilt, unabhängig vom Bericht oben\n\n"
        "1. **Zuerst mit dem Hausarzt sprechen.** Der Hausarzt koordiniert "
        "alles Weitere und kann die Dringlichkeit einschätzen — das ist "
        "immer die erste Anlaufstelle, auch bevor eine Facharztpraxis "
        "direkt kontaktiert wird.\n"
        "2. **Dafür sorgen, dass alle Ärzte alle Arztberichte bekommen.** "
        "Jeden behandelnden Arzt bitten, seine Befunde an den Hausarzt (und "
        "wo relevant an die anderen Behandelnden) weiterzuleiten, und zu "
        "neuen Facharztterminen Kopien aller vorhandenen Befunde mitbringen. "
        "Lückenhafte Aktenlage ist ein wiederkehrendes Problem in diesem "
        "Fall — das ist der wirksamste Hebel dagegen.\n"
    )


def _pem_caveat(lang: str) -> str:
    """Fester, nicht vom LLM abhängiger Hinweis (wie _standing_recommendations) —
    wird nur angehängt, wenn der Quellbericht PEM überhaupt erwähnt (s.
    _mentions_pem). compute_pem.py ist @tier heuristic: die konkreten
    Schwellenwerte/Punktzahlen sind selbst gewählte Defaults, nicht klinisch
    validiert — und das ist kein Mangel speziell dieses Tools, sondern der
    Stand des Feldes: es gibt aktuell kein anerkanntes physiologisches
    PEM-Biomarker-Verfahren, PEM wird klinisch ausschließlich über
    Selbstauskunft diagnostiziert (DePaul Symptom Questionnaire, IOM 2015)."""
    if lang == "en":
        return (
            "\n\n---\n\n## About PEM scores in this report\n\n"
            "Any \"PEM score\" or PEM-related pattern mentioned above comes from "
            "this project's own heuristic algorithm (exertion signals compared "
            "against a delayed HRV/heart-rate drop) — its specific thresholds "
            "and point values are reasonable-looking defaults, not clinically "
            "validated numbers. This isn't a shortcoming specific to this tool: "
            "there is currently no accepted physiological biomarker for PEM at "
            "all in the medical literature — PEM is diagnosed clinically by "
            "self-report alone (e.g. the DePaul Symptom Questionnaire, IOM 2015 "
            "criteria). Treat a high score as \"worth a second look\" (large "
            "exertion followed by a multi-day disproportionate HRV drop), not "
            "as a measurement. Your own symptom diary is the more clinically "
            "load-bearing evidence — the wearable pattern is supporting context "
            "at most.\n"
        )
    return (
        "\n\n---\n\n## Zu PEM-Scores in diesem Bericht\n\n"
        "Ein oben erwähnter \"PEM-Score\" oder ein PEM-Muster stammt aus dem "
        "projekteigenen Heuristik-Algorithmus (Belastungssignale gegen einen "
        "verzögerten HRV-/Pulsabfall) — die konkreten Schwellenwerte und "
        "Punktzahlen sind plausibel wirkende Standardwerte, keine klinisch "
        "validierten Zahlen. Das ist kein Mangel speziell dieses Tools: Es "
        "gibt aktuell überhaupt kein anerkanntes physiologisches "
        "Biomarker-Verfahren für PEM in der Fachliteratur — PEM wird klinisch "
        "ausschließlich über Selbstauskunft diagnostiziert (z. B. DePaul "
        "Symptom Questionnaire, IOM-2015-Kriterien). Ein hoher Score bedeutet "
        "\"lohnt einen zweiten Blick\" (viel Belastung, danach mehrtägiger "
        "unverhältnismäßiger HRV-Abfall), nicht \"gemessener Wert\". Das "
        "eigene Symptomtagebuch ist die klinisch eigentlich tragfähige "
        "Quelle — das Wearable-Muster ist höchstens unterstützender "
        "Kontext.\n"
    )


def _build_prompt(report_text: str, lang: str) -> str:
    if lang == "en":
        return (
            "Below is the final report of a multi-model medical consult panel, "
            "written for clinicians. Rewrite it in plain, everyday English for "
            "the patient herself, who is not a medical professional.\n\n"
            "Rules:\n"
            "- Translate ALL medical jargon, abbreviations and lab/metric names "
            "into plain terms, explained in one clause where needed.\n"
            "- Do NOT drop, soften, or invent any finding. Every confidence or "
            "probability qualifier in the source (e.g. \"likely\", \"possible\", "
            "\"~60%\", \"unconfirmed\") MUST be carried over — do not turn a "
            "possibility into a certainty or vice versa.\n"
            "- Do not add new medical claims that are not in the source text.\n"
            "- After the plain-language rewrite, add two sections:\n"
            "  ## What should I do now?\n"
            "  (concrete, prioritized next steps based on what the report "
            "actually says)\n"
            "  ## Which doctors would be the right contacts?\n"
            "  (list relevant specialties based on the findings, in plain "
            "language, e.g. \"cardiologist (heart rhythm)\" not just "
            "\"cardiology\")\n"
            "- Do not mention which doctor to see first in that second section — "
            "that is handled separately below your output.\n\n"
            "--- SOURCE REPORT ---\n\n"
            f"{report_text}\n"
        )
    return (
        "Im Folgenden der Abschlussbericht eines Multi-Modell-Konsils, "
        "geschrieben für Ärzte. Schreibe ihn in einfacher Alltagssprache für "
        "die Patientin selbst um, die keine medizinische Fachperson ist.\n\n"
        "Regeln:\n"
        "- Übersetze ALLE Fachbegriffe, Abkürzungen und Labor-/Metrik-Namen in "
        "einfache Sprache, bei Bedarf mit einem kurzen Nebensatz erklärt.\n"
        "- Lasse KEINEN Befund weg, schwäche keinen ab und erfinde keinen "
        "hinzu. Jede Konfidenz- oder Wahrscheinlichkeitsangabe aus der "
        "Quelle (z. B. \"wahrscheinlich\", \"möglich\", \"~60%\", "
        "\"unbestätigt\") MUSS erhalten bleiben — mache aus einer Möglichkeit "
        "keine Gewissheit und umgekehrt.\n"
        "- Füge keine neuen medizinischen Aussagen hinzu, die nicht im "
        "Quelltext stehen.\n"
        "- Ergänze nach der Übertragung zwei Abschnitte:\n"
        "  ## Was sollte ich jetzt tun?\n"
        "  (konkrete, priorisierte nächste Schritte, basierend auf dem, was "
        "der Bericht tatsächlich sagt)\n"
        "  ## Welche Ärzte wären die richtigen Ansprechpartner?\n"
        "  (relevante Fachrichtungen aus den Befunden ableiten, in "
        "Alltagssprache, z. B. \"Kardiologe (Herzrhythmus)\" statt nur "
        "\"Kardiologie\")\n"
        "- Erwähne in diesem zweiten Abschnitt nicht, wer zuerst "
        "aufzusuchen ist — das wird unten separat behandelt.\n\n"
        "--- QUELLBERICHT ---\n\n"
        f"{report_text}\n"
    )


def run(file_arg: "str | None", lang: str) -> None:
    src_path = Path(file_arg) if file_arg else _latest_synthesis_file()
    if not src_path or not src_path.exists():
        print(t("Keine Synthese-Datei gefunden (analyse_synthesis.py zuerst laufen lassen, oder --file angeben).",
                 "No synthesis file found (run analyse_synthesis.py first, or pass --file)."))
        return

    print(t(f"Quelle: {src_path}", f"Source: {src_path}"))
    full_content = src_path.read_text(encoding="utf-8")
    report_text = _strip_appendices(full_content)

    print(t("Übersetze in Alltagssprache …", "Translating into plain language …"))
    prompt = _build_prompt(report_text, lang)
    system = (
        "You are a careful medical translator. You never invent or omit "
        "clinical findings; you only reword them for a lay reader, "
        "preserving every confidence/probability qualifier exactly."
    )
    try:
        response = call_llm(prompt, system=system, max_tokens=8000)
    except Exception as e:
        print(t(f"Fehler: {e}", f"Error: {e}"), file=sys.stderr)
        sys.exit(1)

    out_body = response.strip() + _standing_recommendations(lang)
    if _mentions_pem(report_text):
        out_body += _pem_caveat(lang)
    out_path = src_path.with_name(f"{src_path.stem}{_OUTPUT_SUFFIX[lang]}.md")
    out_path.write_text(
        t(f"# Patientenversion — {src_path.name}\n\n",
          f"# Plain-language version — {src_path.name}\n\n")
        + t("*Automatisch aus dem Konsil-Abschlussbericht übersetzt. "
            "Ersetzt kein Arztgespräch.*\n\n---\n\n",
            "*Automatically translated from the consult's final report. "
            "Does not replace talking to a doctor.*\n\n---\n\n")
        + out_body + "\n",
        encoding="utf-8",
    )
    print(t(f"\n✓ Patientenversion gespeichert: {out_path}",
            f"\n✓ Plain-language version saved: {out_path}"))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Konsil-Synthese in Alltagssprache übersetzen",
                       "Translate consult synthesis into plain language"))
    ap.add_argument("--file", default=None,
                     help=t("Pfad zu einer bestimmten synthesis_*.md (Default: neueste)",
                            "Path to a specific synthesis_*.md (default: latest)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    run(args.file, args.lang or "de")


if __name__ == "__main__":
    main()
