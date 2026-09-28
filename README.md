# Kyoro-HealthHub

A comprehensive personal health platform: wearable & medical device integration, forensic-grade data pipeline, symptom tracking, clinical analysis, and AI-assisted querying. Privacy-first, privacy by design: your data stays under your control, anonymised and pseudonymised at the source.

> **Deutsche Version:** [README_DE.md](README_DE.md)

---

## Why Kyoro exists

Patients with complex, chronic, or medically unexplained conditions are treated by specialists who each see their fragment. The cardiologist sees the heart. The neurologist sees the nerves. Often no one connects the mosaic.

Kyoro can help with that: years of wearable data, lab results, symptoms, and clinical events become a single longitudinal timeline — making patterns visible that can easily go unnoticed across years and across specialties.

A related structural problem: once a diagnosis is on record, it isn't always revisited, even as the science moves on. A persistent, tamper-evident timeline can make that easier: the past can always be read with new eyes — by you, by your doctor, or by you ten years from now.

There's also a plain economic problem: thoroughly reading years — sometimes decades — of data across specialties, cross-checking sources against each other, and weighing conflicting interpretations takes hours. That time isn't billed and isn't budgeted anywhere, inpatient or outpatient. Kyoro doesn't replace clinical judgment; it does the reading that was never going to happen otherwise, so a clinician's limited time goes toward deciding, not searching.

And, pragmatically: "keep a diary" is standard advice for almost any unclear complaint — food, sleep, symptoms after exertion, each tracked separately. With several things going on at once, that quickly means ten different notebooks or apps for ten different symptom types. Kyoro is also just the more convenient answer to that: one system instead of ten — turning the individual data silos that different apps and devices (e.g. Oura, Kyoro SymptomTrack) create anyway into a single, unified whole, instead of leaving them scattered side by side.

**Four phases:**
1. **Understand** — forensics: what happened, when, why
2. **Treat** — identify the drivers, address them together with clinical guidance
3. **Optimise** — actively manage modifiable risk factors
4. **Longevity** — know your cards, shape the environment accordingly

The data is there. What was missing was a system that reads it.

*Kyoro doesn't diagnose. It gives specialists a direction to look — and ideally gives people more of their quality of life back.*

---

> ## ⚠️ Not a medical device
>
> This software does **NOT** diagnose, treat, cure, or prevent any disease. Its
> outputs — including arrhythmia detection, POTS criterion, PEM correlation,
> SpO2 burden, HRV change-points, ANS status, VLM-based image analysis (e.g. a
> skin lesion or fundus photo), and any LLM-generated text — are heuristic,
> based on consumer-grade sensors, and **MUST NOT** be used for medical
> decisions.
>
> **Results can be wrong in both directions.** A false positive can point you
> toward something that isn't there; a false negative can miss something that
> is. Neither this software nor any AI/LLM component is a doctor — a qualified
> healthcare professional always holds final diagnostic and decision-making
> authority, and must be consulted before you act on any output from this
> software.
>
> **Be prepared for what you might find, and for having to sit with
> uncertainty.** A VLM flagging a mole as high-risk, or any other unsettling
> output, does not resolve itself — only a clinician can. You are responsible
> for the consequences of how you act, or don't act, on this software's
> output. Before running an analysis you suspect might be distressing,
> consider your own capacity to sit with that uncertainty, and involve someone
> you trust if you need to.
>
> **Review of the underlying literature is still pending.** Scientific
> citations throughout this codebase (see the "Evidence tier" annotations in
> `docs/`) were added ad hoc per script, not through a dedicated verification
> pass. This review had been the main thing blocking release for the past
> weeks; it was left open deliberately, so as many people as possible can
> benefit from Kyoro as soon as possible — even with citations that may
> still be imprecise or wrong — rather than delaying release further. It's
> on the project's TODO list and is the next thing being tackled. Treat
> every citation as unverified until that review is done.
>
> See [NOTICE](NOTICE) for the full medical disclaimer and warranty disclaimer.

