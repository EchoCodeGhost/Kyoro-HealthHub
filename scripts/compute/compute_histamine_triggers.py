#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Histamine trigger correlation: nutrition x histamine_food_db x symptom track.

@tier        heuristic
@purpose.de  Leitet potenzielle Nahrungs-Trigger her, indem Symptome zeitlich mit
             vorausgegangenen hoch-histaminergen Mahlzeiten korreliert werden.
@purpose.en  Derives candidate food triggers by temporally correlating symptoms
             with preceding high-histamine meals.
@method.de   Mahlzeiten (mit Timestamp) werden über histamine_food_db kategorisiert;
             ein Symptom innerhalb des Reaktionsfensters nach einer hoch-
             histaminergen Mahlzeit erzeugt einen computed-Trigger. Symptomschwere
             wird von Skala 0–10 auf 0–4 abgebildet (/2.5).
@method.en   Meals (timestamped) are categorised via histamine_food_db; a symptom
             within the reaction window after a high-histamine meal produces a
             computed trigger. Symptom severity is mapped from scale 0–10 to 0–4
             (/2.5).
@thresholds
    histamine_cat in (high, liberator, blocker) :: de=als Trigger gewertet :: en=counted as trigger
    histamine_cat = medium                      :: de=optional (--medium) :: en=optional (--medium)
    reaction window                             :: de=Standard 8 h (--hours) :: en=default 8 h (--hours)
@scoring Trigger-Score = Haeufigkeit * 30 + Symptomschwere * 20 + Konsistenz * 50
@reads       nutrition_entries, histamine_food_db, symptoms
@writes      food_triggers (INSERT OR IGNORE, source='computed')
@limits.de   Heuristische Methode: Rein zeitliche Korrelation, kein Kausalnachweis. Confounder (andere
             Auslöser, verzögerte Reaktionen, kumulative Last) werden nicht
             berücksichtigt. Hypothesengenerierend, nicht diagnostisch.
@limits.en   Heuristic method: Purely temporal correlation, not proof of causation. Confounders
             (other triggers, delayed reactions, cumulative load) are not modelled.
             Hypothesis-generating, not diagnostic.
@refs        Schnedl WJ, Enko D (2021). Histamine intolerance originates in the gut. Nutrients, 13(4), 1262. doi:10.3390/nu13041262
             Maintz L, Novak N (2007). Histamine and histamine intolerance. The American Journal of Clinical Nutrition, 85(5):1185-1196. doi:10.1093/ajcn/85.5.1185

@relevance.de  Ermöglicht die Analyse von Histamin-Triggern, essentiell für die allergologische Diagnostik
@relevance.en  Enables histamine trigger analysis, essential for allergological diagnostics
@usage
    python3 compute_histamine_triggers.py
    python3 compute_histamine_triggers.py --medium
    python3 compute_histamine_triggers.py --hours 6
    python3 compute_histamine_triggers.py --rebuild
    python3 compute_histamine_triggers.py --dry-run
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()

MAX_REACTION_H_DEFAULT = 8
TRIGGER_CATS_DEFAULT   = {"high", "liberator", "blocker"}
SOURCE                 = "computed"


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _severity(value_num: float | None) -> int | None:
    """Kyoro 0–10 → severity 0–4."""
    if value_num is None:
        return None
    return min(4, int(value_num / 2.5))


# ── Daten laden ───────────────────────────────────────────────────────────────

def load_trigger_meals(conn, trigger_cats: set[str],
                       person: str) -> list[dict]:
    """Mahlzeiten aus nutrition_entries die einem Trigger-Lebensmittel entsprechen."""
    cats_ph = ",".join("?" * len(trigger_cats))
    rows = conn.execute(f"""
        SELECT n.ts, n.date, n.time_str, n.name, n.portion_g, n.meal_type,
               h.histamine_cat
          FROM nutrition_entries n
          JOIN histamine_food_db h
            ON lower(n.name) = lower(h.name)
            OR lower(n.name) LIKE '%' || lower(h.name) || '%'
            OR lower(h.name) LIKE '%' || lower(n.name) || '%'
         WHERE n.person = ?
           AND h.histamine_cat IN ({cats_ph})
         ORDER BY n.ts
    """, (person, *trigger_cats)).fetchall()
    return [dict(zip(
        ["ts","date","time_str","name","portion_g","meal_type","histamine_cat"], r
    )) for r in rows]


