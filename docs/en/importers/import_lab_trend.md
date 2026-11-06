# import_lab_trend.py — Laborwert-Trendberichte & in Arztbriefe eingebettete Laborwerte (mehrere Daten pro Dokument möglich) → medicine.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_lab_trend.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Extracts lab values via a local LLM from (a) historical trend reports where several draw dates appear as side-by-side columns in one row (e.g. "Marker 10.0-20.0s 15.0s 03.04.2000 01.02.2000 ..."), instead of assuming one date per document/ page like import_lab_results.py does, AND (b) lab values embedded in a doctor's letter (letter text + lab values on the same page) — the prompt explicitly tells the LLM to extract ONLY genuine lab values, not other measurements from the same letter (e.g. exercise/ECG/echo findings from a sports- cardiology letter). Two-stage: --extract writes candidates for review, --commit writes to the DB only afterwards.

## Relevance

Enables import of historical lab trend reports, essential for a complete lab history

## Method

Reads PDF (via pdftotext, expects an already-OCR'd file — see ocrmypdf) or .txt. Per page: finds all date patterns (DD.MM.YYYY) in the text. The actual value-to-date assignment does NOT use regex (unreliable against OCR-scrambled column layout) — it uses an EXCLUSIVELY LOCAL LLM (modules.llm.call_llm_importer_only — refuses the call if the effective provider isn't local, even for "multi"). Each page is sent individually, asking the model to extract every (date, parameter, value, unit, ref_min, ref_max, labor, location) tuple it can find on that page, even when a row has several dates/values. "location" (the text line(s), as close to verbatim as possible) goes through modules.review_notes.build_ocr_note() into each candidate's notes field, together with the page number -- the same building block as in import_billed_diagnoses.py, so a human can relocate the spot on the page without re-searching the whole original document; notes is run through scrub_patient_identity() before being written, since a lab report is typically about the user themselves and the quoted line can contain their identity. Unlike import_billed_diagnoses.py, there is NO regex-confirmed "unambiguous" case here -- every candidate comes from the same non-deterministic LLM call, so status is ALWAYS "needs_review" and llm_attempted is ALWAYS true; certainty is tiered by the number of distinct draw dates on the page (_page_certainty(): 1 date -> 0.6, 2-3 -> 0.5, 4+ -> 0.3), no longer a flat 0.5 as before -- the more date columns sit side by side, the more error-prone the assignment (see @limits). Older reports sometimes write the year with only 2 digits (DD.MM.YY) -- _normalize_date() expands that to 4 digits (century heuristic: YY <= current 2-digit year -> 20YY, else 19YY), both as a fallback after the LLM call and via a prompt instruction to the LLM itself. After EVERY page (not only at the end), the candidate JSON is atomically rewritten and the (file,page) pair recorded in a *.progress.json sidecar -- on a dense page a single LLM call can take several minutes, and a crash after many pages must not cost the whole run. A re-run of --extract automatically skips already-processed pages. Result never goes straight to the DB: --extract first (candidate JSON for review), then --commit (actual import, with a duplicate check against date+parameter+labor+person in lab_manual). The raw scanner/source filename (which may embed a device/batch/timestamp identifier, e.g. in a scan batch) is NEVER written to the candidate JSON, only its pseudonym (identity_resolver.resolve_sourcefile(), same principle as in import_billed_diagnoses.py) -- found missing in the first real run, fixed since. The extracted lab/practice name is likewise pseudonymized (_pseudonymize_labor(): registry lookup via provider_scrubbing.scrub_provider_text() as in import_lab_results.py, but WITH a fallback hash pseudonym for unregistered names instead of leaving them unchanged as that importer does -- see @limits for why this deviates).

## Thresholds

