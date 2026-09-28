# dasrehaportal.de → LibreOffice-Calc-Export

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/rehaportal_export_ods.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Exportiert die von rehaportal_parse.py erzeugte kliniken.json als .ods-Tabelle mit aktiviertem AutoFilter, zum manuellen Durchsuchen und Filtern in LibreOffice Calc.

## Relevanz

Bietet ein durchsuchbares Nachschlagewerk für die Reha-Planung, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Definiert nur die Spaltenzuordnung (inkl. Kostenträger und Zimmer-/Unterbringungsdaten, sofern die zugehörigen Detailseiten bereits per rehaportal_details_download.py heruntergeladen wurden) und delegiert den Tabellenbau an modules/ods_export.py — dasselbe Modul, das auch drv_kliniken_export_ods.py verwendet.

## Datenfluss

- **Liest:** `imports/rehaportal/kliniken.json`
- **Schreibt:** `analyses/reha_klinik/kliniken_rehaportal.ods`

## Grenzen

Keine Datenvalidierung; Zellinhalte werden 1:1 aus dem JSON übernommen. Kostenträger-/Unterbringungsspalten bleiben leer, wenn für die jeweilige Einrichtung keine Detailseite heruntergeladen wurde.

## Aufruf

```bash
python3 rehaportal_export_ods.py
python3 rehaportal_export_ods.py --help
```
