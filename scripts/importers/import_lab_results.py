#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Laborbefunde PDF → Review-CSV oder health.db

@tier        infrastructure
@purpose.de  Importiert Laborbefunde aus PDF-Dateien
@purpose.en  Imports lab results from PDF files
@method.de   Workflow:
             1. python import_lab_results.py datei.pdf
                to Kyoro-HealthHub/Laborbefunde/YYYY-MM-DD_lab_ocr.csv
             2. CSV in LibreOffice/Excel oeffnen, OCR-Errors korrigieren,
                als YYYY-MM-DD_labor.csv speichern
             3. python medical_query.py labor
                to liest alle CSVs direkt, keine DB noetig
             4. python import_lab_results.py --db datei.pdf
                to Speichert die Daten direkt in der DB
@method.en   Workflow:
             1. python import_lab_results.py file.pdf
                to Kyoro-HealthHub/Laborbefunde/YYYY-MM-DD_lab_ocr.csv
             2. Open CSV in LibreOffice/Excel, correct OCR errors,
                save as YYYY-MM-DD_labor.csv
             3. python medical_query.py labor
                to reads all CSVs directly, no DB needed
             4. python import_lab_results.py --db file.pdf
                to saves data directly in the database
@reads       PDF-Dateien (Laborbefunde)
@writes      CSV-Dateien oder lab_results in health.db
@limits.de   OCR kann ungenau sein. Manuelle Korrektur erforderlich.

@relevance.de  Ermöglicht den Import von Laborergebnissen, essentiell für die Integration klinischer Daten
@relevance.en  Enables import of laboratory results, essential for integration of clinical data
@limits.en   OCR may be inaccurate. Manual correction required.
@usage
    python import_lab_results.py datei.pdf
    python import_lab_results.py *.pdf
    python import_lab_results.py --datum YYYY-MM-DD alter_befund.pdf
    python import_lab_results.py --db datei.pdf
