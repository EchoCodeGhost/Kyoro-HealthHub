#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_acute_response.py — Retrospektive Analyse akuter Systemreaktionen

@tier        research
@purpose.de  Identifiziert akute Episoden aus der acute_events-Tabelle, clustert
             konsekutive Tage mit Score ≥ 1 zu Episoden, erstellt Zeitreihen-Plots
             mit Severity-Farbbändern und schreibt einen Markdown-Bericht mit
             optionalem LLM-Kommentar. Startet bei moderate/severe Episoden
             automatisch einen Anamnese-Dialog mit Pflicht-Redflag-Screen.
@purpose.en  Identifies acute episodes from the acute_events table, clusters
             consecutive days with score ≥ 1 into episodes, creates time-series
             plots with severity colour bands, and writes a Markdown report with
             optional LLM commentary. Launches an anamnesis dialog with mandatory
             red-flag screening for moderate/severe episodes.
@method.de   Episode-Clustering: konsekutive Tage mit score_total ≥ 1, Lücken
             bis zu 2 Tagen toleriert. Plot: score_total als Balken,
             hrv_rmssd als Linie (rechte Y-Achse), SpO2-Anomalien als Scatter.
             Severity-Bänder als Hintergrundfarben (none=weiß, mild=gelb,
             moderate=orange, severe=rot). Klinische Events aus cfg.clinical.events
             als vertikale Linien. Anamnese-Dialog: Tier 0 (Sofortcheck) →
             Tier 1 (Pflicht-Redflags: Schlaganfall/Herzinfarkt/Anaphylaxie/
             Sepsis/Zeckenstich) → Tier 2 (Leitsymptom) → Tier 3 (Module).
@method.en   Episode clustering: consecutive days with score_total ≥ 1, gaps of
             up to 2 days tolerated. Plot: score_total as bars, hrv_rmssd as line
             (right y-axis), SpO2 anomalies as scatter. Severity bands as background
             colours (none=white, mild=yellow, moderate=orange, severe=red).
             Clinical events from cfg.clinical.events as vertical lines.
             Anamnesis dialog: Tier 0 (emergency check) →
             Tier 1 (mandatory red flags: stroke/heart attack/anaphylaxis/
             sepsis/tick bite) → Tier 2 (chief complaint) → Tier 3 (modules).
@refs        Royal College of Physicians (2017). National Early Warning Score (NEWS) 2: Standardising the assessment of acute-illness severity in the NHS. RCP, London. https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/ doi: nicht verfügbar (Leitliniendokument)
             DGN/DSG AWMF 030-046 (Schlaganfall); ESC ACS 2023; WAO/EAACI Anaphylaxis 2020;
             S3 Sepsis AWMF 079-001; AWMF 013-054 (Borreliose); RKI FSME 2023
@relevance.de Ermöglicht die frühzeitige Erkennung und systematische Dokumentation
             akuter gesundheitlicher Verschlechterungen, essentiell für die
             Früherkennung von Notfällen und die retrospektive Analyse von
             Krankheitsverläufen
@relevance.en Enables early detection and systematic documentation of acute health
             deteriorations, essential for emergency recognition and retrospective
             analysis of disease progression
@reads       acute_events
@writes      analyses/infectious/acute_response_{from}_{to}.{md,png}
@limits.de   Erfordert vorangegangenen compute_acute_events-Lauf. Episoden-Clustering
             ist heuristisch (gap_days=2 parametrisiert). Kein Kausalnachweis
             zwischen Episode und Auslöser. Anamnese-Dialog ist kein validiertes
             Medizinprodukt. LLM-Kommentar erfordert konfigurierten LLM-Endpunkt.
@limits.en   Requires a prior compute_acute_events run. Episode clustering is
             heuristic (gap_days=2 parameterised). No causal link between episode
             and trigger. Anamnesis dialog is not a validated medical device.
             LLM commentary requires a configured LLM endpoint.
@usage
    python3 scripts/analysis/infectious/analyse_acute_response.py
    python3 scripts/analysis/infectious/analyse_acute_response.py --plot --no-llm
    python3 scripts/analysis/infectious/analyse_acute_response.py --from 2023-01-01 --to 2024-12-31
    python3 scripts/analysis/infectious/analyse_acute_response.py --min-severity moderate
    python3 scripts/analysis/infectious/analyse_acute_response.py --no-interactive
