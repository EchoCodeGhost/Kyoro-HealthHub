## Context

Three image-consuming code paths existed before today, built at different
times: `import_skin.py` (routes through `imaging_utils.normalize_to_jpeg`/
`strip_exif_pii`), `import_fundus.py` (DICOM path uses `dicom_utils.strip_pii`,
but the direct-JPEG path used a raw `shutil.copy2` with no stripping at
all), and `scrub_pdf_metadata.py` (strips embedded PDF images via
`imaging_utils.strip_exif_pii`). Only the DICOM and skin paths were
actually safe; the fundus JPEG path was a real, shipped gap. Today's
session also added RAW format support (pyexiv2 metadata-only stripping +
rawpy preview decode) and GPS-before-discard capture into a new
`photo_locations` table — both implemented in `imaging_utils.py` and
wired into `import_skin.py`/`scrub_pdf_metadata.py`, but not yet
`import_fundus.py`'s DICOM path (which has its own, independently correct
`strip_pii()` and doesn't currently extract GPS at all, since DICOM rarely
carries EXIF GPS — mobile phone JPEGs are the actual GPS-bearing case).

## Goals / Non-Goals

**Goals:**
- Establish a single required pattern — route through `imaging_utils.py`
  (or an equivalent, equally-audited stripping path) — that any current or
  future image-consuming importer must follow, closing the class of bug
  found in `import_fundus.py` today.
- Document GPS-before-discard and RAW dual-file handling as requirements,
  not just as `import_skin.py`'s implementation detail.
- Document the constraint (explicit user instruction) that captured
  location data must not automatically appear in per-image analysis
  output — it is scoped to `photo_locations` and consumed only by
  analyses that actually need it (e.g. travel/exposure correlation).

**Non-Goals:**
- Not retrofitting DICOM's `dicom_utils.strip_pii()` into
  `imaging_utils.py` — DICOM has its own well-established, separately
  audited PII model (patient name, institution, etc. as DICOM tags, not
  EXIF) and stays a parallel, equally-valid stripping path for that format
  family.
- Not adding GPS extraction to DICOM-sourced fundus images in this change
  — DICOM fundus captures are clinical-device output, not phone/camera
  JPEGs, and essentially never carry EXIF GPS; if a future need arises
  this would be a small, separate addition.
- Not building automated CI enforcement (e.g. a static check that greps
  for bespoke `shutil.copy2`/`Image.open` patterns outside
  `imaging_utils.py`) — this spec is the review standard; tooling to
  automatically enforce it is a possible later change.

## Decisions

- **One spec, two stripping paths recognized as compliant**:
  `imaging_utils.py`'s EXIF/RAW path for photos, and `dicom_utils.py`'s
  `strip_pii()` for DICOM — both count as satisfying "mandatory PII
  stripping," since DICOM's metadata model is genuinely different from
  EXIF and doesn't benefit from being forced through the same code path.
- **GPS lives in a separate table (`photo_locations`), not inline on
  `imaging_files`**: keeps location data out of every default query
  against imaging tables, matching the explicit instruction that it
  should only surface where medically relevant, not leak into every skin-
  lesion or fundus report by default.
- **RAW keeps both files (Weg 2)** rather than only decoding to JPEG: for
  skin-lesion documentation specifically, the RAW original's exposure/
  white-balance flexibility can matter for later re-examination, so the
  spec requires preserving it (metadata-stripped) alongside a JPEG preview
  for immediate viewing/VLM use, rather than discarding it after decode.

## Risks / Trade-offs

- [Risk] A future image importer could still bypass `imaging_utils.py` by
  writing its own ad-hoc file-copy code, exactly as `import_fundus.py` did
  — this spec documents the requirement but doesn't technically prevent
  it → Mitigation: none automated yet; relies on code review against this
  spec (see Non-Goals — CI enforcement is a possible follow-up).
- [Risk] RAW format coverage (`RAW_EXTENSIONS` in `imaging_utils.py`) is a
  fixed list (NEF, CR2, CR3, ARW, DNG, RAF, ORF, RW2, PEF, SRW); a camera
  producing an unlisted RAW extension would silently fall outside
  `is_supported()` → Mitigation: `process_raw()`/`strip_raw_metadata()`
  are format-agnostic (pyexiv2/rawpy handle any format their underlying
  libraries support), so extending `RAW_EXTENSIONS` for a new format is a
  one-line change, not a new code path.