"""

import argparse
import re
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from modules.base import log_import, resolve_person
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import Config as _Cfg
from modules.db import open_db
from utils.scrub_pdf_metadata import scrub as _scrub_pdf_metadata

PDF_DIR       = Path(__file__).parents[2] / "medicine" / "laborbefunde"
ORIGINALE_DIR = PDF_DIR / "originals"


def _archive_original(pdf_path: Path, ziel: Path, person: str | None = None) -> None:
    """Entfernt PII-Metadaten (Info/XMP/eingebettete EXIF) und archiviert nach originals/.

    GPS-Funde aus eingebetteten Fotos werden vor dem Strippen (gerundet)
    in health.db::photo_locations gespeichert, nicht verworfen.
    """
    from modules.imaging_utils import record_photo_location

    person = resolve_person(person)
    _, locations = _scrub_pdf_metadata(pdf_path, ziel)
    pdf_path.unlink()

    dated_locations = [loc for loc in locations if loc["date"]]
    if dated_locations:
        health_conn = open_db()
        try:
            for loc in dated_locations:
                record_photo_location(
                    health_conn, loc["date"], loc["gps"],
                    "import_lab_results", person,
                )
            health_conn.commit()
        finally:
            health_conn.close()

_cfg = _Cfg()
DB_PATH = _cfg.db_path

# ── Kategorien-Erkennung ──────────────────────────────────────────────────────
KNOWN_CATEGORIES = {
    "Hämatologie", "Klinische Chemie", "Gerinnung", "Hormone",
    "Schilddrüse", "Hormone / Schilddrüse", "Infektionsdiagnostik",
    "Vitamine", "Rheumatologie", "Genetik", "Urinstatus", "Liquor",
    "Autoimmundiagnostik", "Tumormarker", "Mikrobiologie",
}

KATEGORIEN_MAP = {
    "TSH": "Schilddrüse", "fT3": "Schilddrüse", "fT4": "Schilddrüse",
    "Trijodthyronin": "Schilddrüse", "Tretrajodthyronin": "Schilddrüse",
    "Tyroidea": "Schilddrüse", "Anti-TSH": "Schilddrüse",
    "A-TPO": "Schilddrüse", "1.84-PTH": "Schilddrüse",
    "TPO-AK": "Schilddrüse", "Tg-AK": "Schilddrüse",
    "Leukozyten": "Blutbild", "Erythrozyten": "Blutbild",
    "Hämoglobin": "Blutbild", "Hämatokrit": "Blutbild",
    "MCV": "Blutbild", "MCH": "Blutbild", "MCHC": "Blutbild",
    "Thrombozyten": "Blutbild", "MPV": "Blutbild",
    "Neutrophile": "Blutbild", "Lymphozyten": "Blutbild",
    "Monozyten": "Blutbild", "Eosinophile": "Blutbild",
    "Basophile": "Blutbild", "IG ": "Blutbild",
    "CRP": "Entzündung", "Interleukin": "Entzündung",
    "Haptoglobin": "Entzündung", "Fibrinogen": "Gerinnung",
    "Ferritin": "Eisen/Entzündung", "Transferrin": "Eisen",
    "Transferrinsättigung": "Eisen", "Eisen": "Eisen",
    "Vitamin B12": "Vitamine", "Folsäure": "Vitamine",
    "Vitamin D": "Vitamine", "25-OH-Vitamin": "Vitamine",
    "HbA1c": "Metabolismus", "Cholesterin": "Metabolismus",
    "Lipoprotein": "Metabolismus", "Triglyceride": "Metabolismus",
    "LDL": "Metabolismus", "HDL": "Metabolismus",
    "Homocystein": "Metabolismus", "Harnsäure": "Metabolismus",
    "Kreatinin": "Niere/Leber", "GFR": "Niere/Leber",
    "GOT": "Niere/Leber", "GPT": "Niere/Leber", "Gamma-GT": "Niere/Leber",
    "Bilirubin": "Niere/Leber", "Albumin": "Niere/Leber",
    "Globulin": "Niere/Leber", "Phosphatase": "Niere/Leber",
    "Borrelia": "Immunologie", "Hepatitis": "Immunologie",
    "CMV": "Immunologie", "EBV": "Immunologie",
    "ANA": "Immunologie", "Anti-DNA": "Immunologie",
    "Rheumafaktor": "Rheumatologie", "HLA-B27": "Genetik",
}


def _float(s):
    if s is None:
        return None
    try:
        return float(str(s).strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


def parse_result(raw: str) -> tuple:
    """Gibt (wert, qualitativ, status) zurück."""
    s = raw.strip()
    status = None
    if s.endswith(" +") or s.endswith("+"):
        status = "hoch"
        s = s.rstrip("+").strip()
    elif s.endswith(" -") or (s.endswith("-") and not s.startswith("<")):
        status = "niedrig"
        s = s.rstrip("-").strip()
    lower = s.lower()
    if lower in ("negativ", "negative", "neg"):
        return None, "negativ", status
    if lower in ("positiv", "positive", "pos"):
        return None, "positiv", status
    if lower in ("folgt", "ausstehend", "pending"):
        return None, "folgt", status
    if re.match(r'^[a-zA-Z]{2,}', s) and not re.match(r'^\d', s):
        return None, s, status
    if s.startswith(("<", ">")):
        s = s[1:].strip()
    wert = _float(s)
    if wert is None and s:
        return None, s, status
    return wert, None, status


def parse_ref(raw: str) -> tuple:
    """Gibt (ref_min, ref_max, ref_text) zurück."""
    s = raw.strip()
    if not s:
        return None, None, None
    m = re.match(r'^([<>]?[\d,.]+)\s*[-–]\s*([\d,.]+)$', s)
    if m:
        return _float(m.group(1)), _float(m.group(2)), s
    m = re.match(r'^<\s*([\d,.]+)$', s)
    if m:
        return None, _float(m.group(1)), s
    m = re.match(r'^>\s*([\d,.]+)$', s)
    if m:
        return _float(m.group(1)), None, s
    if re.match(r'^[a-zA-Z]', s):
        return None, None, s
    return None, None, s


def plausibility_fix(wert, ref_min, ref_max, ocr_status):
    """Korrigiert OCR-Dezimalfehler only if OCR explizit +/- gesetzt hat."""
    if wert is None or (ref_min is None and ref_max is None):
        return wert
    if ocr_status not in ("hoch", "niedrig"):
        return wert
    lo = min(r for r in [ref_min, ref_max] if r is not None)
    hi = max(r for r in [ref_min, ref_max] if r is not None)
    if lo == 0 and hi == 0:
        return wert
    ref_mid = (lo + hi) / 2 if lo != hi else hi
    if ref_mid == 0:
        return wert
    ratio = wert / ref_mid
    if 7 < ratio < 15:
        fixed = round(wert / 10, 4)
        if lo * 0.5 <= fixed <= hi * 2:
            return fixed
    if 0.07 < ratio < 0.15:
        fixed = round(wert * 10, 4)
        if lo * 0.5 <= fixed <= hi * 2:
            return fixed
    return wert


def compute_status(wert, ref_min, ref_max, existing_status):
    if existing_status:
        return existing_status
    if wert is None or (ref_min is None and ref_max is None):
        return None
    if ref_min is not None and wert < ref_min:
        return "niedrig"
    if ref_max is not None and wert > ref_max:
        return "hoch"
    return "normal"


def guess_kategorie(param: str) -> str:
    for prefix, kat in KATEGORIEN_MAP.items():
        if param.startswith(prefix) or prefix.lower() in param.lower():
            return kat
    return "Sonstiges"


# ── Qualitätsscore ───────────────────────────────────────────────────────────
_NOISE_PAT = re.compile(
    r'[=|]{2,}|^\d+$|^[A-Z]\)$|\s{3,}'
    r'|(und|oder|bzw|nach|bei|von|für|der|die|das)\s',
    re.IGNORECASE,
)

def _quality_score(rows: list[dict]) -> float:
    """0.0 = sehr schlecht, 1.0 = sehr gut. Anteil valider OCR-Zeilen."""
    if not rows:
        return 0.0
    n_clean = sum(
        1 for r in rows
        if (r.get("wert") is not None or r.get("qualitativ"))
        and not _NOISE_PAT.search(r["parameter"])
        and len(r["parameter"]) < 40
        and r["kategorie"] != "Sonstiges"
    )
    return n_clean / len(rows)


# ── VLM-Fallback ─────────────────────────────────────────────────────────────
def _vlm_pdf_page(page, datum: str, labor: str, pdf_name: str) -> list[dict]:
    """Seite als Bild per VLM (Claude) extrahieren — Fallback wenn OCR-Qualität zu niedrig."""
    import base64
    import io
    import json as _json

    try:
        from modules.llm import call_llm
    except ImportError:
        return []

    pil = page.to_image(resolution=120).original
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()

    datum_hint = f'Falls kein Datum erkennbar, verwende "{datum}".' if datum else ""
    prompt = (
        "Extrahiere alle Laborbefund-Werte aus diesem Bild als JSON-Array.\n"
        "Jedes Objekt hat folgende Felder (fehlende als null):\n"
        '  "datum": Befunddatum im Format YYYY-MM-DD (aus dem Dokument lesen, z.B. Druckdatum, Entnahmedatum oder Berichtsdatum)\n'
        '  "parameter": Parameterbezeichnung exakt wie im Dokument\n'
        '  "wert": Messwert als String -- kann eine Dezimalzahl, ein Textbefund '
        '("negativ"/"positiv") oder eine Schwellenangabe ("<X.X") sein\n'
        '  "einheit": Einheit exakt wie im Dokument (z.B. "mg/l", "G/l", "%") oder null\n'
        '  "ref_min": untere Referenzgrenze als Zahl oder null\n'
        '  "ref_max": obere Referenzgrenze als Zahl oder null\n'
        '  "status": "hoch", "niedrig", "normal" oder null\n'
        f"{datum_hint}\n"
        "Ignoriere Kopfzeilen, Fußnoten, Kommentartexte, Seitenzahlen.\n"
        "Gib NUR das JSON-Array zurück, keinen weiteren Text."
    )

    try:
        response = call_llm(prompt, image_b64=b64, image_mime="image/jpeg", max_tokens=3000,
                             label_output=False)
        m = re.search(r'\[.*\]', response, re.DOTALL)
        if not m:
            return []
        data = _json.loads(m.group(0))
    except Exception as e:
        print(f"  VLM-Fehler: {e}")
        return []

    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        param = (item.get("parameter") or "").strip()
        if not param:
            continue
        vlm_datum = (item.get("datum") or "").strip()
        row_datum = vlm_datum if re.match(r'\d{4}-\d{2}-\d{2}', vlm_datum) else datum
        wert, qualitativ, _ = parse_result(str(item.get("wert") or ""))
        ref_min = _float(item.get("ref_min"))
        ref_max = _float(item.get("ref_max"))
        status  = item.get("status") or compute_status(wert, ref_min, ref_max, None)
        rows.append({
            "datum":      row_datum,
            "parameter":  param,
            "kategorie":  guess_kategorie(param),
            "wert":       wert,
            "qualitativ": qualitativ,
            "einheit":    (item.get("einheit") or "").strip() or None,
            "ref_min":    ref_min,
            "ref_max":    ref_max,
            "ref_text":   None,
            "status":     status,
            "hinweis":    None,
            "labor":      labor,
            "quelle":     "vlm",
            "pdf_datei":  pdf_name,
        })
    return rows


# ── PDF-Import ────────────────────────────────────────────────────────────────
def _import_pdf_page(page, datum: str, labor: str, pdf_name: str) -> list[dict]:
    """OCR einer PDF-Seite → Liste from Laborbefand-Dicts."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        print(t("pytesseract/Pillow fehlen: pip3 install pytesseract pillow",
                "pytesseract/Pillow missing: pip3 install pytesseract pillow"))
        return []

    # Originalbild aus PDF-Stream
    if page.images:
        try:
            img_obj = page.images[0]
            raw = img_obj["stream"].get_rawdata()
            data = zlib.decompress(raw)
            w, h = img_obj["srcsize"]
            pil = Image.frombytes("RGB", (w, h), data)
        except Exception:
            pil = page.to_image(resolution=300).original
    else:
        pil = page.to_image(resolution=300).original

    w_img = pil.width

    # OCR with Wort-Boanding-Boxes
    ocr = pytesseract.image_to_data(
        pil, lang="deu", config="--psm 6 --oem 1",
        output_type=pytesseract.Output.DICT
    )

    # columnsbreiten (relativ zur Bildbreite)
    # Kalibriert auf typisches A4-Labor-Layout (1787px Originalbreite)
    scale = w_img / 1787
    COL_PARAM_MAX  = int(540  * scale)
    COL_RESULT_MAX = int(795  * scale)
    COL_UNIT_MAX   = int(1040 * scale)
    COL_REF_MAX    = int(1450 * scale)
    COL_HINT_MAX   = int(1600 * scale)

    # Wörter nach Zeile gruppieren (y-Toleranz 15px)
    rows: dict[int, list] = {}
    for i, text in enumerate(ocr["text"]):
        if not text.strip() or ocr["conf"][i] < 20:
            continue
        y = ocr["top"][i]
        x = ocr["left"][i]
        # rows-Bucket
        bucket = round(y / 15) * 15
        rows.setdefault(bucket, []).append({
            "text": text, "x": x, "y": y,
            "conf": ocr["conf"][i]
        })

    # Kategorie and Resultse aufbauen
    current_kat = "Unbekannt"
    results = []
    skip_patterns = re.compile(
        r"^(Seite\s+\d|Vor-?\s*und|geb\.|Patienten|Untersuchung|Resultat|"
        r"Einheit|Referenz|Entscheidung|Hinweis|Methode|Auftrag|Abnahme|"
        r"Eingangs|Teilbefund|\*\)|Grenzbereich|Diabetes|Therapie|"
        r"Vitamin\s+B\s*12\s+Mangel|Herzinsuffi|Akut-Phase|"
        r"Befund\s+wurde|Dieser\s+Befund|Kurzarzt|Bei\s+dem|"
        r"Ein\s+HLA|Eine\s+erh|HLA-B27-Sub|HLA-B27-All|"
        r"suboptimal|ausreichend|mögliche\s+Über|toxisch|"
        r"\d+\s*(Citrat|EDTA|PFA|Serum)|"
        r"Impedanz|Koagulo|Nephelom|Turbid|Aggluti|vitro|"
        r"extern|Laborauf|validiert|elektron|Unterschrift|"
        r"Kein\s+Hinweis|Herzinsuf|unwahrscheinlich)",
        re.IGNORECASE | re.VERBOSE
    )
    stop_at_kurzarzt = False

    for bucket in sorted(rows.keys()):
        if stop_at_kurzarzt:
            break
        words = sorted(rows[bucket], key=lambda w: w["x"])

        # columns zuweisen
        param_words, result_words, unit_words, ref_words, hint_words = [], [], [], [], []
        for w in words:
            x = w["x"]
            if x < COL_PARAM_MAX:
                param_words.append(w["text"])
            elif x < COL_RESULT_MAX:
                result_words.append(w["text"])
            elif x < COL_UNIT_MAX:
                unit_words.append(w["text"])
            elif x < COL_REF_MAX:
                ref_words.append(w["text"])
            elif x < COL_HINT_MAX:
                hint_words.append(w["text"])

        param_raw  = " ".join(param_words).strip()
        result_raw = " ".join(result_words).strip()
        unit_raw   = " ".join(unit_words).strip()
        ref_raw    = " ".join(ref_words).strip()
        hint_raw   = " ".join(hint_words).strip()

        if not param_raw:
            continue

        # Fußnoten-Zahlen and OCR-Artefakte aus Parameternamen entfernen
        param_clean = param_raw.strip()
        # (*) Präfix: original and OCR-Varianten (!*, '*, (*), (*), ...)
        param_clean = re.sub(r"^\(?\*?\)?\s*", "", param_clean).strip()
        param_clean = re.sub(r"^[!'\"`´\(\)]\*?\s*", "", param_clean).strip()
        # Fußnotenzahl am Ende (Parametername gefolgt von 1-2-stelliger Fußnoten-Referenz)
        param_clean = re.sub(r"\s+\d{1,2}$", "", param_clean).strip()
        # OCR-Artefakte im Parameternamen: !, ', `, ´, °, $, ®, @, © + folgende */#/Zahl
        param_clean = re.sub(r"\s+[!'\"`´]\s*[\*#]?\s*\d*\s*$", "", param_clean).strip()
        param_clean = re.sub(r"[°$®@©]", "", param_clean).strip()
        # Doppelte Leerzeichen
        param_clean = re.sub(r"\s{2,}", " ", param_clean).strip()

        # Kurzarztbericht → ab hier stoppen
        if "kurzarzt" in param_clean.lower():
            stop_at_kurzarzt = True
            break

        # Kategorie-Header erkennen (no Result-column, kurzer Text)
        if not result_raw and not unit_raw and param_clean:
            if len(param_clean) < 45 and not re.search(r'\d', param_clean):
                for cat in KNOWN_CATEGORIES:
                    if cat.lower() in param_clean.lower():
                        current_kat = cat
                        break
                # Unbekannte Sub-Labels (e.g. "Akut-Phase-Protein") setzen kat NICHT zurück
            continue

        # Überspringe Überschriften and Fußnoten
        if skip_patterns.search(param_clean):
            continue

        # Pipe-Zeichen im Parameter → Fußnoten-Erklärungszeile
        if "|" in param_clean or "|" in result_raw:
            continue

        # Sehr langer Parametertext without Einheit = Sub-Note
        if len(param_clean) > 55 and not unit_raw:
            continue

        # Muss mindestens ein Result haben
        if not result_raw:
            continue

        # Parameter zu kurz / only Zahlen → no echtes Result
        if len(param_clean) < 2 or re.match(r'^\d+$', param_clean):
            continue

        # Noch verbliebene OCR-Artefakte im Parameternamen
        if re.match(r"^[!'\"`´\*#<>]", param_clean):
            continue

        # Einheit bereinigen
        unit_clean = re.sub(r'[°]', '', unit_raw).strip()

        # Parsen
        wert, qualitativ, status = parse_result(result_raw)
        ref_min, ref_max, ref_text = parse_ref(ref_raw)

        # Plausibilität (OCR-Dezimalfehler) — only if OCR +/- gesetzt hat
        wert = plausibility_fix(wert, ref_min, ref_max, status)

        status = compute_status(wert, ref_min, ref_max, status)

        kategorie = guess_kategorie(param_clean)
        if current_kat not in ("Unbekannt",):
            # Verwende aktuellen Abschnitt als Hint for guess
            if kategorie == "Sonstiges":
                kategorie = current_kat

        results.append({
            "datum":      datum,
            "parameter":  param_clean,
            "kategorie":  kategorie,
            "wert":       wert,
            "qualitativ": qualitativ,
            "einheit":    unit_clean or None,
            "ref_min":    ref_min,
            "ref_max":    ref_max,
            "ref_text":   ref_text,
            "status":     status,
            "hinweis":    hint_raw or None,
            "labor":      labor,
            "quelle":     "pdf",
            "pdf_datei":  pdf_name,
        })

    return results


