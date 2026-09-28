#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
medical_query.py — Medizinische Datenanalyse via LLM

@tier        heuristic
@purpose.de  Analysiert medizinische Daten aus CSV-Dateien direkt über LLM-Modelle.
             Ermöglicht natürliche Sprachabfragen auf Laborbefunde und Medikamentendaten.
@purpose.en  Analyzes medical data from CSV files directly via LLM models.
             Enables natural language queries on lab results and medication data.
@method.de   Liest CSV-Dateien aus verschiedenen Quellen: Laborbefunde, Medikamente,
             Gesundheitsdaten. Unterstützt verschiedene spezialisierte medizinische Modelle
             (Med42, OpenBioLLM, MMed, BioMistral) und Ensembles.
@method.en   Reads CSV files from various sources: lab results, medications,
             health data. Supports various specialized medical models
             (Med42, OpenBioLLM, MMed, BioMistral) and ensembles.
@reads       medicine/laborbefunde/*.csv, medicine/medikamente.csv,
             imports/manual/health_visits.txt
@writes      analyses/medical/ Verzeichnis (LLM-Analyseergebnisse)
@limits.de   Heuristische Methode: Ergebnisse hängen von der Qualität der LLM-Modelle und der Eingabedaten ab.
             Keine automatische Validierung. Dient nur zur Unterstützung, nicht zur Diagnose.
@limits.en   Heuristic method: Results depend on LLM model quality and input data quality.
             No automatic validation. For support only, not for diagnosis.
@refs        Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
             Moor M, Banerjee O, Abad ZSH et al. (2023). Foundation models for generalist medical artificial intelligence. Nature, 616(7956):259-265. doi:10.1038/s41586-023-05881-4

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@scoring Relevanz-Score basierend auf Abweichung von Referenzbereichen und klinischer Signifikanz
@usage
    python medical_query.py labor                    # Med42 (Standard)
    python medical_query.py labor --model qwen3
    python medical_query.py labor --ensemble
    python medical_query.py medikamente
    python medical_query.py health_visits
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import Config as _Cfg
_cfg = _Cfg()

LABOR_DIR    = Path(__file__).parents[2] / "medicine" / "laborbefunde"
MEDIZIN_DIR  = Path(__file__).parents[2] / "medicine"
MANUELL_DIR  = _cfg.manual_dir
ANALYSEN_DIR = Path(__file__).parents[2] / "analyses" / "medical"

try:
    import openvino_genai as ov_genai
    _OV_OK = True
except ImportError:
    _OV_OK = False

# ── Modelle ───────────────────────────────────────────────────────────────────
MODELS = {
    # Medizinisch spezialisiert
    "med42":        Path.home() / "models" / "med42-8b-genai",
    "openbiollm":   Path.home() / "models" / "openbiollm-8b-genai",
    "mmed":         Path.home() / "models" / "mmed-llama3-8b-genai",
    "biomistral":   Path.home() / "models" / "biomistral-7b-genai",
    "medicine":     Path.home() / "models" / "medicine-chat-genai",
    # German-optimiert
    "sauerkraut":   Path("/opt/voice-assistant/sauerkraut-14b-genai"),
    "eurollm":      Path("/opt/voice-assistant/eurollm-9b-int4-genai"),
    # Allgemein
    "qwen3":        _cfg.llm_path,
}

# Med42 ist Standard for Laborbefunde (clinical spezialisiert)
DEFAULT_MODEL    = "med42"
ENSEMBLE_MODELS  = ["med42", "openbiollm", "mmed"]       # Medizin-Ensemble
ENSEMBLE_DE      = ["eurollm", "sauerkraut"]             # Deutsch-Ensemble
ENSEMBLE_ALL     = ["med42", "openbiollm", "eurollm"]    # Gemischt

# 8B/9B-Modelle auf CPU stabiler; größere auf GPU
DEVICE_LARGE = _cfg.llm_device
DEVICE_8B    = "CPU"
_LARGE_MODELS = {"qwen3", "sauerkraut"}  # ≥14B → GPU

LLAMA3_MODELS  = {"med42", "mmed", "medicine"}
PLAIN_MODELS   = {"openbiollm"}   # kein chat_template → plain prompt
MISTRAL_MODELS = {"biomistral"}
CHATML_MODELS  = {"sauerkraut", "eurollm", "qwen3"}
# Modelle without chat_template → Plain-Prompt (System + User als Fließtext)
_DEUTSCH = "\n\nWICHTIG: Antworte ausschließlich auf Deutsch."


# ── LLM-Infrastruktur ─────────────────────────────────────────────────────────
def _load_model(name: str) -> "ov_genai.LLMPipeline":
    path = MODELS.get(name)
    if path is None:
        raise ValueError(f"Unbekanntes Modell: {name}. Verfügbar: {list(MODELS)}")
    if not path.exists():
        raise FileNotFoundError(f"Modell nicht gefunden: {path}")
    device = DEVICE_LARGE if name in _LARGE_MODELS else DEVICE_8B
    print(t(f"  Lade {name} auf {device} ...", f"  Loading {name} on {device} ..."), end=" ", flush=True)
    pipe = ov_genai.LLMPipeline(str(path), device)
    print("OK")
    return pipe


def _generate(pipe: "ov_genai.LLMPipeline", model_name: str,
              system: str, user: str, max_tokens: int = 4000) -> str:
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens     = max_tokens
    cfg.temperature        = 0.3
    cfg.do_sample          = True
    cfg.repetition_penalty = 1.1

    if model_name in PLAIN_MODELS:
        prompt = f"### System:\n{system}\n\n### User:\n{user}\n\n### Assistant:\n"
    elif model_name in MISTRAL_MODELS:
        prompt = (f"<s>[INST] {system}\n\nWICHTIG: Antworte AUSSCHLIESSLICH auf DEUTSCH.\n\n"
                  f"{user} [/INST] Analyse auf Deutsch:")
    elif model_name in LLAMA3_MODELS:
        prompt = (f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                  f"{system}{_DEUTSCH}<|eot_id|>"
                  f"<|start_header_id|>user<|end_header_id|>\n\n"
                  f"{user}<|eot_id|>"
                  f"<|start_header_id|>assistant<|end_header_id|>\n\n")
    elif model_name in CHATML_MODELS:
        prompt = (f"<|im_start|>system\n{system}{_DEUTSCH}<|im_end|>\n"
                  f"<|im_start|>user\n{user}<|im_end|>\n"
                  f"<|im_start|>assistant\n")
    else:
        prompt = f"{system}\n\n{user}"

    return pipe.generate(prompt, cfg).strip()


def _run_llm(system: str, user: str, model: str = DEFAULT_MODEL,
             ensemble: str | None = None, max_tokens: int = 4000,
             use_provider: bool = False) -> None:
    if use_provider or not _OV_OK:
        from utils.llm_provider import LLMProvider
        provider = LLMProvider.from_config()
        print(t(f"\n── KI-Analyse: {provider.name} ──",
                f"\n── AI Analysis: {provider.name} ──"))
        try:
            result = provider.chat(system, user, max_tokens=max_tokens)
            print(result)
            from datetime import datetime
            ANALYSEN_DIR.mkdir(parents=True, exist_ok=True)
            ts  = datetime.now().strftime("%Y-%m-%d_%H-%M")
            out = ANALYSEN_DIR / f"{ts}_provider.md"
            out.write_text(
                f"# Analyse — {provider.name} — {ts}\n\n"
                f"## Prompt\n\n{user}\n\n"
                f"## Analyse\n\n{result}\n",
                encoding="utf-8"
            )
            print(t(f"\n  → gespeichert: {out.name}", f"\n  → saved: {out.name}"))
        except Exception as e:
            print(t(f"  Fehler: {e}", f"  Error: {e}"))
        return

    if ensemble == "medizin":
        models_to_run = ENSEMBLE_MODELS
    elif ensemble == "deutsch":
        models_to_run = ENSEMBLE_DE
    elif ensemble == "alle":
        models_to_run = ENSEMBLE_ALL
    else:
        models_to_run = [model]

    from datetime import datetime
    ANALYSEN_DIR.mkdir(parents=True, exist_ok=True)

    for name in models_to_run:
        path = MODELS.get(name)
        if path is None or not path.exists():
            print(t(f"\n[{name}: nicht gefunden, übersprungen]", f"\n[{name}: not found, skipped]"))
            continue
        print(t(f"\n── KI-Analyse: {name} {'─'*(44-len(name))}", f"\n── AI Analysis: {name} {'─'*(44-len(name))}"))
        try:
            pipe   = _load_model(name)
            result = _generate(pipe, name, system, user, max_tokens=max_tokens)
            print(result)
            del pipe

            # Automatisch speichern
            ts  = datetime.now().strftime("%Y-%m-%d_%H-%M")
            out = ANALYSEN_DIR / f"{ts}_{name}.md"
            out.write_text(
                f"# Laboranalyse — {name} — {ts}\n\n"
                f"## Prompt\n\n{user}\n\n"
                f"## Analyse\n\n{result}\n",
                encoding="utf-8"
            )
            print(t(f"\n  → gespeichert: Analysen/{out.name}", f"\n  → saved: Analysen/{out.name}"))
        except Exception as e:
            print(t(f"  Fehler: {e}", f"  Error: {e}"))


# ── CSV laden ─────────────────────────────────────────────────────────────────
def _float(s) -> float | None:
    if s is None:
        return None
    try:
        return float(str(s).strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


def load_labor(csv_path: Path | None = None) -> list[dict]:
    """Loads Labor-CSVs. csv_path=None → all in Laborbefunde/, sonst only diese File."""
    rows = []

    if csv_path is not None:
        sources = [csv_path]
    elif LABOR_DIR.exists():
        sources = sorted(LABOR_DIR.glob("*.csv"), reverse=True)
    else:
        return rows

    for csv_path in sources:
        with open(csv_path, encoding="utf-8") as f:
            header_seen = False
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                parts = stripped.split(",")
                if not header_seen and parts[0] == "datum":
                    header_seen = True
                    continue
                if len(parts) < 4:
                    continue

                datum      = parts[0].strip()
                parameter  = parts[1].strip()
                kategorie  = parts[2].strip() if len(parts) > 2 else ""
                wert_raw   = parts[3].strip() if len(parts) > 3 else ""
                einheit    = parts[4].strip() if len(parts) > 4 else ""
                ref_min    = _float(parts[5]) if len(parts) > 5 else None
                ref_max    = _float(parts[6]) if len(parts) > 6 else None
                labor      = parts[7].strip() if len(parts) > 7 else ""
                status     = parts[8].strip() if len(parts) > 8 else ""
                kommentar  = parts[9].strip() if len(parts) > 9 else ""

                if not datum or not parameter:
                    continue

                wert = _float(wert_raw)
                qualitativ = None
                if wert is None and wert_raw:
                    qualitativ = wert_raw.lower().replace("negative", "negativ").replace("positive", "positiv")

                rows.append({
                    "datum":     datum,
                    "parameter": parameter,
                    "kategorie": kategorie or _guess_kat(parameter),
                    "wert":      wert,
                    "qualitativ": qualitativ,
                    "einheit":   einheit,
                    "ref_min":   ref_min,
                    "ref_max":   ref_max,
                    "status":    status,
                    "kommentar": kommentar,
                    "labor":     labor,
                    "quelle":    csv_path.name,
                })

    return rows


def _guess_kat(param: str) -> str:
    for prefix, kat in [
        ("TSH", "Schilddrüse"), ("fT", "Schilddrüse"), ("TPO", "Schilddrüse"),
        ("Trijod", "Schilddrüse"), ("Tretrajod", "Schilddrüse"),
        ("Leukozyten", "Blutbild"), ("Erythrozyten", "Blutbild"),
        ("Hämoglobin", "Blutbild"), ("MCV", "Blutbild"), ("MCH", "Blutbild"),
        ("Thrombozyten", "Blutbild"), ("Neutrophile", "Blutbild"),
        ("CRP", "Entzündung"), ("Ferritin", "Eisen/Entzündung"),
        ("Transferrin", "Eisen"), ("Vitamin", "Vitamine"),
        ("Folsäure", "Vitamine"), ("HbA1c", "Metabolismus"),
        ("Cholesterin", "Metabolismus"), ("Triglyceride", "Metabolismus"),
        ("Kreatinin", "Niere/Leber"), ("GPT", "Niere/Leber"),
        ("GOT", "Niere/Leber"), ("Borrelia", "Immunologie"),
        ("Hepatitis", "Immunologie"),
    ]:
        if param.startswith(prefix):
            return kat
    return "Sonstiges"


# ── Analysen ──────────────────────────────────────────────────────────────────
def analyse_labor(model: str = DEFAULT_MODEL, ensemble: str | None = None,
                  csv_path: Path | None = None, max_tokens: int = 4000,
                  use_provider: bool = False) -> None:
    rows = load_labor(csv_path)
    if not rows:
        print(t(f"Keine Labor-CSVs in {LABOR_DIR}", f"No lab CSVs in {LABOR_DIR}"))
        print(t("Workflow: python import_lab_results.py befund.pdf", "Workflow: python import_lab_results.py report.pdf"))
        return

    # Statistik
    daten = sorted({r["datum"] for r in rows})
    params = {r["parameter"] for r in rows}
    print(t("\n── Laborbefunde ────────────────────────────────────────", "\n── Lab Results ─────────────────────────────────────────"))
    print(t(f"  {len(rows)} Werte | {len(params)} Parameter | {len(daten)} Befunddatum/daten", f"  {len(rows)} values | {len(params)} parameters | {len(daten)} report date(s)"))
    print(t(f"  Zeitraum: {daten[0]} → {daten[-1]}", f"  Period: {daten[0]} → {daten[-1]}"))

    # Notable Werte
    auffaellig = [r for r in rows if r["status"] in ("hoch", "niedrig")]
    if auffaellig:
        print(t(f"\n  AUFFÄLLIG ({len(auffaellig)} Werte):", f"\n  NOTABLE ({len(auffaellig)} values):"))
        print(t(f"  {'Datum':<12} {'Parameter':<38} {'Wert':>10}  {'Ref':<18} St.", f"  {'Date':<12} {'Parameter':<38} {'Value':>10}  {'Ref':<18} St."))
        print("  " + "─" * 78)
        kat_prev = None
        for r in sorted(auffaellig, key=lambda x: (x["kategorie"], x["parameter"], x["datum"])):
            if r["kategorie"] != kat_prev:
                print(f"\n  [{r['kategorie']}]")
                kat_prev = r["kategorie"]
            wert_str = f"{r['wert']} {r['einheit']}".strip() if r["wert"] is not None else r["qualitativ"] or "?"
            ref_min, ref_max = r["ref_min"], r["ref_max"]
            if ref_min is not None and ref_max is not None:
                ref_str = f"{ref_min}–{ref_max}"
            elif ref_max is not None:
                ref_str = f"<{ref_max}"
            elif ref_min is not None:
                ref_str = f">{ref_min}"
            else:
                ref_str = ""
            marker = "↑" if r["status"] == "hoch" else "↓"
            print(f"  {r['datum']:<12} {r['parameter']:<38} {wert_str:>10}  {ref_str:<18} {marker}")
    else:
        print(t("\n  Alle Werte im Referenzbereich.", "\n  All values within reference range."))

    # Kategorien-Overview
    from collections import Counter
    kats = Counter(r["kategorie"] for r in rows)
    print(t("\n  KATEGORIEN:", "\n  CATEGORIES:"))
    for kat, n in sorted(kats.items()):
        print(t(f"  {kat:<30} {n} Werte", f"  {kat:<30} {n} values"))

    # Zeitverlauf for Schlüsselparameter (mehrere Messzeitpunkte)
    from collections import defaultdict
    by_param = defaultdict(list)
    for r in rows:
        by_param[r["parameter"]].append(r)

    mehrfach = {p: vs for p, vs in by_param.items() if len(vs) > 1}
    if mehrfach:
        print(t("\n  VERLAUF (Parameter mit mehreren Messungen):", "\n  TREND (parameters with multiple measurements):"))
        for param, vs in sorted(mehrfach.items()):
            einheit = vs[0]["einheit"]
            print(f"\n  {param} ({einheit}):")
            for r in sorted(vs, key=lambda x: x["datum"]):
                wert_str = str(r["wert"]) if r["wert"] is not None else r["qualitativ"] or "?"
                marker = " ↑" if r["status"] == "hoch" else (" ↓" if r["status"] == "niedrig" else "")
                print(f"    {r['datum']}  {wert_str}{marker}")

    # KI-Prompt
    auff_text = "\n".join(
        f"{r['datum']} {r['parameter']} {r['wert']} {r['einheit']} "
        f"({'↑' if r['status']=='hoch' else '↓'}, Ref {r['ref_min']}–{r['ref_max']})"
        for r in auffaellig
    ) or "Keine"

    alle_text = "\n".join(
        f"{r['parameter']}: {r['wert'] if r['wert'] is not None else r['qualitativ']} {r['einheit']} "
        f"[{r['datum']}]"
        for r in sorted(rows, key=lambda x: (x["kategorie"], x["parameter"]))
    )

    system = (
        "Du bist ein erfahrener Internist und Labormediziner. "
        "Analysiere Laborbefunde klinisch präzise und praxisnah."
    )
    user = f"""Laborbefunde:

Alle Werte:
{alle_text}

Auffällig (außerhalb Referenzbereich):
{auff_text}

Aufgaben:
1. Klinische Einordnung der auffälligen Werte
2. Muster und Zusammenhänge (z.B. Entzündungszeichen, Gerinnungsstatus)
3. Verlaufsbewertung sofern mehrere Messungen vorliegen
4. Empfehlungen (weitere Diagnostik, Monitoring-Intervall)

Ausschließlich auf Basis der vorliegenden Laborwerte antworten.
Antwort auf Deutsch, nach Kategorien strukturiert."""

    _run_llm(system, user, model=model, ensemble=ensemble, max_tokens=max_tokens,
             use_provider=use_provider)


def analyse_medikamente() -> None:
    csv_path = MEDIZIN_DIR / "medikamente.csv"
    if not csv_path.exists():
        print(t(f"Keine medikamente.csv in {MEDIZIN_DIR}", f"No medikamente.csv in {MEDIZIN_DIR}"))
        print(t("Format: name,wirkstoff,dosis,einheit,frequenz,seit,bis,indikation", "Format: name,ingredient,dose,unit,frequency,since,until,indication"))
        return

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("name,"):
                continue
            parts = s.split(",")
            rows.append({
                "name":       parts[0].strip() if len(parts) > 0 else "",
                "wirkstoff":  parts[1].strip() if len(parts) > 1 else "",
                "dosis":      parts[2].strip() if len(parts) > 2 else "",
                "einheit":    parts[3].strip() if len(parts) > 3 else "",
                "frequenz":   parts[4].strip() if len(parts) > 4 else "",
                "seit":       parts[5].strip() if len(parts) > 5 else "",
                "bis":        parts[6].strip() if len(parts) > 6 else "",
                "indikation": parts[7].strip() if len(parts) > 7 else "",
            })

    if not rows:
        print(t("Keine Medikamente eingetragen.", "No medications entered."))
        return

    print(t("\n── Medikamente ─────────────────────────────────────────", "\n── Medications ─────────────────────────────────────────"))
    aktiv    = [r for r in rows if not r["bis"]]
    inaktiv  = [r for r in rows if r["bis"]]

    print(t(f"\n  AKTUELL ({len(aktiv)}):", f"\n  CURRENT ({len(aktiv)}):"))
    print(t(f"  {'Name':<28} {'Dosis':<15} {'Seit':<12} Indikation", f"  {'Name':<28} {'Dose':<15} {'Since':<12} Indication"))
    print("  " + "─" * 70)
    for r in aktiv:
        dosis = f"{r['dosis']} {r['einheit']}".strip()
        print(f"  {r['name']:<28} {dosis:<15} {r['seit']:<12} {r['indikation']}")

    if inaktiv:
        print(t(f"\n  ABGESETZT ({len(inaktiv)}):", f"\n  DISCONTINUED ({len(inaktiv)}):"))
        for r in inaktiv:
            dosis = f"{r['dosis']} {r['einheit']}".strip()
            print(f"  {r['name']:<28} {dosis:<15} {r['seit']}–{r['bis']}  {r['indikation']}")


def analyse_arztbesuche() -> None:
    txt_path = MANUELL_DIR / "arztbesuche.txt"
    if not txt_path.exists() or txt_path.stat().st_size == 0:
        print(t(f"Keine Arztbesuche in {txt_path}", f"No doctor visits in {txt_path}"))
        print(t("Format: Datum | Facharzt | Anlass | Diagnosen | Maßnahmen", "Format: Date | Specialist | Reason | Diagnoses | Measures"))
        return

    print(t("\n── Arztbesuche ─────────────────────────────────────────", "\n── Doctor Visits ────────────────────────────────────────"))
    with open(txt_path, encoding="utf-8") as f:
        print(f.read())


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Medizinische Befund-Analyse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Verfügbare Modelle: {', '.join(MODELS)}
Standard: {DEFAULT_MODEL}
Ensemble: {', '.join(ENSEMBLE_MODELS)}"""
    )
    parser.add_argument("befehl", nargs="?",
                        choices=["labor", "medikamente", "arztbesuche", "hilfe"],
                        help="Analysebefehl")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        choices=list(MODELS),
                        help=f"KI-Modell (Standard: {DEFAULT_MODEL})")
    parser.add_argument("--ensemble",
                        nargs="?", const="medizin",
                        choices=["medizin", "deutsch", "alle"],
                        help="medizin (med42+openbiollm+mmed), deutsch (eurollm+sauerkraut), alle (med42+openbiollm+eurollm)")
    parser.add_argument("--csv", metavar="DATEI",
                        help="Einzelne CSV-Datei analysieren (Standard: alle)")
    parser.add_argument("--max-tokens", type=int, default=4000, metavar="N",
                        help="Max. Output-Token pro Modell (Standard: 4000)")
    parser.add_argument("--kein-llm", action="store_true",
                        help=t("Nur Statistik, keine KI-Analyse",
                               "Statistics only, no AI analysis"))
    parser.add_argument("--provider", action="store_true",
                        help=t("LLM-Provider aus health_config.json nutzen statt lokaler Modelle",
                               "Use LLM provider from health_config.json instead of local models"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if not args.befehl or args.befehl == "hilfe":
        print(t("\nVerfügbare Befehle:", "\nAvailable commands:"))
        print(t("  labor            Laborbefunde (Statistik + KI-Analyse)", "  labor            Lab results (statistics + AI analysis)"))
        print(t("  medikamente      Medikamenten-Historie", "  medikamente      Medication history"))
        print(t("  arztbesuche      Arztbesuche & Diagnosen", "  arztbesuche      Doctor visits & diagnoses"))
        print(t("\nOptionen für 'labor':", "\nOptions for 'labor':"))
        print(f"  --model NAME     Modell wählen ({', '.join(MODELS)})")
        print("  --ensemble medizin   med42 + openbiollm + mmed")
        print("  --ensemble deutsch   eurollm + sauerkraut")
        print("  --ensemble alle      med42 + openbiollm + eurollm")
        print(t("  --kein-llm           Nur Statistik, keine KI", "  --kein-llm           Statistics only, no AI"))
        print(t(f"\nLabor-CSVs:  {LABOR_DIR}", f"\nLab CSVs:    {LABOR_DIR}"))
        model_status = [
            f"  {'✓' if p.exists() else '✗'} {n:<12} {p.name}"
            for n, p in MODELS.items()
        ]
        print(t("\nModelle:", "\nModels:"))
        print("\n".join(model_status))
        return

    if args.befehl == "labor":
        if args.kein_llm:
            global _OV_OK
            _OV_OK = False
        csv = Path(args.csv) if args.csv else None
        if csv and not csv.exists():
            print(t(f"Datei nicht gefunden: {csv}", f"File not found: {csv}"))
            sys.exit(1)
        analyse_labor(model=args.model, ensemble=args.ensemble,
                      csv_path=csv, max_tokens=args.max_tokens,
                      use_provider=args.provider)

    elif args.befehl == "medikamente":
        analyse_medikamente()
    elif args.befehl == "arztbesuche":
        analyse_arztbesuche()


if __name__ == "__main__":
    main()
