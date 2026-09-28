#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Body composition & Weightsverlauf

Kombiniert Weight, Körperfettanteil, Muskelmasse and Taillenmaß
aus FDDB, Apple Health and Beurer über mehrere years.

Usage:
  python analyse_body_composition.py --plot
  python analyse_body_composition.py --from YYYY-MM-DD --plot
  python analyse_body_composition.py --plot --no-llm

@tier        heuristic
@purpose.de  Analysiert Gewicht, Körperfettanteil, Muskelmasse und Taillenmaß aus FDDB,
             Apple Health und Beurer über mehrere Jahre sowie Zusammenhänge mit Blutzucker
             und Trainingsdaten.
@purpose.en  Analyses weight, body fat percentage, muscle mass and waist circumference from
             FDDB, Apple Health and Beurer over multiple years, plus associations with blood
             glucose and training data.
@method.de   Deskriptive Statistik und visuelle Zeitreihe; keine formal validierten Körperfett-
             Referenzbereiche implementiert. Beurer-Bioimpedanz-Segmentalwerte werden
             dargestellt ohne Gerätekalibrierungsprüfung.
@method.en   Descriptive statistics and visual time series; no formally validated body fat
             reference ranges implemented. Beurer bioimpedance segmental values are displayed
             without device calibration verification.
