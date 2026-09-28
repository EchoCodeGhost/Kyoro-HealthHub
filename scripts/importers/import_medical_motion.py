#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Medical-Motion PDF-Berichte → health.db

@tier        infrastructure
@purpose.de  Liest monatliche Reports der Medical-Motion-App (CE-zertifiziertes System)
             und schreibt Daten zu Schmerzbereichen, Wohlbefindens-Scores und
             Kategorien in eigene Tabellen. Basis für Zeitreihen-Analysen.
@purpose.en  Reads monthly reports from the Medical Motion app (CE-certified system)
             and writes pain region data, wellbeing scores and categories into
             dedicated tables. Basis for time series analysis.
@method.de   pdfplumber extrahiert Text seitenweise. Seite 1: Report-
             Zeitraum per Regex; Scores per OCR (pdf2image + pytesseract,
             Crop Y=455–525 pt). Seite 2: ICD-10-Codes per Regex,
             Übungsstatistiken per Token-Matching. Seiten 3–4 (Schmerz-
             karten): VLM-Aufruf (OpenRouter, vision-fähiges Modell) mit Farbskala-
             Referenzbild aus intern/mm_farbskala/; Scores landen in mm_pain_regions.pain_score.
             Seiten 5–11: Regionsnamen per Wort-Koordinaten-Gruppierung (Y-Toleranz
             3 pt), Aufteilung links/rechts am Seitenmittelpunkt.
@method.en   pdfplumber extracts text page by page. Page 1: report period
             via regex; scores via OCR (pdf2image + pytesseract, crop
             Y=455–525 pt). Page 2: ICD-10 codes via regex, exercise
             stats via token matching. Pages 3–4 (pain cards): VLM call
             (OpenRouter, vision-capable model) with color scale reference
             from intern/mm_farbskala/; scores stored in pain_score.
             Skippable via --no-vlm. Pages 5–11: region names via word-
             coordinate grouping (Y-tolerance 3 pt), split left/right
             at page midpoint.
@reads       mm_report_meta (MAX(report_to) für --update-Modus)
@writes      mm_report_meta: report_from TEXT, report_to TEXT,
             wellbeing_score_start INTEGER, wellbeing_label_start TEXT,
             wellbeing_score_end INTEGER, wellbeing_label_end TEXT,
             pain_score_start INTEGER, pain_label_start TEXT,
             pain_score_end INTEGER, pain_label_end TEXT,
             pain_trend TEXT, exercise_days_done INTEGER,
             exercise_days_total INTEGER, exercises_done INTEGER,
             exercises_skipped INTEGER, longest_streak INTEGER,
             surgery_regions TEXT, source_file TEXT, person TEXT;
             mm_pain_regions: report_to TEXT, region TEXT,
             region_label TEXT, pain_score INTEGER, duration TEXT,
             pain_type TEXT, timing TEXT, person TEXT, source TEXT;
             mm_diagnoses: report_to TEXT, icd_code TEXT,
             description TEXT, person TEXT
@limits.de   Seiten 3–4 (Schmerzkarten) sind reine Vektorgrafiken —
             Schmerz-Scores pro Region sind nicht als Text verfügbar;
             OCR-Extraktion erfordert installiertes pdf2image + tesseract.
             Übungsstatistiken fehlen wenn Nutzer kein Feedback gegeben hat
             ("Keine Angabe"). VLM-Scoring erfordert openrouter_api_key und vision-fähiges 
             Modell (z. B. claude-sonnet-4-6 oder gpt-4o); ohne API-Key wird pain_score 
             auf NULL gesetzt. PDF-Layout-Änderungen können das Parsing brechen.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Pages 3–4 (pain cards) are pure vector graphics — per-region
             pain scores are not available as text; OCR extraction requires
             pdf2image + tesseract. Exercise stats are absent when the user
             gave no feedback ("Keine Angabe"). VLM scoring requires openrouter_api_key and 
             vision-capable model (e.g. claude-sonnet-4-6 or gpt-4o); without API key, 
             pain_score is set to NULL. PDF layout changes may break parsing.
