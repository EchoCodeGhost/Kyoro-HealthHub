#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Lärmbelastung & Symptom-Analyse

Analysiert Umgebungslärm-Exposition aus Apple Watch (dBASPL)
und korreliert sie mit Migräne, neurologischen Symptomen und HRV.

WHO-Richtwert Environmental Noise 2018: Lden ≤55 dB(A) Tagesdurchschnitt; >55 dB(A) = erhöhtes Gesundheitsrisiko.
Dauerlärm >70 dB(A) gilt als Gesundheitsrisiko. Lärm ist ein bekannter Trigger für Migräne und autonome Überreizung.

@tier        heuristic
@purpose.de  Analysiert Umgebungslärm-Exposition (Apple Watch dBASPL) auf Tagesmittel, Hochlärm-Tage, Tageszeit-Muster und Korrelation mit Migräne und neurologischen Symptomen.
@purpose.en  Analyses ambient noise exposure (Apple Watch dBASPL) for daily averages, high-noise days, time-of-day patterns and correlation with migraine and neurological symptoms.
@method.de   Tages- und Stunden-Aggregation von audio_exposure_env; WHO Environmental Noise 2018 Lden >55 dB(A) als Orientierungsschwelle; eigene Kritisch-Schwelle 70 dB; Korrelation mit symptoms und sessions (Migräne).
@method.en   Daily and hourly aggregation of audio_exposure_env; WHO Environmental Noise 2018 Lden >55 dB(A) as orientation threshold; own critical threshold 70 dB; correlation with symptoms and sessions (migraine).
@refs        WHO Regional Office for Europe. Environmental Noise Guidelines for the European Region. Copenhagen: WHO/Europe; 2018. doi:https://iris.who.int/handle/10665/279952

@relevance.de  Untersucht die Auswirkungen von Lärmbelastung auf Stresslevel, Schlafqualität und kardiovaskuläre Gesundheit, essentiell für die Identifikation umweltbedingter Stressfaktoren
@relevance.en  Examines the effects of noise exposure on stress levels, sleep quality, and cardiovascular health, essential for identifying environment-related stress factors
@limits.de   Heuristische Methode: Apple-Watch-Mikrofon misst instantanen Umgebungsschallpegel (dBSPL), kein zeitgewichtetes Lden gemäß WHO 2018; eigene Kritisch-Schwelle 70 dB projektintern; Schwelle 55 dB als dBSPL-Annäherung an Lden-Richtwert (methodisch nicht äquivalent); Korrelation explorativ ohne Signifikanztests.
@limits.en   Heuristic method: Apple Watch microphone measures instantaneous ambient sound level (dBSPL), not the time-weighted Lden of WHO 2018; own critical threshold 70 dB is project-internal; 55 dB used as dBSPL approximation of Lden guideline (not methodologically equivalent); correlation is exploratory without significance tests.
@scoring
    Noise level: <55 dB acceptable | 55-70 dB elevated | >70 dB critical (WHO guideline approximation)
    High-noise day: >70 dB for >=1 hour
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       measurements, symptoms, sessions
@writes      analyses/environment/noise_*.{md,png}

Usage:
  python analyse_noise.py --plot
  python analyse_noise.py --from YYYY-MM-DD --plot
  python analyse_noise.py --plot --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_noise.py
    python analyse_noise.py --help
    python analyse_noise.py --from 2024-01-01 --to 2024-12-31
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

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "environment"

from modules.prompts.analysis_environment import (
    SYSTEM_PROMPT_ANALYSE_NOISE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_NOISE_EN as SYSTEM_PROMPT_EN,
)

DB_SCHWELLE = 70   # kritisch (Hörschaden/Gesundheitsrisiko; Literatur-Konsens)
DB_ERHOEHT  = 55   # WHO Environmental Noise 2018: Lden >55 dB(A); doi:https://iris.who.int/handle/10665/279952
                   # (hier als dBSPL-Annäherung verwendet — methodisch nicht äquivalent zu Lden)


def load_data(conn, d_from, d_to):
    # Tages-Aggregat
    daily = conn.execute("""
        SELECT date,
               AVG(value) AS avg_db,
               MAX(value) AS max_db
        FROM measurements
        WHERE metric = 'audio_exposure_env'
          AND source_app = 'apple_health'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # hours-Profiles
    hourly = conn.execute("""
        SELECT CAST(SUBSTR(ts, 12, 2) AS INTEGER) AS stunde,
               AVG(value) AS avg_db
        FROM measurements
        WHERE metric = 'audio_exposure_env'
          AND source_app = 'apple_health'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY stunde
        ORDER BY stunde
    """, (d_from, d_to)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ?
              AND category IN ('Erschöpfung/Neurologie','Schmerz','Sensorisch/Neurologie')
              AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert
    elif "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ?
              AND category IN ('Erschöpfung/Neurologie','Schmerz','Sensorisch/Neurologie')
              AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    migraene = set()
    if "migraine_live" in tables:
        for row in conn.execute("""
            SELECT DATE(started_at) FROM migraine_live
            WHERE DATE(started_at) >= ? AND DATE(started_at) <= ?
        """, (d_from, d_to)):
            migraene.add(row[0])

    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, *_ in conn.execute("""
            SELECT date, rmssd_ms FROM daily_stress WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = rmssd

    return daily, hourly, symptome, migraene, stress


def spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)
    def ranks(vals):
        sv = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sv, 1):
            r[idx] = rank
        return r
    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n ** 2 - 1)), 3)


