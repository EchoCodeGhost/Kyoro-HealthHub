## MODIFIED Requirements

### Requirement: GPS capture before discard
If an image file (including an image embedded in a PDF) contains GPS
coordinates in its metadata, the importer SHALL resolve the location
policy for its importer name and file type (see the `location-privacy`
capability) before stripping. If the policy allows storing a location, the
importer SHALL write it via the location registry at the configured
precision, together with the original-file and stored-file hashes; if the
policy is `store: "none"` or there is no entry, the coordinates SHALL be
discarded with the metadata. The importer SHALL NOT write to
`photo_locations`. If a capture date is missing, the GPS finding SHALL NOT
be stored (a location without a date is not usable for exposure/travel
correlation).

#### Scenario: A photo with a complete GPS tag is imported and the policy allows it
- **WHEN** `import_skin` processes a photo with a valid `GPSLatitude` +
  `GPSLongitude` and a capture date, and the policy for `import_skin` is
  precision 2
- **THEN** the position rounded to 2 decimal places is stored in the
  location registry with date, source, file hashes, a reference to the
  `imaging_files` row and person, before the photo is stripped of its GPS
  tag

#### Scenario: An image importer whose policy forbids storing locations
- **WHEN** `import_fundus` or `import_lab_results` processes an image or a
  PDF-embedded image with GPS coordinates, and the policy is
  `store: "none"`
- **THEN** the GPS tag is stripped and no registry entry is written

#### Scenario: A photo with GPS but no capture date
- **WHEN** an importer processes a photo with GPS coordinates but no
  usable capture date
- **THEN** no registry entry is written (the date is a required field for
  later correlation analysis)

### Requirement: Location data only appears in analyses where medically relevant
Location data derived from photos SHALL NOT automatically appear in
image-related analysis reports (e.g. skin-lesion or fundus VLM analysis)
or in prompts sent to a remote provider. It SHALL only be consumed by
analyses for which the location is medically relevant (e.g.
travel/exposure correlation), and only through the location registry's
output function at the level that analysis is allowed in
`location_privacy.json`.

#### Scenario: A skin-lesion analysis report is generated
- **WHEN** `analyse_skin.py` (or an equivalent analysis script) generates a
  report for a lesion whose photo has a registry entry
- **THEN** the report and any prompt sent for it contain no GPS
  coordinates or location data, unless the script is explicitly allowed a
  location level in `location_privacy.json` for exposure/travel
  correlation
