# Security Policy

> **Deutsche Version:** [SECURITY_DE.md](SECURITY_DE.md)

Kyoro-HealthHub is a local-first personal health data pipeline (see
[README.md](../README.md)). There is no central server: the attack surface
that matters most here is local — decrypted temporary files, exposed local
services (e.g. the Datasette browser), path traversal in importers/exporters,
and privacy/pseudonymization failures — not a hosted backend.

## Supported versions

This project does not use versioned releases (see the "Versioning and
changelogs" convention in [CONTRIBUTING.md](CONTRIBUTING.md)). Only the
current `main` branch is maintained; please report issues against the latest
commit.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting instead of a public
issue: go to the repository's **Security** tab → **Report a vulnerability**.
This opens a private advisory visible only to maintainers until it's
resolved.

> **Currently unavailable:** this repository is private, and GitHub only
> offers private vulnerability reporting on private repos with GitHub
> Advanced Security enabled (not the case here — see details below). The
> **Report a vulnerability** button will not appear in the Security tab
> until the repository is public. Until then, please use the fallback
> below.

**Fallback while unavailable:** open a regular issue with as few technical
details as possible and ask for a private channel to share the rest.

## Scope

In scope:
- Local data exposure (world-readable temp files, services bound to
  `0.0.0.0` that should be `localhost`-only, decrypted database artifacts
  left on disk)
- Pseudonymization/anonymization bypasses (device IDs, person IDs, or other
  identifiers that should never appear in plaintext leaking anyway)
- SQL injection, path traversal, or command injection in importers,
  exporters, or query tools
- Secrets (API keys, DB encryption keys) logged, committed, or otherwise
  exposed
- Privacy-rule violations in the *pipeline's own behavior* (as opposed to
  content review of docstrings/comments, which `check_compliance.py` and
  `check_source_privacy.py` already cover — see CONTRIBUTING.md)

Out of scope:
- Security of third-party device APIs or cloud services this project
  integrates with (Polar, Oura, Garmin, etc.) — report those to the vendor
- General bugs without a security/privacy impact — use a regular issue
- Missing features or hardening suggestions without a concrete exploitable
  scenario — open a regular issue or discussion instead

## What to expect

This is an individually maintained, non-commercial project — response times
are best-effort, not covered by an SLA. Confirmed vulnerabilities will be
fixed and credited (unless you prefer to stay anonymous) in the fix's commit
message.

## Known dependency advisories (accepted, not actionable)

**`setuptools` — CVE-2026-59890 / GHSA-h35f-9h28-mq5c** (`MANIFEST.in`
exclusion bypass via NFC/NFD Unicode normalization mismatch when building an
sdist on macOS APFS/HFS+): this repository has no `setup.py`,
`pyproject.toml`, or `MANIFEST.in`. It is never built or published as its
own sdist, so the vulnerable code path — a maintainer publishing a package
whose `MANIFEST.in` exclusions get silently bypassed — does not apply here.
`setuptools` appears in `requirements-lock.txt` only as a transitive build
dependency for third-party packages installed via `pip`.

The pin also can't be bumped past the fixed version right now regardless:
it is deliberately held below `neurokit2`'s own upper bound
(`setuptools<82.0.0`, from `neurokit2`'s package metadata, not this
project's choice) to keep `pip install -r requirements-lock.txt`
resolvable. Revisit if/when a `neurokit2` release lifts that ceiling.

## A note on the private-repository period

GitHub's private vulnerability reporting requires GitHub Advanced Security
on private repositories, which isn't enabled here. It becomes available at
no extra cost once this repository is public — until then, please use the
regular-issue fallback above.