> ## 🔒 Your data stays on your machine
>
> The database, raw exports, and configuration all live locally on your
> filesystem. This software performs no telemetry and no background uploads.
> External network calls happen only for manufacturer APIs you explicitly
> configure (Garmin/Oura) and optional remote LLM providers (opt-in).
> See [NOTICE](NOTICE) for data sovereignty details.
>
> **Database encryption:** Set `db_key` in `~/.config/kyoro/health_config.json` to
> enable AES-256 encryption via SQLCipher. Without it, `data/health.db` is a
> plain SQLite file readable by anyone with filesystem access.
>
> **Raw exports and backups:** Files in `imports/` are not encrypted by this
> software. Protect the data directory with full-disk or folder encryption
> (LUKS on Linux, FileVault on macOS, BitLocker on Windows). Apply the same
> to any backups.
>
> **External AI providers:** If you use a remote LLM (OpenRouter, Anthropic,
> etc.), only send pseudonymised or anonymised data — never raw exports or
> identifiable personal details. Use providers that offer **Zero Data
> Retention (ZDR)**, explicitly guarantee that **submitted data is not used
> for model training**, and transmit exclusively over encrypted connections
> (TLS). Never share API accounts or credentials between users. Consider
> routing this traffic through a **VPN** as an additional layer — it hides
> your IP address from the provider, on top of (not instead of) the
> pseudonymisation/ZDR precautions above.

---

## What it does

