# check_icd_codes.py — ICD-10-GM-Code↔Text-Review-Checker für Kandidaten-JSON

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_icd_codes.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Scannt eine Kandidaten-JSON von import_billed_diagnoses.py (Stufe 1, vor --commit) und meldet pro diagnoses-Zeile, ob der icd_code real existiert UND ob description inhaltlich zum amtlichen Titel dieses Codes passt -- der eigentliche "ICD-Checker", der weder import_billed_diagnoses.py's ICD_RE (nur Format) noch dessen _looks_bundled() (nur Struktur-Signal "mehrere Diagnosen zusammengezogen") leisten kann: eine Code↔Text-Fehlzuordnung mit nur EINER (nicht mehreren) Diagnose bleibt sonst unsichtbar.

## Relevanz

Macht Code↔Text-Fehlzuordnungen sichtbar, die sonst erst beim zufälligen Drüberlesen auffallen (wie im F32.9-Fall), essentiell vor --commit

## Methode

Pro diagnoses-Zeile (table=="diagnoses"): modules.icd10_catalog.is_known()/ lookup()/.check_description_plausible()/.check_bundled_contamination(). Fünf Ausgabekategorien: UNBEKANNTER CODE (Code existiert nicht im geladenen ICD-10-GM-Jahrgang -- fängt z.B. OCR-verwechselte Ziffern, die trotzdem das Regex-Format treffen), NICHT- TERMINALER CODE (Code existiert, aber nur als Kategorie- Überschrift ohne fünfte Stelle -- laut Metadaten-Feld 13/14 nicht zur Verschlüsselung zugelassen, z.B. "F60.3" statt "F60.31"), GEBÜNDELT/KONTAMINIERT (geprüft VOR Text-Mismatch: description enthält die zum Code passende Diagnose, aber zusätzlich Text fremder Diagnosen -- check_description_plausible() allein würde das als "plausibel" werten, weil die passenden Wörter ja irgendwo in der Mitte des längeren Textes stehen), TEXT-MISMATCH (Code existiert, aber description teilt kein Inhaltswort mit dem amtlichen Titel -- Zeilen mit dem Platzhalter "(nicht automatisch zuordenbar)" werden übersprungen, da dort gar kein Text zum Vergleichen vorliegt), sowie, falls kein Katalog installiert ist, ein einmaliger Hinweis auf update_icd10_catalog.py statt stiller Null- Treffer. Ändert NICHTS an der Kandidaten-Datei -- reiner Report, die Entscheidung (Text korrigieren, Code korrigieren, als false positive ignorieren) bleibt bei der Nutzerin.

## Datenfluss

- **Liest:** `imports/manual/billed_diagnoses_candidates.json`, `(Default`, `oder`, `--file);`, `data/reference/icd10gm/`, `(über`, `modules.icd10_catalog)`
- **Schreibt:** `keine Tabellen (reiner Report nach stdout)`

## Grenzen

Erkennt nur, was modules.icd10_catalog erkennen kann -- siehe dessen @limits (Wortüberlappungs-Heuristik, kein semantischer Vergleich; nur Codes der installierten Jahresversion). Ein Mismatch-Report ist ein Hinweis, keine automatische Korrektur -- manche echten Diagnosetexte (z.B. ein vollständiger Arztbrief-Satz statt des knappen amtlichen Kurztitels) teilen zufällig kein Inhaltswort und werden als False Positive gemeldet.

## Aufruf

```bash
python3 check_icd_codes.py
python3 check_icd_codes.py --file imports/manual/andere_kandidaten.json
```