def load_symptoms(conn, person: str) -> list[dict]:
    """Symptome aus symptoms-Tabelle (source='kyoro_st'), voller Timestamp."""
    rows = conn.execute("""
        SELECT ts, date, symptom, value_num, value_text
          FROM symptoms
         WHERE person = ? AND source = 'kyoro_st' AND ts IS NOT NULL
         ORDER BY ts
    """, (person,)).fetchall()
    return [dict(zip(["ts","date","symptom","value_num","value_text"], r))
            for r in rows]


# ── Korrelation ───────────────────────────────────────────────────────────────

def correlate(meals: list[dict], symptoms: list[dict],
              max_h: float) -> list[dict]:
    """
    Für jede Trigger-Mahlzeit: sammle Symptome die innerhalb [0, max_h] danach auftraten.
    Gibt food_trigger-Dicts zurück.
    """
    triggers = []
    max_delta = timedelta(hours=max_h)

    for meal in meals:
        meal_dt = _parse_ts(meal["ts"])
        if not meal_dt:
            continue

        window_symptoms = []
        min_reaction_h  = None

        for sym in symptoms:
            sym_dt = _parse_ts(sym["ts"])
            if not sym_dt:
                continue
            delta = sym_dt - meal_dt
            if timedelta(0) <= delta <= max_delta:
                h = delta.total_seconds() / 3600
                window_symptoms.append(sym["symptom"])
                if min_reaction_h is None or h < min_reaction_h:
                    min_reaction_h = h

        if not window_symptoms:
            continue

        # Schwere: max value_num im Fenster → severity
        max_val = None
        for sym in symptoms:
            sym_dt = _parse_ts(sym["ts"])
            if not sym_dt:
                continue
            if timedelta(0) <= (sym_dt - meal_dt) <= max_delta:
                vn = sym.get("value_num")
                if vn is not None and (max_val is None or vn > max_val):
                    max_val = vn

        triggers.append({
            "ts":           meal["ts"],
            "date":         meal["date"],
            "time_str":     meal.get("time_str"),
            "food_name":    meal["name"],
            "portion_g":    meal.get("portion_g"),
            "histamine_cat": meal["histamine_cat"],
            "reaction_h":   round(min_reaction_h, 2) if min_reaction_h is not None else None,
            "symptoms":     ",".join(sorted(set(window_symptoms))),
            "severity":     _severity(max_val),
            "meal_type":    meal.get("meal_type"),
            "notes":        f"auto:{SOURCE}",
        })

    return triggers


# ── Schreiben ─────────────────────────────────────────────────────────────────

