#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
generate_patient_summary.py - Patienten-Übersicht als OpenOffice-Writer-Dokument

Erstellt ein ODT-Fließtext-Dokument (nicht Tabellenblatt) nach dem Vorbild der
Standardvorlage für Arztbesuche: Stichpunkt-Abschnitte statt Tabellen, zum
Mitnehmen/Vorzeigen statt zum Durchblättern.

@tier        infrastructure
@purpose.de  Fasst die manuell gepflegten Kyoro-Konfig-JSON-Dateien (Familien-
             anamnese, Vorerkrankungen, Medikamente, Impfungen, Operationen)
             sowie aktuelle Medikationsstatus aus medicine.db in einem
             druckfertigen ODT-Fließtext-Dokument zusammen.
@purpose.en  Summarizes the manually maintained Kyoro config JSON files (family
             history, prior conditions, medications, vaccinations, surgeries)
             plus current medication status from medicine.db in a print-ready
             ODT flow-text document.
@method.de   Liest dieselben JSON-Quellen wie export_arzt_komplett.py, baut
             daraus Abschnitte mit Überschrift + Stichpunktliste über odfpy
             (OpenDocumentText) statt Tabellenblättern. Keine Diagnose- oder
             Personennamen im Quellcode — alle Inhalte kommen zur Laufzeit aus
             KYORO_CONFIG_DIR.
@method.en   Reads the same JSON sources as export_arzt_komplett.py, builds
             heading + bullet-list sections via odfpy (OpenDocumentText)
             instead of spreadsheet tabs. No personal content in source
             code - all content comes from KYORO_CONFIG_DIR at runtime.
@limits.de   Abschnitte ohne strukturierte Kyoro-Quelle (Notfallkontakt, GdB,
             Patientenverfügung, Implantate) werden als auszufüllende
             Platzhalter ausgegeben, nicht automatisch befüllt. --language stellt
             den Text des Dokuments um; Einträge aus Config und medicine.db bleiben
             in der Sprache, in der sie erfasst wurden.
@limits.en   Sections without a structured Kyoro source (emergency contact,
             disability status, advance directive, implants) are emitted as
             fill-in placeholders, not auto-populated. --language switches the
             document's own text; entries from config and medicine.db stay in the
             language they were entered in.

@relevance.de  Reduziert wiederholtes Von-Hand-Ausfüllen von Anamnesebögen bei jedem Arztbesuch
@relevance.en  Reduces repeated by-hand intake-form filling at every appointment
@reads       ~/.config/kyoro/family_history.json, clinical_events.json,
             medication_history.json, medicine.db::medications
@writes      <output>.odt - Patientenübersicht als Fließtext

@usage
    python3 scripts/exporters/generate_patient_summary.py
    python3 scripts/exporters/generate_patient_summary.py --output intern/patientenuebersicht.odt
    python3 scripts/exporters/generate_patient_summary.py --language en
