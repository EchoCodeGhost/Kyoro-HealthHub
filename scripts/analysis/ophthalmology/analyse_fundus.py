#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_fundus.py — Fundusfotos auswerten (VLM) und Verlauf anzeigen

Usage:
  python3 scripts/analysis/ophthalmology/analyse_fundus.py              # Übersicht aller Fundus-Aufnahmen
  python3 scripts/analysis/ophthalmology/analyse_fundus.py --analyse    # VLM für alle noch nicht analysierten Bilder
  python3 scripts/analysis/ophthalmology/analyse_fundus.py --exam 3     # Befunde für Untersuchung ID 3

@tier        heuristic
@refs        Esteva A, Kuprel B, Novoa RA et al. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542(7639):115-118. doi:10.1038/nature21056
             Gulshan V, Peng L, Coram M et al. (2016). Development and Validation of a Deep Learning Algorithm for Detection of Diabetic Retinopathy in Retinal Fundus Photographs. JAMA, 316(22):2402. doi:10.1001/jama.2016.17216
@relevance.de Ermöglicht die automatisierte Auswertung von Fundusfotos zur Früherkennung
             von Netzhautveränderungen, essentiell für die Unterstützung der
             ophthalmologischen Diagnostik und Verlaufskontrolle
@relevance.en Enables automated evaluation of fundus photographs for early detection of
             retinal changes, essential for supporting ophthalmological assessment and
             monitoring
@prompt-classification LLM:Analysis
@prompt.de _SYSTEM_DE
@prompt.en _SYSTEM_EN
@purpose.de  Wertet Fundusfotos via Vision Language Model (VLM) aus: Sehnervkopf
             (Cup-to-Disc-Ratio, ISNT-Regel), Gefäßbefunde und Netzhaut; speichert
             strukturierten Befundtext in imaging_analysis.
@purpose.en  Evaluates fundus photographs via Vision Language Model (VLM): optic disc
             (cup-to-disc ratio, ISNT rule), vessel findings and retina; stores structured
             findings text in imaging_analysis.
@method.de   Strukturierter VLM-Prompt für klinische Befundbeschreibung (kein Bewertung-Output);
             Ergebnisse werden in imaging_analysis (DB) gespeichert. Keine automatische
             quantitative Bildauswertung — reine LLM-Textgenerierung.
@method.en   Structured VLM prompt for clinical findings description (no assessment output);
             results stored in imaging_analysis (DB). No automatic quantitative image
             analysis — pure LLM text generation.
@limits.de   Heuristische Methode: VLM-Output ist nicht für klinische Diagnosen validiert. Bildqualität und
             Beleuchtung beeinflussen die Beschreibungsqualität. Kein Vergleich mit
             ophthalmologischer Referenzdiagnose. n=1, explorativ.
@limits.en   Heuristic method: VLM output is not validated for clinical diagnoses. Image quality and
             illumination affect description quality. No comparison with ophthalmological
             reference assessment. n=1, exploratory.
@scoring
    Finding categories: optic_disc | vessels | retina | other
    Severity: normal | mild | moderate | severe | not_assessable