"""

import argparse
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from pathlib import Path
import sys

# lokaler Import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.base import resolve_person, resolve_timezone
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_infectious import (
    SYSTEM_PROMPT_ANALYSE_ACUTE_RESPONSE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_ACUTE_RESPONSE_EN as SYSTEM_PROMPT_EN,
)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

_cfg = Config()

# Konstanten
SEPSIS_WINDOW_DAYS = 14
FSME_WINDOW_DAYS = 35
BORRELIOSE_WINDOW_DAYS = 90
DEFAULT_LOOKBACK_DAYS = 90

# Severity Farben für Plot
SEVERITY_COLORS = {
    'none': '#ffffff',    # weiß
    'mild': '#fff3cd',    # helles gelb
    'moderate': '#fd7e14', # orange
    'severe': '#dc3545',  # rot
}

# Leitlinien-Diagnostik-Blöcke
LEITLINIEN_DIAGNOSTIK = {
    'sepsis': {
        'titel': 'Sepsis / schwere systemische Infektion',
        'leitlinie': 'S3-Leitlinie Sepsis (AWMF 079-001, 2018/Update 2020) + qSOFA',
        'diagnostik': [
            '🔴 BLUTKULTUR (aerob + anaerob, 2 Paare aus 2 verschiedenen Stellen) — VOR erster Antibiotikagabe abnehmen — danach verfälscht',
            '🔴 Procalcitonin (PCT) — Sepsis-Marker, steigt bei bakterieller Infektion',
            '🔴 Laktat (venös) — Laktat ≥ 2 mmol/l = Sepsis; ≥ 4 = septischer Schock',
            '🔴 Großes Blutbild (Leukozytose ≥ 12.000 oder Leukopenie ≤ 4.000)',
            '🔴 CRP (weniger spezifisch als PCT, aber Standard)',
            'Kreatinin, Bilirubin, Gerinnung (INR/Quick, PTT) — Organdysfunktion?',
            'Urinstatus + Urinkultur',
            'Bei unklarem Fokus: Röntgen Thorax, ggf. CT Abdomen/Thorax',
        ],
        'zeitkritisch': [
            '"Hour-1 Bundle" der Surviving Sepsis Campaign:',
            'Blutkultur + Laktat + Antibiotikagabe innerhalb 1 Stunde bei Schock',
            'Jede Stunde Verzögerung der Antibiose erhöht Mortalität um ~7 %'
        ]
    },
    'borreliose': {
        'titel': 'Lyme-Borreliose',
        'leitlinie': 'S3-Leitlinie Lyme-Borreliose (AWMF 013-054, 2023)',
        'stadium_i': [
            'Wanderröte ist KLINISCHE Diagnose — kein Labortest erforderlich!',
            'Sofort Therapie beginnen: Doxycyclin 100 mg 2×/Tag × 14–21 Tage',
            'Serologie in Stadium I oft noch negativ (Serokonversion 4–6 Wochen)',
        ],
        'stadium_ii': [
            'ELISA (IgM + IgG) als Suchtest',
            'Bei positivem ELISA: Bestätigungstest Western Blot',
            'Bei Neuroborreliose-Verdacht: Liquorpunktion + Liquor-ELISA',
            'Bei Karditis-Verdacht: EKG (AV-Block!)',
        ],
        'stadium_iii': [
            'IgG-Antikörper (IgM oft nicht mehr nachweisbar)',
            'Gelenkpunktat PCR bei Lyme-Arthritis',
            'MRT Gehirn bei chronischer Neuroborreliose',
        ],
        'hinweis': 'Kein zugelassener Borreliose-Impfstoff in Deutschland (VLA15/Valneva: klinische Phase III, noch nicht zugelassen).'
    },
    'fsme': {
        'titel': 'FSME (Frühsommer-Meningoenzephalitis)',
        'leitlinie': 'RKI Steckbrief FSME 2023 + AWMF-Leitlinie Virusenzephalitiden',
        'diagnostik': [
            'FSME-IgM + IgG im Serum (ab Phase 2 positiv)',
            'Bei ZNS-Symptomen: Liquorpunktion → Liquor-FSME-IgM, lymphozytäre Pleozytose',
            'MRT Gehirn/Rückenmark bei Enzephalitis / Myelitis',
            'Erreger-PCR im Serum (nur in Phase 1, kurzes Fenster — meist verpasst)',
        ],
        'therapie': [
            'KEINE KAUSALE THERAPIE verfügbar.',
            'Symptomatische Behandlung, ggf. Intensivstation',
            'Impfschutz für Kontaktpersonen prüfen',
        ],
        'meldepflicht': 'FSME ist nach IfSG §7 meldepflichtig.'
    },
    'mcas': {
        'titel': 'Mastzellaktivierungssyndrom (MCAS/MCAD)',
        'leitlinie': 'EAACI Position Paper 2022 + AWMF in Arbeit',
        'diagnose_kriterien': [
            'Konsensus-Kriterien (Valent/EAACI):',
            '1. Wiederkehrende Episoden mit Symptomen in ≥ 2 Organsystemen',
            '2. Objektiver Nachweis einer Mastzellaktivierung während Episode',
            '3. Ansprechen auf Mastzell-gerichtete Therapie',
        ],
        'diagnostik': [
            '🔴 Serum-Tryptase: Basal + 2h nach Episode (> 20% + 2 μg/l über Baseline)',
            '🔴 24h-Urin: Histamin-Metaboliten, Prostaglandin D2, Leukotrien E4',
            'Knochenmark: Mastzell-Tryptase-Immunhistochemie (bei systemischer MCAS)',
            'Flow-Zytometrie: CD25+ auf Mastzellen (bei Verdacht auf klonale MCAS)',
            'Genetik: KIT D816V Mutation (bei Mastzell-Leukämie/klonaler MCAS)',
            'Allergietest: IgE gegen spezifische Trigger',
        ],
        'therapie_akut': [
            'H1-Antihistaminika (z. B. Cetirizin 10 mg 1-2×/Tag)',
            'H2-Antihistaminika (z. B. Famotidin 20 mg 2×/Tag)',
            'Mastzellstabilisatoren: Ketotifen, Cromoglicinsäure',
            'Kortikosteroide: Prednison bei schweren Reaktionen',
            'Adrenalin: Bei Anaphylaxie (EpiPen)',
            'Leukotrien-Rezeptor-Antagonisten: Montelukast',
        ],
        'therapie_langfristig': [
            'Trigger-Meidung (Identifikation durch Ernährungstagebuch)',
            'Mastzell-stabilisierende Ernährung (niedrig-histamin, DAO-Enzym)',
            'Omalizumab (Anti-IgE) bei refraktären Fällen (Off-Label)',
            'Imatinib (Tyrosinkinase-Hemmer) bei KIT D816V+ MCAS',
        ],
        'hinweis': 'MCAS ist eine Ausschlussdiagnose. Immer andere Ursachen abklären (z. B. allergische Reaktionen, autoimmune Erkrankungen).'
    },
    'sjogren': {
        'titel': 'Sjögren-Syndrom (primär/sekundär)',
        'leitlinie': 'ACR/EULAR Klassifikationskriterien 2016',
        'klassifikation': [
            'Primäres Sjögren: ≥ 2 von 3 Kriterien:',
            '  • Positive Autoantikörper (ANA, SSA/Ro, SSB/La)',
            '  • Schirmer-Test: ≤ 5 mm in 5 Minuten (beide Augen)',
            '  • Sialometrie: ≤ 0.1 ml Speichel in 15 Minuten',
            'Sekundäres Sjögren: Bei bekannter Autoimmunerkrankung (z. B. rheumatoide Arthritis, SLE)',
        ],
        'diagnostik': [
            '🔴 Autoantikörper: ANA, SSA/Ro, SSB/La, Rheumafaktor',
            '🔴 Augen: Schirmer-Test, Fluorescein-Färbung, Rose-Bengal-Score',
            '🔴 Speichel: Sialometrie, Speicheldrüsen-Szintigraphie',
            'Lippenbiopsie: Minor-Speicheldrüsen mit Fokus-Score ≥ 1',
            'Ultra-Schall: Speicheldrüsen (Parotis, Glandula submandibularis)',
            'MRT: Bei extra-glandulärer Manifestation',
            'Blutbild: Leukopenie, Hypergammaglobulinämie, RF, CRP',
        ],
        'therapie': [
            'Sicca-Symptome:',
            '  • Augen: Tränenersatzmittel (ohne Konservierungsstoffe!), Cyclosporin A',
            '  • Mund: Speichelersatz, Pilocarpin (cholinerg), Sugarless Kaugummi',
            '  • Haut: Feuchtigkeitsspendende Cremes',
            'Systemisch: Hydroxychloroquin bei extra-glandulärer Manifestation',
            'Immunsuppression: Rituximab, Azathioprin bei schweren Verläufen',
            'Physiotherapie: Bei Gelenkbeteiligung',
        ],
        'ueberwachung': [
            'Regelmäßige augenärztliche Kontrollen (alle 6-12 Monate)',
            'Zahnpflege: 3-4× jährlich beim Zahnarzt (Karies-Risiko!)',
            'Tumor-Risiko: Erhöhtes Lymphom-Risiko (jährliche Kontrollen)',
            'Schwangerschaft: Krankheitsaktivität kann zunehmen',
        ],
        'hinweis': 'Primäres Sjögren hat ein 44-fach erhöhtes Lymphom-Risiko. Regelmäßige Tumor-Screening-Gespräche.'
    }
}


# ============================================================================
# TIER-ARCHITEKTUR FÜR ANAMNESE-DIALOG (Abschnitt 4 im Plan)
# ============================================================================

from datetime import date

# Severity-Rang für Vergleich
_SEVERITY_RANK = {'none': 0, 'mild': 1, 'moderate': 2, 'severe': 3}

def _severity_rank(severity: str) -> int:
    return _SEVERITY_RANK.get(severity, 0)


# ---------------------------------------------------------------------------
# TIER 0 — Sofortcheck
# ---------------------------------------------------------------------------

def _ask_tier0_emergency() -> bool:
    """Sofortcheck - immer als erstes, nicht überspringbar."""
    ans = input(
        "\nBRAUCHST DU JETZT SOFORT HILFE oder hast du das Gefühl, "
        "nicht warten zu können? [j/n]: "
    ).strip().lower()
    return ans in ('j', 'ja', 'y', 'yes')


def _print_emergency_exit():
    """Notfall-Ausgabe."""
    print("""
