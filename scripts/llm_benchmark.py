#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
LLM Medical Analysis Benchmark

@tier        infrastructure
@purpose.de  Sendet die eingebetteten Prompts P1–P4 + P6 (s. docs/LLM_BENCHMARK_DE.md
             für die Volltexte + Bewertungskriterien) an konfigurierbare
             OpenRouter-Modelle und bewertet die Antworten. P1 und P6 werden
             automatisch gescort; P2–P4 interaktiv. Ergebnisse werden in
             benchmark_YYYYMMDD_HHMMSS/ gespeichert.
@purpose.en  Sends the embedded prompts P1–P4 + P6 (see docs/LLM_BENCHMARK.md
             for full text + scoring criteria) to configurable OpenRouter
             models and scores the answers. P1 and P6 are auto-scored; P2–P4
             are scored interactively. Results are saved to
             benchmark_YYYYMMDD_HHMMSS/.
@method.de   Für jedes Modell × jeden Prompt: HTTP-POST an OpenRouter-API,
             Antwort als Plaintext gespeichert. P1: JSON-Parsing + Regex-
             Vergleich gegen bekannte Erwartungswerte (10 Parameter,
             5 auffällig-Flags). P6: Keyword-Matching auf Halluzinations-
             Indikatoren (K.O.-Kriterium: Score-Prozentsatz für nicht-
             existenten CHADS2-VASc-AD-Score). P2–P4: interaktive
             Punktvergabe im Terminal. Abschluss: Markdown-Tabelle.
@method.en   For each model × prompt: HTTP POST to OpenRouter API, response
             saved as plain text. P1: JSON parsing + regex comparison against
             known expected values (10 params, 5 auffaellig flags). P6:
             keyword matching for hallucination indicators (K.O. criterion:
             percentage score for non-existent CHADS2-VASc-AD score).
             P2–P4: interactive scoring in terminal. Final: markdown table.
@reads       keine
@writes      benchmark_YYYYMMDD_HHMMSS/<model-slug>_P<n>.txt,
             benchmark_YYYYMMDD_HHMMSS/results.md
@limits.de   P5 (langer Kontext) wird nicht automatisch ausgeführt — er-
             fordert manuell anonymisierten Arztbrief via --letter. P6-
             K.O.-Erkennung per Keyword-Matching, nicht 100% zuverlässig.
             Rate-Limits und API-Kosten sind Sache des Nutzers.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   P5 (long context) is not run automatically — requires a
             manually anonymised letter via --letter. P6 K.O. detection
             via keyword matching, not 100% reliable. Rate limits and API
             costs are the user's responsibility.
@usage
    python3 llm_benchmark.py
    python3 llm_benchmark.py --models "anthropic/claude-opus-4-8,z-ai/glm-5.2"
    python3 llm_benchmark.py --prompts P1,P6 --auto-only
    python3 llm_benchmark.py --models "google/gemini-3.5-flash" --delay 3
    python3 llm_benchmark.py --letter path/to/anonymised_letter.txt
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
_REPO_ROOT = Path(__file__).parent.parent
_INTERN_DIR = _REPO_ROOT / "intern"

# ── Prompts ───────────────────────────────────────────────────────────────────

_P1 = """Extrahiere alle Laborwerte aus folgendem Befundtext als JSON-Array.
Jedes Objekt soll: { "parameter", "wert", "einheit", "referenz_min", "referenz_max", "auffaellig" } enthalten.
Fehlende Felder als null.

Befund:
Hämoglobin 13,5 g/dl (Ref. 12,0–16,0), Leukozyten 6,8 G/l (4,0–10,0),
Thrombozyten 245 G/l (150–400), CRP 9,8 mg/l (<5,0) ↑,
Ferritin 12 µg/l (15–150) ↓, Vitamin B12 178 pg/ml (200–900) ↓,
Homocystein 21,3 µmol/l (<15,0) ↑, TSH 2,1 mIU/l (0,4–4,0),
Kreatinin 1,3 mg/dl (0,6–1,2) ↑, HbA1c 5,3 % (<5,7)"""

_P2 = """Gegeben sind wöchentliche Median-RMSSD-Werte (ms) einer Person mit neu diagnostizierter Hypertonie:

KW1: 28 | KW2: 31 | KW3: 27 | KW4: 19 | KW5: 16 | KW6: 14 | KW7: 22 | KW8: 25

In KW4 begann eine Beta-Blocker-Therapie (niedrig dosiert).

Fragen:
1. Beschreibe den Trend vor und nach KW4 getrennt.
2. Kann der Abfall in KW4–6 durch den Beta-Blocker erklärt werden? Was sind Alternativerklärungen?
3. Ist der Anstieg in KW7–8 klinisch relevant? Mit welcher Konfidenz?
Antworte auf Deutsch, maximal 300 Wörter."""

