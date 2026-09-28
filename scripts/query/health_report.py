#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Gesundheitsbericht Generator — KI-generierte Gesundheitsberichte für Check-ups

@tier        heuristic
@purpose.de  Erstellt strukturierte Gesundheitsberichte im Markdown-Format für
             Gesundheits-Check-ups. Fasst alle wichtigen Gesundheitsmetriken zusammen und
             ordnet sie ein. Dient als Vorbereitung für medizinische Konsultationen.
@purpose.en  Generates structured health reports in Markdown format for health check-ups.
             Summarizes all important health metrics and categorizes them.
             Serves as preparation for medical consultations.
@prompt-classification LLM:System, LLM:Summary
@prompt.de    SYSTEM_REPORT: Du bist ein erfahrener Gesundheitsanalyst und erstellst einen strukturierten
             Gesundheitsbericht. Auf Basis der vorliegenden Messdaten erstellst du einen prägnanten
             Bericht. Format: Summary, Vorgeschichte, Kardiovaskuläre Parameter,
             Sauerstoffsättigung, Sleep & Recovery, Aktivität & Fitness,
             Auffälligkeiten & Empfehlungen, Weiterführende Analysen.
             WICHTIG: Am Ende explizit darauf hinweisen dass dies KI-generiert ist und keine
             medizinische Bewertung ersetzt.
@prompt.en    SYSTEM_REPORT: You are an experienced health analyst creating a structured health
             report. Based on the available measurement data, create a concise report.
             Format: Summary, History, Cardiovascular Parameters,
             Oxygen Saturation, Sleep & Recovery, Activity & Fitness, Abnormalities & Recommendations,
             Further Analysis. IMPORTANT: Explicitly state at the end that this is AI-generated
             and does not replace medical evaluation.
@method.de   Sammelt Daten aus verschiedenen Tabellen (measurements, blood_pressure, sleep,
             etc.) und strukturiert sie nach Gesundheitskategorien. Nutzt LLMProvider
             für die Generierung des freien Textes. Unterstützt Fokus auf bestimmte Bereiche
             (kardio, schlaf, etc.) und Zeiträume.
@method.en   Collects data from various tables (measurements, blood_pressure, sleep, etc.)
             and structures it by health categories. Uses LLMProvider for generating the
             free text. Supports focus on specific areas (cardio, sleep, etc.) and time periods.
@reads       measurements, blood_pressure, sleep, ppi_hrv_advanced, sessions, symptoms
@writes      OUT_DIR/health_reports/ (Markdown-Berichte)
@limits.de   Heuristische Methode: KI-generiert, ersetzt KEINE medizinische Bewertung. Berichte basieren auf
             verfügbaren Messdaten und können unvollständig sein. Medizinische Bewertung
             durch Fachpersonal erforderlich.
@limits.en   Heuristic method: AI-generated, does NOT replace medical diagnosis. Reports are based on
             available measurement data and may be incomplete. Medical evaluation by a
             healthcare professional is required.
@refs        Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
             Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7

@relevance.de  Ermöglicht die Generierung von Gesundheitsberichten, essentiell für die klinische Dokumentation
@relevance.en  Enables health report generation, essential for clinical documentation
@scoring Gesundheits-Score basierend auf Abweichung von Normalbereichen und Risikofaktoren
@usage
    python health_report.py                    # Standardbericht (letzte 12 Monate)
    python health_report.py --period 2024     # Nur ein Jahr
    python health_report.py --focus kardio    # Schwerpunkt Kardiologie
    python health_report.py --focus schlaf    # Schwerpunkt Schlaf
    python health_report.py --output report.md # Ausgabedatei angeben
