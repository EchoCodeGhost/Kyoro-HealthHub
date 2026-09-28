## Why

Kyoro-HealthHub now has multiple image-consuming importers
(`import_skin.py`, `import_fundus.py`, the PDF-embedded-image path in
`scrub_pdf_metadata.py`) built at different times without a shared,
enforced contract. Auditing `import_fundus.py` while designing today's
GPS-capture feature found a real gap: its direct-JPEG path did a raw
`shutil.copy2()` with the comment "already assumed anonymized" — GPS,
device serial, and other EXIF PII would have been copied verbatim into
the database on import, completely bypassing the DICOM path's
`strip_pii()`. This was found and fixed today, but nothing prevented it
and nothing would catch the same mistake in a future image importer.
Separately, `imaging_utils.py` gained new capabilities today (RAW format
support via pyexiv2/rawpy, GPS extraction into `health.db::photo_locations`
before stripping) that should be a required pattern for any image
importer, not an implementation detail only `import_skin.py` happens to
use.

## What Changes

- New spec `image-importer-pattern` documenting the required shape of any
  Kyoro-HealthHub image-consuming importer: mandatory PII stripping via
  the shared `imaging_utils.py` pipeline (no bespoke copy/load paths), GPS
  capture-before-discard into `photo_locations`, RAW-format handling
  (metadata-only stripping, original preserved alongside a decoded
  preview), and device-serial pseudonymization.
- Also documents the constraint that captured GPS/location data must not
  be surfaced in per-image analysis output unless medically relevant to
  that specific analysis (e.g. travel/exposure correlation) — it lives in
  a separate table precisely so it doesn't leak into unrelated reports
  (skin lesion VLM analysis, fundus VLM analysis) by default.
- No further code changes in this proposal — `import_fundus.py`'s
  bespoke-copy bug, `imaging_utils.py`'s RAW/GPS support, and the
  `photo_locations` table already shipped in the preceding session; this
  documents that shipped behavior as an enforceable spec so the next
  image importer is reviewed against it instead of reinventing the
  pattern (or missing the PII-stripping step, as `import_fundus.py` did).

## Capabilities

### New Capabilities
- `image-importer-pattern`: mandatory EXIF/RAW-metadata stripping via
  `scripts/modules/imaging_utils.py` for every image-consuming importer;
  GPS-before-discard capture into `photo_locations`; RAW format handling
  (original preserved + decoded preview, both metadata-clean); device-
  serial pseudonymization; restriction on surfacing location data outside
  medically relevant analysis contexts.

### Modified Capabilities
(none — this is a new capability; no existing spec's requirements change)

## Impact

- References: `scripts/modules/imaging_utils.py`,
  `scripts/importers/import_skin.py`, `scripts/importers/import_fundus.py`,
  `scripts/utils/scrub_pdf_metadata.py`,
  `scripts/utils/create_medicine_imaging_schema.py` (`raw_file_path`
  column), `scripts/utils/create_schema.py` (`photo_locations` table).
- Serves as the review standard for any future image-consuming importer
  (e.g. a wound-care or dermatoscope-photo importer), preventing a repeat
  of the `import_fundus.py` raw-copy gap found today.
