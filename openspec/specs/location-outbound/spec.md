# location-outbound Specification

## Purpose
Defines how much location information leaves the machine for external
non-LLM services (weather, air quality, pollen, geocoding): one coarsening
function with a configurable precision, a finer precision only for place
names, opt-in for services tied to a personal key, a configured DWD pollen
region, local point-plus-radius area matching and a documented list of
external services.
## Requirements
### Requirement: One precision for external services
Every request that sends coordinates to an external non-LLM service SHALL
pass them through `location_store.for_external_api()`, which rounds to
`external_api.precision` (default 1 decimal place). No script SHALL round
coordinates for an external request by other means.

#### Scenario: Daily environment fetch
- **WHEN** `fetch_daily` requests weather, air quality or pollen for the
  home position with the default policy
- **THEN** the request carries the position rounded to 1 decimal place

#### Scenario: Policy file missing
- **WHEN** `location_privacy.json` does not exist
- **THEN** coordinates are rounded to 1 decimal place

### Requirement: Finer precision only for place names
Requests whose purpose is to obtain a town-level place name (reverse
geocoding at town zoom) SHALL use `external_api.place_precision`
(default 2) via `for_external_api(..., place=True)`. All other requests
SHALL use `external_api.precision`.

#### Scenario: Town name for a stay
- **WHEN** `geocode_stays` asks Nominatim for the town of a stay
- **THEN** the request carries the position rounded to 2 decimal places

#### Scenario: Country and state only
- **WHEN** `analyse_pathogen_exposure` asks Nominatim for country and state
- **THEN** the request carries the position rounded to 1 decimal place

### Requirement: Services tied to a personal key are opt-in
A service that identifies the user by a personal API key and receives
coordinates SHALL only be called when it is enabled in
`location_privacy.json` under `external_api.services`. The shipped
template SHALL disable Google Pollen.

#### Scenario: Key present, service not enabled
- **WHEN** `google_pollen_key` is set but `external_api.services.google_pollen`
  is not `true`
- **THEN** no request is sent and the run reports the service as skipped,
  with a hint where to enable it

#### Scenario: Enabled
- **WHEN** the key is set and the service is enabled
- **THEN** the request is sent with coordinates from `for_external_api()`

### Requirement: Home pollen region by configuration
The DWD pollen region for the home location SHALL come from a configured
region ID. Without a configured ID the region SHALL be estimated from the home
coordinates with a warning that names the setting. For stays away from home in
Germany the region SHALL be estimated from the stay location; abroad no DWD
pollen region SHALL be used. The region SHALL be chosen locally; the DWD
download SHALL NOT depend on the location. States without sub-regions in the
DWD file SHALL be addressed by their region ID.

#### Scenario: Configured region
- **WHEN** a DWD pollen region ID is configured
- **THEN** the import uses that region for the home location

#### Scenario: Listing the regions
- **WHEN** the user runs the pollen importer with `--list-regions`
- **THEN** it prints the region IDs and names from the downloaded DWD file, including states without sub-regions

#### Scenario: Nothing configured
- **WHEN** no region ID is configured
- **THEN** the estimate is used and a warning names the setting to fill in, without coordinates

#### Scenario: Travelling in Germany
- **WHEN** the day's location is a stay away from home inside Germany
- **THEN** the region of the stay location is used for that day

#### Scenario: Travelling abroad
- **WHEN** the day's location is outside Germany
- **THEN** no DWD pollen region is used for that day

### Requirement: Area matching stays point plus radius
Matching of stays against outbreak, endemic and FSME reference data SHALL
keep the point-plus-radius method and SHALL state in its `@limits` that
it approximates administrative areas.

#### Scenario: Documented limit
- **WHEN** the docs of the matching scripts are generated
- **THEN** `@limits` states the approximation

### Requirement: Disclosure of external services
The privacy documentation, in English and German, SHALL list every
external service Kyoro contacts with location data: what it receives (coordinates with
precision, area code or place name), whether it is tied to a personal
key, and which setting controls it.

#### Scenario: New external caller
- **WHEN** a script adds a request with location data to a new service
- **THEN** the table in both language versions of the privacy
  documentation lists that service

