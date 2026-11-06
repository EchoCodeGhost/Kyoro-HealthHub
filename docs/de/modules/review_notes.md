# review_notes.py — Baut die menschenlesbare Review-Notiz für LLM-unterstützte Kandidaten-Extraktionen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/review_notes.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erzeugt den bilingualen notes-Text (Seite + optionale vom LLM gelieferte Fundstelle + roher OCR-Ausschnitt, auf dem die LLM-Werte beruhen) für Importer nach dem Extrakt→Review→Commit- Muster (--extract schreibt Kandidaten, Mensch prüft, --commit schreibt in die DB). Ohne dieses Modul hätte jeder solche Importer dieselbe Fundstellen-/OCR-Formatierung einzeln neu geschrieben -- entstanden, als dieselbe Logik beim zweiten Importer (import_lab_trend.py) fast wortgleich zum ersten (import_billed_diagnoses.py) wiederholt worden wäre.

## Relevanz

Hält die Review-Notiz (Fundstelle + Originaltext) über alle Extrakt→Review→Commit-Importer hinweg konsistent, essentiell dafür, dass eine Review-Entscheidung ohne Rückgriff auf das Originaldokument möglich ist

## Methode

Der rohe OCR-Ausschnitt wird mit " | " statt "\n" zwischen den Zeilen zusammengesetzt, NICHT weil Zeilenumbrueche an sich stoeren, sondern weil der fertige notes-Text in jedem bekannten Aufrufer anschliessend durch scrub_patient_identity() laeuft (eigene Identitaet raus vor dem Schreiben) -- und die normalisiert jeden Whitespace (inkl. "\n") zu einem einzelnen Leerzeichen, was einen mehrzeiligen Ausschnitt sonst zu einer unlesbaren Wortwurst verschmelzen wuerde. Ein optionaler prefix (de, en) wird vor "Seite ..." gesetzt, fuer Faelle, die einen erklaerenden Satz brauchen (z.B. "LLM konnte auch nichts finden"). Das Scrubben selbst bleibt Aufgabe der Aufrufer, nicht dieses Moduls -- @limits.

## Datenfluss

- **Liest:** `keine`, `Tabellen`, `(reine`, `Textverarbeitungsfunktion)`
- **Schreibt:** `keine Tabellen (reine Textverarbeitungsfunktion)`

## Grenzen

Baut nur den Text zusammen -- entfernt KEINE Patientenidentität aus dem OCR-Ausschnitt. Aufrufer müssen das Ergebnis selbst durch scrub_patient_identity() schicken, bevor es in eine Kandidaten-JSON oder DB-Spalte geschrieben wird (der rohe OCR-Text UND eine vom LLM gelieferte Fundstelle können die Identität der Nutzerin enthalten, gerade bei Dokumenten über sie selbst). Keine Kürzung des Ausschnitts -- ein sehr breites Fenster (viele Zeilen) ergibt einen entsprechend langen notes-Wert.

## Aufruf

```bash
from modules.review_notes import build_ocr_note
de, en = build_ocr_note(page=3, raw_text=window, location=result.get("fundstelle"))
notes = t(de, en)
```
