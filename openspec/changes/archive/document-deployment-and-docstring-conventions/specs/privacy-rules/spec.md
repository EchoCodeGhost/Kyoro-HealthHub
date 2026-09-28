## ADDED Requirements

### Requirement: No hardcoded host or user values in deployment artifacts
Deployment artifacts (systemd units, Caddyfiles, and comparable infra
configs) SHALL NOT hardcode a real Linux username or absolute home path.
A generic placeholder token (`CHANGEME`) SHALL be used instead, replaced
at deployment time via a documented one-liner (e.g. `sed
's/CHANGEME/YOURUSER/g'`).

#### Scenario: New systemd unit for a local service
- **WHEN** a contributor adds a new systemd unit file for a project-owned
  service
- **THEN** `User=`, `WorkingDirectory=`, `ExecStart=`, and
  `Environment=HOME=` contain the placeholder `CHANGEME` instead of a
  real username or absolute path, and a comment in the file header
  documents the replacement command for deployment

#### Scenario: Review of an existing deployment file
- **WHEN** an existing deployment file (e.g. `*.service`, `Caddyfile`)
  contains a real username or absolute home path instead of a
  placeholder
- **THEN** this counts as a violation of this requirement and is
  switched to `CHANGEME` before the next merge