@usage
    python3 import_medical_motion.py
    python3 import_medical_motion.py --update
    python3 import_medical_motion.py --file imports/_inbox/mm_report_05072026.pdf
    python3 import_medical_motion.py --inbox
    python3 import_medical_motion.py --no-vlm
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import

_cfg = _Cfg()

# Verzeichnisse
MM_DIR = _cfg.data_root / "medical_motion"
MM_DIR.mkdir(parents=True, exist_ok=True)
INBOX_DIR = _cfg.data_root / "_inbox"

# Datenbank-Schema
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mm_report_meta (
    report_from          TEXT NOT NULL,
    report_to            TEXT NOT NULL,
    wellbeing_score_start INTEGER,
    wellbeing_label_start TEXT,
    wellbeing_score_end   INTEGER,
    wellbeing_label_end   TEXT,
    pain_score_start      INTEGER,
    pain_label_start      TEXT,
    pain_score_end        INTEGER,
    pain_label_end        TEXT,
    pain_trend            TEXT,
    exercise_days_done    INTEGER,
    exercise_days_total   INTEGER,
    exercises_done        INTEGER,
    exercises_skipped     INTEGER,
    longest_streak        INTEGER,
    surgery_regions       TEXT,
    source_file           TEXT,
    person                TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (report_from, report_to, person)
);

CREATE TABLE IF NOT EXISTS mm_pain_regions (
    report_to    TEXT NOT NULL,
    region       TEXT NOT NULL,
    region_label TEXT,
    pain_score   INTEGER,
    duration     TEXT,
    pain_type    TEXT,
    timing       TEXT,
    person       TEXT NOT NULL DEFAULT 'unknown',
    source       TEXT DEFAULT 'medical_motion',
    PRIMARY KEY (report_to, region, person)
);

