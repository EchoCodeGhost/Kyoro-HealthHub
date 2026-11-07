## ADDED Requirements

### Requirement: Inbox routes SymptomTrack JSON exports
`process_inbox.py` SHALL route JSON files whose name starts with `symptomtrack_export` or whose content has a top-level `symptom_entries` key to `import_symptomtrack_export.py`.

#### Scenario: Export from the iPhone app
- **WHEN** `symptomtrack_export_2026-11-07.json` is in `imports/_inbox/`
- **THEN** it is copied to the SymptomTrack export directory and imported, instead of being skipped as an unknown JSON source
