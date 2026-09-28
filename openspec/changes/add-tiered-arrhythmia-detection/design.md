## Context

The user asked for an OpenSpec change covering both general arrhythmia
detection and AFib detection, and supplied a detailed technical survey
of the design space (RR-interval methods, QRS/morphology methods, ML
approaches, PPG-specific limitations). This document records which parts
of that survey are adopted now, which are deferred, and why — following
the same pattern as `add-tamper-evident-audit-log/design.md` (evaluate
the full option space, adopt the lightest solution that meets the actual
need, record the reasoning for the rejected heavier options so it
doesn't have to be re-litigated later).

## Options considered

### A) RR-interval / Poincaré-plot features (adopted, phase 1)

Tateno & Glass (2001), CVRR, sample entropy, Poincaré SD1/SD2, turning
point ratio — all computable from `ppi_raw`/`ppi_windows` alone, no new
data source. This is what `compute_arrhythmia.py` already does for
AFib; extending the same feature family to a universal irregularity
score and to ectopic-beat detection (short-RR-then-compensatory-pause)
is a natural, low-risk extension of existing, already-calibrated code
rather than a new subsystem.

**Decision: adopt for all three new tiers (universal score, AFib
signal-type labelling, ectopy screening).**

### B) QRS/morphology-based analysis (deferred)

Real ECG waveform analysis (QRS width, P-wave morphology, beat
prematurity from waveform shape rather than just interval timing) can in
principle distinguish far more rhythm types (PACs vs PVCs, AV block,
atrial flutter) than interval-only methods. This project does have two
raw-ECG sources today: Apple Watch's 30-second snapshot ECG and the
ECG Logger's long-term recordings (see `compute_arrhythmia.py`'s source
hierarchy).

**Decision: out of scope for this change.** Waveform-level QRS/P-wave
detection is a materially different engineering task from the
interval-statistics methods every other compute script in this project
uses (it needs a QRS detector, e.g. Pan-Tompkins — already implemented
in `modules/ecg_signal.py` for a different purpose — plus morphology
feature extraction and per-beat classification). Worth a dedicated
follow-up change once the RR-interval tiers in this change are shipped
and validated, not bundled in with them.

### C) Machine-learning classifiers (rejected for now)

PhysioNet/CinC Challenge 2017 (AF classification) and 2020 (multi-class
arrhythmia classification) both demonstrate that CNN/CNN-LSTM models
trained on MIT-BIH-style datasets outperform classical feature methods
on held-out data from the *same* population and device type.

**Rejected for this project specifically:**
- **Generalisation risk.** A model trained on MIT-BIH (clinical Holter
  ECG, specific demographic) has no established transfer guarantee to
  consumer PPG or a single specific person's physiology — the opposite
  of every other calibrated component in this project, which either
  cites a published closed-form method or documents its own explicit
  single-person calibration (see `compute_orthostatic_detection.py`,
  `compute_pem.py` for the pattern this project already follows).
- **Opacity.** A CNN's decision boundary can't be cited the way
  `HR_JUMP_MIN = 15  # Sheldon 2015, not directly, see @method` can —
  this project's whole documentation convention (`@refs`, `@method`,
  `@limits` on every compute script) assumes a method a reader can
  trace to a published source or an explicit calibration, not a learned
  weight matrix.
- **Maintenance burden.** No existing ML training/serving infrastructure
  in this project (LLM calls are the only ML-adjacent capability, and
  those are opt-in, externally hosted, and never used for numeric
  clinical scoring). Adding a trained-model pipeline is a new category
  of infrastructure, not an incremental extension.

**Not rejected permanently** — if a future change specifically wants to
explore this, it should be its own proposal with its own validation plan
(train/test split methodology, generalisation testing against this
project's own data), not folded into this one.

### D) Multi-sensor fusion (accelerometer/EDA/skin temp for artefact rejection) (deferred)

Useful in principle (movement artefacts are already a known confound
across several compute scripts tonight, e.g. `compute_orthostatic_detection.py`'s
step-count confirmation window). Not adopted as part of *this* change
because it's an artefact-rejection improvement orthogonal to adding new
detection tiers — worth its own follow-up once the new tiers exist and
their false-positive rate from movement artefacts is actually measured.

## Device-capability gating (the core new architectural decision)

The universal irregularity score is device-agnostic (works from any
`ppi_raw` source). AFib screening already works across chest-strap and
PPG sources today, but has never labelled *which* it ran on. The new
ectopic-beat tier is the first tier in this project that is
**structurally unavailable** on PPG-only sources — this is a genuine
capability gap (PPG's mechanical pulse-wave signal doesn't carry
beat-prematurity information reliably enough for the compensatory-pause
pattern to be trustworthy), not a conservative default that could be
loosened later with better tuning.

Gating decision: derive availability from `device_registry.sensor_type`
(`chest_strap` → all tiers; `optical_wrist`/`optical_wrist_gps` → universal
score + AFib screening only, ectopy tier not computed at all rather than
computed-but-hidden) — matching this project's existing device-agnostic,
registry-driven pattern (`cross-cutting-conventions` spec) rather than a
per-script hardcoded device list.

## Non-diagnostic framing

The clinical-review flag is intentionally binary and non-specific
("persistent irregular rhythm detected, medical evaluation recommended")
rather than naming a suspected condition — matching `docs/ETHICS.md`'s
existing boundary against this project outputting anything that reads as
a diagnosis.
