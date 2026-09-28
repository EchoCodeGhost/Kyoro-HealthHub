# Medical-Motion PDF-Berichte → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_medical_motion.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Liest monatliche Reports der Medical-Motion-App (CE-zertifiziertes System) und schreibt Daten zu Schmerzbereichen, Wohlbefindens-Scores und Kategorien in eigene Tabellen. Basis für Zeitreihen-Analysen.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

pdfplumber extrahiert Text seitenweise. Seite 1: Report- Zeitraum per Regex; Scores per OCR (pdf2image + pytesseract, Crop Y=455–525 pt). Seite 2: ICD-10-Codes per Regex, Übungsstatistiken per Token-Matching. Seiten 3–4 (Schmerz- karten): VLM-Aufruf (OpenRouter, vision-fähiges Modell) mit Farbskala- Referenzbild aus intern/mm_farbskala/; Scores landen in mm_pain_regions.pain_score. Seiten 5–11: Regionsnamen per Wort-Koordinaten-Gruppierung (Y-Toleranz 3 pt), Aufteilung links/rechts am Seitenmittelpunkt.

## Datenfluss

- **Liest:** `mm_report_meta`, `(MAX(report_to)`, `für`, `--update-Modus)`
- **Schreibt:**

  ```
  mm_report_meta: report_from TEXT, report_to TEXT,
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
  ```

## Grenzen

Seiten 3–4 (Schmerzkarten) sind reine Vektorgrafiken — Schmerz-Scores pro Region sind nicht als Text verfügbar; OCR-Extraktion erfordert installiertes pdf2image + tesseract. Übungsstatistiken fehlen wenn Nutzer kein Feedback gegeben hat ("Keine Angabe"). VLM-Scoring erfordert openrouter_api_key und vision-fähiges Modell (z. B. claude-sonnet-4-6 oder gpt-4o); ohne API-Key wird pain_score auf NULL gesetzt. PDF-Layout-Änderungen können das Parsing brechen.

## Aufruf

```bash
python3 import_medical_motion.py
python3 import_medical_motion.py --update
python3 import_medical_motion.py --file imports/_inbox/mm_report_05072026.pdf
python3 import_medical_motion.py --inbox
python3 import_medical_motion.py --no-vlm
```
