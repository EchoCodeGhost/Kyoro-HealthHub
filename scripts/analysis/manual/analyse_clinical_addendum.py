#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_clinical_addendum.py — Klinisches Addendum zur Daten-Synthese

@tier        heuristic
@refs        Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7
             Moor M, Banerjee O, Abad ZSH, Krumholz HM, Leskovec J, Topol EJ, Rajpurkar P (2023). Foundation models for generalist medical artificial intelligence. Nature, 616(7956):259-265. doi:10.1038/s41586-023-05881-4

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@purpose.de  Generiert ein klinisches Addendum zur Daten-Synthese
@purpose.en  Generates a clinical addendum for data synthesis
@method.de   Liest den aktuellsten Synthese-Bericht und klinische Beobachtungen aus der Config (clinical.observations)
             und generiert ein Addendum, das strukturelle Datenlücken adressiert.
             Typische Lücken:
             - Unterschätzung von Mustern mangels Messdaten
             - Pharmakologische Ansprechmuster aus klinischer Beobachtung
             - Methodische Verzerrungen (z.B. Deckeneffekt beim Orthostase-Test)
@method.en   Reads the latest synthesis report and clinical observations from config (clinical.observations)
             and generates an addendum that addresses structural data gaps.
             Typical gaps:
             - Underestimation of patterns due to lack of measurement data
             - Pharmacological response patterns from clinical observation
             - Methodological biases (e.g., ceiling effect in orthostatic test)
@reads       Synthese-Berichte aus analyses/synthesis/, Config clinical.observations
@writes      Addendum als Markdown-Datei
@limits.de   Heuristische Methode. Abhängig von Qualität der klinischen Beobachtungen.
@limits.en   Heuristic method. Dependent on quality of clinical observations.
@scoring Gewichtung basierend auf Datenverfügbarkeit und Beobachtungsqualität
@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_DE, SYSTEM_EN
@prompt.en    SYSTEM_DE, SYSTEM_EN
@usage
    python3 scripts/analysis/manual/analyse_clinical_addendum.py
    python3 scripts/analysis/manual/analyse_clinical_addendum.py --synthesis analyses/synthesis/synthesis_20260704_2140.md
    python3 scripts/analysis/manual/analyse_clinical_addendum.py --lang en
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import ai_label
from modules.prompts.analysis_manual import (
    SYSTEM_PROMPT_ANALYSE_CLINICAL_ADDENDUM_DE_STR as SYSTEM_DE,
    SYSTEM_PROMPT_ANALYSE_CLINICAL_ADDENDUM_EN_STR as SYSTEM_EN
)

_cfg = Config()

SYNTHESIS_DIR = _cfg.analyses_dir / "synthesis"


# ── Synthese-Bericht finden ───────────────────────────────────────────────────

# Nur der kanonische Berichtsname (synthesis_YYYYMMDD_HHMM.md) — nicht dessen
# Ableitungen wie *_patientenversion.md (explain_synthesis.py) oder
# *_vollstaendig.md, die typischerweise NACH dem eigentlichen Bericht
# geschrieben werden und sonst wegen des juengeren mtime faelschlich als
# "neuester Bericht" gewaehlt wuerden — mit weniger technischer Tiefe
# (Zahlen, Evidenzzitate) als Grundlage fuer das Addendum.
_CANONICAL_SYNTHESIS_RE = re.compile(r"^synthesis_\d{8}_\d{4}\.md$")