CREATE TABLE IF NOT EXISTS mm_diagnoses (
    report_to   TEXT NOT NULL,
    icd_code    TEXT NOT NULL,
    description TEXT,
    person      TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (report_to, icd_code, person)
);
"""

_MONTH_ABBREVS = {'Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'}
_SKIP_WORDS = {'patienten', 'report', 'übersicht', 'schmerzbereiche'}


def parse_date(date_str: str) -> str | None:
    """Parsed 'D.M.YYYY' → 'YYYY-MM-DD'. Beispiele: '4.6.2026' → '2026-06-04'"""
    try:
        match = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', date_str.strip())
        if not match:
            return None
        
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        
        if month < 1 or month > 12 or day < 1 or day > 31:
            return None
            
        return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception:
        return None


def extract_report_period(text: str) -> tuple[str, str] | None:
    """Extrahiert den Report-Zeitraum aus dem Header."""
    pattern = r'von\s+(\d{1,2}\.\d{1,2}\.\d{4})\s+bis\s+(\d{1,2}\.\d{1,2}\.\d{4})'
    match = re.search(pattern, text)
    if match:
        return parse_date(match.group(1)), parse_date(match.group(2))
    return None


def extract_pain_trend(text: str) -> str | None:
    """Extrahiert den Schmerztrend."""
    pattern = r'Schmerzentwicklung anhand der Feedbackfragen:\s*(\w+)'
    match = re.search(pattern, text)
    return match.group(1) if match else None


def extract_surgery_regions(text: str) -> str | None:
    """Extrahiert die von Operationen betroffenen Körperteile."""
    pattern = r'Von Operationen betro[^\n]+:\s*([^\n]+)'
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def extract_scores_and_labels(page_words: list[dict]) -> dict:
    """Extrahiert Wohlbefindens- und Schmerzscores von Seite 1."""
    # Nach Y-Position gruppieren
    words_sorted = sorted(page_words, key=lambda w: w['top'])
    rows = []
    current_row = [words_sorted[0]]
    
    for word in words_sorted[1:]:
        if abs(word['top'] - current_row[0]['top']) <= 5:
            current_row.append(word)
        else:
            if current_row:
                rows.append(current_row)
            current_row = [word]
    if current_row:
        rows.append(current_row)
    
    # Scores und Labels extrahieren
    result = {}
    
    # Labels finden (Y=456.2)
    label_row = None
    for row in rows:
        if 455 <= row[0]['top'] <= 457:
            label_row = row
            break
    
    if label_row:
        row_texts = [w['text'] for w in sorted(label_row, key=lambda w: w['x0'])]
        # Format: ['GENERELLES', 'WOHLBEFINDEN', 'SCHMERZEMPFINDEN', 'GENERELLES', 'WOHLBEFINDEN', 'SCHMERZEMPFINDEN']
        # Linke Hälfte = Start, rechte Hälfte = Ende
        if len(row_texts) >= 6:
            # Linkes Label (Start)
            result['wellbeing_label_start'] = ' '.join(row_texts[:2])
            result['pain_label_start'] = ' '.join(row_texts[2:4])
            # Rechtes Label (Ende)
            result['wellbeing_label_end'] = ' '.join(row_texts[4:6])
            if len(row_texts) > 6:
                result['pain_label_end'] = ' '.join(row_texts[6:8])
    
    return result


def extract_scores_ocr(pdf_path: Path) -> dict:
    """Extrahiert Wellbeing/Pain-Scores per OCR aus Seite 1 (Y=455–525 pt)."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        return {}
    try:
        pages = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=1)
        img = pages[0]
        w, h = img.size
        y1 = int(455 / 842 * h)
        y2 = int(525 / 842 * h)
        crop = img.crop((0, y1, w, y2))
        text = pytesseract.image_to_string(crop, lang='deu', config='--psm 6')
        # Matcht "X/10" und "X710" (OCR liest "/" oft als "7")
        scores = re.findall(r'(\d{1,2})[/7][01]0', text)
        keys = ['wellbeing_score_start', 'pain_score_start',
                'wellbeing_score_end', 'pain_score_end']
        return dict(zip(keys, (int(s) for s in scores[:4])))
    except Exception:
        return {}


def extract_exercise_stats(text: str) -> dict:
    """Extrahiert Übungsstatistiken von Seite 2."""
    result = {}
    
    # Tage von Übungen
    days_pattern = r'(\d+)\s*/\s*(\d+)\s*Tage von Übungen'
    match = re.search(days_pattern, text)
    if match:
        result['exercise_days_done'] = int(match.group(1))
        result['exercise_days_total'] = int(match.group(2))
    
    # Durchgeführte Übungen
    done_pattern = r'(\d+)\s*Durchgeführte Übung'
    match = re.search(done_pattern, text)
    if match:
        result['exercises_done'] = int(match.group(1))
    
    # Längste Folge
    streak_pattern = r'(\d+)\s*Tag Längste Folge'
    match = re.search(streak_pattern, text)
    if match:
        result['longest_streak'] = int(match.group(1))
    
    # Übersprungene Übungen
    skipped_pattern = r'(\d+)\s*Übersprungene Übung'
    match = re.search(skipped_pattern, text)
    if match:
        result['exercises_skipped'] = int(match.group(1))
    
    return result


def extract_icd_codes(text: str) -> list[tuple[str, str]]:
    """Extrahiert ICD-10-Codes und Beschreibungen."""
    # Einfacherer Ansatz: Jede Zeile separat parsen
    lines = text.split('\n')
    result = []
    
    for line in lines:
        # ICD-Codes in dieser Zeile finden
        pattern = r'([A-Z]\d+\.?\d*)\s*-\s*([^,]+(?:,(?!\s*[A-Z]\d)[^,]+)*)'
        matches = re.findall(pattern, line)
        
        for match in matches:
            icd_code = match[0].strip()
            description = match[1].strip()
            
            # Beschreibungen mit Kommas bereinigen (nur wenn sie zu diesem Code gehören)
            # Wir nehmen alles bis zum nächsten ICD-Code oder Zeilenende
            result.append((icd_code, description))
    
    return result