🚨 NOTRUF: 112 anrufen.
   Wenn möglich: liegenbleiben, jemanden rufen.
   Tür aufschließen wenn du allein bist.
   Dieses System kann keine Notfallhilfe leisten.""")


# ---------------------------------------------------------------------------
# TIER 1 — Pflicht-Redflags (immer durchführen, nicht überspringbar)
# ---------------------------------------------------------------------------

def run_redflag_screen(episode: dict, score_total: int, conn=None, person=None) -> dict:
    """
    Führt alle 5 Redflag-Blöcke durch.
    Gibt zurück:
      emergency: bool          — Dialog sofort abbrechen
      urgent: bool             — heute Arzt
      tier3_modules: list[str] — durch Gates aktivierte Module
      answers: dict            — alle rf_-Antworten
      recommendations: list    — Ausgabe-Texte
    """
    answers = {}
    tier3_modules = []
    emergency = False
    urgent = False
    recommendations = []

    # RF-A: Schlaganfall
    a_result = _rf_schlaganfall(answers)
    if a_result == 'emergency':
        return {'emergency': True, 'urgent': False,
                'tier3_modules': [], 'answers': answers, 'recommendations': []}

    # RF-B: Herzinfarkt
    b_result = _rf_herzinfarkt(answers)
    if b_result == 'emergency':
        return {'emergency': True, 'urgent': False,
                'tier3_modules': [], 'answers': answers, 'recommendations': []}

    # RF-C: Anaphylaxie
    c_result = _rf_anaphylaxie(answers, conn, person)
    if c_result == 'emergency':
        return {'emergency': True, 'urgent': False,
                'tier3_modules': [], 'answers': answers, 'recommendations': []}

    # RF-D: Sepsis
    d_result, d_text = _rf_sepsis(answers, score_total)
    if d_result == 'emergency':
        return {'emergency': True, 'urgent': False,
                'tier3_modules': [], 'answers': answers, 'recommendations': []}
    if d_result == 'urgent':
        urgent = True
        recommendations.append(d_text)

    # RF-E: Zeckenstich-Gate
    e_modules = _rf_zeckenstich_gate(answers)
    tier3_modules.extend(e_modules)

    return {
        'emergency': emergency, 'urgent': urgent,
        'tier3_modules': tier3_modules,
        'answers': answers, 'recommendations': recommendations,
    }


def _rf_schlaganfall(answers: dict) -> str | None:
    """Schlaganfall-Check (FAST). Grundlage: DGN/DSG AWMF 030-046"""
    print("\n── SCHLAGANFALL-CHECK (FAST) ──────────────────────────────")
    q = [
        ('rf_A1_gesicht',  "Hängt eine Gesichtshälfte herab oder kannst du nicht mehr\n"
                            "  symmetrisch lächeln?"),
        ('rf_A2_arm',      "Kannst du beide Arme gleichzeitig heben und halten?\n"
                            "  Sinkt ein Arm ab oder fühlt er sich schwach an?"),
        ('rf_A3_sprache',  "Ist deine Sprache verwaschen oder undeutlich?\n"
                            "  Kannst du 'Friede Freude Eierkuchen' klar aussprechen?"),
        ('rf_A4_kopf',     "Plötzlicher starker Kopfschmerz 'wie noch nie',\n"
                            "  Doppelbilder, Gesichtsfeldausfall oder starker Schwindel?"),
    ]
    triggered = False
    for key, text in q:
        ans = input(f"  {text} [j/n]: ").strip().lower()
        answers[key] = ans in ('j', 'ja')
        if answers[key]:
            triggered = True

    if triggered:
        print("""
🚨 SCHLAGANFALL-VERDACHT — SOFORT 112

   → 112 anrufen. Uhrzeit des ersten Symptoms merken.
   → Zeit = Hirngewebe. Thrombolyse-Fenster: 4,5 Stunden.
   → NICHTS essen oder trinken (Schluckstörung möglich).
   → Nicht selbst Auto fahren.

   Grundlage: DGN/DSG AWMF 030-046""")
        return 'emergency'
    return None


def _rf_herzinfarkt(answers: dict) -> str | None:
    """Herzinfarkt-Check. Grundlage: ESC ACS Guidelines 2023, AWMF 072-001"""
    print("\n── HERZINFARKT-CHECK ──────────────────────────────────────")
    q = [
        ('rf_B1_brustschmerz', "Druckgefühl, Enge, Brennen oder Schmerz in der Brust —\n"
                                "  jetzt oder in den letzten 30 Minuten?"),
        ('rf_B2_ausstrahlung', "Schmerz oder Taubheit in linkem Arm, Kiefer,\n"
                                "  Schulter, Hals oder Rücken?"),
        ('rf_B3_schweiss',     "Kalter Schweiß kombiniert mit Übelkeit oder Schwindel\n"
                                "  ohne klare andere Ursache?"),
        ('rf_B4_herzrasen',    "Starkes Herzrasen mit Ohnmachtsgefühl, Atemnot in Ruhe\n"
                                "  oder extremes Schwächegefühl?"),
    ]
    for key, text in q:
        ans = input(f"  {text} [j/n]: ").strip().lower()
        answers[key] = ans in ('j', 'ja')

    klassisch = answers.get('rf_B1_brustschmerz')
    atypisch  = answers.get('rf_B3_schweiss') and answers.get('rf_B4_herzrasen')

    if klassisch:
        print("""
🚨 HERZINFARKT-VERDACHT — SOFORT 112

   → Hinsetzen oder hinlegen, ruhig bleiben.
   → ASS 300 mg kauen (nicht schlucken) wenn vorhanden und keine Allergie.
   → Nichts essen oder trinken.
   → 112 anrufen, Tür aufschließen.

   Grundlage: ESC ACS Guidelines 2023""")
        return 'emergency'

    if atypisch:
        print("""
⚠️  MÖGLICHER HERZINFARKT (ATYPISCH) — SOFORT 112 ERWÄGEN

   Herzinfarkt kann ohne Brustschmerz auftreten — besonders bei Frauen.
   Kalt-feuchter Schweiß + Übelkeit + Schwäche ist eine klassische atypische Trias.
   Im Zweifel: 112 anrufen. Lieber einmal zu viel.

   Grundlage: ESC ACS Guidelines 2023""")
        return 'emergency'

    return None


def _rf_anaphylaxie(answers: dict, conn=None, person=None) -> str | None:
    """Anaphylaxie-Check. Grundlage: WAO/EAACI Anaphylaxis Guidelines 2020, AWMF 061-025"""
    print("\n── ANAPHYLAXIE-CHECK ──────────────────────────────────────")
    q = [
        ('rf_C1_ausloeser', "Kontakt mit einem Auslöser in der letzten Stunde?\n"
                             "  (Insektenstich, Nahrung, Medikament, Latex)"),
        ('rf_C2_schwellung', "Schwellung von Lippen, Zunge oder Hals?"),
        ('rf_C3_atemweg',    "Atemnot, Heiserkeit oder pfeifendes Atemgeräusch?"),
        ('rf_C4_kreislauf',  "Schwindel, Ohnmachtsgefühl, blasse oder graue Haut?"),
        ('rf_C5_haut',       "Quaddeln, Rötung oder Juckreiz am ganzen Körper?"),
    ]
    for key, text in q:
        ans = input(f"  {text} [j/n]: ").strip().lower()
        answers[key] = ans in ('j', 'ja')

    organ = answers.get('rf_C2_schwellung') or answers.get('rf_C3_atemweg') or answers.get('rf_C4_kreislauf')
    triggered = (answers.get('rf_C1_ausloeser') and organ) or (answers.get('rf_C3_atemweg') and answers.get('rf_C4_kreislauf'))

    if triggered:
        # MCAS-Hinweis: generisch prüfen (kein Diagnosename hardcoden)
        mcas_relevant = False
        if conn and person:
            try:
                import sqlite3
                mcas_check = conn.execute(
                    "SELECT 1 FROM symptoms WHERE person=? AND symptom='mcas' LIMIT 1", (person,)
                ).fetchone()
                mcas_relevant = mcas_check is not None
            except Exception:
                pass

        mcas_text = "\n   Bei bekannter Mastzellaktivierung: Notfallplan beachten." if mcas_relevant else ""

        print(f"""
🚨 ANAPHYLAXIE-VERDACHT — SOFORT 112

   → Adrenalin-Autoinjektor sofort anwenden wenn vorhanden:
     Oberschenkel außen, durch Kleidung, 10 Sekunden halten.
   → Flach hinlegen, Beine hochlegen.
     (NICHT aufsetzen bei Atemwegsbeteiligung)
   → 112 anrufen.
   → Zweite Injektion nach 5–15 Min wenn keine Besserung.{mcas_text}

   Grundlage: WAO/EAACI 2020, AWMF 061-025""")
        return 'emergency'

    return None


def _rf_sepsis(answers: dict, score_total: int) -> tuple[str | None, str]:
    """Sepsis-Check. Grundlage: S3-Leitlinie Sepsis AWMF 079-001, UK Sepsis Trust 6-Question Screen"""
    print("\n── SEPSIS-CHECK ───────────────────────────────────────────")
    q = [
        ('rf_D1_worst_ever', "Du hast das Gefühl, kränker zu sein als je zuvor in deinem Leben —\n"
                              "  oder ein starkes Gefühl, dass etwas sehr falsch ist?"),
        ('rf_D2_verwirrt',   "Bist du verwirrt, desorientiert oder fällt dir Denken / Sprechen\n"
                              "  deutlich schwerer als sonst?"),
        ('rf_D3_haut',       "Haut marmoriert (livide Flecken), kalt-klebrig-feucht,\n"
                              "  oder Lippen / Fingernägel bläulich?"),
        ('rf_D4_urin',       "Urinierst du deutlich weniger als sonst — oder gar nicht?"),
    ]
    for key, text in q:
        ans = input(f"  {text} [j/n]: ").strip().lower()
        answers[key] = ans in ('j', 'ja')

    sofort  = answers.get('rf_D3_haut') or (answers.get('rf_D1_worst_ever') and answers.get('rf_D2_verwirrt'))
    dringend = answers.get('rf_D1_worst_ever') or answers.get('rf_D4_urin')

    if sofort:
        print("""
