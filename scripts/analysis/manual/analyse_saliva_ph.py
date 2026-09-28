#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_saliva_ph.py — Speichel-pH Heimmonitoring Trendanalyse

@tier        heuristic
@purpose.de  Analysiert Speichel-pH-Daten aus Heimmonitoring
@purpose.en  Analyzes saliva pH data from home monitoring
@method.de   Liest Speichel-pH-Daten aus medicine.db (lab_manual, parameter="Speichel-pH"),
             gruppiert nach Kontext (fasting_morning, post_meal_1h …) und erstellt:
             - Trendtabelle aller Kontexte über Zeit
             - Alarm-Flagging anhand der Schwellen in ~/.config/kyoro/saliva_ph_ranges.json
             - Kontext-Mittelwerte + Min/Max-Spanne
             - Optional: LLM-Kommentar (Internist/Allergologe-Perspektive)
             - Optional: Plot (pH-Verlauf pro Kontext)
@method.en   Reads saliva pH data from medicine.db (lab_manual, parameter="Speichel-pH"),
             groups by context (fasting_morning, post_meal_1h …) and creates:
             - Trend table of all contexts over time
             - Alarm flagging from thresholds in ~/.config/kyoro/saliva_ph_ranges.json
             - Context means + min/max range
             - Optional: LLM comment (internist/allergologist perspective)
             - Optional: Plot (pH trend per context)
@reads       medicine.db (lab_manual), ~/.config/kyoro/saliva_ph_ranges.json
@writes      Analyseergebnisse als Markdown (analyses/manual/)
@limits.de   Heuristische Methode. pH-Streifen-Genauigkeit ±0,5; pH-Meter-Werte präziser.
             Kontext-Trennung hängt von korrekter CSV-Eingabe ab.
@limits.en   Heuristic method. pH strip accuracy ±0.5; pH meter values more precise.
             Context separation depends on correct CSV input.
@refs        Tenovuo J, Lagerlöf F (1994). Saliva. In: Thylstrup A, Fejerskov O (Hrsg.), Textbook of Clinical Cariology (2. Aufl.). Munksgaard, Kopenhagen. (kein DOI verfügbar, Buchkapitel)
             Bardow A, Moe D, Nyvad B, Nauntofte B (2000). The buffer capacity and buffer systems of human whole saliva measured without loss of CO2. Archives of Oral Biology, 45(1):1-12. doi:10.1016/S0003-9969(99)00119-3

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@scoring     Anomalie-Score basierend auf Anteil der Messungen außerhalb kontextspezifischer pH-Referenzbereiche
@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_PROMPT
@prompt.en    SYSTEM_PROMPT
@usage
    python3 scripts/analysis/manual/analyse_saliva_ph.py
    python3 scripts/analysis/manual/analyse_saliva_ph.py --plot
    python3 scripts/analysis/manual/analyse_saliva_ph.py --from 2026-01-01
    python3 scripts/analysis/manual/analyse_saliva_ph.py --no-llm
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config, OWN_PERSON_ID, KYORO_CONFIG_DIR
from modules.db import open_medicine_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import call_llm
from modules.prompts.analysis_manual import (
    _SYSTEM_PROMPT_ANALYSE_SALIVA_PH_DE as SYSTEM_PROMPT_DE,
    _SYSTEM_PROMPT_ANALYSE_SALIVA_PH_EN as SYSTEM_PROMPT_EN,
)

cfg     = Config()
OUT_DIR = cfg.analyses_dir / "manual"

_RANGES_PATH = KYORO_CONFIG_DIR / "saliva_ph_ranges.json"

CONTEXT_ORDER = [
    "fasting_morning",
    "post_meal_1h",
    "post_meal_2h",
    "post_antihistamine",
    "evening_baseline",
    "suspected_flare",
]