# ── CSV-Export (OCR → Review-CSV) ────────────────────────────────────────────
def rows_to_csv(rows: list[dict], out_path: Path) -> None:
    """Schreibt OCR-Resultse als reviewbares CSV."""
    import csv
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        f.write("# Laborbefund-Review-CSV — bitte vor dem Import prüfen und korrigieren\n")
        f.write("# Spalten: datum, parameter, kategorie, wert, einheit, ref_min, ref_max, labor, status, kommentar\n")
        f.write("# status: hoch | niedrig | normal | (leer lassen = automatisch berechnen)\n")
        f.write("# Qualitative Werte (negativ/positiv/folgt) in die wert-Spalte eintragen\n")
        f.write("#\n")
        writer = csv.writer(f)
        writer.writerow(["datum", "parameter", "kategorie", "wert", "einheit",
                         "ref_min", "ref_max", "labor", "status", "kommentar"])
        kat_prev = None
        for r in rows:
            if r["kategorie"] != kat_prev:
                f.write(f"#\n# ── {r['kategorie']} ──\n")
                kat_prev = r["kategorie"]
            wert_str = str(r["wert"]) if r["wert"] is not None else (r["qualitativ"] or "")
            writer.writerow([
                r["datum"],
                r["parameter"],
                r["kategorie"],
                wert_str,
                r["einheit"] or "",
                r["ref_min"] if r["ref_min"] is not None else "",
                r["ref_max"] if r["ref_max"] is not None else "",
                r["labor"] or "",
                r["status"] or "",
                "",  # Kommentar: leer, für Nutzer
            ])
    print(f"  → {out_path}")
    print(t(f"     {len(rows)} Parameter — bitte prüfen, dann: python medical_query.py labor",
            f"     {len(rows)} parameters — please review, then: python medical_query.py labor"))