🚨 SEPSIS-VERDACHT — SOFORT 112 oder Notaufnahme

   Sepsis ist ein medizinischer Notfall.
   Jede Stunde Verzögerung erhöht die Mortalität um ~7 %.

   → 112 anrufen oder sofort Notaufnahme aufsuchen.
   → Sag: "Ich glaube, ich habe eine Sepsis."
   → KEINE Antibiotika vor Blutkultur-Abnahme — danach verfälscht.

   Grundlage: S3-Leitlinie Sepsis AWMF 079-001""")
        return 'emergency', ''

    if dringend:
        text = (
            "⚠️  MÖGLICHE SEPSIS — HEUTE ZUM ARZT (116 117 oder Notaufnahme)\n\n"
            "   Sepsis-Frühzeichen sind oft unspezifisch.\n"
            "   'Schlimmste Erkrankung' ist ein klinisch validiertes Warnsignal (UK Sepsis Trust).\n\n"
            "   Diagnostik: CRP, Procalcitonin, Blutbild, Laktat, Blutkultur (VOR Antibiose).\n"
            "   Grundlage: S3-Leitlinie Sepsis AWMF 079-001"
        )
        print(f"\n{text}")
        return 'urgent', text

    return None, ''


def _rf_zeckenstich_gate(answers: dict) -> list[str]:
    """Zeckenstich-Gate. Aktiviert Module: borreliose, fsme"""
    print("\n── ZECKENSTICH-CHECK ──────────────────────────────────────")
    ans_e1 = input(
        "  Hattest du in den letzten 90 Tagen einen Zeckenstich,\n"
        "  oder bist du in Unterholz / langem Gras / Wald gewesen\n"
        "  und könntest gestochen worden sein ohne es zu bemerken? [j/n/weiß nicht]: "
    ).strip().lower()
    answers['rf_E1_zeckenstich'] = ans_e1

    if ans_e1 not in ('j', 'ja'):
        return []

    ans_e2 = input(
        "  Hast du eine ringförmige, sich ausdehnende Hautrötung (≥ 5 cm)\n"
        "  gesehen — auch wenn sie NICHT juckt oder schmerzt? [j/n]: "
    ).strip().lower()
    answers['rf_E2_wanderroete'] = ans_e2 in ('j', 'ja')

    if answers['rf_E2_wanderroete']:
        print("""
⚠️  BORRELIOSE-VERDACHT (STADIUM I) — HEUTE ZUM ARZT

   Wanderröte ist eine klinische Diagnose — kein Labortest erforderlich.
   Sofortige Antibiose (Doxycyclin) verhindert Spätstadien.

   → Hausarzt oder Infektiologe heute oder morgen.
   → Sag: "Ich hatte einen Zeckenstich und habe eine Wanderröte."
   → Serologie in Stadium I oft noch negativ — nicht abwarten.

   Grundlage: S3-Leitlinie Lyme-Borreliose AWMF 013-054""")

    modules = ['borreliose']
    from datetime import datetime
    if datetime.now().month in range(4, 11):  # FSME-Saison April-Oktober
        modules.append('fsme')
    return modules


# ---------------------------------------------------------------------------
# TIER 2 — Leitsymptom-Auswahl
# ---------------------------------------------------------------------------

TIER2_TO_MODULES = {
    '1': ['herz_kreislauf'],
    '2': ['atemwege'],
    '3': ['neurologie'],
    '4': ['infektion'],
    '5': ['crash_pem'],
    '6': ['gastro'],
    '7': ['haut_gelenke'],
    '8': ['allgemein'],
}


def _ask_tier2_leitsymptom() -> list[str]:
    """Leitsymptom-Auswahl mit Mehrfachauswahl."""
    print("""
── LEITSYMPTOM ─────────────────────────────────────────────
Was ist dein Hauptproblem in dieser Episode?
(Mehrfachauswahl möglich, z.B. "1,4")

  [1] Herz / Kreislauf     Herzrasen, Herzstolpern, Ohnmacht, Brustenge
  [2] Atemwege             Luftnot, Husten, SpO2 niedrig
  [3] Neurologie           Kopfschmerzen, Schwindel, Taubheit, Sehstörungen
  [4] Infektion / Fieber   Fieber, Schüttelfrost, Wundinfektion
  [5] Crash / Erschöpfung  PEM, OI, deutlich unter Baseline
  [6] Bauch / GI           Übelkeit, Erbrechen, Durchfall
  [7] Haut / Gelenke       Ausschlag, Schwellung, Gelenkschmerzen
  [8] Unklar / Allgemein   kein klares Leitsymptom