"""

import sys
import argparse
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from health_config import Config, get_own_person_id
from modules.db import open_medicine_db
from exporters.export_arzt_komplett import load_json_config
from modules.i18n import t, apply_lang_from_args

PERSISTENT_INFECTION_KEYWORDS = [
    "borreliose", "lyme", "epstein", "ebv", "cmv", "zytomegalie",
    "hepatitis", "hiv", "herpes", "vzv", "varizell", "cytomegal", "varicell",
]
ALLERGY_KEYWORDS = ["allergi", "allergy", "unverträg", "überempfindlich", "intoleran", "hypersensitiv"]


def _today_str():
    return date.today().isoformat()


def section_aktuelle_medikation(conn, cfg):
    """Aktive Medikation: medication_history.json (date_to leer/zukünftig),
    abgeglichen mit zuletzt in medicine.db vermerkten Pausierungen."""
    meds = load_json_config("medication_history.json")
    today = _today_str()
    active = []
    for m in meds:
        date_to = (m.get("date_to") or "").strip()
        if date_to and date_to <= today:
            continue
        active.append(m)

    cur = conn.cursor()
    cur.execute(
        "SELECT drug_name, is_chronic FROM medications "
        "WHERE person = ? AND source = 'manual_note' AND (drug_name, date) IN ("
        "  SELECT drug_name, MAX(date) FROM medications "
        "  WHERE person = ? AND source = 'manual_note' GROUP BY drug_name"
        ")",
        (get_own_person_id(), get_own_person_id()),
    )
    paused = {row[0] for row in cur.fetchall() if row[1] == 0}

    lines = []
    for m in active:
        name = m.get("name", "")
        if name in paused:
            continue
        dosis = m.get("dosis", "")
        freq = m.get("frequenz", "")
        indikation = m.get("indikation", "")
        bit = f"{name}"
        if dosis:
            bit += f" {dosis}"
        if freq:
            bit += f" ({freq})"
        if indikation:
            bit += f" — {indikation}"
        lines.append(bit)
    for name in sorted(paused):
        lines.append(t(f"{name} — aktuell pausiert/abgesetzt", f"{name} — currently paused/stopped"))
    return lines


def section_ops(cfg):
    events = load_json_config("clinical_events.json")
    lines = []
    for e in sorted((ev for ev in events if ev.get("type") == "surgery"), key=lambda x: x.get("date", "")):
        lines.append(f"{e.get('date', '')}: {e.get('name', '')}")
    return lines


def section_vaccinations(cfg):
    events = load_json_config("clinical_events.json")
    vac = [e for e in events if e.get("type") == "vaccination"]
    by_name = {}
    for e in sorted(vac, key=lambda x: x.get("date", "")):
        key = (
            e.get("name", "")
            .split("(")[0]
            .split("Booster")[0]
            .split("Auffrischung")[0]
            .split("Grundimmunisierung")[0]
            .strip()
        )
        by_name[key] = e
    suffix = t("letzte Dosis", "last dose")
    lines = [f"{e.get('date', '')}: {e.get('name', '')} ({suffix})" for e in by_name.values()]
    return sorted(lines)


def section_vorerkrankungen(cfg):
    events = load_json_config("clinical_events.json")
    diag = [e for e in events if e.get("type") == "diagnosis"]
    return [f"{e.get('date', '')}: {e.get('name', '')}" for e in sorted(diag, key=lambda x: x.get("date", ""))]


def section_infektionen(cfg):
    events = load_json_config("clinical_events.json")
    lines = []
    for e in events:
        t = e.get("type", "")
        name_lower = e.get("name", "").lower()
        if t in ("infection", "reinfection") or any(kw in name_lower for kw in PERSISTENT_INFECTION_KEYWORDS):
            lines.append(f"{e.get('date', '')}: {e.get('name', '')}")
    return sorted(lines)


def section_allergien(cfg):
    events = load_json_config("clinical_events.json")
    lines = []
    for e in events:
        name_lower = (e.get("name", "") + " " + e.get("notes", "")).lower()
        if any(kw in name_lower for kw in ALLERGY_KEYWORDS):
            lines.append(f"{e.get('date', '')}: {e.get('name', '')}")
    return sorted(lines)


def section_familienanamnese(cfg):
    """Gruppiert family_history.json nach Seite, kondensiert je Erkrankung
    über Verwandte (ein Eintrag pro condition, Verwandte zusammengefasst)."""
    data = load_json_config("family_history.json")
    by_side = {}
    for entry in data:
        side = entry.get("side", t("unbekannt", "unknown"))
        condition = entry.get("condition", "")
        relative = entry.get("relative", "")
        by_side.setdefault(side, {}).setdefault(condition, set()).add(relative)

    sections = {}
    for side, conditions in by_side.items():
        lines = []
        for condition, relatives in sorted(conditions.items()):
            rel_str = ", ".join(sorted(relatives))
            lines.append(f"{condition} ({rel_str})")
        sections[side] = sorted(lines)
    return sections


def placeholder_sections():
    blank = "____________________"
    note = t("nicht in Kyoro erfasst — manuell ergänzen", "not recorded in Kyoro — fill in by hand")
    return {
        t("Notfallkontakt", "Emergency contact"): f"{blank} ({note})",
        t("Implantate / Fremdkörper", "Implants / foreign bodies"):
            f"{t('keine bekannt', 'none known')} / {blank} ({note})",
        t("Schwerbehinderung (GdB)", "Disability status"): f"{blank} ({note})",
        t("Patientenverfügung / Betreuungsverfügung", "Advance directive / power of attorney"):
            f"{t('vorhanden: ja / nein', 'in place: yes / no')} {blank} ({note})",
    }


def build_odt(cfg, conn, output_path):
    from odf.opendocument import OpenDocumentText
    from odf.style import Style, TextProperties, ParagraphProperties
    from odf.text import H, P

    doc = OpenDocumentText()

    h1_style = Style(name="Heading1Big", family="paragraph")
    h1_style.addElement(TextProperties(fontsize="16pt", fontweight="bold"))
    doc.styles.addElement(h1_style)

    h2_style = Style(name="Heading2Section", family="paragraph")
    h2_style.addElement(TextProperties(fontsize="12pt", fontweight="bold"))
    h2_style.addElement(ParagraphProperties(marginleft="0cm", margintop="0.3cm"))
    doc.styles.addElement(h2_style)

    bullet_style = Style(name="BulletPara", family="paragraph")
    bullet_style.addElement(ParagraphProperties(marginleft="0.5cm"))
    doc.styles.addElement(bullet_style)

    doc.text.addElement(H(outlinelevel=1, stylename=h1_style, text=t("Patientenübersicht", "Patient summary")))
    name = cfg.name or "____________________"
    birthdate = cfg.birthdate or "____________________"
    doc.text.addElement(P(text=t(f"Name: {name}    Geb.: {birthdate}    Stand: {_today_str()}",
                                f"Name: {name}    Born: {birthdate}    As of: {_today_str()}")))

    empty_note = t("(keine Einträge in Kyoro erfasst)", "(no entries recorded in Kyoro)")

    def add_section(title, lines):
        doc.text.addElement(H(outlinelevel=2, stylename=h2_style, text=title))
        if not lines:
            doc.text.addElement(P(stylename=bullet_style, text=empty_note))
            return
        for line in lines:
            doc.text.addElement(P(stylename=bullet_style, text=f"• {line}"))

    add_section(t("Aktuelle Medikation", "Current medication"), section_aktuelle_medikation(conn, cfg))
    add_section(t("Operationen", "Surgeries"), section_ops(cfg))
    add_section(t("Relevante Vorerkrankungen / Diagnosen", "Relevant prior conditions"), section_vorerkrankungen(cfg))
    add_section(t("Bekannte Infektionen", "Known infections"), section_infektionen(cfg))
    add_section(t("Bekannte Allergien / Unverträglichkeiten", "Known allergies / intolerances"), section_allergien(cfg))
    add_section(t("Impfstatus (letzte Dosis je Impfung)", "Vaccination status (last dose per vaccine)"), section_vaccinations(cfg))

    doc.text.addElement(H(outlinelevel=2, stylename=h2_style, text=t("Familienanamnese", "Family history")))
    fam = section_familienanamnese(cfg)
    if not fam:
        doc.text.addElement(P(stylename=bullet_style, text=empty_note))
    for side, lines in fam.items():
        doc.text.addElement(P(stylename=bullet_style, text=f"{side.capitalize()}:"))
        for line in lines:
            doc.text.addElement(P(stylename=bullet_style, text=f"  • {line}"))

    for title, placeholder in placeholder_sections().items():
        add_section(title, [placeholder])

    doc.save(str(output_path))


def main():
    parser = argparse.ArgumentParser(description=t("Erstellt Patientenübersicht als ODT (OpenOffice Writer)",
                                                   "Creates a patient summary as ODT (OpenOffice Writer)"))
    parser.add_argument("--output", "-o", default=None,
                        help=t("Ausgabedatei (Standard: intern/patientenuebersicht_<Datum>.odt)",
                               "Output file (default: intern/patient_summary_<date>.odt)"))
    parser.add_argument("--language", "--lang", dest="lang", choices=["de", "en"], default=None,
                        help=t("Sprache des Dokuments (Standard: KYORO_LANG, sonst de)",
                               "Document language (default: KYORO_LANG, otherwise de)"))
    args = parser.parse_args()
    apply_lang_from_args(args)

    cfg = Config()
    conn = open_medicine_db()

    if args.output:
        output_path = Path(args.output)
    else:
        stem = t("patientenuebersicht", "patient_summary")
        output_path = PROJECT_ROOT / "intern" / f"{stem}_{_today_str()}.odt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    build_odt(cfg, conn, output_path)
    conn.close()
    print(t(f"Datei gespeichert: {output_path}", f"File saved: {output_path}"))


if __name__ == "__main__":
    main()