def normalize_region_label(label: str) -> str:
    """Normalisiert Regionsnamen für die Datenbank."""
    # Null-Bytes und andere Steuerzeichen entfernen
    label = label.replace('\x00', ' ')
    # Nicht-druckbare Zeichen entfernen (inkl. andere Steuerzeichen)
    label = ''.join(c for c in label if c.isprintable() or c.isspace())
    # Klammern entfernen
    label = re.sub(r'[()]', '', label)
    # Mehrere Leerzeichen zusammenführen
    label = re.sub(r'\s+', ' ', label)
    # Leerzeichen durch Unterstriche ersetzen
    label = label.lower().replace(' ', '_')
    # Mehrere Unterstriche zusammenführen
    label = re.sub(r'_+', '_', label)
    return label.strip('_')


def _is_region_row(row: list[dict]) -> bool:
    """True wenn die Zeile mindestens ein ALL-CAPS-Wort hat und keine Monats-/Skipwörter."""
    words = [w['text'] for w in row]
    has_allcaps = any(
        len(w) >= 3
        and w.replace('ß', 'S').isupper()
        and w.replace('ß', 'S').replace('Ä', 'A').replace('Ö', 'O').replace('Ü', 'U').isalpha()
        for w in words
    )
    has_month = any(w in _MONTH_ABBREVS for w in words)
    has_skip = any(w.lower().rstrip(':') in _SKIP_WORDS for w in words)
    return has_allcaps and not has_month and not has_skip


def extract_pain_regions(pages: list) -> list[dict]:
    """Extrahiert Schmerzbereiche von Seiten 5–11 (Zeitverlaufs-Charts)."""
    cards = []
    seen = set()

    for page in pages:
        words = page.extract_words()
        if not words:
            continue

        # Nach Y-Position gruppieren (Toleranz 3 pt)
        words_sorted = sorted(words, key=lambda w: w['top'])
        rows: list[list[dict]] = []
        current_row = [words_sorted[0]]
        for word in words_sorted[1:]:
            if abs(word['top'] - current_row[0]['top']) <= 3:
                current_row.append(word)
            else:
                rows.append(current_row)
                current_row = [word]
        rows.append(current_row)

        mid_x = page.width / 2

        for row in rows:
            row_texts = [w['text'] for w in sorted(row, key=lambda w: w['x0'])]
            if 'Übersicht der Schmerzbereiche' in ' '.join(row_texts):
                continue
            if not _is_region_row(row):
                continue

            # Zeile an Seitenmitte in linke und rechte Karte aufteilen
            for side_words in (
                [w for w in row if w['x0'] < mid_x],
                [w for w in row if w['x0'] >= mid_x],
            ):
                if not side_words:
                    continue
                side_texts = [w['text'] for w in sorted(side_words, key=lambda w: w['x0'])]
                # Seite muss mindestens ein ALL-CAPS-Wort enthalten
                if not any(
                    len(t) >= 3
                    and t.replace('ß', 'S').isupper()
                    and t.replace('ß', 'S').replace('Ä', 'A').replace('Ö', 'O').replace('Ü', 'U').isalpha()
                    for t in side_texts
                ):
                    continue
                region_label = ' '.join(side_texts)
                region = normalize_region_label(region_label)
                if region and region not in seen:
                    seen.add(region)
                    cards.append({
                        'region_label': region_label,
                        'region': region,
                        'pain_score': None,
                        'duration': None,
                        'pain_type': None,
                        'timing': None,
                    })

    return cards


