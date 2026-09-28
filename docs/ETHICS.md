# Ethical Principles

> **Deutsche Version:** [ETHICS_DE.md](ETHICS_DE.md)

Kyoro-HealthHub has grown into more than a personal data tool.

People with complex, chronic, or medically unexplained conditions are treated by specialists who each see their fragment. Often no one is in a position to connect the mosaic. Kyoro can support that role: it connects wearable data, lab results, symptoms, and clinical events into a single longitudinal timeline — making the invisible and diffuse visible: patterns that easily go unnoticed on their own, but together, across years, specialties, family members, and generations, form a clear picture.

A related structural issue: once a diagnosis is on record, it isn't always revisited, even as the science moves on. A persistent, tamper-evident timeline is therefore not merely a practical tool — it supports an ethical stance: a person's past remains readable, revisable, and theirs.

The platform now spans personal tracking, forensic documentation, preparation for clinical conversations, and self-directed research. These principles apply to all these contexts — personal, clinical, and research. They are grounded in human dignity, fundamental rights, and the lived reality of people with chronic illness or disability.

---

## Mission

The core purpose of this project is **empowerment**.

Every person has the right to understand their own body and their own health
data — regardless of whether they live with a disability or chronic illness,
regardless of gender identity, age, educational background, income, digital
literacy, native language, or any other characteristic. This right is not a
privilege for the technically skilled or the medically informed. It belongs to
everyone.

This software exists to make that right real. For people living with
chronic illness, disability, or medically unexplained symptoms, access to their
own data can mean the difference between being heard and being dismissed —
between finding patterns that lead to better care and years of fruitless
searching.

Kyoro-HealthHub exists to give people:

- **Self-determination** — the ability to analyse their own health data without
  depending on institutions, insurers, or commercial platforms
- **Informed agency** — a solid, evidence-based foundation for conversations
  with clinicians, for pacing decisions, for understanding what helps and what
  harms
- **Dignity in data** — ownership and control over intimate information, without
  it being monetised, surveilled, or used against them

Everything in this project — the architecture, the license, the security
requirements, the ethical principles below — serves this mission. When in
doubt, ask: *does this make it easier or harder for a person to understand and
govern their own health?*

**Technology must serve people — not the other way around.**
This means: no dark patterns, no lock-in, no extractive design. The software
works for the person running it and answers to that person alone — and aims
to leave them more capable and informed than before, though that outcome
depends on the person and situation and cannot be guaranteed by the software
alone.

*Kyoro does not diagnose. It connects fragments that specialists never saw together — and gives them a direction to look. The goal: more quality of life for people who have been searching too long.*

---

## 1. Human dignity and fundamental rights

Every person whose data this software touches has inalienable dignity. Health
data is among the most intimate information that exists. Its misuse can cause
irreversible harm — loss of employment, insurance, housing, custody, or safety.

This software is built on the following non-negotiable foundations:

- **Dignity** — no person may be reduced to their diagnoses, biomarkers, or
  data points
- **Autonomy** — individuals decide what happens to their own health data, always
- **Non-discrimination** — health data must never be used to disadvantage a
  person on grounds of illness, disability, gender identity, sexual orientation,
  ethnicity, or any other protected characteristic
- **Proportionality** — collect and process only what is necessary for the
  stated purpose

---

## 2. Rights of people with chronic illness and disability

The following principles are not optional courtesies — they reflect rights
under the UN Convention on the Rights of Persons with Disabilities (UN CRPD)
and equivalent national law:

- **Believe the patient.** Contributions, issues, and discussions must not
  dismiss, minimise, or pathologise self-reported symptoms, fatigue, or
  cognitive difficulties. "Unexplained" does not mean "imagined".
- **No paternalism.** People with chronic illness are experts on their own
  bodies. This tool supports their self-determination; it does not override it.
- **Accessibility as a goal, not a promise.** New features should try, where
  possible, not to assume full physical or cognitive capacity in the user.
  This is an aspiration, not something already delivered: the project is
  mostly command-line scripts today and currently assumes a degree of
  technical familiarity; not every interface is usable without effort in a
  state of cognitive fatigue.
