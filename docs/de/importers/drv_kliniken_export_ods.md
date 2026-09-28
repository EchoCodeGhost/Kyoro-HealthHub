# DRV-Reha-Kliniken → LibreOffice-Calc-Export

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/drv_kliniken_export_ods.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Exportiert die von drv_kliniken_parse.py erzeugte kliniken.json als .ods-Tabelle mit aktiviertem AutoFilter, zum manuellen Durchsuchen und Filtern der Reha-Kliniken in LibreOffice Calc.

## Relevanz

Bietet ein durchsuchbares Nachschlagewerk für die Reha-Planung, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Definiert nur die Spaltenzuordnung und delegiert den Tabellenbau (odfpy, kein LibreOffice-Prozess nötig, table:database-range für sofort sichtbare Filter-Pfeile) an modules/ods_export.py — dasselbe Modul, das auch rehaportal_export_ods.py verwendet.

## Datenfluss

- **Liest:** `imports/drv-kliniken/kliniken.json`
- **Schreibt:** `analyses/reha_klinik/kliniken.ods`

## Grenzen

Keine Datenvalidierung; Zellinhalte werden 1:1 aus dem JSON übernommen.

## Aufruf

```bash
python3 drv_kliniken_export_ods.py
python3 drv_kliniken_export_ods.py --help
```
