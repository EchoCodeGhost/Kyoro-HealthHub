#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_skin.py — Hautlaesionen Verlaufsanalyse

@tier        heuristic
@refs        Esteva A, Kuprel B, Novoa RA et al. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542(7639):115-118. doi:10.1038/nature21056
             Tschandl P, Codella N, Akay BN et al. (2019). Comparison of the accuracy of human readers versus machine-learning algorithms for pigmented skin lesion classification: an open, web-based, international, diagnostic study. The Lancet Oncology, 20(7):938-947. doi:10.1016/S1470-2045(19)30333-X

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@purpose.de  Zeigt zeitlichen Verlauf von Hautläsionen mit LLM/VLM-Analyse
@purpose.en  Shows temporal progression of skin lesions with LLM/VLM analysis
@method.de   Analysiert Hautläsionen und zeigt:
             - Übersicht aller Läsionen mit aktuellem Triage-Status
             - Zeitachse einer einzelnen Läsion (alle Fotos + VLM-Befunde)
             - VLM-Analyse aller noch nicht analysierten Fotos (--analyse)
             - LLM-Delta-Analyse: Veränderungen zwischen Aufnahmen
@method.en   Analyzes skin lesions and shows:
             - Overview of all lesions with current triage status
             - Timeline of a single lesion (all photos + VLM findings)
             - VLM analysis of all unanalyzed photos (--analyse)
             - LLM delta analysis: changes between recordings
@reads       lesion_photos, lesion_metadata
@writes      Analyseergebnisse als Markdown
@limits.de   Heuristische Methode. VLM/LLM-Analyse kann ungenau sein.
@limits.en   Heuristic method. VLM/LLM analysis may be inaccurate.
@scoring Triage-Score basierend auf Läsionsgröße, Veränderungsrate und VLM-Klassifikation
@prompt-classification LLM:Analysis
@prompt.de    _SYSTEM_DE, _SYSTEM_EN
@prompt.en    _SYSTEM_DE, _SYSTEM_EN
@usage
    python3 scripts/analysis/analyse_skin.py              # Uebersicht alle Laesionen
    python3 scripts/analysis/analyse_skin.py --analyse    # VLM fuer alle neuen Fotos
    python3 scripts/analysis/analyse_skin.py --lesion 3   # Verlauf Laesion 3
    python3 scripts/analysis/analyse_skin.py --lesion 3 --compare  # LLM-Delta
    python3 scripts/analysis/analyse_skin.py --watch-list  # Nur Laesionen mit Handlungsbedarf
"""

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config, OWN_PERSON_ID
from modules.db import open_medicine_imaging_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import call_llm
from modules.prompts.analysis_manual import (
    SYSTEM_PROMPT_ANALYSE_SKIN_DE_STR as _SYSTEM_DE,
    SYSTEM_PROMPT_ANALYSE_SKIN_EN_STR as _SYSTEM_EN
)

cfg     = Config()
OUT_DIR = cfg.analyses_dir / "manual"

TRIAGE_ORDER = {"sofort": 0, "zeitnah": 1, "verlauf": 2, "unauffaellig": 3, "unbekannt": 4}
TRIAGE_SYM   = {"sofort": "🔴", "zeitnah": "🟡", "verlauf": "🟢",
                 "unauffaellig": "✅", "unbekannt": "❓"}

VLM_PROMPT_DE = """\
Analysiere dieses Hautfoto klinisch nach dermoskopischen Kriterien.
Falls es sich um einen Screenshot einer Screening-App handelt, werte auch deren sichtbare Angaben aus.

**ABCDE-Kriterien:**
- **A — Asymmetrie:** symmetrisch oder asymmetrisch? In wievielen Achsen?
- **B — Begrenzung (Border):** scharf/unscharf, regelmäßig/unregelmäßig, ausgefranst?
- **C — Colorierung:** Farben (braun/schwarz/rot/weiß/blau-grau)? Homogen oder heterogen?
- **D — Durchmesser:** Größenschätzung (falls Referenzobjekt sichtbar)?
- **E — Entwicklung:** aus Einzelfoto nicht beurteilbar — nicht bewerten

