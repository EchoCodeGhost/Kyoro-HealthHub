# import_skin.py — Hautlaesionen importieren (source-agnostisch)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_skin.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Hautlaesions-Fotos und Metadaten aus verschiedenen Quellen in die medicine.db

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Akzeptiert Bilder aus Smartphone-Kamera, Screenshots (Skinscreener/SkinVision), DSLR oder anderen JPEG/PNG Quellen. Jede Laesion erhaelt eine persistente ID in skin_lesions. Folgefotos werden ueber --lesion-id verknuepft. Fotos werden in imaging_files gespeichert mit Referenz auf die Laesion. Klinische Outcomes (Hautarzt-Befund, Operation, Histologie) koennen ueber --update-lesion nachgetragen werden. Bilder werden automatisch nach JPEG normalisiert und mit anonymisierten Dateinamen gespeichert.

## Datenfluss

- **Liest:** `Bilddateien`, `(JPEG/PNG/HEIC/MOV)`, `aus`, `Inbox-Verzeichnissen`, `oder`, `als`, `Argument`
- **Schreibt:** `skin_lesions, imaging_files, user_context, import_log`

## Grenzen

Abhaengig von Bildqualitaet und Metadaten-Verfuegbarkeit. Keine automatische Bildanalyse. Histologie-Befunde muessen manuell erfasst werden.

## Aufruf

```bash
python3 scripts/importers/import_skin.py foto.jpg --location "Ruecken links, 5cm unterhalb Schulterblatt" --date 2026-06-28 --source camera
python3 scripts/importers/import_skin.py foto2.jpg --lesion-id 3
python3 scripts/importers/import_skin.py --update-lesion 3 --app-score mittel --app-name Skinscreener
python3 scripts/importers/import_skin.py --update-lesion 3 --derm-assessment "Compound-Naevus, unauffaellig" --derm-date 2026-08-15
# VLM-Analyse ist ein separater Schritt: scripts/analysis/manual/analyse_skin.py --analyse
python3 scripts/importers/import_skin.py --list-lesions
```
