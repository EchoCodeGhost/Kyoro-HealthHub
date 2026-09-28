#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Umgebungs- & Sleepqualitäts-Analyse

Analysiert den Zusammenhang zwischen Umgebungsparametern (Temperatur,
Humidity, Helligkeit/Lux, Sonnenstrahlung) and Sleepqualität
sowie HRV.

Datenquellen:
  - home_environment: Innenraum (Temperatur, Humidity, Lux)
  - weather_station: Outdoor temperature, Luftdruck, solar_wm2_max
  - daily_stress: Sleep (sleep_h), HRV, Stress-Score

@tier        heuristic
@purpose.de  Analysiert den Zusammenhang zwischen Innenraum- und Außenumgebungsparametern (Temperatur, Luftfeuchtigkeit, Lux, Luftdruck, Solarstrahlung) und Schlafqualität sowie HRV.
@purpose.en  Analyses the association between indoor and outdoor environmental parameters (temperature, humidity, lux, air pressure, solar radiation) and sleep quality as well as HRV.
@method.de   Spearman-Rangkorrelation zwischen Umgebungsparametern und Schlaf/HRV; eigene Optimalwertgrenzen (Schlafzimmer 16–19 °C, Luftfeuchte 40–60 %).
@method.en   Spearman rank correlation between environmental parameters and sleep/HRV; custom optimal value ranges (bedroom 16–19 °C, humidity 40–60 %).
@limits.de   Heuristische Methode: Beobachtungsstudie ohne Kausalitätsnachweis; Optimalwerte aus allgemeinen Schlafhygiene-Empfehlungen, nicht individuell validiert. Daten nur verfügbar wenn Home-Assistant-Sensoren vorhanden.
@limits.en   Heuristic method: Observational study without causal inference; optimal values from general sleep hygiene guidelines, not individually validated. Data only available if Home Assistant sensors are present.
@refs        Okamoto-Mizuno K, Mizuno K (2012). Effects of thermal environment on sleep and circadian rhythm. Journal of Physiological Anthropology, 31(1). doi:10.1186/1880-6805-31-14
             Hirshkowitz M, Whiton K, Albert SM et al. (2015). National Sleep Foundation’s sleep time duration recommendations: methodology and results summary. Sleep Health, 1(1):40-43. doi:10.1016/j.sleh.2014.12.010

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@scoring
    Indoor temperature: 16-19°C optimal bedroom (Lack & Gradisar 2019)
    Humidity: 40-60% optimal
    Lux: higher = brighter (daytime correlation)
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       home_environment, weather_station, daily_stress
@writes      analyses/sleep/*.{md,png}

Usage:
  python analyse_sleep_environment.py --plot
  python analyse_sleep_environment.py --from YYYY-MM-DD --plot
  python analyse_sleep_environment.py --plot --no-llm

@usage
    python analyse_sleep_environment.py
    python analyse_sleep_environment.py --help
    python analyse_sleep_environment.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_SLEEP_ENVIRONMENT_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SLEEP_ENVIRONMENT_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

TEMP_OPT_MIN = 16.0
TEMP_OPT_MAX = 19.0
FEUCHTE_OPT_MIN = 40.0
FEUCHTE_OPT_MAX = 60.0


def load_data(conn, d_from, d_to):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    env = defaultdict(dict)
    if "home_environment" in tables:
        for d, stype, mean_val in conn.execute("""
            SELECT date, sensor_type, AVG(mean_value)
            FROM home_environment
            WHERE date >= ? AND date <= ?
              AND sensor_type IN ('temperature', 'humidity', 'illuminance')
              AND mean_value IS NOT NULL
            GROUP BY date, sensor_type
        """, (d_from, d_to)):
            env[d][stype] = round(mean_val, 2)

    weather = {}
    if "weather_station" in tables:
        for row in conn.execute("""
            SELECT date, temp_out_c, humidity_out, solar_wm2_max, pressure_hpa
            FROM weather_station
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            weather[row[0]] = {
                "temp_out": row[1], "humidity_out": row[2],
                "solar": row[3], "pressure": row[4]
            }

    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, rhr, stress_s, sleep_h in conn.execute("""
            SELECT date, rmssd_ms, resting_hr, stress_score, sleep_hours
            FROM daily_stress WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = {"hrv": rmssd, "rhr": rhr, "stress": stress_s, "sleep_h": sleep_h}

    return dict(env), weather, stress


def spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)

    def ranks(vals):
        sorted_v = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sorted_v, 1):
            r[idx] = rank
        return r

    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    rs = 1 - 6 * d2 / (n * (n ** 2 - 1))
    return round(rs, 3)


def build_report(env, weather, stress, d_from, d_to):
    all_dates = sorted(set(list(env.keys()) + list(weather.keys())))
    if not all_dates:
        return "No Umgebungsdaten im angefragten Time range."

    # Aggregierte Statistiken Indoor
    temp_in_vals     = [env[d]["temperature"]  for d in all_dates if d in env and "temperature"  in env[d]]
    humidity_in_vals = [env[d]["humidity"]      for d in all_dates if d in env and "humidity"      in env[d]]
    lux_vals         = [env[d]["illuminance"]   for d in all_dates if d in env and "illuminance"   in env[d]]

    # Outdoor
    temp_out_vals  = [weather[d]["temp_out"]  for d in all_dates if d in weather and weather[d]["temp_out"]]
    solar_vals     = [weather[d]["solar"]     for d in all_dates if d in weather and weather[d]["solar"]]
    pressure_vals  = [weather[d]["pressure"]  for d in all_dates if d in weather and weather[d]["pressure"]]

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None
    def pct_in_range(lst, lo, hi): return round(sum(1 for v in lst if lo <= v <= hi) / len(lst) * 100, 1) if lst else None

    lines = [
        f"## Umgebungs- & Sleep-Analyse — {d_from} bis {d_to}\n",
        f"days with Umgebungsdaten: **{len(all_dates)}**  |  "
        f"days with Schlafdaten: {sum(1 for d in all_dates if d in stress and stress[d].get('sleep_h'))}\n",
        "### Innenraum\n",
    ]

    if temp_in_vals:
        a = avg(temp_in_vals)
        p = pct_in_range(temp_in_vals, TEMP_OPT_MIN, TEMP_OPT_MAX)
        flag = "" if TEMP_OPT_MIN <= a <= TEMP_OPT_MAX else " ⚠"
        lines.append(f"  Temperatur (Innen): Ø {a} °C  |  "
                     f"Im Optimalbereich ({TEMP_OPT_MIN}–{TEMP_OPT_MAX} °C): {p}%{flag}")

    if humidity_in_vals:
        a = avg(humidity_in_vals)
        p = pct_in_range(humidity_in_vals, FEUCHTE_OPT_MIN, FEUCHTE_OPT_MAX)
        flag = "" if FEUCHTE_OPT_MIN <= a <= FEUCHTE_OPT_MAX else " ⚠"
        lines.append(f"  Humidity (Innen): Ø {a} %rF  |  "
                     f"Im Optimalbereich ({FEUCHTE_OPT_MIN:.0f}–{FEUCHTE_OPT_MAX:.0f}%): {p}%{flag}")

    if lux_vals:
        a = avg(lux_vals)
        lines.append(f"  Helligkeit (Innen, Lux): Ø {a} lx  |  "
                     f"Max: {max(lux_vals):.0f} lx")

    lines.append("\n### Außen\n")

    if temp_out_vals:
        lines.append(f"  Outdoor temperature: Ø {avg(temp_out_vals)} °C  |  "
                     f"Min: {min(temp_out_vals):.1f}  |  Max: {max(temp_out_vals):.1f}")

    if solar_vals:
        a = avg(solar_vals)
        n_hell = sum(1 for v in solar_vals if v > 400)
        lines.append(f"  Sonnenstrahlung: Ø {a} W/m²  |  "
                     f"Helle days (>400 W/m²): {n_hell}/{len(solar_vals)}")

    if pressure_vals:
        lines.append(f"  Luftdruck: Ø {avg(pressure_vals)} hPa  |  "
                     f"Min: {min(pressure_vals):.0f}  |  Max: {max(pressure_vals):.0f}")

    # Sleep-Statistiken
    sleep_vals = [stress[d]["sleep_h"] for d in all_dates if d in stress and stress[d].get("sleep_h")]
    hrv_vals   = [stress[d]["hrv"]     for d in all_dates if d in stress and stress[d].get("hrv")]
    if sleep_vals:
        lines.append(f"\n  Sleep (Ø): **{avg(sleep_vals)} h**  |  "
                     f"n={len(sleep_vals)} Nights")
    if hrv_vals:
        lines.append(f"  HRV RMSSD (Ø): **{avg(hrv_vals)} ms**  |  n={len(hrv_vals)}")

    # Correlationen
    pairs_map = {
        "Temp. Innen":    [env[d].get("temperature")  if d in env else None for d in all_dates],
        "Luftfeucht. In": [env[d].get("humidity")     if d in env else None for d in all_dates],
        "Lux Innen":      [env[d].get("illuminance")  if d in env else None for d in all_dates],
        "Solar (W/m²)":   [weather[d]["solar"]        if d in weather and weather[d]["solar"] else None for d in all_dates],
        "Temp. Außen":    [weather[d]["temp_out"]      if d in weather and weather[d]["temp_out"] else None for d in all_dates],
        "Luftdruck":      [weather[d]["pressure"]      if d in weather and weather[d]["pressure"] else None for d in all_dates],
    }
    sleep_y  = [stress[d]["sleep_h"] if d in stress and stress[d].get("sleep_h") else None for d in all_dates]
    hrv_y    = [stress[d]["hrv"]     if d in stress and stress[d].get("hrv")     else None for d in all_dates]
    stress_y = [stress[d]["stress"]  if d in stress and stress[d].get("stress")  else None for d in all_dates]

    corr_rows = []
    for label, xvals in pairs_map.items():
        r_sleep  = spearman_r(xvals, sleep_y)
        r_hrv    = spearman_r(xvals, hrv_y)
        r_stress = spearman_r(xvals, stress_y)
        if any(r is not None for r in [r_sleep, r_hrv, r_stress]):
            corr_rows.append((label, r_sleep, r_hrv, r_stress))

    if corr_rows:
        lines += [
            "\n### Correlation Umgebung × Sleep/HRV (Spearman r)\n",
            f"  {'Parameter':<22} {'× Sleep':>9} {'× HRV':>7} {'× Stress':>9}",
            "  " + "-" * 52,
        ]
        for label, r_s, r_h, r_st in corr_rows:
            lines.append(
                f"  {label:<22} "
                f"{str(r_s)  if r_s  is not None else 'n.a.':>9} "
                f"{str(r_h)  if r_h  is not None else 'n.a.':>7} "
                f"{str(r_st) if r_st is not None else 'n.a.':>9}")

    # Temperatur-Quartilanalyse
    if temp_in_vals and sleep_vals:
        sorted_temp_sleep = sorted(
            [(env[d].get("temperature"), stress[d]["sleep_h"])
             for d in all_dates
             if d in env and "temperature" in env[d]
             and d in stress and stress[d].get("sleep_h")],
            key=lambda x: x[0]
        )
        if len(sorted_temp_sleep) >= 8:
            q = len(sorted_temp_sleep) // 4
            kalt_sleep = [s for _, s in sorted_temp_sleep[:q]]
            warm_sleep = [s for _, s in sorted_temp_sleep[-q:]]
            avg_kalt = round(sum(kalt_sleep) / len(kalt_sleep), 2)
            avg_warm = round(sum(warm_sleep) / len(warm_sleep), 2)
            t_kalt   = round(sum(t for t, _ in sorted_temp_sleep[:q]) / q, 1)
            t_warm   = round(sum(t for t, _ in sorted_temp_sleep[-q:]) / q, 1)
            lines += [
                "\n### Sleep bei kühlen vs. warmen Indoor temperatureen\n",
                f"  Kälteste 25% (Ø {t_kalt} °C): Sleep Ø {avg_kalt} h",
                f"  Wärmste  25% (Ø {t_warm} °C): Sleep Ø {avg_warm} h",
            ]

    return "\n".join(lines)


def _plot(env, weather, stress, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    all_dates = sorted(set(list(env.keys()) + list(weather.keys())))

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"Umgebung & Sleep {d_from}–{d_to}", color="#E0E0E0", fontsize=13)

    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    dts = [datetime.fromisoformat(d) for d in all_dates]

    # Panel 1: Innen/Außen-Temperatur + Sleep
    temp_in  = [env[d].get("temperature") if d in env else None for d in all_dates]
    temp_out = [weather[d]["temp_out"]     if d in weather and weather[d]["temp_out"] else None for d in all_dates]

    def filter_none(ds, vs):
        return zip(*[(d, v) for d, v in zip(ds, vs) if v is not None]) if any(v is not None for v in vs) else ([], [])

    d_in, v_in   = filter_none(dts, temp_in)
    d_out, v_out = filter_none(dts, temp_out)

    if list(d_in):
        axes[0].plot(list(d_in), list(v_in), color="#fdcb6e", lw=1.2, label="Temp Innen")
    if list(d_out):
        axes[0].plot(list(d_out), list(v_out), color="#74b9ff", lw=1.0, ls="--", alpha=0.7,
                     label="Temp Außen")
    axes[0].axhspan(TEMP_OPT_MIN, TEMP_OPT_MAX, color="#2ecc71", alpha=0.08,
                    label=f"Optimal ({TEMP_OPT_MIN}–{TEMP_OPT_MAX} °C)")
    axes[0].set_ylabel("Temperatur (°C)", color="#ccc", fontsize=9)
    axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 2: Humidity + Luftdruck
    humid_in  = [env[d].get("humidity")       if d in env else None for d in all_dates]
    pressure  = [weather[d]["pressure"]        if d in weather and weather[d]["pressure"] else None for d in all_dates]
    d_h, v_h  = filter_none(dts, humid_in)
    d_p, v_p  = filter_none(dts, pressure)

    ax2b = axes[1].twinx() if list(d_p) else None
    if list(d_h):
        axes[1].plot(list(d_h), list(v_h), color="#a29bfe", lw=1.2, label="Luftfeucht. (%rF)")
        axes[1].axhspan(FEUCHTE_OPT_MIN, FEUCHTE_OPT_MAX, color="#2ecc71", alpha=0.08)
        axes[1].set_ylabel("Luftfeucht. (%rF)", color="#ccc", fontsize=9)
        axes[1].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
    if ax2b and list(d_p):
        ax2b.plot(list(d_p), list(v_p), color="#636e72", lw=0.8, ls=":", alpha=0.6,
                  label="Luftdruck")
        ax2b.set_ylabel("Luftdruck (hPa)", color="#aaa", fontsize=8)
        ax2b.tick_params(colors="#aaa", labelsize=7)
        ax2b.legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white", loc="upper right")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 3: Solar + HRV
    solar = [weather[d]["solar"] if d in weather and weather[d]["solar"] else None for d in all_dates]
    hrv   = [stress[d]["hrv"]    if d in stress and stress[d].get("hrv") else None for d in all_dates]
    d_sol, v_sol = filter_none(dts, solar)
    d_hrv, v_hrv = filter_none(dts, hrv)

    ax3b = axes[2].twinx() if list(d_hrv) else None
    if list(d_sol):
        axes[2].bar(list(d_sol), list(v_sol), color="#fdcb6e", alpha=0.5, width=0.8,
                    label="Solar W/m²")
        axes[2].set_ylabel("Solar (W/m²)", color="#ccc", fontsize=9)
        axes[2].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
    if ax3b and list(d_hrv):
        ax3b.plot(list(d_hrv), list(v_hrv), color="#a29bfe", lw=1.2, label="HRV RMSSD")
        ax3b.set_ylabel("HRV RMSSD (ms)", color="#aaa", fontsize=8)
        ax3b.tick_params(colors="#aaa", labelsize=7)
        ax3b.legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white", loc="upper right")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p  = OUT_DIR / f"sleep_environment_{ts}.png"
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
    out = OUT_DIR / f"sleep_environment_{ts}.md"
    content = f"# Umgebungs- & Sleep-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Umgebungs- & Sleep-Analyse", "Environment & sleep analysis"))
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
    env, weather, stress = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not env and not weather:
        print(t("Keine Umgebungsdaten. Zuerst: python3 importers/import_homeassistant.py "
                "und/oder import_ecowitt.py",
                "No environment data. First run: python3 importers/import_homeassistant.py "
                "and/or import_ecowitt.py"))
        return

    n_env     = len(env)
    n_weather = len(weather)
    print(t(f"Umgebungstage: Indoor={n_env}, Outdoor={n_weather}",
            f"Environment days: indoor={n_env}, outdoor={n_weather}"))

    report = build_report(env, weather, stress, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(env, weather, stress, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