**Zusätzliche Merkmale:**
- Oberfläche: glatt, schuppig, verruköse Struktur, Erosion, Ulzeration?
- Pigmentnetz: regelmäßig oder atypisch/unterbrochen/ausgefranst?
- Gefäße: atypische Gefäßmuster (Punkt-, Globuli-, irreguläre Gefäße)?
- Strukturen: Globuli, Punkte, Regressionszonen, weißlicher Schleier, Milien-ähnliche Zysten?
- Läsionstyp: melanozytär vs. nicht-melanozytär?

**Differenzialdiagnosen** (wahrscheinlichste zuerst, mit kurzer Begründung):

**Triage-Empfehlung:**
🔴 Sofort zum Dermatologen (< 2 Wochen)
🟡 Zeitnah (innerhalb 4–8 Wochen)
🟢 Verlaufskontrolle (6–12 Monate, Eigenfoto)
✅ Unauffällig

**Begründung der Triage:** (1–2 Sätze)

Falls Bildqualität für Beurteilung unzureichend: bitte explizit sagen und was fehlt."""

VLM_PROMPT_EN = """\
Analyze this skin photo clinically using dermoscopic criteria.
If this is a screenshot from a screening app, also evaluate any visible app findings.

**ABCDE criteria:**
- **A — Asymmetry:** symmetric or asymmetric? In how many axes?
- **B — Border:** sharp/blurry, regular/irregular, notched?
- **C — Color:** colors present (brown/black/red/white/blue-gray)? Homogeneous or heterogeneous?
- **D — Diameter:** size estimate (if reference object visible)?
- **E — Evolution:** cannot be assessed from single photo — skip

**Additional features:**
- Surface: smooth, scaly, verrucous, erosion, ulceration?
- Pigment network: regular or atypical/disrupted/frayed?
- Vessels: atypical vascular patterns (dotted, globular, irregular)?
- Structures: globules, dots, regression zones, white veil, milia-like cysts?
- Lesion type: melanocytic vs. non-melanocytic?

**Differential diagnoses** (most likely first, brief rationale):

**Triage recommendation:**
🔴 See dermatologist immediately (< 2 weeks)
🟡 Soon (within 4–8 weeks)
🟢 Follow-up (6–12 months, self-photo)
✅ Unremarkable

**Triage rationale:** (1–2 sentences)

