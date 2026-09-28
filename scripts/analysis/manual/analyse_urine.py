#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_urine.py — Urin-Monitoring Trendanalyse

@tier        heuristic
@purpose.de  Analysiert Urin-Streifentestdaten aus Heimmonitoring
@purpose.en  Analyzes urine dipstick test data from home monitoring
@method.de   Liest Urin-Streifentestdaten aus medicine.db (lab_manual, Parameter Urin-*)
             und erstellt:
             - Trendtabelle aller 12 Parameter ueber Zeit
             - Protein/Kreatinin-Quotient (PCR) wenn numerisch veruegbar
             - Flagging auffaelliger Einzelwerte und Trends
             - Optional: LLM-Kommentar
@method.en   Reads urine dipstick test data from medicine.db (lab_manual, Urine-* parameters)
             and creates:
             - Trend table of all 12 parameters over time
             - Protein/Creatinine Ratio (PCR) if numerically available
             - Flagging of conspicuous individual values and trends
             - Optional: LLM comment
@reads       medicine.db (lab_manual)
@writes      Analyseergebnisse als Markdown/CSV
@limits.de   Heuristische Methode: Heuristische Analyse. Abhaengig von Datenqualitaet.
@limits.en   Heuristic method: Heuristic analysis. Dependent on data quality.
@refs        Simerville JA, Maxted WC, Pahira JJ (2005). Urinalysis: A Comprehensive Review. American Family Physician, 71(6):1153-1162. (kein DOI verfügbar)
             Fogazzi GB, Verdesca S, Garigali G (2008). Urinalysis: Core Curriculum 2008. American Journal of Kidney Diseases, 51(6):1052-1067. doi:10.1053/j.ajkd.2007.11.039

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@scoring Anomalie-Score basierend auf Abweichung von Normalbereichen und Trendrichtung
@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_PROMPT
@prompt.en    SYSTEM_PROMPT
@usage
    python3 scripts/analysis/analyse_urine.py
    python3 scripts/analysis/analyse_urine.py --plot
    python3 scripts/analysis/analyse_urine.py --from 2026-01-01
    python3 scripts/analysis/analyse_urine.py --no-llm
