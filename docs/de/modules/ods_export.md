# ods_export.py — Generischer LibreOffice-Calc-Export mit AutoFilter

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/ods_export.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet einen wiederverwendbaren Baustein, um eine Liste von Dicts als .ods-Tabelle mit aktiviertem AutoFilter zu exportieren, ohne odfpy-Boilerplate in jedem Exporter-Skript zu wiederholen.

## Relevanz

Infrastruktur für durchsuchbare Referenz-Exporte, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Baut die Tabelle(n) direkt mit odfpy auf (kein LibreOffice- Prozess nötig) und hinterlegt pro Tabellenblatt einen table:database-range über den gesamten Datenbereich, damit Calc die Filter-Pfeile in der Kopfzeile sofort anzeigt. export_to_ods() erzeugt ein Blatt, export_multi_sheet_to_ods() mehrere Blätter in einer Datei. Listenfelder werden für die Tabellenzelle mit "; " verbunden.

## Datenfluss

- **Liest:** `Keine`, `Tabellen`, `(reine`, `Funktionsbibliothek)`
- **Schreibt:** `Die vom Aufrufer angegebene .ods-Datei`

## Grenzen

Keine Datenvalidierung; Zellinhalte werden 1:1 aus den übergebenen Dicts übernommen.

## Aufruf

```bash
from modules.ods_export import export_to_ods, export_multi_sheet_to_ods
export_to_ods(
    rows=kliniken,
    columns=[("id", "ID"), ("name", "Name")],
    sheet_name="Kliniken",
    output_file=Path("out.ods"),
)
export_multi_sheet_to_ods(
    sheets=[(rows1, columns1, "Tabelle1"), (rows2, columns2, "Tabelle2")],
    output_file=Path("out.ods"),
)
```