If image quality is insufficient for assessment: please state explicitly and what is missing."""




def _triage_flag(response: str) -> str:
    for line in response.splitlines():
        if "🔴" in line: return "sofort"
        if "🟡" in line: return "zeitnah"
        if "🟢" in line: return "verlauf"
        if "✅" in line: return "unauffaellig"
    return "unbekannt"


# ── VLM ───────────────────────────────────────────────────────────────────────

def _analyse_pending(conn, lang: str) -> int:
    """Analysiert alle imaging_files ohne Eintrag in imaging_analysis. Gibt Anzahl zurück."""
    rows = conn.execute("""
        SELECT f.id, f.file_path, f.lesion_id, f.acquisition_date
        FROM imaging_files f
        WHERE f.person=? AND f.image_type='skin_lesion'
          AND NOT EXISTS (SELECT 1 FROM imaging_analysis a WHERE a.file_id=f.id)
        ORDER BY f.acquisition_date, f.id
    """, (OWN_PERSON_ID,)).fetchall()

    if not rows:
        print(t("Alle Fotos bereits analysiert.", "All photos already analysed."))
        return 0

    print(t(f"{len(rows)} Foto(s) ohne VLM-Analyse.", f"{len(rows)} photo(s) without VLM analysis."))
    prompt  = VLM_PROMPT_DE if lang == "de" else VLM_PROMPT_EN
    system  = _SYSTEM_DE    if lang == "de" else _SYSTEM_EN
    llm_mdl = cfg._cfg.get("llm", {}).get("openrouter_model", "anthropic/claude-opus-4-8")
    done    = 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for file_id, file_path, lesion_id, acq_date in rows:
        fp = Path(file_path)
        if not fp.exists():
            print(t(f"  Datei fehlt: {fp}", f"  File missing: {fp}"), file=sys.stderr)
            continue
        print(t(f"  VLM — {fp.name} [Läsion {lesion_id}] …",
                f"  VLM — {fp.name} [Lesion {lesion_id}] …"))
        try:
            img_b64  = base64.b64encode(fp.read_bytes()).decode()
            response = call_llm(prompt, system=system, image_b64=img_b64,
                                max_tokens=1400, temperature=0.1, label_output=False)
        except Exception as e:
            print(t(f"  VLM-Fehler: {e}", f"  VLM error: {e}"), file=sys.stderr)
            continue

        triage = _triage_flag(response)
        now    = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO imaging_analysis
              (file_id, ts, model, prompt, response, findings_json, source)
            VALUES (?,?,?,?,?,?,?)
        """, (file_id, now, llm_mdl, prompt, response,
              json.dumps({"triage": triage}), "vlm_skin"))

        date_str = (acq_date or now[:10]).replace("-", "")
        out = OUT_DIR / f"skin_{date_str}_{lesion_id:04d}_{fp.stem}.md"
        out.write_text(
            f"# Hautläsion {lesion_id} — Analyse {acq_date or now[:10]}\n\n"
            f"**Modell:** {llm_mdl}  \n**Datei:** {fp.name}  \n"
            f"**Triage:** {TRIAGE_SYM.get(triage,'?')} {triage}\n\n---\n\n{response}\n",
            encoding="utf-8",
        )
        print(t(f"  → {TRIAGE_SYM.get(triage,'?')} {triage}  {out.name}",
                f"  → {TRIAGE_SYM.get(triage,'?')} {triage}  {out.name}"))
        done += 1
        # Pro Foto committen, nicht erst am Ende der Schleife: die "noch offen"-
        # Abfrage prueft NOT EXISTS gegen imaging_analysis — ohne Commit hier wuerde
        # ein Absturz nach Foto N bereits bezahlte VLM-Analysen bei Fotos 1..N-1
        # beim naechsten Lauf unbemerkt nochmal (und nochmal bezahlt) ausloesen.
        conn.commit()

    return done


# ── Daten laden ───────────────────────────────────────────────────────────────

