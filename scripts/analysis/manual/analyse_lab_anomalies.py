#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_lab_anomalies.py — Chronische Mangel-/Überschuss-Erkennung aus Laborwerten

@tier        heuristic
@purpose.de  Findet automatisch Laborparameter, die über einen Großteil der
             gemessenen Zeitpunkte durchgehend unter (oder über) dem
             Referenzbereich liegen — statt sich auf die Erinnerung zu
             verlassen, welche Mängel "schon bekannt" sind.
@purpose.en  Automatically finds lab parameters that sit below (or above)
             the reference range across most of the measured time points —
             instead of relying on memory of which deficiencies are
             "already known".
@method.de   Liest lab_all (health.db+medicine.db via open_lab_db) für alle
             quantitativen Messungen (wert_num + ref_min/ref_max gesetzt).
             Pro Parameter: Anteil der Messungen unterhalb ref_min
             ("Mangel-Quote") bzw. oberhalb ref_max ("Überschuss-Quote").
             Als chronisch markiert, wenn die Quote eine Schwelle überschreitet
             UND genug Messungen vorliegen (verhindert Alarm durch einen
             einzelnen Ausreißer). Kein LLM beteiligt — rein statistisch.
@method.en   Reads lab_all (health.db+medicine.db via open_lab_db) for all
             quantitative measurements (wert_num + ref_min/ref_max set). Per
             parameter: fraction of measurements below ref_min ("deficiency
             rate") or above ref_max ("excess rate"). Flagged as chronic
             when the rate exceeds a threshold AND enough measurements
             exist (prevents a single outlier from triggering an alert). No
             LLM involved — purely statistical.
@reads       medicine.db (lab_manual), health.db (lab_results) via lab_all
@writes      Analyseergebnis als Markdown (analyses/manual/)
@limits.de   Referenzbereiche kommen aus der DB (Labor-abhängig, können
             zwischen Laboren leicht variieren). Qualitative Werte
             (negativ/positiv) werden nicht berücksichtigt, nur numerische.
             Erkennt nur statistische Muster, keine klinische Bewertung —
             Ersatz für ärztliche Einordnung ist das nicht.
@limits.en   Reference ranges come from the DB (lab-dependent, can vary
             slightly between labs). Qualitative values (negative/positive)
             are not considered, only numeric ones. Detects statistical
             patterns only, no clinical judgment — not a substitute for a
             doctor's assessment.
@scoring     Pro (Kategorie, Parameter)-Gruppe mit mindestens --min-measurements
             (Default 3) Messungen: rate_low = Anteil der Messungen unter
             ref_min, rate_high = Anteil über ref_max (je Messung gegen die
             EIGENE Referenzspanne dieser Zeile verglichen, nicht gegen eine
             gemeinsame). rate_low >= --threshold (Default 0.5) → "mangel",
             sonst rate_high >= threshold → "ueberschuss". Beide Richtungen
             sind gleich gewichtet, keine Richtung bevorzugt.

@relevance.de  Automatisiert die Erkennung chronischer Mängel/Überschüsse, essentiell um sie nicht zu übersehen
@relevance.en  Automates detection of chronic deficiencies/excesses, essential for not overlooking them
@usage
    python3 analyse_lab_anomalies.py
    python3 analyse_lab_anomalies.py --threshold 0.6 --min-measurements 5
    python3 analyse_lab_anomalies.py --from 2020-01-01
"""

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_lab_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

cfg = Config()
OUT_DIR = cfg.analyses_dir / "manual"


def load_quantitative(date_from: date) -> list[tuple]:
    """[(date, kategorie, parameter, wert_num, einheit, ref_min, ref_max)]."""
    conn = open_lab_db()
    rows = conn.execute(
        """
        SELECT date, COALESCE(kategorie,'—'), parameter, wert_num,
               COALESCE(einheit,''), ref_min, ref_max
        FROM lab_all
        WHERE person=? AND date >= ? AND wert_num IS NOT NULL
              AND ref_min IS NOT NULL AND ref_max IS NOT NULL
        ORDER BY parameter, date
        """,
        [OWN_PERSON_ID, date_from.isoformat()],
    ).fetchall()
    conn.close()
    return rows


def analyse(rows: list[tuple], threshold: float, min_n: int) -> list[dict]:
    by_param: dict[tuple, list[tuple]] = defaultdict(list)
    for d, kat, param, wert, einheit, ref_min, ref_max in rows:
        by_param[(kat, param)].append((d, wert, einheit, ref_min, ref_max))

    findings = []
    for (kat, param), measurements in by_param.items():
        n = len(measurements)
        if n < min_n:
            continue
        # ref_min/ref_max can differ slightly between labs, so compare each
        # measurement against its OWN row's reference range, not a shared one
        n_low = sum(1 for _, w, _, rmin, _ in measurements if w < rmin)
        n_high = sum(1 for _, w, _, _, rmax in measurements if w > rmax)
        rate_low = n_low / n
        rate_high = n_high / n
        last = measurements[-1]
        entry = {
            "kategorie": kat, "parameter": param, "n": n,
            "rate_low": rate_low, "rate_high": rate_high,
            "last_date": last[0], "last_wert": last[1], "einheit": last[2],
            "first_date_measured": measurements[0][0],
        }
        if rate_low >= threshold:
            entry["kind"] = "mangel"
            findings.append(entry)
        elif rate_high >= threshold:
            entry2 = dict(entry)
            entry2["kind"] = "ueberschuss"
            findings.append(entry2)
    return findings


def render(findings: list[dict], lang: str) -> str:
    mangel = sorted((f for f in findings if f["kind"] == "mangel"), key=lambda f: -f["rate_low"])
    ueberschuss = sorted((f for f in findings if f["kind"] == "ueberschuss"), key=lambda f: -f["rate_high"])

    lines = [t("# Chronische Labor-Mängel/Überschüsse", "# Chronic Lab Deficiencies/Excesses"), ""]
    lines.append(t(
        "*Rein statistisch ermittelt, kein LLM beteiligt. Kein Ersatz für ärztliche Einordnung.*",
        "*Purely statistical, no LLM involved. Not a substitute for a doctor's assessment.*",
    ))
    lines.append("")

    lines.append(t("## Chronischer Mangel (dauerhaft unter Referenzbereich)",
                    "## Chronic Deficiency (persistently below reference range)"))
    if not mangel:
        lines.append(t("Keine gefunden.", "None found."))
    for f in mangel:
        lines.append(
            f"- **{f['parameter']}** ({f['kategorie']}): {f['rate_low']:.0%} von {f['n']} Messungen "
            f"unter Referenz — letzter Wert {f['last_wert']} {f['einheit']} am {f['last_date']} "
            f"(erste Messung: {f['first_date_measured']})"
        )
    lines.append("")

    lines.append(t("## Chronischer Überschuss (dauerhaft über Referenzbereich)",
                    "## Chronic Excess (persistently above reference range)"))
    if not ueberschuss:
        lines.append(t("Keine gefunden.", "None found."))
    for f in ueberschuss:
        lines.append(
            f"- **{f['parameter']}** ({f['kategorie']}): {f['rate_high']:.0%} von {f['n']} Messungen "
            f"über Referenz — letzter Wert {f['last_wert']} {f['einheit']} am {f['last_date']} "
            f"(erste Messung: {f['first_date_measured']})"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=t(
        "Chronische Labor-Mängel/Überschüsse automatisch erkennen",
        "Automatically detect chronic lab deficiencies/excesses",
    ))
    ap.add_argument("--from", dest="date_from", default=None,
                    help=t("Daten ab Datum (YYYY-MM-DD), Standard: Geburtsdatum aus Config",
                           "Data from date (YYYY-MM-DD), default: birthdate from config"))
    ap.add_argument("--threshold", type=float, default=0.5,
                    help=t("Anteil außerhalb Referenz ab dem als 'chronisch' gilt (Standard: 0.5)",
                           "Fraction outside reference above which it counts as 'chronic' (default: 0.5)"))
    ap.add_argument("--min-measurements", type=int, default=3, dest="min_n",
                    help=t("Mindestanzahl Messungen, um gewertet zu werden (Standard: 3)",
                           "Minimum number of measurements to be considered (default: 3)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de")

    if args.date_from:
        date_from = date.fromisoformat(args.date_from)
    elif cfg.birthdate:
        date_from = date.fromisoformat(cfg.birthdate)
    else:
        date_from = date(1900, 1, 1)  # Fallback nur falls Geburtsdatum nicht konfiguriert ist
    rows = load_quantitative(date_from)
    if not rows:
        print(t("Keine quantitativen Laborwerte gefunden.", "No quantitative lab values found."))
        sys.exit(0)

    findings = analyse(rows, args.threshold, args.min_n)
    report = render(findings, lang)
    print(report)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    out_path = OUT_DIR / f"lab_auffaelligkeiten_{now.strftime('%Y%m%d_%H%M')}.md"
    out_path.write_text(report, encoding="utf-8")
    print(t(f"\n→ Bericht: {out_path}", f"\n→ Report: {out_path}"))


if __name__ == "__main__":
    main()
