# check_fsme_source_freshness — Erkennt Aktualisierungen der RKI-FSME-Risikogebietsquelle

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_fsme_source_freshness.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft, ob sich die RKI-Quelle hinter den in import_outbreak_data.py hart codierten FSME-Risikokreis-Listen (FSME_RISIKOKREISE_*) seit der letzten Prüfung geändert hat, damit die jährlich fällige Aktualisierung (RKI veröffentlicht i.d.R. Ende Februar im Epidemiologischen Bulletin, meist Ausgabe 9) nicht schlicht vergessen wird.

## Relevanz

Ohne diese Pruefung bleibt die jaehrliche FSME-Risikokreis- Aktualisierung rein gedaechtnisbasiert -- genau das Wartungsproblem, das nach der bundesweiten FSME-Erweiterung im September 2026 auffiel (die vorherige Quelle war bereits tot, ohne dass es aufgefallen war).

## Methode

Lädt die RKI-FSME-Themenseite per HTTP und extrahiert per Regex den Text "Epid Bull <Ausgabe>/<Jahr>", mit dem die Seite direkt neben "Karte der FSME-Risikogebiete" auf die aktuell gueltige Ausgabe des Epidemiologischen Bulletins verweist. Ein SHA-256-Hash der kompletten Seite waere hier NICHT robust genug -- verifiziert per Mehrfachabruf: dieselbe Seite liefert bei jedem Request einen anderen Hash trotz identischer Byte-Laenge (vermutlich Tracking- Token o.ae. im HTML), waehrend der Ausgabe-Verweis stabil bleibt. Vergleicht diesen Verweis gegen den zuletzt bestätigten in fsme_source_baseline.json. Anders als beim Tigermuecken-Checker gibt es keine feste jaehrliche PDF-URL zum direkten Ueberwachen -- das Epid.-Bulletin-PDF mit der eigentlichen Risikokreis-Tabelle muss nach einer erkannten Ausgaben-Aenderung manuell gesucht werden (z.B. Websuche "RKI Epidemiologisches Bulletin FSME-Risikogebiete <Jahr>").

## Datenfluss

- **Liest:** `Externe`, `URL`, `(RKI`, `FSME-Themenseite);`, `fsme_source_baseline.json`, `(lokaler`, `Zustand)`
- **Schreibt:** `fsme_source_baseline.json (nur mit --update)`

## Grenzen

Die RKI-Themenseite ist ein allgemeiner Ueberblicksartikel, kein maschinenlesbares Datenformat -- ein geaenderter Hash kann auch rein kosmetische Aenderungen bedeuten (z.B. Layout, Werbebanner) ohne inhaltlichen Bezug zu den Risikogebieten. Ersetzt keine jaehrliche manuelle Pruefung, verhindert nur, dass sie vergessen wird. Die frueher hart codierten RKI-Content-URLs in import_outbreak_data.py waren zum Zeitpunkt dieses Skripts bereits seit unbekannter Zeit tot (404) -- dieselbe Site-Struktur- Aenderung koennte die hier verwendete Themenseiten-URL erneut brechen; ein dauerhaft fehlschlagender Abruf ist daher ebenfalls ein Pruefsignal, nicht nur ein geaenderter Hash.

## Aufruf

```bash
python3 scripts/utils/check_fsme_source_freshness.py
python3 scripts/utils/check_fsme_source_freshness.py --update
```