@reads       imaging_files (medicine_imaging_db), imaging_analysis (medicine_imaging_db)
@writes      imaging_analysis (DB-Write), analyses/ophthalmology/*.{md,png}

@usage
    python analyse_fundus.py
    python analyse_fundus.py --help
    python analyse_fundus.py --from 2024-01-01 --to 2024-12-31
"""

from __future__ import annotations

import argparse
import base64
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config, OWN_PERSON_ID
from modules.db import open_medicine_imaging_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import call_llm
from modules.prompts.analysis_ophthalmology import (
    SYSTEM_DE_ANALYSE_FUNDUS as _SYSTEM_DE,
    SYSTEM_EN_ANALYSE_FUNDUS as _SYSTEM_EN,
)

_cfg    = Config()
OUT_DIR = _cfg.analyses_dir / "ophthalmology"

VLM_PROMPT_DE = """Analysiere dieses Fundusfoto klinisch und präzise:

**1. Sehnervkopf (Papilla nervi optici)**
- Cup-to-Disc-Ratio (vertikal + horizontal, numerische Schätzung)
- Neuroretinaler Randsaum: ISNT-Regel (inferior ≥ superior ≥ nasal ≥ temporal)?
- Excavationsform: zentral / temporal / diffus / fokales Notching?
- Papillenrand: scharf oder unscharf, Blutungen, Splitter-Hämorrhagien?
- Gefäßknick am Papillenrand (Bayonetting)?

**2. Gefäße**
- Arterio-venöses Kaliberverhältnis (normal ~2:3)
- Kaliberunregelmäßigkeiten, Engstellungen, Kreuzungszeichen
- Gefäßverlauf: nasal/temporal verschoben?

**3. Netzhaut**
- Makulabereich: Reflexe, Drusen, Pigmentveränderungen
- Periphere Netzhaut: Blutungen, Exsudate, Läsionen

**4. Gesamtbeurteilung**
- Verdacht auf Glaukom / Normaldruckglaukom? Begründung.
- Differenzialdiagnose zur Papillenexkavation (große physiologische Papille, AION, etc.)
- Dringlichkeit weiterer Diagnostik (1=elektiv, 2=zeitnah, 3=dringend)

Bitte strukturiert antworten, numerische Schätzungen wo möglich."""

VLM_PROMPT_EN = """Analyze this fundus photograph clinically and precisely:

**1. Optic Disc (Papilla nervi optici)**
- Cup-to-disc ratio (vertical + horizontal, numeric estimate)
- Neuroretinal rim: ISNT rule (inferior ≥ superior ≥ nasal ≥ temporal)?
- Excavation pattern: central / temporal / diffuse / focal notching?
- Disc margin: sharp or blurred, hemorrhages, splinter hemorrhages?
- Bayonetting sign at disc margin?

**2. Vessels**
- Arterio-venous caliber ratio (normal ~2:3)
- Caliber irregularities, narrowing, arterio-venous nicking
- Vessel course: nasally/temporally displaced?

**3. Retina**
- Macular area: reflexes, drusen, pigment changes
- Peripheral retina: hemorrhages, exudates, lesions

**4. Overall Assessment**
- Suspicion of glaucoma / normal-tension glaucoma? Rationale.
- Differential assessment for disc excavation (large physiological disc, AION, etc.)
- Urgency of further diagnostics (1=elective, 2=soon, 3=urgent)

Please respond in structured format with numeric estimates where possible."""


# ── Daten laden ───────────────────────────────────────────────────────────────

def _load_exams(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT f.id, f.acquisition_date, f.laterality, f.file_path,
               f.manufacturer, f.model_name,
               a.id AS ana_id, a.ts AS ana_ts, a.model AS ana_model
        FROM imaging_files f
        LEFT JOIN imaging_analysis a ON a.file_id = f.id
        WHERE f.person=? AND (f.modality='fundus' OR f.image_type IS NULL
              OR f.file_path LIKE '%fundus%')
        ORDER BY f.acquisition_date, f.laterality, f.id
    """, (OWN_PERSON_ID,)).fetchall()
    cols = ["id","date","laterality","file_path","manufacturer","model",
            "ana_id","ana_ts","ana_model"]
    seen: dict[int, dict] = {}
    for r in rows:
        d = dict(zip(cols, r))
        fid = d["id"]
        if fid not in seen or (d["ana_ts"] or "") > (seen[fid]["ana_ts"] or ""):
            seen[fid] = d
    return sorted(seen.values(), key=lambda x: (x["date"] or "", x["laterality"] or ""))


def _load_response(conn, file_id: int) -> str | None:
    row = conn.execute(
        "SELECT response FROM imaging_analysis WHERE file_id=? ORDER BY ts DESC LIMIT 1",
        (file_id,)
    ).fetchone()
    return row[0] if row else None


# ── VLM ───────────────────────────────────────────────────────────────────────

def _run_vlm(conn, exam: dict, lang: str) -> None:
    file_path = Path(exam["file_path"])
    if not file_path.exists():
        print(t(f"  Datei nicht gefunden: {file_path}", f"  File not found: {file_path}"),
              file=sys.stderr)
        return

    lat  = exam["laterality"] or "?"
    print(t(f"  VLM — {file_path.name} [{lat}] …", f"  VLM — {file_path.name} [{lat}] …"))

    prompt = VLM_PROMPT_DE if lang == "de" else VLM_PROMPT_EN
    system = _SYSTEM_DE      if lang == "de" else _SYSTEM_EN
    img_b64 = base64.b64encode(file_path.read_bytes()).decode()

    try:
        response = call_llm(prompt, system=system, image_b64=img_b64,
                            max_tokens=1800, temperature=0.1, label_output=False)
    except Exception as e:
        print(t(f"  VLM-Fehler: {e}", f"  VLM error: {e}"), file=sys.stderr)
        return

    llm_model = _cfg._cfg.get("llm", {}).get("openrouter_model", "anthropic/claude-opus-4-8")
    now       = datetime.now(timezone.utc).isoformat()

    conn.execute("""
        INSERT INTO imaging_analysis (file_id, ts, model, prompt, response, laterality, source)
        VALUES (?,?,?,?,?,?,?)
    """, (exam["id"], now, llm_model, prompt, response, exam["laterality"], "vlm_fundus"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lat_label   = (exam["laterality"] or "X").upper()
    date_label  = (exam["date"] or now[:10]).replace("-", "")
    report_path = OUT_DIR / f"fundus_{date_label}_{lat_label}.md"
    report_path.write_text(
        f"# Fundus-Analyse {exam['date'] or now[:10]} — Auge {lat_label}\n\n"
        f"**Modell:** {llm_model}  \n"
        f"**Datei:** {file_path.name}\n\n"
        f"---\n\n{response}\n",
        encoding="utf-8",
    )
    print(t(f"  → {report_path.name}", f"  → {report_path.name}"))


# ── Ausgabe ───────────────────────────────────────────────────────────────────

def _render_overview(exams: list[dict]) -> str:
    lines = [t("# Fundus-Aufnahmen — Übersicht", "# Fundus Images — Overview"),
             f"{t('Gesamt', 'Total')}: {len(exams)}  |  "
             f"{t('Stand', 'As of')}: {datetime.now().strftime('%Y-%m-%d')}\n"]

    for e in exams:
        ana = "✓" if e["ana_id"] else t("— nicht analysiert", "— not analysed")
        lat = e["laterality"] or "?"
        dev = f"  ({e['manufacturer']} {e['model']})" if e["manufacturer"] else ""
        lines.append(f"ID {e['id']:3d}  {e['date'] or '?':12}  [{lat}]  VLM: {ana}{dev}")

    return "\n".join(lines)


def _render_exam(exam: dict, response: str | None) -> str:
    lat   = exam["laterality"] or "?"
    lines = [f"# Fundus ID {exam['id']} — {exam['date'] or '?'}  [{lat}]\n"]
    dev   = f"{exam['manufacturer']} {exam['model']}" if exam["manufacturer"] else "?"
    lines.append(f"**Gerät:** {dev}  \n**Datei:** {Path(exam['file_path']).name}\n")

    if response:
        lines.append(f"**VLM-Analyse** ({exam['ana_model'] or '?'}):\n\n{response}")
    else:
        lines.append(t("_(Noch keine VLM-Analyse — mit --analyse ausführen)_",
                       "_(No VLM analysis yet — run with --analyse)_"))
    return "\n".join(lines)


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Fundusfotos auswerten und Verlauf anzeigen",
                      "Analyze fundus photos and display timeline")
    )
    ap.add_argument("--analyse", action="store_true",
                    help=t("VLM für alle noch nicht analysierten Bilder ausführen",
                           "Run VLM for all images without analysis"))
    ap.add_argument("--exam", type=int, default=None, metavar="ID",
                    help=t("Befunde für eine Aufnahme (ID aus Übersicht)",
                           "Show findings for one image (ID from overview)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", None) or "de"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn  = open_medicine_imaging_db()
    exams = _load_exams(conn)

    if not exams:
        print(t("Keine Fundus-Aufnahmen in der DB. Erst mit import_fundus.py importieren.",
                "No fundus images in DB. Import first with import_fundus.py."))
        conn.close()
        return

    if args.analyse:
        pending = [e for e in exams if not e["ana_id"]]
        print(t(f"{len(pending)} Bild(er) ohne VLM-Analyse.",
                f"{len(pending)} image(s) without VLM analysis."))
        for e in pending:
            _run_vlm(conn, e, lang)
        conn.commit()
        exams = _load_exams(conn)

    if args.exam:
        exam = next((e for e in exams if e["id"] == args.exam), None)
        if not exam:
            print(t(f"ID {args.exam} nicht gefunden.", f"ID {args.exam} not found."),
                  file=sys.stderr)
            conn.close()
            sys.exit(1)
        response = _load_response(conn, exam["id"])
        report   = _render_exam(exam, response)
    else:
        report = _render_overview(exams)

    print(report)

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    suffix  = f"_exam{args.exam}" if args.exam else "_uebersicht"
    out     = OUT_DIR / f"fundus{suffix}_{now_str}.md"
    out.write_text(report, encoding="utf-8")
    print(t(f"\n→ Bericht: {out}", f"\n→ Report: {out}"))

    conn.close()


if __name__ == "__main__":
    main()
