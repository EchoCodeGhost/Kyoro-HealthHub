## Why

No importer currently exists for Sun-a-ware (a UV-exposure tracker, used
as a vitamin-D-synthesis proxy). Adding one would make sun-exposure/
vitamin-D-proxy data available alongside the existing data sources (e.g.
for correlations with mood, energy, seasonal patterns).

**Note — blocker:** The device's export format is currently unknown. No
sample file exists. This change primarily serves as a **demo of the
importer-pattern workflow** (see
`openspec/specs/importer-pattern/spec.md`) and makes the blocker
explicitly visible — it should not move into implementation before the
first task (obtain a sample file) is done.

## What Changes

- New importer `scripts/importers/import_sun_a_ware.py` following the
  importer pattern (`run(conn, data_path, lang='de', person=None) ->
  ImportResult`).
- Registration in the `IMPORTERS` list in `scripts/import_all.py`.
- Precondition that must be met before any implementation: a real
  sample export file from the device, to clarify format, field names,
  and data structure.

## Capabilities

### New Capabilities
- `sun-a-ware-import`: Import of sun-exposure/vitamin-D-proxy data from
  the Sun-a-ware device into `measurements` (EAV), once the export
  format is known.

### Modified Capabilities
(none)

## Impact

- Affects `scripts/import_all.py` (new line in `IMPORTERS`).
- No impact on existing importers or schema — follows the established
  EAV pattern in `measurements`, presumably a new `metric` value (e.g.
  `uv_exposure` or `vitamin_d_proxy`, exact name only determinable after
  reviewing the sample file).
- **Blocked** until a sample export file is available — see `tasks.md`.
