#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_lab_verlauf.py — Zeitlicher Verlauf aller Laborwerte als Tabelle + Plot

@tier        heuristic
@purpose.de  Erstellt eine Verlaufstabelle aller Laborwerte aus lab_manual:
             Zeilen = Parameter (nach Kategorie gruppiert), Spalten = Messdaten.
             Auffällige Werte (↑ / ↓) werden markiert.
@purpose.en  Creates a longitudinal table of all lab values from lab_manual:
             rows = parameters (grouped by category), columns = measurement dates.
             Out-of-range values (↑ / ↓) are flagged.
@method.de   Liest lab_manual aus medicine.db, pivotiert nach (kategorie, parameter) × datum,
             gibt je Kategorie eine Tabelle aus und erzeugt optional Plots.
             Qualitative Werte (neg/pos) werden als Text dargestellt, nicht geplottet.
@method.en   Reads lab_manual from medicine.db, pivots by (kategorie, parameter) × date,
             prints one table per category, optionally generates plots.
             Qualitative values (neg/pos) are shown as text, not plotted.
@reads       medicine.db (lab_manual)
@writes      Analyseergebnisse als Markdown (analyses/manual/), optional PNG
@limits.de   Referenzwerte kommen direkt aus der DB (per Import gesetzt) und können
             zwischen Laboren variieren. Qualitative Parameter werden nicht geplottet.

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@limits.en   Reference values come directly from the DB (set during import) and may
             vary between labs. Qualitative parameters are not plotted.
@scoring     Anomalie-Score pro Parameter: Anzahl außerhalb-Referenz-Messungen / Gesamtmessungen
@refs        Ozarda Y (2016). Reference intervals: current status, recent developments and future considerations. Biochemia Medica, 26(1), 5-16. doi:10.11613/BM.2016.001
@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_PROMPT
@prompt.en    SYSTEM_PROMPT
@usage
    python3 scripts/analysis/manual/analyse_lab_verlauf.py
    python3 scripts/analysis/manual/analyse_lab_verlauf.py --plot
    python3 scripts/analysis/manual/analyse_lab_verlauf.py --kategorie Blutbild
    python3 scripts/analysis/manual/analyse_lab_verlauf.py --from 2024-01-01 --plot
    python3 scripts/analysis/manual/analyse_lab_verlauf.py --no-llm
    python3 scripts/analysis/manual/analyse_lab_verlauf.py --exclude-source import_urine_strip
