## ADDED Requirements

The hub bridge is optional. The app SHALL work without it; the bridge adds the analyses that do not run on the device, automatic downloads that need a computer, and a backup target.

### Requirement: Bridge runs only allowlisted pipeline jobs
The bridge SHALL start work only through the TUI job runner and manifests, with argument lists and no shell. It SHALL run at most one job at a time.

#### Scenario: Second job requested
- **WHEN** the app starts a job while another one runs
- **THEN** the bridge rejects it with a "job already running" status and the running job continues

#### Scenario: Script outside the allowlist
- **WHEN** a request names a script or flag that is not in the manifests
- **THEN** the bridge rejects it and runs nothing

### Requirement: Autopilot is one job
The autopilot SHALL run inbox import, compute and analyse in the documented order as one job and report each stage in plain language.

#### Scenario: A stage fails
- **WHEN** a stage exits non-zero
- **THEN** later stages do not run, uploaded files stay in the inbox, and the app shows one sentence about what failed and a retry action

### Requirement: Remote LLM use needs consent per run
The bridge SHALL pass flags that send data to a remote LLM provider only when the request carries the user's consent for that run.

#### Scenario: Autopilot without consent
- **WHEN** the autopilot starts without consent
- **THEN** `analyse_all.py` runs without remote LLM commentary

### Requirement: Paired devices only
The bridge SHALL accept requests only from devices paired through a QR code shown on the hub, over TLS, and SHALL allow revoking a device from the hub.

#### Scenario: Unpaired request
- **WHEN** a request arrives without a valid device token
- **THEN** the bridge answers with an authentication error and does nothing else