"""

from datetime import datetime
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import add_lang_arg, apply_lang_from_args
from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
from modules.prompts.query import (
    SYSTEM_REPORT_DE as SYSTEM_REPORT_DE,
    SYSTEM_REPORT_EN as SYSTEM_REPORT_EN,
)
_cfg = _Cfg()

DB_PATH       = _cfg.db_path
OUT_DIR       = _cfg.analyses_dir / "medical_reports"
TIMELINE_PATH = _cfg.manual_dir / "timeline_symptome.txt"


def _dominant_label(days) -> str:
    """Haeufigste tatsaechliche Geraetebezeichnung unter den geladenen Tagen —
    fuer Abschnittsueberschriften statt eines hartcodierten Markennamens wie
    'Apple Watch', der nicht mehr zur real ladenden Quelle passt."""
    from collections import Counter
    c = Counter(d.label for d in days.values() if d.label)
    return c.most_common(1)[0][0] if c else "keine Daten in dieser Installation"


def gather_data(period: str | None = None) -> str:
    conn = open_db()
    year_filter = f"AND strftime('%Y', date) = '{period}'" if period else ""
    sections = []

    # Manuelle Anamnese-Timeline (falls vorhanden)
    if TIMELINE_PATH.exists():
        timeline = TIMELINE_PATH.read_text(encoding="utf-8").strip()
        if timeline:
            sections.append("## ANAMNESE / VORGESCHICHTE (manuell erfasst)")
            sections.append(timeline)
            sections.append("")

    # Clinicalr Kontext — aus Anamnese-Timeline (manuell/*.txt)
    sections.append("## KLINISCHER KONTEXT")
    sections.append("(Siehe Anamnese-Timeline — Diagnosen, Krankheitsverlauf und Befunde aus Messdaten folgen)")

    # Stammdaten
    sections.append("\n## PATIENTENDATEN (aus Gerätedaten abgeleitet)")
    if _cfg.age:
        sections.append(f"Alter: {_cfg.age} Jahre")
    sections.append(f"Berichtszeitraum: {period or 'gesamt'}")
    sections.append(f"Berichtsdatum: {datetime.now().strftime('%Y-%m-%d')}")

    # Kardiovaskulär
    sections.append("\n## HERZFREQUENZ")
    rhr = conn.execute(f"""
        SELECT ROUND(AVG(resting_hr),1), ROUND(MIN(resting_hr),0), ROUND(MAX(resting_hr),0)
        FROM daily_stress WHERE resting_hr IS NOT NULL {year_filter}""").fetchone()
    if rhr[0]: sections.append(f"Ruhepuls: ∅{rhr[0]} bpm | Min {rhr[1]} | Max {rhr[2]} bpm")
    # Langzeittrend Resting heart rate
    rhr_trend = conn.execute("""
        SELECT strftime('%Y',date), ROUND(AVG(resting_hr),1)
        FROM daily_stress WHERE resting_hr IS NOT NULL
        GROUP BY 1 ORDER BY 1""").fetchall()
    if len(rhr_trend) > 1:
        first, last = rhr_trend[0], rhr_trend[-1]
        delta = round((last[1] or 0) - (first[1] or 0), 1)
        sections.append(f"Langzeittrend: {first[0]} ∅{first[1]} → {last[0]} ∅{last[1]} bpm (Δ{delta:+.1f})")

    tachy = conn.execute(f"""
        SELECT COUNT(*) FROM daily_stress WHERE resting_hr > 100 {year_filter}""").fetchone()[0]
    if tachy: sections.append(f"Tage mit Ruhepuls >100 bpm (Tachykardie): {tachy}")

    hr_events = conn.execute("""
        SELECT COUNT(*) FROM apple_records WHERE type='high_hr_event'""").fetchone()[0]
    if hr_events: sections.append(f"Apple High-HR-Events: {hr_events}")

    # Blood pressure — blood_pressure ist die reale, geraeteunabhaengige
    # Tabelle (Omron, Withings, manuelle Eintraege, Hilo-Laborwerte, siehe
    # scripts/importers/import_omron.py u.a.). apple_records.type=
    # 'bp_systolic'/'bp_diastolic' hat DB-weit 0 Zeilen — Apple Health
    # liefert hier nichts, der Abschnitt war deshalb bisher immer leer,
    # obwohl blood_pressure reale Messungen enthaelt.
    sections.append("\n## BLUTDRUCK")
    bp = conn.execute(f"""
        SELECT ROUND(AVG(systolic),1), ROUND(AVG(diastolic),1),
               ROUND(MAX(systolic),0), ROUND(MIN(systolic),0), COUNT(*)
        FROM blood_pressure
        WHERE systolic IS NOT NULL AND diastolic IS NOT NULL {year_filter}""").fetchone()
    if bp[0]:
        # Einstufung ueber das gemeinsame Modul: die Grenzen hier waren um eine
        # Stufe verschoben (ab 140 als "Grad 2"), und ein Grad wurde auch bei
        # einer einzigen Messung vergeben. Beides erzeugt eine folgenreiche
        # Aussage aus einer Datenlage, die sie nicht traegt.
        from modules.bp_norms import classify, exceeds_home_threshold
        grade, graded = classify(bp[0], bp[1], n_readings=bp[4])
        sections.append(f"∅ {bp[0]}/{bp[1]} mmHg | Max systolisch {bp[2]} mmHg "
                        f"| {bp[4]} Messung(en) → {grade}")
        if not graded and exceeds_home_threshold(bp[0], bp[1]):
            sections.append("Wert liegt ueber der Schwelle fuer haeusliche Selbstmessung "
                            "(135/85) — fuer eine Einstufung fehlt eine Messreihe.")
        bp_grad3 = conn.execute(f"""
            SELECT COUNT(*) FROM blood_pressure WHERE systolic >= 160 {year_filter}""").fetchone()[0]
        if bp_grad3: sections.append(f"Messungen ≥160 mmHg: {bp_grad3} ⚠️")
    else:
        sections.append("(keine Blutdruckdaten in dieser Installation)")

    # HRV — geraeteunabhaengig ueber measurements. polar_nightly_hrv ist ohne
    # Polar-Geraet ein leerer Stub (compat_views.py); der reale Kanal sind die
    # HRV-Metriknamen aus modules/sensor_confidence.py (METRIC_FAMILY).
    date_from = f"{period}-01-01" if period else "0001-01-01"
    date_to   = f"{period}-12-31" if period else "9999-12-31"
    hrv_days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms", "hrv_sdnn", "overnight_hrv"),
                                  date_from, date_to, agg="avg", valid_range=(0.0, 300.0))
    sections.append(f"\n## HERZFREQUENZVARIABILITÄT (HRV) — {_dominant_label(hrv_days)}")
    by_year: dict[str, list[float]] = {}
    for date, day in hrv_days.items():
        by_year.setdefault(date[:4], []).append(day.value)
    for jahr, vals in sorted(by_year.items()):
        sections.append(f"  {jahr}: RMSSD∅ {sum(vals)/len(vals):.1f}ms ({len(vals)} Nächte)")
    if hrv_days:
        sections.append(f"  Konfidenz: {weakest_confidence(hrv_days)}")

    # SpO2 — geraeteunabhaengig ueber measurements. Vorher zwei tote Kanaele:
    # apple_records.type='oxygen_saturation' hat DB-weit 0 Zeilen (realer Name:
    # measurements.metric='spo2'; Werte liegen dort bereits in Prozent, nicht
    # als Bruchwert 0..1), und polar_spo2 ist ohne Polar-Geraet ein leerer Stub.
    sections.append("\n## SAUERSTOFFSÄTTIGUNG (SpO2)")
    spo2_days = load_metric_daily(conn, ("spo2", "oxygen_saturation"), date_from, date_to,
                                   agg="min", valid_range=(50.0, 100.0))
    if spo2_days:
        vals = [d.value for d in spo2_days.values()]
        n_readings = sum(d.n_readings for d in spo2_days.values())
        quellen = ", ".join(f"{label} ({n})" for label, n in source_summary(spo2_days).items())
        sections.append(f"{quellen}: {n_readings} Messungen an {len(spo2_days)} Tagen | "
                         f"∅{sum(vals)/len(vals):.1f}% | Min {min(vals):.1f}% "
                         f"[Konfidenz: {weakest_confidence(spo2_days)}]")
        for threshold, label in [(85, "KRITISCH <85%"), (90, "Bedenklich <90%"), (95, "Grenzwertig <95%")]:
            n = sum(1 for v in vals if v < threshold)
            if n: sections.append(f"  {label}: {n} Tage {'⚠️' if threshold <= 90 else ''}")
        # Naechtliches Minimum: ts ist UTC, keine Lokalzeit-Umrechnung hier —
        # dieselbe Naeherung wie im Vorgaengercode, nur mit korrigierter
        # Metrik/Skalierung. Siehe cross-cutting-conventions zu Zeitzonen.
        nacht_min = conn.execute("""
            SELECT ROUND(MIN(value),1) FROM measurements
            WHERE metric IN ('spo2','oxygen_saturation') AND value BETWEEN 50 AND 100
              AND (strftime('%H',ts)<'06' OR strftime('%H',ts)>='22')""").fetchone()[0]
        if nacht_min: sections.append(f"Nächtliches Minimum: {nacht_min}% {'🚨 Schlafapnoe-Abklärung empfohlen' if nacht_min < 90 else ''}")
    else:
        sections.append("(keine SpO2-Daten in dieser Installation)")

    # Orthostatic — sessions/session_metrics (type='orthostatic'), NICHT die
    # verwaiste orthostatic_tests-Tabelle (leer in der echten DB, wird von
    # analyse_orthostatic.py & Co. nicht gelesen; s. compute_orthostatic_detection.py
    # fuer die Herleitung dieser Zielstruktur).
    sections.append("\n## ORTHOSTASE (Brustgurt-/Handgelenk-Quelle)")
    ortho_deltas = [r[0] for r in conn.execute("""
        SELECT sm.value FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type='orthostatic' AND sm.metric='hr_delta'
    """).fetchall() if r[0] is not None]
    if ortho_deltas:
        rms_sup = [r[0] for r in conn.execute("""
            SELECT sm.value FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type='orthostatic' AND sm.metric='rmssd_supine'
        """).fetchall() if r[0] is not None]
        rms_sta = [r[0] for r in conn.execute("""
            SELECT sm.value FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type='orthostatic' AND sm.metric='rmssd_stand'
        """).fetchall() if r[0] is not None]
        avg_delta = sum(ortho_deltas) / len(ortho_deltas)
        sections.append(f"{len(ortho_deltas)} Tests | ΔHR ∅{round(avg_delta,1)} bpm (Max {round(max(ortho_deltas),1)} bpm)")
        if rms_sup and rms_sta:
            avg_sup = sum(rms_sup) / len(rms_sup)
            avg_sta = sum(rms_sta) / len(rms_sta)
            sections.append(f"RMSSD: liegend ∅{round(avg_sup,1)}ms → stehend ∅{round(avg_sta,1)}ms "
                           f"(Einbruch {round(100*(avg_sup-avg_sta)/avg_sup)}%)")
        pots = sum(1 for d in ortho_deltas if d >= 30)
        near = sum(1 for d in ortho_deltas if 15 <= d < 30)
        if pots: sections.append(f"POTS-Kriterium (≥30 bpm): {pots}× erfüllt ⚠️")
        if near: sections.append(f"Grenzwertig (15–29 bpm): {near}× — Kipptisch-Test empfohlen ⚠️")

    # Arrhythmia
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
    if "arrhythmie_episoden" in tables:
        # Quelle aus ppi_raw ableiten statt hartcodiert "Polar" zu behaupten —
        # in dieser Installation stammen die PPI-Rohdaten tatsaechlich von
        # einem Garmin-GDPR-Export (device_id -> devices.sensor_type), nicht
        # von einem Polar-Geraet.
        from modules import device_registry as _dr
        ppi_devices = {r[0] for r in conn.execute(
            "SELECT DISTINCT device FROM ppi_raw WHERE device IS NOT NULL")}
        ppi_label = ", ".join(sorted(_dr.label(d) or d for d in ppi_devices)) or "unbekannte Quelle"
        sections.append(f"\n## ARRHYTHMIE (aus PPI-Rohdaten — {ppi_label})")
        ep = conn.execute("""
            SELECT COUNT(*), ROUND(AVG(dauer_min),1), ROUND(MAX(dauer_min),0),
                   ROUND(AVG(cv_mean),3)
            FROM arrhythmie_episoden""").fetchone()
        if ep[0]:
            sections.append(f"Episoden unregelmäßiger Herzrhythmus: {ep[0]} ({ep[3]} CV∅)")
            sections.append(f"Durchschnittliche Dauer: {ep[1]} min | Längste: {ep[2]} min")
        for row in conn.execute("""
            SELECT time_of_day, COUNT(*), ROUND(AVG(dauer_min),1)
            FROM arrhythmie_episoden GROUP BY time_of_day ORDER BY 2 DESC"""):
            sections.append(f"  {row[0]}: {row[1]}× ∅{row[2]} min")
        ppi_pct = conn.execute("""
            SELECT ROUND(100.0*SUM(arrhythmie_flag)/COUNT(*),1)
            FROM ppi_windows""").fetchone()[0]
        if ppi_pct: sections.append(f"Anteil auffälliger 5-Min-Fenster: {ppi_pct}%")
        sections.append("Hinweis: PPI-basierte Detektion — klinische EKG-Kontrolle erforderlich")

    # Sleep
    sections.append("\n## SCHLAF")
    sleep = conn.execute(f"""
        SELECT ROUND(AVG(sleep_quality),3), ROUND(AVG(sleep_hours),2), COUNT(*)
        FROM daily_stress WHERE sleep_quality > 0 {year_filter}""").fetchone()
    if sleep[0]:
        sections.append(f"Schlafqualität (daily_stress): ∅{sleep[0]:.0%} | Dauer: ∅{sleep[1]:.1f}h ({sleep[2]} Nächte)")
    # sleep_cycle_nights ist ohne die Sleep-Cycle-App ein leerer Stub
    # (compat_views.py legt die View immer an — `in tables` war deshalb immer
    # wahr, unabhaengig von echten Daten; hier jetzt gegen eine echte TABELLE
    # geprueft).
    real_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "sleep_cycle_nights" in real_tables:
        sc = conn.execute("""
            SELECT COUNT(*), ROUND(AVG(bett_stunden),2),
                   ROUND(MIN(bett_stunden),1), ROUND(MAX(bett_stunden),1),
                   SUM(CASE WHEN bett_stunden < 6 THEN 1 ELSE 0 END)
            FROM sleep_cycle_nights WHERE bett_stunden > 2""").fetchone()
        if sc[0]:
            sections.append(f"Sleep Cycle: ∅{sc[1]}h | Min {sc[2]}h | Max {sc[3]}h | {sc[4]} Nächte <6h")

    # Fitness & Aktivitaet — geraeteunabhaengig. polar_fitness.own_index ist
    # Polars proprietaerer Score ohne Aequivalent bei anderen Marken (und ohne
    # Polar-Geraet ein leerer Stub); der reale, geraeteunabhaengige Kanal ist
    # measurements.metric='vo2max'. polar_daily_activity.steps/met_minutes
    # sind ebenso ein leerer Stub ohne Polar-Geraet — Schritte liegen real
    # unter measurements.metric='steps'; MET-Minuten haben in dieser
    # Installation kein Aequivalent (nicht importiert).
    sections.append("\n## FITNESS & AKTIVITÄT")
    vo2_days = load_metric_daily(conn, ("vo2max", "vo2_max"), date_from, date_to, agg="avg")
    if vo2_days:
        sections.append(f"VO2max ({_dominant_label(vo2_days)}):")
        for date, day in sorted(vo2_days.items())[-3:]:
            sections.append(f"  {date}: {day.value:.1f} ml/kg/min")
    steps_days = load_metric_daily(conn, ("steps",), date_from, date_to, agg="sum")
    if steps_days:
        vals = [d.value for d in steps_days.values()]
        sections.append(f"∅ Schritte/Tag ({_dominant_label(steps_days)}): {sum(vals)/len(vals):.0f} (MET-Minuten in dieser Installation nicht erfasst)")

    weight = conn.execute("""
        SELECT ROUND(AVG(value),1), MIN(value), MAX(value) FROM apple_records WHERE type='body_mass'""").fetchone()
    if weight[0]: sections.append(f"Körpergewicht: ∅{weight[0]} kg | {weight[1]}–{weight[2]} kg")

    conn.close()

    # EKG-Befunde aus CSV-Dateien (Apple Watch)
    sections.append("\n## EKG-BEFUNDE (Apple Watch)")
    ecg_dir = _cfg.apple_xml.parent / "electrocardiograms"
    if ecg_dir.exists():
        import csv as _csv
        from collections import Counter
        klassifizierungen = []
        for f in sorted(ecg_dir.glob("ecg_*.csv")):
            meta = {}
            try:
                with open(f) as fh:
                    for row in _csv.reader(fh):
                        if len(row) >= 2 and row[0] in ("Aufzeichnungsdatum","Klassifizierung","Symptome"):
                            meta[row[0]] = row[1].strip()
                        if row and row[0] == "Einheit":
                            break
            except Exception:
                continue
            if meta.get("Klassifizierung"):
                klassifizierungen.append((meta.get("Aufzeichnungsdatum",""), meta.get("Klassifizierung","")))

        sections.append(f"Gesamt: {len(klassifizierungen)} EKG-Aufzeichnungen")
        counts = Counter(k for _, k in klassifizierungen)
        for k, n in counts.most_common():
            flag = " ⚠️" if "Vorhofflimmern" in k else ""
            sections.append(f"  {k}: {n}x{flag}")

        af_befunde = [(dt, k) for dt, k in klassifizierungen if "Vorhofflimmern" in k]
        if af_befunde:
            sections.append(f"\nVorhofflimmern-Ereignisse: {len(af_befunde)}")
            for dt, k in af_befunde:
                sections.append(f"  {dt[:16]}: {k}")

    # Clinical Befunde aus compute_clinical.py
    conn2 = open_db()
    tables2 = {r[0] for r in conn2.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    if "clinical_findings" in tables2:
        sections.append("\n## ALGORITHMISCH VORAUSGEWERTETE KLINISCHE BEFUNDE")
        sections.append("(Berechnet aus Messdaten — nicht LLM-generiert)")
        for cat_label in [
            ("pots",        "POTS / Orthostase"),
            ("hrv",         "HRV-Analyse"),
            ("pem",         "PEM / Belastungsintoleranz"),
            ("arrhythmia",  "Arrhythmie"),
            ("spo2",        "SpO2"),
            ("sleep",       "Schlaf"),
            ("ans",         "ANS-Gesamtstatus"),
        ]:
            cat, label = cat_label
            rows = conn2.execute("""
                SELECT severity, description FROM clinical_findings
                WHERE category=? AND severity IN ('critical','warning')
                ORDER BY CASE severity WHEN 'critical' THEN 0 ELSE 1 END
            """, (cat,)).fetchall()
            if rows:
                sections.append(f"\n{label}:")
                for sev, desc in rows:
                    marker = "⚠️" if sev == "critical" else "!"
                    sections.append(f"  {marker} {desc[:200]}")
    conn2.close()

    return "\n".join(sections)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default=None, help="Jahr e.g. 2024")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    from modules.i18n import t, language_directive, get_lang
    print(t("Sammle Daten ...", "Collecting data ..."))
    data = gather_data(args.period)

    from utils.llm_provider import LLMProvider
    provider = LLMProvider.from_config()
    print(t(f"{provider.name} erstellt Arztbericht ...", f"{provider.name} generating medical report ..."))
    report  = provider.chat(t(SYSTEM_REPORT_DE, SYSTEM_REPORT_EN) + language_directive(get_lang()), data, max_tokens=5000)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"health_report_{args.period or 'all'}_{ts}.md"
    out.write_text(
        f"# Gesundheitsbericht{f' {args.period}' if args.period else ''}\n\n"
        f"*KI-generiert am {datetime.now().strftime('%Y-%m-%d %H:%M')} | Nicht for klinische Diagnose*\n\n"
        f"---\n\n## Rohdaten\n```\n{data}\n```\n\n---\n\n{report}\n",
        encoding="utf-8")

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)
    print(t(f"\n⚕️  Bericht gespeichert: {out}", f"\n⚕️  Report saved: {out}"))
    print(t("Bitte mit behandelndem Arzt besprechen — KI-generiert, keine Diagnose.",
            "Please discuss with your doctor — AI-generated, not a diagnosis."))


if __name__ == "__main__":
    main()