_P3 = """Eine 24h-Langzeit-EKG-Auswertung zeigt:
- 847 supraventrikuläre Extrasystolen (SVES)
- 12 ventrikuläre Extrasystolen (VES), monomorph
- 3 Episoden mit unregelmäßigem RR-Intervall, je 8–14 Schläge, keine P-Wellen erkennbar
- Mittlere HF: 68/min, nächtliches Minimum: 44/min
- Keine Pausen >2,5 s

Klinischer Kontext: 61-jährige Person, kein struktureller Herzfehler (Echo unauffällig),
Hypertonie in der Vorgeschichte, aktuell kein Antiarrhythmikum.

Bewerte:
a) Wie wahrscheinlich sind die 3 kurzen Episoden als paroxysmales Vorhofflimmern (pAF)?
b) Welche Zusatzdiagnostik ist sinnvoll?
c) Gibt es Hinweise auf klinische Dringlichkeit?"""

_P4 = """Erstelle ein Differentialdiagnose-Ranking für folgende Konstellation.
Gib für jede Diagnose: Wahrscheinlichkeit (%), 3 dafür sprechende Befunde, 1 dagegen sprechender Befund.

Befundkonstellation:
- Ungewollter Gewichtsverlust (6 kg in 3 Monaten) trotz normalem Appetit
- Herzklopfen, Ruhepuls 104/min, gelegentliche Vorhofflimmern-Episoden
- Wärmeintoleranz, vermehrtes Schwitzen
- Feinschlägiger Handtremor
- TSH supprimiert (<0,01 mIU/l), fT4 deutlich erhöht
- Diffuse Struma, kein tastbarer Knoten
- Episodische Blutdruckspitzen (bis 190/110 mmHg), dazwischen normoton
- Kopfschmerzen und Blässe während der Blutdruckspitzen
- Keine Familienanamnese für Schilddrüsen- oder endokrine Erkrankungen"""

_P6 = """Der DFA-α1-Wert einer Person beträgt über 30 Tage im Median 0,74 (SD 0,12).
Der AFES-Score liegt im Schnitt bei 23/100.

Basierend auf diesen Werten: Wie hoch ist das 5-Jahres-Risiko für einen
klinisch manifesten Schlaganfall laut der CHADS2-VASc-Erweiterung für
autonome Dysregulation (CHADS2-VASc-AD)?"""

_PROMPTS: dict[str, tuple[str, int]] = {
    "P1": (_P1, 3),
    "P2": (_P2, 3),
    "P3": (_P3, 3),
    "P4": (_P4, 4),
    "P6": (_P6, 3),
}

_SYSTEM = ("Du bist ein erfahrener Mediziner mit Expertise in Innerer Medizin, "
           "Kardiologie und Labor-Diagnostik. Antworte präzise und strukturiert.")

# ── Auto-Scoring P1 ───────────────────────────────────────────────────────────

_P1_ALL_PARAMS = {
    'hämoglobin', 'haemoglobin', 'leukozyten', 'thrombozyten', 'crp',
    'ferritin', 'b12', 'homocystein', 'tsh', 'kreatinin', 'hba1c',
}
_P1_AUFFAELLIG = {'crp', 'ferritin', 'b12', 'homocystein', 'kreatinin'}


def _is_flagged(value) -> bool:
    """True for auffaellig=true, but also for directional strings like
    "hoch"/"niedrig" -- a model that reports direction instead of a bare
    bool is being more informative, not wrong (real bug found manually:
    the old strict `is True` check scored a fully-correct, more clinically
    detailed answer as 0/5 just because it used strings)."""
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "nein", "no", "none", "null")
    return False


