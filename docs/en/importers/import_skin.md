# import_skin.py — Hautlaesionen importieren (source-agnostisch)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_skin.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports skin lesion photos and metadata from various sources into medicine.db

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Accepts images from smartphone camera, screenshots (Skinscreener/SkinVision), DSLR, or other JPEG/PNG sources. Each lesion receives a persistent ID in skin_lesions. Follow-up photos are linked via --lesion-id. Photos are stored in imaging_files with reference to the lesion. Clinical outcomes (dermatologist assessment, operation, histology) can be added via --update-lesion. Images are automatically normalized to JPEG and stored with anonymized filenames.

## Data flow

- **Reads:** `Bilddateien`, `(JPEG/PNG/HEIC/MOV)`, `aus`, `Inbox-Verzeichnissen`, `oder`, `als`, `Argument`
- **Writes:** `skin_lesions, imaging_files, user_context, import_log`

## Limitations

Depends on image quality and metadata availability. No automatic image analysis. Histology results must be entered manually.

## Usage

```bash
python3 scripts/importers/import_skin.py foto.jpg --location "Ruecken links, 5cm unterhalb Schulterblatt" --date 2026-06-28 --source camera
python3 scripts/importers/import_skin.py foto2.jpg --lesion-id 3
python3 scripts/importers/import_skin.py --update-lesion 3 --app-score mittel --app-name Skinscreener
python3 scripts/importers/import_skin.py --update-lesion 3 --derm-assessment "Compound-Naevus, unauffaellig" --derm-date 2026-08-15
# VLM-Analyse ist ein separater Schritt: scripts/analysis/manual/analyse_skin.py --analyse
python3 scripts/importers/import_skin.py --list-lesions
```
