# icd10_catalog.py — Lokaler ICD-10-GM-Katalog-Abgleich (Code-Existenz + amtlicher Text)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/icd10_catalog.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft, ob ein ICD-10-GM-Code tatsächlich existiert (nicht nur formal wie ICD_RE in import_billed_diagnoses.py) und liefert dessen amtlichen Klassentitel zum Abgleich gegen einen extrahierten Freitext -- entstanden aus einem echten Fund: eine OCR-Extraktion hatte den Code F32.9 (Depressive Episode) mit einem Freitext aus VIER fremden Diagnosen bestückt, ohne dass das formale Regex-Format dies verhindert hätte (siehe import_billed_diagnoses.py::_looks_bundled() für die Struktur-Heuristik; dieses Modul deckt die inhaltliche Prüfung ab, die eine Formatprüfung nicht leisten kann).

## Relevanz

Fängt inhaltliche Fehlzuordnungen (falscher/nicht-existenter Code, Code↔Text-Mismatch) ab, die eine reine Formatprüfung nicht erkennen kann, essentiell für die Zuverlässigkeit importierter Diagnosedaten

## Methode

Liest NICHT aus dem Repo (das Repo enthält keine ICD-10-GM- Daten, siehe @limits), sondern aus einer lokalen, von scripts/utils/update_icd10_catalog.py heruntergeladenen Datei unter data/reference/icd10gm/ -- Format laut BfArM-Spezifikation (Semikolon-getrennt, Feld 7 = Code ohne Strich/Stern/ Ausrufezeichen, Feld 2 = T/N terminal-Flag, Feld 9 = zusammengesetzter Klassentitel). Wird lazy beim ersten Aufruf geladen und pro Prozess gecacht (Datei hat >16.000 Zeilen, soll nicht pro Kandidat neu eingelesen werden). check_description_plausible() vergleicht Inhaltswort- Mengen (≥4 Zeichen, Boilerplate wie "nicht näher bezeichnet" per _STOPWORDS_DE herausgefiltert) statt eines rohen Zeichen- Ratios -- ein roher difflib.SequenceMatcher-Ratio-Vergleich wurde zuerst versucht und beim Testen verworfen: kurze deutsche Wörter teilen so viele Buchstaben, dass selbst ein klar falsches Paar (J42 "chronische Bronchitis" vs. Text "Fraktur einer sonstigen Zehe") einen Ratio von 0.30 erreichte -- oberhalb jeder sinnvollen Schwelle. Keine Embeddings/kein LLM -- bewusst simpel und deterministisch, da hier nur grobe Fehlzuordnungen wie das F32.9-Beispiel gefunden werden müssen, keine feinen Formulierungsunterschiede.

## Datenfluss

- **Liest:** `data/reference/icd10gm/icd10gm<JAHR>syst_kodes.txt`, `(lokal`, `nicht`, `im`, `Repo`, `--`, `siehe`, `@limits)`
- **Schreibt:** `keine Tabellen (reine Nachschlage-/Prüffunktion)`

## Grenzen

KEIN Katalog im Repo gebündelt -- der ICD-10-GM-Download bei BfArM erfordert pro Nutzer*in die Zustimmung zu einem eigenen Nutzungsvertrag (Downloadbedingungen), das kann und soll nicht stellvertretend für alle Nutzer*innen des öffentlichen Repos einmalig geschehen. Jede Installation muss update_icd10_catalog.py selbst einmal laufen lassen (eigener Formular-Durchlauf) oder die ZIP-Datei von bfarm.de manuell ablegen. Ohne diese lokale Datei liefert jede Funktion hier None/False mit einem Hinweis auf update_icd10_catalog.py, KEIN Absturz. Nur Codes der aktuell heruntergeladenen Jahresversion werden erkannt -- ein Code, der zwischen zwei ICD-10-GM- Versionen gestrichen oder neu eingeführt wurde, kann je nach Jahr der Abrechnung fälschlich als unbekannt/bekannt gelten (siehe scripts/utils/update_icd10_catalog.py --check für Versionsstand). check_description_plausible() ist eine grobe Wortüberlappungs-Heuristik, kein semantischer Vergleich -- ein spezifischerer Text als der knappe amtliche Titel (z.B. ein ausführlicher Arztbrief-Satz) kann fälschlich als "nicht plausibel" markiert werden; gedacht als Review-Hinweis, nicht als automatische Korrektur.

## Aufruf

```bash
from modules.icd10_catalog import lookup, is_known, check_description_plausible, catalog_version
```