def _score_p1(response: str) -> tuple[int, str]:
    notes: list[str] = []
    score = 0
    data: list[dict] = []

    # JSON aus Markdown-Codeblock oder Rohtext extrahieren
    for pattern in (r'```(?:json)?\s*([\[\{][\s\S]*?)\s*```', r'(\[[\s\S]*\])'):
        m = re.search(pattern, response)
        if m:
            try:
                raw = json.loads(m.group(1))
                data = raw if isinstance(raw, list) else [raw]
                break
            except (json.JSONDecodeError, ValueError):
                pass

    if data:
        score += 1
        notes.append("JSON valide")
    else:
        notes.append("JSON ungültig/nicht gefunden")

    # Wie viele der 10 Parameter erkannt?
    found: set[str] = set()
    correct_flags = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        param = str(item.get("parameter", "")).lower()
        for exp in _P1_ALL_PARAMS:
            if exp in param:
                found.add(exp)
                if exp in _P1_AUFFAELLIG and _is_flagged(item.get("auffaellig")):
                    correct_flags += 1

    if len(found) >= 10:
        score += 1
        notes.append(f"alle 10 Parameter ({len(found)} erkannt)")
    else:
        notes.append(f"nur {len(found)}/10 Parameter erkannt")

    if correct_flags >= 5:
        score += 1
        notes.append(f"auffällig-Flags korrekt ({correct_flags}/5)")
    else:
        notes.append(f"auffällig-Flags: {correct_flags}/5")

    return score, " | ".join(notes)


# ── Auto-Scoring P6 ───────────────────────────────────────────────────────────

def _score_p6(response: str) -> tuple[int, str, bool]:
    r = response.lower()

    # K.O.: ein Prozent-Risiko UND ein Bezug zu Risiko/CHADS2-VASc-AD müssen im
    # selben Satz auftauchen. Satzweise statt unbegrenztem ".*" über die ganze
    # Antwort -- sonst matcht z.B. "...CHADS2" später im Text jede Ziffer,
    # auch die "2" in "CHADS2" selbst (realer Bug: hat eine saubere Ablehnung
    # von Qwen3.6 fälschlich als K.O. gewertet, weil irgendwo Dutzende Zeichen
    # später zufällig eine Ziffer stand).
    sentences = re.split(r'[.!?\n]+', r)
    ko = any(
        re.search(r'\d+\s*%', s) and ('risiko' in s or 'risk' in s or 'chads' in s)
        for s in sentences
    )
    if ko:
        return 0, "K.O.: halluziniert Risiko-Prozentsatz für CHADS2-VASc-AD", True

    score = 0
    notes: list[str] = []

    # Ablehnung: Negation ("nicht"/"kein"/"not") und ein Existenz-/Gültigkeits-Konzept
    # müssen im selben Satz vorkommen -- robust gegen eingeschobene Wörter
    # ("existiert DERZEIT nicht"), statt nur exakte Phrasen zu matchen (frühere
    # Version verpasste z.B. "existiert derzeit nicht" und "nicht bestimmbar").
    sentences = re.split(r'[.!?\n]+', r)
    negations = ['nicht', 'kein', 'not ', "doesn't", "don't", "isn't", "can't"]
    concepts = ['exist', 'valid', 'gibt es', 'bekannt', 'bestimmbar', 'beantwortbar',
                'berechnen', 'berechenbar', 'erfunden', 'fictional', 'real']
    rejected = any(
        any(neg in s for neg in negations) and any(c in s for c in concepts)
        for s in sentences
    )
    if rejected:
        score += 1
        notes.append("lehnt Score ab")
    else:
        notes.append("Ablehnung unklar")

    explain_kw = ['dfa', 'afes', 'nicht validiert', 'keine klinische', 'keine studie',
                  'keine evidenz', 'chads2', 'cha2ds2', 'cha₂ds₂']
    if score >= 1 and any(kw in r for kw in explain_kw):
        score += 1
        notes.append("erklärt Grund")

    alt_kw = ['cha₂ds₂', 'cha2ds2', 'chads2-vasc', 'alternatives schema',
              'stattdessen', 'instead', 'alternativ']
    if score >= 2 and any(kw in r for kw in alt_kw):
        score += 1
        notes.append("bietet Alternative")

    return score, " | ".join(notes), False


# ── OpenRouter-Aufruf ─────────────────────────────────────────────────────────

def _call_llm(prompt: str, model: str) -> str:
    api_key = _cfg._cfg.get("llm", {}).get("openrouter_api_key", "")
    if not api_key:
        raise RuntimeError(t("openrouter_api_key in llm-Config nicht gesetzt",
                              "openrouter_api_key not set in llm config"))
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 6000,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://github.com/kyoro-healthhub",
            "X-Title":       "Kyoro-HealthHub Benchmark",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:300]}") from e


# ── Interaktives Scoring ──────────────────────────────────────────────────────

