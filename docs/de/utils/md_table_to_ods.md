# md_table_to_ods.py — Markdown-Tabellen → LibreOffice-Calc

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/md_table_to_ods.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wandelt jede GFM-Markdown-Tabelle (| Spalte | Spalte |) in einer beliebigen .md-Datei in ein Tabellenblatt einer .ods-Datei mit aktiviertem AutoFilter um — allgemeiner Helfer, nicht an ein bestimmtes Dokumentformat gebunden. Fallback für Dateien ohne Tabelle: das "### Rang N: REF — Name"-Format der von analyse_reha_klinik_empfehlung.py gespeicherten Berichte.

## Relevanz

Allgemeines Konvertierungswerkzeug, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Sucht zeilenweise nach dem Muster Kopfzeile+Trennzeile (`|---|---|`), sammelt die folgenden Datenzeilen bis zur nächsten Leerzeile/Nicht-Tabellenzeile, und merkt sich die zuletzt gesehene Markdown-Überschrift als Tabellenblattnamen. Mehrere Tabellen in derselben Datei werden zu mehreren Tabellenblättern in einer .ods (via modules/ods_export.export_multi_sheet_to_ods). Zellinhalte werden von Fett-/Kursiv-/Code-Markup befreit, escapte Pipes (\|) werden entpackt. Findet sich keine Tabelle, wird stattdessen versucht, "### Rang N: REF — Name"-Einträge zu parsen; pro Eintrag werden alle vorkommenden fett markierten Felder ("**Label:** Inhalt") generisch als Spalte übernommen, statt einen festen Feldsatz vorauszusetzen — LLM-Freitext ist kein festes Schema. Ein Feld ohne Inline-Inhalt (z. B. "Offene Fragen:" gefolgt von einer Aufzählung) wird aus der nachfolgenden Bullet-Liste zusammengesetzt.

## Datenfluss

- **Liest:** `Die`, `vom`, `Aufrufer`, `angegebene`, `.md-Datei`
- **Schreibt:** `Die vom Aufrufer angegebene (oder abgeleitete) .ods-Datei`

## Grenzen

Nur GFM-Pipe-Tabellen bzw. das feste "### Rang N: ..."-Muster, keine anderen Tabellen-/Berichtsformate. Keine Typ-Erkennung — alle Zellen werden als Text behandelt, keine automatische Zahlenkonvertierung. Der Rang-N-Fallback ist auf Freitext eines LLM angewiesen — abweichende Formulierungen (z. B. andere Feldnamen) landen als eigene, ungruppierte Spalte statt in der erwarteten.

## Aufruf

```bash
python3 md_table_to_ods.py klinikliste.md
python3 md_table_to_ods.py klinikliste.md --output ausgewaehlte_kliniken.ods
```