def _find_latest_synthesis() -> Path:
    candidates = sorted(
        (p for p in SYNTHESIS_DIR.glob("synthesis_*.md")
         if _CANONICAL_SYNTHESIS_RE.match(p.name)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(t(
            f"Kein Synthese-Bericht in {SYNTHESIS_DIR} gefunden.",
            f"No synthesis report found in {SYNTHESIS_DIR}.",
        ))
    return candidates[0]


# ── Klinische Beobachtungen aus Config laden ──────────────────────────────────

def _load_observations() -> dict:
    return _cfg._cfg.get("clinical", {}).get("observations", {})


def _format_observations(obs: dict, lang: str) -> str:
    if not obs:
        return t(
            "Keine klinischen Beobachtungen in clinical.observations konfiguriert.",
            "No clinical observations configured in clinical.observations.",
        )

    lines: list[str] = []

    responses = obs.get("treatment_responses", [])
    if responses:
        lines.append(t(
            "### Pharmakologische Ansprechmuster",
            "### Pharmacological response patterns",
        ))
        for r in responses:
            substance = r.get("substance", "?")
            response  = r.get("response", "?")
            date      = r.get("date", "")
            notes     = r.get("notes", "")
            date_str  = f" ({date})" if date else ""
            lines.append(f"- **{substance}**{date_str}: {response}")
            if notes:
                lines.append(f"  → {notes}")
        lines.append("")

    limitations = obs.get("diagnostic_limitations", [])
    if limitations:
        lines.append(t(
            "### Methodische Limitierungen der Messdaten",
            "### Methodological limitations of measurement data",
        ))
        for lim in limitations:
            condition = lim.get("condition", "?")
            limitation = lim.get("limitation", "")
            lines.append(f"- **{condition}:** {limitation}")
        lines.append("")

    extra = obs.get("additional_context", [])
    if extra:
        lines.append(t("### Weiterer klinischer Kontext", "### Additional clinical context"))
        for item in extra:
            label = item.get("label", "")
            text  = item.get("text", "")
            lines.append(f"- **{label}:** {text}" if label else f"- {text}")

    return "\n".join(lines)


# ── Synthese-Relevantabschnitte extrahieren ───────────────────────────────────

def _extract_synthesis_core(synthesis_text: str) -> str:
    """Extrahiert die für das Addendum relevanten Abschnitte."""
    lines = synthesis_text.splitlines()
    relevant: list[str] = []
    in_section = False
    target_headers = {
        "## 2.", "## 3.", "## 4.",  # Wechselwirkungen, Priorisierung, Differenzialdiagnosen
        "## 2 ", "## 3 ", "## 4 ",
    }

    for line in lines:
        stripped = line.strip()
        # Vorbemerkung zur Datenqualität immer mitnehmen
        if stripped.startswith("## Vorbemerkung") or stripped.startswith("## Data quality"):
            in_section = True
        elif any(stripped.startswith(h) for h in target_headers):
            in_section = True
        elif stripped.startswith("## ") and not any(stripped.startswith(h) for h in target_headers):
            # Neuer Abschnitt der nicht relevant ist → stopp, außer es folgt nochmal ein Ziel
            if in_section and stripped.startswith("## 5"):
                in_section = False

        if in_section:
            relevant.append(line)

    # Fallback: letzte 150 Zeilen wenn nichts extrahiert
    if len(relevant) < 20:
        relevant = lines[-150:]

    return "\n".join(relevant[:300])  # max 300 Zeilen



def _build_prompt(synthesis_core: str, obs_text: str, synthesis_path: Path, lang: str) -> str:
    return t(
        f"""Der folgende Synthesebericht wurde ausschließlich aus Wearable- und Labormessdaten \
abgeleitet. Das Modell hatte keine Vordiagnosen und keine klinischen Beobachtungen außerhalb \
der Messdaten. Einige Diagnosen wurden daher möglicherweise unterschätzt, weil der entscheidende \
Nachweis nicht in den Messdaten enthalten ist — sondern in pharmakologischen Ansprechmustern, \
methodischen Testlimitierungen oder klinischen Beobachtungen.

## Relevante Abschnitte aus dem Synthese-Bericht
*(Quelle: {synthesis_path.name})*

{synthesis_core}

---

## Klinische Beobachtungen (nicht in Wearable-Daten enthalten)

{obs_text}

---

## Deine Aufgabe

Schreibe ein **klinisches Addendum** mit folgenden Abschnitten:

### 1. Diagnosen mit Datenlücken-Unterschätzung
Liste alle Diagnosen aus dem Bericht, bei denen die niedrige Wahrscheinlichkeit \
auf fehlende Messdaten zurückzuführen ist (nicht auf aktive Gegenargumente). \
Format: `Diagnose — ursprünglich X% — Begründung der Unterschätzung — \
revidierte Einschätzung mit verfügbarer klinischer Evidenz`

### 2. Pharmakologische Evidenz
Werte die Ansprechmuster systematisch aus. Welche Diagnosen werden durch das \
pharmakologische Muster gestärkt oder geschwächt? Welche pathophysiologischen \
Mechanismen legt das Muster nahe?

### 3. Methodische Korrekturen
Benenne explizit, wo die rein datenbasierte Analyse methodisch an ihre Grenzen \
stößt (z.B. Score-Kriterien die bei bestimmten Patientenkonstellationen \
systematisch versagen).

### 4. Gesamteinschätzung nach Addendum
Wie verändert diese Ergänzung das Bild gegenüber dem Synthese-Bericht? \
Was bleibt offen, was ist jetzt klarer?
""",
        f"""The following synthesis report was derived exclusively from wearable and lab measurement \
data. The model had no prior diagnoses and no clinical observations outside the measurements. \
Some diagnoses may therefore be underestimated because the decisive evidence is not in the \
measurement data — but in pharmacological response patterns, methodological test limitations, \
or clinical observations.

## Relevant sections from the synthesis report
*(Source: {synthesis_path.name})*

{synthesis_core}

---

## Clinical observations (not in wearable data)

{obs_text}

---

## Your task

Write a **clinical addendum** with the following sections:

### 1. Diagnoses with data-gap underestimation
List all diagnoses from the report where the low probability is attributable to \
missing measurement data (not active counterarguments). \
Format: `Diagnosis — originally X% — reason for underestimation — \
revised assessment with available clinical evidence`

### 2. Pharmacological evidence
Systematically evaluate the response patterns. Which diagnoses are strengthened \
or weakened by the pharmacological pattern? What pathophysiological mechanisms \
does the pattern suggest?

### 3. Methodological corrections
Explicitly name where the purely data-based analysis reaches its limits \
(e.g., score criteria that systematically fail in certain patient constellations).

### 4. Overall assessment after addendum
How does this supplement change the picture compared to the synthesis report? \
What remains open, what is now clearer?
""",
    )


def _call_llm(prompt: str, lang: str) -> str:
    api_key = _cfg._cfg.get("openrouter_api_key", "")
    model   = _cfg._cfg.get("openrouter_model", "anthropic/claude-opus-4-8")
    system  = SYSTEM_DE if lang == "de" else SYSTEM_EN

    if not api_key:
        raise RuntimeError(t(
            "openrouter_api_key nicht konfiguriert.",
            "openrouter_api_key not configured.",
        ))

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 8000,
        "temperature": 0.2,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://github.com/kyoro-healthhub",
            "X-Title":       "Kyoro-HealthHub Clinical Addendum",
        },
        method="POST",
    )
    print(t(
        f"  → Sende {len(payload):,} Byte an {model} …",
        f"  → Sending {len(payload):,} bytes to {model} …",
    ))
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def run(synthesis_path: Path | None, lang: str, dry_run: bool) -> None:
    SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)

    if synthesis_path is None:
        synthesis_path = _find_latest_synthesis()
    print(t(
        f"Synthese-Bericht: {synthesis_path.name}",
        f"Synthesis report: {synthesis_path.name}",
    ))

    synthesis_text = synthesis_path.read_text(encoding="utf-8", errors="replace")
    synthesis_core = _extract_synthesis_core(synthesis_text)

    obs = _load_observations()
    if not obs:
        print(t(
            "⚠  Keine klinischen Beobachtungen in clinical.observations gefunden.\n"
            "   Bitte clinical.observations.treatment_responses und\n"
            "   clinical.observations.diagnostic_limitations in der Config ergänzen.",
            "⚠  No clinical observations found in clinical.observations.\n"
            "   Please add clinical.observations.treatment_responses and\n"
            "   clinical.observations.diagnostic_limitations to the config.",
        ))
        return

    obs_text = _format_observations(obs, lang)
    prompt   = _build_prompt(synthesis_core, obs_text, synthesis_path, lang)

    if dry_run:
        print(t("Dry-run — kein LLM-Aufruf.", "Dry-run — no LLM call."))
        print(f"\n--- PROMPT ({len(prompt)} Zeichen) ---\n{prompt[:2000]}\n[…]")
        return

    print(t("Klinisches Addendum wird generiert …", "Generating clinical addendum …"))
    result = _call_llm(prompt, lang)

    ts       = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out_path = SYNTHESIS_DIR / f"addendum_{ts}.md"

    addendum_model = _cfg._cfg.get('openrouter_model', 'anthropic/claude-opus-4-8')
    header = t(
        f"# Klinisches Addendum — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        f"**Grundlage:** {synthesis_path.name}  \n"
        f"**Modell:** {addendum_model}  \n"
        f"**Zweck:** Ergänzung der Wearable-Synthese um klinische Beobachtungen und "
        f"Methodenkorrekturen\n\n"
        f"{ai_label(addendum_model)}\n\n---\n\n",
        f"# Clinical Addendum — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        f"**Based on:** {synthesis_path.name}  \n"
        f"**Model:** {addendum_model}  \n"
        f"**Purpose:** Supplement of wearable synthesis with clinical observations and "
        f"methodological corrections\n\n"
        f"{ai_label(addendum_model)}\n\n---\n\n",
    )

    out_path.write_text(header + result, encoding="utf-8")
    print(t(
        f"\n✓ Addendum gespeichert: {out_path}",
        f"\n✓ Addendum saved: {out_path}",
    ))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--synthesis", type=Path, default=None,
        help=t(
            "Pfad zum Synthese-Bericht (Standard: neueste Datei in analyses/synthesis/)",
            "Path to synthesis report (default: latest file in analyses/synthesis/)",
        ),
    )
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Prompt anzeigen ohne LLM-Aufruf", "Show prompt without LLM call"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    run(
        synthesis_path=args.synthesis,
        lang=getattr(args, "lang", "de"),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