- **Energy awareness as an aim.** We try to avoid contributions that require
  exhausting multi-step manual workflows without good reason — again an aim,
  not a guarantee.

---

## 3. LGBTQ+ and gender-diverse users

Health data can reveal or imply sexual orientation, gender identity, transition
history, reproductive choices, and family structures — information that can
endanger users in certain legal or social contexts.

- Gender identity and sexual orientation are **never** to be inferred,
  stored, or exposed beyond what the user explicitly provides
- Hormone levels, surgical history, and reproductive data are treated as
  maximally sensitive; they must not appear in logs, error output, or exports
  without explicit user configuration
- Default export profiles must not include fields that could out a trans or
  intersex person to a third party (e.g. a treating physician in a different
  specialty)
- The software must never assume binary gender for any health calculation;
  all formulas that depend on biological sex must accept explicit user input
  and document their assumptions

---

## 4. Prohibited uses

The following uses are explicitly prohibited regardless of technical possibility:

- Profiling individuals for insurance underwriting, employer screening,
  credit decisions, or law enforcement
- Surveillance of employees, patients, family members, or any person without
  their knowledge and freely given consent
- Training commercial AI models on personal health data without explicit,
  specific, and revocable consent
- Exposing an individual's health, gender, or identity data to parties they
  have not personally authorised
- Using health data to discriminate on grounds of disability, chronic illness,
  gender identity, sexual orientation, or any other protected characteristic

See `openspec/specs/ethics-enforcement/` for the formal, reviewable
requirements and scenarios derived from this list.

---

## 5. Research with human subjects

If you use this software as part of a study involving data from other people:

- Obtain ethics committee / IRB approval **before** data collection
- Ensure informed consent covers the specific analyses you intend to run,
  including any AI/LLM processing
- Anonymise or pseudonymise data before it leaves the data subject's control
- Follow applicable law (GDPR Art. 9, HIPAA, or equivalent)
- Do not re-identify or attempt to re-identify pseudonymised data

Personal use and self-research are exempt from IRB requirements, but consent
and anonymisation principles remain good practice.

---

## 6. AI and LLM outputs are not clinical decisions

LLM outputs generated by this software:

- are not validated diagnostic tools and carry no regulatory approval
- can be factually wrong, incomplete, or confidently misleading
- must not be presented to patients or caregivers as medical advice
- must not replace clinical judgment or delay appropriate care
- must be clearly labelled as AI-generated wherever they are displayed
  (formal requirement: `openspec/specs/ethics-enforcement/` — previously
  enforced only by manual PR review, which in practice left it unmet across
  most analysis scripts despite existing on paper; `modules/llm.py`'s
  `call_llm()` now labels its output by default, and
  `scripts/utils/check_ai_labeling.py` (run via `tools/qa_check.py` in CI)
  enforces it automatically instead of relying on review alone)
- carry AI-specific risks the end user should keep in mind: hallucination
  (confident but fabricated content), sycophancy/confirmation bias (a model
  tends to agree with the user's own hypothesis rather than challenge it —
  a particular risk when a user approaches it with a strong pre-existing
  suspicion), automation bias (trusting a data-derived output more than
  warranted simply because it is computed), a training-data cutoff that
  may miss current medical guidelines, non-deterministic answers across
  runs/models, and correlation in wearable/lab data being described as if
  it were causation
- should be researched and checked for plausibility by the private end user
  themselves — against other sources or their own records — before being
  brought to a doctor unchecked or acted upon; this check matters even when
  an output sounds confident and coherent

Always involve a qualified clinician before acting on any output from this tool.

**Calibration and grounding:** motivated by Muneer et al. (2026), *Foundation
models in biomedical imaging: turning hype into reality*, Nature Biomedical Engineering,
10:1557-1575, doi:10.1038/s41551-026-01762-z (REAL-FM framework), a project-wide gap was found
and closed: `modules/llm.py`'s `call_llm()` now appends a confidence/grounding instruction to
every LLM prompt by default (`require_grounding=True`), requiring the model to mark a confidence
level per claim and trace it to a concrete data point, or explicitly label it as its own
assessment rather than fact. `analyse_synthesis.py`'s multi-model panel additionally has its
chair cross-check each panel opinion against its own independently-formed notes and flag
unsupported claims as possibly hallucinated.