"""

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config, OWN_PERSON_ID
from modules.db import open_lab_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import call_llm
from modules.prompts.analysis_manual import (
    _SYSTEM_PROMPT_ANALYSE_LAB_VERLAUF_DE as SYSTEM_PROMPT_DE,
    _SYSTEM_PROMPT_ANALYSE_LAB_VERLAUF_EN as SYSTEM_PROMPT_EN,
)

cfg     = Config()
OUT_DIR = cfg.analyses_dir / "manual"

_QUALITATIVE = {"neg", "negativ", "negative", "-", "pos", "positiv", "positive",
                "+", "++", "+++", "trace", "spuren", "reaktiv", "nicht reaktiv",
                "nachgewiesen", "nicht nachgewiesen"}

_CATEGORY_ORDER = [
    "Blutbild", "Differentialblutbild", "Eisen/Entzündung", "Entzündung",
    "Gerinnung", "Elektrolyte", "Metabolismus", "Stoffwechsel",
    "Niere", "Niere/Leber", "Schilddrüse", "Vitamine",
    "Herzmarker", "Muskel/Enzym", "Elektrophorese",
    "Infektionsdiagnostik", "Infektologie", "Tumor-/Autoimmunmarker",
    "Speichel", "Urinstatus",
]


# ── Daten laden ───────────────────────────────────────────────────────────────

def _load(date_from: date, kategorie_filter: str | None,
          exclude_sources: list[str]) -> list[tuple]:
    """Gibt [(date, kategorie, parameter, wert, wert_num, einheit, ref_min, ref_max, status)] zurück."""
    conn   = open_lab_db()
    query  = """
        SELECT date, COALESCE(kategorie,'—'), parameter,
               wert, wert_num, COALESCE(einheit,''), ref_min, ref_max, COALESCE(status,'')
        FROM lab_all
        WHERE person=? AND date >= ?
    """
    params: list = [OWN_PERSON_ID, date_from.isoformat()]

    if kategorie_filter:
        query += " AND kategorie=?"
        params.append(kategorie_filter)

    if exclude_sources:
        placeholders = ",".join("?" * len(exclude_sources))
        query += f" AND (source NOT IN ({placeholders}) OR source IS NULL)"
        params.extend(exclude_sources)

    query += " ORDER BY date, kategorie, parameter"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def _pivot(rows: list) -> dict:
    """
    Gibt {kategorie: {parameter: {date: (wert, wert_num, einheit, ref_min, ref_max, status)}}} zurück.
    Mehrere Werte pro (parameter, date): letzter gewinnt (neueste Laborangabe).
    """
    data: dict = defaultdict(lambda: defaultdict(dict))
    units:  dict = {}
    refs:   dict = {}

    for dt, kat, param, wert, wert_num, einheit, ref_min, ref_max, status in rows:
        data[kat][param][dt] = (wert or "", wert_num, status)
        if einheit and (param, kat) not in units:
            units[(param, kat)] = einheit
        if (ref_min is not None or ref_max is not None) and (param, kat) not in refs:
            refs[(param, kat)] = (ref_min, ref_max)

    return data, units, refs


def _all_dates(data: dict) -> list[str]:
    dates: set[str] = set()
    for kat_data in data.values():
        for param_data in kat_data.values():
            dates.update(param_data.keys())
    return sorted(dates)


def _is_qualitative(wert: str, wert_num) -> bool:
    if wert_num is not None:
        return False
    return wert.lower().strip() in _QUALITATIVE or not wert.strip()


# ── Flagging ──────────────────────────────────────────────────────────────────

def _flag(status: str, wert: str, wert_num) -> str:
    if status == "high":
        return " ↑"
    if status == "low":
        return " ↓"
    if wert.lower() in {"pos", "positiv", "positive", "+", "++", "+++",
                        "reaktiv", "nachgewiesen"}:
        return " ⚠"
    return ""


# ── Tabellenausgabe ───────────────────────────────────────────────────────────

def _render_category(kat: str, kat_data: dict, dates: list[str],
                     units: dict, refs: dict, lang: str) -> list[str]:
    lines: list[str] = []
    lines.append(f"\n### {kat}\n")

    # Nur Daten dieser Kategorie
    local_dates = sorted({d for param_data in kat_data.values() for d in param_data})
    if not local_dates:
        return lines

    # Spaltenbreiten
    param_w = max(len(p) for p in kat_data) + 2
    unit_w  = max((len(units.get((p, kat), "")) for p in kat_data), default=0) + 2
    col_w   = 11

    # Header
    header = f"{'Parameter':<{param_w}}{'Einheit':<{unit_w}}" + \
             "".join(f"{d[5:]:>{col_w}}" for d in local_dates)
    lines.append(header)
    lines.append("─" * len(header))

    # Ref-Zeile (optional, wenn es Referenzwerte gibt)
    has_refs = any(refs.get((p, kat)) for p in kat_data)
    if has_refs:
        ref_row = f"{'  Referenz':<{param_w}}{'':<{unit_w}}"
        for d in local_dates:
            ref_row += f"{'':>{col_w}}"
        # Wir zeigen Referenzen pro Parameter, nicht als extra Zeile

    for param in sorted(kat_data.keys()):
        param_data = kat_data[param]
        einheit    = units.get((param, kat), "")
        ref        = refs.get((param, kat), (None, None))
        ref_str    = ""
        if ref[0] is not None and ref[1] is not None:
            ref_str = f"[{ref[0]}–{ref[1]}]"
        elif ref[0] is not None:
            ref_str = f"[≥{ref[0]}]"
        elif ref[1] is not None:
            ref_str = f"[≤{ref[1]}]"

        label = param if not ref_str else f"{param} {ref_str}"
        row   = f"{label:<{param_w}}{einheit:<{unit_w}}"

        for d in local_dates:
            if d in param_data:
                wert, wert_num, status = param_data[d]
                flag = _flag(status, wert, wert_num)
                if wert_num is not None:
                    cell = f"{wert_num:g}{flag}"
                else:
                    cell = f"{wert}{flag}"
            else:
                cell = "—"
            row += f"{cell:>{col_w}}"
        lines.append(row)

    return lines


def _render(data: dict, dates: list[str], units: dict, refs: dict, lang: str) -> str:
    lines: list[str] = []
    lines.append(t("# Labor-Verlauf", "# Lab Value Longitudinal Overview"))
    lines.append(f"\n{t('Zeitraum', 'Period')}: {dates[0]} – {dates[-1]}  |  "
                 f"{t('Messdaten', 'Measurement dates')}: {len(dates)}\n")

    # Kategorien in definierter Reihenfolge, dann Rest alphabetisch
    all_kats = set(data.keys())
    ordered  = [k for k in _CATEGORY_ORDER if k in all_kats]
    ordered += sorted(all_kats - set(_CATEGORY_ORDER))

    for kat in ordered:
        lines.extend(_render_category(kat, data[kat], dates, units, refs, lang))

    return "\n".join(lines)


# ── Kurzübersicht auffälliger Werte ──────────────────────────────────────────

def _summary_flags(data: dict, units: dict, lang: str) -> list[str]:
    hits: list[str] = []
    for kat, kat_data in data.items():
        for param, param_data in kat_data.items():
            for dt, (wert, wert_num, status) in sorted(param_data.items()):
                flag = _flag(status, wert, wert_num)
                if flag:
                    einheit = units.get((param, kat), "")
                    val = f"{wert_num:g} {einheit}".strip() if wert_num is not None else wert
                    icon = "↑" if "↑" in flag else ("↓" if "↓" in flag else "⚠")
                    hits.append(f"  {icon}  {dt}  {param} ({kat}): {val}")
    return hits


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(data: dict, units: dict, refs: dict, out_dir: Path, lang: str,
          kategorie_filter: str | None) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import Patch
    except ImportError:
        print(t("matplotlib nicht verfügbar — kein Plot.", "matplotlib not available — no plot."))
        return

    all_kats = set(data.keys())
    ordered  = [k for k in _CATEGORY_ORDER if k in all_kats]
    ordered += sorted(all_kats - set(_CATEGORY_ORDER))

    for kat in ordered:
        kat_data = data[kat]

        # Nur numerisch plottbare Parameter
        numeric_params = [
            p for p, pd in kat_data.items()
            if any(wn is not None for _, wn, _ in pd.values())
        ]
        if not numeric_params:
            continue

        n_plots = len(numeric_params)
        fig, axes = plt.subplots(n_plots, 1,
                                 figsize=(13, max(3, 2.5 * n_plots)),
                                 sharex=True, squeeze=False)

        for ax, param in zip(axes[:, 0], sorted(numeric_params)):
            param_data = kat_data[param]
            einheit    = units.get((param, kat), "")
            ref_min, ref_max = refs.get((param, kat), (None, None))

            xs, ys, statuses = [], [], []
            for dt in sorted(param_data):
                wert, wn, status = param_data[dt]
                if wn is not None:
                    xs.append(datetime.strptime(dt, "%Y-%m-%d").date())
                    ys.append(wn)
                    statuses.append(status)

            if not xs:
                ax.set_visible(False)
                continue

            # Referenzband
            if ref_min is not None or ref_max is not None:
                lo = ref_min if ref_min is not None else min(ys) * 0.8
                hi = ref_max if ref_max is not None else max(ys) * 1.2
                ax.axhspan(lo, hi, color="#16a34a", alpha=0.08, label=t("Referenz", "Reference"))
                if ref_min is not None:
                    ax.axhline(ref_min, color="#16a34a", linestyle="--", linewidth=0.8, alpha=0.5)
                if ref_max is not None:
                    ax.axhline(ref_max, color="#16a34a", linestyle="--", linewidth=0.8, alpha=0.5)

            # Punkte nach Status einfärben
            colors = []
            for s in statuses:
                if s == "high":
                    colors.append("#dc2626")
                elif s == "low":
                    colors.append("#2563eb")
                else:
                    colors.append("#16a34a")

            ax.plot(xs, ys, "-", color="#6b7280", linewidth=1.2, zorder=1)
            ax.scatter(xs, ys, c=colors, s=40, zorder=2)

            label = f"{param}" + (f" ({einheit})" if einheit else "")
            ax.set_ylabel(label, fontsize=8)
            ax.grid(True, alpha=0.25)

            # Werte als Annotation
            if len(xs) <= 12:
                for x, y, s in zip(xs, ys, statuses):
                    ax.annotate(f"{y:g}", (x, y),
                                textcoords="offset points", xytext=(0, 6),
                                ha="center", fontsize=7, color="#374151")

        axes[-1, 0].xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
        plt.setp(axes[-1, 0].xaxis.get_majorticklabels(), rotation=30, ha="right")

        legend_handles = [
            Patch(color="#dc2626", label=t("erhöht ↑", "elevated ↑")),
            Patch(color="#2563eb", label=t("erniedrigt ↓", "low ↓")),
            Patch(color="#16a34a", label=t("normal", "normal")),
        ]
        if ref_min is not None or ref_max is not None:
            legend_handles.append(Patch(color="#16a34a", alpha=0.2,
                                        label=t("Referenzband", "Reference band")))
        axes[0, 0].legend(handles=legend_handles, loc="upper right", fontsize=7)

        fig.suptitle(f"{t('Labor-Verlauf', 'Lab Trend')}: {kat}", fontsize=12)
        plt.tight_layout()

        slug = kat.replace("/", "_").replace(" ", "_").lower()
        ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        out  = out_dir / f"lab_{slug}_{ts}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(t(f"  → Plot: {out}", f"  → Plot: {out}"))


# ── LLM-Kommentar ─────────────────────────────────────────────────────────────

def _llm_comment(report_text: str, flags: list[str], lang: str) -> str:
    flag_block = "\n".join(flags) if flags else t("Keine auffälligen Werte.", "No flagged values.")
    prompt = t(
        f"Analysiere diesen Laborwert-Verlauf klinisch:\n\n{report_text}\n\n"
        f"Auffällige Werte:\n{flag_block}\n\n"
        "Bitte bewerte:\n"
        "1. Übergeordnete Muster über die Zeit (Verbesserung, Verschlechterung, stabil)\n"
        "2. Klinisch relevante Einzelbefunde im Verlauf\n"
        "3. Zusammenhänge zwischen verschiedenen Kategorien\n"
        "4. Empfehlungen (weitere Diagnostik, Verlaufskontrolle)\n"
        "Antworte präzise und klinisch strukturiert.",

        f"Clinically analyze this longitudinal lab value overview:\n\n{report_text}\n\n"
        f"Flagged values:\n{flag_block}\n\n"
        "Please assess:\n"
        "1. Overall patterns over time (improvement, worsening, stable)\n"
        "2. Clinically relevant individual findings in context\n"
        "3. Relationships between different categories\n"
        "4. Recommendations (further diagnostics, follow-up)\n"
        "Respond precisely and in structured clinical format."
    )
    try:
        return call_llm(prompt, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN))
    except Exception as e:
        return t(f"LLM-Fehler: {e}", f"LLM error: {e}")


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Labor-Verlaufstabelle aus allen lab_manual-Einträgen",
                      "Longitudinal lab value table from all lab_manual entries")
    )
    ap.add_argument("--from", dest="date_from", default=None,
                    help=t("Daten ab Datum (YYYY-MM-DD), Standard: alle",
                           "Data from date (YYYY-MM-DD), default: all"))
    ap.add_argument("--kategorie", default=None,
                    help=t("Nur diese Kategorie anzeigen (z. B. Blutbild)",
                           "Show only this category (e.g. Blutbild)"))
    ap.add_argument("--plot", action="store_true",
                    help=t("Plots pro Kategorie erzeugen", "Generate plots per category"))
    ap.add_argument("--no-llm", action="store_true",
                    help=t("Kein LLM-Kommentar", "No LLM comment"))
    ap.add_argument("--exclude-source", metavar="SOURCE", action="append", default=[],
                    dest="exclude_sources",
                    help=t("Quelle ausschließen (wiederholbar, z. B. import_urine_strip)",
                           "Exclude source (repeatable, e.g. import_urine_strip)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de")

    date_from = (date.fromisoformat(args.date_from) if args.date_from
                 else date(1970, 1, 1))

    rows = _load(date_from, args.kategorie, args.exclude_sources)
    if not rows:
        msg_filter = f" (Kategorie: {args.kategorie})" if args.kategorie else ""
        print(t(f"Keine Laborwerte in medicine.db gefunden{msg_filter}.",
                f"No lab values found in medicine.db{msg_filter}."))
        sys.exit(0)

    data, units, refs = _pivot(rows)
    dates = _all_dates(data)

    report = _render(data, dates, units, refs, lang)
    print(report)

    flags = _summary_flags(data, units, lang)
    if flags:
        print(t("\n## Zusammenfassung Auffälligkeiten", "\n## Summary of Flagged Values"))
        print("\n".join(flags))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now      = datetime.now(timezone.utc)
    out_path = OUT_DIR / f"lab_verlauf_{now.strftime('%Y%m%d_%H%M')}.md"

    full = report
    if flags:
        full += t("\n\n## Zusammenfassung Auffälligkeiten\n\n",
                  "\n\n## Summary of Flagged Values\n\n") + "\n".join(flags) + "\n"

    if not args.no_llm:
        print(t("\nLLM-Kommentar …", "\nLLM comment …"))
        comment = _llm_comment(report[:4000], flags, lang)
        full   += f"\n\n## {t('Klinische Einordnung (LLM)', 'Clinical Assessment (LLM)')}\n\n{comment}\n"
        print(comment)

    if args.plot:
        _plot(data, units, refs, OUT_DIR, lang, args.kategorie)

    out_path.write_text(full, encoding="utf-8")
    print(t(f"\n→ Bericht: {out_path}", f"\n→ Report: {out_path}"))


if __name__ == "__main__":
    main()
