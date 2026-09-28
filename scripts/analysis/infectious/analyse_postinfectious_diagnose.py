#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Post-Infektions-Syndrom — Multi-Domain Biomarker Score

Bewertet 6 klinische Domänen gegen publizierte Referenzwerte und individuelle Baseline.
Unterstützt alle Post-Infektionssyndrome via --syndrome (ein oder mehrere parallel).
Default: generic. Verfügbar: post_covid, borreliose, q_fieber, ebv, bartonellose,
fsme, influenza, cmv, anaplasmose, babesiose, dengue, parvovirus, mycoplasma, generic.

Domänen:
  1. Autonome Dysregulation  (RHR, DFA α1, LF/HF, RMSSD mit Baseline-Delta)
  2. Post-Exertionelle Malaise (PEM-Kaskade, HRV-Einbrüche)
  3. Kardiovaskulär           (AF-Burden als Screening-Signal)
  4. Schlaf & Erholung        (Nightly HRV, Deep Sleep)
  5. Aktivitätstoleranz       (MET-Minuten mit Baseline-Delta)
  6. Respiratorisch           (SpO2)
  + Quarterly Trend (RMSSD, MET, HRV-Crash-Rate pro Quartal)
  + Gesamtschweregrad
  + Datenlücken & Empfehlungen

@tier        heuristic
@purpose.de  Bewertet 6 Wearable-Domänen (Autonomie, PEM, Kardio, Schlaf, Aktivität, Respiration) + bis zu 10 Symptomtagebuch-Domänen (Neurologie, Schmerz, GI, Psychiatrie, Sensorik u.a.) gegen publizierte Referenzwerte für 58 Post-Infektionssyndrome.
@purpose.en  Scores 6 wearable domains (autonomic, PEM, cardiac, sleep, activity, respiration) plus up to 10 symptom-diary domains (neurological, pain, GI, psychiatric, sensory, etc.) against published reference values for 58 post-infectious syndromes.
@method.de   Eigenentwickelter Multi-Domain-Score mit Baseline-Delta; einzelne Kriterien validated (HR-Anstieg >=30 bpm nach Raj et al. 2021; DFA alpha1 <0.75 nach Gronwald 2023). Gesamtscoring nicht klinisch validiert.
@method.en   Proprietary multi-domain score with baseline delta; individual criteria are validated (HR rise >=30 bpm per Raj et al. 2021; DFA alpha1 <0.75 per Gronwald 2023). Overall scoring is not clinically validated.
@refs        Soriano JB, Murthy S, Marshall JC, Relan P, Diaz JV (2022). A clinical case definition of post-COVID-19 condition by a Delphi consensus. The Lancet Infectious Diseases, 22(4):e102-e107. doi:10.1016/S1473-3099(21)00703-9
             Gronwald T, Rogers B, Hoos O (2020). Fractal Correlation Properties of Heart Rate Variability: A New Biomarker for Intensity Distribution in Endurance Exercise and Training Prescription?. Frontiers in Physiology, 11. doi:10.3389/fphys.2020.550572 (DFA-alpha1-Schwelle, Originalkonzept HRVT1)
             Raj SR, Fedorowski A, Sheldon RS (2022). Diagnosis and management of postural orthostatic tachycardia syndrome. CMAJ, 194(10):E378-E385. doi:10.1503/cmaj.211373 (HR-Anstieg-Kriterium)
             Davis HE, McCorkell L, Vogel JM, Topol EJ (2023). Long COVID: major findings, mechanisms and recommendations. Nature Reviews Microbiology, 21(3):133-146. doi:10.1038/s41579-022-00846-2
             Hickie I, Davenport T, Wakefield D et al. (2006). Post-infective and chronic fatigue syndromes precipitated by viral and non-viral pathogens: prospective cohort study. BMJ, 333(7568):575. doi:10.1136/bmj.38933.585764.AE
@relevance.de Ermöglicht die Unterscheidung zwischen zufälligen und tatsächlich infektionsgetriggerten Symptomclustern, zentral für die Abgrenzung postinfektiöser Syndrome untereinander. Unterstützt die klinische Entscheidungsfindung bei der Abgrenzung von Long-COVID, Post-Lyme-Syndrom, ME/CFS und anderen postinfektiösen Erkrankungen.
@relevance.en Enables differentiation between random and infection-triggered symptom clusters, central to distinguishing between post-infectious syndromes. Supports clinical decision-making in distinguishing Long-COVID, Post-Lyme syndrome, ME/CFS, and other post-infectious conditions.
@limits.de   Heuristische Methode: Kein validiertes Medizinprodukt; AFES ist ein Screening-Indikator. Validierte Einzelkomponenten: orthostatischer HR-Anstieg >=30 bpm (Sheldon 2015), DFA alpha1 <0.75 (Gronwald 2020), SpO2 <95% (WHO/ESC), RMSSD >=30 ms (Shaffer 2017), MET >=86/Tag (WHO GAPA 2018). Heuristisch: Multi-Domain-Kombination, spo2_lc_warn=97%, hrv_crash_pct=-10%, rmssd_lc_typical=20 ms, Deep-Sleep-Schwelle <15% (Orientierungswert ohne formale Primaerquelle), Schweregrad-Formel. Schwellenwerte nicht prospektiv evaluiert; Datenqualitaet abhaengig von Geraeteverfuegbarkeit.
@limits.en   Heuristic method: Not a validated medical device; AFES is a screening indicator. Validated individual components: orthostatic HR rise >=30 bpm (Sheldon 2015), DFA alpha1 <0.75 (Gronwald 2020), SpO2 <95% (WHO/ESC), RMSSD >=30 ms (Shaffer 2017), MET >=86/day (WHO GAPA 2018). Heuristic: multi-domain combination, spo2_lc_warn=97%, hrv_crash_pct=-10%, rmssd_lc_typical=20 ms, deep-sleep threshold <15% (orientation value without formal primary source), severity formula. Thresholds not prospectively evaluated; data quality depends on device availability.
@scoring     Domänen (Ampel-System):
               1. Autonome Dysregulation
                  RHR:    gut ≤60 bpm / Warnung ≤80 / Krit. >90 bpm
                  RMSSD:  gut ≥30 ms (Shaffer 2017) / Warnung ≥20 ms / Krit. <15 ms
                  DFA α1: gut ≥1.0 (Goldberger 2002) / Warnung ≥0.75 / Krit. <0.75 (Gronwald 2020)
                  orthostatischer HR-Anstieg:   gut <20 bpm / Grenz 20–29 bpm / Krit. ≥30 bpm (Sheldon 2015)
               2. Post-Exertionelle Malaise (PEM)
                  HRV-Crash-Rate: gut <10% / Warnung <20% / Krit. ≥20%
                  (Crash-Def.: Tages-RMSSD ≥10% unter Vortag; heuristisch)
               3. Kardiovaskulär (AFES)
                  gut: kein high/critical-Tag / Warnung: low/moderate / Krit.: ≥1 high/critical Tag
               4. Schlaf & Erholung
                  Tiefschlaf%: gut ≥20% / Warnung ≥15% / Krit. <10%
                  (AASM-Orientierung: N3 15–25% beim Erwachsenen)
               5. Aktivitätstoleranz
                  MET·min/Tag: gut ≥86 / Warnung ≥43 / Krit. <20
                  (WHO GAPA 2018: 600 MET·min/Woche = 86 MET·min/Tag; doi:10.9745/GHSP-D-18-00067)
               6. Respiration (SpO2)
                  gut ≥98% / Warnung ≥97% (heuristisch) / Krit. <95% (WHO/ESC)
             Gesamtschweregrad (bewerte_schweregrad):
               Punkte: MET-Einbruch +1–3 | RMSSD-Einbruch +1–2 | PEM-Crash% +1–2 | nHRV<15 +1
               leicht = 0–2 | moderat = 3–5 | schwer ≥6 (heuristische Formel, nicht prospektiv validiert)
             Validiert: orthostatischer HR-Anstieg ≥30 bpm, DFA α1 <0.75, SpO2 <95%, RMSSD ≥30 ms, MET ≥86/Tag
             Heuristisch: Kombinations-Score, spo2_lc_warn, hrv_crash_pct, Deep-Sleep-Schwelle
