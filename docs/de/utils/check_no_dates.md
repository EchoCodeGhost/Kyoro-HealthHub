# check_no_dates — Enforces the no-embedded-dates/versions convention (CONTRIBUTING.md)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_no_dates.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft .py- und .md-Dateien auf hardcodierte Datums-/Versionsangaben, die *wann* etwas geändert wurde oder *welche* Revision es einführte markieren (Statuswort direkt vor einem Datum wie "Fixed <Datum>" oder "Bestellt (<Datum>)", "As of <Datum>", eine bloße "Version X.Y"-Revisionsmarke, dateibehaftete Dateinamen mit angehängtem Datum vor der Endung) — genau die Muster, die docs/CONTRIBUTING.md § "Versioning and changelogs" verbietet, weil Git-Historie diese Information bereits trägt und eine im Dateiinhalt duplizierte Angabe veraltet, ohne dass es auffällt.

## Relevanz

Setzt die Datums-/Versionskonvention aus CONTRIBUTING.md technisch durch, verhindert stillschweigend veraltende Changelog-Reste im Dateiinhalt

## Methode

Wortnahe Regex-Muster statt eines pauschalen Datums-Scans: ein blindes "\d{4}-\d{2}-\d{2}"-Muster würde auf jedes legitime Datenfeld anschlagen (clinical.events, `--from 2024-01-01`-Beispiele in @usage-Blöcken, "birthdate" im Config-Template) — Tausende Fehlalarme. Stattdessen: (1) Statuswort (Fixed/Resolved/Ordered/Bestellt/Behoben/Gefunden/Repariert/ Dead/Benchmarked/Flagged/Befund/Finding/Korrigiert/Corrected/ Ergänzt/…) vor oder nach einem Datum (Volldatum ODER Monatsdatum YYYY-MM), case-insensitive, mit bis zu 4 Füllwörtern dazwischen erlaubt — fängt sowohl "Fixed 2026-07-18" als auch "Found in production data 2026-07-20" oder "2026-07-22 live verifiziert"; (2) "As of"/"Stand:"/"seit"/"since" vor einem Datum; (3) Dateiname mit angehängtem Datum vor der Endung; (4) "Version X.Y" als bloße Revisionsmarke; (5) "commit `<hash>`" als Erzähl-Referenz (nicht "git commit -m", da dort kein Hex-String folgt); (6) eine Datensatz-Zahl direkt vor einem Mengen-Substantiv (Zeilen/rows/Messungen/Datensätze/…) KOMBINIERT MIT einem Datum auf derselben Zeile — beide Teilmuster müssen treffen, damit z.B. CSV-Beispielzeilen oder ISO-Zeitstempel mit Millisekunden (".000") nicht anschlagen. Zeilen mit Zitat-Signalwörtern (doi:, AWMF, RKI, WHO, guideline, Leitlinie, …) sind von Kategorie 4 ausgenommen, da CONTRIBUTING.md Literaturangaben (Leitlinien-Versionen, Publikationsjahre, DOIs) explizit als Domäneninhalt erlaubt, nicht als Projekt-Changelog. "ab"/"bis" vor einem Datum wird bewusst NICHT geprüft — zu viele legitime Domänenfakten (Geräte-Verfügbarkeit ab Datum X, Datenquelle deckt Zeitraum bis Y ab) hätten sonst Fehlalarme ausgelöst. Scannt git-getrackte Dateien (git ls-files) — private/gitignorte Verzeichnisse (intern/, data/, …) fallen automatisch raus. Exit-Code: 0 = sauber, 1 = Findings gefunden.

## Datenfluss

- **Liest:** `all`, `git-tracked`, `.py/.md`, `files`, `in`, `the`, `scanned`, `directory`
- **Schreibt:** `stdout (report and JSON output)`

## Grenzen

Wortliste (Statuswörter, Zitat-Signalwörter, Mengen-Substantive) ist nicht erschöpfend — ungewöhnliche Formulierungen können durchrutschen. Zeilenbasiert: ein Statuswort und ein Datum, die über zwei Kommentar- /Docstring-Zeilen verteilt sind (z.B. "...(N rows, back to # YYYY-MM-DD)"), werden NICHT erkannt. Kategorie 6 (Zahl+Datum) verlangt ein explizites Mengen-Substantiv direkt nach der Zahl — ein Datensatz- Fakt ohne ein solches Substantiv auf derselben Zeile wie das Datum (z.B. "gemessen: N Zeilen über mehrere Geräte-IDs" ohne Datum in der Zeile) bleibt unentdeckt. Kann in seltenen Fällen falsch-positiv sein (z.B. ein Statuswort und ein unabhängiges Datumsfeld zufällig in derselben Zeile ohne Kausalbezug). Prüft nicht, ob ein gefundenes Datum tatsächlich stimmt/veraltet ist — nur ob eines der Muster überhaupt vorkommt.

## Aufruf

```bash
python scripts/utils/check_no_dates.py
python scripts/utils/check_no_dates.py --dir docs
python scripts/utils/check_no_dates.py --json
```