def build_report(daily, hourly, symptome, migraene, stress, d_from, d_to):
    if not daily:
        return "No Lärmexpositions-Daten im angefragten Time range."

    n = len(daily)
    avg_vals = [r[1] for r in daily if r[1]]
    max_vals = [r[2] for r in daily if r[2]]
    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    n_erhoeht  = sum(1 for v in avg_vals if v > DB_ERHOEHT)
    n_kritisch = sum(1 for v in max_vals if v and v > DB_SCHWELLE)

    lines = [
        f"## Lärmbelastung — {d_from} bis {d_to}\n",
        f"days: **{n}**  |  Time range: {daily[0][0]} – {daily[-1][0]}\n",
        "### Exposition\n",
        f"  Ø Tagesbelastung: **{avg(avg_vals)} dB(A)**",
        f"  Erhöhte days (>{DB_ERHOEHT} dB): {n_erhoeht} ({round(n_erhoeht/n*100,1)}%)",
        f"  Spitzen-days (Max >{DB_SCHWELLE} dB): {n_kritisch}",
    ]

    # Lauteste days
    top5 = sorted(daily, key=lambda r: r[1] or 0, reverse=True)[:5]
    lines.append("\n### Lauteste days\n")
    for r in top5:
        lines.append(f"  {r[0]}  Ø {r[1]:.1f} dB  (Max: {r[2]:.0f} dB)")

    # Stunden-Profile
    if hourly:
        peak_h = max(hourly, key=lambda x: x[1])
        lines += [
            "\n### Tageszeit-Profile\n",
            f"  Lauteste Stande: {peak_h[0]:02d}:00 Uhr (Ø {peak_h[1]:.1f} dB)",
        ]

    # Correlationen
    dates = [r[0] for r in daily]
    db_x  = [r[1] for r in daily]
    sym_y = [symptome.get(d) for d in dates]
    hrv_y = [stress.get(d) for d in dates]

    r_db_sym = spearman_r(db_x, sym_y)
    r_db_hrv = spearman_r(db_x, hrv_y)

    if r_db_sym or r_db_hrv:
        lines += [
            "\n### Correlation Lärm × (Spearman r)\n",
            f"  × Neurolog. Symptoms: {r_db_sym if r_db_sym else 'n.a.'}",
            f"  × HRV RMSSD:          {r_db_hrv if r_db_hrv else 'n.a.'}",
        ]

    return "\n".join(lines)


def _plot(daily, hourly, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Lärmbelastung {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    if daily:
        dts  = [datetime.fromisoformat(r[0]) for r in daily if r[1]]
        vals = [r[1] for r in daily if r[1]]
        max_ = [r[2] for r in daily if r[2]]
        dts_m = [datetime.fromisoformat(r[0]) for r in daily if r[2]]
        axes[0].plot(dts, vals, color="#fdcb6e", lw=1.2, alpha=0.9, label="Ø dB(A)")
        if dts_m:
            axes[0].fill_between(dts_m, vals[:len(dts_m)], max_,
                                 color="#fdcb6e", alpha=0.2)
        axes[0].axhline(DB_ERHOEHT, color="#fdcb6e", lw=0.7, ls="--", alpha=0.5)
        axes[0].axhline(DB_SCHWELLE, color="#e17055", lw=0.7, ls="--", alpha=0.5)
        axes[0].set_ylabel("dB(A)", color="#ccc", fontsize=9)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    if hourly:
        hours = [r[0] for r in hourly]
        vals  = [r[1] for r in hourly]
        axes[1].bar(hours, vals, color="#fdcb6e", alpha=0.8)
        axes[1].axhline(DB_SCHWELLE, color="#e17055", lw=0.7, ls="--", alpha=0.5)
        axes[1].set_ylabel("Ø dB(A)", color="#ccc", fontsize=9)
        axes[1].set_xlabel("Uhrzeit", color="#ccc", fontsize=9)
        axes[1].set_xticks(range(0, 24))
        axes[1].set_xticklabels([f"{h}" for h in range(0, 24)], fontsize=7, color="#aaa")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"noise_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
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
    out = OUT_DIR / f"noise_{ts}.md"
    content = f"# Lärmbelastung\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Lärmbelastung & Symptom-Analyse", "Noise exposure & symptom analysis"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.birthdate or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    daily, hourly, symptome, migraene, stress = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not daily:
        print("No Lärmexpositionsdaten. Zuerst: python3 importers/import_apple_health.py")
        return

    print(f"Lärm-days: {len(daily)}")
    report = build_report(daily, hourly, symptome, migraene, stress,
                               args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(daily, hourly, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
