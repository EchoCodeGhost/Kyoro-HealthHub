#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Sport × Umwelt-Analyse

Korreliert Trainingseinheiten (Sportart, Dauer, Load) mit Umweltdaten
(Pollen, Luftqualität, UV-Index, Temperatur) für denselben Tag.
Bestimmt Trainingsstandort aus GPS-Tracks oder Aufenthaltshistorie.

Plots:
  1. Zeitreihe: Trainingshäufigkeit + Pollenbelastung
  2. Sportart × Pollensaison (Heatmap)
  3. Trainingsintensität × Luftqualität / UV
  4. Sport-Standortverteilung (Heim vs. Reise)

@tier        heuristic
@refs        D'Amato G, Cecchi L, Bonini S, Nunes C, Annesi-Maesano I, Behrendt H, Liccardi G, Popov T, Van Cauwenberge P (2007). Allergenic pollen and pollen allergy in Europe. Allergy, 62(9):976-990. doi:10.1111/j.1398-9995.2007.01393.x
             Brook RD, Rajagopalan S, Pope CA et al. (2010). Particulate Matter Air Pollution and Cardiovascular Disease. Circulation, 121(21):2331-2378. doi:10.1161/CIR.0b013e3181dbece1

@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@purpose.de  Korreliert Trainingseinheiten (Sportart, Dauer, Load) mit Umweltdaten (Pollen, Luftqualität, UV, Temperatur) unter Berücksichtigung des Trainingsstandorts via GPS.
@purpose.en  Correlates training sessions (sport type, duration, load) with environmental data (pollen, air quality, UV, temperature) taking training location via GPS into account.
@method.de   Spearman-Rangkorrelation zwischen Pollenbelastung/AQI und Trainingsparametern; GPS-Zentroid aus session_tracks oder location_stays; Standort-Matching mit ±1-Tag-Toleranz.
@method.en   Spearman rank correlation between pollen load/AQI and training parameters; GPS centroid from session_tracks or location_stays; location matching with ±1-day tolerance.
@limits.de   Heuristische Methode: Keine Kausalitätsaussage; Pollenexposition abhängig von Quell- und Gebietsgenauigkeit; kein personalisierter Allergie-Schwellenwert; GPS-Daten nicht immer vorhanden.
@limits.en   Heuristic method: No causal inference; pollen exposure depends on source and location accuracy; no personalised allergy threshold; GPS data not always available.
@scoring
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
    Location type: home | travel | mixed
