#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Exposition × Symptom-Analyse

Wertet product_exposures (Medikamente, Kosmetik, Zahnpflege, Haushaltsmittel, ...)
gegen die Symptom-Einträge aus und zeigt:

  1. Expositions-Kalender: welche Kategorien an welchen Tagen
  2. Substanz-Häufigkeit: welche Substanzen am häufigsten geloggt
  3. Ko-Auftreten: Expositions-Tage MIT Symptomeinträgen vs. ohne
  4. Zeitversatz-Analyse: gleicher Tag / +1 Tag / +2 Tage
  5. Sonnenallergie-Report: UV/Solarstrahlung × Hautreaktionen

Daten einloggen mit:
  python log_exposure.py add --category dental --product "Colgate Total" --substance "SLS,Menthol"

Usage:
  python analyse_product_exposures.py
  python analyse_product_exposures.py --category medication
  python analyse_product_exposures.py --person partner

@tier        heuristic
@refs        Simons FER, Ebisawa M, Sanchez-Borges M, et al. (2015). 2015 update of the evidence base: World Allergy Organization anaphylaxis guidelines. World Allergy Organization Journal, 8:32. doi:10.1186/s40413-015-0080-1
             Worm M, Moneret-Vautrin A, Scherer K, et al. (2014). First European data from the network of severe allergic reactions (NORA). Allergy, 69(10):1397-1404. doi:10.1111/all.12475

@relevance.de  Analysiert Expositionen gegenüber Haushalts- und Konsumprodukten, essentiell für die Identifikation potenzieller toxischer Belastungen und allergischer Auslöser
@relevance.en  Analyzes exposures to household and consumer products, essential for identifying potential toxic exposures and allergic triggers
@purpose.de  Wertet Produktexpositionen (Medikamente, Kosmetik, Zahnpflege, Haushaltsmittel)
             gegen Symptomeinträge aus: Kalender, Substanz-Häufigkeit, Ko-Auftreten und
             Zeitversatz-Analyse (0–2 Tage).
@purpose.en  Cross-analyses product exposures (medications, cosmetics, dental care,
             household products) against symptom entries: calendar, substance frequency,
             co-occurrence and time-lag analysis (0–2 days).
@method.de   Ko-Auftreten Exposition × Symptom als Verhältnis (Tage mit/ohne); Spearman-
             Korrelation für quantitative Symptomscores. Zeitversatz 0–2 Tage. Keine
             Confounder-Kontrolle, kein statistisches Testverfahren mit Korrekturniveau.
@method.en   Co-occurrence exposure × symptom as ratio (days with/without); Spearman
             correlation for quantitative symptom scores. Time lag 0–2 days. No confounder
             control, no statistical test with correction level.
@limits.de   Heuristische Methode: Kausalitätsnachweis nicht möglich. Expositions-Logging ist lückenhaft
             (manuelle Eingabe). n=1, explorative Hypothesengenerierung.
@limits.en   Heuristic method: Causality cannot be established. Exposure logging is incomplete (manual
             input). n=1, exploratory hypothesis generation.
@scoring
    Exposure categories: medication | cosmetics | dental | household | food | other
    Time lag: 0 days | +1 day | +2 days (exposure to symptom onset)
    Co-occurrence: days with exposure AND symptoms vs days with exposure only
@reads       product_exposures, symptoms, weather_station
@writes      Konsolenausgabe (kein analyses/-Verzeichnis, kein DB-Write)

@usage
    python analyse_product_exposures.py
    python analyse_product_exposures.py --help
    python analyse_product_exposures.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from log_exposure import setup_table as setup_exposure_table, CAT_LABELS_DE, CATEGORIES
from modules.prompts.analysis_environment import (
    SYSTEM_PROMPT_ANALYSE_PRODUCT_EXPOSURES_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_PRODUCT_EXPOSURES_EN as SYSTEM_PROMPT_EN,
)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

