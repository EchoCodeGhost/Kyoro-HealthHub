# apply_icd_corrections.py — ICD-10-GM-Text-Mismatches in einer Kandidaten-JSON automatisch korrigieren (neue Datei)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/apply_icd_corrections.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wendet die von check_icd_codes.py gefundenen Text-Mismatches automatisch an: description wird durch den amtlichen ICD-10-GM-Klassentitel ersetzt, der alte Wert bleibt in notes erhalten. Schreibt NIE die Eingabedatei, sondern immer eine neue Ausgabedatei -- die Korrektur ist ein Vorschlag, der vor --commit noch durchgesehen werden soll (die ersetzten/ markierten Zeilen bleiben als solche erkennbar, siehe icd_catalog_flag).

## Relevanz

Automatisiert den mechanischen Teil der ICD-Review-Arbeit (Text-Ersetzung), hält aber jede Änderung nachvollziehbar, essentiell um die Masse an Text-Mismatches handhabbar zu machen

## Methode

Pro diagnoses-Zeile: unbekannter Code oder nicht-terminaler Code werden NICHT automatisch korrigiert (es gibt keine sichere automatische Lösung -- der richtige Code bzw. die fünfte Stelle ist unbekannt), sondern nur mit icd_catalog_flag="unknown_code"/"non_terminal" markiert und ein Warnhinweis an notes angehängt, damit sie beim Review in der neuen Datei trotzdem auffindbar sind (z.B. "grep icd_catalog_flag"). Zwei Fälle werden automatisch korrigiert, jeweils description durch lookup(code)["title"] ersetzt und der alte Wert an notes angehängt (NICHTS geht verloren, nur überschrieben wirkt es auf den ersten Blick): Text-Mismatches (Code bekannt und terminal, aber description teilt kein Inhaltswort mit dem amtlichen Titel -- icd_catalog_flag= "text_mismatch_corrected") UND gebündelte/kontaminierte Zeilen (description enthält die passende Diagnose PLUS Text fremder Diagnosen -- icd_catalog_flag="bundled_corrected"; wird VOR dem Text-Mismatch-Check geprüft, weil check_description_plausible() so einen Fall fälschlich als plausibel werten würde). Zeilen mit dem Platzhalter "(nicht automatisch zuordenbar)" werden übersprungen (kein Text zum Ersetzen vorhanden). medications- Zeilen werden unverändert durchkopiert (ICD-Katalog gilt nur für Diagnosen). JEDE markierte Zeile wird zusätzlich auf status="needs_review" zurückgestuft, auch wenn sie vorher certainty=0.9/confirmed war -- gefunden an einem echten Fall: zwei L70.0-Zeilen mit einer Praxisadresse statt Diagnosetext waren "confirmed", weil die Original-Heuristik (Datum+Text+ kein Nachbar-Code) für genau diese Fehlerart blind ist; ohne das Zurückstufen hätte die Korrektur den Fehler nur versteckt (Text wirkt stimmig), statt ihn zur Prüfung vorzulegen.

## Datenfluss

- **Liest:** `Kandidaten-JSON`, `(Default:`, `imports/manual/billed_diagnoses_candidates.json);`, `data/reference/icd10gm/`, `(über`, `modules.icd10_catalog)`
- **Schreibt:**

  ```
  Neue Kandidaten-JSON (Default: <eingabe>_icd_corrected.json) --
  NIE die Eingabedatei
  ```

## Grenzen

Korrigiert NUR description, NIE icd_code selbst -- wenn der eigentliche Fehler der Code war (nicht der Text), bleibt der falsche Code stehen und description wird auf dessen (dann ebenfalls falschen) amtlichen Titel "korrigiert". Das Ergebnis sieht dann konsistent aus, ist aber trotzdem falsch -- daher weiterhin "reviewbar", nicht automatisch committen.

## Aufruf

```bash
python3 apply_icd_corrections.py
python3 apply_icd_corrections.py --file imports/manual/andere_kandidaten.json --out imports/manual/andere_korrigiert.json
```
