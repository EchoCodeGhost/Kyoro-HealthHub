## ADDED Requirements

### Requirement: Mandatory PII stripping via an audited path
Every image-consuming importer SHALL route image files through an
audited PII-stripping path before storing them permanently: for photo
formats (HEIC/HEIF/JPEG/PNG/RAW) `scripts/modules/imaging_utils.py`, for
DICOM `scripts/modules/dicom_utils.py::strip_pii()`. An importer SHALL
NOT implement its own, unaudited copy/load logic (e.g. raw
`shutil.copy2()`) for image files.

#### Scenario: New importer copies an image file without stripping
- **WHEN** a contribution introduces a new or changed image importer
  that stores an image file with `shutil.copy2()` or an equivalent raw
  file copy, without first passing through
  `imaging_utils.strip_exif_pii()`/`strip_raw_metadata()` or
  `dicom_utils.strip_pii()`
- **THEN** this counts as a convention violation that MUST be fixed
  before merge (exactly the finding that was fixed in
  `import_fundus.py`'s direct-JPEG path)

#### Scenario: A known image format is not recognized
- **WHEN** an importer processes an image file with an extension not
  contained in `imaging_utils.SUPPORTED_EXTENSIONS`
- **THEN** either the extension is added to `SUPPORTED_EXTENSIONS`/
  `RAW_EXTENSIONS`, or the importer explicitly rejects the file — it is
  not silently passed through unchecked

### Requirement: GPS capture before discard
If an image file contains GPS coordinates in its EXIF data, the importer
SHALL extract them before stripping and store them via
`imaging_utils.record_photo_location()` (rounded to ~1km, analogous to
`air_quality`/`pollen`/`biometeo`) in `health.db::photo_locations`,
instead of discarding them without a trace. If a capture date is
missing, the GPS finding SHALL NOT be stored (a location without a date
is not usable for exposure/travel correlation).

#### Scenario: A photo with a complete GPS tag is imported
- **WHEN** an importer processes a photo with a valid `GPSLatitude` +
  `GPSLongitude` (and a capture date)
- **THEN** the rounded position is stored with date, source, and person
  in `photo_locations` before the photo is stripped of its GPS tag

#### Scenario: A photo with GPS but no capture date
- **WHEN** an importer processes a photo with GPS coordinates but no
  usable capture date
- **THEN** no `photo_locations` entry is written (the date is a required
  field for later correlation analysis)

### Requirement: RAW files keep both the original AND a preview
For RAW formats (`imaging_utils.RAW_EXTENSIONS`), the importer SHALL
keep both variants: the metadata-stripped RAW original (pixel raster
data unchanged, only metadata stripped) AND a decoded, PII-free JPEG
preview derived from it. The RAW original SHALL NOT be discarded in
favor of the JPEG preview.

#### Scenario: A NEF file is imported for a skin lesion
- **WHEN** a `.nef` file (or another supported RAW format) is imported
  for a skin lesion
- **THEN** both the metadata-stripped RAW and a JPEG preview end up in
  the target directory, both referenced in `imaging_files` (`file_path`
  = JPEG preview, `raw_file_path` = RAW original)

### Requirement: Device-serial pseudonymization applies to RAW too
If a RAW file contains a device serial number in its EXIF data, it SHALL
be pseudonymized (→ `identity.db`) before stripping, analogous to the
existing behavior for JPEG/HEIC in `strip_exif_pii()`.

#### Scenario: A RAW file with BodySerialNumber is stripped
- **WHEN** `strip_raw_metadata()` processes a RAW file whose EXIF
  contains a device serial number (`Exif.Photo.BodySerialNumber` or a
  vendor-specific equivalent)
- **THEN** the serial number is pseudonymized before `clear_exif()`, and
  the mapping is stored in `identity.db`

### Requirement: Location data only appears in analyses where medically relevant
Location data derived from photos (`photo_locations`) SHALL NOT
automatically appear in image-related analysis reports (e.g. skin-lesion
or fundus VLM analysis). It SHALL only be consumed by analyses for which
the location is medically relevant (e.g. travel/exposure correlation).

#### Scenario: A skin-lesion analysis report is generated
- **WHEN** `analyse_skin.py` (or an equivalent analysis script)
  generates a report for a lesion whose photo has a `photo_locations`
  entry
- **THEN** the report contains no GPS coordinates or location data from
  `photo_locations`, unless the report is explicitly intended for
  exposure/travel correlation