def _load_lesions(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT l.id, l.body_location, l.first_seen, l.last_checked,
               l.app_score, l.app_name,
               l.dermatologist_assessment, l.dermatologist_date,
               l.operated, l.operation_date,
               l.histology, l.histology_subtype, l.histology_date,
               l.notes,
               COUNT(f.id) AS foto_count
        FROM skin_lesions l
        LEFT JOIN imaging_files f ON f.lesion_id = l.id
        WHERE l.person=?
        GROUP BY l.id ORDER BY l.first_seen DESC
    """, (OWN_PERSON_ID,)).fetchall()

    cols = ["id","body_location","first_seen","last_checked","app_score","app_name",
            "derm_assessment","derm_date","operated","op_date",
            "histology","hist_subtype","hist_date","notes","foto_count"]
    return [dict(zip(cols, r)) for r in rows]


def _load_timeline(conn, lesion_id: int) -> list[dict]:
    rows = conn.execute("""
        SELECT f.id, f.acquisition_date, f.file_path, f.source_type,
               a.response, a.findings_json, a.ts AS analysis_ts
        FROM imaging_files f
        LEFT JOIN imaging_analysis a ON a.file_id = f.id AND a.source LIKE 'vlm%'
        WHERE f.lesion_id=? AND f.person=?
        ORDER BY f.acquisition_date, f.id
    """, (lesion_id, OWN_PERSON_ID)).fetchall()

    cols = ["file_id","date","file_path","source_type","vlm_response","findings_json","analysis_ts"]
    # Deduplizieren: je Foto nur die neueste Analyse
    seen: dict[int, dict] = {}
    for r in rows:
        d = dict(zip(cols, r))
        fid = d["file_id"]
        if fid not in seen or (d["analysis_ts"] or "") > (seen[fid]["analysis_ts"] or ""):
            seen[fid] = d
    return sorted(seen.values(), key=lambda x: x["date"])


def _triage_from_row(row: dict) -> str:
    fj = row.get("findings_json")
    if fj:
        try:
            return json.loads(fj).get("triage", "unbekannt")
        except Exception:
            pass
    resp = row.get("vlm_response") or ""
    for line in resp.splitlines():
        if "🔴" in line: return "sofort"
        if "🟡" in line: return "zeitnah"
        if "🟢" in line: return "verlauf"
        if "✅" in line: return "unauffaellig"
    return "unbekannt"


# ── Übersicht ─────────────────────────────────────────────────────────────────

def _render_overview(lesions: list[dict], conn, watch_only: bool) -> str:
    lines: list[str] = []
    lines.append(t("# Hautläsionen — Übersicht", "# Skin Lesions — Overview"))
    lines.append(f"{t('Gesamt', 'Total')}: {len(lesions)}  |  "
                 f"{t('Stand', 'As of')}: {datetime.now().strftime('%Y-%m-%d')}\n")

    # Triage pro Läsion aus letztem Foto ermitteln
    enriched = []
    for l in lesions:
        timeline = _load_timeline(conn, l["id"])
        last_triage = "unbekannt"
        for entry in reversed(timeline):
            if entry["vlm_response"]:
                last_triage = _triage_from_row(entry)
                break
        enriched.append((l, timeline, last_triage))

    if watch_only:
        enriched = [(l, tl, tr) for l, tl, tr in enriched
                    if tr in ("sofort", "zeitnah") and not l["histology"]]
        lines.append(t("## Handlungsbedarf (🔴 sofort / 🟡 zeitnah, noch kein Hautarzt-Befund)",
                       "## Action needed (🔴 immediate / 🟡 soon, no dermatologist result yet)"))
        if not enriched:
            lines.append(t("✓ Keine offenen Auffälligkeiten.", "✓ No pending findings."))
            return "\n".join(lines)
        lines.append("")

    for l, timeline, last_triage in sorted(enriched,
            key=lambda x: TRIAGE_ORDER.get(x[2], 9)):
        sym  = TRIAGE_SYM.get(last_triage, "❓")
        op   = t(" | operiert", " | operated") if l["operated"] else ""
        hist = f" | {l['histology']}" if l["histology"] else ""
        derm = t(" | Hautarzt ✓", " | Derm ✓") if l["derm_assessment"] else ""
        fotos = l["foto_count"]
        last  = l["last_checked"] or l["first_seen"]

        lines.append(f"{sym} **ID {l['id']}** — {l['body_location']}")
        lines.append(f"   Erstgesehen: {l['first_seen']}  |  "
                     f"Zuletzt: {last}  |  "
                     f"{fotos} {t('Foto(s)', 'photo(s)')}{op}{hist}{derm}")
        if l["app_score"]:
            lines.append(f"   App ({l['app_name'] or '?'}): {l['app_score']}")
        if l["derm_assessment"]:
            lines.append(f"   {t('Hautarzt', 'Dermatologist')}: {l['derm_assessment']}")
        lines.append("")

    return "\n".join(lines)


# ── Verlauf einer Läsion ──────────────────────────────────────────────────────

def _render_lesion(lesion: dict, timeline: list[dict]) -> str:
    lines: list[str] = []
    lines.append(f"# {t('Verlauf Läsion', 'Lesion Timeline')} {lesion['id']} — {lesion['body_location']}")
    lines.append(f"\n{t('Erstgesehen', 'First seen')}: {lesion['first_seen']}  |  "
                 f"{t('Aufnahmen', 'Photos')}: {len(timeline)}\n")

    if lesion["histology"]:
        lines.append(f"**{t('Histologie', 'Histology')}:** {lesion['histology']}"
                     + (f" — {lesion['hist_subtype']}" if lesion["hist_subtype"] else "")
                     + (f"  ({lesion['hist_date']})" if lesion["hist_date"] else ""))
    if lesion["derm_assessment"]:
        lines.append(f"**{t('Hautarzt', 'Dermatologist')}:** {lesion['derm_assessment']}"
                     + (f"  ({lesion['derm_date']})" if lesion["derm_date"] else ""))
    if lesion["operated"]:
        lines.append(f"**{t('Operiert', 'Operated')}:** "
                     + (lesion["op_date"] or t("ja", "yes")))
    lines.append("")

    # Kompakte Zeitachse
    lines.append(f"## {t('Zeitachse', 'Timeline')}")
    lines.append(f"{'Datum':<14} {'Quelle':<12} {'Triage':<10} {'Befund (Kurzfassung)'}")
    lines.append("─" * 80)
    for entry in timeline:
        triage = _triage_from_row(entry) if entry["vlm_response"] else "—"
        sym    = TRIAGE_SYM.get(triage, "—")
        src    = entry["source_type"] or "?"
        fname  = Path(entry["file_path"]).name
        # Erste inhaltliche Zeile des VLM-Responses (Triage-Zeile überspringen)
        summary = ""
        if entry["vlm_response"]:
            for line in entry["vlm_response"].splitlines():
                line = line.strip()
                if line and not any(s in line for s in ["🔴","🟡","🟢","✅","**Triage","**Empfehlung"]):
                    summary = line[:55]
                    break
        lines.append(f"{entry['date']:<14} {src:<12} {sym} {triage:<8} {summary}")

    lines.append("")

    # Vollständige VLM-Befunde chronologisch
    lines.append(f"## {t('VLM-Befunde im Verlauf', 'VLM Assessments Over Time')}\n")
    for i, entry in enumerate(timeline, 1):
        fname  = Path(entry["file_path"]).name
        triage = _triage_from_row(entry) if entry["vlm_response"] else None
        sym    = TRIAGE_SYM.get(triage, "") if triage else ""
        lines.append(f"### {t('Aufnahme', 'Photo')} {i} — {entry['date']}  "
                     f"({entry['source_type'] or '?'})  {sym}")
        lines.append(f"*{t('Datei', 'File')}: {fname}*\n")
        if entry["vlm_response"]:
            lines.append(entry["vlm_response"])
        else:
            lines.append(t("_(Keine VLM-Analyse vorhanden — mit --analyse ausführen)_",
                           "_(No VLM analysis — run with --analyse)_"))
        lines.append("")

    return "\n".join(lines)


# ── LLM Delta-Analyse ─────────────────────────────────────────────────────────

def _llm_delta(lesion: dict, timeline: list[dict], lang: str) -> str:
    analysed = [e for e in timeline if e["vlm_response"]]
    if len(analysed) < 2:
        return t("Mindestens 2 VLM-Analysen nötig für Verlaufsvergleich.",
                 "At least 2 VLM analyses needed for comparison.")

    entries_text = ""
    for e in analysed:
        entries_text += f"\n### Aufnahme {e['date']} ({e['source_type'] or '?'})\n"
        entries_text += e["vlm_response"] + "\n"

    prompt = t(
        f"Vergleiche diese {len(analysed)} VLM-Hautanalysen einer Läsion ({lesion['body_location']}) "
        f"chronologisch:\n{entries_text}\n\n"
        "Bitte bewerte:\n"
        "1. **Stabilität:** Ist die Läsion stabil, rückläufig oder progredient?\n"
        "2. **Veränderungen:** Was hat sich konkret verändert (ABCDE-Kriterien, Farbe, Begrenzung)?\n"
        "3. **Triage-Entwicklung:** Hat sich der Dringlichkeitsgrad verändert?\n"
        "4. **Empfehlung:** Ist eine dermatologische Vorstellung jetzt angezeigt?\n"
        "Antworte klinisch präzise, nur auf Basis der vorliegenden Analysedaten.",

        f"Compare these {len(analysed)} VLM skin analyses of one lesion ({lesion['body_location']}) "
        f"chronologically:\n{entries_text}\n\n"
        "Please assess:\n"
        "1. **Stability:** Is the lesion stable, improving, or progressing?\n"
        "2. **Changes:** What specifically changed (ABCDE criteria, color, border)?\n"
        "3. **Triage trajectory:** Has the urgency level changed?\n"
        "4. **Recommendation:** Is a dermatologist visit now indicated?\n"
        "Respond clinically and precisely, based only on the provided analysis data."
    )

    system = t(
        "Du bist ein erfahrener Dermatologe. Vergleiche Verlaufsaufnahmen einer Hautläsion "
        "objektiv und klinisch präzise. Keine Vordiagnosen — nur Datenbasis.",
        "You are an experienced dermatologist. Compare follow-up photos of a skin lesion "
        "objectively and clinically. No prior diagnoses — data only."
    )

    try:
        return call_llm(prompt, system=system)
    except Exception as e:
        return t(f"LLM-Fehler: {e}", f"LLM error: {e}")


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Hautläsionen Verlaufsanalyse", "Skin lesion timeline analysis")
    )
    ap.add_argument("--analyse", action="store_true",
                    help=t("VLM (ABCDE + Triage) für alle noch nicht analysierten Fotos",
                           "VLM (ABCDE + triage) for all photos without analysis"))
    ap.add_argument("--lesion", type=int, default=None, metavar="ID",
                    help=t("Verlauf einer Läsion (ID aus --list-lesions)",
                           "Timeline for one lesion (ID from --list-lesions)"))
    ap.add_argument("--compare", action="store_true",
                    help=t("LLM-Delta: Veränderungen zwischen Aufnahmen analysieren",
                           "LLM delta: analyze changes between photos"))
    ap.add_argument("--watch-list", action="store_true",
                    help=t("Nur Läsionen mit Handlungsbedarf (🔴/🟡, kein Histologie-Befund)",
                           "Only lesions needing action (🔴/🟡, no histology yet)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", None) or "de"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn    = open_medicine_imaging_db()
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")

    if args.analyse:
        _analyse_pending(conn, lang)

    if args.lesion:
        lesions  = _load_lesions(conn)
        lesion   = next((l for l in lesions if l["id"] == args.lesion), None)
        if not lesion:
            print(t(f"Läsion {args.lesion} nicht gefunden.", f"Lesion {args.lesion} not found."),
                  file=sys.stderr)
            conn.close(); sys.exit(1)

        timeline = _load_timeline(conn, args.lesion)
        report   = _render_lesion(lesion, timeline)
        print(report)

        full = report
        if args.compare:
            print(t(f"\nLLM-Verlaufsvergleich ({len([e for e in timeline if e['vlm_response']])} Analysen) …",
                    f"\nLLM timeline comparison ({len([e for e in timeline if e['vlm_response']])} analyses) …"))
            delta = _llm_delta(lesion, timeline, lang)
            full += f"\n\n## {t('Verlaufsbeurteilung (LLM)', 'Timeline Assessment (LLM)')}\n\n{delta}\n"
            print(delta)

        out = OUT_DIR / f"skin_verlauf_{args.lesion:04d}_{now_str}.md"

    else:
        lesions = _load_lesions(conn)
        if not lesions:
            print(t("Keine Läsionen in der DB. Erst mit import_skin.py importieren.",
                    "No lesions in DB. Import first with import_skin.py."))
            conn.close(); return

        report = _render_overview(lesions, conn, watch_only=args.watch_list)
        print(report)
        full   = report
        suffix = "_watchlist" if args.watch_list else "_uebersicht"
        out    = OUT_DIR / f"skin{suffix}_{now_str}.md"

    conn.close()
    out.write_text(full, encoding="utf-8")
    print(t(f"\n→ Bericht: {out}", f"\n→ Report: {out}"))


if __name__ == "__main__":
    main()