def extract_region_scores_vlm(pdf_path: Path) -> dict[str, int]:
    """Liest Schmerzscores per VLM aus Seiten 3–4 der Schmerzkarte.

    Gibt {region_key: score} zurück. Gibt {} zurück wenn kein API-Key
    konfiguriert oder pdf2image nicht verfügbar ist.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        return {}

    import base64, io, json as _json, re, urllib.request, urllib.error

    api_key = _cfg._cfg.get("llm", {}).get("openrouter_api_key", "")
    model   = _cfg._cfg.get("llm", {}).get("openrouter_model",
                                            "anthropic/claude-sonnet-4-6")
    if not api_key:
        return {}

    # Farbskala-Referenzbild laden
    scale_path = Path(__file__).parent.parent.parent / "intern" / "mm_farbskala" \
                 / "Bildschirmfoto 2026-07-05 um 16.52.33.png"
    if not scale_path.exists():
        return {}
    scale_b64 = base64.b64encode(scale_path.read_bytes()).decode()

    # Seiten 3–4 (Index 2–3) als Bilder
    try:
        pages = convert_from_path(pdf_path, dpi=150, first_page=3, last_page=4)
    except Exception:
        return {}

    results: dict[str, int] = {}

    for page_img in pages:
        buf = io.BytesIO()
        page_img.save(buf, format="PNG")
        page_b64 = base64.b64encode(buf.getvalue()).decode()

        prompt = (
            "Bild 1 zeigt die Farbskala für Schmerzintensität: "
            "grün = 1 (leichter Schmerz) bis orange/rot = 10 (stärkster Schmerz), "
            "grau = 0 (keine Bewertung).\n"
            "Bild 2 ist eine medizinische Schmerzkarte mit einer Körpersilhouette. "
            "Jede eingefärbte Region hat einen Schmerzwert der Farbe aus Bild 1 entspricht.\n"
            "Identifiziere alle sichtbaren Körperregionen und schätze den Schmerzwert (0–10) "
            "anhand der Farbe in Bild 1.\n"
            "Antworte NUR als JSON-Array ohne Text davor/danach:\n"
            '[{"region": "Körperteil auf Deutsch", "score": N}]'
        )

        payload = _json.dumps({
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{scale_b64}"}},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{page_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            "max_tokens": 2000,
            "temperature": 0.1,
        }).encode()

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://github.com/kyoro-healthhub",
                "X-Title":       "Kyoro-HealthHub MM Scores",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = _json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            m = re.search(r'\[[\s\S]*?\]', content)
            if not m:
                continue
            items = _json.loads(m.group(0))
            for item in items:
                label = str(item.get("region", "")).strip()
                score = item.get("score")
                if label and score is not None:
                    try:
                        score_int = max(0, min(10, int(score)))
                    except (ValueError, TypeError):
                        continue
                    region_key = normalize_region_label(label)
                    if region_key:
                        results[region_key] = score_int
        except Exception:
            continue

    return results


# Skipp-Flag für VLM (wird von --no-vlm gesetzt)
_skip_vlm = False


def parse_pdf(pdf_path: Path) -> dict:
    """Extrahiert alle Daten aus einer Medical Motion PDF."""
    import pdfplumber
    
    result = {
        'meta': {},
        'diagnoses': [],
        'pain_regions': []
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Seite 1: Report-Zeitraum und Scores
            page1_text = pdf.pages[0].extract_text()
            
            # Report-Zeitraum
            period = extract_report_period(page1_text)
            if period:
                result['meta']['report_from'], result['meta']['report_to'] = period
            
            # Schmerztrend
            pain_trend = extract_pain_trend(page1_text)
            if pain_trend:
                result['meta']['pain_trend'] = pain_trend
            
            # Chirurgie-Regionen
            surgery_regions = extract_surgery_regions(page1_text)
            if surgery_regions:
                result['meta']['surgery_regions'] = surgery_regions
            
            # Scores und Labels: Labels per Koordinaten, Scores per OCR
            scores = extract_scores_and_labels(pdf.pages[0].extract_words())
            result['meta'].update(scores)
            result['meta'].update(extract_scores_ocr(pdf_path))
            
            # Seite 2: Diagnosen und Übungsstatistiken
            page2_text = pdf.pages[1].extract_text()
            
            # ICD-Codes
            icd_codes = extract_icd_codes(page2_text)
            result['diagnoses'] = icd_codes
            
            # Übungsstatistiken
            exercise_stats = extract_exercise_stats(page2_text)
            result['meta'].update(exercise_stats)
            
            # Seiten 5–11: Schmerzbereiche (Zeitverlaufs-Charts)
            pain_pages = pdf.pages[4:11]  # Seiten 5-11 (Index 4-10)
            pain_regions = extract_pain_regions(pain_pages)
            result['pain_regions'] = pain_regions
            
            # Schmerzscores via VLM (Seiten 3–4)
            if not _skip_vlm:
                vlm_scores = extract_region_scores_vlm(pdf_path)
                for region_data in result['pain_regions']:
                    if region_data['region'] in vlm_scores:
                        region_data['pain_score'] = vlm_scores[region_data['region']]
            
    except Exception as e:
        print(f"Fehler beim Parsen von {pdf_path}: {e}")
        raise
    
    return result


def get_last_import(conn) -> str | None:
    """Ermittelt das Datum des letzten Imports."""
    r = conn.execute(
        "SELECT MAX(report_to) FROM mm_report_meta WHERE person=?",
        (OWN_PERSON_ID,)
    ).fetchone()
    return r[0] if r and r[0] else None


def import_pdf(conn, pdf_path: Path, update_from: str | None) -> int:
    """Importiert eine PDF in die DB. Gibt Anzahl eingefügter Zeilen zurück."""
    # Daten parsen
    data = parse_pdf(pdf_path)
    
    total_inserted = 0
    
    # Meta-Daten importieren
    meta = data['meta']
    if meta.get('report_from') and meta.get('report_to'):
        # Prüfen, ob Update-Modus aktiv ist
        if update_from and meta['report_to'] < update_from:
            print(f"  Report bis {meta['report_to']} ist älter als Update-Cutoff {update_from} — übersprungen")
        else:
            conn.execute("""
                INSERT OR IGNORE INTO mm_report_meta
                (report_from, report_to, wellbeing_score_start, wellbeing_label_start,
                 wellbeing_score_end, wellbeing_label_end, pain_score_start, pain_label_start,
                 pain_score_end, pain_label_end, pain_trend, exercise_days_done,
                 exercise_days_total, exercises_done, exercises_skipped, longest_streak,
                 surgery_regions, source_file, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                meta['report_from'], meta['report_to'],
                meta.get('wellbeing_score_start'), meta.get('wellbeing_label_start'),
                meta.get('wellbeing_score_end'), meta.get('wellbeing_label_end'),
                meta.get('pain_score_start'), meta.get('pain_label_start'),
                meta.get('pain_score_end'), meta.get('pain_label_end'),
                meta.get('pain_trend'),
                meta.get('exercise_days_done'), meta.get('exercise_days_total'),
                meta.get('exercises_done'), meta.get('exercises_skipped'),
                meta.get('longest_streak'),
                meta.get('surgery_regions'),
                str(pdf_path),
                OWN_PERSON_ID
            ))
            
            cursor = conn.execute("SELECT changes()")
            if cursor.fetchone()[0] > 0:
                total_inserted += 1
            
            # Diagnosen importieren
            for icd_code, description in data['diagnoses']:
                conn.execute("""
                    INSERT OR IGNORE INTO mm_diagnoses
                    (report_to, icd_code, description, person)
                    VALUES (?,?,?,?)
                """, (meta['report_to'], icd_code, description, OWN_PERSON_ID))
                cursor = conn.execute("SELECT changes()")
                if cursor.fetchone()[0] > 0:
                    total_inserted += 1
            
            # Schmerzbereiche importieren
            for region_data in data['pain_regions']:
                conn.execute("""
                    INSERT OR IGNORE INTO mm_pain_regions
                    (report_to, region, region_label, pain_score, duration, pain_type, timing, person, source)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    meta['report_to'],
                    region_data['region'],
                    region_data.get('region_label'),
                    region_data.get('pain_score'),
                    region_data.get('seit'),
                    region_data.get('typ'),
                    region_data.get('wann'),
                    OWN_PERSON_ID,
                    'medical_motion'
                ))
                cursor = conn.execute("SELECT changes()")
                if cursor.fetchone()[0] > 0:
                    total_inserted += 1
            
            log_import(conn, 'medical_motion', str(pdf_path), total_inserted)
            conn.commit()
    
    return total_inserted


def list_inbox_pdfs() -> list[Path]:
    """Listet PDFs aus dem Inbox-Verzeichnis ohne sie zu verschieben."""
    return list(INBOX_DIR.glob("mm_*.pdf"))


def move_to_processed(pdf: Path) -> None:
    """Verschiebt eine PDF nach erfolgreichem Import in das processed-Verzeichnis."""
    processed_dir = INBOX_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    target = processed_dir / f"{pdf.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{pdf.suffix}"
    pdf.rename(target)


def main():
    parser = argparse.ArgumentParser(description=t("Medical Motion PDF → health.db", "Medical Motion PDF → health.db"))
    parser.add_argument("--file", help=t("Bestimmte PDF-Datei", "Specific PDF file"))
    parser.add_argument("--inbox", action="store_true", help=t("Verarbeite _inbox/mm_*.pdf", "Process _inbox/mm_*.pdf"))
    parser.add_argument("--update", action="store_true", help=t("Nur neue Daten", "Only new data"))
    parser.add_argument("--no-vlm", action="store_true",
        help=t("VLM-Scoring überspringen (schneller, offline)",
               "Skip VLM scoring (faster, offline)"))
    add_lang_arg(parser)
    
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    # VLM-Skip-Flag setzen
    global _skip_vlm
    _skip_vlm = args.no_vlm
    
    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Tabellen erstellen (einmalig)
    conn.executescript(_SCHEMA_SQL)
    
    update_from = None
    if args.update:
        last = get_last_import(conn)
        if last:
            from datetime import timedelta
            d = datetime.strptime(last, "%Y-%m-%d")
            update_from = (d + timedelta(days=1)).strftime("%Y-%m-%d")
            print(t(f"Update-Modus: ab {update_from}", f"Update mode: from {update_from}"))
    
    # Dateien ermitteln
    if args.file:
        files = [Path(args.file)]
    elif args.inbox:
        files = list_inbox_pdfs()
    else:
        files = sorted(MM_DIR.glob("*.pdf"))
    
    if not files:
        if args.inbox:
            print(t(f"Keine Medical Motion PDFs in {INBOX_DIR}", f"No Medical Motion PDFs in {INBOX_DIR}"))
        else:
            print(t(f"Keine PDF-Dateien in {MM_DIR}", f"No PDF files in {MM_DIR}"))
        return
    
    total = 0
    for f in files:
        print(f"  {f.name} ...", flush=True)
        try:
            n = import_pdf(conn, f, update_from)
            total += n
            print(t(f"    {n} Einträge", f"    {n} entries"))
            # Nur bei erfolgreichem Import verschieben (Inbox-Modus)
            if args.inbox:
                move_to_processed(f)
                print(t("    → verschoben nach processed/", "    → moved to processed/"))
        except Exception as e:
            print(f"    Fehler: {e}")
            # Bei Fehler bleibt die Datei in _inbox/ für manuelle Prüfung
    
    # Statistik anzeigen
    r = conn.execute(
        "SELECT COUNT(*) FROM mm_report_meta WHERE person=?",
        (OWN_PERSON_ID,)
    ).fetchone()
    
    print(t("\n── Medical Motion ──────────────────────────────────────────────", "\n── Medical Motion ────────────────────────────────────────────"))
    print(t(f"  Gesamt: {r[0]} Reports", f"  Total: {r[0]} reports"))
    
    conn.close()


if __name__ == "__main__":
    main()