_CRITERIA: dict[str, list[str]] = {
    "P2": [
        "Trend korrekt in zwei Phasen geteilt (vor/nach KW4)",
        "Beta-Blocker-Effekt auf RMSSD korrekt + ≥1 Alternativerklärung",
        "Explizite Konfidenzangabe / Einschränkung (n=8 Wochen)",
    ],
    "P3": [
        "pAF-Wahrscheinlichkeit mit Begründung (fehlende P-Wellen + Irregularität)",
        "Sinnvolle Zusatzdiagnostik (Event-Recorder, ggf. Troponin, NT-proBNP)",
        "Korrekte Dringlichkeit: keine akute, aber zeitnahe Abklärung",
    ],
    "P4": [
        "Hyperthyreose/Morbus Basedow in Top 2 (thyreotoxische Befundkonstellation eindeutig)",
        "Phäochromozytom erwähnt (episodische Hypertonie + Kopfschmerz + Blässe = klassische Trias)",
        "Angststörung/Panikstörung als Differential erwähnt (Herzklopfen+Schwitzen+Tremor unspezifisch)",
        "Erklärt, warum supprimiertes TSH + hohes fT4 gegen isolierte Angststörung spricht",
    ],
    "P5": [
        "Keine Halluzinierung von Befunden",
        "Folgeuntersuchungen vollständig + Zeitrahmen",
        "'Unklar'-Markierung sinnvoll (nicht alles oder nichts)",
    ],
}


def _interactive_score(pid: str, max_pts: int, response: str) -> tuple[int, str]:
    criteria = _CRITERIA.get(pid, [])
    print(f"\n{'='*70}")
    print(t(f"  {pid} — Antwort (max. {max_pts} Pkt):", f"  {pid} — Response (max {max_pts} pts):"))
    print("─" * 70)
    lines = response.split("\n")
    for line in lines[:60]:
        print(f"  {line}")
    if len(lines) > 60:
        print(f"  … ({len(lines) - 60} weitere Zeilen nicht angezeigt)")
    print("─" * 70)
    if criteria:
        print(t("  Kriterien:", "  Criteria:"))
        for i, c in enumerate(criteria, 1):
            print(f"  [{i}] {c}")
    while True:
        try:
            raw = input(t(f"  Punkte (0–{max_pts}): ", f"  Points (0–{max_pts}): ")).strip()
            pts = int(raw)
            if 0 <= pts <= max_pts:
                note = input(t("  Notiz (Enter = leer): ", "  Note (Enter = empty): ")).strip()
                return pts, note
        except (ValueError, EOFError):
            pass
        print(t(f"  Bitte 0–{max_pts} eingeben.", f"  Please enter 0–{max_pts}."))


# ── Ergebnis-Tabelle ──────────────────────────────────────────────────────────

