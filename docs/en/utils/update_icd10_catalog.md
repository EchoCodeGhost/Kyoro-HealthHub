# update_icd10_catalog.py — ICD-10-GM-Katalog lokal installieren/aktualisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/update_icd10_catalog.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Installs or updates the local ICD-10-GM catalog (data/reference/icd10gm/) that scripts/modules/icd10_catalog.py uses for ICD code validation and the code↔text plausibility check. The catalog is NOT bundled in the repo (see icd10_catalog.py's module docstring @limits) -- every installation must run this download step itself once.

## Relevance

Keeps the local ICD-10-GM catalog current, essential so the code↔text plausibility check doesn't validate against a stale year's version

## Method

Three modes: --check only queries the BfArM downloads page and compares the newest year found there against the locally installed one (from the filename in data/reference/icd10gm/), WITHOUT downloading anything or accepting any terms. --download performs the actual download: BfArM requires EACH USER to explicitly accept a usage contract (download conditions) -- this script therefore shows a short summary of the terms before every download and requires explicit confirmation (interactively, or via --accept-terms for non-interactive runs), NEVER an automatic/on-behalf-of acceptance. The current download URL is NOT hardcoded to one year -- it's read fresh from the BfArM downloads page on every run (regex for "icd10gmYYYYsyst-meta_zip.html"), so --download keeps working next year without a code change, as long as BfArM keeps the URL scheme. --from-zip <path> skips the download entirely: for users who already downloaded the ZIP manually in their browser (and accepted the terms there). In every case, only Klassifikationsdateien/icd10gmYYYYsyst_kodes.txt is extracted from the ZIP (the code+title list, see icd10_catalog.py) -- everything else (mortality lists, PDFs, the alphabetical index) is discarded to keep data/reference/ icd10gm/ small; that one file is kept UNCHANGED (no text rewriting -- see the no-alteration clause, § 62 UrhG, in BfArM's download conditions).

## Data flow

- **Reads:** `https://www.bfarm.de/.../Kodiersysteme/Services/Downloads/`, `(online`, `nur`, `--check`, `und`, `--download)`
- **Writes:**

  ```
  data/reference/icd10gm/icd10gmJJJJsyst_kodes.txt (unveränderte
  Kopie aus der BfArM-ZIP); data/reference/icd10gm/NOTICE.txt
  (Pflicht-Quellenangabe nach § 63 UrhG, siehe
  Downloadbedingungen-Anhang)
  ```

## Limitations

BfArM's page layout/URL scheme can change -- this then fails with a clear error message (no guarantee against needing a code update). Does NOT auto-check for ICD-11 -- the BfArM downloads page currently only offers ICD-10-GM/OPS/ICD-10-WHO/ Alpha-ID-SE/ICD-O-3/ICF; --check only prints a static note about this, not a live signal of whether/when Germany switches to ICD-11 for billing (as of this project, not an automatically observable fact).

## Usage

```bash
python3 update_icd10_catalog.py --check
python3 update_icd10_catalog.py --download --accept-terms
python3 update_icd10_catalog.py --from-zip ~/Downloads/icd10gm2026syst-meta.zip
```