@reads       sessions, session_metrics, pollen, air_quality, biometeo, session_tracks, location_stays, symptoms
@writes      analyses/activity/*.{md,png}

Usage:
  python analyse_sport_environment.py
  python analyse_sport_environment.py --from 2022-01-01 --plot
  python analyse_sport_environment.py --no-llm

@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_PROMPT
@prompt.en    SYSTEM_PROMPT
@usage
    python analyse_sport_environment.py
    python analyse_sport_environment.py --help
    python analyse_sport_environment.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_activity import SYSTEM_PROMPT_ANALYSE_SPORT_ENVIRONMENT_STR as SYSTEM_PROMPT

_cfg    = _Cfg()
DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "activity"

POLLEN_COLS = ["birch", "alder", "grass", "mugwort", "ragweed", "olive"]
POLLEN_DE   = {"birch": "Birke", "alder": "Erle", "grass": "Gräser",
               "mugwort": "Beifuß", "ragweed": "Ragweed", "olive": "Olive"}

SEASON_MAP = {1: "Winter", 2: "Winter", 3: "Frühling", 4: "Frühling",
              5: "Frühling", 6: "Sommer", 7: "Sommer", 8: "Sommer",
              9: "Herbst", 10: "Herbst", 11: "Herbst", 12: "Winter"}


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def spearman_r(xs: list, ys: list) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)
    rank_x = _ranks([p[0] for p in pairs])
    rank_y = _ranks([p[1] for p in pairs])
    d2 = sum((rx - ry) ** 2 for rx, ry in zip(rank_x, rank_y))
    denom = n * (n ** 2 - 1)
    return 1 - 6 * d2 / denom if denom else None


def _ranks(vals: list) -> list:
    indexed = sorted(enumerate(vals), key=lambda x: x[1])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) - 1 and indexed[j][1] == indexed[j + 1][1]:
            j += 1
        avg = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg
        i = j + 1
    return ranks


def pollen_level(row: dict) -> float | None:
    vals = [row.get(c) for c in POLLEN_COLS if row.get(c) is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def aq_index(row: dict) -> float | None:
    v = row.get('aqi_eu_mean')
    if v is not None:
        return float(v)
    pm = row.get('pm25_mean')
    return float(pm) if pm is not None else None


def _gps_centroid(conn: sqlite3.Connection, session_id: str) -> tuple[float, float] | None:
    row = conn.execute(
        "SELECT AVG(lat), AVG(lon) FROM session_tracks WHERE session_id=?",
        (session_id,)
    ).fetchone()
    if row and row[0] is not None:
        return float(row[0]), float(row[1])
    return None


def _travel_location(conn: sqlite3.Connection, date_s: str,
                     ts_start: str) -> tuple[float, float] | None:
    """Look up lat/lon from location_stays if session is away from home."""
    try:
        row = conn.execute("""
            SELECT lat, lon FROM location_stays
            WHERE is_home = 0
              AND start_ts <= ? AND end_ts >= ?
            LIMIT 1
        """, (ts_start or date_s + 'T23:59:59', ts_start or date_s + 'T00:00:00')).fetchone()
        if row:
            return float(row[0]), float(row[1])
    except Exception:
        pass
    return None


def _closest_env(env: dict, date_s: str,
                 lat: float | None, lon: float | None) -> dict:
    """Find closest env record by (date, lat, lon).

    Priority:
    1. Exact (date, lat, lon) match
    2. Same date, closest lat/lon
    3. ±1 day at closest lat/lon
    """
    rlat = round(lat, 2) if lat else None
    rlon = round(lon, 2) if lon else None

    # Exact match
    if rlat is not None and rlon is not None:
        exact = env.get((date_s, rlat, rlon))
        if exact:
            return exact

    # Same date, closest location
    best = {}
    best_dist = float('inf')
    d_obj = datetime.strptime(date_s, '%Y-%m-%d')
    for delta in [0, 1, -1, 2, -2]:
        d_key = (d_obj + timedelta(days=delta)).strftime('%Y-%m-%d')
        candidates = [(k, v) for k, v in env.items() if k[0] == d_key]
        for (_, elat, elon), v in candidates:
            dist = (((rlat or elat) - elat) ** 2 +
                    ((rlon or elon) - elon) ** 2) ** 0.5 if rlat else 0
            if dist < best_dist:
                best_dist = dist
                best = v
        if best and delta == 0:
            return best   # same-day match good enough
    return best


# ── Daten laden ────────────────────────────────────────────────────────────────

def load_sessions(conn: sqlite3.Connection, d_from: str, d_to: str) -> list[dict]:
    rows = conn.execute("""
        SELECT s.id, s.date, s.ts_start, s.sport,
               MAX(CASE WHEN sm.metric='duration_s'    THEN sm.value END) AS dur_s,
               MAX(CASE WHEN sm.metric='training_load' THEN sm.value END) AS load,
               MAX(CASE WHEN sm.metric='hr_avg'        THEN sm.value END) AS hr_avg,
               MAX(CASE WHEN sm.metric='distance_m'    THEN sm.value END) AS dist_m,
               MAX(CASE WHEN sm.metric='calories'      THEN sm.value END) AS kcal
        FROM sessions s
        LEFT JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'training'
          AND s.date >= ? AND s.date <= ?
        GROUP BY s.id
        HAVING dur_s IS NOT NULL AND dur_s > 60
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()

    sessions = []
    for sid, date_s, ts_start, sport, dur_s, load, hr_avg, dist_m, kcal in rows:
        sessions.append({
            'id': sid, 'date': date_s, 'ts_start': ts_start,
            'sport': sport or 'Unbekannt',
            'dur_min': round(float(dur_s) / 60, 1) if dur_s else None,
            'load': float(load) if load else None,
            'hr_avg': float(hr_avg) if hr_avg else None,
            'dist_m': float(dist_m) if dist_m else None,
            'kcal': float(kcal) if kcal else None,
        })
    return sessions


def _fetch_table(conn: sqlite3.Connection, table: str,
                 d_from: str, d_to: str) -> dict[tuple, dict]:
    """Return {(date, lat, lon): row_dict} for all rows in date range."""
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    result: dict[tuple, dict] = {}
    for row in conn.execute(
        f"SELECT * FROM {table} WHERE date >= ? AND date <= ? ORDER BY date",
        (d_from, d_to)
    ).fetchall():
        d = dict(zip(cols, row))
        key = (d['date'], round(float(d.get('lat', 0) or 0), 2),
               round(float(d.get('lon', 0) or 0), 2))
        result[key] = d
    return result


def load_environment(conn: sqlite3.Connection, d_from: str, d_to: str) -> dict:
    """Return {(date, lat, lon): env_dict} merged from all env tables."""
    env: dict[tuple, dict] = {}

    for table in ('pollen', 'air_quality', 'biometeo'):
        for key, row_dict in _fetch_table(conn, table, d_from, d_to).items():
            env.setdefault(key, {}).update(row_dict)

    return env


def load_symptoms(conn: sqlite3.Connection, d_from: str, d_to: str) -> dict:
    """Return {date: avg_severity} from symptoms table if available."""
    syms: dict[str, float] = {}
    try:
        for d_s, severity in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            syms[d_s] = round(float(severity), 2)
    except Exception:
        pass
    return syms


def sessions_with_gps(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT DISTINCT session_id FROM session_tracks").fetchall()
    return {r[0] for r in rows}


# ── Analyse ────────────────────────────────────────────────────────────────────

def analyse(sessions: list[dict], env: dict, symptoms: dict,
            gps_ids: set, conn: sqlite3.Connection) -> dict:
    result = {
        'total': len(sessions),
        'with_env': 0,
        'with_gps': 0,
        'sport_counts': defaultdict(int),
        'sport_dur_min': defaultdict(list),
        'sport_by_season': defaultdict(lambda: defaultdict(int)),
        'pollen_vs_dur': [],
        'aq_vs_dur': [],
        'uv_vs_hr': [],
        'pollen_by_sport': defaultdict(list),
        'outdoor_sports': {'Outdoorsport', 'Wandern', 'Laufen', 'Radfahren',
                           'Spazieren', 'SUP', 'Triathlon'},
        'high_pollen_outdoor': 0,
        'total_outdoor': 0,
        'correlations': {},
        'monthly_counts': defaultdict(int),
        'monthly_pollen': defaultdict(list),
    }

    for s in sessions:
        date_s = s['date']
        sport  = s['sport']
        season = SEASON_MAP.get(int(date_s[5:7]), '?')

        result['sport_counts'][sport] += 1
        if s['dur_min']:
            result['sport_dur_min'][sport].append(s['dur_min'])
        result['sport_by_season'][season][sport] += 1
        result['monthly_counts'][date_s[:7]] += 1

        # Standort: GPS-Zentroid > home
        if s['id'] in gps_ids:
            result['with_gps'] += 1
            coords = _gps_centroid(conn, s['id'])
        else:
            coords = None
        lat_use = coords[0] if coords else _cfg.home_lat
        lon_use = coords[1] if coords else _cfg.home_lon

        # Env lookup — bevorzuge standortgenaue Daten
        e = _closest_env(env, date_s, lat_use, lon_use)
        if not e:
            continue
        result['with_env'] += 1

        pl = pollen_level(e)
        aqi = aq_index(e)
        uv  = e.get('uv_index_max')

        if pl is not None:
            result['monthly_pollen'][date_s[:7]].append(pl)

        if s['dur_min']:
            if pl is not None:
                result['pollen_vs_dur'].append((pl, s['dur_min']))
                result['pollen_by_sport'][sport].append(pl)
            if aqi is not None:
                result['aq_vs_dur'].append((aqi, s['dur_min']))
            if uv is not None and s['hr_avg']:
                result['uv_vs_hr'].append((uv, s['hr_avg']))

        # Outdoor on high-pollen days
        if sport in result['outdoor_sports']:
            result['total_outdoor'] += 1
            if pl is not None and pl > 20:
                result['high_pollen_outdoor'] += 1

    # Spearman correlations
    if result['pollen_vs_dur']:
        xs, ys = zip(*result['pollen_vs_dur'])
        result['correlations']['pollen_vs_dur'] = spearman_r(list(xs), list(ys))
    if result['aq_vs_dur']:
        xs, ys = zip(*result['aq_vs_dur'])
        result['correlations']['aq_vs_dur'] = spearman_r(list(xs), list(ys))

    return result


# ── Text-Bericht ───────────────────────────────────────────────────────────────

def make_report(r: dict, d_from: str, d_to: str) -> str:
    lines = [
        f"# Sport × Umwelt-Analyse ({d_from} – {d_to})",
        f"\nAnalysiert: {r['total']} Trainingseinheiten, "
        f"davon {r['with_env']} mit Umweltdaten ({r['with_gps']} mit GPS-Track)\n",
        "## Sportartenverteilung\n",
    ]

    top = sorted(r['sport_counts'].items(), key=lambda x: -x[1])
    for sport, n in top[:12]:
        avg_dur = None
        durs = r['sport_dur_min'][sport]
        if durs:
            avg_dur = round(sum(durs) / len(durs), 0)
        avg_pollen = None
        pl_vals = r['pollen_by_sport'][sport]
        if pl_vals:
            avg_pollen = round(sum(pl_vals) / len(pl_vals), 1)
        dur_str = f", ⌀ {avg_dur:.0f} min" if avg_dur else ""
        pol_str = f", Pollen ⌀ {avg_pollen:.1f}" if avg_pollen else ""
        lines.append(f"- **{sport}**: {n}×{dur_str}{pol_str}")

    lines.append("\n## Saisonale Verteilung\n")
    for season in ["Frühling", "Sommer", "Herbst", "Winter"]:
        d = r['sport_by_season'][season]
        if not d:
            continue
        top3 = sorted(d.items(), key=lambda x: -x[1])[:3]
        top3_str = ", ".join(f"{s} ({n}×)" for s, n in top3)
        lines.append(f"- **{season}**: {sum(d.values())} Einheiten — {top3_str}")

    if r['pollen_vs_dur']:
        lines.append("\n## Pollen × Training\n")
        corr = r['correlations'].get('pollen_vs_dur')
        corr_str = f"(Spearman r={corr:.2f})" if corr is not None else ""
        lines.append(f"- Datenpunkte: {len(r['pollen_vs_dur'])} {corr_str}")
        pollen_vals = [x for x, _ in r['pollen_vs_dur']]
        avg_p = sum(pollen_vals) / len(pollen_vals)
        high_days = sum(1 for p in pollen_vals if p > 20)
        lines.append(f"- Ø Pollenindex an Trainingstagen: {avg_p:.1f}")
        lines.append(f"- Trainingstage mit hoher Pollenbelastung (>20): {high_days}/{len(pollen_vals)}")
        lines.append(f"- Outdoor-Trainings bei hohem Pollen: "
                     f"{r['high_pollen_outdoor']}/{r['total_outdoor']}")

    if r['aq_vs_dur']:
        lines.append("\n## Luftqualität × Training\n")
        corr = r['correlations'].get('aq_vs_dur')
        corr_str = f"(Spearman r={corr:.2f})" if corr is not None else ""
        lines.append(f"- Datenpunkte: {len(r['aq_vs_dur'])} {corr_str}")
        aqi_vals = [x for x, _ in r['aq_vs_dur']]
        avg_aqi = sum(aqi_vals) / len(aqi_vals)
        high_aqi = sum(1 for v in aqi_vals if v > 50)
        lines.append(f"- Ø AQI an Trainingstagen: {avg_aqi:.1f}")
        lines.append(f"- Trainingstage mit erhöhter AQI (>50): {high_aqi}/{len(aqi_vals)}")

    if r['uv_vs_hr']:
        lines.append("\n## UV × Herzfrequenz\n")
        uv_vals = [u for u, _ in r['uv_vs_hr']]
        hr_vals = [h for _, h in r['uv_vs_hr']]
        lines.append(f"- Datenpunkte: {len(r['uv_vs_hr'])}")
        lines.append(f"- Ø UV-Index: {sum(uv_vals)/len(uv_vals):.1f}, "
                     f"Ø HF: {sum(hr_vals)/len(hr_vals):.0f} bpm")

    return "\n".join(lines)


# ── Plots ──────────────────────────────────────────────────────────────────────

def make_plots(sessions: list[dict], env: dict, r: dict,
               d_from: str, d_to: str) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
        import numpy as np
    except ImportError:
        return None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), facecolor="#1e1e2e")
    bg, fg = "#1e1e2e", "#cdd6f4"
    for ax in axes.flat:
        ax.set_facecolor("#313244")
        ax.tick_params(colors=fg, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#45475a")

    # ── Plot 1: Monatsübersicht Trainings + Pollen ──────────────────────────
    ax1 = axes[0, 0]
    months = sorted(r['monthly_counts'].keys())
    if months:
        counts = [r['monthly_counts'][m] for m in months]
        x = list(range(len(months)))
        ax1.bar(x, counts, color="#89b4fa", alpha=0.8, label="Trainings")
        pollen_avgs = [
            (sum(r['monthly_pollen'][m]) / len(r['monthly_pollen'][m])
             if r['monthly_pollen'][m] else 0)
            for m in months
        ]
        ax2_twin = ax1.twinx()
        ax2_twin.set_facecolor("#313244")
        ax2_twin.tick_params(colors="#f38ba8", labelsize=7)
        ax2_twin.plot(x, pollen_avgs, color="#f38ba8", lw=1.5,
                      marker='o', markersize=3, label="Ø Pollen")
        ax2_twin.set_ylabel("Ø Pollenindex", color="#f38ba8", fontsize=8)
        xtick_step = max(1, len(months) // 10)
        ax1.set_xticks(x[::xtick_step])
        ax1.set_xticklabels(months[::xtick_step], rotation=45, ha='right', fontsize=7)
    ax1.set_title("Trainings / Monat + Pollenbelastung", color=fg, fontsize=9)
    ax1.set_ylabel("Trainingseinheiten", color=fg, fontsize=8)

    # ── Plot 2: Sport × Saison Heatmap ─────────────────────────────────────
    ax2 = axes[0, 1]
    seasons = ["Frühling", "Sommer", "Herbst", "Winter"]
    top_sports = [s for s, _ in sorted(r['sport_counts'].items(),
                                        key=lambda x: -x[1])[:8]]
    if top_sports:
        matrix = np.zeros((len(top_sports), len(seasons)))
        for i, sp in enumerate(top_sports):
            for j, sea in enumerate(seasons):
                matrix[i, j] = r['sport_by_season'][sea].get(sp, 0)
        ax2.imshow(matrix, cmap='Blues', aspect='auto')
        ax2.set_xticks(range(len(seasons)))
        ax2.set_xticklabels(seasons, color=fg, fontsize=8)
        ax2.set_yticks(range(len(top_sports)))
        ax2.set_yticklabels(top_sports, color=fg, fontsize=8)
        for i in range(len(top_sports)):
            for j in range(len(seasons)):
                v = int(matrix[i, j])
                if v > 0:
                    ax2.text(j, i, str(v), ha='center', va='center',
                             color='white', fontsize=7)
    ax2.set_title("Sportart × Saison", color=fg, fontsize=9)

    # ── Plot 3: Trainings-Dauer × Pollenbelastung ───────────────────────────
    ax3 = axes[1, 0]
    if r['pollen_vs_dur']:
        xs, ys = zip(*r['pollen_vs_dur'])
        ax3.scatter(xs, ys, color="#a6e3a1", alpha=0.5, s=15)
        # Trend
        if len(xs) > 5:
            z = np.polyfit(xs, ys, 1)
            p = np.poly1d(z)
            xi = np.linspace(min(xs), max(xs), 100)
            ax3.plot(xi, p(xi), color="#f9e2af", lw=1.5, ls='--', alpha=0.8)
        corr = r['correlations'].get('pollen_vs_dur')
        title_suffix = f" (r={corr:.2f})" if corr is not None else ""
        ax3.set_xlabel("Ø Pollenindex", color=fg, fontsize=8)
        ax3.set_ylabel("Dauer (min)", color=fg, fontsize=8)
    ax3.set_title(f"Dauer × Pollen{title_suffix if r['pollen_vs_dur'] else ''}", color=fg, fontsize=9)

    # ── Plot 4: Top Sportarten Balken ───────────────────────────────────────
    ax4 = axes[1, 1]
    top10 = sorted(r['sport_counts'].items(), key=lambda x: -x[1])[:10]
    if top10:
        sports_l, counts_l = zip(*top10)
        y_pos = list(range(len(sports_l)))
        colors = cm.tab10(np.linspace(0, 1, len(sports_l)))
        ax4.barh(y_pos, counts_l, color=colors, alpha=0.85)
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(sports_l, color=fg, fontsize=8)
        ax4.set_xlabel("Anzahl", color=fg, fontsize=8)
    ax4.set_title("Top Sportarten", color=fg, fontsize=9)

    plt.suptitle(f"Sport × Umwelt ({d_from} – {d_to})", color=fg, fontsize=11)
    plt.tight_layout()

    out = OUT_DIR / f"sport_environment_{ts}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=bg)
    plt.close()
    return out


# ── LLM ───────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=SYSTEM_PROMPT, max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report: str, llm_text: str, plot_path: Path | None) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"sport_environment_{ts}.md"
    content = report
    if plot_path:
        content += f"\n\n![Plot]({plot_path.name})\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    return out


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Sport × Umwelt-Analyse", "Sport × Environment analysis"))
    parser.add_argument("--from",   dest="date_from", metavar="DATE")
    parser.add_argument("--to",     dest="date_to",   metavar="DATE")
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plots ausgeben", "Generate plots"))
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    d_to   = args.date_to   or datetime.now().strftime('%Y-%m-%d')
    d_from = args.date_from or _cfg.birthdate or '2000-01-01'

    # Enable plot in batch mode
    do_plot = args.plot
    if not do_plot:
        import os
        do_plot = bool(os.environ.get('KYORO_ANALYSES_DIR'))

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    print(t("\n── Sport × Umwelt ───────────────────────────────────────",
            "\n── Sport × Environment ──────────────────────────────────"))

    sessions = load_sessions(conn, d_from, d_to)
    env      = load_environment(conn, d_from, d_to)
    symptoms = load_symptoms(conn, d_from, d_to)
    gps_ids  = sessions_with_gps(conn)

    print(t(f"  Sessions: {len(sessions)}, Umwelttage: {len(env)}, "
            f"Symptomtage: {len(symptoms)}",
            f"  Sessions: {len(sessions)}, Env days: {len(env)}, "
            f"Symptom days: {len(symptoms)}"))

    if not sessions:
        print(t("  Keine Daten im Zeitraum.", "  No data in range."))
        conn.close()
        return

    result  = analyse(sessions, env, symptoms, gps_ids, conn)
    report = make_report(result, d_from, d_to)

    print(report)

    plot_path = None
    if do_plot:
        plot_path = make_plots(sessions, env, result, d_from, d_to)
        if plot_path:
            print(t(f"\n  Plot: {plot_path}", f"\n  Plot: {plot_path}"))

    if not args.no_llm:
        llm_text = _run_llm(report)
        out = _save(report, llm_text, plot_path)
        print(t(f"  Bericht: {out}", f"  Report: {out}"))
    else:
        out = _save(report, "", plot_path)
        print(t(f"  Bericht: {out}", f"  Report: {out}"))

    conn.close()


if __name__ == '__main__':
    main()
