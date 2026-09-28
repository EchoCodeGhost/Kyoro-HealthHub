# DRV-Reha-Kliniken → HTML-Download

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/drv_kliniken_download.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Downloads the clinic location overview of the German pension insurance (drv-reha.de/kliniken) as an HTML file.

## Relevance

Fetches raw data for rehabilitation planning, no direct relevance to personal health data

## Method

Fetches the page via wget and stores it unchanged under imports/drv-kliniken/kliniken. Contains no parsing logic — turning the clinic list into structured data is the job of a downstream importer.

## Data flow

- **Reads:** `https://www.drv-reha.de/kliniken`, `(online)`
- **Writes:** `imports/drv-kliniken/kliniken (Roh-HTML)`

## Limitations

Requires a working wget installation and internet access. Does not detect layout changes on the target page.

## Usage

```bash
python3 drv_kliniken_download.py
python3 drv_kliniken_download.py --help
```
