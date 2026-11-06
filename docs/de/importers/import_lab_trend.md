# import_lab_trend.py — Laborwert-Trendberichte & in Arztbriefe eingebettete Laborwerte (mehrere Daten pro Dokument möglich) → medicine.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_lab_trend.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Extrahiert Laborwerte per lokalem LLM aus (a) historischen Trend-Berichten, bei denen mehrere Entnahme-Daten als Spalten in einer Zeile nebeneinander stehen (z.B. "Marker 10,0-20,0s 15,0s 03.04.2000 01.02.2000 ..."), statt wie import_lab_results.py ein Datum pro Dokument/Seite anzunehmen, UND (b) Laborwerten, die in einen Arztbrief eingebettet sind (Brieftext + Laborwerte auf derselben Seite) — der Prompt weist das LLM explizit an, NUR echte Laborwerte zu extrahieren, keine anderen Messwerte aus demselben Brief (z.B. Ergometrie-/ EKG-/Echo-Befunde aus einem sportkardiologischen Arztbrief). Zweistufig: --extract schreibt Kandidaten zur Durchsicht, --commit schreibt erst danach in die DB.

## Relevanz

Ermöglicht den Import historischer Laborwert-Trendberichte, essentiell für die lückenlose Laborhistorie

## Methode

Liest PDF (via pdftotext, erwartet bereits OCR'te Datei — siehe ocrmypdf) oder .txt. Pro Seite: findet alle Datumsmuster (TT.MM.JJJJ) im Text. Die eigentliche Werte-zu-Datum-Zuordnung läuft NICHT über Regex (bei gescrambeltem OCR-Spaltenlayout unzuverlässig), sondern über ein AUSSCHLIESSLICH LOKALES LLM (modules.llm.call_llm_importer_only — verweigert den Aufruf, wenn der effektive Provider nicht lokal ist, auch bei "multi"). Jede Seite wird einzeln ans LLM gegeben mit der Bitte, alle (date, parameter, wert, einheit, ref_min, ref_max, labor, fundstelle)-Tupel zu extrahieren, die es auf der Seite finden kann — auch wenn pro Zeile mehrere Daten/Werte stehen. "fundstelle" (die Textzeile(n), möglichst wortgleich zum Original) geht über modules.review_notes.build_ocr_note() ins notes-Feld jedes Kandidaten, zusammen mit der Seitenzahl -- derselbe Baustein wie in import_billed_diagnoses.py, damit ein Mensch die Stelle auf der Seite wiederfindet, ohne das Originaldokument komplett neu zu durchsuchen; notes läuft vor dem Schreiben durch scrub_patient_identity(), da ein Laborbefund typischerweise über die Nutzerin selbst ist und die zitierte Zeile ihre Identität enthalten kann. Anders als bei import_billed_diagnoses.py gibt es hier KEINEN Regex- bestätigten "eindeutig"-Fall -- jeder Kandidat stammt aus demselben nicht-deterministischen LLM-Aufruf, daher ist status IMMER "needs_review" und llm_attempted IMMER true; certainty ist nach Anzahl verschiedener Entnahme-Daten auf der Seite gestuft (_page_certainty(): 1 Datum -> 0.6, 2-3 -> 0.5, 4+ -> 0.3), nicht mehr eine Konstante 0.5 wie zuvor -- je mehr Daten- Spalten nebeneinander stehen, desto fehleranfälliger die Zuordnung (siehe @limits). Frühere Berichte schreiben das Jahr teils nur zweistellig (TT.MM.JJ) -- _normalize_date() erweitert das auf vierstellig (Jahrhundert- Heuristik: JJ <= aktuelles zweistelliges Jahr -> 20JJ, sonst 19JJ), sowohl als Fallback nach dem LLM-Aufruf als auch per Prompt-Anweisung ans LLM selbst. Nach JEDER Seite (nicht erst am Ende) wird die Kandidaten-JSON atomar neu geschrieben und das (Datei,Seite)-Paar in einer *.progress.json-Sidecar vermerkt -- bei dichten Seiten kann ein einzelner LLM-Aufruf mehrere Minuten dauern, ein Absturz nach vielen Seiten darf nicht den gesamten Lauf kosten. Ein erneuter --extract-Aufruf überspringt bereits verarbeitete Seiten automatisch. Ergebnis geht NIE direkt in die DB: erst --extract (Kandidaten-JSON zur Durchsicht), dann --commit (tatsächlicher Import, mit Duplikat-Check gegen date+parameter+labor+person in lab_manual). Der rohe Scanner-/Quelldateiname (kann Geräte-/Batch-/ Zeitstempel-Kennungen enthalten, z.B. bei einem Scan-Batch) wird NIE in die Kandidaten-JSON geschrieben, nur sein Pseudonym (identity_resolver.resolve_sourcefile(), dasselbe Prinzip wie in import_billed_diagnoses.py) -- gefunden als fehlend beim ersten echten Lauf, nachgebessert. Ebenso wird der extrahierte Labor-/Praxisname pseudonymisiert (_pseudonymize_labor(): Registry-Abgleich via provider_scrubbing.scrub_provider_text() wie in import_lab_results.py, aber MIT Fallback auf einen Hash- Pseudonym für nicht registrierte Namen statt sie wie dort unverändert zu lassen -- siehe @limits für die Begründung der Abweichung).

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `certainty = 0.6` | nur 1 Entnahme-Datum auf der Seite -- status immer needs_review, nie confirmed |
| `certainty = 0.5` | 2-3 Entnahme-Daten auf der Seite nebeneinander |
| `certainty = 0.3` | 4 oder mehr Entnahme-Daten auf der Seite -- Spalten-Zuordnung am fehleranfälligsten |
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

## Datenfluss

- **Liest:** `lab_manual`, `(medicine.db)`, `—`, `nur`, `für`, `--commit`, `(Duplikat-Check)`
- **Schreibt:**

  ```
  imports/manual/lab_trend_candidates.json (--extract, nach jeder
  Seite neu geschrieben -- siehe @method); *.progress.json
  (Sidecar, bereits verarbeitete (Datei,Seite)-Paare für Resume);
  lab_manual in medicine.db (--commit)
  ```

## Grenzen

Qualität der Zuordnung hängt vom lokalen LLM ab — kann Werte falsch zuordnen, besonders bei sehr dichten Tabellen. Jede Kandidatenzeile trägt eine gestufte certainty (siehe

## Aufruf

```bash
python3 import_lab_trend.py --extract --file bericht.pdf
python3 import_lab_trend.py --extract --file bericht1.pdf bericht2.txt
python3 import_lab_trend.py --extract --file *.pdf --skip S001-004 --skip S023-027
python3 import_lab_trend.py --extract --file grosser_batch/*.pdf --out imports/manual/lab_trend_batch2.json
python3 import_lab_trend.py --commit
python3 import_lab_trend.py --commit --file imports/manual/andere_kandidaten.json
```