| Value | Meaning |
|---|---|
| `certainty = 0.6` | only 1 draw date on the page -- status always needs_review, never confirmed |
| `certainty = 0.5` | 2-3 draw dates side by side on the page |
| `certainty = 0.3` | 4 or more draw dates on the page -- column assignment most error-prone |
| `) UND status="needs_review" -- es gibt hier, anders` |  |
| `als bei import_billed_diagnoses.py, KEINEN confirmed-Fall, weil` |  |
| `jeder Kandidat aus demselben nicht-deterministischen LLM-Aufruf` |  |
| `stammt, nie aus einem Regex-Treffer — vor --commit durchsehen,` |  |
| `nicht blind vertrauen. Die vom LLM gelieferte "fundstelle" im` |  |
| `notes-Feld ist nur so wortgetreu wie das LLM sie zitiert --` |  |
| `keine Garantie für 1:1-Übereinstimmung mit dem Originaltext.` |  |
| `Läuft NICHT ohne lokalen LLM-Provider (kein Cloud-Fallback,` |  |
| `auch nicht optional). Die extrahierte ANZAHL Werte pro Seite schwankt` |  |
| `zwischen Läufen (beobachtet: 90 vs. 18 Kandidaten für` |  |
| `dieselbe dichte Seite in zwei Läufen) -- das LLM kann bei sehr` |  |
| `vielen Werten vorzeitig abbrechen (natürlicher Stopp, nicht` |  |
| `durch max_tokens=2000 abgeschnitten), ohne dass dies als Fehler` |  |
| `erkennbar ist. Bei auffällig wenigen Kandidaten für eine` |  |
| `erkennbar dichte Seite ggf. die Seite erneut extrahieren` |  |
| `(--file erneut mit derselben Seite, nach Löschen ihres` |  |
| `Progress-Eintrags) und Ergebnisse von Hand zusammenführen.` |  |
| `_pseudonymize_labor()'s Hash-Fallback für nicht in der` |  |
| `Registry stehende Namen (Abweichung von import_lab_results.py,` |  |
| `das solche Namen unverändert lässt) hat einen eigenen` |  |
| `Kompromiss: OCR-Schreibvarianten DESSELBEN Labors ohne` |  |
| `Registry-Eintrag (z.B. "Musterlabor Beispiel GmbH" vs. "Or.` |  |
| `Musterlabar Beispiel GmbH") erhalten UNTERSCHIEDLICHE Pseudonyme,` |  |
| `keine Kanonisierung über Fuzzy-Matching -- beim Testen an` |  |
| `echten Daten deckte die Registry nur einen Teil der tatsächlich` |  |
| `vorkommenden Labor-Werte ab. Bewusst in Kauf genommen: die` |  |
| `Alternative (Klartext bei fehlendem Registry-Treffer) wäre` |  |
| `für ein Projekt mit Datenschutzanspruch schlechter als` |  |
| `redundante Pseudonyme für dasselbe Labor.` |  |

## Data flow

- **Reads:** `lab_manual`, `(medicine.db)`, `—`, `nur`, `für`, `--commit`, `(Duplikat-Check)`
- **Writes:**

  ```
  imports/manual/lab_trend_candidates.json (--extract, nach jeder
  Seite neu geschrieben -- siehe @method); *.progress.json
  (Sidecar, bereits verarbeitete (Datei,Seite)-Paare für Resume);
  lab_manual in medicine.db (--commit)
  ```

## Limitations

Assignment quality depends on the local LLM — can misassign values, especially in very dense tables. Every candidate row carries a tiered certainty (see @thresholds) AND status="needs_review" -- unlike import_billed_diagnoses.py, there is NO confirmed case here, because every candidate comes from the same non-deterministic LLM call, never from a regex match — review before --commit, don't trust blindly. The "location" the LLM supplies in the notes field is only as verbatim as the LLM quotes it -- no guarantee of an exact match to the original text. Does NOT run without a local LLM provider (no cloud fallback, not even optionally). The extracted value COUNT per page varies between runs (observed: 90 vs. 18 candidates for the same dense page across two runs) — the LLM can stop early on very value-dense pages (a natural stop, not a max_tokens=2000 cutoff), with no way to detect this as an error. If a visibly dense page yields suspiciously few candidates, consider re-extracting it (re-run --file with the same page after removing its progress entry) and merging results by hand. _pseudonymize_labor()'s hash fallback for names not in the registry (a deviation from import_lab_results.py, which leaves such names unchanged) has its own trade-off: OCR spelling variants of the SAME lab without a registry entry (e.g. "Musterlabor Beispiel GmbH" vs. "Or. Musterlabar Beispiel GmbH") get DIFFERENT pseudonyms, no canonicalization via fuzzy matching -- when tested against real data, the registry only covered part of the actually occurring lab values. Accepted deliberately: the alternative (cleartext on a missing registry hit) would be worse for a privacy-conscious project than redundant pseudonyms for the same lab.

## Usage

```bash
python3 import_lab_trend.py --extract --file bericht.pdf
python3 import_lab_trend.py --extract --file bericht1.pdf bericht2.txt
python3 import_lab_trend.py --extract --file *.pdf --skip S001-004 --skip S023-027
python3 import_lab_trend.py --extract --file grosser_batch/*.pdf --out imports/manual/lab_trend_batch2.json
python3 import_lab_trend.py --commit
python3 import_lab_trend.py --commit --file imports/manual/andere_kandidaten.json
```