_cfg = _Cfg()
DB_PATH = _cfg.db_path

# ── Symptom-Gruppen die für Kontakt-/Chemikalienallergien relevant sind ───────

SYMPTOM_GROUPS: dict[str, list[str]] = {
    "Haut":        ["Hautausschlag", "Trockene Haut", "Juckreiz"],
    "GI":          ["Blähungen", "Durchfall", "Bauchschmerzen", "Übelkeit",
                    "Sodbrennen", "Aufstoßen"],
    "Atemwege":    ["Schnupfen", "Verstopfte Nase", "Husten", "Halsschmerzen",
                    "Atemnot (physiologisch)", "Keuchen/Atemgeräusche"],
    "Auge":        ["Trockenes Auge", "Augenschmerzen"],
    "Erschöpfung": ["Erschöpfung/Fatigue", "Körperschmerz"],
    "Neurologie":  ["Kopfschmerz", "Schwindel", "Tinnitus"],
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _spearman(x: list, y: list) -> tuple[float, float]:
    n = len(x)
    if n < 4:
        return float("nan"), float("nan")

    def ranks(lst):
        sv = sorted(enumerate(lst), key=lambda t: t[1])
        r  = [0.0] * n
        i  = 0
        while i < n:
            j = i
            while j < n - 1 and sv[j + 1][1] == sv[i][1]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[sv[k][0]] = avg_rank
            i = j + 1
        return r

    rx, ry = ranks(x), ranks(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx  = math.sqrt(sum((v - mx) ** 2 for v in rx))
    dy  = math.sqrt(sum((v - my) ** 2 for v in ry))
    if dx == 0 or dy == 0:
        return float("nan"), float("nan")
    rho    = num / (dx * dy)
    t_stat = rho * math.sqrt((n - 2) / max(1e-12, 1 - rho ** 2))
    z      = abs(t_stat) * math.sqrt(1 / (n - 1))
    p      = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    return round(rho, 3), round(p, 4)


def _symptom_score(conn: sqlite3.Connection, date_str: str,
                   symptom_list: list[str]) -> float:
    rows = conn.execute(
        "SELECT value_num FROM symptoms WHERE date=? AND symptom IN ({})".format(
            ",".join("?" * len(symptom_list))
        ),
        [date_str] + symptom_list,
    ).fetchall()
    return sum(r[0] or 0 for r in rows)


def _all_dates(conn: sqlite3.Connection, date_from: str | None = None, date_to: str | None = None) -> set[str]:
    date_filter = ""
    params = []
    if date_from:
        date_filter = "WHERE date >= ?"
        params.append(date_from)
    if date_to:
        if date_filter:
            date_filter += " AND date <= ?"
        else:
            date_filter = "WHERE date <= ?"
        params.append(date_to)
    return {r[0] for r in conn.execute(f"SELECT DISTINCT date FROM symptoms {date_filter}", params)}


# ── Report-Funktionen ─────────────────────────────────────────────────────────

def report_calendar(conn: sqlite3.Connection, person: str, category: str | None, 
                   date_from: str | None = None, date_to: str | None = None):
    """Show exposure entries per day per category."""
    print(t(
        "\n═══ Expositions-Kalender ═══════════════════════════════════════════",
        "\n═══ Exposure calendar ══════════════════════════════════════════════",
    ))

    filter_sql = "AND category=?" if category else ""
    date_filter = ""
    params = [person]
    if category:
        params.append(category)
    if date_from:
        date_filter = "AND date >= ?"
        params.append(date_from)
    if date_to:
        if date_filter:
            date_filter += " AND date <= ?"
        else:
            date_filter = "AND date <= ?"
        params.append(date_to)

    rows = conn.execute(f"""
        SELECT date, category, COUNT(*) n, GROUP_CONCAT(product, ' | ') products
        FROM product_exposures
        WHERE person=? {filter_sql} {date_filter}
        GROUP BY date, category
        ORDER BY date DESC, category
    """, params).fetchall()

    if not rows:
        print(t(
            "  Noch keine Expositions-Einträge. Nutze: python log_exposure.py add ...",
            "  No exposure entries yet. Use: python log_exposure.py add ...",
        ))
        return

    cur_date = None
    for d, cat, n, prods in rows:
        if d != cur_date:
            print(f"\n  {d}")
            cur_date = d
        label = CAT_LABELS_DE.get(cat, cat)
        print(f"    [{label}]  {prods[:70]}")


def report_substances(conn: sqlite3.Connection, person: str, category: str | None,
                     date_from: str | None = None, date_to: str | None = None):
    """Frequency table of all logged substances."""
    print(t(
        "\n═══ Substanz-Häufigkeit ════════════════════════════════════════════",
        "\n═══ Substance frequency ════════════════════════════════════════════",
    ))

    filter_sql = "AND category=?" if category else ""
    date_filter = ""
    params = [person]
    if category:
        params.append(category)
    if date_from:
        date_filter = "AND date >= ?"
        params.append(date_from)
    if date_to:
        if date_filter:
            date_filter += " AND date <= ?"
        else:
            date_filter = "AND date <= ?"
        params.append(date_to)

    rows = conn.execute(f"""
        SELECT substance FROM product_exposures
        WHERE person=? AND substance IS NOT NULL {filter_sql} {date_filter}
    """, params).fetchall()

    if not rows:
        print(t(
            "  Keine Substanzeinträge vorhanden (--substance beim Loggen angeben).",
            "  No substance entries found (use --substance when logging).",
        ))
        return

    freq: dict[str, int] = defaultdict(int)
    for (subst_str,) in rows:
        for s in subst_str.split(","):
            s = s.strip()
            if s:
                freq[s] += 1

    ranked = sorted(freq.items(), key=lambda x: -x[1])
    print(f"\n  {'Substanz':<30} Einträge")
    print(f"  {'-'*30} ────────")
    for subst, cnt in ranked:
        bar = "█" * min(cnt, 20)
        print(f"  {subst:<30} {cnt:3}  {bar}")


def report_cooccurrence(
    conn: sqlite3.Connection,
    person: str,
    category: str | None,
    lag_days: int = 0,
    date_from: str | None = None,
    date_to: str | None = None,
):
    """For each exposure category: show symptom co-occurrence (same day or +lag)."""
    title_sfx = (
        t(" (gleicher Tag)", " (same day)") if lag_days == 0
        else t(f" (+{lag_days} Tag{'e' if lag_days>1 else ''} Verzögerung)",
               f" (+{lag_days} day{'s' if lag_days>1 else ''} lag)")
    )
    print(t(
        f"\n═══ Ko-Auftreten: Exposition × Symptome{title_sfx} ══════════════════",
        f"\n═══ Co-occurrence: exposure × symptoms{title_sfx} ═══════════════════",
    ))

    cats = [category] if category else CATEGORIES
    all_sym_dates = _all_dates(conn, date_from, date_to)

    print(f"\n  {'Kategorie':<20}" + "".join(f"{k[:8]:<9}" for k in SYMPTOM_GROUPS) + "  Tage")
    print(f"  {'-'*20}" + "-" * (9 * len(SYMPTOM_GROUPS)) + "  ----")

    for cat in cats:
        date_filter_exp = ""
        params_exp = [person, cat]
        if date_from:
            date_filter_exp = "AND date >= ?"
            params_exp.append(date_from)
        if date_to:
            if date_filter_exp:
                date_filter_exp += " AND date <= ?"
            else:
                date_filter_exp = "AND date <= ?"
            params_exp.append(date_to)
        
        exp_dates = {r[0] for r in conn.execute(
            f"SELECT DISTINCT date FROM product_exposures WHERE person=? AND category=? {date_filter_exp}",
            params_exp
        )}
        if not exp_dates:
            continue

        # Shift dates by lag
        target_dates = {
            (date.fromisoformat(d) + timedelta(days=lag_days)).isoformat()
            for d in exp_dates
        }
        overlap = target_dates & all_sym_dates

        if not overlap:
            label = CAT_LABELS_DE.get(cat, cat)[:19]
            print(f"  {label:<20}" + "  n/a      " * len(SYMPTOM_GROUPS) + f"  {len(exp_dates)}")
            continue

        sym_scores: dict[str, list[float]] = {g: [] for g in SYMPTOM_GROUPS}
        no_exp_dates = all_sym_dates - target_dates

        for d in sorted(overlap):
            for grp, symptoms in SYMPTOM_GROUPS.items():
                sym_scores[grp].append(_symptom_score(conn, d, symptoms))

        # Baseline on non-exposure symptom days
        baseline: dict[str, float] = {}
        for grp, symptoms in SYMPTOM_GROUPS.items():
            vals = [_symptom_score(conn, d, symptoms) for d in no_exp_dates]
            baseline[grp] = sum(vals) / len(vals) if vals else 0.0

        label = CAT_LABELS_DE.get(cat, cat)[:19]
        row_str = f"  {label:<20}"
        for grp in SYMPTOM_GROUPS:
            scores = sym_scores[grp]
            mean_exp = sum(scores) / len(scores) if scores else 0
            base     = baseline[grp]
            if mean_exp == 0 and base == 0:
                row_str += f"{'·':>9}"
            elif base == 0:
                row_str += f"{'↑':>9}"
            else:
                delta = mean_exp - base
                arrow = "↑" if delta > 0.2 else ("↓" if delta < -0.2 else "=")
                row_str += f"{mean_exp:>6.1f}{arrow:>2} "
        row_str += f"  {len(overlap)}"
        print(row_str)

    print(t(
        "\n  Legende: Mittelwert (Tage mit Exposition) ↑>Basis ↓<Basis =≈Basis",
        "\n  Legend:  Mean score (exposure days) ↑>baseline ↓<baseline =≈baseline",
    ))


def report_lag_analysis(conn: sqlite3.Connection, person: str, category: str | None):
    """Show symptom load for lag 0, +1, +2 days after exposure."""
    print(t(
        "\n═══ Zeitversatz-Analyse (gleicher Tag / +1 / +2 Tage) ══════════════",
        "\n═══ Lag analysis (same day / +1 / +2 days) ═════════════════════════",
    ))

    cats = [category] if category else CATEGORIES
    all_sym_grp = [s for syms in SYMPTOM_GROUPS.values() for s in syms]

    print(f"\n  {'Kategorie':<20} {'Lag 0':>8} {'Lag +1':>8} {'Lag +2':>8}  {'n Exp':>6}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}  {'-'*6}")

    for cat in cats:
        exp_dates = sorted({r[0] for r in conn.execute(
            "SELECT DISTINCT date FROM product_exposures WHERE person=? AND category=?",
            (person, cat)
        )})
        if not exp_dates:
            continue

        means = []
        for lag in range(3):
            scores = []
            for d in exp_dates:
                shifted = (date.fromisoformat(d) + timedelta(days=lag)).isoformat()
                scores.append(_symptom_score(conn, shifted, all_sym_grp))
            means.append(sum(scores) / len(scores) if scores else 0.0)

        label = CAT_LABELS_DE.get(cat, cat)[:19]
        # Mark the lag with highest mean
        max_m = max(means)
        cells = []
        for m in means:
            mark = " *" if (m == max_m and max_m > 0) else "  "
            cells.append(f"{m:>6.2f}{mark}")
        print(f"  {label:<20} {'  '.join(cells)}  {len(exp_dates):>6}")

    print(t(
        "\n  * = höchste mittlere Symptombelastung nach Exposition",
        "\n  * = highest mean symptom load following exposure",
    ))


def _ensure_solar_view(conn: sqlite3.Connection) -> None:
    """Create v_solar view merging local Ecowitt + Open-Meteo data.

    Priority: weather_station (Ecowitt, local sensor) > biometeo (Open-Meteo).
    sunshine_h is only available from Open-Meteo.
    Unit conversion: solar_wm2 * 86400 / 1e6 = solar_mj_m2 (daily total).
    """
    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_solar AS
        SELECT
            d.date,
            -- UV: Ecowitt (local) > DWD station (nearby) > Open-Meteo (model)
            COALESCE(ws.uv_index_max, dwd.uv_index, bm.uv_index_max) AS uv_index_max,
            -- Solar W/m²: Ecowitt > DWD station > Open-Meteo (converted)
            COALESCE(ws.solar_wm2_max, dwd.solar_wm2,
                CASE WHEN bm.solar_mj_m2 IS NOT NULL
                     THEN ROUND(bm.solar_mj_m2 * 1000000.0 / 86400.0, 1)
                     ELSE NULL END)                              AS solar_wm2,
            -- Solar MJ/m²: Open-Meteo > convert from Ecowitt/DWD
            COALESCE(bm.solar_mj_m2,
                CASE WHEN ws.solar_wm2_max IS NOT NULL
                     THEN ROUND(ws.solar_wm2_max * 86400.0 / 1000000.0, 3)
                     WHEN dwd.solar_wm2 IS NOT NULL
                     THEN ROUND(dwd.solar_wm2 * 86400.0 / 1000000.0, 3)
                     ELSE NULL END)                              AS solar_mj_m2,
            -- Sunshine hours: Ecowitt CSV (computed) > DWD/AEMET station > Open-Meteo
            COALESCE(dwd.sunshine_h, bm.sunshine_h) AS sunshine_h,
            dwd.cloud_pct                                        AS cloud_pct,
            CASE
                WHEN ws.date  IS NOT NULL THEN 'ecowitt'
                ELSE '' END
            || CASE WHEN dwd.date IS NOT NULL THEN '+dwd'    ELSE '' END
            || CASE WHEN bm.date  IS NOT NULL THEN '+open_meteo' ELSE '' END
                                                                 AS src
        FROM (
            SELECT date FROM weather_station
            UNION SELECT date FROM weather_dwd_station
            UNION SELECT date FROM biometeo
        ) d
        LEFT JOIN weather_station     ws  ON ws.date  = d.date
        LEFT JOIN weather_dwd_station dwd ON dwd.date = d.date
        LEFT JOIN biometeo            bm  ON bm.date  = d.date
    """)


def report_sun_allergy(conn: sqlite3.Connection, person: str):
    """Detailed UV × skin symptom analysis with lag."""
    _ensure_solar_view(conn)
    print(t(
        "\n═══ Sonnenallergie-Report (UV/Solar × Haut-Symptome) ═══════════════",
        "\n═══ Sun allergy report (UV/solar × skin symptoms) ══════════════════",
    ))

    SKIN_SYM = ["Hautausschlag", "Trockene Haut", "Lichtempfindlichkeit",
                 "tag_generic_sun", "Juckreiz"]

    # UV source breakdown
    src_counts = dict(conn.execute(
        "SELECT src, COUNT(*) FROM v_solar GROUP BY src"
    ).fetchall())
    n_ecowitt = src_counts.get("ecowitt", 0) + src_counts.get("ecowitt+open_meteo", 0)
    n_om      = src_counts.get("open_meteo", 0) + src_counts.get("ecowitt+open_meteo", 0)

    has_uv = conn.execute(
        "SELECT COUNT(*) FROM v_solar WHERE uv_index_max IS NOT NULL"
    ).fetchone()[0] > 0

    uv_col   = "uv_index_max" if has_uv else "solar_mj_m2"
    uv_label = "UV-Index" if has_uv else "Solar MJ/m²"

    # Collect per-date UV + skin symptoms (same day AND next day lag)
    bio_rows = conn.execute(
        f"SELECT date, {uv_col}, sunshine_h FROM v_solar "
        f"WHERE {uv_col} IS NOT NULL ORDER BY date"
    ).fetchall()

    if not bio_rows:
        print(t("  Keine Solar-Daten vorhanden.", "  No solar data available."))
        return

    print(t(
        f"  UV-Quelle: {uv_label}  "
        f"(Ecowitt: {n_ecowitt} Tage | Open-Meteo: {n_om} Tage)",
        f"  UV source: {uv_label}  "
        f"(Ecowitt: {n_ecowitt} days | Open-Meteo: {n_om} days)",
    ))

    # Percentile thresholds for "high UV day"
    uv_vals_all = sorted(r[1] for r in bio_rows if r[1] is not None)
    p75 = uv_vals_all[int(len(uv_vals_all) * 0.75)] if uv_vals_all else 0

    print(t(f"  75. Perzentil: {p75:.1f} {uv_label}",
            f"  75th percentile: {p75:.1f} {uv_label}"))

    high_uv_days  = {r[0] for r in bio_rows if (r[1] or 0) >= p75}
    skin_sym_days = {r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM symptoms WHERE symptom IN ({}) "
        "AND COALESCE(value_num, 0) > 0".format(
            ",".join("?" * len(SKIN_SYM))
        ),
        SKIN_SYM,
    )}

    same_day  = high_uv_days & skin_sym_days
    next_day  = {
        (date.fromisoformat(d) + timedelta(days=1)).isoformat()
        for d in high_uv_days
    } & skin_sym_days

    n_high = len(high_uv_days)
    n_all  = len(bio_rows)

    print(t(
        f"\n  Tage mit hoher UV-/Solarstrahlung (≥ 75. Pz.): {n_high}/{n_all}",
        f"\n  High UV/solar days (≥ 75th pctile): {n_high}/{n_all}",
    ))
    print(t(
        f"  Haut-Symptome am gleichen Tag wie hoher UV: {len(same_day)} Tage",
        f"  Skin symptoms on same day as high UV: {len(same_day)} days",
    ))
    print(t(
        f"  Haut-Symptome am Tag NACH hohem UV (+1 Tag): {len(next_day)} Tage",
        f"  Skin symptoms the day AFTER high UV (+1 day): {len(next_day)} days",
    ))

    if same_day or next_day:
        print(t("\n  Betroffene Tage:", "\n  Affected days:"))
        for d in sorted(same_day | next_day):
            lag  = "(gleicher Tag)" if d in same_day else "(+1 Tag)"
            uv_r = conn.execute(
                f"SELECT {uv_col}, sunshine_h FROM v_solar WHERE date=? LIMIT 1", (d,)
            ).fetchone()
            syms = conn.execute(
                "SELECT symptom, value_num FROM symptoms WHERE date=? AND symptom IN ({})".format(
                    ",".join("?" * len(SKIN_SYM))
                ),
                [d] + SKIN_SYM,
            ).fetchall()
            uv_str   = f"{uv_r[0]:.1f} {uv_label}" if uv_r else "–"
            sym_str  = ", ".join(f"{r[0]} ({r[1] or 0:.0f})" for r in syms)
            print(f"    {d}  {lag:<15}  UV: {uv_str}  → {sym_str}")

    # Correlation: all days
    bio_map = {r[0]: (r[1] or 0) for r in bio_rows}
    all_dates_sorted = sorted(bio_map)
    uv_series  = [bio_map[d] for d in all_dates_sorted]
    sym_series = [_symptom_score(conn, d, SKIN_SYM) for d in all_dates_sorted]

    if len([v for v in sym_series if v > 0]) >= 3 and len(all_dates_sorted) >= 5:
        rho, p = _spearman(uv_series, sym_series)
        sig = "**" if p < 0.01 else ("*" if p < 0.05 else "n.s.")
        print(t(
            f"\n  Spearman ρ ({uv_label} × Haut-Symptome, alle Tage): "
            f"{rho:+.3f}  p={p:.4f}  {sig}",
            f"\n  Spearman ρ ({uv_label} × skin symptoms, all days): "
            f"{rho:+.3f}  p={p:.4f}  {sig}",
        ))
    else:
        print(t(
            "\n  Zu wenig Haut-Symptomeinträge für Korrelationsanalyse.",
            "\n  Insufficient skin symptom entries for correlation analysis.",
        ))

    # Manual sun exposure log
    sun_exp = conn.execute("""
        SELECT date, product, substance, notes
        FROM product_exposures
        WHERE category='environment' AND person=?
          AND (substance LIKE '%UV%' OR substance LIKE '%Sonne%'
               OR product LIKE '%Sonne%' OR notes LIKE '%Sonne%')
        ORDER BY date
    """, (person,)).fetchall()
    if sun_exp:
        print(t("\n  Manuell geloggte Sonnen-Expositionen:",
                "\n  Manually logged sun exposures:"))
        for d, prod, subst, notes in sun_exp:
            print(f"    {d}  {prod}"
                  + (f" | {subst}" if subst else "")
                  + (f" → {notes}" if notes else ""))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Exposition × Symptom-Analyse (Medikamente, Kosmetik, UV, ...)",
            "Exposure × symptom analysis (medications, cosmetics, UV, ...)",
        )
    )
    parser.add_argument("--category", "-c", choices=CATEGORIES, default=None,
                        help=t("Nur diese Kategorie", "Filter by category"))
    parser.add_argument("--person", default=OWN_PERSON_ID)
    parser.add_argument("--from", dest="date_from", default=None,
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to", dest="date_to", default=None,
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--lag", type=int, default=None,
                        help=t("Zeitversatz in Tagen für Ko-Auftreten (default: alle 0-2)",
                               "Lag in days for co-occurrence (default: show 0-2)"))
    parser.add_argument("--sun-only", action="store_true",
                        help=t("Nur Sonnenallergie-Report", "Only sun allergy report"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plots speichern", "Save plots"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("KI-Kommentare deaktivieren", "Disable AI commentary"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    setup_exposure_table(conn)

    from modules.llm import capture_stdout

    with capture_stdout() as buf:
        if args.sun_only:
            try:
                report_sun_allergy(conn, args.person)
            except Exception as e:
                print(t(f"Sonnen-/UV-Analyse übersprungen (Wetterdaten fehlen): {e}",
                    f"Sun/UV analysis skipped (weather data missing): {e}"))
        else:
            report_calendar(conn, args.person, args.category, args.date_from, args.date_to)
            report_substances(conn, args.person, args.category, args.date_from, args.date_to)

            if args.lag is not None:
                report_cooccurrence(conn, args.person, args.category, lag_days=args.lag,
                                   date_from=args.date_from, date_to=args.date_to)
            else:
                report_cooccurrence(conn, args.person, args.category, lag_days=0,
                                   date_from=args.date_from, date_to=args.date_to)
                report_lag_analysis(conn, args.person, args.category)

            try:
                report_sun_allergy(conn, args.person)
            except Exception as e:
                print(t(f"Sonnen-/UV-Analyse übersprungen (Wetterdaten fehlen): {e}",
                        f"Sun/UV analysis skipped (weather data missing): {e}"))

    if not args.no_llm:
        llm_text = _run_llm(buf.getvalue())
        if llm_text:
            print(t("\n══ KLINISCHE INTERPRETATION ══", "\n══ CLINICAL INTERPRETATION ══"))
            print(llm_text)

    conn.close()


if __name__ == "__main__":
    main()