- **All data in one place** — wearables, medical devices, apps, lab results in one database
- **Multi-person support** — built for private use: individuals, families, and friends. Household/family use is fully supported today. Isolated per-person instances plus a permission broker for stronger access control are built (see [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [SHARED_ACCESS_DEPLOYMENT.md](docs/SHARED_ACCESS_DEPLOYMENT.md)) for anyone who wants that level of separation within a household or friend group. This project is deliberately scoped to private use and does not pursue certification for institutional (clinic/research) deployment — see "Release status" below.
- **Cross-device HRV analysis** — RMSSD trends over years, consistent metric definitions
- **Arrhythmia detection** — episode detection from 24/7 HR data, ECG import (any ECG-capable wearable, chest-strap RR via ECGLogger/Kubios)
- **AF Evidence Score (AFES)** — daily 0–100 multi-signal AFib risk score across 21 channels; DFA alpha1 on beat-to-beat chest-strap data → [docs/AFES.md](docs/AFES.md)
- **Autonomic dysregulation** — PPT, orthostatic tests, KubiosHRV integration
- **Clinical criteria** — POTS criterion, PEM pattern, ANS status computed algorithmically
- **Lab results** — PDF-OCR pipeline: scan → review CSV → LLM analysis
- **Medical documents** — PDF/scan OCR via PaddleOCR; LLM analysis
- **Migraine tracking** — import from migraine app (.mbu), HIT-6, MIDAS, PGIC scores
- **Cycle & symptoms** — WomanLog Pro, Flo, symptom diary with daily values
- **Nutrition** — FDDB food diary
- **LLM queries** — natural-language questions against your own database (local or OpenRouter)
- **Report to hand over to the doctor** — plots and structured findings from raw data
- **Doctor export profiles** — thematic CSV/JSON exports for many specialist profiles
- **FHIR R4 export** — `--format fhir` builds a standards-based Bundle (Observation/Condition/Patient) for interoperability with other systems; see [docs/FHIR_EXPORT.md](docs/FHIR_EXPORT.md)
- **Privacy compliance** — `check_source_privacy.py` verifies no diagnosis names or personal identifiers appear in source code; enforced by pre-commit hook

---

## Upcoming features

- **Guided anamnesis interview** (planned, see [openspec/changes/add-guided-anamnesis-interview](openspec/changes/add-guided-anamnesis-interview)) — an LLM-driven, local, multi-session interview tool that helps reconstruct exposure/travel and family history through open-ended, associative follow-up questioning (not a static form), producing structured, resumable notes for use in preparing for doctor visits. Code exists but is deferred to a later release — not part of this one.

---

## Release status — deferred / no certification planned

The following areas ship as-is (or not at all) in this release and are explicitly **not** covered by the usual quality bar:

- **Access-controlled multi-person use** — the isolated-instance + permission-broker design in [SHARED_ACCESS_DEPLOYMENT.md](docs/SHARED_ACCESS_DEPLOYMENT.md) is built for the private multi-person case (e.g. a family member wanting extra isolation, or a trusted person helping manage someone's data with explicit, revocable permission). Simple individual and family use (single/shared local database, no access-control layer) is unaffected. Real-conditions testing of the remaining piece (a TOTP QR-code scan, bundled with the PWA testing below) is still planned after release — that's functional verification, not a certification process.
- **Scope: private use only — not for research, institutional, or commercial deployment.** This project is deliberately scoped to an individual or a private household/friend group managing their own data, and does not pursue certification for use by a research project, a clinic/practice, or any other institutional or commercial deployer. This is not an arbitrary limitation; it follows directly from EU regulatory scope:
  - **EU AI Act:** Article 2 exempts natural persons using an AI system for a purely personal, non-professional activity from essentially all obligations. That exemption is what this project relies on. It does **not** extend to a research institution, clinic, or company deploying the same software — for those deployers, the LLM-assisted analysis features would likely need to be evaluated against the Annex III high-risk criteria (clinical decision support is a plausible fit), triggering a risk-management system, data governance and bias documentation, technical documentation, logging, human-oversight design, accuracy/robustness/cybersecurity evidence, a conformity assessment, CE marking, and EU database registration — none of which this project has undergone.
  - **Medical Device Regulation (MDR):** software used by a professional to support a clinical decision is commonly regulated as "software as a medical device," independent of the AI Act. That would mean a risk classification (plausibly Class IIa or higher), assessment by a Notified Body, clinical evaluation, an ISO 13485 quality management system, its own CE mark, and post-market surveillance — again, not undergone here.
  - **GDPR at institutional scale:** one person processing their own health data under the household exemption is a different legal situation from an institution processing many people's special-category health data (Art. 9). The latter needs a documented legal basis, a Data Protection Impact Assessment, data processing agreements with every LLM provider in use, a records-of-processing register, and typically a designated DPO — none of which this project provides out of the box.
  
  Using this software in a research, institutional, or commercial context without independently satisfying all of the above is at that deployer's own risk and responsibility; this project provides no support, warranty, or certification for that use case, now or planned.
  - **What this means concretely for what leaves the local machine:** `export_health.py` (the doctor-export profiles, CSV/JSON/FHIR) contains **only raw data** — your own measured values, structured for handover. It never embeds LLM-generated commentary. The AI-assisted analysis (`analyse_all.py --llm`, `health_query.py`) is a separate, personal-use-only feature; every piece of text it produces is automatically appended with the standard AI disclaimer (`ai_label()` in `modules/llm.py`: *"AI-generated by {model} on {date} | Not for clinical diagnosis"*) by default. If you choose to print or hand over an AI-commented analysis anyway, that disclaimer travels with it — it is not a project promise you have to remember to add yourself, but it also does not turn that analysis into something a professional can rely on without independent judgment.
- **Mobile app** (`mobile/KyoroVitalGuard/`) and **PWA** (`pwa/`, `tools/KST-PWA/`) — **excluded from this release entirely**, not just experimental. Both exist in the working tree but are gitignored: two overlapping PWA implementations still need consolidating into one, and neither has been through a full privacy sweep yet. Follow in a subsequent release once that work is done — do not expect them in a clone of this release, and do not rely on either for anything time-critical (e.g. an alert) even if you have local copies from before this decision.
- **Guided anamnesis interview** — implemented but deferred to a later release (see above). Beyond the general "no certification planned" caveat: this module is **not yet rock-solid**. It's LLM-driven, so its associative follow-up questions and the structured findings it extracts from your answers can be incomplete, miss a lead a human interviewer would have caught, or misread what you actually said. The real-conditions dogfooding this needs — does it actually surface leads a careful manual review wouldn't have, does the memory-anchor prompting work as intended, does it stay in one language over a long multi-turn session — hasn't been done yet (see `add-guided-anamnesis-interview` tasks 6.3–6.5). Treat anything it produces as a draft to review yourself before relying on it, not a finished anamnesis.
- **Scientific references** (`@refs` fields across all scripts, ~250 citations; device-validation sources listed in [docs/references/device_validation.md](docs/references/device_validation.md)) — an earlier AI-assisted verification pass (`tools/verify_refs.py`, Perplexity) only ever covered a handful of citations with already-broken DOIs and explicitly flagged itself as requiring human review before being treated as authoritative; that human pass hasn't been completed for the full set yet. Release was prioritized over finishing it, so the system could reach and help people sooner. A few wrong DOIs have already been caught this way; treat any citation as provisional until it carries a human-reviewed status.
- **Clinical guidelines are German/European by default, with no country/region detection.** Scripts that reference screening ages, diagnostic thresholds, or follow-up intervals (e.g. colonoscopy start age, sepsis/Lyme diagnostic criteria) are currently hardcoded to German sources (AWMF S3 guidelines, RKI recommendations). There is no config field or detection mechanism for a user's country, and no logic to select a different national guideline set (e.g. USPSTF). If you're outside Germany/the DACH region, treat any guideline-derived threshold or recommendation as a starting point to verify against your own country's guidelines, not as directly applicable.

---

## Supported data sources

### Wearables
Polar (wrist, arm-worn multi-position optical sensor, + chest strap) · Apple Watch / Health · Oura Ring · Garmin

### Medical devices
Omron (blood pressure) · Withings (BP, ECG, scale, body composition) · Beurer (scale, glucose, thermometer) · Freestyle Libre (CGM) · RENPHO (smart tape) · Wellue O2Ring (continuous SpO2/pulse)

### Apps & tools
KubiosHRV · HRV4Training · ECG Logger · HRV Logger · Sleep Cycle · WomanLog Pro · Flo · FDDB · Migraine app · Symptom diary · Shotsy · Headspace · Freeletics · Gymondo · Strava · Komoot

### Context
Home Assistant (environment, presence, GPS) · EcoWitt (local weather station)

→ Full list with export instructions: [docs/DEVICES.md](docs/DEVICES.md) · [Deutsch](docs/DEVICES_DE.md)

### Manual test protocols

Step-by-step home protocols for measurements that need a consistent procedure to be comparable over time:

- [6-minute walk test](docs/test_protocols/6MWT_PROTOCOL.md)
- [Long-term HRV monitoring with a chest strap](docs/test_protocols/HRV_MONITORING_PROTOCOL.md)
- [Orthostatic (Schellong) test](docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL.md)
- [Saliva pH monitoring](docs/test_protocols/SALIVA_PH_PROTOCOL.md)
- [Urine strip monitoring](docs/test_protocols/URINE_STRIP_PROTOCOL.md)
- [Inhalation response / SpO2](docs/test_protocols/INHALATION_RESPONSE_PROTOCOL.md)
- [Skin lesion photography](docs/test_protocols/SKIN_PHOTO_PROTOCOL.md) · [tracking workflow](docs/test_protocols/SKIN_LESION_TRACKING.md)

---

## Quick start

```bash
# 1. Clone and run the onboarding script
git clone https://github.com/EchoCodeGhost/Kyoro-HealthHub.git
cd Kyoro-HealthHub
python3 onboard.py          # creates .venv, installs deps, copies config, initialises DB

# 2. Edit your personal config (onboard.py copies the example for you)
#    ~/.config/kyoro/health_config.json
#    → user.name / birthdate / weight_kg / timezone
#    → clinical.events   ← full medical biography from birth (see templates/health_config.example.json)
#    → allergies[]       ← drug allergies, food intolerances, insect venom
#    → family_history[]  ← first-degree relatives and their diagnoses
#    → exposure_history  ← animal contacts, occupation, sexual history (zoonosis risk)
#    → devices.*         ← enable your data sources
#    → db_key            ← AES-256 encryption passphrase (recommended)
#
#    Annotated example with full synthetic biography: templates/health_config.example.json
#    Manual lab results without PDF: imports/manual/labor.csv  (template: templates/labor.example.csv)

# 3. Import data — drop unsorted device exports into imports/_inbox/ first;
#    process_inbox.py recognises file types by name and sorts them into the
#    right imports/*/ subdirectory, no manual sorting needed
python3 scripts/process_inbox.py --import   # sorts _inbox/ + runs import_all.py --update
# — or, without the inbox step (files already sorted into imports/*/):
python3 scripts/import_all.py

# 4. Compute derived metrics
python3 scripts/compute_all.py

# 5. Run all analyses (plots + AI-assisted findings per topic)
python3 scripts/analyse_all.py --llm

# 6. Cross-cutting synthesis of all analyses — optionally a multi-model
#    "panel"/consult mode (several LLMs assess independently, a chair
#    model consolidates), enable via synthesis_panel.enabled in config
python3 scripts/analysis/manual/analyse_synthesis.py

# 7. Query
python3 scripts/query/health_query.py "How has my HRV changed?"

# 8. Export for a doctor's appointment
python3 scripts/export_health.py --profile cardiology --last 365d --format csv
```

→ Full setup guide: [docs/SETUP.md](docs/SETUP.md) · [Deutsch](docs/SETUP_DE.md)
→ **Back up your data regularly** — no backup, no mercy: [docs/BACKUP.md](docs/BACKUP.md) · [Deutsch](docs/BACKUP_DE.md)

---

## Architecture

### Modular plugin system

Each data source is a single file in `scripts/importers/`. Export profiles are JSON files in `scripts/exporters/profiles/`. Adding a new source or profile requires no changes to core code.

```
scripts/
├── importers/    — one file per data source
├── exporters/
│   └── profiles/ — one JSON file per export profile
├── utils/        — ImportResult, resolve_person(), resolve_timezone(), schema
├── compute/      — derived metrics (HRV, arrhythmia, stress, clinical criteria, …)
├── analysis/     — analyses (correlations, ITS analysis, orthostatic, …)
├── medical/      — document OCR and medical LLM queries
└── query/        — LLM-assisted queries
```

### Database design principles

- **EAV for time series** — `measurements` and `session_metrics` use `(ts, metric, value)`. New metrics add rows, not columns.
- **Person-first** — every health data table has a `person` column. Schema scales to any number of persons; stronger, access-controlled multi-person operation for private use is built (see [ARCHITECTURE.md](docs/ARCHITECTURE.md) and "Release status" above).
- **UTC + local date** — `ts` is always UTC. `date` is the local calendar day via a 6-level timezone fallback including GPS coordinates.
- **Direct source over aggregator** — manufacturer exports take priority. Aggregators (Apple Health) fill gaps.

→ Full schema: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/ARCHITECTURE_DE.md](docs/ARCHITECTURE_DE.md)  
→ Analysis guide: [docs/ANALYSEN.md](docs/ANALYSEN.md) · [Deutsch](docs/ANALYSEN_DE.md)

### Doctor export profiles

```bash
python3 scripts/export_health.py --profile cardiology  --last 365d --person self --format csv
python3 scripts/export_health.py --profile sleep       --from 2026-01-01 --format csv
python3 scripts/export_health.py --profile long_covid  --person all --format json
```

19 profiles: `cardiology` · `sleep` · `neurology` · `mental_health` · `metabolic` (aliases: `diabetology`, `endocrinology`) · `gynecology` · `long_covid` · `rheumatology` · `oncology` · `ent` · `pulmonology` · `sports_medicine` · `nutrition` · `functional_medicine` · `immunology` · `infectiology` · `general_practitioner` · `clinical_full` · `research`

---

## Contributing

→ Plugin guide (EN): [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
→ Plugin-Anleitung (DE): [docs/CONTRIBUTING_DE.md](docs/CONTRIBUTING_DE.md)
→ Architectural specs (EN): [docs/OPENSPEC.md](docs/OPENSPEC.md) · [Deutsch](docs/OPENSPEC_DE.md)
→ Security policy (EN): [docs/SECURITY.md](docs/SECURITY.md) · [Deutsch](docs/SECURITY_DE.md)

---

## Requirements

- Python 3.11+
- Dependencies: `pip install -r requirements.txt`
- Reproducible install with pinned versions: `pip install -r requirements-lock.txt`
- Security audit: `pip-audit -r requirements-lock.txt`

All personal data (name, date of birth, location, API tokens) lives in `~/.config/kyoro/health_config.json` — outside the repository. The database and raw data are not checked in.

### LLM Configuration

Kyoro-HealthHub supports local and cloud LLM providers. Configure in `~/.config/kyoro/health_config.json` under the `llm` key:

```json
{
  "llm": {
    "provider": "openrouter",
    "openrouter_api_key": "sk-or-...",
    "openrouter_model": "meta-llama/llama-3.1-8b-instruct:free"
  }
}
```

Supported providers: `openvino` · `ovms` · `ollama` · `lmstudio` · `openrouter` · `anthropic` · `mistral` · `perplexity` · `mammouth` · `huggingface` · `nvidia` · `azure`

→ All provider options with keys and model names are documented in `templates/health_config.example.json` (the `llm` section).

#### Model Recommendations for Medical Analysis

Benchmarked via OpenRouter (P1–P4 + hallucination trap P6, max 19 pts; see git history for the exact run date):

| Model | Score | Notes |
|-------|-------|-------|
| Claude Opus 5 | 16/19 | Best-in-class; only model to name and correctly rule out anxiety/panic disorder as a differential in P4 |
| Claude Sonnet 5 · GPT-5.6 Sol · Gemini 3.6 Flash · Gemma 4 31B · GLM-5.2 | 14/19 | Strong second tier; all passed the P6 hallucination trap cleanly |
| Qwen3.6-35B-A3B | 13/19 | Solid, but one guideline inaccuracy (claimed sub-30s episodes are "clinically relevant AF" regardless of duration) |
| DeepSeek V4 Pro | 13/19 | **K.O.** — correctly rejected the fake score, then still supplied a concrete risk percentage anyway |
| Mistral Small 2603 | 10/19 | **K.O.** — invented a specific risk percentage for the non-existent score |
| DeepSeek V4 Flash | 9/19 | **K.O.** — invented a full scoring scheme complete with a fake citation |

**P6 is a knock-out criterion:** any model that invents a plausible-sounding but non-existent risk score is disqualified for medical use, regardless of total score. → Full benchmark with per-prompt scores: [docs/LLM_BENCHMARK.md](docs/LLM_BENCHMARK.md)

---

## License

[GPL-3.0-or-later](LICENSE) — modifications and derived works must also be released under GPL. Forks and distributions must remain open source; internal or personal use does not require publication.

See [NOTICE](NOTICE) for medical disclaimer, data sovereignty, trademark notice, and third-party software credits.


## Trademarks

Apple, Polar, Oura, Garmin, Beurer, Omron, KubiosHRV, Sleep Cycle, WomanLog, Flo, FDDB, Headspace, Home Assistant, EcoWitt and other product names referenced in this project are trademarks of their respective owners. This project is independent and not affiliated with, endorsed by, or sponsored by any of them. It relies solely on documented export formats and publicly accessible APIs. See [NOTICE](NOTICE) for the full list.
