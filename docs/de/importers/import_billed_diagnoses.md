# Abgerechnete Diagnosen- und Medikamentenhistorie (ICD-10 + Apotheken-Verordnungen, OCR-Scan) → medicine.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_billed_diagnoses.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Extrahiert ICD-10-codierte Diagnoseeinträge UND Apotheken- Verordnungsblöcke aus einer OCR'ten Krankenkassen-/Leistungs- träger-Übersicht (gescannt + ocrmypdf) und importiert sie zweistufig (Extraktion → menschliche Review → Commit) in die bestehenden Tabellen diagnoses bzw. medications.

## Relevanz

Ermöglicht den Import einer jahrzehntelangen, gescannten Diagnose- und Medikamentenhistorie, essentiell für eine lückenlose Krankengeschichte

## Methode

Stufe 1 (--extract): liest .txt oder .pdf (via pdftotext), findet ICD-10-Codes per Regex sowie Apotheke/PZN/Verordnung-Anker, ordnet Datum/Code/Diagnosetext bzw. PZN/Präparatname per Zeilenfenster- und Typ-Heuristik zu (Label-Reihenfolge im OCR- Text ist nicht verlässlich fest). Diagnosen werden oft als Beginn/Ende-Zeitraum abgerechnet, Medikamente haben separate Verordnungs-/Abgabedaten -- find_date_candidates() sucht daher nach ZWEI Label-Typen parallel (beginn/ende bzw. verordnung/ abgabe) und choose_date() wählt pro Label-Typ unabhängig. Uneindeutige Fälle gehen NUR mit --llm-fallback an ein AUSSCHLIESSLICH LOKALES LLM (openvino/ ovms/ollama/lmstudio/llamacpp/exo/mlx — Cloud-Provider werden hart abgelehnt). Ohne --llm-fallback (Standard) werden uneindeutige Fälle NICHT ans LLM gegeben, sondern direkt mit niedriger certainty als Kandidat markiert — bewusste Abweichung vom ursprünglichen Plan, weil die auf dieser Maschine verfügbaren lokalen LLMs bei diesem Dokumentumfang (hunderte Treffer) zu langsam für einen Vollauf sind; kein Treffer wird dadurch verworfen, nur die automatische Klärung ausgelassen. Bei Diagnosen fragt der LLM-Fallback-Prompt zusätzlich nach dem korrekten ICD-10-Code (OCR verwechselt gelegentlich Ziffern/ Buchstaben, z.B. "O" statt "0") -- ein abweichender, aber regex-valider Code überschreibt den per Anker gefundenen Code. Bei beiden Typen fragt der Prompt zusätzlich nach einer knappen Fundstelle (Label/Nachbarzeile), damit ein Mensch die Stelle im Originaldokument wiederfindet. certainty=0.6-Einträge tragen deshalb in notes: Seitenzahl, diese Fundstelle (falls vom LLM geliefert) sowie den kompletten rohen OCR-Fensterausschnitt, der dem LLM vorlag -- nicht nur ein "LLM war beteiligt"-Vermerk, sondern die Grundlage, auf der das LLM seine Werte erkannt hat, damit die Review-Entscheidung ohne Rückgriff auf das Originaldokument möglich ist. Stufe 2 (--commit) liest die (ggf. von Hand korrigierte) Kandidaten-JSON und schreibt jeden Eintrag in die per "table" angegebene Zieltabelle. Der rohe Scanner-Dateiname (kann Geräte-/Batch-/ Zeitstempel-Kennungen enthalten) wird vor dem Schreiben in die Kandidaten-JSON über identity_resolver.resolve_sourcefile() pseudonymisiert, nie im Klartext gespeichert.

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `certainty = 0.9 (diagnoses)` | Datum+Text+kein Nachbar-Code eindeutig -- status=confirmed, ohne LLM |
| `certainty = 0.7 (medications)` | Datum+Präparatname+kein Nachbar-PZN eindeutig -- status=confirmed, ohne LLM |
| `certainty = 0.6` | uneindeutig, aber --llm-fallback lieferte einen Wert -- status=needs_review, notes enthält Fundstelle+OCR-Original |
| `certainty = 0.3` | uneindeutig und (ohne --llm-fallback ODER auch vom LLM) nicht klärbar -- status=needs_review |

## Datenfluss

- **Liest:** `diagnoses`, `medications`, `(für`, `Duplikat-Vermeidung`, `via`, `UNIQUE-/`, `PRIMARY-KEY-Constraint`, `nur`, `Stufe`, `2)`
- **Schreibt:**

  ```
  imports/manual/billed_diagnoses_candidates.json (Stufe 1; "source_file"
  enthält bereits das Pseudonym, nicht den rohen Scanner-Dateinamen
  -- siehe identity_resolver.resolve_sourcefile());
  diagnoses: date TEXT (Beginn), date_to TEXT (Ende, meist NULL --
  siehe @limits), icd_code TEXT, description TEXT, status TEXT,
  certainty REAL, source TEXT, notes TEXT, provider_pseudonym TEXT
  (via scripts/modules/provider_scrubbing.py);
  medications: ts TEXT, date TEXT (Verordnung), date_abgabe TEXT
  (Abgabe, meist NULL -- siehe @limits), medication_id TEXT,
  drug_name TEXT, is_chronic INTEGER, source TEXT, notes TEXT,
  prescriber_pseudonym TEXT (Verordner-Nummer, ebenfalls über
  identity_resolver pseudonymisiert statt im Klartext behalten)
  (Stufe 2)
  ```

## Grenzen

Leistungserbringer wird nur pseudonymisiert übernommen (provider_pseudonym), nicht im Klartext, und nur so präzise wie scrub_provider_text()'s Registry/Heuristiken — ein unbekannter Name ohne Titel/Adresse bleibt unerkannt (NULL). Keine Kosten-Spalte bei Diagnosen. date_to/date_abgabe werden nur gefüllt, wenn ein "Ende"-/"Abgabe"-Label eindeutig in der Nähe steht ODER das LLM-Fallback sie liefert -- die Label-Wörter selbst sind in diesem Dokumenttyp seltene Spaltenköpfe (ca. 1 pro 30 Einträge), kein Pro-Eintrag-Marker, daher bleiben beide Felder beim deterministischen Pass fast immer NULL. Bei Medikamenten keine Dosierungsangabe im Quelldokument vorhanden (dose_value/ dose_unit/route bleiben NULL). OCR-Fehler in Codes/PZN werden nur korrigiert, wenn --llm-fallback lief UND das LLM einen regex-validen abweichenden Wert zurückgab (icd_code bei Diagnosen, medication_id bei Medikamenten) -- ohne --llm-fallback oder bei einem vom LLM nicht erkannten Fehler bleibt der per Regex-Anker gefundene (ggf. fehlerhafte) Wert stehen. Dubletten-Schutz bei medications nur über (ts, person, source). Ohne --llm-fallback bleiben alle uneindeutigen Faelle auf certainty=0.3/needs_review stehen, auch wenn ein LLM sie theoretisch hätte klären können — das ist Absicht (siehe @method), keine Einschränkung, die händisches Prüfen ersetzen könnte.

## Aufruf

```bash
python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.txt
python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.pdf
python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.pdf --llm-fallback
python3 import_billed_diagnoses.py --commit
python3 import_billed_diagnoses.py --commit --file imports/manual/andere_kandidaten.json
```
