## Why

`region_of()` maps coordinates to the nearest German state capital inside a
rough box around Germany: Würzburg becomes Baden-Württemberg, Basel becomes
Saarland, and anything outside Germany is just "Abroad". The region level of
the location policy is therefore wrong in Germany and useless elsewhere, and
`store: "region"` is not implemented at all. At the same time, coordinates
go to several external services (weather, air quality, pollen, reverse
geocoding) at ~1 km precision, finer than most of these services need, and
Google Pollen is called with a personal API key whenever a key is present.

## What Changes

- Region becomes an ISO 3166 code worldwide (`DE-BY`, `ES-GC`, `US-HI`;
  country code when no subdivision applies; `XX` when unknown), looked up
  offline from bundled Natural Earth admin-1 boundaries. Display names come
  from the same data in German or English.
- The registry stores the region per entry, computed before coarsening;
  `store: "region"` stores the region without coordinates.
- One outbound precision for all non-LLM services, default 1 decimal place
  (~11 km). A second setting with default 2 applies only where a call needs
  a place name (reverse geocoding at town level).
- Google Pollen is off by default and needs an explicit opt-in in
  `location_privacy.json`, in addition to the API key. **BREAKING** for
  installations that rely on the key alone.
- The DWD pollen region for the home location is chosen once in the
  config instead of being guessed from approximate centres; the guess
  remains only as a fallback for stays away from home.
- Outbreak, endemic and FSME matching keeps the existing point-plus-radius
  approach; its limits are documented.
- Documentation lists every external service with what it receives.

## Capabilities

### New Capabilities
- `location-region`: ISO-coded region lookup, region column in the
  registry, `store: "region"`, display names.
- `location-outbound`: precision for external services, opt-in for
  services tied to a personal key, home pollen region by configuration,
  disclosure of external services.

### Modified Capabilities
- None in `openspec/specs/`. The pending change `location-privacy-registry`
  defines the region level and `external_api.precision`; this change
  builds on it and refines both.

## Impact

- `scripts/modules/location_store.py` (`region_of`, `region_name`,
  `record`, `for_prompt`, `for_external_api`)
- `scripts/utils/create_location_schema.py` (region column, nullable
  lat/lon, unique index)
- New data file with simplified boundaries (~1.3 MB, gzip) and a build tool
  under `tools/`
- New dependency `shapely` (BSD)
- External callers: `fetch_daily`, `import_airquality`,
  `import_dwd_brightsky`, `import_aemet`, `import_pollen_google`,
  `import_pollen_dwd`, `import_travel_environment`, `weather_lookup`,
  `track_location`, `geocode_stays`, `analyse_pathogen_exposure`,
  `analyse_sport_environment`
- `export_health.py` (region columns), `templates/location_privacy.example.json`,
  `templates/health_config.example.json`; docs in English and German:
  `PRIVACY_ARCHITECTURE.md` (+ new `_DE`), `PII_Anonymization(_DE).md`,
  `SETUP(_DE).md`
