#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_longevity.py — Longevity-Profil: Biologisches Alter, Biomarker & Genetik

@tier        heuristic
@refs        Levine ME, Lu AT, Quach A et al. (2018). An epigenetic biomarker of aging for lifespan and healthspan. Aging, 10(4):573-591. doi:10.18632/aging.101414 (Phenotypic Age)
             Horvath S (2013). DNA methylation age of human tissues and cell types. Genome Biology, 14(10). doi:10.1186/gb-2013-14-10-r115 (epigenetic clock)
             Lopez-Otin C, Blasco MA, Partridge L, Serrano M, Kroemer G (2023). Hallmarks of aging: An expanding universe. Cell, 186(2):243-278. doi:10.1016/j.cell.2022.11.001
             Willcox BJ, Donlon TA, He Q, Chen R, Grove JS et al. (2008). FOXO3A genotype is strongly associated with human longevity. PNAS, 105(37):13987-13992. doi:10.1073/pnas.0801030105
             Sebastiani P, Gurinovich A, Bae H, Andersen S, Malovini A, Atzmon G, Villa F, Kraja AT, Ben-Avraham D, Barzilai N, Puca A, Perls TT (2017). Four Genome-Wide Association Studies Identify New Extreme Longevity Variants. The Journals of Gerontology: Series A, 72(11):1453-1464. doi:10.1093/gerona/glx027

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT_DE
@prompt.en SYSTEM_PROMPT_EN
@purpose.de  Erstellt ein integriertes Longevity-Profil aus biologischem Alter (Aniva-Epigenetik),
             Longevity-Biomarkern (Inflammaging, Metabolismus, Hormone, Mikronährstoffe),
             kardiovaskulären Langlebigkeitsmarkern (HRV, RHR-Trend) und genetischen
             Longevity-Varianten (APOE, FOXO3, MTHFR u. a.).
@purpose.en  Creates an integrated longevity profile from biological age (Aniva epigenetics),
             longevity biomarkers (inflammaging, metabolism, hormones, micronutrients),
             cardiovascular longevity markers (HRV, RHR trend) and genetic longevity
             variants (APOE, FOXO3, MTHFR et al.).
@method.de   Deskriptive Aggregation ohne statistische Modellierung. Biologisches Alter
             aus lab_manual (parameter='Biologisches Alter'), Biomarker aus lab_manual
             (Kategorien: Longevity, Vitamin, Hormon, Entzündung, Metabolismus),
             HRV/RHR aus measurements, Genetik aus genetic_risk_markers (category='longevity')
             und genetic_variants (bekannte Longevity-SNPs per Liste). LLM-Interpretation
             durch Longevity-Mediziner-Prompt.
@method.en   Descriptive aggregation without statistical modelling. Biological age from
             lab_manual (parameter='Biologisches Alter'), biomarkers from lab_manual
             (categories: Longevity, Vitamin, Hormon, Entzündung, Metabolismus),
             HRV/RHR from measurements, genetics from genetic_risk_markers (category='longevity')
             and genetic_variants (known longevity SNPs by list). LLM interpretation
             via longevity physician prompt.
@scoring
    Biologisches Alter vs. Kalenderalter: Differenz in Jahren (negativ = jünger)
    Biomarker-Status: normal | low | high (aus lab_manual.status)
    Longevity-SNPs: Schutz-Allel | Risiko-Allel | neutral