""")
    raw = input("Auswahl: ").strip()
    selected = []
    for token in raw.split(','):
        token = token.strip()
        if token in TIER2_TO_MODULES:
            selected.extend(TIER2_TO_MODULES[token])
    return selected or ['allgemein']


def _merge_modules(tier2: list[str], tier1_gates: list[str]) -> set[str]:
    """Kombiniert Module aus Tier 1 und Tier 2."""
    return set(tier2) | set(tier1_gates)


# ---------------------------------------------------------------------------
# TIER 3 — Modul-Dispatcher
# ---------------------------------------------------------------------------

def _run_module(module: str, episode: dict, cfg: Config) -> dict:
    """Führt ein spezifisches Modul aus."""
    if module == 'infektion':
        return _run_infektion_blocks(episode)
    if module == 'borreliose':
        return _run_borreliose_block(episode)
    if module == 'fsme':
        return _run_fsme_block(episode)
    # Alle anderen Module: Platzhalter
    print(f"\n  [Modul '{module}' folgt im nächsten Update]")
    return {}


def _run_infektion_blocks(episode: dict) -> dict:
    """Modul infektion — Blöcke A-C (Eintrittspforten + Sepsis-Klassik)"""
    answers = {}
    
    # Block A — Eintrittspforten
    print("\n--- Block A: Eintrittspforten & Infektionszeichen ---")
    
    a1 = input("A1: Lokale Wunde / Verletzung (Schnitt, Schürfwunde, Nagel, Verbrennung)? [j/n]: ").strip().lower()
    answers['A1_wunde'] = a1 == 'j'
    if a1 == 'j':
        answers['A1_gerötet'] = input("    Rötung/Schwellung/Wärme? [j/n]: ").strip().lower() == 'j'
        if answers['A1_gerötet']:
            answers['A1_eiter'] = input("    Eiter? [j/n]: ").strip().lower() == 'j'
            answers['A1_red_streaks'] = input("    Rote Streifen (Lymphangitis)? [j/n]: ").strip().lower() == 'j'
    
    answers['A2_insektenstich'] = input("A2: Insektenstich (Mücke, Bremse, Hornisse)? [j/n]: ").strip().lower() == 'j'
    if answers['A2_insektenstich']:
        answers['A2_rötung'] = input("    Rötung/Schwellung? [j/n]: ").strip().lower() == 'j'
        diameter = input("    Durchmesser: <5 cm / 5-10 cm / >10 cm? ").strip()
        answers['A2_durchmesser'] = diameter
    
    answers['A3_zahn'] = input("A3: Zahnbehandlung / HNO / Abszess in letzten 2 Wochen? [j/n]: ").strip().lower() == 'j'
    answers['A4_eingriffe'] = input("A4: Invasive Eingriffe (Injektion, Katheter, Akupunktur, Piercing)? [j/n]: ").strip().lower() == 'j'
    answers['A5_harnwege'] = input("A5: Brennen beim Wasserlassen, häufiger Harndrang, trüber Urin? [j/n]: ").strip().lower() == 'j'
    answers['A6_gastro'] = input("A6: Durchfall/Erbrechen ≥ 24h, blutiger Stuhl, starke Bauchschmerzen? [j/n]: ").strip().lower() == 'j'
    answers['A7_abszess'] = input("A7: Rötung/Schwellung/Wärme ohne Wunde? Eiter/Abzess? [j/n]: ").strip().lower() == 'j'
    answers['A8_atemwege'] = input("A8: Husten, Auswurf, Halsschmerzen, Brustschmerzen beim Atmen? [j/n]: ").strip().lower() == 'j'
    
    # Block B — Klassische Sepsis-Warnzeichen
    print("\n--- Block B: Klassische Sepsis-Warnzeichen ---")
    answers['B1_fieber'] = input("B1: Fieber ≥ 38,5°C ODER Untertemperatur < 36°C? [j/n]: ").strip().lower() == 'j'
    if answers['B1_fieber']:
        answers['B1_schüttelfrost'] = input("    Schüttelfrost? [j/n]: ").strip().lower() == 'j'
    
    answers['B3_atmung'] = input("B3: Atmung > 20/min in Ruhe oder Kurzatmigkeit? [j/n]: ").strip().lower() == 'j'
    answers['B4_schmerzen'] = input("B4: Starke diffuse Schmerzen ohne klare Lokalisation? [j/n]: ").strip().lower() == 'j'
    answers['B5_haut'] = input("B5: Marmorierte Haut, kalt-feucht-klebrig, Blässe, Zyanose? [j/n]: ").strip().lower() == 'j'
    
    # Block C — Nicht-klassische Zeichen
    print("\n--- Block C: Nicht-klassische / subtile Zeichen ---")
    answers['C2_schüttelfrost'] = input("C2: Schüttelfrost OHNE messbares Fieber? [j/n]: ").strip().lower() == 'j'
    answers['C3_gi'] = input("C3: Übelkeit/Erbrechen/Durchfall OHNE Magen-Darm-Erkrankung? [j/n]: ").strip().lower() == 'j'
    answers['C4_erschöpfung'] = input("C4: Extreme Erschöpfung deutlich schlimmer als üblich? [j/n]: ").strip().lower() == 'j'
    answers['C6_schwindel'] = input("C6: Schwindel/Ohnmachtsgefühl beim Aufstehen (stärker als üblich)? [j/n]: ").strip().lower() == 'j'
    
    # Tier-1-Antworten wiederverwenden
    answers['C1_verwirrt'] = answers.get('rf_D2_verwirrt', False)
    answers['C5_urin'] = answers.get('rf_D4_urin', False)
    answers['C7_worst_ever'] = answers.get('rf_D1_worst_ever', False)
    answers['B5_haut'] = answers.get('rf_D3_haut', answers.get('B5_haut', False))
    
    return answers


def _run_borreliose_block(episode: dict) -> dict:
    """Modul borreliose — Block D"""
    answers = {}
    
    print("\n--- Block D: Borreliose ---")
    
    # D1 wird aus Tier 1 übernommen
    answers['D1_wanderroete'] = answers.get('rf_E2_wanderroete', False)
    
    answers['D2_grippe'] = input("D2: Grippeähnliche Symptome nach dem Stich? [j/n]: ").strip().lower() == 'j'
    answers['D3_fazialisparese'] = input("D3: Gesichtslähmung / einseitige Muskelschwäche im Gesicht? [j/n]: ").strip().lower() == 'j'
    answers['D4_gelenkschmerz'] = input("D4: Gelenkschmerzen/-schwellungen (besonders Knie)? [j/n]: ").strip().lower() == 'j'
    answers['D5_meningism'] = input("D5: Nackenstarre, Kopfschmerzen, Lichtempfindlichkeit? [j/n]: ").strip().lower() == 'j'
    answers['D7_risikogebiet'] = input("D7: Risikogebiet (Süddeutschland, Österreich, Schweiz, Osteuropa)? [j/n]: ").strip().lower() == 'j'
    answers['D8_eingestochen'] = input("D8: Zecke vollständig entfernt? Wie lange eingestochen (Stunden)? ").strip()
    
    return answers


def _run_fsme_block(episode: dict) -> dict:
    """Modul fsme — Block E"""
    answers = {}
    
    print("\n--- Block E: FSME ---")
    
    answers['E1_impfstatus'] = input("E1: FSME-Impfstatus? [vollständig/unvollständig/nein/weiß nicht]: ").strip().lower()
    if answers['E1_impfstatus'] in ('vollständig',):
        answers['E1_auffrischung'] = input("    Wann letzte Auffrischung? ").strip()
    
    answers['E2_biphasic'] = input("E2: Zweiphasiger Verlauf (Grippe → Intervall → ZNS-Symptome)? [j/n]: ").strip().lower() == 'j'
    answers['E3_neurological'] = input("E3: Neurologische Zeichen (Lichtscheu, Übelkeit, Koordination, Lähmung)? [j/n]: ").strip().lower() == 'j'
    answers['E4_risikogebiet'] = input("E4: Risikogebiet (Bayern, BaWü, Thüringen, Sachsen, etc.)? [j/n]: ").strip().lower() == 'j'
    
    if answers['E2_biphasic'] or answers['E3_neurological']:
        print("""