def _load_ranges() -> dict:
    if not _RANGES_PATH.exists():
        return {}
    with open(_RANGES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _context_label(ranges: dict, context: str, lang: str) -> str:
    ctx = ranges.get("contexts", {}).get(context, {})
    key = "label_de" if lang == "de" else "label_en"
    return ctx.get(key, context)


# ── Daten laden ───────────────────────────────────────────────────────────────

def _load(date_from: date) -> list[tuple[str, str, float, str, str]]:
    """Gibt [(date, context, ph_num, status, kommentar), …] zurück."""
    conn = open_medicine_db()
    rows = conn.execute("""
        SELECT date, wert_num, status, kommentar FROM lab_manual
        WHERE person=? AND parameter='Speichel-pH'
          AND source='import_saliva_ph'
          AND date >= ?
        ORDER BY date
    """, (OWN_PERSON_ID, date_from.isoformat())).fetchall()
    conn.close()

    result = []
    for dt, ph_num, status, kommentar in rows:
        if ph_num is None:
            continue
        context = "unbekannt"
        if kommentar:
            for part in kommentar.split("|"):
                part = part.strip()
                if part.startswith("Kontext:"):
                    # Kontext-Label ist gespeichert; wir versuchen es rückzumappen
                    # Fallback: Rohlabel als context
                    context = part[len("Kontext:"):].strip()
                    break
        result.append((dt, context, float(ph_num), status or "", kommentar or ""))
    return result


def _group_by_date(rows: list) -> dict[str, dict[str, list[float]]]:
    """Gibt {date: {context_label: [ph, …]}} zurück."""
    result: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for dt, context, ph, *_ in rows:
        result[dt][context].append(ph)
    return result


def _all_dates(grouped: dict) -> list[str]:
    return sorted(grouped.keys())


# ── Alarm-Prüfung ─────────────────────────────────────────────────────────────

def _in_target(ph: float, ranges: dict, context_label: str) -> bool:
    """True wenn ph im Zielbereich des Kontexts liegt (anhand Label-Rücksuche)."""
    for ctx_def in ranges.get("contexts", {}).values():
        if context_label in (ctx_def.get("label_de", ""), ctx_def.get("label_en", "")):
            ph_min = ctx_def.get("ph_min")
            ph_max = ctx_def.get("ph_max")
            if ph_min is None and ph_max is None:
                return False
            lo_ok = ph_min is None or ph >= ph_min
            hi_ok = ph_max is None or ph <= ph_max
            return lo_ok and hi_ok
    return False


def _check_alarms(rows: list, ranges: dict, lang: str) -> tuple[list[str], list[str]]:
    """Gibt (alarm_lines, ok_lines) zurück. 🟡/🔴 = Alarm, 🟢 = Zielbereich erreicht."""
    alarm_lines: list[str] = []
    ok_lines:    list[str] = []

    thresholds = sorted(
        ranges.get("alarm_thresholds", []),
        key=lambda x: x.get("threshold", 0),
        reverse=True,
    )
    msg_key = "message_de" if lang == "de" else "message_en"

    for dt, context, ph, *_ in rows:
        triggered = False
        for thr in thresholds:
            direction = thr.get("direction", "low")
            threshold = thr.get("threshold")
            severity  = thr.get("severity", "medium")
            msg       = thr.get(msg_key, "")
            if threshold is None:
                continue
            if (direction == "low"  and ph <= threshold) or \
               (direction == "high" and ph >= threshold):
                icon = "🔴" if severity == "high" else "🟡"
                alarm_lines.append(f"{icon} {dt}  pH {ph:.2f}  [{context}]  {msg}")
                triggered = True
                break

        if not triggered and _in_target(ph, ranges, context):
            ok_lines.append(f"🟢 {dt}  pH {ph:.2f}  [{context}]")

    return alarm_lines, ok_lines


# ── Kontext-Statistik ─────────────────────────────────────────────────────────

def _context_stats(rows: list) -> dict[str, dict]:
    stats: dict[str, dict] = defaultdict(lambda: {"vals": []})
    for dt, context, ph, *_ in rows:
        stats[context]["vals"].append(ph)
    result = {}
    for ctx, d in stats.items():
        vals = d["vals"]
        result[ctx] = {
            "n":    len(vals),
            "mean": sum(vals) / len(vals),
            "min":  min(vals),
            "max":  max(vals),
        }
    return result


# ── Ausgabe ───────────────────────────────────────────────────────────────────

def _render(rows: list, ranges: dict, lang: str) -> str:
    if not rows:
        return t("Keine Speichel-pH-Daten gefunden.", "No saliva pH data found.")

    grouped = _group_by_date(rows)
    dates   = _all_dates(grouped)
    lines: list[str] = []

    lines.append(t("# Speichel-pH Heimmonitoring", "# Saliva pH Home Monitoring"))
    lines.append(f"\n{t('Zeitraum', 'Period')}: {dates[0]} – {dates[-1]}  |  "
                 f"{t('Messungen', 'Measurements')}: {len(rows)}\n")

    # Alle vorkommenden Kontexte (bekannte zuerst, dann unbekannte)
    all_contexts_in_data: set[str] = set()
    for dt_data in grouped.values():
        all_contexts_in_data.update(dt_data.keys())
    ordered = [c for c in CONTEXT_ORDER if c in all_contexts_in_data]
    ordered += sorted(all_contexts_in_data - set(CONTEXT_ORDER))

    # Kontext-Labels
    ctx_labels = {c: _context_label(ranges, c, lang) for c in ordered}
    max_label  = max((len(v) for v in ctx_labels.values()), default=20)
    col_w      = max(max_label + 2, 22)

    # Header
    header = f"{'Kontext' if lang == 'de' else 'Context':<{col_w}}" + \
             "".join(f"{d[5:]:>10}" for d in dates)
    lines.append(header)
    lines.append("─" * len(header))

    for ctx in ordered:
        label = ctx_labels[ctx]
        row   = f"{label:<{col_w}}"
        for dt in dates:
            vals = grouped[dt].get(ctx, [])
            if vals:
                cell = f"{sum(vals)/len(vals):.1f}" + ("*" if len(vals) > 1 else "")
            else:
                cell = "—"
            row += f"{cell:>10}"
        lines.append(row)

    # Mehrfachmessungen-Hinweis
    if any(len(v) > 1 for dt_data in grouped.values() for v in dt_data.values()):
        lines.append(t("\n* = Mittelwert aus mehreren Messungen", "\n* = Mean of multiple measurements"))

    lines.append("")

    # Kontext-Statistik
    stats = _context_stats(rows)
    lines.append(t("## Kontext-Statistik", "## Context Statistics"))
    stat_header = f"{'Kontext' if lang == 'de' else 'Context':<{col_w}}{'n':>5}{'Ø pH':>8}{'Min':>8}{'Max':>8}"
    lines.append(stat_header)
    lines.append("─" * len(stat_header))
    for ctx in ordered:
        if ctx not in stats:
            continue
        s = stats[ctx]
        label = ctx_labels[ctx]
        lines.append(f"{label:<{col_w}}{s['n']:>5}{s['mean']:>8.2f}{s['min']:>8.2f}{s['max']:>8.2f}")
    lines.append("")

    # Alarme + Zielbereich-Treffer
    alarm_lines, ok_lines = _check_alarms(rows, ranges, lang)
    if alarm_lines:
        lines.append(t("## Auffälligkeiten", "## Findings"))
        lines.extend(alarm_lines)
        lines.append("")
    else:
        lines.append(t("✓ Keine Alarmwerte in diesem Zeitraum.", "✓ No alarm values in this period."))
        lines.append("")
    if ok_lines:
        lines.append(t("## Im Zielbereich", "## Within target range"))
        lines.extend(ok_lines)
        lines.append("")

    # Referenzbereiche aus Config
    ctx_defs = ranges.get("contexts", {})
    if ctx_defs:
        lines.append(t("## Referenzbereiche (aus saliva_ph_ranges.json)",
                       "## Reference ranges (from saliva_ph_ranges.json)"))
        for ctx in ordered:
            if ctx not in ctx_defs:
                continue
            d      = ctx_defs[ctx]
            label  = d.get("label_de" if lang == "de" else "label_en", ctx)
            ph_min = d.get("ph_min")
            ph_max = d.get("ph_max")
            note   = d.get("note_de" if lang == "de" else "note_en", "")
            if ph_min is not None or ph_max is not None:
                ref_str = f"{ph_min or '?'}–{ph_max or '?'}"
            else:
                t_no_ref = t("kein Referenzbereich", "no reference range")
                ref_str  = t_no_ref
            lines.append(f"  {label:<{col_w-2}}  pH {ref_str}  {note}")
        lines.append("")

    return "\n".join(lines)


# ── LLM-Kommentar ─────────────────────────────────────────────────────────────

def _llm_comment(report_text: str, lang: str) -> str:
    prompt = t(
        f"Analysiere diese Speichel-pH-Heimmonitoring-Daten klinisch:\n\n{report_text}\n\n"
        "Bitte bewerte:\n"
        "1. pH-Muster im Kontext-Vergleich (nüchtern vs. postprandial, Schub vs. Baseline)\n"
        "2. Klinische Relevanz: Histamin-Mediator-Wirkung auf Speicheldrüsen, Hyposalivation, "
        "   Reflux, Sjögren-Syndrom\n"
        "3. Auffällige Schwankungen oder Trends\n"
        "4. Empfehlungen (weitere Diagnostik, Verhaltensänderung, Arztvorstellung)\n"
        "Antworte präzise und klinisch strukturiert.",

        f"Clinically analyze these saliva pH home-monitoring data:\n\n{report_text}\n\n"
        "Please assess:\n"
        "1. pH pattern in context comparison (fasting vs. postprandial, flare vs. baseline)\n"
        "2. Clinical relevance: histamine mediator effect on salivary glands, hyposalivation, "
        "   reflux, Sjögren's syndrome\n"
        "3. Notable fluctuations or trends\n"
        "4. Recommendations (further diagnostics, behavioral change, physician visit)\n"
        "Respond precisely and in structured clinical format."
    )
    try:
        return call_llm(prompt, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN))
    except Exception as e:
        return t(f"LLM-Fehler: {e}", f"LLM error: {e}")


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(rows: list, ranges: dict, out_dir: Path, lang: str) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print(t("matplotlib nicht verfügbar — kein Plot.", "matplotlib not available — no plot."))
        return

    grouped = _group_by_date(rows)
    dates   = [datetime.strptime(d, "%Y-%m-%d").date() for d in _all_dates(grouped)]

    all_contexts: set[str] = set()
    for dt_data in grouped.values():
        all_contexts.update(dt_data.keys())
    ordered = [c for c in CONTEXT_ORDER if c in all_contexts]
    ordered += sorted(all_contexts - set(CONTEXT_ORDER))

    if not ordered:
        return

    colors = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2"]
    fig, ax = plt.subplots(figsize=(13, 5))

    ctx_defs = ranges.get("contexts", {})
    ref_drawn: set[float] = set()

    for i, ctx in enumerate(ordered):
        color = colors[i % len(colors)]
        label = _context_label(ranges, ctx, lang)
        xs, ys = [], []
        for d_str, dt_data in sorted(grouped.items()):
            vals = dt_data.get(ctx, [])
            if vals:
                xs.append(datetime.strptime(d_str, "%Y-%m-%d").date())
                ys.append(sum(vals) / len(vals))
        if xs:
            ax.plot(xs, ys, "o-", color=color, linewidth=1.5, markersize=5, label=label)

        # Referenzlinien (je Kontext, nur wenn noch nicht gezeichnet)
        cdef = ctx_defs.get(ctx, {})
        for ref_val, ls, lbl_suffix in [
            (cdef.get("ph_min"), "--", "min"),
            (cdef.get("ph_max"), ":",  "max"),
        ]:
            if ref_val is not None and ref_val not in ref_drawn:
                ax.axhline(ref_val, color=color, linestyle=ls, linewidth=0.7, alpha=0.5)
                ref_drawn.add(ref_val)

    # Alarm-Schwellen
    for thr_def in ranges.get("alarm_thresholds", []):
        thr = thr_def.get("threshold")
        if thr is None:
            continue
        sev = thr_def.get("severity", "medium")
        c   = {"high": "#dc2626", "medium": "#f59e0b"}.get(sev, "#f59e0b")
        ax.axhline(thr, color=c, linestyle="-.", linewidth=0.9, alpha=0.6)

    ax.set_ylabel(t("pH-Wert", "pH value"), fontsize=9)
    ax.set_ylim(4.0, 9.0)
    ax.set_yticks([4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0])
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.legend(loc="upper right", fontsize=8)
    fig.suptitle(t("Speichel-pH Heimmonitoring", "Saliva pH Home Monitoring"),
                 fontsize=13)
    plt.tight_layout()

    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out = out_dir / f"saliva_ph_{ts}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(t(f"  → Plot: {out}", f"  → Plot: {out}"))


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Speichel-pH Heimmonitoring Trendanalyse",
                      "Saliva pH home monitoring trend analysis")
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

    ranges = _load_ranges()
    rows   = _load(date_from)

    if not rows:
        print(t(f"Keine Speichel-pH-Daten seit {date_from} in medicine.db.",
                f"No saliva pH data since {date_from} in medicine.db."))
        sys.exit(0)

    report = _render(rows, ranges, lang)
    print(report)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now      = datetime.now(timezone.utc)
    out_path = OUT_DIR / f"saliva_ph_{now.strftime('%Y%m%d_%H%M')}.md"

    full = report
    if not args.no_llm:
        print(t("\nLLM-Kommentar …", "\nLLM comment …"))
        comment = _llm_comment(report, lang)
        full   += f"\n\n## {t('Klinische Einordnung (LLM)', 'Clinical Assessment (LLM)')}\n\n{comment}\n"
        print(comment)

    if args.plot:
        _plot(rows, ranges, OUT_DIR, lang)

    out_path.write_text(full, encoding="utf-8")
    print(t(f"\n→ Bericht: {out_path}", f"\n→ Report: {out_path}"))


if __name__ == "__main__":
    main()