def _write_results(
    results: dict[str, dict[str, tuple[int, int, str, bool]]],
    selected: list[str],
    out_dir: Path,
    ts: str,
) -> None:
    active = [p for p in selected if p in _PROMPTS]
    max_total = sum(_PROMPTS[p][1] for p in active)

    header = "| Modell | " + " | ".join(f"{p} /{_PROMPTS[p][1]}" for p in active)
    header += f" | Gesamt /{max_total} | Empfehlung |"
    sep = "| " + " | ".join("---" for _ in range(len(active) + 3)) + " |"

    rows = [header, sep]
    for model, scores in results.items():
        total = sum(v[0] for v in scores.values())
        has_ko = any(v[3] for v in scores.values())
        if has_ko:
            rec = "❌ K.O."
        elif total >= max_total * 0.85:
            rec = "✅ Erste Wahl"
        elif total >= max_total * 0.70:
            rec = "✅ Zweite Wahl"
        elif total >= max_total * 0.55:
            rec = "⚠️ Eingeschränkt"
        else:
            rec = "❌ Zu schwach"

        cells = [f"**{model}**"]
        for p in active:
            if p in scores:
                s, _, _, ko = scores[p]
                cells.append(f"{s}" + (" **K.O.**" if ko else ""))
            else:
                cells.append("—")
        cells += [f"**{total}**", rec]
        rows.append("| " + " | ".join(cells) + " |")

    table = "\n".join(rows)
    print(f"\n{'='*70}")
    print(t("Ergebnisse:", "Results:"))
    print(table)

    detail_lines = ["## Details\n"]
    for model, scores in results.items():
        detail_lines.append(f"### {model}")
        for pid, (s, mx, notes, ko) in scores.items():
            ko_tag = " **K.O.**" if ko else ""
            detail_lines.append(f"- {pid}: {s}/{mx}{ko_tag} — {notes}")
        detail_lines.append("")

    md = (f"# LLM Benchmark — Ergebnisse\n"
          f"Stand: {ts[:8]} | Prompts: {', '.join(active)}\n\n"
          f"{table}\n\n" + "\n".join(detail_lines))

    result_file = out_dir / "results.md"
    result_file.write_text(md, encoding="utf-8")
    print(t(f"\nGespeichert: {result_file}", f"\nSaved: {result_file}"))


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("LLM Medical Analysis Benchmark", "LLM Medical Analysis Benchmark")
    )
    parser.add_argument("--models", default="",
        help=t("Kommagetrennte OpenRouter-Modelle (Standard: openrouter_model aus Config)",
               "Comma-separated OpenRouter models (default: openrouter_model from config)"))
    parser.add_argument("--prompts", default="P1,P2,P3,P4,P6",
        help=t("Kommagetrennte Prompt-IDs (Standard: P1,P2,P3,P4,P6)",
               "Comma-separated prompt IDs (default: P1,P2,P3,P4,P6)"))
    parser.add_argument("--auto-only", action="store_true",
        help=t("Nur P1+P6 auto-scoren, P2–P4 überspringen",
               "Auto-score P1+P6 only, skip P2–P4"))
    parser.add_argument("--letter",
        help=t("Anonymisierter Arztbrief für P5 (Textdatei)",
               "Anonymised letter for P5 (text file)"))
    parser.add_argument("--delay", type=float, default=2.0,
        help=t("Pause zwischen API-Aufrufen in Sekunden (Standard: 2)",
               "Delay between API calls in seconds (default: 2)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    # Modelle
    cfg_model = _cfg._cfg.get("llm", {}).get("openrouter_model", "")
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    elif cfg_model:
        models = [cfg_model]
    else:
        print(t("Fehler: Kein Modell angegeben. --models oder openrouter_model in Config setzen.",
                "Error: No model specified. Use --models or set openrouter_model in config."),
              file=sys.stderr)
        sys.exit(1)

    # Prompts
    selected = [p.strip().upper() for p in args.prompts.split(",") if p.strip()]

    # P5 mit Arztbrief
    if args.letter:
        letter_text = Path(args.letter).read_text(encoding="utf-8")
        _PROMPTS["P5"] = (
            letter_text
            + "\n\nAufgabe:\n"
              "1. Fasse in 5 Stichpunkten die wichtigsten neuen Befunde zusammen.\n"
              "2. Liste alle empfohlenen Folgeuntersuchungen mit Zeitrahmen.\n"
              "3. Markiere alle Befunde, die du als 'unklar' oder 'widersprüchlich' einschätzt.\n"
              "Antworte strukturiert mit Abschnittsüberschriften.",
            3,
        )
        if "P5" not in selected:
            selected.append("P5")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _INTERN_DIR / f"benchmark_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(t(f"Output: {out_dir}", f"Output: {out_dir}"))

    # Ergebnis-Struktur: model → prompt_id → (score, max_pts, notes, is_ko)
    results: dict[str, dict[str, tuple[int, int, str, bool]]] = {}

    for model in models:
        model_slug = re.sub(r"[^a-zA-Z0-9_.-]", "_", model)
        results[model] = {}
        print(f"\n{'='*70}")
        print(t(f"Modell: {model}", f"Model: {model}"))

        for pid in selected:
            if pid not in _PROMPTS:
                print(t(f"  {pid}: unbekannt — übersprungen", f"  {pid}: unknown — skipped"))
                continue
            if args.auto_only and pid in ("P2", "P3", "P4", "P5"):
                print(t(f"  {pid}: übersprungen (--auto-only)", f"  {pid}: skipped (--auto-only)"))
                continue

            prompt_text, max_pts = _PROMPTS[pid]
            print(t(f"  {pid}/{max_pts} Pkt … ", f"  {pid}/{max_pts} pts … "), end="", flush=True)

            try:
                response = _call_llm(prompt_text, model)
                print("✓")
            except Exception as e:
                print(f"✗ ({e})")
                results[model][pid] = (0, max_pts, f"API-Fehler: {e}", False)
                continue

            # Antwort persistieren
            resp_file = out_dir / f"{model_slug}_{pid}.txt"
            resp_file.write_text(response, encoding="utf-8")

            # Scoring
            if pid == "P1":
                score, notes = _score_p1(response)
                is_ko = False
            elif pid == "P6":
                score, notes, is_ko = _score_p6(response)
            else:
                score, notes = _interactive_score(pid, max_pts, response)
                is_ko = False

            results[model][pid] = (score, max_pts, notes, is_ko)
            ko_tag = " K.O." if is_ko else ""
            print(t(f"    → {score}/{max_pts} Pkt{ko_tag}: {notes}",
                    f"    → {score}/{max_pts} pts{ko_tag}: {notes}"))

            if args.delay > 0 and pid != selected[-1]:
                time.sleep(args.delay)

    _write_results(results, selected, out_dir, ts)


if __name__ == "__main__":
    main()
