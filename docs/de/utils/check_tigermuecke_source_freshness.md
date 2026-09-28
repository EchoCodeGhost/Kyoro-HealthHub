# check_tigermuecke_source_freshness — Erkennt Aktualisierungen der Tigermücken-Kartenquellen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_tigermuecke_source_freshness.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft, ob sich die externen Kartenquellen für die in import_outbreak_data.py hart codierten Tigermücken-Landkreisdaten (_TIGERMUECKE_*) seit der letzten Prüfung geändert haben, damit die jährlich fällige Aktualisierung nicht schlicht vergessen wird.

## Relevanz

Ohne diese Prüfung bleibt die jährliche Tigermücken-Landkreis- Aktualisierung rein gedächtnisbasiert — genau das Wartungsproblem, das nach der Landkreis-genauen Erfassung im September 2026 auffiel.

## Methode

Lädt für jede bekannte Quelle (FLI-Kommissionsseite, LGL-Monitoring- Indexseite, LGL-Jahresbericht-PDF) die Rohbytes per HTTP und bildet einen SHA-256-Hash. Vergleicht diesen gegen den zuletzt bestätigten Hash in tigermuecke_source_baseline.json. Eine Quelle gilt als "geändert", wenn der Hash abweicht; als "verschwunden", wenn der Abruf fehlschlägt (z.B. weil sich eine jahresgebundene URL wie .../jb24_....pdf zu .../jb25_....pdf geändert hat — dann muss die neue URL manuell gesucht werden, s. Kommentare in import_outbreak_data.py bei den _TIGERMUECKE_*-Listen). Es wird bewusst NICHT versucht, das "Stand: DD.MM.YYYY"-Datum aus den Kartenbildern per OCR zu lesen (Kartenbeschriftung ist reine Pixelgrafik, siehe Kommentare bei _TIGERMUECKE_BAYERN_LGL_NOTE) — der Hash-Vergleich der Rohdatei ist robuster und braucht keine Bilderkennung.

## Datenfluss

- **Liest:** `Externe`, `URLs`, `(FLI`, `LGL);`, `tigermuecke_source_baseline.json`, `(lokaler`, `Zustand)`
- **Schreibt:** `tigermuecke_source_baseline.json (nur mit --update)`

## Grenzen

Ein geänderter Hash heisst nur "die Seite/Datei hat sich irgendwie verändert" (z.B. auch bei rein kosmetischen HTML-Änderungen ohne Karteninhalt) — kein Beweis, dass sich tatsächlich Landkreis-Daten geändert haben. Umgekehrt bedeutet ein unveränderter Hash nicht, dass die Quelle inhaltlich weiter Bestand hat (Cache-Effekte beim Abruf sind nicht ausgeschlossen). Ersetzt keine jährliche manuelle Sichtprüfung, verhindert nur, dass sie vergessen wird.

## Aufruf

```bash
python3 scripts/utils/check_tigermuecke_source_freshness.py
python3 scripts/utils/check_tigermuecke_source_freshness.py --update
```
