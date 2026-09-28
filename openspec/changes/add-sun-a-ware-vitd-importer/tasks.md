## 1. Resolve blocker (must happen first)

- [ ] 1.1 Obtain a sample export file from the Sun-a-ware device/app (CSV/JSON/screenshot — format currently unknown)
- [ ] 1.2 Document format, field names, and units from the sample file (either in this change or in a local plan document via the `plan-importer` skill)

## 2. Implementation (only after task 1)

- [ ] 2.1 Create `scripts/importers/import_sun_a_ware.py` with `run(conn, data_path, lang='de', person=None) -> ImportResult`
- [ ] 2.2 Settle on a `metric` name for `measurements` (e.g. `uv_exposure` or `vitamin_d_proxy`, depending on the actual fields)
- [ ] 2.3 Implement `INSERT OR IGNORE`, `resolve_person()`, `resolve_timezone()`, `log_import()` before commit
- [ ] 2.4 Register in the `IMPORTERS` list in `scripts/import_all.py`

## 3. Review

- [ ] 3.1 Check against `openspec/specs/importer-pattern/spec.md` (`review-importer` skill)