@reads       measurements, ppi_hrv_advanced, polar_nightly_hrv, af_evidence_scores, pem_evidence_scores, pem_correlation, sessions, session_metrics, symptoms, outbreak_events, location_stays, travel_history.json
@writes      analyses/postinfectious/*.{md,png}

Usage:
  python analyse_postinfectious_diagnose.py --infection-date YYYY-MM-DD
  python analyse_postinfectious_diagnose.py --infection-date YYYY-MM-DD --syndrome post_covid
  python analyse_postinfectious_diagnose.py --infection-date YYYY-MM-DD --syndrome borreliose
  python analyse_postinfectious_diagnose.py --infection-date YYYY-MM-DD --syndrome generic --plot
  python analyse_postinfectious_diagnose.py --infection-date YYYY-MM-DD --no-llm

@usage
    python analyse_postinfectious_diagnose.py
    python analyse_postinfectious_diagnose.py --help
    python analyse_postinfectious_diagnose.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, open_medicine_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.baseline import get_baseline, baseline_delta_pct
from modules.confidence import label_finding
from modules.endemic_matching import (
    geo_dist_km as _geo_dist_km, resolve_radius_km, since_floor_ok,
)

# ── ITS-Integration (optional) ────────────────────────────────────────────
import importlib.util as _ilu, pathlib as _pl
_its_path = _pl.Path(__file__).parent / "analyse_postinfectious_its.py"
if _its_path.exists():
    _spec = _ilu.spec_from_file_location("_its_mod", _its_path)
    _its_mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_its_mod)
    _run_its = _its_mod.run_its
    _ITS_AVAILABLE = True
else:
    _ITS_AVAILABLE = False

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "postinfectious"

KOGNITIONS_SYMPTOME = {
    "Konzentrationsstörungen", "Wortfindungsstörungen", "Sprachliche Erschöpfung",
    "Brain Fog", "Gedächtnisprobleme", "Mutismus", "Verlangsamtes Denken",
}

# ── Symptom-Kategorien-Map aus config/symptom_map.json ───────────────────────
_SYMPTOM_MAP_PATH = Path(__file__).parent.parent.parent / "config" / "symptom_map.json"
_SYMPTOM_CATEGORY_MAP: dict[str, str] = {}  # raw key/alias → category
_SYMPTOM_LABEL_MAP:    dict[str, str] = {}  # raw key/alias → German display label
if _SYMPTOM_MAP_PATH.exists():
    _sm_raw = json.loads(_SYMPTOM_MAP_PATH.read_text(encoding="utf-8"))
    for _k, _v in _sm_raw.items():
        if _k.startswith("_"):
            continue
        _cat = _v.get("category") if isinstance(_v, dict) else None
        _de  = _v.get("de", _k)   if isinstance(_v, dict) else _k
        if _cat:
            _SYMPTOM_CATEGORY_MAP[_k]  = _cat
            _SYMPTOM_CATEGORY_MAP[_de] = _cat
            _SYMPTOM_LABEL_MAP[_k]     = _de
            _SYMPTOM_LABEL_MAP[_de]    = _de
    del _sm_raw, _k, _v, _cat, _de

# Syndrom-Boost wenn Symptom-Kategorie stark belastet (n_tage-skaliert)
_CATEGORY_SLUG_BOOST: dict[str, dict[str, float]] = {
    "neurological":    {"ebv": 2.0, "hhv6": 2.0, "borreliose": 1.5, "post_covid": 1.5,
                        "enterovirus": 2.0, "cmv": 1.5, "bartonellose": 1.0},
    "musculoskeletal": {"borreliose": 2.5, "bartonellose": 2.0, "parvovirus": 2.0,
                        "reaktive_arthritis": 3.0, "post_covid": 1.0, "chikungunya": 2.0,
                        "q_fieber": 1.0},
    "gastrointestinal":{"giardiose": 3.0, "sibo": 2.5, "yersiniose": 2.5,
                        "reaktive_arthritis": 1.5, "q_fieber": 1.0, "ehec_hus": 2.0},
    "psychiatric":     {"post_covid": 1.5, "ebv": 1.5, "hhv6": 1.5,
                        "toxoplasmose": 1.0, "bartonellose": 1.5},
    "sensory":         {"borreliose": 1.5, "ebv": 1.5, "hhv6": 1.5,
                        "vzv": 2.0, "post_covid": 1.0},
    "autonomic":       {"post_covid": 1.5, "sfn": 2.0, "borreliose": 1.0,
                        "bartonellose": 1.0},
    "cardiovascular":  {"post_covid": 2.0, "enterovirus": 2.5, "borreliose": 1.0},
    "respiratory":     {"mycoplasma": 2.0, "post_covid": 1.0, "rsv": 1.5,
                        "influenza": 1.0, "ornithose": 1.5},
    "general":         {},
    "reproductive":    {},
}

_CATEGORY_DISPLAY_ORDER = [
    "neurological", "musculoskeletal", "gastrointestinal",
    "psychiatric", "sensory", "autonomic", "cardiovascular",
    "respiratory", "general", "reproductive",
]

_CATEGORY_DOMAIN_LABEL: dict[str, str] = {
    "neurological":    "Neurologie / Kognition",
    "musculoskeletal": "Schmerz / Muskuloskeletal",
    "gastrointestinal":"Gastrointestinal",
    "psychiatric":     "Psychiatrisch / Stimmung",
    "sensory":         "Sensorisch",
    "autonomic":       "Autonom (subjektiv)",
    "cardiovascular":  "Kardiovaskulär (subjektiv)",
    "respiratory":     "Respiratorisch (subjektiv)",
    "general":         "Allgemein (Fatigue, Malaise)",
    "reproductive":    "Reproduktiv",
}

_SYNDROMES_DIR = Path(__file__).parent.parent / "syndromes"


def _load_syndromes():
    """Load syndrome definitions from JSON files in the syndromes/ directory.

    Returns (SYNDROME_CONFIG, SYNDROME_CODES, SYNDROME_SERO) with the same
    structure as the former hardcoded dicts so all downstream code is unaffected.
    """
    afes_text = (_SYNDROMES_DIR / "_afes_context.txt").read_text(encoding="utf-8")
    syndrome_config: dict = {}
    syndrome_codes:  dict = {}
    syndrome_sero:   dict = {}
    for jf in sorted(_SYNDROMES_DIR.glob("*.json")):
        if jf.name.startswith("_"):
            continue
        rec = json.loads(jf.read_text(encoding="utf-8"))
        key = jf.stem  # filename without .json — matches original dict key
        system_prompt = rec.get("system_prompt", "").replace("{AFES_CONTEXT}", afes_text)
        syndrome_config[key] = {
            "slug":          rec["slug"],
            "name_de":       rec["name_de"],
            "lag_weeks":     rec["lag_weeks"],
            "refs":          rec.get("refs"),
            "system_prompt": system_prompt,
        }
        syndrome_codes[key] = {
            "icd10_gm":        rec.get("icd10_gm", []),
            "meldepflicht_de": rec.get("meldepflicht_de", False),
            "guidelines":      rec.get("guidelines", {}),
            "symptoms":        rec.get("symptoms", []),
        }
        syndrome_sero[key] = {
            "seroprevalence_de": rec.get("seroprevalence_de"),
            "sero_category":     rec.get("sero_category"),
            "endemic_regions":   rec.get("endemic_regions", []),
        }
    return syndrome_config, syndrome_codes, syndrome_sero


# _AFES_CONTEXT kept as a Python constant so any code referencing it directly still works
_AFES_CONTEXT = (_SYNDROMES_DIR / "_afes_context.txt").read_text(encoding="utf-8")

SYNDROME_CONFIG, SYNDROME_CODES, SYNDROME_SERO = _load_syndromes()
_SYNDROME_CFG = SYNDROME_CONFIG["post_covid"]

_lab_markers_file = _SYNDROMES_DIR / "_lab_markers.json"
LAB_MARKERS: dict[str, list[dict]] = (
    json.loads(_lab_markers_file.read_text(encoding="utf-8"))
    if _lab_markers_file.exists() else {}
)
# Remove metadata keys that start with "_"
LAB_MARKERS = {k: v for k, v in LAB_MARKERS.items() if not k.startswith("_")}

_LAB_BOOST: dict[str, dict] = {
    "IgM":     {"elevated": 2.5,  "negative": -0.5},
    "IgG":     {"elevated": 1.0,  "negative": -0.3},
    "IgA":     {"elevated": 1.0,  "negative": -0.3},
    "PCR":     {"elevated": 3.0,  "negative": -1.5},
    "Antigen": {"elevated": 2.0,  "negative": -1.0},
    "Kultur":  {"elevated": 2.0,  "negative": -0.5},
}

_STATUS_ELEVATED = {"hoch", "H", "high", "pathologisch", "auffällig", "erhöht",
                    "positiv", "reaktiv", "detektiert"}
_STATUS_NEGATIVE = {"normal", "L", "low", "niedrig", "negativ", "nicht reaktiv",
                    "nicht detektiert", "unauffällig"}


# Keyword → slug mapping for clinical events prior-infection boost
_EVENT_SLUG_KEYWORDS: dict[str, list[str]] = {
    "masern":            ["masern", "morbilli", "measles"],
    "post_mumps":        ["mumps", "parotitis"],
    "vzv":               ["windpocken", "varizella", "vzv", "zoster", "vericella"],
    "ebv":               ["epstein-barr", "ebv", "pfeiffersches", "mononukleose"],
    "influenza":         ["influenza", "grippe"],
    "borreliose":        ["borreliose", "borrelia", "zeckenstich"],
    "q_fieber":          ["q-fieber", "coxiella"],
    "post_covid":        ["covid", "sars-cov-2", "corona"],
    "cmv":               ["cmv", "cytomegalie"],
    "hhv6":              ["hhv-6", "hhv6", "roseola"],
    "mycoplasma":        ["mycoplasma", "mykoplasmen"],
    "ornithose":         ["psittaci", "ornithose", "wellensittich"],
    "chlamydia_pneumoniae": ["chlamydia pneumoniae", "chlamydophila"],
    "fsme":              ["fsme", "frühsommer"],
    "west_nile":         ["west-nil", "west nile", "wnv"],
    "hantavirus":        ["hantavirus", "hanta", "puumala"],
    "leptospirose":      ["leptospira", "leptospirose"],
    "tularaemie":        ["tularämie", "francisella"],
    "legionellose":      ["legionella", "legionellose"],
    "post_strep":        ["streptokokken", "streptococcus", "asl", "scharlach"],
    "reaktive_arthritis":["campylobacter", "salmonella"],
    "rickettsia":        ["rickettsia", "rickettsiose"],
}


_UNCERTAIN_MARKERS = (
    "wahrscheinlich", "exposition vorhanden", "v.a.", "verdacht",
    "möglich", "möglicherweise", "atypischer erreger", "nicht ausgeschlossen",
    "verdachtsdiagnose", "hypothese",
)

# Keywords that indicate a documented high-risk exposure (not a confirmed infection)
_EXPOSURE_MARKERS = (
    "exposition", "hochdosis-exposition", "tiermarkt", "stallstaub",
    "angeschafft", "stallarbeit", "reiten", "pferde", "hühner",
    "wellensittich", "barthelmarkt", "bauernhof", "coxiella", "psittaci",
)

# Tier → score boost (on the scale of IDF symptom scores, which reach ~90+)
_BOOST_CONFIRMED  = 20.0   # confirmed past infection (lab/clinical)
_BOOST_EXPOSURE   = 14.0   # documented high-risk exposure (event name contains exposure marker)
_BOOST_SUSPECTED  =  6.0   # uncertain / suspected (uncertainty markers present)


def _exposure_slug_boosts() -> dict[str, tuple[float, str, str]]:
    """Return {slug: (boost, event_label, tier)} for all relevant clinical events.

    Three tiers:
      'confirmed' — infection/reinfection, no uncertainty markers → +20
      'exposure'  — any type, contains exposure indicator keywords  → +14
      'suspected' — infection with uncertainty markers              → +6
    """
    result: dict[str, tuple[float, str, str]] = {}
    for event in _cfg.events:
        etype      = event.get("type", "")
        name       = event.get("name", "")
        name_lower = name.lower()
        notes      = (event.get("notes") or "").lower()
        text       = name_lower + " " + notes

        has_uncertain = any(m in text for m in _UNCERTAIN_MARKERS)
        has_exposure  = any(m in text for m in _EXPOSURE_MARKERS)

        if etype in ("infection", "reinfection"):
            tier  = "suspected" if has_uncertain else "confirmed"
            boost = _BOOST_CONFIRMED if tier == "confirmed" else _BOOST_SUSPECTED
        elif has_exposure:
            tier  = "exposure"
            boost = _BOOST_EXPOSURE
        else:
            continue  # irrelevant event type

        # Count exposure markers to prefer more specific events (e.g. Barthelmarkt > Pyelonephritis)
        specificity = sum(1 for m in _EXPOSURE_MARKERS if m in text)
        for slug, keywords in _EVENT_SLUG_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                prev = result.get(slug)
                if prev is None:
                    result[slug] = (boost, name, tier, specificity)
                else:
                    prev_boost, _, prev_tier, prev_spec = prev
                    # Higher boost wins; on tie prefer higher specificity (more exposure markers)
                    if boost > prev_boost or (boost == prev_boost and specificity > prev_spec):
                        result[slug] = (boost, name, tier, specificity)

    # Strip the internal specificity field before returning
    return {slug: (b, lbl, t) for slug, (b, lbl, t, _spec) in result.items()}


_EXPOSURE_BOOSTS: dict[str, tuple[float, str, str]] = _exposure_slug_boosts()
# backward-compat alias used nowhere else but kept for safety
_PRIOR_INFECTIONS: dict[str, str] = {
    slug: label for slug, (_, label, tier) in _EXPOSURE_BOOSTS.items()
    if tier == "confirmed"
}


# ── Expositionsprofil-Boost ──────────────────────────────────────────────────
# Lifestyle/Hintergrundrisiko aus exposure_profile.json → schwächere Boosts
# als bestätigte Infektionen (+20) oder dokumentierte Expositionen (+14).
# Diese Boosts spiegeln erhöhtes Basisrisiko wider, keine direkte Evidenz.
_LIFESTYLE_BOOST: dict[str, dict[str, float]] = {
    "tick_exposure":   {"borreliose": 7.0, "fsme": 5.0, "anaplasmose": 7.0,
                        "bartonellose": 4.0},
    "outdoor":         {"borreliose": 4.0, "fsme": 3.0, "anaplasmose": 4.0,
                        "west_nile": 2.0},
    "rural_living":    {"borreliose": 3.0, "q_fieber": 3.0, "anaplasmose": 3.0},
    "animal_contact":  {"bartonellose": 3.0, "toxoplasmose": 4.0, "q_fieber": 2.0},
    "cat_contact":     {"bartonellose": 5.0, "toxoplasmose": 5.0},
    "dog_contact":     {"bartonellose": 3.0},
    "livestock":       {"q_fieber": 8.0, "brucellose": 6.0},
    "bird_contact":    {"ornithose": 8.0},
    "water_exposure":  {"leptospirose": 7.0},
    "soil_contact":    {"q_fieber": 5.0, "toxoplasmose": 3.0},
    "raw_food":        {"toxoplasmose": 4.0},
}

_LIFESTYLE_TYPE_LABEL: dict[str, str] = {
    "tick_exposure":  "🦟 Zecken",
    "outdoor":        "🌲 Outdoor",
    "rural_living":   "🏡 Ländl. Umfeld",
    "animal_contact": "🐾 Tiere",
    "cat_contact":    "🐱 Katzen",
    "dog_contact":    "🐕 Hunde",
    "livestock":      "🐄 Nutztiere",
    "bird_contact":   "🐦 Vögel",
    "water_exposure": "💧 Süßwasser",
    "soil_contact":   "🌱 Erde/Acker",
    "raw_food":       "🥩 Rohfleisch",
    "occupation":     "💼 Beruf",
}


def _lifestyle_boost_for_slug(slug: str) -> float:
    """Return total lifestyle boost for a slug from exposure_profile.json."""
    total = 0.0
    for factor in _cfg.exposure_factors:
        ftype = factor.get("type", "")
        boosts = _LIFESTYLE_BOOST.get(ftype, {})
        total += boosts.get(slug, 0.0)
    return total


def _exposure_profile_lines() -> list[str]:
    """Render the Expositionsprofil section for the differential report."""
    factors = _cfg.exposure_factors
    if not factors:
        return []

    lines: list[str] = ["### Expositionsprofil\n"]
    boosted_slugs: dict[str, float] = {}

    for factor in factors:
        ftype  = factor.get("type", "other")
        detail = factor.get("detail", "")
        since  = factor.get("since", "")
        freq   = factor.get("frequency", "")
        label  = _LIFESTYLE_TYPE_LABEL.get(ftype, f"• {ftype}")

        parts = []
        if freq:
            parts.append(freq)
        if since:
            parts.append(f"seit {since}")
        meta = f"  ({', '.join(parts)})" if parts else ""

        lines.append(f"  {label:<22} {detail}{meta}")

        for slug, boost in _LIFESTYLE_BOOST.get(ftype, {}).items():
            boosted_slugs[slug] = boosted_slugs.get(slug, 0.0) + boost

    if boosted_slugs:
        top = sorted(boosted_slugs.items(), key=lambda x: -x[1])[:6]
        slug_names = [SYNDROME_CONFIG.get(s, {}).get("name_de", s) for s, _ in top]
        lines.append(f"\n  Syndrom-Relevanz: {', '.join(slug_names)} ↑\n")
    else:
        lines.append("")

    return lines


# ── Impf-Keyword-Map ─────────────────────────────────────────────────────────
# slug → keywords that appear in vaccination event names
_VACCINE_SLUG_KEYWORDS: dict[str, list[str]] = {
    "fsme":        ["fsme", "frühsommer", "tbe", "encepur", "fsme-immun"],
    "post_covid":  ["covid", "corona", "biontech", "moderna", "mrna"],
    "masern":      ["masern", "mmr", "priorix", "m-m-rvaxpro"],
    "post_mumps":  ["mumps", "mmr", "priorix"],
    "vzv":         ["varizella", "varicella", "vzv", "varilix", "varivax"],
    "hepatitis_a": ["hepatitis a", "twinrix", "havrix", "epaxal"],
    "hepatitis_b": ["hepatitis b", "twinrix", "engerix", "hbvaxpro"],
    "influenza":   ["influenza", "grippe", "influvac", "fluarix"],
    "typhus":      ["typhoid", "typhim", "typhoral", "vivotif"],
    "borreliose":  ["lyme"],  # kein zugelassener Impfstoff DE
}

# How long (years) a vaccine's protection lasts; None = lifetime / indefinite
_VACCINE_DURATION_YEARS: dict[str, float | None] = {
    "fsme":       5.0,
    "post_covid": 1.0,
    "masern":     None,
    "post_mumps": None,
    "vzv":        None,
    "hepatitis_a": None,
    "hepatitis_b": None,
    "influenza":  1.0,
    "typhus":     3.0,
}


def _vaccination_status_for_slug(slug: str, as_of_date: str) -> tuple[str, str] | None:
    """Return (status_label, detail) if a vaccination entry exists for this slug.

    status_label: '✅ Geimpft', '⚠ Impfschutz abgelaufen', '📋 Grundimmunisierung unvollständig'
    Returns None if no vaccination found.
    Detail includes total dose count when > 1.
    """
    keywords = _VACCINE_SLUG_KEYWORDS.get(slug, [])
    if not keywords:
        return None

    vacc_events = []
    for ev in _cfg.events:
        if ev.get("type") != "vaccination":
            continue
        name_lower = ev.get("name", "").lower()
        if any(kw in name_lower for kw in keywords):
            vacc_events.append(ev)

    if not vacc_events:
        return None

    latest = max(vacc_events, key=lambda e: e.get("date", ""))
    last_date = latest.get("date", "")
    last_name = latest.get("name", "")[:50]
    dose_count = len(vacc_events)
    dose_suffix = f" ({dose_count} Dosen gesamt)" if dose_count > 1 else ""

    duration = _VACCINE_DURATION_YEARS.get(slug)
    if duration is None:
        return ("✅ Geimpft", f"{last_name} ({last_date}), Schutz lebenslang{dose_suffix}")

    from datetime import date
    try:
        last_dt = date.fromisoformat(last_date[:10])
        as_of_dt = date.fromisoformat(as_of_date[:10])
        expiry = date(last_dt.year + int(duration),
                      last_dt.month, last_dt.day)
        if as_of_dt <= expiry:
            return ("✅ Geimpft", f"{last_name} ({last_date}), Schutz bis ~{expiry.year}-{expiry.month:02d}{dose_suffix}")
        else:
            return ("⚠ Impfschutz abgelaufen", f"Letzter: {last_name} ({last_date}), abgelaufen ~{expiry.year}-{expiry.month:02d}{dose_suffix}")
    except (ValueError, OverflowError):
        return ("✅ Geimpft", f"{last_name} ({last_date}){dose_suffix}")


def _all_infections_for_slug(slug: str) -> list[dict]:
    """Return all infection/reinfection events from config matching this slug's keywords."""
    keywords = _EVENT_SLUG_KEYWORDS.get(slug, [])
    if not keywords:
        return []
    results = []
    seen_dates: set[str] = set()
    for ev in _cfg.events:
        if ev.get("type") not in ("infection", "reinfection"):
            continue
        name_lower = ev.get("name", "").lower()
        notes_lower = (ev.get("notes") or "").lower()
        if any(kw in name_lower or kw in notes_lower for kw in keywords):
            date_key = ev.get("date", "")
            if date_key not in seen_dates:
                seen_dates.add(date_key)
                results.append(ev)
    results.sort(key=lambda e: e.get("date", ""))
    return results


def _lab_results_for_slug(conn, slug: str) -> list[tuple[str, str, str]]:
    """Return list of (date, parameter, result_label) from lab_manual for this slug.

    Checks all markers defined in LAB_MARKERS for the slug.
    Returns entries regardless of when they were taken — for context display.
    """
    results = []
    med_conn = open_medicine_db()
    for marker in LAB_MARKERS.get(slug, []):
        rows = med_conn.execute(
            "SELECT date, parameter, wert, wert_num, ref_max, status "
            "FROM lab_manual WHERE parameter LIKE ? ORDER BY date DESC LIMIT 1",
            (f"%{marker['parameter']}%",),
        ).fetchall()
        for date_v, param, wert, wert_num, ref_max, status_v in rows:
            result_status = _lab_result_status(wert, wert_num, ref_max, status_v)
            icon = {"elevated": "↑ positiv/erhöht", "negative": "✗ negativ",
                    "unknown": "? kein Referenz"}.get(result_status, "?")
            results.append((date_v or "?", marker["label"], icon))
    med_conn.close()
    return results


def _lab_result_status(wert: str | None, wert_num: float | None,
                       ref_max: float | None, status: str | None) -> str:
    """Return 'elevated', 'negative', or 'unknown' for a single lab_manual row."""
    s = (status or "").strip().lower()
    if s in {x.lower() for x in _STATUS_ELEVATED}:
        return "elevated"
    if s in {x.lower() for x in _STATUS_NEGATIVE}:
        return "negative"
    # numeric comparison
    if wert_num is not None and ref_max is not None:
        return "elevated" if wert_num > ref_max else "negative"
    # text value like "<0.150" or ">100"
    if wert:
        stripped = wert.strip()
        if stripped.startswith("<"):
            return "negative"
        if stripped.startswith(">"):
            return "elevated"
    return "unknown"

# ── Referenzwerte ─────────────────────────────────────────────────────────────
REF = {
    "rhr_normal_max":   60,    # AHA: Ruhepuls 60–100 bpm; ≤60 = gut trainierten Zustand
    "rmssd_min_normal": 30,    # Shaffer & Ginsberg 2017: RMSSD ≥30 ms = akzeptabel; doi:10.3389/fpubh.2017.00258
    "rmssd_lc_typical": 20,    # Klinik-Beobachtung: reduzierter RMSSD bei PQFS/Long-COVID (explorativ)
    "dfa_kritisch":   0.75,    # Gronwald et al. 2020: α1 <0.75 = aerobe Schwelle erreicht; doi:10.3389/fphys.2020.550572
    "dfa_grenz":       1.0,    # Goldberger 2002: α1 ~1.0 = gesunder Ruhezustand (1/f-Rauschen); doi:10.1073/pnas.012579499
    "spo2_min":       95.0,    # WHO/ESC: SpO2 <95% = Hypoxämie-Grenze; O2-Sättigung beim Erwachsenen
    "spo2_lc_warn":   97.0,    # Konservative Warnschwelle bei postinfektiöser Erschöpfung (heuristisch)
    "pots_delta":       30,    # Sheldon et al. 2015 (HRS): HR-Anstieg ≥30 bpm beim Aufstehen = POTS-Kriterium; doi:10.1016/j.hrthm.2015.03.029
    "hrv_crash_pct":  -10.0,   # Heuristischer Schwellenwert: HRV-Absturz >10% unter Baseline = PEM-Signal
    "met_min_normal":   86,    # WHO GAPA 2018: 600 MET·min/Woche Minimum = 86 MET·min/Tag (150 min moderat × 4 MET / 7); doi:10.9745/GHSP-D-18-00067
    "deep_sleep_min":   15,    # Orientierungswert: N3 <15% gilt klinisch als reduziert (AASM-Orientierung: 15–25% N3 beim Erwachsenen; Walker 2017 ist keine Primärquelle — heuristisch)
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _lc_start(infection_date: str) -> str:
    d = datetime.strptime(infection_date, "%Y-%m-%d") + timedelta(weeks=_SYNDROME_CFG["lag_weeks"])
    return d.strftime("%Y-%m-%d")


def _avg(lst):
    return round(sum(lst) / len(lst), 2) if lst else None


def _pct_below(lst, threshold):
    if not lst:
        return None
    return round(sum(1 for v in lst if v < threshold) / len(lst) * 100, 1)


def _f(val, fmt=".0f", fallback="?"):
    if val is None:
        return fallback
    return format(val, fmt)


def _delta_str(post, base):
    """Formatiert Delta zwischen post- und Baseline-Wert."""
    if post is None or base is None or base == 0:
        return ""
    pct = (post - base) / base * 100
    return f"  (Baseline: {base:.0f} → {post:.0f}, {pct:+.0f}%)"


def _score_symbol(wert, gut, warn, schlecht, invert=False):
    if wert is None:
        return "?"
    if not invert:
        return "✅" if wert <= gut else "⚠" if wert <= warn else "❌"
    else:
        return "✅" if wert >= gut else "⚠" if wert >= warn else "❌"


# ── Daten laden ───────────────────────────────────────────────────────────────

def load_all_data(conn, lc_start: str, d_to: str) -> dict:
    data = {}

    data["rhr"] = {r[0]: r[1] for r in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric IN ('resting_heart_rate','resting_hr','hr_resting')
          AND date >= ? AND date <= ? AND value > 30
        GROUP BY date ORDER BY date
    """, (lc_start, d_to)).fetchall()}

    rows = conn.execute("""
        SELECT DATE(fenster_start), AVG(dfa_alpha1), MIN(dfa_alpha1),
               AVG(lf_hf_ratio), AVG(rmssd_ms)
        FROM ppi_hrv_advanced
        WHERE DATE(fenster_start) >= ? AND DATE(fenster_start) <= ?
          AND artifact_pct < 0.1
        GROUP BY DATE(fenster_start) ORDER BY DATE(fenster_start)
    """, (lc_start, d_to)).fetchall()
    data["dfa"] = {r[0]: {"avg": r[1], "min": r[2], "lfhf": r[3], "rmssd": r[4]}
                   for r in rows}

    rows = conn.execute("""
        SELECT date, rmssd_ms, baseline_rmssd_ms, recovery_indicator
        FROM polar_nightly_hrv
        WHERE date >= ? AND date <= ? AND rmssd_ms > 0
        ORDER BY date
    """, (lc_start, d_to)).fetchall()
    data["nhrv"] = {r[0]: {"rmssd": r[1], "baseline": r[2], "recovery": r[3]}
                    for r in rows}

    # Fallback ohne Polar: HRV (rMSSD) aus measurements (Garmin/Apple), Tagesmittel
    if not data["nhrv"]:
        rows = conn.execute("""
            SELECT date, AVG(value) FROM measurements
            WHERE metric IN ('hrv_rmssd','rmssd','hrv')
              AND date >= ? AND date <= ? AND value > 0
            GROUP BY date ORDER BY date
        """, (lc_start, d_to)).fetchall()
        data["nhrv"] = {r[0]: {"rmssd": r[1], "baseline": None, "recovery": None}
                        for r in rows}

    rows = conn.execute("""
        SELECT date,
               AVG(CASE WHEN value <= 1.5 THEN value * 100.0 ELSE value END),
               MIN(CASE WHEN value <= 1.5 THEN value * 100.0 ELSE value END)
        FROM measurements
        WHERE metric IN ('oxygen_saturation','spo2')
          AND date >= ? AND date <= ? AND value > 0
        GROUP BY date ORDER BY date
    """, (lc_start, d_to)).fetchall()
    data["spo2"] = {r[0]: {"avg": round(r[1], 1) if r[1] else None,
                            "min": round(r[2], 1) if r[2] else None} for r in rows}

    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    data["af"] = {}
    if "af_evidence_scores" in tables:
        rows = conn.execute("""
            SELECT date, score, level FROM af_evidence_scores
            WHERE date >= ? AND date <= ? ORDER BY date
        """, (lc_start, d_to)).fetchall()
        data["af"] = {r[0]: {"score": r[1], "level": r[2]} for r in rows}

    rows = conn.execute("""
        SELECT date, metric, AVG(value) FROM measurements
        WHERE metric IN ('met_minutes','level_moderate_s','level_vigorous_s')
          AND date >= ? AND date <= ?
        GROUP BY date, metric ORDER BY date
    """, (lc_start, d_to)).fetchall()
    by_date = defaultdict(dict)
    for d, m, v in rows:
        by_date[d][m] = v
    data["activity"] = dict(by_date)

    # Fallback ohne Polar/Apple-MET: MET-Minuten aus Garmin-Intensitätsminuten
    # (moderat ×4 MET, intensiv ×8 MET — Standard-MET-Minuten-Näherung)
    if not any("met_minutes" in v for v in data["activity"].values()):
        rows = conn.execute("""
            SELECT date, metric, AVG(value) FROM measurements
            WHERE metric IN ('intensity_moderate','intensity_vigorous')
              AND date >= ? AND date <= ? AND value >= 0
            GROUP BY date, metric
        """, (lc_start, d_to)).fetchall()
        im = defaultdict(dict)
        for d, m, v in rows:
            im[d][m] = v
        for d, mv in im.items():
            met = (mv.get("intensity_moderate", 0) or 0) * 4 + (mv.get("intensity_vigorous", 0) or 0) * 8
            data["activity"].setdefault(d, {})["met_minutes"] = met

    rows = conn.execute("""
        SELECT date, hrv_delta_pct, pem_signal, pem_staerke, training_load,
               had_sport, sport_prior_3d, source
        FROM pem_correlation
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (lc_start, d_to)).fetchall()
    data["pem"] = {r[0]: {"delta": r[1], "signal": r[2], "staerke": r[3],
                           "tl": r[4], "had_sport": r[5], "sport_prior_3d": r[6],
                           "source": r[7]}
                   for r in rows}

    # Sport-bereinigter PEM Evidence Score
    _tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    if "pem_evidence_scores" in _tables:
        has_conf = any(r[1] == "confidence" for r in
                       conn.execute("PRAGMA table_info(pem_evidence_scores)"))
        conf_filter = "AND confidence = 'confirmed'" if has_conf else ""
        ev_rows = conn.execute(f"""
            SELECT date, score, level, recovery_pattern, recovery_source
            FROM pem_evidence_scores
            WHERE date >= ? AND date <= ? {conf_filter}
            ORDER BY date
        """, (lc_start, d_to)).fetchall()
        data["pem_evidence"] = {r[0]: {"score": r[1], "level": r[2],
                                        "pattern": r[3], "source": r[4]}
                                 for r in ev_rows}
    else:
        data["pem_evidence"] = {}

    rows = conn.execute("""
        SELECT s.date, sm.metric, sm.value
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep'
          AND sm.metric IN ('deep_pct','efficiency_pct','duration_h')
          AND s.date >= ? AND s.date <= ?
        ORDER BY s.date
    """, (lc_start, d_to)).fetchall()
    sleep = defaultdict(dict)
    for d, m, v in rows:
        sleep[d][m] = v
    data["sleep"] = dict(sleep)

    # Fallback ohne Polar: Tiefschlaf% + Dauer aus Garmin-Schlaf-Sessions
    if not data["sleep"]:
        rows = conn.execute("""
            SELECT s.date, sm.metric, sm.value
            FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type = 'sleep' AND sm.metric IN ('deep_s','duration_s','awake_s')
              AND s.date >= ? AND s.date <= ?
        """, (lc_start, d_to)).fetchall()
        gs = defaultdict(dict)
        for d, m, v in rows:
            gs[d][m] = v
        for d, mv in gs.items():
            dur = mv.get("duration_s")
            if dur and dur > 0:
                awake = mv.get("awake_s", 0) or 0
                data["sleep"][d] = {
                    "deep_pct": 100.0 * (mv.get("deep_s", 0) or 0) / dur,
                    "duration_h": dur / 3600.0,
                    "efficiency_pct": 100.0 * dur / (dur + awake) if (dur + awake) else None,
                }

    rows = conn.execute("""
        SELECT s.date, sm.metric, sm.value
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'orthostatic'
          AND sm.metric IN ('hr_supine','hr_lowest','hr_stand','hr_standup_min')
          AND s.date >= ? AND s.date <= ?
        ORDER BY s.date
    """, (lc_start, d_to)).fetchall()
    ortho = defaultdict(dict)
    for d, m, v in rows:
        ortho[d][m] = v
    data["ortho"] = dict(ortho)

    return data


def load_symptoms_kognitiv(conn, lc_start: str, d_to: str) -> dict:
    """Kognitive Symptome aus Symptomtagebuch im Analysefenster."""
    rows = conn.execute("""
        SELECT date, symptom FROM symptoms
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (lc_start, d_to)).fetchall()
    by_date = defaultdict(list)
    for d, s in rows:
        if s in KOGNITIONS_SYMPTOME:
            by_date[d].append(s)
    alle = sorted({s for syms in by_date.values() for s in syms})
    return {
        "by_date": dict(by_date),
        "n_tage": len(by_date),
        "symptome": alle,
        "caveat": "Symptomtagebuch erst kurzfristig erhoben, noch nicht systematisch.",
    }


def load_symptoms_syndrom(conn, lc_start: str, d_to: str) -> dict:
    """Gleicht alle dokumentierten Symptome gegen das Syndrom-Symptomprofil ab."""
    codes = SYNDROME_CODES.get(_SYNDROME_CFG["slug"], {})
    syndrom_symptome = set(codes.get("symptoms", []))
    if not syndrom_symptome:
        return {"treffer": [], "alle_dokumentiert": [], "n_treffer": 0, "n_gesamt": 0}

    rows = conn.execute("""
        SELECT DISTINCT symptom, COUNT(DISTINCT date) as n_tage
        FROM symptoms
        WHERE date >= ? AND date <= ?
        GROUP BY symptom ORDER BY n_tage DESC
    """, (lc_start, d_to)).fetchall()

    alle = [(s, n) for s, n in rows]
    treffer = [(s, n) for s, n in rows if s in syndrom_symptome]
    return {
        "treffer":          treffer,
        "alle_dokumentiert": alle,
        "n_treffer":        len(treffer),
        "n_gesamt":         len(alle),
        "syndrom_symptome": sorted(syndrom_symptome),
    }


def _travel_region_set() -> set[str]:
    """Alle besuchten Regionen/Länder/Klimazonen aus health_config als Set."""
    tags: set[str] = set()
    for trip in _cfg.travel_history:
        for field in ("name", "country", "subregion", "climate_zone"):
            val = trip.get(field)
            if val:
                tags.add(val)
    return tags


# _geo_dist_km, resolve_radius_km, since_floor_ok kommen aus
# modules.endemic_matching (s. Imports oben) statt hier dupliziert zu sein.

def _structural_exposure_hits(conn) -> dict[str, str]:
    """Koordinatenbasierte Endemie-Treffer je Syndrom-Slug (Reise + Wohnsitz-Historie).

    Ergaenzt _travel_region_set()'s Freitext-Abgleich (gegen endemic_regions in
    den Syndrom-JSONs) um die strukturierten Endemie-Referenzdaten aus
    outbreak_events (source IN endemic_ref, lgl_fsme) — inkl. radius_km-Praezision
    (z.B. landkreisgenaue Tigermuecken-/FSME-Daten) und since_date-Zeitfilter
    (aktiv expandierende Risiken werden nicht rueckwirkend auf Aufenthalte
    vor ihrer dokumentierten Entstehung angewandt). Ohne diese Ergaenzung
    hatte die Differenzialdiagnose gar keinen Zugriff auf diese Daten, nur
    die separaten Expositions-Berichte (analyse_outbreak_exposure.py/
    analyse_pathogen_exposure.py) — genau die Luecke, die dieses Feature von
    Anfang an schliessen sollte (Diagnose ohne Reiseanamnese moeglich).

    Deckt sowohl travel_history.json (Reisen) als auch location_stays
    (GPS-Aufenthalte UND Wohnsitz-Historie, is_home 0 und 1) ab — ein
    strukturelles Risiko am aktuellen oder frueheren Wohnort soll genauso
    zaehlen wie eine Reise.

    Returns:
        dict slug -> Name der am besten treffenden Region (fuer die Anzeige)
    """
    stays: list[dict] = []
    for trip in _cfg.travel_history:
        lat = trip.get("lat") or trip.get("_lat")
        lon = trip.get("lon") or trip.get("_lon")
        if lat is not None and lon is not None:
            stays.append({
                "lat": float(lat), "lon": float(lon),
                "date_to": trip.get("date_to") or trip.get("date_from") or "",
            })

    try:
        rows = conn.execute("""
            SELECT lat, lon, COALESCE(end_ts, start_ts) FROM location_stays
            WHERE lat IS NOT NULL AND lon IS NOT NULL
        """).fetchall()
        today = datetime.now().strftime("%Y-%m-%d")
        for lat, lon, end_ts in rows:
            stays.append({
                "lat": float(lat), "lon": float(lon),
                "date_to": (end_ts or "")[:10] or today,
            })
    except Exception:
        pass

    if not stays:
        return {}

    try:
        refs = conn.execute("""
            SELECT syndrome_slug, region, lat, lon, radius_km, since_date, source
            FROM outbreak_events
            WHERE source IN ('endemic_ref', 'lgl_fsme') AND syndrome_slug IS NOT NULL
                  AND lat IS NOT NULL AND lon IS NOT NULL
        """).fetchall()
    except Exception:
        return {}

    # Praezisere Eintraege (kleiner radius_km, z.B. ein landkreisgenauer
    # FSME-/Tigermuecken-Kreis) sollen einen groben Laender-/Bundesland-Punkt
    # (radius_km NULL -> 200km-Default) als Treffer immer verdraengen koennen,
    # auch wenn beide fuer denselben Slug passen -- sonst gewinnt sonst
    # willkuerlich, wer in der DB-Abfrage zuerst auftaucht (gefunden: eine
    # grobe "Gesamtschweiz"-FSME-Referenz ueberdeckte den viel praeziseren
    # Landkreis-Treffer, nur weil sie eine kleinere DB-ID hatte).
    refs = sorted(refs, key=lambda r: r[4] or 9999.0)

    hits: dict[str, str] = {}
    for slug, region, o_lat, o_lon, radius_km, since_date, source in refs:
        if slug in hits:
            continue
        radius = resolve_radius_km({"radius_km": radius_km, "source": source})
        for stay in stays:
            try:
                stay_end_dt = datetime.strptime(stay["date_to"][:10], "%Y-%m-%d")
            except (ValueError, TypeError, KeyError):
                stay_end_dt = None
            if not since_floor_ok(since_date, stay_end_dt):
                continue
            if _geo_dist_km(stay["lat"], stay["lon"], float(o_lat), float(o_lon)) <= radius:
                hits[slug] = region
                break
    return hits


def vermute_syndrome(conn, lc_start: str, d_to: str,
                     respiration: dict = None, kardio: dict = None,
                     autonome: dict = None, aktivitaet: dict = None,
                     symptom_kategorien: dict = None,
                     exposure_priors: dict = None) -> list:
    """Differenzialdiagnose: rankt alle Syndrome nach gewichtetem Symptom-Match.

    Scoring:
    - IDF-gewichteter Symptom-Score: seltene Symptome zählen mehr
    - Biomarker-Bonus: syndromspezifische Biomarkermuster
    - Seropr.-Prior: hohe Seropr. → "assume prior, is it active?" (gedämpft)
    - Reise-Boost: Überschneidung mit endemic_regions aus travel_history
    """
    rows = conn.execute("""
        SELECT symptom, COUNT(DISTINCT date) as n
        FROM symptoms WHERE date >= ? AND date <= ?
        GROUP BY symptom
    """, (lc_start, d_to)).fetchall()
    dok_symptome = {s: n for s, n in rows}

    if not dok_symptome:
        return []

    visited_regions = _travel_region_set()
    structural_hits = _structural_exposure_hits(conn)

    symptom_in_n = defaultdict(int)
    for slug, codes in SYNDROME_CODES.items():
        if slug == "generic":
            continue
        for sym in codes.get("symptoms", []):
            symptom_in_n[sym] += 1
    n_syndromes = sum(1 for s in SYNDROME_CODES if s != "generic")

    results = []
    for slug, codes in SYNDROME_CODES.items():
        if slug == "generic":
            continue
        profil = set(codes.get("symptoms", []))
        if not profil:
            continue

        sero = SYNDROME_SERO.get(slug, {})
        sero_pct   = sero.get("seroprevalence_de")
        sero_cat   = sero.get("sero_category", "unbekannt")
        endemisch  = set(sero.get("endemic_regions", []))

        # IDF-gewichteter Symptom-Score
        score = 0.0
        matched = []
        for sym in profil:
            if sym in dok_symptome:
                idf = n_syndromes / max(symptom_in_n[sym], 1)
                tage_boost = min(dok_symptome[sym] / 10, 2.0)
                score += idf * (1 + tage_boost)
                matched.append((sym, dok_symptome[sym]))

        coverage_pct = round(len(matched) / len(profil) * 100, 1) if profil else 0.0

        # ── Seropr.-Prior ─────────────────────────────────────────────────────
        # Hohe Seropr. → Vorinfektion wahrscheinlich, aber "aktiv?" unklar.
        # Wir dämpfen leicht (nicht boosten), weil hohe Seropr. allein keine
        # Kausalität begründet; der LLM-Framing-Text übernimmt die Erklärung.
        sero_note = None
        if sero_pct is not None:
            if sero_pct >= 0.50:
                sero_note = f"Vorinfektion wahrscheinlich ({sero_pct:.0%}) — Reaktivierung?"
            elif sero_pct >= 0.10:
                sero_note = f"Seropr. {sero_pct:.0%} — bei passender Anamnese relevant"
            else:
                sero_note = f"Selten DE ({sero_pct:.1%})"

        # ── Expositions-/Prior-Boost ──────────────────────────────────────────
        # Drei Stufen: bestätigte Infektion (+20), dokumentierte Exposition (+14),
        # Verdacht/wahrscheinlich (+6). Skaliert auf IDF-Score-Niveau (~90+).
        prior_note = None
        prior_data = _EXPOSURE_BOOSTS.get(slug)
        if prior_data:
            exp_boost, exp_label, exp_tier = prior_data
            score += exp_boost
            _LEVEL_MAP = {"confirmed": "confirmed", "exposure": "suspected", "suspected": "lead"}
            level = _LEVEL_MAP.get(exp_tier, "lead")
            prior_note_de, _ = label_finding(exp_label, exp_label, level)
            prior_note = prior_note_de
        elif exposure_priors and slug in exposure_priors:
            db_b = min(exposure_priors[slug], 3.0)
            score += db_b
            prior_note = f"Expositions-Prior (DB): +{db_b:.1f}"

        # ── Reise-/Struktur-Boost ─────────────────────────────────────────────
        # Zwei unabhaengige Evidenzquellen: Freitext-Ueberschneidung mit den
        # groben endemic_regions-Tags der Syndrom-Datei, UND koordinatenbasierte
        # Treffer gegen die strukturierten Endemie-Referenzdaten (radius_km/
        # since_date-bewusst, deckt auch Wohnsitz-Historie ab) aus
        # _structural_exposure_hits(). Ein struktureller Treffer zaehlt wie ein
        # weiterer Text-Treffer, wird aber nicht doppelt gezaehlt, wenn dieselbe
        # Region schon per Text erkannt wurde.
        reise_treffer = endemisch & visited_regions
        struct_region = structural_hits.get(slug)
        labels = sorted(reise_treffer)[:3]
        if struct_region and struct_region not in labels:
            labels = (labels + [struct_region])[:3]
        n_treffer   = len(reise_treffer) + (1 if struct_region and struct_region not in reise_treffer else 0)
        reise_boost = 0.0
        reise_note  = None
        if n_treffer:
            reise_boost = min(n_treffer * 0.8, 3.0)
            score += reise_boost
            reise_note = f"Reise: {', '.join(labels)}"

        # ── Lifestyle-/Expositionsprofil-Boost ───────────────────────────────
        score += _lifestyle_boost_for_slug(slug)

        # ── Symptom-Kategorie-Boost ───────────────────────────────────────────
        # Skaliert mit n_tage: ≥30 → 1.0×, 10–29 → 0.5×, 5–9 → 0.25×
        if symptom_kategorien:
            for cat, cat_boosts in _CATEGORY_SLUG_BOOST.items():
                cat_boost = cat_boosts.get(slug, 0.0)
                if cat_boost == 0.0:
                    continue
                n = symptom_kategorien.get(cat, {}).get("n_tage", 0)
                scale = 1.0 if n >= 30 else (0.5 if n >= 10 else (0.25 if n >= 5 else 0.0))
                score += cat_boost * scale

        # ── Biomarker-Bonus ───────────────────────────────────────────────────
        biomarker_hints = []

        if respiration and respiration.get("pct_unter_95") and respiration["pct_unter_95"] > 20:
            if slug in ("babesiose", "mycoplasma", "chlamydia_pneumoniae", "dengue"):
                score += 1.5
                biomarker_hints.append("SpO2 <95% häufig")

        if kardio and kardio.get("high_af_tage", 0) > 0:
            if slug in ("enterovirus", "brucellose", "post_covid"):
                score += 1.0
                biomarker_hints.append("AFES elevated")

        if autonome and autonome.get("avg_ortho_delta") and autonome["avg_ortho_delta"] >= 20:
            if slug in ("sfn", "post_covid", "bartonellose", "hhv6", "q_fieber"):
                score += 1.2
                biomarker_hints.append("OI-Muster")

        if aktivitaet and aktivitaet.get("met_delta_pct") and aktivitaet["met_delta_pct"] < -30:
            if slug in ("chikungunya", "parvovirus", "yersiniose", "dengue"):
                score += 0.8
                biomarker_hints.append("Aktivitäts-Einbruch passend")

        arthr_dok = any(s in dok_symptome for s in
                        ("Gelenkschmerzen", "Arthralgie", "Arthritis"))
        if arthr_dok and slug in ("chikungunya", "parvovirus", "yersiniose",
                                   "borreliose", "anaplasmose", "brucellose"):
            score += 1.0
            biomarker_hints.append("Arthralgie dokumentiert")

        # ── Labor-Boost ───────────────────────────────────────────────────────
        lab_hints: list[str] = []
        lab_ausstehend: list[str] = []
        _med = open_medicine_db()
        for marker in LAB_MARKERS.get(slug, []):
            # Only use lab results from the post-infection window
            rows_lab = _med.execute(
                "SELECT wert, wert_num, ref_max, status FROM lab_manual"
                " WHERE parameter LIKE ? AND date >= ? ORDER BY date DESC LIMIT 1",
                (f"%{marker['parameter']}%", lc_start),
            ).fetchall()
            if not rows_lab:
                lab_ausstehend.append(marker["label"])
                continue
            wert, wert_num_v, ref_max_v, status_v = rows_lab[0]
            result_status = _lab_result_status(wert, wert_num_v, ref_max_v, status_v)
            boosts = _LAB_BOOST.get(marker.get("type", "IgG"), _LAB_BOOST["IgG"])
            if result_status == "elevated":
                score += boosts["elevated"]
                lab_hints.append(f"✓ {marker['label']} positiv/erhöht")
            elif result_status == "negative":
                score += boosts["negative"]
                lab_hints.append(f"✗ {marker['label']} negativ")
            else:
                lab_hints.append(f"? {marker['label']} (kein Referenz)")

        results.append({
            "slug":            slug,
            "name":            SYNDROME_CONFIG[slug]["name_de"],
            "score":           round(score, 2),
            "coverage_pct":    coverage_pct,
            "n_matched":       len(matched),
            "n_profil":        len(profil),
            "matched":         sorted(matched, key=lambda x: -x[1]),
            "biomarker_hints":  biomarker_hints,
            "lab_hints":        lab_hints,
            "lab_ausstehend":   lab_ausstehend,
            "prior_note":       prior_note,
            "sero_cat":         sero_cat,
            "sero_note":        sero_note,
            "reise_note":       reise_note,
            "reise_boost":      reise_boost,
        })

    _med.close()
    results.sort(key=lambda x: (-x["score"], -x["coverage_pct"]))
    return results


def build_differential_report(ranking: list, infection_date: str,
                                 lc_start: str, d_to: str, conn=None) -> str:
    lines = [
        "## Differenzialdiagnose — Syndrom-Vermutung (automatisch)\n",
        f"Infektionsdatum: **{infection_date}**  | Fenster: **{lc_start} – {d_to}**\n",
        "Methode: IDF-gewichteter Symptom-Abgleich + Biomarker-Bonus.  \n"
        "⚠ Kein Ersatz für klinische Diagnostik — nur Hinweisgeber.\n",
    ]

    if not ranking:
        lines.append("Keine Symptome im Tagebuch → kein Ranking möglich.")
        return "\n".join(lines)

    # ── Klinisch priorisiert: Exposition / bestätigte Infektion ──────────────
    # Unabhängig vom Symptom-Score — Expositionsanamnese + Therapierelevanz
    all_boosts = [
        (slug, boost, label, tier)
        for slug, (boost, label, tier) in _EXPOSURE_BOOSTS.items()
        if tier in ("confirmed", "exposure")
    ]
    exposure_entries  = sorted([e for e in all_boosts if e[3] == "exposure"],
                                key=lambda x: -x[1])
    confirmed_entries = sorted([e for e in all_boosts if e[3] == "confirmed"],
                                key=lambda x: -x[1])

    if exposure_entries:
        lines += [
            "### ⚕ Noch nicht getestet — Hochrisiko-Exposition dokumentiert\n",
            "Serologisch nie abgeklärt; Therapiekonsequenz möglich:\n",
        ]
        for slug, boost, exp_label, tier in exposure_entries:
            name = SYNDROME_CONFIG.get(slug, {}).get("name_de", slug)
            lab_markers = LAB_MARKERS.get(slug, [])

            # Impfstatus
            vacc = _vaccination_status_for_slug(slug, d_to)
            vacc_line = f"    Impfstatus: {vacc[0]} — {vacc[1]}" if vacc else ""

            # Vorhandene Lab-Ergebnisse
            existing_lab = _lab_results_for_slug(conn, slug) if conn else []
            if existing_lab:
                lab_done = "    Labor vorhanden: " + " | ".join(
                    f"{lbl} {icon} ({dt})" for dt, lbl, icon in existing_lab)
                pending = [m["label"] for m in lab_markers
                           if not any(m["label"] == lbl for _, lbl, _ in existing_lab)]
            else:
                lab_done = ""
                pending = [m["label"] for m in lab_markers]

            pending_str = ", ".join(pending[:4]) if pending else "–"
            entry = (
                f"  **{name}**\n"
                f"    Exposition: {exp_label}\n"
            )
            if vacc_line:
                entry += vacc_line + "\n"
            if lab_done:
                entry += lab_done + "\n"
            entry += f"    ⏳ Noch ausstehend: {pending_str}"
            lines.append(entry)
        lines.append("")

    if confirmed_entries:
        lines += [
            "### Bekannte Infektionen mit Post-Syndrom-Potenzial\n",
            "Alle klinisch/laborbestätigt — Reaktivierung oder Sequele möglich:\n",
        ]
        for slug, boost, exp_label, tier in confirmed_entries:
            name = SYNDROME_CONFIG.get(slug, {}).get("name_de", slug)
            lab_markers = LAB_MARKERS.get(slug, [])

            # Alle Infektionsereignisse für diesen Slug
            all_infections = _all_infections_for_slug(slug)

            # Impfstatus
            vacc = _vaccination_status_for_slug(slug, d_to)
            vacc_line = f"    Impfstatus: {vacc[0]} — {vacc[1]}" if vacc else ""

            # Lab-Ergebnisse
            existing_lab = _lab_results_for_slug(conn, slug) if conn else []
            if existing_lab:
                lab_done = "    Labor: " + " | ".join(
                    f"{lbl} {icon} ({dt})" for dt, lbl, icon in existing_lab)
            else:
                lab_done = ""
            pending = [m["label"] for m in lab_markers
                       if not any(m["label"] == lbl for _, lbl, _ in existing_lab)]
            pending_str = ("    ⏳ Ausstehend: " + ", ".join(pending[:4])) if pending else ""

            # Infektionszeile(n): bei mehreren Ereignissen alle auflisten
            if len(all_infections) > 1:
                vacc_count = len([e for e in _cfg.events
                                  if e.get("type") == "vaccination"
                                  and any(kw in e.get("name", "").lower()
                                          for kw in _VACCINE_SLUG_KEYWORDS.get(slug, []))])
                entry = f"  **{name}**  —  {len(all_infections)} Infektionen"
                if vacc_count:
                    entry += f" (trotz {vacc_count} Impfdosen — Impfdurchbrüche)"
                entry += "\n"
                for ev in all_infections:
                    ev_type = "↩ Reinfektion" if ev.get("type") == "reinfection" else "Infektion"
                    entry += f"    • {ev.get('date', '?')} {ev_type}: {ev.get('name', '')}\n"
            else:
                entry = f"  **{name}**  —  {exp_label}\n"

            if vacc_line:
                entry += vacc_line + "\n"
            if lab_done:
                entry += lab_done + "\n"
            if pending_str:
                entry += pending_str
            lines.append(entry)
        lines.append("")

    # Reise-Info aus Config anzeigen
    visited = _travel_region_set()
    if visited:
        lines.append(f"Bekannte Reiseregionen: {', '.join(sorted(visited))}\n")

    # Expositionsprofil
    lines += _exposure_profile_lines()

    lines += [
        "### Symptom-basiertes Ranking\n",
        f"  {'Rang':<5} {'Syndrom':<42} {'Score':>7} {'Cov':>6} {'Treffer':<8} {'Sero':<8} {'Hinweise'}",
        "  " + "─" * 90,
    ]
    for i, r in enumerate(ranking[:10], 1):
        hints_parts = []
        if r.get("prior_note"):
            hints_parts.append(f"📋 {r['prior_note']}")
        if r.get("reise_note"):
            hints_parts.append(f"✈ {r['reise_note']}")
        if r["biomarker_hints"]:
            hints_parts.append(", ".join(r["biomarker_hints"]))
        hints = f"  {' | '.join(hints_parts)}" if hints_parts else ""
        sero_label = {"hoch": "↑↑↑", "mittel": "↑↑", "niedrig": "↑",
                      "reise": "✈", "novel": "neu", "autoimmun": "AI",
                      "dysbiose": "GI"}.get(r.get("sero_cat", ""), "?")
        lines.append(
            f"  {i:<5} {r['name']:<42} {r['score']:>7.2f} "
            f"{r['coverage_pct']:>5.1f}%  "
            f"{r['n_matched']}/{r['n_profil']:<5}  {sero_label:<8}{hints}"
        )

    lines.append("")
    top = ranking[0]
    lines += [
        f"### Top-Treffer: **{top['name']}** (Score {top['score']:.2f})\n",
        f"Übereinstimmende Symptome: {', '.join(s for s,_ in top['matched'][:8])}",
    ]
    if top["biomarker_hints"]:
        lines.append(f"Biomarker-Hinweise: {', '.join(top['biomarker_hints'])}")
    if top.get("lab_hints"):
        lines.append(f"Labor: {', '.join(top['lab_hints'])}")
    lines.append("")

    # ── Labor-Status für alle Top-10 ─────────────────────────────────────────
    lab_rows = [(r["name"], r.get("lab_hints", []), r.get("lab_ausstehend", []))
                for r in ranking[:10]
                if r.get("lab_hints") or r.get("lab_ausstehend")]
    if lab_rows:
        lines += ["### Labor-Status (Top 10)\n"]
        for name, hints, ausstehend in lab_rows:
            lines.append(f"**{name}**")
            for h in hints:
                lines.append(f"  {h}")
            if ausstehend:
                lines.append(f"  ⏳ Ausstehend: {', '.join(ausstehend)}")
            lines.append("")

    lines += [
        "### Empfohlene Folge-Analyse\n",
        "Führe die Vollanalyse für die Top-3-Syndrome durch:\n",
    ]
    top3 = [r["slug"] for r in ranking[:3]]
    lines.append(
        f"  python analyse_postinfectious_diagnose.py "
        f"--infection-date {infection_date} "
        f"--syndrome {' '.join(top3)}"
    )

    # ── Seropr.-Kategorien-Übersicht ──────────────────────────────────────────
    lines += ["", "### Seroepidemiologischer Kontext\n",
              "Legende: ↑↑↑ Vorinfektion wahrscheinlich (≥50%) | ↑↑ möglich | "
              "↑ selten | ✈ reiseabhängig\n"]

    cat_groups = {"hoch": [], "mittel": [], "niedrig": [], "reise": []}
    for r in ranking:
        cat = r.get("sero_cat", "")
        if cat in cat_groups:
            sero = SYNDROME_SERO.get(r["slug"], {})
            pct  = sero.get("seroprevalence_de")
            pct_str = f"{pct:.0%}" if pct is not None else "?"
            cat_groups[cat].append(f"{r['name']} ({pct_str})")

    cat_labels = {
        "hoch":   "Annahme: Vorinfektion fast sicher — Frage ist Reaktivierung",
        "mittel": "Möglich — bei passender Anamnese relevant",
        "niedrig":"Selten in DE — spezifische Exposition / Risikogebiet nötig",
        "reise":  "Nur bei Auslandsaufenthalt in Endemiegebiet relevant",
    }
    for cat, label in cat_labels.items():
        names = cat_groups[cat]
        if names:
            lines.append(f"**{label}:**")
            lines.append(f"  {', '.join(names)}")
            lines.append("")

    return "\n".join(lines)


def load_baseline(conn, infection_date: str) -> dict:
    """Lädt Prä-Infektions-Werte (vor infection_date) als Vergleichsbasis."""
    end = (datetime.strptime(infection_date, "%Y-%m-%d")
           - timedelta(days=1)).strftime("%Y-%m-%d")
    start = (datetime.strptime(infection_date, "%Y-%m-%d")
             - timedelta(days=730)).strftime("%Y-%m-%d")

    base = {}

    r = conn.execute("""
        SELECT AVG(rmssd_ms), COUNT(*) FROM polar_nightly_hrv
        WHERE date >= ? AND date <= ? AND rmssd_ms > 0
    """, (start, end)).fetchone()
    base["rmssd"] = r[0]
    base["rmssd_n"] = r[1]
    # Fallback ohne Polar: HRV-Baseline aus measurements (oft leer bei Garmin pre-2026)
    if not base["rmssd"]:
        r = conn.execute("""
            SELECT AVG(value), COUNT(*) FROM measurements
            WHERE metric IN ('hrv_rmssd','rmssd') AND date >= ? AND date <= ? AND value > 0
        """, (start, end)).fetchone()
        base["rmssd"], base["rmssd_n"] = r[0], r[1]

    r = conn.execute("""
        SELECT AVG(value), COUNT(*) FROM measurements
        WHERE metric = 'met_minutes' AND date >= ? AND date <= ? AND value IS NOT NULL
    """, (start, end)).fetchone()
    base["met"] = r[0]
    base["met_n"] = r[1]
    # Fallback: MET-Baseline aus Garmin-Intensitätsminuten (moderat×4 + intensiv×8)
    if not base["met"]:
        r = conn.execute("""
            SELECT date, metric, AVG(value) FROM measurements
            WHERE metric IN ('intensity_moderate','intensity_vigorous')
              AND date >= ? AND date <= ? GROUP BY date, metric
        """, (start, end)).fetchall()
        im = defaultdict(dict)
        for d, m, v in r:
            im[d][m] = v
        mets = [(mv.get("intensity_moderate", 0) or 0) * 4 + (mv.get("intensity_vigorous", 0) or 0) * 8
                for mv in im.values()]
        base["met"] = sum(mets) / len(mets) if mets else None
        base["met_n"] = len(mets)

    r = conn.execute("""
        SELECT AVG(dfa_alpha1), COUNT(DISTINCT DATE(fenster_start))
        FROM ppi_hrv_advanced
        WHERE DATE(fenster_start) >= ? AND DATE(fenster_start) <= ?
          AND artifact_pct < 0.1
    """, (start, end)).fetchone()
    base["dfa"] = r[0]
    base["dfa_n"] = r[1]

    r = conn.execute("""
        SELECT AVG(sm.value) FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep' AND sm.metric = 'deep_pct'
          AND s.date >= ? AND s.date <= ?
    """, (start, end)).fetchone()
    base["deep_pct"] = r[0]

    base["period"] = (start, end)
    return base


def load_exposure_priors(conn, lc_start: str) -> dict[str, float]:
    """Liest Exposition-Priors aus den DB-Tabellen der Exposure-Skripte.

    Datenquellen:
    - pathogen_exposure_summary: Lifetime-Expositionsrisiko aus manuellen Einträgen
      und Reisehistorie (z.B. Endemiegebiete, bekannte Expositionen)
    - outbreak_exposure × outbreak_events: Reise-basierte Exposure-Berechnung
      durch Überschneidung von Reisedaten mit gemeldeten Ausbrüchen
      (Quellen: WHO, ECDC, RKI, LGL, CDC, ProMED, HealthMap, etc.)

    Gibt {slug: boost} zurück. Fällt auf {} zurück wenn Tabellen leer/fehlen.
    Config-basierte _EXPOSURE_BOOSTS haben immer Vorrang (bestätigte Infektionen).
    DB-Priors sind Hintergrund-Hypothesen aus Reise- und Expositionsdaten.
    """
    priors: dict[str, float] = {}

    # ── pathogen_exposure_summary ────────────────────────────────────────────
    RISK_BOOST = {"hoch": 2.0, "high": 2.0, "mittel": 1.0,
                  "medium": 1.0, "niedrig": 0.5, "low": 0.5}
    try:
        rows = conn.execute("""
            SELECT slug, risk_level, MAX(score) AS top_score
            FROM pathogen_exposure_summary
            WHERE slug IS NOT NULL AND slug != ''
            GROUP BY slug
        """).fetchall()
        for slug, risk_level, top_score in rows:
            base = RISK_BOOST.get(risk_level, 0.5)
            scale = min(top_score / 100.0, 1.0)
            priors[slug] = round(base * (0.5 + 0.5 * scale), 2)
    except Exception:
        pass  # Tabelle nicht befüllt

    # ── outbreak_exposure × outbreak_events ──────────────────────────────────
    # Nur Ausbrüche, deren Reise nach lc_start endete (zeitlich relevant).
    try:
        rows = conn.execute("""
            SELECT ob.syndrome_slug, MAX(oe.exposure_score) AS top_score
            FROM outbreak_exposure oe
            JOIN outbreak_events ob ON oe.outbreak_id = ob.id
            WHERE ob.syndrome_slug IS NOT NULL
              AND oe.trip_date_to >= ?
            GROUP BY ob.syndrome_slug
        """, (lc_start,)).fetchall()
        for slug, top_score in rows:
            # Outbreak-Boost addiert sich auf Pathogen-Prior (falls vorhanden)
            priors[slug] = round(priors.get(slug, 0.0) + top_score * 1.5, 2)
    except Exception:
        pass  # Tabelle nicht befüllt

    return priors


# ── Quarterly Trend ───────────────────────────────────────────────────────────

def compute_trend(data: dict, lc_start: str, d_to: str) -> list:
    """Quartals-Übersicht: RMSSD, MET-Minuten, HRV-Crash-Rate."""
    start = datetime.strptime(lc_start, "%Y-%m-%d")
    end   = datetime.strptime(d_to, "%Y-%m-%d")

    # Earliest date with nightly RMSSD — used to annotate source in the table.
    # polar_nightly_hrv = sleep-context RMSSD; before that only daytime H10
    # sessions exist (ppi_hrv_advanced), which are not used here.
    first_nhrv = min(data["nhrv"].keys()) if data["nhrv"] else None

    quarters = []
    cur = start
    while cur < end:
        q_end = min(cur + timedelta(days=91), end)
        qs = cur.strftime("%Y-%m-%d")
        qe = q_end.strftime("%Y-%m-%d")

        nhrv = [v["rmssd"] for d, v in data["nhrv"].items() if qs <= d <= qe]
        met  = [v["met_minutes"] for d, v in data["activity"].items()
                if qs <= d <= qe and "met_minutes" in v]
        pem_q = {d: v for d, v in data["pem"].items() if qs <= d <= qe}
        pem_d = [v["delta"] for v in pem_q.values() if v["delta"] is not None]
        crash_pct = (_pct_below(pem_d, REF["hrv_crash_pct"])
                     if pem_d else None)
        sdnn_days = sum(1 for v in pem_q.values() if (v.get("source") or "") == "sdnn_apple")

        # "nightly" = polar_nightly_hrv; "none" = no nightly RMSSD this quarter
        rmssd_source = "nightly" if nhrv else "none"

        quarters.append({
            "label":        cur.strftime("%Y-Q%q").replace("Q1", "Q1").replace(
                            "%q", str((cur.month - 1) // 3 + 1)),
            "start":        qs, "end": qe,
            "rmssd":        _avg(nhrv),
            "rmssd_source": rmssd_source,
            "first_nhrv":   first_nhrv,
            "met":          _avg(met),
            "crash_pct":    crash_pct,
            "n_nhrv":       len(nhrv),
            "n_met":        len(met),
            "sdnn_days":    sdnn_days,
        })
        cur = q_end + timedelta(days=1)

    return quarters


# ── Domain-Bewertungen ────────────────────────────────────────────────────────

def bewerte_autonome(data: dict, baseline: dict, personal_bl: dict | None = None) -> dict:
    rhr_vals  = list(data["rhr"].values())
    dfa_vals  = [v["avg"] for v in data["dfa"].values() if v["avg"]]
    lfhf_vals = [v["lfhf"] for v in data["dfa"].values() if v["lfhf"]]
    nhrv_vals = [v["rmssd"] for v in data["nhrv"].values()]

    avg_rhr  = _avg(rhr_vals)
    avg_dfa  = _avg(dfa_vals)
    avg_lfhf = _avg(lfhf_vals)
    avg_nhrv = _avg(nhrv_vals)
    pct_dfa_krit = _pct_below(dfa_vals, REF["dfa_kritisch"])

    ortho_deltas = []
    for v in data["ortho"].values():
        sup = v.get("hr_supine") or v.get("hr_lowest")
        std = v.get("hr_stand") or v.get("hr_standup_min")
        if sup and std:
            ortho_deltas.append(std - sup)
    avg_ortho = _avg(ortho_deltas)

    rmssd_delta_pct = None
    rmssd_baseline_src = None
    if avg_nhrv and baseline.get("rmssd"):
        rmssd_delta_pct = round(
            (avg_nhrv - baseline["rmssd"]) / baseline["rmssd"] * 100, 1)
        rmssd_baseline_src = "pre-event"
    elif avg_nhrv and personal_bl and personal_bl["n_days"] >= 30:
        delta = baseline_delta_pct(avg_nhrv, personal_bl)
        if delta is not None:
            rmssd_delta_pct = round(delta, 1)
            rmssd_baseline_src = f"personal ({personal_bl['value']:.0f} ms, n={personal_bl['n_days']})"

    return {
        "avg_rhr": avg_rhr, "avg_dfa": avg_dfa, "avg_lfhf": avg_lfhf,
        "avg_nhrv": avg_nhrv, "pct_dfa_krit": pct_dfa_krit,
        "avg_ortho_delta": avg_ortho,
        "n_rhr": len(rhr_vals), "n_dfa": len(dfa_vals), "n_nhrv": len(nhrv_vals),
        "rmssd_delta_pct": rmssd_delta_pct,
        "rmssd_baseline_src": rmssd_baseline_src,
        "baseline_rmssd": baseline.get("rmssd"),
    }


def bewerte_pem(data: dict) -> dict:
    pem = data["pem"]
    deltas = [v["delta"] for v in pem.values() if v["delta"] is not None]
    crashes = [d for d, v in pem.items()
               if v["delta"] is not None and v["delta"] <= REF["hrv_crash_pct"]]
    pem_events = sum(1 for v in pem.values() if v["signal"] == 1)
    avg_delta = _avg(deltas)
    pct_crashes = round(len(crashes) / len(deltas) * 100, 1) if deltas else None
    worst = min(deltas) if deltas else None
    pem_sport   = sum(1 for v in pem.values() if v["signal"] == 1 and v.get("sport_prior_3d") == 1)
    pem_nosport = sum(1 for v in pem.values() if v["signal"] == 1 and v.get("sport_prior_3d") == 0)
    nopem_sport = sum(1 for v in pem.values() if v["signal"] == 0 and v.get("sport_prior_3d") == 1)
    n_sport_total = pem_sport + nopem_sport
    return {
        "n_tage": len(pem), "avg_hrv_delta": avg_delta, "pct_crashes": pct_crashes,
        "n_crashes": len(crashes), "pem_events": pem_events, "worst_delta": worst,
        "pem_sport": pem_sport, "pem_nosport": pem_nosport,
        "nopem_sport": nopem_sport, "n_sport_total": n_sport_total,
    }


def bewerte_kardio(data: dict) -> dict:
    af = data["af"]
    af_tage_pos = sum(1 for v in af.values()
                      if v.get("level") not in (None, "none", "NONE"))
    avg_af      = _avg([v["score"] for v in af.values() if v.get("score") is not None])
    high_af     = sum(1 for v in af.values()
                      if v.get("level") in ("high", "HIGH", "critical", "CRITICAL",
                                             "very_high", "VERY_HIGH"))
    by_level = {}
    for v in af.values():
        lvl = (v.get("level") or "none").lower()
        by_level[lvl] = by_level.get(lvl, 0) + 1
    return {
        "af_tage": af_tage_pos, "af_gesamt": len(af),
        "avg_af_score": avg_af, "high_af_tage": high_af,
        "by_level": by_level,
    }


def bewerte_schlaf(data: dict) -> dict:
    sleep = data["sleep"]
    deep_vals = [v["deep_pct"] for v in sleep.values() if "deep_pct" in v]
    eff_vals  = [v["efficiency_pct"] for v in sleep.values() if "efficiency_pct" in v]
    avg_deep = _avg(deep_vals)
    avg_eff  = _avg(eff_vals)
    pct_low_deep = _pct_below(deep_vals, REF["deep_sleep_min"])

    nhrv = data["nhrv"]
    nhrv_devs = []
    for v in nhrv.values():
        if v["baseline"] and v["baseline"] > 0:
            nhrv_devs.append((v["rmssd"] - v["baseline"]) / v["baseline"] * 100)
    avg_nhrv_dev    = _avg(nhrv_devs)
    pct_below_base  = _pct_below(nhrv_devs, -10.0)

    return {
        "avg_deep_pct": avg_deep, "avg_efficiency": avg_eff,
        "pct_low_deep": pct_low_deep, "n_schlaefe": len(sleep),
        "avg_nhrv_dev": avg_nhrv_dev, "pct_nhrv_below_base": pct_below_base,
        "n_nhrv": len(nhrv_devs),
    }


def bewerte_aktivitaet(data: dict, baseline: dict) -> dict:
    act = data["activity"]
    met = [v["met_minutes"] for v in act.values() if "met_minutes" in v]
    mod = [v["level_moderate_s"] / 60 for v in act.values() if "level_moderate_s" in v]
    vig = [v["level_vigorous_s"] / 60 for v in act.values() if "level_vigorous_s" in v]
    avg_met = _avg(met)

    met_delta_pct = None
    if avg_met and baseline.get("met"):
        met_delta_pct = round((avg_met - baseline["met"]) / baseline["met"] * 100, 1)

    return {
        "avg_met": avg_met, "pct_unter_200met": _pct_below(met, 200),
        "avg_moderate_min": _avg(mod), "avg_vigorous_min": _avg(vig),
        "n_tage": len(met), "met_delta_pct": met_delta_pct,
        "baseline_met": baseline.get("met"),
    }


def bewerte_respiration(data: dict) -> dict:
    spo2 = data["spo2"]
    avg_vals = [v["avg"] for v in spo2.values() if v["avg"]]
    min_vals = [v["min"] for v in spo2.values() if v["min"]]
    return {
        "avg_spo2": _avg(avg_vals),
        "min_spo2": min(min_vals) if min_vals else None,
        "pct_unter_97": _pct_below(avg_vals, REF["spo2_lc_warn"]),
        "pct_unter_95": _pct_below(min_vals, REF["spo2_min"]),
        "n_tage": len(avg_vals),
    }


def bewerte_symptom_kategorien(conn, lc_start: str, d_to: str) -> dict:
    """Kategorisiert Symptomtagebuch-Einträge nach symptom_map.json-Kategorien.

    Returns: {category: {n_tage, n_unique, top: [(symptom, n_tage), ...]}}
    Kognitivtest-Performance wird separat aus cognitive_tests integriert.
    """
    rows = conn.execute("""
        SELECT symptom, COUNT(DISTINCT date) as n_tage
        FROM symptoms WHERE date >= ? AND date <= ?
        GROUP BY symptom ORDER BY n_tage DESC
    """, (lc_start, d_to)).fetchall()

    # Normalize raw symptom strings to canonical German display label
    # and deduplicate (e.g. 'tinnitus' + 'Tinnitus' → 'Tinnitus', summed)
    merged: dict[str, tuple[str, int]] = {}  # label → (category, n_tage)
    for symptom, n_tage in rows:
        cat = (_SYMPTOM_CATEGORY_MAP.get(symptom)
               or _SYMPTOM_CATEGORY_MAP.get(symptom.lower()))
        if not cat or cat in ("treatment", "other"):
            continue
        label = (_SYMPTOM_LABEL_MAP.get(symptom)
                 or _SYMPTOM_LABEL_MAP.get(symptom.lower())
                 or symptom)
        if label in merged:
            existing_cat, existing_n = merged[label]
            merged[label] = (existing_cat, existing_n + n_tage)
        else:
            merged[label] = (cat, n_tage)

    by_cat: dict[str, dict] = {}
    for label, (cat, n_tage) in merged.items():
        if cat not in by_cat:
            by_cat[cat] = {"n_tage": 0, "n_unique": 0, "top": []}
        by_cat[cat]["n_unique"] += 1
        by_cat[cat]["n_tage"] += n_tage
        by_cat[cat]["top"].append((label, n_tage))

    # Kognitivtest-Daten aus cognitive_tests ergänzen (falls vorhanden)
    try:
        cog_rows = conn.execute("""
            SELECT test_name, COUNT(*) as n_sessions,
                   AVG(score_pct) as avg_pct, MIN(score_pct) as min_pct
            FROM cognitive_tests
            WHERE date >= ? AND date <= ? AND score_pct IS NOT NULL
            GROUP BY test_name
        """, (lc_start, d_to)).fetchall()
        if cog_rows:
            if "neurological" not in by_cat:
                by_cat["neurological"] = {"n_tage": 0, "n_unique": 0, "top": []}
            by_cat["neurological"]["cognitive_tests"] = [
                {"test": t, "n": n, "avg_pct": round(a, 1), "min_pct": round(m, 1)}
                for t, n, a, m in cog_rows
            ]
    except Exception:
        pass  # Tabelle noch nicht vorhanden

    for cat in by_cat:
        by_cat[cat]["top"] = by_cat[cat]["top"][:8]
    return by_cat


def bewerte_schweregrad(autonome, pem, aktivitaet, schlaf) -> str:
    """Gesamtschweregrad basierend auf Workwell/ICC und Baseline-Deltas."""
    met = aktivitaet["avg_met"] or 0
    met_delta = aktivitaet["met_delta_pct"] or 0
    rmssd_delta = autonome["rmssd_delta_pct"] or 0
    crash_pct = pem["pct_crashes"] or 0

    score = 0
    # MET-Einschränkung
    if met < 100 or met_delta < -70:
        score += 3
    elif met < 200 or met_delta < -50:
        score += 2
    elif met < 400 or met_delta < -25:
        score += 1
    # RMSSD-Einbruch
    if rmssd_delta < -50:
        score += 2
    elif rmssd_delta < -25:
        score += 1
    # PEM-Crash-Rate
    if crash_pct > 30:
        score += 2
    elif crash_pct > 15:
        score += 1
    # Autonomie
    nhrv = autonome["avg_nhrv"] or 30
    if nhrv < 15:
        score += 1

    if score >= 6:
        return "schwer"
    if score >= 3:
        return "moderat"
    return "leicht"


# ── Bericht ───────────────────────────────────────────────────────────────────

def build_report(data, autonome, pem, kardio, schlaf, aktivitaet, respiration,
                     trend, baseline, kognition, syndrom_symptome,
                     infection_date, lc_start, d_to,
                     symptom_kategorien: dict = None,
                     exposure_priors: dict = None) -> str:
    codes = SYNDROME_CODES.get(_SYNDROME_CFG["slug"], {})
    icd10_str = ", ".join(codes.get("icd10_gm", [])) or "—"
    melde_str = "⚠ Meldepflichtig (§ 7 IfSG)" if codes.get("meldepflicht_de") else ""
    gl = codes.get("guidelines", {})
    gl_lines = [f"  {k.upper()}: {v}" for k, v in gl.items()]

    lines = [
        f"## {_SYNDROME_CFG['name_de']} — Diagnostik-Score\n",
        f"Infektionsdatum: **{infection_date}**  "
        f"| Analysefenster: **{lc_start} – {d_to}**  "
        f"(≥{_SYNDROME_CFG['lag_weeks']} Wochen post-akut)\n",
        f"ICD-10-GM: `{icd10_str}`"
        + (f"  |  {melde_str}" if melde_str else "") + "\n",
        f"Referenzen: {_SYNDROME_CFG['refs']}\n",
    ]
    if gl_lines:
        lines += ["**Leitlinien:**"] + gl_lines + [""]

    # ── Schweregrad-Banner ────────────────────────────────────────────────────
    schwere = bewerte_schweregrad(autonome, pem, aktivitaet, schlaf)
    schwere_icon = {"leicht": "🟡", "moderat": "🟠", "schwer": "🔴"}.get(schwere, "⚪")
    lines += [
        f"### Gesamtschweregrad: {schwere_icon} **{schwere.upper()}**\n",
        f"  Basierend auf: MET-Einschränkung {_f(aktivitaet['met_delta_pct'], '+.0f')}%"
        f"  | RMSSD-Einbruch {_f(autonome['rmssd_delta_pct'], '+.0f')}%"
        f"  | HRV-Crash-Rate {_f(pem['pct_crashes'], '.0f')}%"
        f"  | Nightly RMSSD {_f(autonome['avg_nhrv'])} ms\n",
    ]

    # ── Baseline-Vergleich ────────────────────────────────────────────────────
    if baseline.get("rmssd") or baseline.get("met"):
        bp = baseline["period"]
        lines += [
            f"### Prä-Infektions-Baseline ({bp[0]} – {bp[1]})\n",
        ]
        if baseline.get("rmssd"):
            d_rmssd = autonome["rmssd_delta_pct"]
            sym = "❌" if (d_rmssd or 0) < -40 else "⚠" if (d_rmssd or 0) < -20 else "✅"
            lines.append(
                f"  Nightly RMSSD: {sym} {_f(baseline['rmssd'], '.0f')} ms → "
                f"{_f(autonome['avg_nhrv'])} ms  "
                f"(**{_f(d_rmssd, '+.0f')}%**; n={baseline.get('rmssd_n', '?')})"
            )
        if baseline.get("met"):
            d_met = aktivitaet["met_delta_pct"]
            sym = "❌" if (d_met or 0) < -40 else "⚠" if (d_met or 0) < -20 else "✅"
            lines.append(
                f"  MET-Minuten/Tag: {sym} {_f(baseline['met'], '.0f')} → "
                f"{_f(aktivitaet['avg_met'])} MET·min  "
                f"(**{_f(d_met, '+.0f')}%**; n={baseline.get('met_n', '?')})"
            )
        if baseline.get("dfa"):
            lines.append(
                f"  DFA α1:        {_f(baseline['dfa'], '.3f')} → "
                f"{_f(autonome['avg_dfa'], '.3f')}  "
                f"(n={baseline.get('dfa_n', '?')})"
            )
        lines.append("")

    # ── Domäne 1: Autonome Dysregulation ──────────────────────────────────────
    rhr_sym  = _score_symbol(autonome["avg_rhr"],  60,  80,  90,  invert=False)
    dfa_sym  = _score_symbol(autonome["avg_dfa"],  REF["dfa_grenz"], 0.85,
                             REF["dfa_kritisch"], invert=True)
    nhrv_sym = _score_symbol(autonome["avg_nhrv"], REF["rmssd_min_normal"], 20, 15, invert=True)
    lfhf_sym = "❌" if (autonome["avg_lfhf"] or 0) > 2 else "⚠"

    pots_str = "keine Daten"
    if autonome["avg_ortho_delta"] is not None:
        d = autonome["avg_ortho_delta"]
        if d >= REF["pots_delta"]:
            pots_str = f"❌ POTS-Kriterium erfüllt ({d:.0f} bpm ≥ 30)"
        elif d >= 20:
            pots_str = (f"⚠ Orthostatische Intoleranz ({d:.0f} bpm; "
                        f"kein formales POTS <30 bpm)")
        else:
            pots_str = f"✅ normal ({d:.0f} bpm)"

    lines += [
        "### 1. Autonome Dysregulation\n",
        f"  Resting HR:      {rhr_sym} Ø **{_f(autonome['avg_rhr'])} bpm**"
        f"  (Ref. ≤60 bpm; n={autonome['n_rhr']})",
        f"  Nightly RMSSD:   {nhrv_sym} Ø **{_f(autonome['avg_nhrv'])} ms**"
        + (_delta_str(autonome["avg_nhrv"], autonome["baseline_rmssd"])
           or "  (LC-typisch ~20 ms; gesund 30+ ms)")
        + f"  n={autonome['n_nhrv']}",
        f"  DFA α1:          {dfa_sym} Ø **{_f(autonome['avg_dfa'], '.3f')}**"
        f"  (Gronwald 2023: <0.75 kritisch;"
        f" {_f(autonome['pct_dfa_krit'], '.1f')}% der Fenster krit.)",
        f"  LF/HF-Ratio:     {lfhf_sym} Ø {_f(autonome['avg_lfhf'], '.2f')}"
        f"  (>2.0 = sympathisch dominiert; LF/HF = indirekter ANS-Stressmarker)",
        f"  Orthostase Δ HR: {pots_str}",
        "",
    ]

    # ── Domäne 2: PEM ─────────────────────────────────────────────────────────
    crash_sym = ("❌" if (pem["pct_crashes"] or 0) > 20
                 else "⚠" if (pem["pct_crashes"] or 0) > 10 else "✅")
    lines += [
        "### 2. Post-Exertionelle Malaise (PEM)\n",
        f"  HRV-Einbrüche ≤−10% (Davis 2023): {crash_sym} "
        f"**{_f(pem['pct_crashes'], '.1f')}%** der Tage"
        f"  ({pem['n_crashes']} von {pem['n_tage']})",
        f"  Ø HRV-Δ Folgetag:  {_f(pem['avg_hrv_delta'], '+.1f')}%"
        f"  | Schlechtester: {_f(pem['worst_delta'])}%",
        f"  Formale PEM-Events (1σ): {pem['pem_events']}",
    ]
    # Sport-bereinigter PEM Evidence Score
    ev = data.get("pem_evidence", {})
    if ev:
        n_ev      = len(ev)
        n_pem_pat = sum(1 for v in ev.values() if v["pattern"] == "pem_pattern")
        n_high    = sum(1 for v in ev.values() if v["level"] in ("high", "critical"))
        n_sport   = sum(1 for v in ev.values()
                        if v["pattern"] in ("sport_adaptation", "supercompensation"))
        pem_pct   = round(n_pem_pat / n_ev * 100, 1) if n_ev else 0
        sport_pct = round(n_sport / n_ev * 100, 1) if n_ev else 0
        lines += [
            f"  Sport-bereinigt (pem_evidence_scores, n={n_ev} Tage):",
            f"    PEM-Pattern: **{n_pem_pat} Tage ({pem_pct}%)**"
            f"  | High/Critical: {n_high}"
            f"  | Sport-erklärbar: {sport_pct}%",
        ]

    # 2×2 Sport-Kontext (sport_prior_3d aus pem_correlation)
    ps = pem["pem_sport"]; pn = pem["pem_nosport"]
    ns = pem["nopem_sport"]; nt = pem["n_sport_total"]
    n_pem_t = ps + pn
    if n_pem_t > 0 or nt > 0:
        lines += [
            "  Sport-Kontext (Rückschau D-1..D-3, alle Tage):",
            f"    Sport-getriggertes PEM: {ps}/{n_pem_t} "
            f"({round(ps/n_pem_t*100) if n_pem_t else 0}%)"
            f"  | Spontanes PEM: {pn}/{n_pem_t}",
            f"    Tolerierter Sport:      {ns}/{nt} "
            f"({round(ns/nt*100) if nt else 0}% ohne PEM-Folge)",
        ]
    lines.append("")

    # ── Domäne 3: Kardiovaskulär ──────────────────────────────────────────────
    if kardio["high_af_tage"] > 0:
        af_sym = "❌"
    elif kardio["af_tage"] > kardio["af_gesamt"] * 0.5:
        af_sym = "⚠"
    else:
        af_sym = "⚠"

    lvl = kardio["by_level"]
    lines += [
        "### 3. Kardiovaskulär\n",
        f"  AF-Evidence-Score (AFES): {af_sym}"
        f"  Level ≥ low an {kardio['af_tage']} von {kardio['af_gesamt']} Tagen"
        f"  | Ø Score: {_f(kardio['avg_af_score'], '.1f')}",
        f"  {'Level':<10} {'Tage':>6}  Bedeutung",
        "  " + "─" * 48,
    ]
    afes_info = {
        "none":     "kein relevantes Signal (<10 Pkt)",
        "low":      "schwaches Signal, mehrere Indikatoren",
        "moderate": "mäßige Evidenz, direkte + Stützsignale",
        "high":     "starke Evidenz (≥50 Pkt)",
        "critical": "sehr starke Evidenz (≥75 Pkt)",
    }
    for k in ("none", "low", "moderate", "high", "critical"):
        n = lvl.get(k, 0)
        if n > 0:
            lines.append(f"  {k:<10} {n:>6}  {afes_info[k]}")
    lines += [
        f"  Direkte Evidenz (high+critical): {kardio['high_af_tage']} Tage",
        "",
    ]

    # ── Domäne 4: Schlaf & Erholung ───────────────────────────────────────────
    deep_sym     = _score_symbol(schlaf["avg_deep_pct"], 20, REF["deep_sleep_min"],
                                 10, invert=True)
    nhrv_dev_sym = ("❌" if (schlaf["pct_nhrv_below_base"] or 0) > 30
                    else "⚠" if (schlaf["pct_nhrv_below_base"] or 0) > 15 else "✅")
    lines += [
        "### 4. Schlaf & Erholung\n",
        f"  Tiefschlaf:      {deep_sym} Ø **{_f(schlaf['avg_deep_pct'], '.1f')}%**"
        f"  (Schlafmedizin: N3 15–25% normal, <15% reduziert;"
        f" {_f(schlaf['pct_low_deep'])}% der Nächte darunter)",
        f"  Schlafeffizienz: Ø {_f(schlaf['avg_efficiency'])}%"
        f"  (n={schlaf['n_schlaefe']} Nächte)",
        f"  Nightly RMSSD vs. Baseline: {nhrv_dev_sym}"
        f"  Ø {_f(schlaf['avg_nhrv_dev'], '+.1f')}%"
        f"  ({_f(schlaf['pct_nhrv_below_base'])}% der Nächte >10% unter Baseline)",
        "",
    ]

    # ── Domäne 5: Aktivitätstoleranz ─────────────────────────────────────────
    # gut=86 (WHO min), warn=43 (50% WHO min), schlecht=20 — invert: höher = besser
    met_sym = _score_symbol(aktivitaet["avg_met"], REF["met_min_normal"], 43, 20,
                            invert=True)
    lines += [
        "### 5. Aktivitätstoleranz\n",
        f"  MET-Minuten/Tag: {met_sym} Ø **{_f(aktivitaet['avg_met'])}**"
        + (_delta_str(aktivitaet["avg_met"], aktivitaet["baseline_met"])
           or f"  (WHO-Minimum: {REF['met_min_normal']} MET·min/Tag)"),
        f"  Moderate Akt.:   Ø {_f(aktivitaet['avg_moderate_min'])} min/Tag"
        f"  | Intensive Akt.: Ø {_f(aktivitaet['avg_vigorous_min'])} min/Tag",
        f"  Tage <200 MET·min: {_f(aktivitaet['pct_unter_200met'])}%"
        f"  (n={aktivitaet['n_tage']})",
        "",
    ]

    # ── Domäne 6: Respiration ─────────────────────────────────────────────────
    spo2_sym = "✅"
    if respiration["n_tage"] > 0:
        spo2_sym = _score_symbol(respiration["avg_spo2"], 98, REF["spo2_lc_warn"],
                                 REF["spo2_min"], invert=True)
        lines += [
            "### 6. Respiratorisch (SpO2)\n",
            f"  Ø SpO2:    {spo2_sym} **{_f(respiration['avg_spo2'], '.1f')}%**"
            f"  (n={respiration['n_tage']} Tage)",
            f"  <97%: {_f(respiration['pct_unter_97'])}% der Tage"
            f"  | <95%: {_f(respiration['pct_unter_95'])}% der Tage"
            f"  | Minimum: **{_f(respiration['min_spo2'])}%**",
                "",
        ]
    else:
        lines += ["### 6. Respiratorisch (SpO2)\n",
                  "  Keine SpO2-Daten im Analysefenster.", ""]

    # ── Quarterly Trend ───────────────────────────────────────────────────────
    if trend:
        first_nhrv_date = next((q["first_nhrv"] for q in trend if q.get("first_nhrv")), None)
        nhrv_note = (f"ab {first_nhrv_date[:7]}" if first_nhrv_date
                     else "keine Nacht-RMSSD")
        lines += ["### Quartalsverlauf (RMSSD / MET / HRV-Crash-Rate)\n",
                  f"  Quelle RMSSD: Nacht-HRV (polar_nightly_hrv, {nhrv_note})."
                  f" Davor: keine Nacht-Baseline (H10-Tagessessions vorhanden, aber hier nicht gezeigt).\n",
                  f"  {'Quartal':<10} {'RMSSD':>8} {'MET·min':>9} {'Crash%':>8}  {'n-HRV':>6}"]
        lines.append("  " + "─" * 48)
        has_sdnn = any(q.get("sdnn_days", 0) for q in trend)
        nhrv_started = False
        for q in trend:
            if q["rmssd_source"] == "nightly" and not nhrv_started:
                lines.append(f"  ▶ Nacht-RMSSD verfügbar ab {q['start'][:7]}")
                nhrv_started = True
            rmssd_str = f"{q['rmssd']:.0f} ms" if q["rmssd"] else "  —   "
            met_str   = f"{q['met']:.0f}"       if q["met"]   else "  —  "
            crash_str = f"{q['crash_pct']:.0f}%" if q["crash_pct"] is not None else "  —  "
            sdnn_marker = "†" if q.get("sdnn_days", 0) else " "
            lines.append(
                f"  {q['label']:<10} {rmssd_str:>8} {met_str:>9} {crash_str:>8}"
                f"  n={q['n_nhrv']}{sdnn_marker}")
        if has_sdnn:
            lines.append("  † Crash-Rate in diesem Quartal SDNN-basiert (Apple Watch), nicht RMSSD")
        # Trend-Urteil
        rmssd_vals = [q["rmssd"] for q in trend if q["rmssd"]]
        if len(rmssd_vals) >= 3:
            first_q = rmssd_vals[0]
            last_q  = rmssd_vals[-1]
            delta_q = last_q - first_q
            if delta_q > 2:
                trend_urteil = f"leichte Verbesserung (+{delta_q:.0f} ms)"
            elif delta_q < -2:
                trend_urteil = f"Verschlechterung ({delta_q:.0f} ms)"
            else:
                trend_urteil = "stabil / persistierend"
            lines.append(f"\n  RMSSD-Trend: **{trend_urteil}**")
        lines.append("")

    # ── Zusammenfassung ───────────────────────────────────────────────────────
    resp_detail = ("keine Daten" if respiration["n_tage"] == 0
                   else f"{_f(respiration['avg_spo2'], '.1f')}% Ø, Min {_f(respiration['min_spo2'])}%")
    lines += [
        "### Zusammenfassung — Domänen-Übersicht\n",
        f"  {'Domäne':<32} {'Status':<6} {'Wichtigster Befund'}",
        "  " + "─" * 74,
        f"  {'1. Autonome Dysregulation':<32} {rhr_sym:<6} "
        f"RHR {_f(autonome['avg_rhr'])} bpm, RMSSD {_f(autonome['avg_nhrv'])} ms"
        + (f" ({_f(autonome['rmssd_delta_pct'], '+.0f')}% vs. Baseline)"
           if autonome["rmssd_delta_pct"] else ""),
        f"  {'2. Post-Exertionelle Malaise':<32} {crash_sym:<6} "
        f"{_f(pem['pct_crashes'])}% HRV-Crashes, Lag +2d",
        f"  {'3. Kardiovaskulär':<32} {af_sym:<6} "
        f"AF-Screening an {kardio['af_tage']} Tagen (keine Diagnose)",
        f"  {'4. Schlaf & Erholung':<32} {deep_sym:<6} "
        f"Tiefschlaf Ø {_f(schlaf['avg_deep_pct'], '.1f')}%",
        f"  {'5. Aktivitätstoleranz':<32} {met_sym:<6} "
        f"Ø {_f(aktivitaet['avg_met'])} MET·min/Tag"
        + (f" ({_f(aktivitaet['met_delta_pct'], '+.0f')}% vs. Baseline)"
           if aktivitaet["met_delta_pct"] else ""),
        f"  {'6. Respiration (SpO2)':<32} {spo2_sym:<6} {resp_detail}",
        "",
    ]

    # ── Kognitive Symptome (Symptomtagebuch) ──────────────────────────────────
    lines += ["### Kognitive Symptome (IOM 2015 Kriterium 4a)\n"]
    if kognition["n_tage"] > 0:
        lines += [
            f"  Tage mit kognitiven Symptomen: **{kognition['n_tage']}**",
            f"  Dokumentiert: {', '.join(kognition['symptome'])}",
            f"  ⚠ {kognition['caveat']}",
        ]
    else:
        lines += ["  Keine kognitiven Symptome im Analysefenster dokumentiert."]
    lines.append("")

    # ── Syndrom-Symptom-Abgleich (Symptomtagebuch × Syndrom-Profil) ───────────
    lines += [f"### Syndrom-Symptom-Abgleich: {_SYNDROME_CFG['name_de']}\n"]
    if syndrom_symptome["n_gesamt"] == 0:
        lines += ["  Keine Einträge im Symptomtagebuch im Analysefenster.", ""]
    else:
        n_t = syndrom_symptome["n_treffer"]
        n_p = len(syndrom_symptome["syndrom_symptome"])
        pct = round(n_t / n_p * 100) if n_p else 0
        lines += [
            f"  Symptomprofil-Treffer: **{n_t}/{n_p}** Syndrom-Symptome dokumentiert ({pct}%)\n",
        ]
        if syndrom_symptome["treffer"]:
            lines.append("  **Im Tagebuch dokumentiert (Syndrom-relevant):**")
            for sym, n in syndrom_symptome["treffer"]:
                lines.append(f"  - {sym} ({n} Tage)")
        nicht_dok = [s for s in syndrom_symptome["syndrom_symptome"]
                     if s not in {t[0] for t in syndrom_symptome["treffer"]}]
        if nicht_dok:
            lines.append(f"\n  Nicht im Tagebuch: {', '.join(nicht_dok)}")
        lines.append("")

    # ── Symptomtagebuch nach Kategorie ────────────────────────────────────────
    if symptom_kategorien:
        lines += ["", "### Symptomtagebuch nach Kategorie"]
        for cat in _CATEGORY_DISPLAY_ORDER:
            if cat not in symptom_kategorien:
                continue
            stats = symptom_kategorien[cat]
            label = _CATEGORY_DOMAIN_LABEL.get(cat, cat)
            if stats["n_tage"] >= 30:
                icon = "❌"
            elif stats["n_tage"] >= 10:
                icon = "⚠"
            else:
                icon = ""
            top_str = " | ".join(
                f"{s} ({n}d)" for s, n in stats["top"][:5]
            )
            lines.append(
                f"- **{label}**: {stats['n_unique']} Symptome,"
                f" {stats['n_tage']} Tage{(' ' + icon) if icon else ''}"
            )
            if top_str:
                lines.append(f"  → {top_str}")
            if "cognitive_tests" in stats:
                for ct in stats["cognitive_tests"]:
                    lines.append(
                        f"  Kognitiv-Test {ct['test']}:"
                        f" Ø {ct['avg_pct']:.0f}% (n={ct['n']})"
                    )

    # ── Expositions-Prior aus DB ──────────────────────────────────────────────
    if exposure_priors:
        slug = _SYNDROME_CFG["slug"]
        if slug in exposure_priors:
            db_b = exposure_priors[slug]
            lines += [
                "",
                "### Dokumentierte Exposition (aus DB)\n",
                f"  Expositions-Prior für {_SYNDROME_CFG['name_de']}: Score-Boost +{db_b:.1f}",
                "  (Über Expositionsanamnese erfasst; fließt in Differential-Scoring ein)",
                "",
            ]

    # ── ITS-Analyse (optional) ────────────────────────────────────────────────
    if _ITS_AVAILABLE:
        try:
            its_text = _run_its(cutoff=infection_date, d_from=lc_start, d_to=d_to)
            if its_text:
                lines += ["", "### Interrupted Time Series (ITS-Analyse)", its_text]
        except Exception:
            pass  # ITS ist optional, nie blockierend

    return "\n".join(lines)


# ── Plot ─────────────────────────────────────────────────────────────────────

def _plot(data, trend, baseline, infection_date, lc_start, d_to):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        fig, axes = plt.subplots(4, 1, figsize=(15, 14), facecolor="#1A1A2E")
        fig.suptitle(
            f"{_SYNDROME_CFG['name_de']} — Biomarker  |  Inf. {infection_date}  (ab {lc_start})",
            color="#E0E0E0", fontsize=12, fontweight="bold")

        BG, TEXT, RED, BLUE, GREEN, AMBER = (
            "#16213E", "#E0E0E0", "#E84855", "#4A90D9", "#57A773", "#F4A261")
        for ax in axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=TEXT, labelsize=7)
            for s in ax.spines.values():
                s.set_color("#8B8B8B")
        fmt = mdates.DateFormatter("%Y-%m")

        # Subplot 1: Nightly RMSSD mit Baseline-Linie
        ax = axes[0]
        nhrv_dates = sorted(data["nhrv"])
        nhrv_vals  = [data["nhrv"][d]["rmssd"] for d in nhrv_dates]
        nhrv_dts   = [datetime.strptime(d, "%Y-%m-%d") for d in nhrv_dates]
        if nhrv_dts:
            ax.plot(nhrv_dts, nhrv_vals, color=BLUE, lw=1.0, alpha=0.7,
                    label="Nightly RMSSD")
            if len(nhrv_vals) >= 14:
                ma = [sum(nhrv_vals[max(0,i-13):i+1])/len(nhrv_vals[max(0,i-13):i+1])
                      for i in range(len(nhrv_vals))]
                ax.plot(nhrv_dts, ma, color="#74b9ff", lw=1.8, label="14d-Ø")
        ax.axhline(REF["rmssd_min_normal"], color=GREEN, lw=0.8, ls="--",
                   alpha=0.5, label=f"Ref. {REF['rmssd_min_normal']} ms")
        if baseline.get("rmssd"):
            ax.axhline(baseline["rmssd"], color=AMBER, lw=1.2, ls="-.",
                       alpha=0.8, label=f"Baseline {baseline['rmssd']:.0f} ms")
        ax.set_ylabel("RMSSD (ms)", color=BLUE, fontsize=8)
        ax.set_title("Nightly RMSSD — autonome Erholung (mit Prä-Infektions-Baseline)",
                     color=TEXT, fontsize=9)
        ax.legend(fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax.xaxis.set_major_formatter(fmt)

        # Subplot 2: DFA α1
        ax2 = axes[1]
        dfa_dates = sorted(data["dfa"])
        dfa_vals  = [data["dfa"][d]["avg"] for d in dfa_dates if data["dfa"][d]["avg"]]
        dfa_dts   = [datetime.strptime(d, "%Y-%m-%d") for d in dfa_dates
                     if data["dfa"][d]["avg"]]
        if dfa_dts:
            colors = [RED if v < REF["dfa_kritisch"] else AMBER if v < REF["dfa_grenz"]
                      else GREEN for v in dfa_vals]
            ax2.scatter(dfa_dts, dfa_vals, c=colors, s=16, alpha=0.8, zorder=3)
            if len(dfa_vals) >= 7:
                ma = [sum(dfa_vals[max(0,i-6):i+1])/len(dfa_vals[max(0,i-6):i+1])
                      for i in range(len(dfa_vals))]
                ax2.plot(dfa_dts, ma, color="#74b9ff", lw=1.5, label="7d-Ø")
            if baseline.get("dfa"):
                ax2.axhline(baseline["dfa"], color=AMBER, lw=1.0, ls="-.",
                            alpha=0.7, label=f"Baseline {baseline['dfa']:.3f}")
            ax2.axhline(REF["dfa_kritisch"], color=RED, lw=1.0, ls="--",
                        alpha=0.7, label="<0.75 kritisch")
        ax2.set_ylabel("DFA α1", color=TEXT, fontsize=8)
        ax2.set_title("DFA α1 — Belastungstoleranz-Marker (Gronwald 2023)",
                      color=TEXT, fontsize=9)
        ax2.legend(fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax2.xaxis.set_major_formatter(fmt)

        # Subplot 3: MET-Minuten mit Baseline
        ax3 = axes[2]
        met_dates = sorted(d for d in data["activity"] if "met_minutes" in data["activity"][d])
        met_vals  = [data["activity"][d]["met_minutes"] for d in met_dates]
        met_dts   = [datetime.strptime(d, "%Y-%m-%d") for d in met_dates]
        if met_dts:
            bar_colors = [RED if v < 100 else AMBER if v < 200 else GREEN for v in met_vals]
            ax3.bar(met_dts, met_vals, color=bar_colors, alpha=0.7, width=0.8)
        if baseline.get("met"):
            ax3.axhline(baseline["met"], color=AMBER, lw=1.2, ls="-.",
                        alpha=0.8, label=f"Baseline {baseline['met']:.0f} MET·min")
        ax3.axhline(200, color=RED, lw=0.8, ls="--", alpha=0.5, label="200 MET·min")
        ax3.set_ylabel("MET·min/Tag", color=TEXT, fontsize=8)
        ax3.set_title("Aktivitätstoleranz: MET-Minuten/Tag (rot=<100, orange=<200)",
                      color=TEXT, fontsize=9)
        ax3.legend(fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax3.xaxis.set_major_formatter(fmt)
        ax3.tick_params(axis="x", colors=TEXT)

        # Subplot 4: Quartals-Trend (RMSSD + Crash-Rate)
        ax4 = axes[3]
        ax4r = ax4.twinx()
        ax4r.set_facecolor(BG)
        if trend:
            q_labels  = [q["label"] for q in trend if q["rmssd"]]
            q_rmssd   = [q["rmssd"] for q in trend if q["rmssd"]]
            q_crashes = [q["crash_pct"] for q in trend
                         if q["crash_pct"] is not None]
            q_x = list(range(len(q_labels)))
            if q_x and q_rmssd:
                ax4.bar(q_x, q_rmssd, color=BLUE, alpha=0.6, label="RMSSD (ms)")
                if baseline.get("rmssd"):
                    ax4.axhline(baseline["rmssd"], color=AMBER, lw=1.0, ls="-.",
                                alpha=0.7, label=f"Baseline {baseline['rmssd']:.0f}")
                ax4.set_xticks(q_x)
                ax4.set_xticklabels(q_labels, fontsize=6, color=TEXT, rotation=30)
            crash_x = list(range(len(q_crashes)))
            if crash_x and q_crashes:
                ax4r.plot(crash_x, q_crashes, color=RED, lw=1.5, marker="o",
                          ms=4, label="HRV-Crash% (rechts)")
                ax4r.axhline(20, color=RED, lw=0.7, ls="--", alpha=0.4)
            ax4.set_ylabel("RMSSD (ms)", color=BLUE, fontsize=8)
            ax4.tick_params(axis="y", labelcolor=BLUE)
            ax4r.set_ylabel("HRV-Crash-Rate (%)", color=RED, fontsize=8)
            ax4r.tick_params(axis="y", labelcolor=RED)
        ax4.set_title("Quartalsverlauf: RMSSD (Balken) & HRV-Crash-Rate (Linie)",
                      color=TEXT, fontsize=9)
        h1, l1 = ax4.get_legend_handles_labels()
        h2, l2 = ax4r.get_legend_handles_labels()
        ax4.legend(h1 + h2, l1 + l2, fontsize=7, facecolor=BG, labelcolor=TEXT)

        fig.autofmt_xdate(rotation=30)
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        p = OUT_DIR / f"{_SYNDROME_CFG['slug']}_diagnosis_{ts}.png"
        fig.savefig(str(p), dpi=140, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {p}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


# ── LLM & Speichern ──────────────────────────────────────────────────────────

def _build_llm_input(autonome: dict, pem: dict, kardio: dict, schlaf: dict,
                     aktivitaet: dict, respiration: dict, trend: list,
                     baseline: dict, kognition: dict, infection_date: str,
                     lc_start: str, d_to: str) -> str:
    """Erstellt LLM-Eingabe ausschließlich aus berechneten Domänenwerten."""
    lines = [
        f"## Berechnete Befunde — {_SYNDROME_CFG['name_de']} Diagnostik",
        f"Infektionsdatum: {infection_date} | Analysefenster: {lc_start} – {d_to}",
        "",
        "### Autonome Dysregulation",
    ]

    if autonome["avg_rhr"] is not None:
        lines.append(f"- RHR: {autonome['avg_rhr']:.0f} bpm (n={autonome['n_rhr']})")
    if autonome["avg_nhrv"] is not None:
        base_str = (f" (Baseline: {baseline['rmssd']:.0f} ms)"
                    if baseline.get("rmssd") else "")
        delta_str = (f", Delta: {autonome['rmssd_delta_pct']:+.0f}%"
                     if autonome["rmssd_delta_pct"] is not None else "")
        lines.append(f"- Nightly RMSSD: {autonome['avg_nhrv']:.0f} ms"
                     f"{base_str}{delta_str} (n={autonome['n_nhrv']})")
    if autonome["avg_dfa"] is not None:
        lines.append(f"- DFA α1: {autonome['avg_dfa']:.3f}"
                     f" ({_f(autonome['pct_dfa_krit'], '.0f')}% der Fenster <0.75 kritisch)")
    if autonome["avg_lfhf"] is not None:
        lines.append(f"- LF/HF-Ratio: {autonome['avg_lfhf']:.2f}")
    if autonome["avg_ortho_delta"] is not None:
        d = autonome["avg_ortho_delta"]
        pots_note = ("POTS-Kriterium erfüllt" if d >= REF["pots_delta"]
                     else "orthostatische Intoleranz, kein formales POTS" if d >= 20
                     else "normal")
        lines.append(f"- Orthostase ΔHR: {d:.0f} bpm ({pots_note})")
    else:
        lines.append("- Orthostase: keine Messdaten")

    lines += ["", "### Post-Exertionelle Malaise (PEM)"]
    if pem["pct_crashes"] is not None:
        lines.append(f"- HRV-Crash-Rate (≤−10%): {pem['pct_crashes']:.1f}%"
                     f" ({pem['n_crashes']} von {pem['n_tage']} Tagen)")
    if pem["avg_hrv_delta"] is not None:
        lines.append(f"- Ø HRV-Delta Folgetag: {pem['avg_hrv_delta']:+.1f}%"
                     f" | Schlechtester: {_f(pem['worst_delta'], '.0f')}%")
    lines.append(f"- Formale PEM-Events (1σ): {pem['pem_events']}")

    lines += ["", "### Kardiovaskulär (AF Evidence Score)"]
    lines.append(f"- Analysierte Tage: {kardio['af_gesamt']}"
                 f" | Level ≥ low: {kardio['af_tage']} Tage"
                 f" | Ø Score: {_f(kardio['avg_af_score'], '.1f')}")
    lvl = kardio.get("by_level", {})
    for k in ("none", "low", "moderate", "high", "critical"):
        if lvl.get(k, 0) > 0:
            lines.append(f"  - {k}: {lvl[k]} Tage")
    lines.append(f"- Tage mit direkter Evidenz (high/critical): {kardio['high_af_tage']}")

    lines += ["", "### Schlaf & Erholung"]
    if schlaf["avg_deep_pct"] is not None:
        lines.append(f"- Tiefschlaf: {schlaf['avg_deep_pct']:.1f}%"
                     f" ({_f(schlaf['pct_low_deep'], '.0f')}% der Nächte <15%)"
                     f" (n={schlaf['n_schlaefe']})")
    if schlaf["avg_efficiency"] is not None:
        lines.append(f"- Schlafeffizienz: {schlaf['avg_efficiency']:.0f}%")
    if schlaf["avg_nhrv_dev"] is not None:
        lines.append(f"- Nightly HRV vs. Baseline: Ø {schlaf['avg_nhrv_dev']:+.1f}%"
                     f" ({_f(schlaf['pct_nhrv_below_base'], '.0f')}%"
                     f" der Nächte >10% unter Baseline)")

    lines += ["", "### Aktivitätstoleranz"]
    if aktivitaet["avg_met"] is not None:
        base_str = (f" (Baseline: {baseline['met']:.0f} MET·min)"
                    if baseline.get("met") else "")
        delta_str = (f", Delta: {aktivitaet['met_delta_pct']:+.0f}%"
                     if aktivitaet["met_delta_pct"] is not None else "")
        lines.append(f"- MET-Minuten/Tag: {aktivitaet['avg_met']:.0f}"
                     f"{base_str}{delta_str} (n={aktivitaet['n_tage']})")
    if aktivitaet["pct_unter_200met"] is not None:
        lines.append(f"- Tage <200 MET·min: {aktivitaet['pct_unter_200met']:.0f}%")

    lines += ["", "### Respiration (SpO2)"]
    if respiration["n_tage"] > 0:
        lines.append(f"- SpO2 Ø: {_f(respiration['avg_spo2'], '.1f')}%"
                     f" | Minimum: {_f(respiration['min_spo2'])}%"
                     f" (n={respiration['n_tage']})")
        if respiration["pct_unter_97"] is not None:
            lines.append(f"- <97%: {respiration['pct_unter_97']:.0f}% der Tage"
                         f" | <95%: {_f(respiration['pct_unter_95'], '.0f')}% der Tage")
    else:
        lines.append("- Keine SpO2-Daten im Analysefenster")

    if trend:
        first_nhrv_date = next((q["first_nhrv"] for q in trend if q.get("first_nhrv")), None)
        lines += ["", "### Quartalsverlauf (RMSSD / MET / HRV-Crash-Rate)",
                  f"Nacht-RMSSD (polar_nightly_hrv) ab {first_nhrv_date[:7] if first_nhrv_date else 'n/a'}."
                  " Ältere Quartale ohne Nacht-HRV zeigen RMSSD=— (H10-Tagessessions existieren,"
                  " werden hier nicht ausgewertet)."]
        for q in trend:
            parts = [q["label"]]
            if q["rmssd"] is not None:
                parts.append(f"RMSSD={q['rmssd']:.0f} ms (Nacht)")
            else:
                parts.append("RMSSD=— (keine Nacht-HRV)")
            if q["met"] is not None:
                parts.append(f"MET={q['met']:.0f}")
            if q["crash_pct"] is not None:
                parts.append(f"Crash={q['crash_pct']:.0f}%")
            lines.append("- " + ", ".join(parts) + f" (n={q['n_nhrv']})")

    # ── Berechnete klinische Signale ──────────────────────────────────────────
    # Schwellenverletzungen und Datenlücken — abgeleitet aus den Messwerten,
    # nicht hardcodiert. Basis für LLM-Interpretation.
    signale = []

    # SpO2-Signale
    if respiration["n_tage"] > 0:
        if respiration["min_spo2"] is not None and respiration["min_spo2"] < 90:
            signale.append(f"SpO2-Minimum {_f(respiration['min_spo2'])}% (<90%)"
                           " — nächtliche Hypoventilation möglich")
        if respiration["pct_unter_95"] is not None and respiration["pct_unter_95"] > 30:
            signale.append(f"{_f(respiration['pct_unter_95'], '.0f')}% der Nächte"
                           " SpO2 <95% — persistente Sättigungsabfälle")
    else:
        signale.append("SpO2: keine Messdaten im Analysefenster")

    # AF-Signal
    if kardio["high_af_tage"] > 0:
        signale.append(f"AF-Score HIGH/VERY_HIGH an {kardio['high_af_tage']} Tagen"
                       " — kardiovaskuläre Abklärung indiziert")
    elif kardio["af_tage"] > kardio["af_gesamt"] * 0.5 and kardio["af_gesamt"] > 0:
        signale.append(f"AF-Screening positiv an {kardio['af_tage']} von"
                       f" {kardio['af_gesamt']} Tagen (>{50}%) — Abklärung empfohlen")

    # Orthostase
    if autonome["avg_ortho_delta"] is None:
        signale.append("Keine Orthostase-Messdaten in der DB (Schellong bisher nicht dokumentiert)")
    elif autonome["avg_ortho_delta"] >= REF["pots_delta"]:
        signale.append(f"POTS-Kriterium erfüllt: ΔHR {autonome['avg_ortho_delta']:.0f} bpm"
                       " ≥ 30 bpm (Raj 2021)")
    elif autonome["avg_ortho_delta"] >= 20:
        signale.append(f"Orthostatische Intoleranz: ΔHR {autonome['avg_ortho_delta']:.0f} bpm"
                       " (kein formales POTS <30 bpm)")

    # RHR persistiert erhöht
    if autonome["avg_rhr"] is not None and autonome["avg_rhr"] > REF["rhr_normal_max"]:
        signale.append(f"RHR persistiert erhöht: Ø {autonome['avg_rhr']:.0f} bpm"
                       f" (Referenz ≤{REF['rhr_normal_max']} bpm)")

    # PEM-Schwelle
    if pem["pct_crashes"] is not None and pem["pct_crashes"] > 20:
        signale.append(f"HRV-Crash-Rate {pem['pct_crashes']:.0f}% — PEM-Muster prominent")

    # Fehlende Baseline-Daten
    if not baseline.get("rmssd"):
        signale.append("Prä-Infektions-RMSSD-Baseline: nicht in der DB")
    if not baseline.get("met"):
        signale.append("Prä-Infektions-MET-Baseline: nicht in der DB")
    if not baseline.get("dfa"):
        signale.append("Prä-Infektions-DFA-Baseline: nicht in der DB")

    # Kognitive Symptome
    lines += ["", "### Kognitive Symptome (IOM 2015 Kriterium 4a)"]
    if kognition["n_tage"] > 0:
        lines.append(f"- {kognition['n_tage']} Tage dokumentiert:"
                     f" {', '.join(kognition['symptome'])}")
        lines.append(f"- Caveat: {kognition['caveat']}")
    else:
        lines.append("- Keine kognitiven Symptome dokumentiert")

    if signale:
        lines += ["", "### Berechnete klinische Signale & Datenlücken"]
        for s in signale:
            lines.append(f"- {s}")

    return "\n".join(lines)


def _run_llm(autonome: dict, pem: dict, kardio: dict, schlaf: dict,
             aktivitaet: dict, respiration: dict, trend: list,
             baseline: dict, kognition: dict, infection_date: str,
             lc_start: str, d_to: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        llm_input = _build_llm_input(
            autonome, pem, kardio, schlaf, aktivitaet, respiration,
            trend, baseline, kognition, infection_date, lc_start, d_to)
        return call_llm(llm_input, system=_SYNDROME_CFG["system_prompt"], max_tokens=1400)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text, infection_date):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"{_SYNDROME_CFG['slug']}_diagnosis_{ts}.md"
    content = f"# {_SYNDROME_CFG['name_de']} — Diagnostik-Score  |  Inf. {infection_date}\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ── Main ─────────────────────────────────────────────────────────────────────

def _resolve_infection_events(args_dates: list[str] | None) -> list[dict]:
    """Gibt Liste von {date, label, estimated} zurück.

    Priorität:
    1. --infection-date explizit übergeben (mehrere möglich)
    2. Alle infection/reinfection-Ereignisse aus health_config.json
    3. Legacy cfg.infection_date
    """
    if args_dates:
        # Explizit übergeben: Datum + optionales Label via "DATUM:LABEL"
        result = []
        for entry in args_dates:
            if ":" in entry:
                date_part, label = entry.split(":", 1)
            else:
                date_part, label = entry, None
            # Config-Ereignisse für dieses Datum suchen (für Namen)
            cfg_event = next(
                (e for e in _cfg.events if e.get("date") == date_part), None)
            result.append({
                "date":      date_part,
                "label":     label or (cfg_event["name"] if cfg_event else date_part),
                "estimated": False,
            })
        return result

    # Aus Config: alle Infektions-/Reinfektions-Ereignisse
    events = _cfg.events_of_type("infection", "reinfection")
    if events:
        return [{"date": e["date"], "label": e.get("name", e["date"]),
                 "estimated": e.get("estimated", False)} for e in events]

    # Legacy-Fallback
    if _cfg.infection_date:
        return [{"date": _cfg.infection_date, "label": _cfg.infection_date,
                 "estimated": False}]

    return []


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=t("Post-Infektions-Syndrom Multi-Domain Diagnose-Score",
                      "Post-infectious syndrome multi-domain diagnostic score"))
    parser.add_argument("--infection-date", dest="infection_dates", nargs="*",
                        metavar="DATUM[:LABEL]",
                        help=t(
                            "Ein oder mehrere Infektionsdaten (YYYY-MM-DD), optional mit Label "
                            "(z.B. 'YYYY-MM-DD:Pathogen'). Ohne Angabe: alle infection/reinfection-"
                            "Ereignisse aus health_config.json. Für geschätzte Daten einfach "
                            "Symptom-Onset-Datum verwenden.",
                            "One or more infection dates (YYYY-MM-DD), optionally with label "
                            "(e.g. 'YYYY-MM-DD:Pathogen'). If omitted: all infection/reinfection "
                            "events from health_config.json."))
    _all_syndromes = list(SYNDROME_CONFIG.keys())
    _choices = _all_syndromes + ["auto"]
    parser.add_argument("--syndrome", nargs="+", choices=_choices,
                        default=["generic"],
                        metavar="SYNDROME",
                        help=t(
                            f"Ein oder mehrere Syndrome, oder 'auto' für automatische Vermutung. "
                            f"Standard: generic. Verfügbar: {', '.join(_all_syndromes)}, auto.",
                            f"One or more syndromes, or 'auto' for automatic differential. "
                            f"Default: generic. Available: {', '.join(_all_syndromes)}, auto."))
    parser.add_argument("--from", dest="date_from", default=None,
                        metavar="DATE",
                        help=t(
                            "Startdatum (YYYY-MM-DD) für die Analyse",
                            "Start date (YYYY-MM-DD) for analysis"))
    parser.add_argument("--onset", dest="onset_override", default=None,
                        metavar="DATE",
                        help=t(
                            "Direkter Analyse-Start (YYYY-MM-DD) ohne Lag — für undokumentierte "
                            "Infektionen (Influenza, Erkältung) wo nur Symptom-Onset bekannt.",
                            "Direct analysis start date (YYYY-MM-DD) bypassing lag — for "
                            "undocumented infections where only symptom onset is known."))
    parser.add_argument("--to",     dest="date_to",  default=today)
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    # Use --from as fallback for --onset if --onset is not provided
    if args.date_from and not args.onset_override:
        args.onset_override = args.date_from

    infection_events = _resolve_infection_events(args.infection_dates)
    if not infection_events:
        sys.exit(t(
            "Fehler: Kein Infektionsdatum gefunden. "
            "--infection-date YYYY-MM-DD übergeben oder "
            "clinical.events in ~/.config/kyoro/health_config.json befüllen.",
            "Error: No infection date found. "
            "Pass --infection-date YYYY-MM-DD or "
            "set clinical.events in ~/.config/kyoro/health_config.json.",
        ))

    global _SYNDROME_CFG

    for ev in infection_events:
        infection_date = ev["date"]
        event_label    = ev["label"]
        estimated_note = "  ⚠ Datum geschätzt (Symptom-Onset)" if ev["estimated"] else ""

        print(f"\n{'#'*60}")
        print(f"Ereignis: {event_label}  ({infection_date}){estimated_note}")
        print(f"{'#'*60}")

        # ── Auto-Modus ────────────────────────────────────────────────────────
        if "auto" in args.syndrome:
            _SYNDROME_CFG = SYNDROME_CONFIG["generic"]
            auto_start = args.onset_override or _lc_start(infection_date)
            print(f"\n{'='*60}")
            print(f"Auto-Differenzialdiagnose  |  {event_label}")
            print(f"Fenster: {auto_start} – {args.date_to}")
            print(f"DB: {_cfg.db_path}\n")

            conn = open_db()
            auto_baseline = load_baseline(conn, infection_date)
            auto_data     = load_all_data(conn, auto_start, args.date_to)
            auto_rmssd_bl = get_baseline(conn, OWN_PERSON_ID, "hrv_rmssd")
            auto_resp     = bewerte_respiration(auto_data)
            auto_kardio   = bewerte_kardio(auto_data)
            auto_autonome = bewerte_autonome(auto_data, auto_baseline, personal_bl=auto_rmssd_bl)
            auto_akt      = bewerte_aktivitaet(auto_data, auto_baseline)
            auto_symptom_kat = bewerte_symptom_kategorien(conn, auto_start, args.date_to)
            ranking       = vermute_syndrome(conn, auto_start, args.date_to,
                                             respiration=auto_resp,
                                             kardio=auto_kardio,
                                             autonome=auto_autonome,
                                             aktivitaet=auto_akt,
                                             symptom_kategorien=auto_symptom_kat,
                                             exposure_priors=load_exposure_priors(conn, auto_start))

            vbericht = build_differential_report(ranking, infection_date,
                                                   auto_start, args.date_to,
                                                   conn=conn)
            conn.close()
            print("\n" + vbericht)

            OUT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            slug_label = event_label.lower().replace(" ", "_")[:20]
            out = OUT_DIR / f"auto_differential_{slug_label}_{ts}.md"
            out.write_text(
                f"# Auto-Differenzialdiagnose — {event_label}\n\n{vbericht}\n",
                encoding="utf-8")
            print(f"Bericht: {out}")

        syndromes_to_run = [s for s in args.syndrome if s != "auto"]
        if not syndromes_to_run:
            continue

        baseline = None
        for syndrome in syndromes_to_run:
            _SYNDROME_CFG = SYNDROME_CONFIG[syndrome]

            lc_start = args.onset_override or _lc_start(infection_date)
            onset_note = "  (--onset, kein Lag)" if args.onset_override else \
                         f"  (≥{_SYNDROME_CFG['lag_weeks']} Wochen post-akut)"
            print(f"\n{'='*60}")
            print(f"{_SYNDROME_CFG['name_de']} — Diagnose-Score")
            print(f"Ereignis:    {event_label}  ({infection_date}){estimated_note}")
            print(f"Fenster:     {lc_start} – {args.date_to}{onset_note}")
            print(f"DB:          {_cfg.db_path}\n")

            conn = open_db()
            data             = load_all_data(conn, lc_start, args.date_to)
            if baseline is None:
                baseline     = load_baseline(conn, infection_date)
            personal_rmssd_bl = get_baseline(conn, OWN_PERSON_ID, "hrv_rmssd")
            kognition        = load_symptoms_kognitiv(conn, lc_start, args.date_to)
            syndrom_symptome = load_symptoms_syndrom(conn, lc_start, args.date_to)
            symptom_kategorien = bewerte_symptom_kategorien(conn, lc_start, args.date_to)
            exposure_priors    = load_exposure_priors(conn, lc_start)
            conn.close()

            autonome    = bewerte_autonome(data, baseline, personal_bl=personal_rmssd_bl)
            pem         = bewerte_pem(data)
            kardio      = bewerte_kardio(data)
            schlaf      = bewerte_schlaf(data)
            aktivitaet  = bewerte_aktivitaet(data, baseline)
            respiration = bewerte_respiration(data)
            trend       = compute_trend(data, lc_start, args.date_to)

            report = build_report(
                data, autonome, pem, kardio, schlaf, aktivitaet, respiration,
                trend, baseline, kognition, syndrom_symptome,
                infection_date, lc_start, args.date_to,
                symptom_kategorien=symptom_kategorien,
                exposure_priors=exposure_priors)
            print("\n" + report)

            if args.plot:
                _plot(data, trend, baseline, infection_date, lc_start, args.date_to)

            llm_text = "" if args.no_llm else _run_llm(
                autonome, pem, kardio, schlaf, aktivitaet, respiration,
                trend, baseline, kognition, infection_date, lc_start, args.date_to)
        _save(report, llm_text, infection_date)


if __name__ == "__main__":
    main()