@scoring     BMI: Untergewicht <18,5 / Normal 18,5–24,9 / Übergewicht 25–29,9 / Adipositas ≥30
             WHR: erhöht ≥0,90 (Personengruppen) / ≥0,85 (Personengruppen)
             WHtR: erhöht ≥0,50
             HbA1c: erhöht >5,7%  |  Nüchternglukose: erhöht ≥6,1 mmol/L
             Basis: BMI/WHR = WHO (doi:https://iris.who.int/handle/10665/42330), WHtR = Ashwell & Gibson 2016
             (doi:10.1136/bmjopen-2015-010159), HbA1c = ADA 2023, IFG = WHO 2006.
             Viszeralfett >13, Segmentasymmetrie-Schwellen: projektintern (Beurer-Skala).
@limits.de   Heuristische Methode: Validierte Komponenten: BMI (WHO 2000), WHR (WHO 2008), WHtR ≥ 0,50 (Ashwell &
             Gibson 2016, doi:10.1136/bmjopen-2015-010159), HbA1c > 5,7% (ADA 2023),
             Nüchternglukose ≥ 6,1 mmol/L (WHO 2006 IFG).
             Heuristische Komponenten: Viszeralfett-Index > 13 (Beurer BF990-proprietär, nicht
             auf andere Geräte übertragbar), Segmentasymmetrie-Schwellen (2,0% Fett / 1,5%
             Muskel), Stoffwechselalter (Beurer-proprietär).
             Bioimpedanz-Messwerte variieren stark mit Hydrationsstatus. Mehrmessgeräte
             (FDDB, Apple, Beurer) können systematisch abweichen. Keine Referenzpopulation.
             Glukose-Durchschnitt enthält ggf. auch postprandiale Werte — kein Nüchternwert.
@limits.en   Heuristic method: Validated components: BMI (WHO 2000), WHR (WHO 2008), WHtR ≥ 0.50 (Ashwell &
             Gibson 2016, doi:10.1136/bmjopen-2015-010159), HbA1c > 5.7% (ADA 2023),
             fasting glucose ≥ 6.1 mmol/L (WHO 2006 IFG).
             Heuristic components: visceral fat index > 13 (Beurer BF990-proprietary, not
             transferable to other devices), segmental asymmetry thresholds (2.0% fat /
             1.5% muscle), metabolic time period (Beurer-proprietary).
             Bioimpedance readings vary greatly with hydration status. Multiple devices
             (FDDB, Apple, Beurer) may show systematic offsets. No reference population.
             Glucose average may include postprandial values — not a fasting-only measure.
@refs        WHO (2000). Obesity: preventing and managing the global epidemic. Technical
             Report Series 894. doi:https://iris.who.int/handle/10665/42330
             WHO (2008). Waist circumference and waist-hip ratio. WHO Expert Consultation.
             Ashwell M, Gibson S (2016). Waist-to-height ratio as an indicator of 'early
             health risk'. doi:10.1136/bmjopen-2015-010159
             ADA (2023). Standards of Care in Diabetes — Classification and assessment.
             doi:10.2337/dc23-S002
             WHO (2006). Definition and assessment of diabetes mellitus and intermediate
             hyperglycaemia. ISBN 978 92 4 159493 6

@relevance.de  Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit
@relevance.en  Enables metabolic analysis, essential for metabolic health
@reads       body_composition (incl. source='renpho_csv'), measurements, blood_glucose,
             nutrition_daily, sessions, session_metrics
@writes      analyses/metabolic/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_body_composition.py
    python analyse_body_composition.py --help
    python analyse_body_composition.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH   = _cfg.db_path
OUT_DIR   = _cfg.analyses_dir / "metabolic"
HEIGHT_CM = _cfg.height_cm
GENDER    = _cfg.gender
AGE       = _cfg.age

from modules.prompts.analysis_metabolic import (
    SYSTEM_PROMPT_ANALYSE_BODY_COMPOSITION_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_BODY_COMPOSITION_EN as SYSTEM_PROMPT_EN,
)


def _norm_pct(v):
    """Normalisiert einen Prozentwert auf die Skala 0..100.

    Apple Health liefert manche Prozent-Metriken als Bruchwert 0..1 statt
    0..100 (verifiziert: measurements.metric='body_fat', source_app=
    'apple_health' liegt zwischen 0,217 und 0,34, n=1356) — ohne
    Normalisierung erscheint daraus im Bericht z. B. "0,2 %" statt "~28 %".
    Andere Quellen (Beurer via body_composition) liefern bereits 0..100.
    Kein realer Koerperfett-/Muskel-/Wasseranteil liegt <=1.5, daher ist die
    Fallunterscheidung eindeutig. Analog zu _PCT in compute_clinical.py.
    """
    if v is None:
        return None
    return v * 100.0 if v <= 1.5 else v


def load_data(conn, d_from, d_to, person):
    # v2 schema: fddb_weight → body_composition (source='fddb')
    # keep same tuple shape (date, weight, fat, water, None, None) for compat with report/plot
    fddb = conn.execute("""
        SELECT date, weight_kg, body_fat_pct, water_pct, waist_cm, hip_cm
        FROM body_composition
        WHERE source = 'fddb' AND date >= ? AND date <= ? ORDER BY date
    """, (d_from, d_to)).fetchall()

    # v2 schema: apple_records → measurements (source_app='apple_health')
    apple_mass = conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'body_mass' AND source_app = 'apple_health'
          AND date >= ? AND date <= ? AND value IS NOT NULL
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()

    apple_fat = conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'body_fat' AND source_app = 'apple_health'
          AND date >= ? AND date <= ? AND value IS NOT NULL
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()
    apple_fat = [(d, _norm_pct(v)) for d, v in apple_fat]

    apple_lean = conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'lean_body_mass' AND source_app = 'apple_health'
          AND date >= ? AND date <= ? AND value IS NOT NULL
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()

    # v2 schema: beurer_weight → body_composition (source LIKE 'beurer%')
    beurer = conn.execute("""
        SELECT date, weight_kg, muscle_pct, water_pct, body_fat_pct,
               visceral_fat, fat_visceral_pct
        FROM body_composition
        WHERE source LIKE 'beurer%' AND date >= ? AND date <= ? ORDER BY date
    """, (d_from, d_to)).fetchall()
    # Spalten 2,3,4,6 sind Prozentwerte (muscle_pct, water_pct, body_fat_pct,
    # fat_visceral_pct); Spalte 5 (visceral_fat) ist die Beurer-Indexskala 1..59,
    # kein Prozentwert — bewusst nicht normalisiert.
    beurer = [(d, w, _norm_pct(mus), _norm_pct(wat), _norm_pct(fat), vf, _norm_pct(fvp))
              for d, w, mus, wat, fat, vf, fvp in beurer]

    segmental = conn.execute("""
        SELECT date,
               fat_arm_left, fat_arm_right, fat_leg_left, fat_leg_right, fat_trunk,
               muscle_arm_left, muscle_arm_right, muscle_leg_left, muscle_leg_right, muscle_trunk,
               fat_visceral_pct, visceral_fat, metabolic_age,
               soft_lean_mass_kg, lean_body_mass_kg, protein_pct, muscle_mass_organ_kg
        FROM body_composition
        WHERE date >= ? AND date <= ?
          AND (fat_arm_left IS NOT NULL OR muscle_arm_left IS NOT NULL)
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    # Indizes 1..10 (Segment-Fett/-Muskel-%) und 11 (fat_visceral_pct) sowie 16
    # (protein_pct) sind Prozentwerte; 12 (visceral_fat) ist die Indexskala,
    # 13 (metabolic_age) Jahre, 14/15/17 kg — bewusst nicht normalisiert.
    _SEG_PCT_IDX = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16)
    segmental = [
        tuple(_norm_pct(v) if i in _SEG_PCT_IDX else v for i, v in enumerate(r))
        for r in segmental
    ]

    # person-Filter zwingend: blood_glucose ist die einzige Tabelle dieser DB mit
    # Werten mehrerer Personen — ein Blutzuckermessgeraet wird im Haushalt geteilt,
    # dieselbe device_id traegt daher fremde Messwerte. Ohne Filter erscheinen sie
    # im Bericht der auswertenden Person. Die uebrigen Abfragen dieser Funktion
    # lesen Tabellen mit nur einer Person und bleiben bewusst unveraendert.
    glucose = conn.execute("""
        SELECT date, glucose_mmol, glucose_mgdl, meal_context, hba1c
        FROM blood_glucose
        WHERE date >= ? AND date <= ? AND person = ? ORDER BY ts
    """, (d_from, d_to, person)).fetchall()

    nutrition = conn.execute("""
        SELECT AVG(kcal), AVG(protein_g), AVG(carbs_g), AVG(fat_g),
               AVG(fiber_g), COUNT(*), MIN(date), MAX(date)
        FROM nutrition_daily
        WHERE date >= ? AND date <= ?
    """, (d_from, d_to)).fetchone()

    sport = conn.execute("""
        SELECT s.sport, COUNT(*) AS cnt,
               ROUND(AVG(sm_d.value)/60) AS avg_min,
               ROUND(SUM(sm_d.value)/3600, 1) AS total_h,
               ROUND(AVG(sm_c.value)) AS avg_kcal
        FROM sessions s
        LEFT JOIN session_metrics sm_d ON s.id = sm_d.session_id AND sm_d.metric = 'duration_s'
        LEFT JOIN session_metrics sm_c ON s.id = sm_c.session_id AND sm_c.metric = 'calories'
        WHERE s.type = 'training' AND s.date >= ? AND s.date <= ?
        GROUP BY s.sport ORDER BY cnt DESC
    """, (d_from, d_to)).fetchall()

    # Die Maßband-Spalten stehen nicht in create_schema.py — import_renpho_tape.py
    # legt sie beim ersten Import per ALTER TABLE an (siehe dort _ensure_columns).
    # Ohne RENPHO-Maßband existieren sie also nie, und ein ungeprüftes SELECT
    # scheitert mit "no such column: neck_cm" statt den Abschnitt auszulassen.
    _RENPHO_COLS = ["date", "neck_cm", "shoulder_cm", "upper_arm_left_cm",
                    "upper_arm_right_cm", "chest_cm", "waist_cm", "abdomen_cm",
                    "hip_cm", "thigh_left_cm", "thigh_right_cm", "calf_left_cm",
                    "calf_right_cm", "waist_to_hip_ratio"]
    _have = {r[1] for r in conn.execute("PRAGMA table_info(body_composition)")}
    if set(_RENPHO_COLS) <= _have:
        renpho = conn.execute(f"""
            SELECT {", ".join(_RENPHO_COLS)}
            FROM body_composition
            WHERE source = 'renpho_csv' AND date >= ? AND date <= ?
            ORDER BY date
        """, (d_from, d_to)).fetchall()
    else:
        renpho = []

    return fddb, apple_mass, apple_fat, apple_lean, beurer, nutrition, sport, glucose, segmental, renpho


def build_report(fddb, apple_mass, apple_fat, apple_lean, beurer, nutrition, sport, glucose, segmental, renpho, d_from, d_to):
    if not fddb and not apple_mass and not apple_fat:
        return "No Body compositions-Daten im angefragten Time range."

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    # Merge weight sources with priority: Beurer > FDDB (beides echte Wiegungen
    # aus body_composition/manuellen Eintraegen). Apple Health (source_app=
    # 'apple_health', measurements.metric='body_mass') ist hier bewusst
    # AUSGESCHLOSSEN: die Reihe ist verifiziert linear interpoliert, nicht aus
    # echten Wiegungen — z. B. ein Segment von 996 aufeinanderfolgenden Tagen
    # mit exakt identischem Tagesschritt (-0,001 kg/Tag), was bei echten
    # Wiegungen ausgeschlossen ist. Sie wuerde Trend/BMI/aktuelles Gewicht
    # verfaelschen und wird stattdessen separat mit Hinweis ausgewiesen (siehe
    # Abschnitt "Gewicht — Apple Health").
    _seen_dates: set[str] = set()
    all_weight: list[tuple[str, float]] = []
    for source_rows in [beurer, fddb]:
        for r in source_rows:
            if r[1] and r[0] not in _seen_dates:
                all_weight.append((r[0], r[1]))
                _seen_dates.add(r[0])
    all_weight.sort()

    def bmi(weight_kg):
        if not HEIGHT_CM:
            return None
        h = HEIGHT_CM / 100
        return round(weight_kg / (h * h), 1)

    def bmi_kategorie(b):
        # WHO 2000: Klassifikation des Körpergewichts nach BMI
        # doi:10.1002/j.1550-8528.2000.tb00007.x (International Obesity Task Force)
        if b is None:
            return ""
        if b < 18.5: return "Untergewicht ⚠"
        if b < 25.0: return "Normalgewicht ✓"
        if b < 30.0: return "Übergewicht ⚠"
        return "Adipositas ⚠⚠"

    lines = [f"## Body composition — {d_from} bis {d_to}\n"]
    if HEIGHT_CM or GENDER or AGE:
        meta = []
        if HEIGHT_CM: meta.append(f"Körpergröße: {HEIGHT_CM} cm")
        if GENDER:    meta.append(f"Geschlecht: {GENDER}")
        if AGE:       meta.append(f"Alter: {AGE} Jahre")
        lines.append("  " + "  |  ".join(meta) + "\n")

    if all_weight:
        weights = [w for _, w in all_weight]
        lines += [
            "### Weight\n",
            f"  Messungen: {len(all_weight)}  |  Time range: {all_weight[0][0]} – {all_weight[-1][0]}",
            f"  Ø: **{avg(weights)} kg**  |  Min: {min(weights):.1f}  |  Max: {max(weights):.1f}",
        ]
        if len(weights) >= 4:
            delta = round(weights[-1] - weights[0], 1)
            lines.append(f"  Trend: {delta:+.1f} kg (erste: {weights[0]:.1f} → letzte: {weights[-1]:.1f})")
        current_bmi = bmi(weights[-1])
        if current_bmi:
            lines.append(f"  BMI (aktuell): **{current_bmi}** → {bmi_kategorie(current_bmi)}")
        lines.append("\n  Messungen:")
        for d, w in all_weight:
            lines.append(f"  {d}  {w:.1f} kg")

    if apple_mass:
        am_vals = [r[1] for r in apple_mass if r[1]]
        lines += [
            "\n### Gewicht — Apple Health (interpoliert, kein Trend-Indikator)\n",
            f"  Messungen: {len(apple_mass)}  |  Zeitraum: {apple_mass[0][0]} – {apple_mass[-1][0]}",
            f"  Ø: {avg(am_vals)} kg  |  Min: {min(am_vals):.1f}  |  Max: {max(am_vals):.1f}",
            "  ⚠ Nicht in Weight-Trend/BMI oben verrechnet: Diese Reihe ist verifiziert linear",
            "  interpoliert (z. B. ein Segment von hunderten aufeinanderfolgenden Tagen mit exakt",
            "  identischem Tagesschritt), keine echten Wiegungen. Echte Wiegungen: siehe Abschnitt",
            "  \"Weight\" oben (Beurer/FDDB).",
        ]

    if apple_fat:
        fat_vals = [r[1] for r in apple_fat if r[1]]
        lines += [
            "\n### Körperfettanteil (Apple Health)\n",
            f"  Messungen: {len(apple_fat)}  |  Ø: {avg(fat_vals)}%",
        ]
        for r in apple_fat:
            lines.append(f"  {r[0]}  {r[1]:.1f}%")

    if apple_lean:
        lean_vals = [r[1] for r in apple_lean if r[1]]
        lines += [
            "\n### Muskelmasse / Lean Body Mass (Apple Health)\n",
            f"  Messungen: {len(apple_lean)}  |  Ø: {avg(lean_vals)} kg",
        ]
        for r in apple_lean:
            lines.append(f"  {r[0]}  {r[1]:.1f} kg")

    if fddb:
        taille_vals = [r[4] for r in fddb if r[4]]
        huefte_vals = [r[5] for r in fddb if r[5]]
        if taille_vals:
            lines += [
                "\n### Taillen-/Hüftmaß (FDDB)\n",
                f"  Taille Ø: {avg(taille_vals)} cm  |  Hüfte Ø: {avg(huefte_vals)} cm" if huefte_vals
                else f"  Taille Ø: {avg(taille_vals)} cm",
            ]
            if taille_vals and huefte_vals:
                whr = round(avg(taille_vals) / avg(huefte_vals), 2) if avg(huefte_vals) else None
                if whr:
                    whr_grenze = 0.90 if GENDER and GENDER.startswith("m") else 0.85
                    # WHO 2008: Taillen-Hüft-Verhältnis — Risikoschwelle Männer ≥0,90 / Frauen ≥0,85
                    # doi:https://iris.who.int/handle/10665/42330 (Ashwell & Hsieh 2005 review; WHO technical report)
                    risiko = f"erhöht ⚠ (Grenze: {whr_grenze})" if whr > whr_grenze else "normal ✓"
                    lines.append(f"  Taille-Hüft-Verhältnis: {whr} → {risiko}")
            if taille_vals and HEIGHT_CM:
                whtr = round(avg(taille_vals) / HEIGHT_CM, 2)
                # Ashwell & Gibson 2016: WHtR ≥ 0,50 als universeller Risikoindikator
                # doi:10.1136/bmjopen-2015-010159
                whtr_risiko = "erhöht ⚠" if whtr >= 0.5 else "normal ✓"
                lines.append(f"  Taille-Größe-Verhältnis (WHtR): {whtr} → {whtr_risiko}")

    if nutrition and nutrition[5]:
        kcal, prot, carbs, fat, fiber, n_days = (nutrition[i] for i in range(6))
        lines += ["\n### Ernährung (Ø pro Tag)\n"]
        if kcal:   lines.append(f"  Kalorien:  {round(kcal)} kcal  ({n_days} Tage erfasst)")
        if prot:   lines.append(f"  Protein:   {round(prot)} g" + (
            f"  ({round(prot / (all_weight[-1][1] if all_weight else 1), 1)} g/kg KG)" if all_weight else ""))
        if carbs:  lines.append(f"  Kohlenhydrate: {round(carbs)} g")
        if fat:    lines.append(f"  Fett:      {round(fat)} g")
        if fiber:  lines.append(f"  Ballaststoffe: {round(fiber)} g")

    if sport:
        lines += ["\n### Sport / Training\n"]
        total_sessions = sum(r[1] for r in sport)
        lines.append(f"  Einheiten gesamt: {total_sessions}")
        for s_type, cnt, avg_min, total_h, avg_kcal in sport:
            parts = [f"{cnt}×"]
            if avg_min:   parts.append(f"Ø {int(avg_min)} min")
            if total_h:   parts.append(f"gesamt {total_h} h")
            if avg_kcal:  parts.append(f"Ø {int(avg_kcal)} kcal")
            lines.append(f"  {s_type or 'Unbekannt'}: {', '.join(parts)}")

    # Beurer: Gesamtkörper-Komposition (Muscle %, Wasser %, Viszeralfett)
    # beurer: (date, weight_kg, muscle_pct, water_pct, body_fat_pct, visceral_fat, fat_visceral_pct)
    beurer_comp = [r for r in beurer if any(r[i] is not None for i in (2, 3, 4, 5))]
    if beurer_comp:
        lines += ["\n### Körperzusammensetzung — Verlauf (Beurer BF990)\n"]
        has_mus = any(r[2] for r in beurer_comp)
        has_wat = any(r[3] for r in beurer_comp)
        has_fat = any(r[4] for r in beurer_comp)
        has_vf  = any(r[5] for r in beurer_comp)

        hdr = f"  {'Datum':<12} {'kg':>6}"
        if has_fat: hdr += f"  {'Fett%':>6}"
        if has_mus: hdr += f"  {'Mus%':>5}"
        if has_wat: hdr += f"  {'H2O%':>5}"
        if has_vf:  hdr += f"  {'VF':>4}"
        lines += [hdr, "  " + "-" * len(hdr.rstrip())]
        for r in beurer_comp:
            row = f"  {r[0]:<12} {r[1]:>6.1f}" if r[1] else f"  {r[0]:<12} {'–':>6}"
            if has_fat: row += f"  {r[4]:>5.1f}%" if r[4] is not None else "       –"
            if has_mus: row += f"  {r[2]:>5.1f}%" if r[2] is not None else "      –"
            if has_wat: row += f"  {r[3]:>5.1f}%" if r[3] is not None else "      –"
            if has_vf:  row += f"  {int(r[5]):>4}" if r[5] is not None else "     –"
            lines.append(row)

        # Referenzwerte / Kontext
        last = beurer_comp[-1]
        if last[2]:
            lines.append(f"\n  Muskelmasse aktuell: {last[2]:.1f}%"
                         "  (Rückgang über Zeit = Sarkopenie-Signal)")
        if last[3]:
            lines.append(f"  Körperwasser aktuell: {last[3]:.1f}%"
                         "  (Abfall = Dehydratation / Ödemverschiebung)")
        if last[5]:
            # Beurer BF990 proprietäre Skala 1–59; >13 = erhöht laut Gerätedokumentation.
            # Kein klinisch validierter Schwellenwert — nicht auf andere Geräte übertragbar.
            vf_risiko = "erhöht ⚠ (>13, Beurer-Skala)" if last[5] > 13 else "normal ✓ (≤13, Beurer-Skala)"
            lines.append(f"  Viszeralfett-Index: {int(last[5])}  →  {vf_risiko}"
                         "  (kardiovaskulärer Risikofaktor)")

    if segmental:
        lines += ["\n### Segmentanalyse & Asymmetrien (Beurer BF990)\n"]
        last = segmental[-1]
        date_s = last[0]
        fat_al, fat_ar, fat_ll, fat_lr, fat_t = last[1], last[2], last[3], last[4], last[5]
        mus_al, mus_ar, mus_ll, mus_lr, mus_t = last[6], last[7], last[8], last[9], last[10]
        visc_pct, visc, met_age             = last[11], last[12], last[13]
        soft_lean, lean_body, protein_pct, mus_organ = last[14], last[15], last[16], last[17]

        lines.append(f"  Letzte Messung: {date_s}")

        def asym(links, rechts, einheit="%", schwelle=2.0):
            if links is None or rechts is None:
                return ""
            diff = round(links - rechts, 1)
            marker = f" ⚠ (>{schwelle}{einheit})" if abs(diff) > schwelle else " ✓"
            return f"L {links}{einheit} / R {rechts}{einheit}  Δ {diff:+.1f}{marker}"

        if fat_al is not None:
            lines.append(f"  Fett Arm:    {asym(fat_al, fat_ar)}")
        if fat_ll is not None:
            lines.append(f"  Fett Bein:   {asym(fat_ll, fat_lr)}")
        if fat_t is not None:
            lines.append(f"  Fett Rumpf:  {fat_t}%")
        if mus_al is not None:
            lines.append(f"  Muskel Arm:  {asym(mus_al, mus_ar, schwelle=1.5)}")
        if mus_ll is not None:
            lines.append(f"  Muskel Bein: {asym(mus_ll, mus_lr, schwelle=1.5)}")
        if mus_t is not None:
            lines.append(f"  Muskel Rumpf: {mus_t}%")
        if visc_pct is not None:
            v_risiko = "erhöht ⚠" if visc_pct > 10 else "normal ✓"
            lines.append(f"  Viszeralfett: {visc_pct}% → {v_risiko}" +
                         (f"  (Level {visc})" if visc else ""))
        if met_age is not None:
            lines.append(f"  Stoffwechselalter: {met_age} Jahre" +
                         (f"  (+{met_age - AGE} ggü. Kalenderalter ⚠)" if AGE and met_age > AGE
                          else (f"  (−{AGE - met_age} ggü. Kalenderalter ✓)" if AGE else "")))
        if lean_body is not None:
            lines.append(f"  Lean Body Mass: {lean_body} kg")
        if soft_lean is not None:
            lines.append(f"  Soft Lean Mass: {soft_lean} kg")
        if mus_organ is not None:
            lines.append(f"  Muskelmasse inkl. Organmuskeln: {mus_organ} kg")
        if protein_pct is not None:
            lines.append(f"  Protein: {protein_pct}%")

    if renpho:
        lines += ["\n### Körperumfänge — RENPHO Maßband\n"]

        # Spaltenbezeichner und Indizes im Tupel (0=date)
        CIRC_FIELDS = [
            ("Hals",            1,  "neck_cm"),
            ("Schulter",        2,  "shoulder_cm"),
            ("L-Oberarm",       3,  "upper_arm_left_cm"),
            ("R-Oberarm",       4,  "upper_arm_right_cm"),
            ("Brust",           5,  "chest_cm"),
            ("Taille",          6,  "waist_cm"),
            ("Abdomen",         7,  "abdomen_cm"),
            ("Hüfte",           8,  "hip_cm"),
            ("L-Oberschenkel",  9,  "thigh_left_cm"),
            ("R-Oberschenkel", 10,  "thigh_right_cm"),
            ("L-Wade",         11,  "calf_left_cm"),
            ("R-Wade",         12,  "calf_right_cm"),
        ]

        for r in renpho:
            lines.append(f"  Messung: {r[0]}")
            for label, idx, _ in CIRC_FIELDS:
                v = r[idx]
                if v is not None:
                    lines.append(f"    {label:<18} {v:.1f} cm")

            whr  = r[13]   # von RENPHO berechnet
            waist = r[6]
            hip   = r[8]
            abd   = r[7]

            # WHR: falls RENPHO-Wert vorhanden, sonst aus Taille/Hüfte berechnen
            if whr is None and waist and hip:
                whr = round(waist / hip, 2)
            if whr is not None:
                whr_grenze = 0.90 if GENDER and GENDER.startswith("m") else 0.85
                # WHO 2008: WHR-Risikoschwelle ♂ ≥0,90 / ♀ ≥0,85
                whr_risiko = f"erhöht ⚠ (Grenze: {whr_grenze})" if whr > whr_grenze else "normal ✓"
                lines.append(f"    {'WHR (Taille/Hüfte)':<18} {whr:.2f} → {whr_risiko}")

            if waist and HEIGHT_CM:
                whtr = round(waist / HEIGHT_CM, 2)
                # Ashwell & Gibson 2016: WHtR ≥ 0,50 universeller Risikoindikator
                # doi:10.1136/bmjopen-2015-010159
                whtr_risiko = "erhöht ⚠" if whtr >= 0.5 else "normal ✓"
                lines.append(f"    {'WHtR (Taille/Größe)':<18} {whtr:.2f} → {whtr_risiko}")

            # Abdomen > Hüfte = viszerale Adipositas-Signal
            if abd is not None and hip is not None:
                diff = round(abd - hip, 1)
                abd_risiko = " ⚠ (Abdomen > Hüfte — viszerales Fettmuster)" if diff > 0 else " ✓"
                lines.append(f"    {'Abdomen − Hüfte':<18} {diff:+.1f} cm{abd_risiko}")

            # Taille-Risikoschwellen: IDF 2005 (abdominelle Adipositas: ♀ ≥80 cm, ♂ ≥94 cm)
            if waist is not None:
                taille_grenze = 94 if GENDER and GENDER.startswith("m") else 80
                taille_risiko = f"erhöht ⚠ (IDF ≥{taille_grenze} cm)" if waist >= taille_grenze else "normal ✓"
                lines.append(f"    {'Taillen-Grenzwert':<18} {waist:.1f} cm → {taille_risiko}")

        # ── Asymmetrie-Analyse ────────────────────────────────────────────────
        # Paare: (Label, idx_links, idx_rechts, Schwelle_cm, Kontext)
        # Schwellen aus Literatur:
        #   Oberschenkel: >1 cm Seitenunterschied → V.a. Atrophie / Lymphödem
        #     (Morrone et al. 2017, J Cachexia Sarcopenia Muscle)
        #   Wade:         >1 cm → V.a. Lymphödem / TVT-Zeichen (Fischler & Jamieson 2005,
        #     JRSM; Johansson et al. 2013, Lymphology)
        #   Oberarm:      >1 cm → V.a. Lymphödem / neurologische Atrophie
        #     (Armer & Stewart 2005, Rehabil Oncol)
        ASYM_PAIRS = [
            ("Oberarm",       3,  4,  1.0, "Lymphödem / Atrophie"),
            ("Oberschenkel",  9, 10,  1.0, "Atrophie / Lymphödem"),
            ("Wade",         11, 12,  1.0, "Lymphödem / TVT-Zeichen"),
        ]

        # Sammle alle Messungen je Paar für Verlaufsanalyse
        asym_data: dict[str, list[tuple]] = {p[0]: [] for p in ASYM_PAIRS}
        for r in renpho:
            for name, il, ir, _, _ in ASYM_PAIRS:
                vl, vr = r[il], r[ir]
                if vl is not None and vr is not None:
                    asym_data[name].append((r[0], vl, vr, round(vl - vr, 1)))

        has_any_asym = any(asym_data[p[0]] for p in ASYM_PAIRS)
        if has_any_asym:
            lines += ["\n#### Links-Rechts-Asymmetrie\n"]
            for name, _, _, schwelle, kontext in ASYM_PAIRS:
                pts = asym_data[name]
                if not pts:
                    continue
                lines.append(f"  **{name}** (Schwelle >{schwelle:.0f} cm | {kontext})")
                hdr = f"    {'Datum':<12}  {'Links':>7}  {'Rechts':>7}  {'Δ (L−R)':>8}  Bewertung"
                lines += [hdr, "    " + "─" * (len(hdr) - 4)]
                for date_r, vl, vr, d in pts:
                    marker = f"⚠ (>{schwelle:.0f} cm)" if abs(d) > schwelle else "✓"
                    dom = "L dominiert" if d > 0 else ("R dominiert" if d < 0 else "symmetrisch")
                    lines.append(
                        f"    {date_r:<12}  {vl:>6.1f}cm  {vr:>6.1f}cm  {d:>+7.1f} cm  {marker} {dom}"
                    )
                # Trend bei mehreren Messungen
                if len(pts) >= 2:
                    delta_trend = round(pts[-1][3] - pts[0][3], 1)
                    trend_str = (
                        f"Asymmetrie wächst ⚠ ({delta_trend:+.1f} cm)" if abs(delta_trend) > schwelle / 2
                        else f"Asymmetrie stabil ({delta_trend:+.1f} cm)"
                    )
                    lines.append(f"    Trend: {trend_str}")
                lines.append("")

        # ── Lipödem-Screening ─────────────────────────────────────────────────
        #
        # Lipödem ist eine chronische Fettverteilungsstörung, die fast
        # ausschließlich Frauen betrifft. Kennzeichen:
        #   • Symmetrische Fettanlagerung an Beinen (und/oder Armen)
        #   • Aussparung von Füßen und Händen (→ "Cuff Sign")
        #   • Druckschmerz, Hämatomneigung, kein Ansprechen auf Diät
        #
        # Quellen:
        #   Herbst KL (2012). Rare adipose disorders. Horm Metab Res 44:245–250
        #   Wold LE et al. (1951). Lipedema of the legs. Proc Mayo Clin 26:234
        #   S1-Leitlinie Lipödem, AWMF 037-012, 2016/2022
        #   Reich-Schupke S et al. (2017). S1-guidelines: Lipedema.
        #     J Dtsch Dermatol Ges 15(7):758–767. doi:10.1111/ddg.13036
        #
        # Messbasiertes Screening (KEIN Diagnose-Ersatz):
        #
        # Kriterium A — Bein-Stamm-Disproportion
        #   Oberschenkel/Taille-Ratio > 0.70 bei Frauen → auffällig
        #   (Konsensus-basiert; kein publizierter Grenzwert)
        #
        # Kriterium B — Symmetrie
        #   |L-Wade − R-Wade| < 1 cm UND |L-OS − R-OS| < 1 cm
        #   Lipödem ist definitionsgemäß bilateral-symmetrisch;
        #   Asymmetrie spricht eher für Lymphödem oder TVT.
        #
        # Kriterium C — Wade-Knöchel-Index (WKI)
        #   WKI = Wade / Knöchel (Malleolenhöhe)
        #   Messung Knöchel: schmalste Stelle zwischen Wade und Fuß,
        #   auf Höhe der tastbaren Knöchelknochen (Malleolen), im
        #   Stehen, morgens. → RENPHO custom_2 (links), custom_3 (rechts)
        #
        #   Beim Lipödem endet das Fettgewebe schlagartig am Knöchel
        #   (Cuff Sign), der Knöchelumfang bleibt relativ klein.
        #   WKI > 1.45 (Frauen) → Cuff-Zeichen möglich
        #   WKI > 1.55          → deutlich auffällig
        #   (Adaptiert aus: Dietzel R et al. 2021, Phlebologie 50:297–304;
        #    Bertsch T & Erbacher G 2018, Vasomed 30:258–263)
        #
        # Kriterium D — Knöchel-Ausschluss-Kriterium
        #   Wenn Knöchel mitgeschwollen (WKI normal/niedrig bei großer Wade)
        #   → eher Lymphödem als Lipödem
        #
        # ⚠ Dieses Screening ersetzt KEINE klinische Untersuchung.
        #   Obligate klinische Kriterien (Druckschmerz, Hämatomneigung,
        #   Stemmer-Zeichen, Verlauf unter Diät) sind hier NICHT erfasst.

        lines += ["\n#### Lipödem-Screening (messungsbasiert)\n"]
        lines.append(
            "  ⚠ Kein Diagnose-Ersatz — obligate Kriterien (Druckschmerz,\n"
            "  Hämatomneigung, Stemmer-Zeichen) nur klinisch beurteilbar.\n"
        )

        score = 0
        score_max = 0

        # Kriterium A: Bein-Stamm-Disproportion
        score_max += 1
        # Nimm die aktuellste Messung (letztes Element)
        last = renpho[-1]
        thigh_l, thigh_r = last[9], last[10]
        waist_r = last[6]
        thigh_avg = (
            round((thigh_l + thigh_r) / 2, 1)
            if thigh_l is not None and thigh_r is not None
            else (thigh_l or thigh_r)
        )
        if thigh_avg is not None and waist_r is not None:
            ratio_a = round(thigh_avg / waist_r, 2)
            # Schwelle 0.70 konsensus-basiert (kein publizierter Cut-off)
            if ratio_a > 0.70:
                score += 1
                flag_a = f"auffällig ⚠ (>{0.70})"
            else:
                flag_a = f"unauffällig ✓ (≤{0.70})"
            lines.append(
                f"  A Bein-Stamm-Disproportion\n"
                f"    Ø Oberschenkel {thigh_avg:.1f} cm / Taille {waist_r:.1f} cm\n"
                f"    Ratio: {ratio_a} → {flag_a}"
            )
        else:
            lines.append("  A Bein-Stamm-Disproportion  — Daten fehlen")

        # Kriterium B: Symmetrie
        score_max += 1
        calf_l, calf_r = last[11], last[12]
        sym_os = (abs(thigh_l - thigh_r) < 1.0) if (thigh_l is not None and thigh_r is not None) else None
        sym_wa = (abs(calf_l - calf_r) < 1.0)   if (calf_l  is not None and calf_r  is not None) else None
        if sym_os is not None or sym_wa is not None:
            both_sym = (sym_os is not False) and (sym_wa is not False)
            if both_sym:
                score += 1
                flag_b = "symmetrisch ✓ (Lipödem-konform)"
            else:
                flag_b = "asymmetrisch ⚠ (eher Lymphödem / TVT)"
            parts_b = []
            if sym_os is not None:
                parts_b.append(f"Oberschenkel Δ={abs(thigh_l - thigh_r):.1f} cm")
            if sym_wa is not None:
                parts_b.append(f"Wade Δ={abs(calf_l - calf_r):.1f} cm")
            lines.append(
                f"\n  B Symmetrie\n"
                f"    {', '.join(parts_b)}\n"
                f"    → {flag_b}"
            )
        else:
            lines.append("\n  B Symmetrie  — Daten fehlen")

        # Kriterium C: Wade-Knöchel-Index
        # custom_2 = L-Knöchel, custom_3 = R-Knöchel (Spalten-Index im Tupel)
        # renpho-Tupel: (date[0], neck[1], shoulder[2], arm_l[3], arm_r[4],
        #                chest[5], waist[6], abdomen[7], hip[8],
        #                thigh_l[9], thigh_r[10], calf_l[11], calf_r[12], whr[13])
        # → custom_2/3 sind NICHT im renpho-Tupel, müssen separat geladen werden
        # (renpho-Query lädt nur die 14 festen Spalten; custom_2/3 über eigene Abfrage)
        score_max += 1
        lines.append("\n  C Wade-Knöchel-Index (WKI)")
        lines.append(
            "    Knöcheldaten noch nicht vorhanden.\n"
            "    → Bitte beim nächsten Messen eintragen:\n"
            "      RENPHO App → 'Benutzerdefinierter Teil 2' = L-Knöchel (cm)\n"
            "      RENPHO App → 'Benutzerdefinierter Teil 3' = R-Knöchel (cm)\n"
            "    Messpunkt: schmalste Stelle zwischen Wade und Fuß,\n"
            "    auf Höhe der tastbaren Knöchelknochen (Malleolen),\n"
            "    im Stehen, morgens nüchtern."
        )

        # Zusammenfassung
        lines.append(
            f"\n  Screening-Score: {score}/{score_max} messbarer Kriterien auffällig"
        )
        if score == 0:
            lines.append("  → Kein messbares Lipödem-Signal (Knöcheldaten noch ausstehend)")
        elif score == 1:
            lines.append("  → Einzelnes Signal — Verlaufsmessungen und Knöchelumfang nötig")
        elif score >= 2:
            lines.append("  → Mehrere Signale — klinische Abklärung empfehlenswert")

    if glucose:
        gluc_mmol = [r[1] for r in glucose if r[1]]
        hba1c_vals = [r[4] for r in glucose if r[4]]
        lines += ["\n### Blutzucker\n"]
        lines.append(f"  Messungen: {len(glucose)}")
        if gluc_mmol:
            avg_g = round(sum(gluc_mmol) / len(gluc_mmol), 1)
            # WHO 2006: Gestörte Nüchternglukose (IFG) ≥ 6,1 mmol/L; Diabetes ≥ 7,0 mmol/L
            # Hinweis: Wert ist Durchschnitt aller Glukose-Messungen (nicht ausschließlich Nüchternwert)
            risiko = "erhöht ⚠" if avg_g >= 6.1 else "normal ✓"
            lines.append(f"  Ø Glukose: {avg_g} mmol/L → {risiko}  |  Min: {min(gluc_mmol):.1f}  Max: {max(gluc_mmol):.1f}")
        if hba1c_vals:
            avg_hba1c = round(sum(hba1c_vals) / len(hba1c_vals), 1)
            # ADA 2023: HbA1c 5,7–6,4% = Prädiabetes; ≥6,5% = Diabetes
            hba1c_risiko = "erhöht ⚠" if avg_hba1c > 5.7 else "normal ✓"
            lines.append(f"  HbA1c: {avg_hba1c}% → {hba1c_risiko}")
        for r in glucose:
            ctx = f"  [{r[3]}]" if r[3] and r[3] != "keine Markierung" else ""
            val = f"{r[1]:.2f} mmol/L" if r[1] else f"{r[2]:.0f} mg/dL"
            lines.append(f"  {r[0]}  {val}{ctx}")

    return "\n".join(lines)


def _plot(fddb, apple_mass, apple_fat, apple_lean, beurer, renpho, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    n_rows = 3 if renpho else 2
    fig, axes = plt.subplots(n_rows, 1, figsize=(14, 4 * n_rows), facecolor="#1e1e2e")
    fig.suptitle(f"Body composition {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Weightsverlauf multi-source
    if fddb:
        dts  = [datetime.fromisoformat(r[0]) for r in fddb if r[1]]
        vals = [r[1] for r in fddb if r[1]]
        if dts:
            axes[0].scatter(dts, vals, color="#fdcb6e", s=40, zorder=3, label="FDDB")
    if apple_mass:
        # Duenne Linie statt kraeftiger Scatter-Punkte + Kennzeichnung im Label:
        # diese Reihe ist verifiziert linear interpoliert (siehe build_report),
        # keine echten Wiegungen — visuell nicht mit den echten Messpunkten
        # (FDDB/Beurer, s.o.) gleichrangig darstellen.
        dts  = [datetime.fromisoformat(r[0]) for r in apple_mass if r[1]]
        vals = [r[1] for r in apple_mass if r[1]]
        if dts:
            axes[0].plot(dts, vals, "-", color="#2ecc71", lw=0.8, alpha=0.5, zorder=1,
                         label="Apple Health (interpoliert)")
    if beurer:
        dts  = [datetime.fromisoformat(r[0]) for r in beurer if r[1]]
        vals = [r[1] for r in beurer if r[1]]
        if dts:
            axes[0].scatter(dts, vals, color="#74b9ff", s=30, zorder=3, label="Beurer")
    axes[0].set_ylabel("Weight (kg)", color="#ccc", fontsize=9)
    axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Körperfett + Muskelmasse
    if apple_fat:
        dts_f = [datetime.fromisoformat(r[0]) for r in apple_fat if r[1]]
        fat_v = [r[1] for r in apple_fat if r[1]]
        if dts_f:
            axes[1].plot(dts_f, fat_v, "o-", color="#e17055", ms=6, lw=1.2,
                         label="Körperfett %")
            axes[1].set_ylabel("Körperfett (%)", color="#ccc", fontsize=9)
    if apple_lean:
        ax1b = axes[1].twinx()
        dts_l = [datetime.fromisoformat(r[0]) for r in apple_lean if r[1]]
        lean_v = [r[1] for r in apple_lean if r[1]]
        if dts_l:
            ax1b.plot(dts_l, lean_v, "s-", color="#2ecc71", ms=6, lw=1.2,
                      label="Muskelmasse kg")
            ax1b.set_ylabel("Muskelmasse (kg)", color="#aaa", fontsize=8)
            ax1b.tick_params(colors="#aaa", labelsize=7)
            ax1b.set_facecolor("#2a2a3e")
    axes[1].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    if renpho:
        ax2 = axes[2]
        CIRC_PLOT = [
            ("Taille",          6,  "#e17055"),
            ("Abdomen",         7,  "#d63031"),
            ("Hüfte",           8,  "#fd79a8"),
            ("L-Oberschenkel",  9,  "#74b9ff"),
            ("L-Wade",         11,  "#55efc4"),
        ]
        dts_r = [datetime.fromisoformat(r[0]) for r in renpho]
        for label, idx, color in CIRC_PLOT:
            vals = [r[idx] for r in renpho]
            non_none = [(d, v) for d, v in zip(dts_r, vals) if v is not None]
            if not non_none:
                continue
            ds, vs = zip(*non_none)
            ax2.plot(ds, vs, "o-", color=color, ms=6, lw=1.5, label=label)
        ax2.set_ylabel("Umfang (cm)", color="#ccc", fontsize=9)
        ax2.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper right")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax2.set_title("Körperumfänge (RENPHO)", color="#E0E0E0", fontsize=10)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"body_composition_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"body_composition_{ts}.md"
    content = f"# Body composition\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Body composition & Weight", "Body composition & weight"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    fddb, apple_mass, apple_fat, apple_lean, beurer, nutrition, sport, glucose, segmental, renpho = load_data(conn, args.date_from, args.date_to, args.person)
    conn.close()

    if not fddb and not apple_mass and not apple_fat and not renpho:
        print(t("Keine Körperzusammensetzungs-Daten vorhanden.", "No body composition data available."))
        return

    report = build_report(fddb, apple_mass, apple_fat, apple_lean, beurer,
                               nutrition, sport, glucose, segmental, renpho, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(fddb, apple_mass, apple_fat, apple_lean, beurer, renpho, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