@reads       lab_manual, genetic_risk_markers, genetic_variants, measurements, personal_baseline
@writes      analyses/longevity/*.{md,png}
@limits.de   Heuristisch. Biologisches Alter nur wenn Aniva-Daten vorhanden. Genetik nur
             wenn import_genetics_*.py ausgeführt wurde. Kein Ersatz für ärztliche Beratung.
@limits.en   Heuristic. Biological age only if Aniva data present. Genetics only if
             import_genetics_*.py was run. Not a substitute for medical advice.
@usage
    python3 scripts/analysis/longevity/analyse_longevity.py
    python3 scripts/analysis/longevity/analyse_longevity.py --plot
    python3 scripts/analysis/longevity/analyse_longevity.py --no-llm
    python3 scripts/analysis/longevity/analyse_longevity.py --from 2024-01-01
    python3 scripts/analysis/longevity/analyse_longevity.py --lang en
"""

import argparse
import sys
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, open_lab_db as _open_lab_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_longevity import (
    SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY as SYSTEM_PROMPT_EN,
)

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "longevity"

# ---------------------------------------------------------------------------
# Bekannte Longevity-SNPs (rsid → (Gen, Trivialname, Schutz-Richtung))
# ---------------------------------------------------------------------------

LONGEVITY_SNPS: dict[str, tuple[str, str, str]] = {
    "rs429358": ("APOE",  "APOE ε4 (rs429358)", "C=Schutz (ε3), T=Risiko (ε4)"),
    "rs7412":   ("APOE",  "APOE ε2 (rs7412)",   "T=Schutz (ε2), C=Standard (ε3)"),
    "rs2802292": ("FOXO3", "FOXO3 G-Allel",      "G=Schutz (Okinawa-Studie)"),
    "rs1042522": ("TP53",  "TP53 Arg72Pro",       "Pro/Pro = länger lebend in einigen Populationen"),
    "rs5882":   ("CETP",  "CETP I405V",          "A=höheres HDL, kardiovaskulärer Schutz"),
    "rs1801131": ("MTHFR", "MTHFR A1298C",       "A=Normalfunktion; C=reduzierter Folsäuremetabolismus"),
    "rs1801133": ("MTHFR", "MTHFR C677T",        "C=Normalfunktion; T=reduzierter Folsäuremetabolismus"),
    "rs4340":   ("ACE",   "ACE I/D Polymorphismus", "Insertion=kardioprotektiv bei Ausdauer"),
    "rs7895833": ("SIRT1", "SIRT1 Promoter",     "A=höhere SIRT1-Expression"),
    "rs2234693": ("ESR1",  "ESR1 PvuII",         "T=günstig kardiovaskulär bei Frauen"),
    "rs5128":   ("APOC3", "APOC3 3'UTR",         "G=niedrigere Triglyzeride, Longevity-assoziiert"),
    "rs2279590": ("CETP",  "CETP Taq1B",         "B2B2=höheres HDL, assoziiert mit Langlebigkeit"),
    "rs4977574": ("CDKN2B","9p21 Locus",         "A=Risiko koronare Herzkrankheit"),
    "rs2228671": ("LDLR",  "LDLR HincII",        "T=niedrigeres LDL"),
}

# ---------------------------------------------------------------------------
# Longevity-Biomarker: Welche lab_manual-Parameter relevant sind
# ---------------------------------------------------------------------------

LONGEVITY_BIOMARKER_GROUPS = {
    t("Biologisches Alter", "Biological Age"): [
        "biologisches alter", "biological age", "phänotypisches alter",
        "epigenetisches alter", "telomerlänge", "glycan age", "horvath",
    ],
    t("Inflammaging", "Inflammaging"): [
        "hscrp", "hs-crp", "crp", "il-6", "il6", "interleukin-6", "interleukin 6",
        "ferritin", "fibrinogen", "homocystein", "homocysteine",
        "serotonin", "nt-probnp", "bnp",
    ],
    t("Metabolismus", "Metabolism"): [
        "hba1c", "nüchternglukose", "fasting glucose", "insulin",
        "triglyzeride", "triglycerides", "triglyceride", "ldl", "hdl",
        "gesamtcholesterin", "cholesterin gesamt", "total cholesterol",
        "non-hdl", "apolipoprotein b", "apob", "lipoprotein a", "lpla",
        "glucose", "glukose", "harnsäure", "uric acid",
    ],
    t("Hormone", "Hormones"): [
        "dhea", "dheas", "dhea-s", "igf-1", "igf1",
        "testosteron", "testosterone", "freies testosteron", "testosteron frei",
        "shbg",
        "cortisol", "tsh", "ft3", "ft4", "freies t3", "freies t4",
        "östradiol", "estradiol", "progesteron", "progesterone",
        "lh", "fsh", "melatonin", "prolaktin",
        "parathormon", "pth",
    ],
    t("Mikronährstoffe", "Micronutrients"): [
        "vitamin d", "25-oh", "25(oh)d", "vitamin b12", "b12", "cobalamin",
        "folsäure", "folate", "folic acid", "zink", "zinc",
        "magnesium", "selen", "selenium", "omega-3", "omega3",
        "epa", "dha", "coenzym q10", "coq10", "nad+",
        "eisen", "transferrin", "ferritin",
    ],
    t("Niere & Urin", "Kidney & Urine"): [
        "egfr", "gfr", "kreatinin", "creatinin", "harnstoff",
        "albumin", "eiweiß im urin", "ph im urin", "urin",
        "mikroalbumin", "albumin/kreatinin",
    ],
    t("Speichel", "Saliva"): [
        "speichel", "saliva", "speichel-ph",
    ],
    t("Körperkomposition", "Body Composition"): [
        "body fat", "körperfett", "muskelmasse", "muscle mass",
        "bmi", "waist", "taillenumfang", "viszeralfett",
    ],
}


def _match_param(param: str, keywords: list[str]) -> bool:
    import re
    p = param.lower()
    for kw in keywords:
        # Kurze Keywords (≤4 Zeichen) als Wortgrenze matchen, lange als Substring
        if len(kw) <= 4:
            if re.search(r'(?<![a-zäöü])' + re.escape(kw) + r'(?![a-zäöü])', p):
                return True
        elif kw in p:
            return True
    return False


# ---------------------------------------------------------------------------
# Datenlade-Funktionen
# ---------------------------------------------------------------------------

def load_bio_age(_conn, person: str, d_from: str, d_to: str) -> list[dict]:
    conn = _open_lab_db()
    rows = conn.execute("""
        SELECT date, parameter, wert, wert_num, einheit, labor, kommentar
        FROM lab_all
        WHERE person = ?
          AND date BETWEEN ? AND ?
          AND (LOWER(parameter) LIKE '%biologisches alter%'
               OR LOWER(parameter) LIKE '%biological age%'
               OR LOWER(parameter) LIKE '%phänotypisches alter%'
               OR LOWER(parameter) LIKE '%epigenetisches alter%'
               OR LOWER(parameter) LIKE '%telomer%'
               OR LOWER(parameter) LIKE '%glycan age%')
        ORDER BY date DESC
    """, (person, d_from, d_to)).fetchall()
    conn.close()
    return [dict(zip(["date", "parameter", "wert", "wert_num", "einheit",
                       "labor", "kommentar"], r)) for r in rows]


def load_biomarkers(conn, person: str, d_from: str, d_to: str) -> dict[str, list[dict]]:
    med_conn = _open_lab_db()
    rows = med_conn.execute("""
        SELECT date, parameter, wert, wert_num, einheit, status, labor, kategorie
        FROM lab_all
        WHERE person = ? AND date BETWEEN ? AND ?
        ORDER BY parameter, date
    """, (person, d_from, d_to)).fetchall()
    med_conn.close()

    result: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        param = r[1]
        for group, keywords in LONGEVITY_BIOMARKER_GROUPS.items():
            if _match_param(param, keywords):
                result[group].append(dict(zip(
                    ["date", "parameter", "wert", "wert_num",
                     "einheit", "status", "labor", "kategorie"], r
                )))
                break
    return result


def load_hrv_rhr(conn, person: str, d_from: str, d_to: str) -> dict:
    hrv = conn.execute("""
        SELECT date, AVG(value) AS avg_rmssd
        FROM measurements
        WHERE person = ? AND metric = 'hrv_rmssd'
          AND date BETWEEN ? AND ?
        GROUP BY date ORDER BY date
    """, (person, d_from, d_to)).fetchall()

    rhr = conn.execute("""
        SELECT date, AVG(value) AS avg_rhr
        FROM measurements
        WHERE person = ? AND metric IN ('resting_heart_rate','hr_resting')
          AND date BETWEEN ? AND ?
        GROUP BY date ORDER BY date
    """, (person, d_from, d_to)).fetchall()

    return {"hrv": hrv, "rhr": rhr}


def load_genetic_risk(conn, person: str) -> list[dict]:
    rows = conn.execute("""
        SELECT rsid, gene, variant_name, genotype, risk_allele,
               effect_size, clinical_significance, phenotype, notes, source
        FROM genetic_risk_markers
        WHERE person = ? AND category = 'longevity'
        ORDER BY gene, rsid
    """, (person,)).fetchall()
    return [dict(zip(["rsid", "gene", "variant_name", "genotype", "risk_allele",
                       "effect_size", "clinical_significance", "phenotype",
                       "notes", "source"], r)) for r in rows]


def load_longevity_snps(conn, person: str) -> list[dict]:
    if not LONGEVITY_SNPS:
        return []
    placeholders = ",".join("?" * len(LONGEVITY_SNPS))
    rows = conn.execute(f"""
        SELECT rsid, chrom, pos, genotype, zygosity, source, genome_build
        FROM genetic_variants
        WHERE person = ? AND rsid IN ({placeholders})
        ORDER BY rsid
    """, (person, *LONGEVITY_SNPS.keys())).fetchall()
    result = []
    for r in rows:
        rsid = r[0]
        gene, name, direction = LONGEVITY_SNPS.get(rsid, ("?", rsid, ""))
        result.append(dict(
            rsid=rsid, gene=gene, name=name, direction=direction,
            genotype=r[3], zygosity=r[4], source=r[5], genome_build=r[6]
        ))
    return result


def load_pharmacogenomics(conn, person: str) -> list[dict]:
    rows = conn.execute("""
        SELECT rsid, gene, variant_name, genotype, risk_allele, phenotype, notes
        FROM genetic_risk_markers
        WHERE person = ? AND category = 'pharmacogenomics'
        ORDER BY gene
    """, (person,)).fetchall()
    return [dict(zip(["rsid", "gene", "variant_name", "genotype",
                       "risk_allele", "phenotype", "notes"], r)) for r in rows]


# ---------------------------------------------------------------------------
# Report-Builder
# ---------------------------------------------------------------------------

def _age_from_config() -> int | None:
    try:
        dob = _cfg._cfg.get("user", {}).get("birthdate")
        if dob:
            today = date.today()
            born = date.fromisoformat(dob)
            # days // 365 drifts by ~1 day/4 years (leap years) and ignores
            # whether this year's birthday has already passed — compare
            # (month, day) tuples instead for an exact age.
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except Exception:
        pass
    return None


def build_report(bio_age: list, biomarkers: dict, cardio: dict,
                 genetic_risk: list, longevity_snps: list,
                 pharma: list, d_from: str, d_to: str) -> str:
    cal_age = _age_from_config()
    lines = [f"## Longevity-Profil  {d_from} → {d_to}\n"]

    # 1. Biologisches Alter
    lines.append("### Biologisches Alter\n")
    if bio_age:
        for r in bio_age:
            delta = ""
            if cal_age and r["wert_num"] is not None:
                diff = r["wert_num"] - cal_age
                sign = "+" if diff >= 0 else ""
                delta = f"  (Kalenderalter: {cal_age}J, Differenz: {sign}{diff:.1f}J)"
            lines.append(f"  {r['date']}  {r['parameter']}: **{r['wert']} {r['einheit']}**{delta}"
                         f"  [{r['labor']}]")
    else:
        lines.append(t(
            "  — Keine Daten (Aniva-Biomarker importieren: import_genetics_aniva.py)",
            "  — No data (import Aniva biomarkers: import_genetics_aniva.py)"
        ))

    # 2. Longevity-Biomarker nach Gruppe
    lines.append("\n### Longevity-Biomarker\n")
    any_biomarker = False
    for group, rows in biomarkers.items():
        if not rows:
            continue
        any_biomarker = True
        abnormal = [r for r in rows if r["status"] in ("high", "low", "critical")]
        icon = "⚠" if abnormal else "✓"
        lines.append(f"  **{group}** {icon} ({len(rows)} Messungen)")
        # Letzte 3 Messwerte je Parameter
        by_param: dict[str, list] = defaultdict(list)
        for r in rows:
            by_param[r["parameter"]].append(r)
        for param, prows in by_param.items():
            latest = prows[-1]
            trend_vals = [r["wert_num"] for r in prows if r["wert_num"] is not None]
            trend = ""
            if len(trend_vals) >= 2:
                delta = trend_vals[-1] - trend_vals[-2]
                trend = f" ({'↑' if delta > 0 else '↓'}{abs(delta):.1f})"
            stat = f" [{latest['status']}]" if latest["status"] and latest["status"] != "normal" else ""
            lines.append(f"    {latest['date']}  {param:35s} {str(latest['wert'] or ''):>8} "
                         f"{str(latest['einheit'] or ''):8}{stat}{trend}")
    if not any_biomarker:
        lines.append(t(
            "  — Keine Longevity-Biomarker in lab_manual. "
            "Template: templates/aniva_biomarker_template.csv",
            "  — No longevity biomarkers in lab_manual. "
            "Template: templates/aniva_biomarker_template.csv"
        ))

    # 3. Kardiovaskuläre Longevity-Marker
    lines.append("\n### Kardiovaskuläre Langlebigkeitsmarker\n")
    hrv = cardio["hrv"]
    rhr = cardio["rhr"]
    if hrv:
        avg_rmssd = sum(r[1] for r in hrv) / len(hrv)
        latest_rmssd = hrv[-1][1]
        lines.append(f"  HRV (RMSSD)  Ø {avg_rmssd:.1f} ms  |  aktuell {latest_rmssd:.1f} ms  "
                     f"({len(hrv)} Tage)")
    else:
        lines.append("  HRV — keine Daten")
    if rhr:
        avg_rhr = sum(r[1] for r in rhr) / len(rhr)
        latest_rhr = rhr[-1][1]
        lines.append(f"  RHR           Ø {avg_rhr:.1f} bpm  |  aktuell {latest_rhr:.1f} bpm  "
                     f"({len(rhr)} Tage)")
    else:
        lines.append("  RHR — keine Daten")

    # 4. Genetische Longevity-Marker
    lines.append("\n### Bekannte Longevity-SNPs\n")
    found_snps = {s["rsid"] for s in longevity_snps}
    if longevity_snps:
        for s in sorted(longevity_snps, key=lambda x: x["gene"]):
            lines.append(f"  {s['rsid']:12s} {s['gene']:8s} {s['name']:35s} "
                         f"GT={s['genotype']:5s} [{s['zygosity']}]")
            lines.append(f"             {s['direction']}")
    else:
        lines.append(t(
            "  — Keine Longevity-SNPs in genetic_variants "
            "(23andMe / Dante / Nebula importieren).",
            "  — No longevity SNPs in genetic_variants "
            "(import 23andMe / Dante / Nebula)."
        ))

    # Bekannte Longevity-SNPs die fehlen
    missing = [rsid for rsid in LONGEVITY_SNPS if rsid not in found_snps]
    if missing and longevity_snps:
        lines.append(f"\n  Nicht im Datensatz: {', '.join(missing[:8])}"
                     + (" ..." if len(missing) > 8 else ""))

    # 5. Risiko-Marker (category=longevity, manuell eingetragen)
    if genetic_risk:
        lines.append("\n### Genetische Risikomarker (manuell / Longevity)\n")
        for r in genetic_risk:
            effect = f" [{r['effect_size']}]" if r["effect_size"] else ""
            lines.append(f"  {r['rsid'] or '—':12s} {r['gene'] or '—':8s} "
                         f"{r['variant_name'] or r['phenotype'] or '—':35s} "
                         f"GT={r['genotype'] or '—':5s}{effect}")
            if r["notes"]:
                lines.append(f"             {r['notes']}")

    # 6. Pharmakogenetik (Kurzform)
    if pharma:
        lines.append("\n### Pharmakogenetik (Überblick)\n")
        for r in pharma[:8]:
            lines.append(f"  {r['gene']:8s} {r['variant_name'] or r['rsid'] or '—':25s} "
                         f"GT={r['genotype'] or '—':5s}  {r['phenotype'] or ''}")
        if len(pharma) > 8:
            lines.append(f"  … +{len(pharma)-8} weitere")

    # 7. Datenverfügbarkeits-Summary
    lines.append("\n### Datenverfügbarkeit\n")
    lines.append(f"  Biologisches Alter:   {'✓ ' + str(len(bio_age)) + ' Messpunkte' if bio_age else '— fehlt'}")
    lines.append(f"  Longevity-Biomarker:  {'✓' if any_biomarker else '— fehlt (Aniva-Import?)'}")
    lines.append(f"  HRV-Daten:            {'✓ ' + str(len(hrv)) + ' Tage' if hrv else '— fehlt'}")
    lines.append(f"  Longevity-SNPs:       {'✓ ' + str(len(longevity_snps)) + ' SNPs' if longevity_snps else '— fehlt (Genetik-Import?)'}")
    lines.append(f"  Genetische Risikomar: {'✓ ' + str(len(genetic_risk)) + ' Marker' if genetic_risk else '— fehlt (import_genetics_manual.py?)'}")
    lines.append(f"  Pharmakogenetik:      {'✓ ' + str(len(pharma)) + ' Marker' if pharma else '— fehlt'}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def _plot(biomarkers: dict, cardio: dict, d_from: str, d_to: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    has_hrv = bool(cardio["hrv"])
    has_rhr = bool(cardio["rhr"])

    # Biologisches Alter Plot (wenn Aniva-Daten vorhanden)
    bio_age_group = t("Biologisches Alter", "Biological Age")
    bio_rows = biomarkers.get(bio_age_group, [])
    bio_rows_with_num = [r for r in bio_rows if r["wert_num"] is not None]
    cal_age = _age_from_config()

    n_plots = sum([
        bool(bio_rows_with_num),
        has_hrv,
        has_rhr,
    ])
    if n_plots == 0:
        print(t("Keine Daten für Plot.", "No data for plot."))
        return

    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 4 * n_plots),
                             facecolor="#1e1e2e")
    if n_plots == 1:
        axes = [axes]
    fig.suptitle(f"Longevity-Profil  {d_from} – {d_to}",
                 color="#E0E0E0", fontsize=13)

    ax_idx = 0

    if bio_rows_with_num:
        ax = axes[ax_idx]; ax_idx += 1
        ax.set_facecolor("#2a2a3e")
        dates = [datetime.fromisoformat(r["date"]) for r in bio_rows_with_num]
        vals  = [r["wert_num"] for r in bio_rows_with_num]
        ax.plot(dates, vals, "o-", color="#a29bfe", linewidth=2, markersize=6,
                label=t("Biologisches Alter", "Biological Age"))
        if cal_age:
            ax.axhline(cal_age, color="#fd79a8", linestyle="--", linewidth=1,
                       label=t(f"Kalenderalter ({cal_age}J)", f"Calendar age ({cal_age}y)"))
        ax.set_ylabel(t("Jahre", "Years"), color="#ccc")
        ax.set_title(t("Biologisches Alter", "Biological Age"),
                     color="#dfe6e9", fontsize=10)
        ax.tick_params(colors="#aaa")
        ax.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    if has_hrv:
        ax = axes[ax_idx]; ax_idx += 1
        ax.set_facecolor("#2a2a3e")
        dates = [datetime.fromisoformat(r[0]) for r in cardio["hrv"]]
        vals  = [r[1] for r in cardio["hrv"]]
        ax.plot(dates, vals, color="#00cec9", linewidth=1.2, alpha=0.8)
        ax.fill_between(dates, vals, alpha=0.15, color="#00cec9")
        ax.set_ylabel("RMSSD (ms)", color="#ccc")
        ax.set_title("HRV (RMSSD)", color="#dfe6e9", fontsize=10)
        ax.tick_params(colors="#aaa")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    if has_rhr:
        ax = axes[ax_idx]; ax_idx += 1
        ax.set_facecolor("#2a2a3e")
        dates = [datetime.fromisoformat(r[0]) for r in cardio["rhr"]]
        vals  = [r[1] for r in cardio["rhr"]]
        ax.plot(dates, vals, color="#fdcb6e", linewidth=1.2, alpha=0.8)
        ax.fill_between(dates, vals, alpha=0.15, color="#fdcb6e")
        ax.set_ylabel("bpm", color="#ccc")
        ax.set_title(t("Ruheherzrate", "Resting Heart Rate"), color="#dfe6e9", fontsize=10)
        ax.tick_params(colors="#aaa")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"longevity_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------


def _run_llm(report: str, lang: str) -> str:
    try:
        from modules.llm import call_llm
        prompt = SYSTEM_PROMPT_DE if lang == "de" else SYSTEM_PROMPT_EN
        print(t("\nLLM analysiert (Longevity-Modus) ...", "\nLLM analysing (longevity mode) ..."))
        return call_llm(report, system=prompt, max_tokens=1200)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report: str, llm_text: str, lang: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"longevity_{ts}.md"
    title = t("# Longevity-Profil\n\n", "# Longevity Profile\n\n")
    content = title + report
    if llm_text:
        header = t("\n## Longevity-Interpretation\n\n",
                   "\n## Longevity Interpretation\n\n")
        content += header + llm_text + "\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Longevity-Profil: Biologisches Alter, Biomarker & Genetik",
                       "Longevity Profile: Biological Age, Biomarkers & Genetics")
    )
    parser.add_argument("--from",   dest="date_from",
                        default=_cfg.birthdate or "1970-01-01",
                        help="Standard: Geburtsdatum — Laborwerte/Biomarker aus lab_manual "
                             "koennen Jahrzehnte vor clinical.data_start (Wearable-Baseline) "
                             "liegen und wuerden sonst stillschweigend ausgeschlossen")
    parser.add_argument("--to",     dest="date_to",
                        default=str(date.today()))
    parser.add_argument("--person", default=None)
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    from modules.base import resolve_person
    person = resolve_person(args.person)

    conn = open_db()

    bio_age      = load_bio_age(conn, person, args.date_from, args.date_to)
    biomarkers   = load_biomarkers(conn, person, args.date_from, args.date_to)
    cardio       = load_hrv_rhr(conn, person, args.date_from, args.date_to)
    genetic_risk = load_genetic_risk(conn, person)
    longevity_snps = load_longevity_snps(conn, person)
    pharma       = load_pharmacogenomics(conn, person)

    conn.close()

    report = build_report(bio_age, biomarkers, cardio,
                          genetic_risk, longevity_snps, pharma,
                          args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(biomarkers, cardio, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report, args.lang)
    _save(report, llm_text, args.lang)


if __name__ == "__main__":
    main()