"""

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config, OWN_PERSON_ID
from modules.db import open_medicine_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import call_llm
from modules.prompts.analysis_manual import (
    _SYSTEM_PROMPT_ANALYSE_URINE_DE as SYSTEM_PROMPT_DE,
    _SYSTEM_PROMPT_ANALYSE_URINE_EN as SYSTEM_PROMPT_EN,
)

cfg     = Config()
OUT_DIR = cfg.analyses_dir / "manual"

# ── Parameterliste (Reihenfolge für Anzeige) ──────────────────────────────────
URIN_PARAMS = [
    ("Urin-Leukozyten",      "Leu",  "Leu/µl", None,  10.0),
    ("Urin-Urobilinogen",    "Uro",  "mg/dl",  0.1,   1.0),
    ("Urin-Protein",         "Pro",  "mg/dl",  None,  10.0),
    ("Urin-Bilirubin",       "Bil",  "",       None,  None),
    ("Urin-Glukose",         "Glu",  "mg/dl",  None,  0.0),
    ("Urin-Ascorbinsäure",   "Asc",  "mg/l",   None,  None),
    ("Urin-Spez.Gewicht",    "SpG",  "g/ml",   1.003, 1.030),
    ("Urin-Ketone",          "Ket",  "mg/dl",  None,  0.0),
    ("Urin-Nitrit",          "Nit",  "",       None,  None),
    ("Urin-Kreatinin",       "Kre",  "mg/dl",  20.0,  370.0),
    ("Urin-pH",              "pH",   "",       4.5,   8.0),
    ("Urin-Blut/Hämoglobin", "Blut", "Ery/µl", None,  5.0),
]

QUALITATIVE_NEG = {"neg", "negativ", "negative", "-"}
QUALITATIVE_POS = {"pos", "positiv", "positive", "trace", "spuren"}

# Alarm-Schwellen: (parameter_db_name, wert_text_enthält_oder_wert_num_gt, meldung, dringlichkeit)
ALARMS = [
    ("Urin-Protein",         100.0,   None, "Protein ≥100 mg/dl (++)",         "🟡"),
    ("Urin-Blut/Hämoglobin",  25.0,   None, "Blut ≥25 Ery/µl (++)",            "🟡"),
    ("Urin-Ketone",           40.0,   None, "Ketone ≥40 mg/dl (++) auf GLP-1", "🟡"),
    ("Urin-Nitrit",           None, "pos",  "Nitrit positiv → HWI-Verdacht",   "🟢"),
    ("Urin-Glukose",          50.0,   None, "Glukosurie (tubuläre Ursache?)",  "🟢"),
    ("Urin-pH",                8.0,   None, "pH > 8,0 nüchtern → RTA?",         "🟢"),
]


# ── Daten laden ───────────────────────────────────────────────────────────────

def _load(date_from: date) -> dict[str, list[tuple[str, str, float | None]]]:
    """Gibt {parameter: [(date, wert_text, wert_num), ...]} zurück."""
    conn   = open_medicine_db()
    result = defaultdict(list)
    params = [p[0] for p in URIN_PARAMS] + ["Urin-Sammelvolumen"]
    placeholders = ",".join("?" * len(params))
    rows = conn.execute(f"""
        SELECT date, parameter, wert, wert_num FROM lab_manual
        WHERE person=? AND parameter IN ({placeholders})
          AND source='import_urine_strip'
          AND date >= ?
        ORDER BY date, parameter
    """, [OWN_PERSON_ID] + params + [date_from.isoformat()]).fetchall()
    conn.close()
    for dt, param, wert, wert_num in rows:
        result[param].append((dt, wert or "", wert_num))
    return result


def _all_dates(data: dict) -> list[str]:
    dates: set[str] = set()
    for rows in data.values():
        dates.update(r[0] for r in rows)
    return sorted(dates)


# ── PCR berechnen ─────────────────────────────────────────────────────────────

def _pcr(data: dict, dt: str) -> float | None:
    def get_num(param):
        for d, _, n in data.get(param, []):
            if d == dt and n is not None:
                return n
        return None
    pro = get_num("Urin-Protein")
    kre = get_num("Urin-Kreatinin")
    if pro is not None and kre and kre > 0:
        return round(pro / kre * 1000, 0)
    return None


# ── Flagging ──────────────────────────────────────────────────────────────────

def _flag(wert: str, wert_num: float | None, ref_min: float | None, ref_max: float | None) -> str:
    if wert.lower() in QUALITATIVE_NEG:
        return "" if ref_max == 0.0 else ""
    if wert.lower() in QUALITATIVE_POS and ref_max == 0.0:
        return " ⚠"
    if wert_num is None:
        return ""
    if ref_max is not None and wert_num > ref_max:
        return " ↑"
    if ref_min is not None and wert_num < ref_min:
        return " ↓"
    return ""


def _alarms(data: dict, dates: list[str]) -> list[str]:
    hits: list[str] = []
    for param, thresh_num, thresh_text, msg, prio in ALARMS:
        rows = data.get(param, [])
        for dt, wert, wert_num in rows:
            triggered = False
            if thresh_num is not None and wert_num is not None and wert_num >= thresh_num:
                triggered = True
            if thresh_text and thresh_text.lower() in wert.lower():
                triggered = True
            if triggered:
                hits.append(f"{prio} {dt}  {msg}  (Wert: {wert})")
    return hits


# ── Ausgabe ───────────────────────────────────────────────────────────────────

def _render(data: dict, dates: list[str]) -> str:
    if not dates:
        return t("Keine Urin-Daten gefunden.", "No urine data found.")

    lines: list[str] = []
    lines.append(t("# Urin-Heimmonitoring", "# Urine Home Monitoring"))
    lines.append(f"\n{t('Zeitraum', 'Period')}: {dates[0]} – {dates[-1]}  |  "
                 f"{t('Messungen', 'Measurements')}: {len(dates)}\n")

    # Trendtabelle
    header = f"{'Parameter':<26}" + "".join(f"{d[5:]:>12}" for d in dates)
    lines.append(header)
    lines.append("─" * len(header))

    for db_name, short, unit, ref_min, ref_max in URIN_PARAMS:
        row_data = {d: (w, n) for d, w, n in data.get(db_name, [])}
        label = f"{short} ({unit})" if unit else short
        row = f"{label:<26}"
        for dt in dates:
            if dt in row_data:
                wert, wert_num = row_data[dt]
                flag = _flag(wert, wert_num, ref_min, ref_max)
                cell = f"{wert}{flag}"
            else:
                cell = "—"
            row += f"{cell:>12}"
        lines.append(row)

    # PCR-Zeile
    pcr_vals = [(dt, _pcr(data, dt)) for dt in dates]
    if any(v is not None for _, v in pcr_vals):
        row = f"{'PCR (mg/g)':<26}"
        for dt, pcr in pcr_vals:
            if pcr is not None:
                flag = " ↑" if pcr > 300 else (" ↗" if pcr > 150 else "")
                row += f"{pcr:.0f}{flag}".rjust(12)
            else:
                row += "—".rjust(12)
        lines.append(row)

    lines.append("")

    # Alarme
    alarms = _alarms(data, dates)
    if alarms:
        lines.append(t("## Auffälligkeiten", "## Findings"))
        lines.extend(alarms)
        lines.append("")
    else:
        lines.append(t("✓ Keine Alarmwerte in diesem Zeitraum.", "✓ No alarm values in this period."))
        lines.append("")

    # Vitamin C Warnung
    asc_rows = data.get("Urin-Ascorbinsäure", [])
    elevated_asc = [(d, w) for d, w, n in asc_rows if w.lower() not in QUALITATIVE_NEG and w]
    if elevated_asc:
        lines.append(t("### Ascorbinsäure-Hinweis", "### Ascorbic Acid Note"))
        for dt, wert in elevated_asc:
            lines.append(t(
                f"  {dt}: Ascorbinsäure {wert} → Blut- und Glukose-Ergebnis dieses Tests möglicherweise falsch negativ.",
                f"  {dt}: Ascorbic acid {wert} → Blood and glucose results for this test may be false negative."
            ))
        lines.append("")

    return "\n".join(lines)


# ── LLM-Kommentar ─────────────────────────────────────────────────────────────

def _llm_comment(report_text: str, lang: str) -> str:
    prompt = t(
        f"Analysiere diese Urin-Heimmonitoring-Daten klinisch:\n\n{report_text}\n\n"
        "Bitte bewerte:\n"
        "1. Übergeordnetes Muster (Nierenfunktion, Entzündung, Metabolismus)\n"
        "2. Auffällige Trends (Verschlechterung, Verbesserung, stabil)\n"
        "3. Klinische Einordnung der Einzelbefunde im Kontext Autoimmun/Postinfektiös\n"
        "4. Empfehlungen (Laborbestätigung, Arztvorstellung, Verhaltensänderung)\n"
        "Antworte präzise und klinisch strukturiert.",

        f"Analyze these urine home monitoring data clinically:\n\n{report_text}\n\n"
        "Please assess:\n"
        "1. Overall pattern (kidney function, inflammation, metabolism)\n"
        "2. Notable trends (worsening, improvement, stable)\n"
        "3. Clinical context for individual findings (autoimmune/post-infectious)\n"
        "4. Recommendations (lab confirmation, physician visit, behavioral change)\n"
        "Respond precisely and in structured clinical format."
    )
    try:
        return call_llm(prompt, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN))
    except Exception as e:
        return t(f"LLM-Fehler: {e}", f"LLM error: {e}")


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(data: dict, dates: list[str], out_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print(t("matplotlib nicht verfügbar — kein Plot.", "matplotlib not available — no plot."))
        return

    NUMERIC_PARAMS = [
        ("Urin-Protein",         "Protein (mg/dl)",       10.0,  None),
        ("Urin-Kreatinin",       "Kreatinin (mg/dl)",     20.0,  370.0),
        ("Urin-Leukozyten",      "Leukozyten (Leu/µl)",  None,  10.0),
        ("Urin-Spez.Gewicht",    "Spez. Gewicht (g/ml)",  1.003, 1.030),
        ("Urin-pH",              "pH",                    4.5,   8.0),
        ("Urin-Ketone",          "Ketone (mg/dl)",        None,  0.0),
    ]

    # PCR separat
    pcr_vals = [(datetime.strptime(d, "%Y-%m-%d").date(), _pcr(data, d))
                for d in dates if _pcr(data, d) is not None]

    fig, axes = plt.subplots(len(NUMERIC_PARAMS) + (1 if pcr_vals else 0),
                             1, figsize=(12, 3 * (len(NUMERIC_PARAMS) + 1)),
                             sharex=True)
    if not hasattr(axes, "__iter__"):
        axes = [axes]

    for ax, (param, label, ref_min, ref_max) in zip(axes, NUMERIC_PARAMS):
        rows = {d: n for d, _, n in data.get(param, []) if n is not None}
        xs = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates if d in rows]
        ys = [rows[d] for d in dates if d in rows]
        if not xs:
            ax.set_ylabel(label, fontsize=8)
            ax.text(0.5, 0.5, t("Keine Daten", "No data"),
                    ha="center", va="center", transform=ax.transAxes, color="gray")
            continue
        ax.plot(xs, ys, "o-", color="#2563eb", linewidth=1.5, markersize=5)
        if ref_max is not None:
            ax.axhline(ref_max, color="#dc2626", linestyle="--", linewidth=0.8, alpha=0.6,
                       label=f"Ref max {ref_max}")
        if ref_min is not None:
            ax.axhline(ref_min, color="#16a34a", linestyle="--", linewidth=0.8, alpha=0.6,
                       label=f"Ref min {ref_min}")
        ax.set_ylabel(label, fontsize=8)
        ax.grid(True, alpha=0.3)

    if pcr_vals:
        ax = axes[len(NUMERIC_PARAMS)]
        xs_p, ys_p = zip(*pcr_vals)
        ax.bar(xs_p, ys_p, color=["#dc2626" if y > 300 else "#f59e0b" if y > 150
                                   else "#16a34a" for y in ys_p], alpha=0.7, width=1.5)
        ax.axhline(150, color="#f59e0b", linestyle="--", linewidth=0.8, alpha=0.8)
        ax.axhline(300, color="#dc2626", linestyle="--", linewidth=0.8, alpha=0.8)
        ax.set_ylabel("PCR (mg/g)", fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=30, ha="right")
    fig.suptitle(t("Urin-Heimmonitoring", "Urine Home Monitoring"), fontsize=13, y=1.01)
    plt.tight_layout()

    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out = out_dir / f"urine_{ts}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(t(f"  → Plot: {out}", f"  → Plot: {out}"))


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Urin-Heimmonitoring Trendanalyse", "Urine home monitoring trend analysis")
    )
    ap.add_argument("--from", dest="date_from", default=None,
                    help=t("Daten ab Datum (YYYY-MM-DD), Standard: 180 Tage",
                           "Data from date (YYYY-MM-DD), default: 180 days"))
    ap.add_argument("--plot",   action="store_true", help=t("Plot erzeugen", "Generate plot"))
    ap.add_argument("--no-llm", action="store_true", help=t("Kein LLM-Kommentar", "No LLM comment"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de")

    date_from = (date.fromisoformat(args.date_from) if args.date_from
                 else date.today() - timedelta(days=180))

    data  = _load(date_from)
    dates = _all_dates(data)

    if not dates:
        print(t(f"Keine Urin-Daten seit {date_from} in medicine.db.",
                f"No urine data since {date_from} in medicine.db."))
        sys.exit(0)

    report = _render(data, dates)
    print(report)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now      = datetime.now(timezone.utc)
    out_path = OUT_DIR / f"urine_{now.strftime('%Y%m%d_%H%M')}.md"

    full = report
    if not args.no_llm:
        print(t("\nLLM-Kommentar …", "\nLLM comment …"))
        comment = _llm_comment(report, lang)
        full   += f"\n\n## {t('Klinische Einordnung (LLM)', 'Clinical Assessment (LLM)')}\n\n{comment}\n"
        print(comment)

    if args.plot:
        _plot(data, dates, OUT_DIR)

    out_path.write_text(full, encoding="utf-8")
    print(t(f"\n→ Bericht: {out_path}", f"\n→ Report: {out_path}"))


if __name__ == "__main__":
    main()