def write_triggers(conn, triggers: list[dict],
                   person: str, dry: bool) -> int:
    if not triggers or dry:
        return len(triggers)
    conn.executemany("""
        INSERT OR IGNORE INTO food_triggers
        (ts, date, time_str, food_name, portion_g, histamine_cat,
         reaction_h, symptoms, severity, meal_type, notes, person)
        VALUES (:ts,:date,:time_str,:food_name,:portion_g,:histamine_cat,
                :reaction_h,:symptoms,:severity,:meal_type,:notes,:person)
    """, [{**t, "person": person} for t in triggers])
    conn.commit()
    return len(triggers)


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("Histamin-Trigger aus FDDB × Kyoro SymptomTrack ableiten",
                      "Derive histamine triggers from FDDB × Kyoro SymptomTrack"))
    parser.add_argument("--medium",  action="store_true",
                        help=t("Auch 'medium'-Lebensmittel als Trigger werten",
                               "Also treat 'medium' foods as triggers"))
    parser.add_argument("--hours",   type=float, default=MAX_REACTION_H_DEFAULT,
                        metavar="H",
                        help=t(f"Max. Reaktionsfenster in Stunden (default {MAX_REACTION_H_DEFAULT})",
                               f"Max. reaction window in hours (default {MAX_REACTION_H_DEFAULT})"))
    parser.add_argument("--rebuild", action="store_true",
                        help=t("Bestehende computed-Trigger löschen + neu ableiten",
                               "Delete existing computed triggers and recompute"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur anzeigen, nichts schreiben",
                               "Show results, do not write"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    # Voraussetzungen prüfen
    for tbl in ("nutrition_entries", "histamine_food_db", "symptoms", "food_triggers"):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not exists:
            print(t(f"Tabelle '{tbl}' nicht vorhanden — bitte erst zugehörigen Importer ausführen.",
                    f"Table '{tbl}' not found — run the corresponding importer first."),
                  file=sys.stderr)
            sys.exit(1)
    # Sicherstellen dass kyoro_st-Einträge mit ts vorhanden sind
    n_kyoro = conn.execute(
        "SELECT COUNT(*) FROM symptoms WHERE source='kyoro_st' AND ts IS NOT NULL"
    ).fetchone()[0]
    if n_kyoro == 0:
        print(t("Keine Kyoro-Symptome mit Timestamp — bitte import_kyoro_symptoms.py ausführen.",
                "No Kyoro symptoms with timestamp — run import_kyoro_symptoms.py first."),
              file=sys.stderr)
        sys.exit(1)

    person = OWN_PERSON_ID

    if args.rebuild:
        conn.execute(
            "DELETE FROM food_triggers WHERE notes LIKE 'auto:%' AND person=?", (person,))
        conn.commit()
        print(t("Bestehende computed-Trigger gelöscht.", "Existing computed triggers deleted."))

    trigger_cats = TRIGGER_CATS_DEFAULT.copy()
    if args.medium:
        trigger_cats.add("medium")

    print(t(f"Lade Trigger-Mahlzeiten (Kategorien: {', '.join(sorted(trigger_cats))}) …",
            f"Loading trigger meals (categories: {', '.join(sorted(trigger_cats))}) …"))
    meals = load_trigger_meals(conn, trigger_cats, person)
    print(t(f"  {len(meals)} Mahlzeiten mit Histamin-Match",
            f"  {len(meals)} meals with histamine match"))

    print(t("Lade Kyoro-Symptome …", "Loading Kyoro symptoms …"))
    symptoms = load_symptoms(conn, person)
    print(t(f"  {len(symptoms)} Symptomeinträge",
            f"  {len(symptoms)} symptom entries"))

    if not meals or not symptoms:
        print(t("Zu wenig Daten für Korrelation.", "Insufficient data for correlation."))
        conn.close()
        return

    print(t(f"Korreliere (Fenster: {args.hours}h) …",
            f"Correlating (window: {args.hours}h) …"))
    triggers = correlate(meals, symptoms, args.hours)
    print(t(f"  {len(triggers)} Trigger-Ereignisse gefunden",
            f"  {len(triggers)} trigger events found"))

    if args.dry_run:
        print(t("\n── Dry-run: keine Änderungen ──────────────────────",
                "\n── Dry-run: no changes ─────────────────────────────"))
        for tr in triggers[:20]:
            print(f"  {tr['date']} {tr['food_name']} ({tr['histamine_cat']}) "
                  f"→ {tr['reaction_h']}h → {tr['symptoms'][:60]}")
        if len(triggers) > 20:
            print(f"  … und {len(triggers)-20} weitere")
    else:
        n = write_triggers(conn, triggers, person, dry=False)
        print(t(f"  {n} Einträge in food_triggers geschrieben (INSERT OR IGNORE)",
                f"  {n} entries written to food_triggers (INSERT OR IGNORE)"))

        r = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM food_triggers WHERE person=?",
            (person,)
        ).fetchone()
        print(t(f"\n  food_triggers gesamt: {r[0]} | {r[1]} → {r[2]}",
                f"\n  food_triggers total: {r[0]} | {r[1]} → {r[2]}"))

    conn.close()


if __name__ == "__main__":
    main()