This was spot-checked, not formally validated: a single real run showed the instruction being
followed consistently (every claim tagged); a repeat run on the same data reached the same
clinical conclusion with different wording (expected non-determinism, already listed above); a
bias probe — the identical HRV report, varying only a patient-context line (name/gender/trans
status: a German woman, a Middle Eastern woman, a trans woman, a German man, a Latin American
man, an Asian man, an Asian woman, an African man, an African woman, a trans man — ten variants
total) — showed the same core recommendation ("further cardiology workup warranted, observation
alone is insufficient") in every single variant, with no pattern in the reported confidence level
correlating to any demographic marker. The same probe (three variants each) was repeated on two
further domains: an ME/CFS activity-pacing report and a reproductive-health cycle report, the
latter including a trans man variant specifically — one of the scenarios with documented
real-world risk of clinician dismissal. Same result: identical clinical content, tone, and depth
across variants, including respectful, correctly gendered address for the trans man case. None of
this is a systematic audit: three clinical scenarios, one model, one point in time, a patient-
context line as the only manipulated variable — treat it as a
documented spot-check, not a validated guarantee of calibration or fairness.

A separate spot-check probed robustness against difficult inputs rather than bias: the same HRV
system prompt was given three synthetic, deliberately awkward reports — a single data point with
no trend to describe, five months of data with one month replaced by a physiologically impossible
value (RMSSD in the hundreds of milliseconds, no human value comes close), and a report where HRV
improves sharply right after a severe infection event while also containing a self-contradictory
line ("total decline: -167% (increase)"). In all three, the model did not build a confident
narrative over the problem: it labelled the single data point as "not assessable" rather than
inventing a trend, identified the implausible value as a likely sensor/transmission artefact and
excluded it from its calculations while flagging that the affected month specifically covered the
event date, and called out the arithmetic contradiction explicitly ("mathematically misleading,
this is in fact an increase") instead of silently accepting the report's own wrong framing, also
noting that the timing of the rise did not fit the expected pattern and offering alternative
explanations rather than forcing a causal story. Same caveat as above: three synthetic cases, one
model, one point in time — a spot-check, not proof the model always catches bad input.

**Decision impact tracking:** the spot-checks above cover how the model behaves at the moment of a
single call; they say nothing about whether an output, once acted on, actually helped (REAL-FM's
"Clinical value" axis). That is a personal practice, not code: see
`templates/decision_impact_log_template.md` for the format — recording, for LLM outputs that
meaningfully drove a real decision, what the output claimed, its stated confidence, and (once
known) the actual outcome. The filled-in log itself stays local and private, never in this
repository.

---

## 7. Security and privacy by design

Health data must be protected with the same rigour as the most sensitive
personal information. Minimum requirements for all contributions (formal,
reviewable version: `openspec/specs/ethics-enforcement/`):

**Storage**
- The database must reside locally; no automatic cloud sync or remote backup
  without explicit user action
- Database encryption (`PRAGMA key`) is supported and documented; new
  contributors must not disable or bypass it
- Export files containing health data must not be written to world-readable
  locations

**Access control**
- The FastAPI backend (if deployed) must require authentication; unauthenticated
  endpoints that return health data are a critical vulnerability
- API tokens, database keys, and credentials must never appear in source code,
  logs, or error output — use `~/.config/kyoro/health_config.json` exclusively

**Data minimisation**
- Import only the fields required for the stated analysis; discard or ignore
  surplus fields at import time
- Staging files in `data/staging/` are transient; document retention periods
  and encourage deletion after import

**Logging and audit trails**
- `import_log` records what was imported and when — do not suppress this
- Do not log raw health values in application output; log counts and statuses only

**Dependencies**
- New dependencies must be reviewed for their own data-handling practices;
  libraries that phone home or collect telemetry are not acceptable

**Vulnerability disclosure**
- Security issues must be reported privately to the maintainer before public
  disclosure. Do not open a public issue for an unpatched vulnerability.

---

## Reporting concerns

If you observe a use of this software that violates these principles, or
discover a security or privacy vulnerability, contact the maintainer directly
before disclosing publicly.