🚨 FSME-ZNS-BETEILIGUNG MÖGLICH — SOFORT NEUROLOGE / NOTAUFNAHME
   Keine kausale Therapie; symptomatische Behandlung, ggf. Intensivstation.
   Meldepflicht: FSME nach §7 IfSG.
   Diagnostik: FSME-IgM + IgG im Serum; bei ZNS-Symptomen Liquorpunktion.
   Grundlage: RKI FSME 2023, AWMF Virusenzephalitiden""")
    
    return answers


# ---------------------------------------------------------------------------
# Haupteinsprungspunkt für Anamnese
# ---------------------------------------------------------------------------

def run_anamnese_dialog(episode: dict, cfg: Config, args=None, conn=None, person=None) -> dict:
    """
    Hauptfunktion für den Anamnese-Dialog.
    Führt die Tier-Architektur in der richtigen Reihenfolge aus.
    """
    # TIER 0
    if _ask_tier0_emergency():
        _print_emergency_exit()
        return {'emergency': True}

    # TIER 1 — immer, auch wenn --no-interactive
    rf_result = run_redflag_screen(episode, episode.get('max_score', 0), conn, person)
    if rf_result['emergency']:
        return rf_result

    _print_disclaimer()

    if args and getattr(args, 'no_interactive', False):
        return rf_result

    # TIER 2
    selected = _ask_tier2_leitsymptom()
    active_modules = _merge_modules(selected, rf_result.get('tier3_modules', []))

    # TIER 3
    tier3_answers = {}
    for module in active_modules:
        tier3_answers.update(_run_module(module, episode, cfg))

    all_answers = {**rf_result.get('answers', {}), **tier3_answers}
    recommendations = _generate_recommendations(all_answers, episode)
    hint = _render_clinical_hint(all_answers, episode, episode.get('max_score', 0))
    if hint:
        print(hint)

    return {'answers': all_answers, 'recommendations': recommendations}


def _print_disclaimer():
    """Einmaliger Disclaimer nach Tier 1."""
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WICHTIG: Dieses System ist kein Medizinprodukt und ersetzt keine ärztliche
Diagnose. Im Zweifel: 116 117 (Bereitschaftsdienst) oder 112 (Notfall).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")


# ---------------------------------------------------------------------------
# Spot-Monitoring-Empfehlungen (Abschnitt 4.5)
# ---------------------------------------------------------------------------

_MONITORING_INTERVALS = {
    'none':     {'pulsoxy': None,  'fieber': None},
    'mild':     {'pulsoxy': '4h',  'fieber': '4h'},
    'moderate': {'pulsoxy': '2h',  'fieber': '2h'},
    'severe':   {'pulsoxy': '1h',  'fieber': '30min'},
}


def _generate_recommendations(answers: dict, episode: dict) -> str:
    """Generiert priorisierte Handlungsempfehlungen."""
    lines = []
    
    # Pulsoxy-Empfehlung
    score_spo2 = episode.get('score_spo2', 0) if isinstance(episode, dict) else 0
    score_total = episode.get('max_score', 0) if isinstance(episode, dict) else 0
    
    if score_spo2 >= 1 or score_total >= 3:
        interval = _MONITORING_INTERVALS.get(episode.get('max_severity', 'none'), {}).get('pulsoxy', '2h')
        lines.append("📟 PULSOXIMETRIE EMPFOHLEN:")
        lines.append(f"   Sofortmessung (Ruhe, warm, 2 min sitzen)")
        lines.append(f"   Wiederholung alle {interval}")
        lines.append("   SpO₂ ≥ 97 % → normal")
        lines.append("   SpO₂ 95–96 % → Beobachten")
        lines.append("   SpO₂ 93–94 % → Arzt (116 117)")
        lines.append("   SpO₂ < 93 %  → 🚨 112")
        lines.append("   Hinweis: Kalte Finger / MCAS können Wert fälschlich senken → Messung wiederholen.")
        lines.append("")
    
    # Fiebermessung-Empfehlung
    score_temp = episode.get('score_temp', 0) if isinstance(episode, dict) else 0
    if score_temp >= 1 or score_total >= 3 or answers.get('B1_fieber'):
        interval = _MONITORING_INTERVALS.get(episode.get('max_severity', 'none'), {}).get('fieber', '2h')
        lines.append("🌡️ FIEBERMESSUNG EMPFOHLEN:")
        lines.append(f"   Sofortmessung (nach 5 min Ruhe)")
        lines.append("   < 37,0 °C    → Untertemperatur (bei Sepsis möglich!)")
        lines.append("   37,5–37,9 °C → Subfebrile Temperatur — beobachten")
        lines.append("   38,0–38.9 °C → Fieber — Arzt wenn Begleitsymptome")
        lines.append("   39,0–39,9 °C → Hohes Fieber — Arzt heute")
        lines.append("   ≥ 40,0 °C   → 🚨 Sehr hohes Fieber — 112 oder Notaufnahme")
        lines.append("")
    
    return "\n".join(lines) if lines else ""


# ---------------------------------------------------------------------------
# Strukturierter Verdachts-Hinweis-Block (Abschnitt 4.8)
# ---------------------------------------------------------------------------

REASON_LABELS = {
    'rf_D1_worst_ever':   'Subjektiv: schlimmste Erkrankung (\"worst ever\")',
    'rf_D2_verwirrt':     'Verwirrtheit / Konzentrationsstörung',
    'rf_D3_haut':         'Marmorierte, kalt-feuchte Haut',
    'rf_D4_urin':         'Reduziertes Urinieren (Perfusionszeichen)',
    'rf_B5_haut':         'Marmorierte Haut / Zyanose',
    'rf_A1_red_streaks':  'Rote Streifen (Lymphangitis) an Wunde',
    'rf_E2_wanderroete':  'Wanderröte (pathognomonisch für Borreliose)',
    'D2_grippe':          'Grippeähnliche Symptome nach Zeckenstich',
    'D3_fazialisparese':  'Gesichtslähmung / Fazialisparese',
    'D4_gelenkschmerz':   'Unklare Gelenkschwellungen',
    'D5_meningism':       'Nackenstarre / Meningismus',
    'E2_fsme_biphasic':   'Zweiphasiger Verlauf (Grippe → Intervall → ZNS)',
    'E3_neurological':    'Neurologische Symptome (Koordination, Lähmung)',
    'E4_fsme_gebiet':     'Aufenthalt in FSME-Endemiegebiet',
}


def _render_clinical_hint(answers: dict, episode: dict, score: int) -> str:
    """Generiert strukturierte Verdachts-Hinweise."""
    hints = []

    sepsis_signals = (
        answers.get('rf_D3_haut') or
        (answers.get('rf_D1_worst_ever') and answers.get('rf_D2_verwirrt')) or
        (score >= 6 and sum([
            bool(answers.get(k)) for k in
            ['rf_D1_worst_ever','B1_fieber','C4_erschoepfung','rf_D2_verwirrt']
        ]) >= 2)
    )
    if sepsis_signals:
        reasons = [REASON_LABELS[k] for k in
                   ['rf_D1_worst_ever','rf_D2_verwirrt','rf_D3_haut','rf_D4_urin']
                   if answers.get(k)]
        hints.append({
            'verdacht': 'Sepsis / schwere systemische Infektion',
            'dringlichkeit': 'NOTFALL' if answers.get('rf_D3_haut') else 'DRINGEND',
            'gruende': reasons,
        })

    if answers.get('rf_E2_wanderroete'):
        hints.append({
            'verdacht': 'Lyme-Borreliose Stadium I',
            'dringlichkeit': 'DRINGEND',
            'gruende': [REASON_LABELS['rf_E2_wanderroete']],
        })
    elif any(answers.get(k) for k in ['D2_grippe','D3_fazialisparese','D4_gelenkschmerz','D5_meningism']):
        reasons = [REASON_LABELS[k] for k in
                   ['D2_grippe','D3_fazialisparese','D4_gelenkschmerz','D5_meningism']
                   if answers.get(k)]
        hints.append({
            'verdacht': 'Lyme-Borreliose Stadium II/III (möglich)',
            'dringlichkeit': 'BALDMÖGLICHST',
            'gruende': reasons,
        })

    if answers.get('E2_fsme_biphasic') or answers.get('E3_neurological'):
        reasons = [REASON_LABELS[k] for k in ['E2_fsme_biphasic','E3_neurological','E4_fsme_gebiet']
                   if answers.get(k)]
        hints.append({
            'verdacht': 'FSME (Frühsommer-Meningoenzephalitis)',
            'dringlichkeit': 'NOTFALL' if answers.get('E3_neurological') else 'DRINGEND',
            'gruende': reasons,
        })

    if not hints:
        return ''

    lines = [
        "",
        "┌─────────────────────────────────────────────────────────────┐",
        "│  KYORO HINWEIS — KEINE DIAGNOSE                             │",
        "└─────────────────────────────────────────────────────────────┘",
        "",
        "Ich bin kein Medizinprodukt und kann keine Diagnosen stellen.",
        "Ich habe Symptommuster analysiert und liefere folgende HINWEISE",
        "MIT BEGRÜNDUNG zur ärztlichen Abklärung:",
        "",
    ]
    for h in hints:
        lines.append(f"  ▶ HINWEIS: Verdacht auf {h['verdacht']}")
        lines.append(f"    Dringlichkeit: {h['dringlichkeit']}")
        lines.append(f"    Begründung:")
        for r in h['gruende']:
            lines.append(f"      • {r}")
        lines.append(f"    → Bitte ärztlich abklären lassen.")
        lines.append("")
    lines.append("Diese Hinweise ersetzen keine ärztliche Untersuchung.")
    lines.append("Im Zweifel: 116 117 (Bereitschaftsdienst) oder 112 (Notfall).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Speicherung der Anamnese-Antworten (Abschnitt 4.7)
# ---------------------------------------------------------------------------

SEVERITY_HIGH = {'rf_A1_red_streaks', 'rf_B5_haut',
                 'rf_D3_haut', 'rf_E2_wanderroete', 'E2_fsme_biphasic', 'E3_neurological'}


def _save_anamnese(conn, episode: dict, answers: dict, person: str) -> None:
    """Speichert Anamnese-Antworten in der symptoms-Tabelle."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    for key, val in answers.items():
        if val in (None, False, 'n', 'nein', 'no', 'weiß nicht', 'unvollständig'):
            continue
        source = 'redflag_screen' if key.startswith('rf_') else 'acute_anamnese'
        severity = 2 if key in SEVERITY_HIGH else 1
        conn.execute("""
            INSERT OR IGNORE INTO symptoms
              (date, symptom, severity, source, person, imported_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (episode['start'], key, severity, source, person, now))

    recs = _generate_recommendations(answers, episode)
    conn.execute("""
        UPDATE acute_events SET notes = ?
        WHERE date = ? AND person = ?
    """, (recs[:2000], episode['start'], person))
    conn.commit()


def load_acute_events(conn, date_from, date_to, person, min_severity='none'):
    """Lädt acute_events für den angegebenen Zeitraum."""
    severity_order = {'none': 0, 'mild': 1, 'moderate': 2, 'severe': 3}
    min_severity_value = severity_order.get(min_severity, 0)

    cur = conn.execute("""
        SELECT * FROM acute_events
        WHERE date >= ? AND date <= ? AND person = ?
        ORDER BY date
    """, (date_from, date_to, person))
    cols = [col[0] for col in cur.description]
    raw_rows = cur.fetchall()

    result = []
    for raw in raw_rows:
        row = dict(zip(cols, raw))
        if severity_order.get(row['severity'], 0) >= min_severity_value:
            result.append(row)

    return result


_SEVERITY_ORDER = {'none': 0, 'mild': 1, 'moderate': 2, 'severe': 3}


def cluster_episodes(rows: list, gap_days: int = 2) -> list:
    """Gruppiert Tage mit score ≥ 1 zu Episoden; lässt bis zu gap_days Lücken zu."""
    if not rows:
        return []

    episodes = []
    current = None

    sorted_rows = sorted(rows, key=lambda r: r['date'])

    for row in sorted_rows:
        row_date = row['date']

        if row['score_total'] == 0:
            if current and _date_diff(row_date, current['end']) > gap_days:
                episodes.append(current)
                current = None
            continue

        if current is None:
            current = {
                'start': row_date,
                'end': row_date,
                'max_score': row['score_total'],
                'max_severity': row['severity'],
                'days': [row],
                'duration_days': 1
            }
        else:
            current['end'] = row_date
            current['max_score'] = max(current['max_score'], row['score_total'])
            if _SEVERITY_ORDER.get(row['severity'], 0) > _SEVERITY_ORDER.get(current['max_severity'], 0):
                current['max_severity'] = row['severity']
            current['days'].append(row)
            current['duration_days'] = _date_diff(current['end'], current['start']) + 1

    if current:
        episodes.append(current)

    return episodes


def _date_diff(date1: str, date2: str) -> int:
    """Berechnet die Differenz in Tagen zwischen zwei Datumstrings."""
    d1 = datetime.strptime(date1, "%Y-%m-%d")
    d2 = datetime.strptime(date2, "%Y-%m-%d")
    return (d1 - d2).days


def _f(v, fmt='.1f', fallback='n/a'):
    return format(v, fmt) if v is not None else fallback


def _temp_display(day: dict) -> str:
    """Formatiert die Temperatur-Zelle je nach Quelle: Beurer FT95 als
    absoluter Klinikwert, Oura/Apple als Baseline-Abweichung."""
    if day.get('temp_method') == 'beurer_absolute':
        return f"{_f(day.get('temp_abs_c'))}°C (klin.)"
    return f"{_f(day.get('temp_deviation_c'), '+.1f')}°C (Abw.)"


def render_markdown(episodes: list, date_from: str, date_to: str, rows: list, cfg: Config,
                     no_llm: bool = False) -> str:
    """Erstellt einen Markdown-Bericht."""
    lines = []
    
    lines.append(f"# Akute systemische Reaktionen — {date_from} bis {date_to}")
    lines.append("")
    
    # Zusammenfassung
    lines.append("## Zusammenfassung")
    lines.append("")
    
    total_episodes = len(episodes)
    total_days = sum(1 for row in rows if row['score_total'] >= 1)
    
    lines.append(f"- **{total_episodes} Episoden** erkannt ({total_days} Tage mit Score ≥ 1)")
    
    if episodes:
        strongest = max(episodes, key=lambda e: e['max_score'])
        lines.append(f"- Stärkste Episode: {strongest['start']} – {strongest['end']} ({strongest['duration_days']} Tage) "
                    f"(Score {strongest['max_score']}, Severity: {strongest['max_severity']})")
    
    lines.append("")
    
    # Episoden-Details
    lines.append("## Episoden")
    lines.append("")
    
    for i, episode in enumerate(episodes, 1):
        lines.append(f"### Episode {i}: {episode['start']} – {episode['end']} ({episode['duration_days']} Tage)")
        lines.append(f"Peak-Score: {episode['max_score']} ({episode['max_severity']})")
        lines.append("")
        
        # Tages-Details für die Episode
        lines.append("| Datum | Score | HR | SpO₂ | AF | Temp | HRV | Symptome |")
        lines.append("|---|---|---|---|---|---|---|---|")
        
        for day in episode['days']:
            lines.append(f"| {day['date']} | {day['score_total']} | {_f(day['hr_bpm'])} | {_f(day['spo2_pct'])} | {_f(day['rr_rpm'])} | {_temp_display(day)} | {_f(day['hrv_rmssd_ms'])} | {day['symptom_count']} |")
        
        lines.append("")
        
        # Peak-Werte anzeigen
        peak_day = max(episode['days'], key=lambda d: d['score_total'])
        lines.append("#### Peak-Werte:")
        lines.append(f"- HR: {_f(peak_day['hr_bpm'])} bpm (Score: {peak_day['score_hr']})")
        lines.append(f"- SpO₂: {_f(peak_day['spo2_pct'])}% (Score: {peak_day['score_spo2']})")
        lines.append(f"- Atemfrequenz: {_f(peak_day['rr_rpm'])} rpm (Score: {peak_day['score_rr']})")
        lines.append(f"- Temperatur: {_temp_display(peak_day)} (Score: {peak_day['score_temp']})")
        lines.append(f"- HRV: {_f(peak_day['hrv_rmssd_ms'])}ms vs. Baseline {_f(peak_day['hrv_baseline_ms'])}ms (Score: {peak_day['score_hrv']})")
        lines.append(f"- Symptome: {peak_day['symptom_count']} (Score: {peak_day['score_symptoms']})")
        lines.append("")
        
        # Quellen und fehlende Domänen für diese Episode
        all_sources = set()
        all_missing = set()
        for day in episode['days']:
            if day['sources_used']:
                all_sources.update(day['sources_used'].split(','))
            if day['missing_domains']:
                all_missing.update(day['missing_domains'].split(','))
        
        lines.append(f"**Quellen:** {', '.join(sorted(all_sources)) if all_sources else 'keine'}")
        lines.append(f"**Fehlende Domänen:** {', '.join(sorted(all_missing)) if all_missing else 'keine'}")
        lines.append("")
    
    # Fehlende Datendomänen (Gesamt)
    lines.append("## Fehlende Datendomänen")
    lines.append("")
    
    missing_by_date = {}
    for row in rows:
        if row['missing_domains']:
            missing_by_date[row['date']] = row['missing_domains']
    
    if missing_by_date:
        for date_str, missing in missing_by_date.items():
            lines.append(f"- {date_str}: {missing}")
    else:
        lines.append("Keine fehlenden Domänen im analysierten Zeitraum.")
    
    lines.append("")

    report_so_far = "\n".join(lines)

    llm_text = "" if no_llm else _run_llm(report_so_far)
    lines.append("## Klinische Interpretation")
    lines.append("")
    lines.append(llm_text if llm_text else t(
        "*(kein LLM-Kommentar verfügbar)*", "*(no LLM commentary available)*"))

    return "\n".join(lines)


def render_plot(rows: list, episodes: list, output_path: Path, cfg: Config):
    """Erstellt einen Plot mit Severity-Farbbändern."""
    if not rows:
        print("Keine Daten zum Plotten verfügbar.")
        return
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), 
                                   gridspec_kw={'height_ratios': [3, 1]},
                                   sharex=True)
    
    # Hauptplot (Score und Vitaldaten)
    dates = [datetime.strptime(row['date'], "%Y-%m-%d") for row in rows]
    scores = [row['score_total'] for row in rows]
    hrv_values = [row['hrv_rmssd_ms'] if row['hrv_rmssd_ms'] else 0 for row in rows]
    spo2_values = [row['spo2_pct'] if row['spo2_pct'] else 100 for row in rows]
    
    # Hintergrundbänder für Severity
    for row in rows:
        row_date = datetime.strptime(row['date'], "%Y-%m-%d")
        severity = row['severity']
        color = SEVERITY_COLORS.get(severity, '#ffffff')
        # Fülle den Bereich für diesen Tag
        ax1.axvspan(row_date, row_date + timedelta(days=1),
                   color=color, alpha=0.3, lw=0)
    
    # Score als Balken
    bars = ax1.bar(dates, scores, width=0.8, color='black', alpha=0.7)
    ax1.set_ylabel('Score', fontsize=12, fontweight='bold')
    ax1.set_ylim(0, 18)
    ax1.set_yticks(range(0, 19, 2))
    ax1.grid(True, alpha=0.3)
    
    # HRV als Linie (rechte Achse)
    line_hrv, = ax1.plot(dates, hrv_values, 'b-', linewidth=2, label='HRV (ms)')
    ax1_right = ax1.twinx()
    ax1_right.set_ylabel('HRV (ms)', fontsize=10, color='blue')
    ax1_right.tick_params(axis='y', colors='blue')
    ax1_right.set_ylim(0, max(hrv_values + [100]) * 1.1 if hrv_values else 100)
    
    # SpO2 < 95% als rote Punkte
    spo2_low_dates = []
    spo2_low_values = []
    for i, (point_date, spo2) in enumerate(zip(dates, spo2_values)):
        if spo2 < 95:
            spo2_low_dates.append(point_date)
            spo2_low_values.append(spo2)
    
    if spo2_low_dates:
        ax1.scatter(spo2_low_dates, [1] * len(spo2_low_dates), 
                   color='red', s=100, marker='v', label='SpO₂ < 95%', zorder=5)
    
    # Episoden markieren
    for episode in episodes:
        start_date = datetime.strptime(episode['start'], "%Y-%m-%d")
        end_date = datetime.strptime(episode['end'], "%Y-%m-%d")
        ax1.axvline(start_date, color='red', linestyle='--', alpha=0.7)
        ax1.axvline(end_date, color='red', linestyle='--', alpha=0.7)
    
    # Clinische Events (falls verfügbar)
    try:
        clinical_events = cfg.clinical.events if hasattr(cfg.clinical, 'events') else []
        for event in clinical_events:
            try:
                event_date = datetime.strptime(event.get('date', ''), "%Y-%m-%d")
                ax1.axvline(event_date, color='purple', linestyle=':', alpha=0.8, 
                           label=f"Event: {event.get('description', '?')}")
            except (ValueError, AttributeError):
                continue
    except Exception:
        pass
    
    # Legende und Titel
    ax1.set_title('Akute systemische Reaktionen — NEWS2-Lite Score', 
                  fontsize=14, fontweight='bold', pad=20)
    
    # Zweite Achse für Details (optional - könnte für Symptom-Anzahl genutzt werden)
    symptom_counts = [row['symptom_count'] for row in rows]
    ax2.bar(dates, symptom_counts, color='green', alpha=0.6)
    ax2.set_ylabel('Symptome', fontsize=10)
    ax2.set_ylim(0, max(symptom_counts + [5]) * 1.2 if symptom_counts else 5)
    ax2.grid(True, alpha=0.3)
    
    # Formatierung
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    
    # Legende
    handles, labels = ax1.get_legend_handles_labels()
    if spo2_low_dates:
        handles.append(plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='red', markersize=10, label='SpO₂ < 95%'))
        labels.append('SpO₂ < 95%')
    
    if len(handles) > 0:
        ax1.legend(handles, labels, loc='upper left')
    
    # Speichern
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    
    print(f"Plot gespeichert: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analysiert akute systemische Reaktionen und erstellt Berichte/Plots"
    )
    parser.add_argument("--from", type=str, default=None,
                        help="Startdatum (YYYY-MM-DD, Standard: 90 Tage vor heute)")
    parser.add_argument("--to", type=str, default=None,
                        help="Enddatum (YYYY-MM-DD, Standard: heute)")
    parser.add_argument("--plot", action="store_true",
                        help="Plot erzeugen")
    parser.add_argument("--no-llm", action="store_true",
                        help="Keinen LLM-Kommentar generieren")
    parser.add_argument("--llm", action="store_true",
                        help="LLM-Kommentar erzwingen")
    parser.add_argument("--min-severity", type=str, default='none',
                        choices=['none', 'mild', 'moderate', 'severe'],
                        help="Mindest-Severity für Analyse (Standard: none)")
    parser.add_argument("--person", type=str, default=None,
                        help="Person-ID (Standard: eigene ID)")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Interaktiven Dialog deaktivieren")
    parser.add_argument("--interactive", action="store_true",
                        help="Interaktiven Dialog erzwingen")
    add_lang_arg(parser)
    
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    # Person-ID auflösen
    person = resolve_person(args.person) if args.person else OWN_PERSON_ID
    
    # Ausgabeverzeichnis
    output_dir = _cfg.analyses_dir / "infectious"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Datenbankverbindung
    with open_db() as conn:
        # Datumsbereich festlegen (innerhalb der Connection, da resolve_timezone conn braucht)
        from modules.base import resolve_timezone
        tz_str = resolve_timezone(conn, person)
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_str)
        today = datetime.now(tz).strftime("%Y-%m-%d")

        date_from_arg = getattr(args, 'from', None)
        if date_from_arg:
            date_from = date_from_arg
        else:
            from_date_obj = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            date_from = from_date_obj.strftime("%Y-%m-%d")

        date_to_arg = getattr(args, 'to', None)
        if date_to_arg:
            date_to = date_to_arg
        else:
            date_to = today
        
        # Daten laden
        print(f"Lade acute_events von {date_from} bis {date_to}...")
        rows = load_acute_events(conn, date_from, date_to, person, args.min_severity)
        
        if not rows:
            print("Keine Daten in acute_events für den angegebenen Zeitraum gefunden.")
            print("Führe zuerst compute_acute_events.py aus.")
            return
        
        print(f"Geladen: {len(rows)} Tage mit Score ≥ {args.min_severity}")
        
        # Episoden clustern
        episodes = cluster_episodes(rows, gap_days=2)
        print(f"Identifiziert: {len(episodes)} Episoden")
        
        # Interaktiver Anamnese-Dialog für moderate/severe Episoden
        if not args.no_interactive and (args.interactive or any(
            ep['max_severity'] in ('moderate', 'severe') and ep['duration_days'] >= 2 
            for ep in episodes
        )):
            for episode in episodes:
                if episode['max_severity'] in ('moderate', 'severe') and episode['duration_days'] >= 2:
                    print(f"\n--- Anamnese-Dialog für Episode {episode['start']} – {episode['end']} ---")
                    answers = run_anamnese_dialog(episode, _cfg, args, conn, person)
                    
                    # Speichern
                    _save_anamnese(conn, episode, answers, person)
                    
                    # Clinical Hint generieren und anzeigen
                    clinical_hint = _render_clinical_hint(answers, episode, episode['max_score'])
                    if clinical_hint:
                        print(clinical_hint)
                    
                    # Empfehlungen
                    recommendations = _generate_recommendations(answers, episode)
                    if recommendations:
                        print("\n" + "="*50)
                        print("HANDLUNGSEMPFEHLUNGEN")
                        print("="*50)
                        print(recommendations)
                        print("\nDiese Empfehlungen ersetzen keine ärztliche Untersuchung.")
        
        # Markdown-Bericht erstellen
        markdown_content = render_markdown(episodes, date_from, date_to, rows, _cfg,
                                            no_llm=args.no_llm)
        markdown_path = output_dir / f"acute_response_{date_from}_{date_to}.md"
        
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"Markdown-Bericht gespeichert: {markdown_path}")
        
        # Plot erstellen
        if args.plot:
            plot_path = output_dir / f"acute_response_{date_from}_{date_to}.png"
            render_plot(rows, episodes, plot_path, _cfg)
        
        print("Analyse abgeschlossen.")


if __name__ == "__main__":
    import sqlite3
    main()