def rows_to_db(rows: list[dict], conn, person: str) -> None:
    """Schreibt OCR-Resultse in die Datenbank und ordnet sie dem Benutzer zu."""
    
    # Erstelle die Tabelle, falls sie nicht existiert
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lab_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datum TEXT NOT NULL,
            parameter TEXT NOT NULL,
            kategorie TEXT,
            wert REAL,
            qualitativ TEXT,
            einheit TEXT,
            ref_min REAL,
            ref_max REAL,
            ref_text TEXT,
            status TEXT,
            hinweis TEXT,
            labor TEXT,
            quelle TEXT,
            pdf_datei TEXT,
            person TEXT NOT NULL,
            UNIQUE(datum, parameter, person)
        )
    """)
    
    # Füge die Daten in die Datenbank ein
    for r in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO lab_results (
                datum, parameter, kategorie, wert, qualitativ, einheit,
                ref_min, ref_max, ref_text, status, hinweis, labor, quelle, pdf_datei, person
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["datum"],
                r["parameter"],
                r["kategorie"],
                r["wert"],
                r["qualitativ"],
                r["einheit"],
                r["ref_min"],
                r["ref_max"],
                r.get("ref_text"),
                r["status"],
                r["hinweis"],
                r["labor"],
                r["quelle"],
                r["pdf_datei"],
                person
            )
        )
    
    conn.commit()
    print(f"  → {len(rows)} Parameter in die Datenbank geschrieben")



# ── Hauptprogramm ─────────────────────────────────────────────────────────────
def _ocr_pdf(pdf_path: Path, datum: str | None, labor: str | None) -> list[dict]:
    try:
        import pdfplumber
    except ImportError:
        print(t("pdfplumber fehlt: pip3 install pdfplumber",
                "pdfplumber missing: pip3 install pdfplumber"))
        return []

    labor = labor or pdf_path.stem
    if datum is None:
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', pdf_path.name)
        if m:
            datum = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        else:
            m = re.search(r'(\d{2})[._-](\d{2})[._-](\d{4})', pdf_path.name)
            if m:
                datum = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    vlm_threshold = getattr(_ocr_pdf, "_vlm_threshold", None)
    if datum is None:
        if vlm_threshold is not None and vlm_threshold >= 1.0:
            datum = "unknown"  # VLM liest Datum aus dem Bild
        else:
            datum = input(f"Datum für {pdf_path.name} (YYYY-MM-DD): ").strip()

    print(t(f"OCR: {pdf_path.name} (Datum: {datum})", f"OCR: {pdf_path.name} (date: {datum})"))
    all_rows = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            rows = _import_pdf_page(page, datum, labor, pdf_path.name)
            score = _quality_score(rows)
            if vlm_threshold is not None and score < vlm_threshold:
                print(t(
                    f"  Seite {i+1}: OCR-Qualität {score:.0%} < {vlm_threshold:.0%} — VLM-Fallback",
                    f"  Page {i+1}: OCR quality {score:.0%} < {vlm_threshold:.0%} — VLM fallback",
                ))
                vlm_rows = _vlm_pdf_page(page, datum, labor, pdf_path.name)
                if vlm_rows:
                    rows = vlm_rows
                    print(t(f"  Seite {i+1}: {len(rows)} Parameter (VLM)",
                            f"  Page {i+1}: {len(rows)} parameters (VLM)"))
                else:
                    print(t(f"  Seite {i+1}: VLM lieferte kein Ergebnis, behalte OCR ({len(rows)} Zeilen)",
                            f"  Page {i+1}: VLM returned nothing, keeping OCR ({len(rows)} rows)"))
            else:
                print(t(f"  Seite {i+1}: {len(rows)} Parameter (OCR {score:.0%})",
                        f"  Page {i+1}: {len(rows)} parameters (OCR {score:.0%})"))
            all_rows.extend(rows)

    seen, dedup = set(), []
    for r in all_rows:
        key = (r["datum"], r["parameter"])
        if key not in seen:
            seen.add(key)
            dedup.append(r)
    return dedup


def main():
    parser = argparse.ArgumentParser(
        description="Laborbefund PDF → Review-CSV oder health.db",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Workflow:
  python import_lab_results.py befund.pdf           # OCR → *_lab_ocr.csv
  (CSV prüfen, OCR-Fehler korrigieren, als *_labor.csv speichern)
  python medical_query.py labor               # analysiert alle CSVs direkt
  
  Alternativ:
  python import_lab_results.py --db befund.pdf  # Direkt in DB speichern"""
    )
    parser.add_argument("pdfs", nargs="+", metavar="PDF", help="PDF-Dateien")
    parser.add_argument("--datum", metavar="YYYY-MM-DD", help="Datum (falls nicht im Dateinamen)")
    parser.add_argument("--labor", metavar="NAME",       help="Labor-Name")
    parser.add_argument("--vlm-threshold", metavar="0-1", type=float, default=0.5,
                        help="OCR-Qualitätsschwelle für VLM-Fallback (0=aus, 1=immer; Standard: 0.5)")
    parser.add_argument("--db", action="store_true", help="Daten direkt in die Datenbank speichern")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    _ocr_pdf._vlm_threshold = args.vlm_threshold if args.vlm_threshold > 0 else None

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ORIGINALE_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = None
    total_rows = 0
    if args.db:
        conn = open_db()

    for pdf_str in args.pdfs:
        pdf_path = Path(pdf_str)
        if not pdf_path.exists():
            print(t(f"Nicht gefunden: {pdf_path}", f"Not found: {pdf_path}"))
            continue
        rows = _ocr_pdf(pdf_path, args.datum, args.labor)
        if rows:
            datum = rows[0]["datum"]
            if args.db:
                rows_to_db(rows, conn, person)
                total_rows += len(rows)
                ziel = ORIGINALE_DIR / pdf_path.name
                _archive_original(pdf_path, ziel, person)
                print(t(f"  → Original verschoben nach: Originale/{pdf_path.name}",
                        f"  → Original moved to: Originale/{pdf_path.name}"))
            else:
                out   = PDF_DIR / f"{datum}_lab_ocr.csv"
                rows_to_csv(rows, out)
                ziel = ORIGINALE_DIR / pdf_path.name
                _archive_original(pdf_path, ziel, person)
                print(t(f"  → Original verschoben nach: Originale/{pdf_path.name}",
                        f"  → Original moved to: Originale/{pdf_path.name}"))

    if conn:
        log_import(conn, "import_lab_results", ", ".join(args.pdfs), total_rows, person=person)
        conn.commit()
        conn.close()


if __name__ == "__main__":
    main()
