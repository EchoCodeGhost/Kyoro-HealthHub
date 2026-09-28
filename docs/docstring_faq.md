# Docstring FAQ — Kyoro-HealthHub

**Version:** 1.1
**Goal:** frequently asked questions and answers about docstrings in Kyoro-HealthHub

---

## 📋 Table of Contents

1. [General Questions](#-general-questions)
2. [Tag-Specific Questions](#-tag-specific-questions)
3. [Compliance & Medical Terminology](#-compliance--medical-terminology)
4. [Validation & Tools](#-validation--tools)
5. [Best Practices](#-best-practices)
6. [Troubleshooting](#-troubleshooting)

---

## 🤔 General Questions

### 1.01 Why are docstrings so important in Kyoro-HealthHub?
**Answer:**
In Kyoro-HealthHub, docstrings aren't just documentation — they're a **compliance requirement** and a **quality-assurance instrument**:
- **Medical validity:** clear separation between validated and heuristic methods
- **Legal safety:** avoiding medical diagnoses, gender, age, locations
- **Research capability:** traceable methods for scientific use
- **Community:** easier onboarding and maintainability

---

### 1.02 Who is responsible for docstrings?
**Answer:** Every contributor! The duty falls on the developer who writes or changes the code. Before every pull request:
- Run docstring validation
- Run the compliance check
- Get a peer review

---

### 1.03 How often do docstrings need to be updated?
**Answer:**
- **Always:** on code changes (new functions, changed methodology)
- **Monthly:** team review of all docstrings
- **Before every PR:** automatic validation
- **Annually:** full template review

---

## 🏷️ Tag-Specific Questions

### 2.01 Which @tier categories exist, and when do I use which?

| Tier | Description | Examples |
|------|--------------|----------|
| **validated** | Clinically validated algorithms (FDA-cleared, peer-reviewed) | AI-based arrhythmia detection (if certified) |
| **calibrated** | Calibrated methods with individual adjustment | Training performance analysis |
| **research** | Complex algorithms with a scientific basis | HRV analysis, DFA alpha1 |
| **heuristic** | Heuristic methods, experimental | PEM detection, stress scores |
| **experimental** | Experimental approaches under development | New algorithms in testing |
| **infrastructure** | System scripts (import, configuration, utilities) | import_polar.py, health_config.py |

---

### 2.02 What's the difference between @purpose and @method?
**Answer:**

| Tag | Question | Example |
|-----|-------|----------|
| **@purpose** | *What* does the script do? | "Computes HRV metrics" |
| **@method** | *How* does it do that? | "Uses DFA alpha1 analysis with Kubios scales" |

**Mnemonic:** Purpose = goal, Method = path

---

### 2.03 What's the difference between @purpose and @relevance?
**Answer:**

| Tag | Question | Example |
|-----|-------|----------|
| **@purpose** | *What* does the script do? | "Computes HRV metrics per 5-minute window" |
| **@relevance** | *Why* is this relevant? | "An HRV drop is an early indicator of autonomic dysfunction — central to tracking progression" |

`@relevance.de`/`@relevance.en` is required for
**all** `@tier` values, without exception (including `infrastructure`
and `heuristic`). Details and examples: [docstring_template.md,
section "@relevance"](docstring_template.md#-relevance--why-is-this-data-type-relevant).

---

### 2.04 When do I need @reads and @writes?
**Answer:**
- **@reads:** whenever the script reads data from the database
- **@writes:** whenever the script writes data to the database
- **Format:** comma-separated list of table names

**Example:**
```python
@reads       ppi_raw, measurements, sessions
@writes      hrv_daily, hrv_advanced
```

---

### 2.05 When do I need @refs?
**Answer:**

| Tier | @refs required? | Rationale |
|------|---------------|------------|
| validated | ✅ Yes | Clinical validation must be referenced |
| calibrated | ✅ Yes | Calibration basis must be traceable |
| research | ✅ Yes | Scientific basis must be cited |
| heuristic | ⚠️ Optional | Recommended when medical context is referenced |
| experimental | ❌ No | Development status makes references difficult |
| infrastructure | ❌ No | No scientific basis needed |

---

### 2.06 How many references do I need?
**Answer:**
- **Minimum:** 1 reference (for research/calibrated/validated)
- **Recommended:** 2-3 references (primary + secondary sources)
- **Format:** always with DOI, if available

---

### 2.07 What is @usage, and when do I need it?
**Answer:**
- **Purpose:** shows concrete usage examples
- **Required for:** heuristic, calibrated scripts
- **Recommended for:** all scripts with a CLI interface
- **Format:** 2-3 concrete command lines

**Example:**
```python
@usage
    python analyse_overview.py --plot
    python analyse_overview.py --from 2024-01-01 --weeks 12
    python analyse_overview.py --no-llm
```

---

### 2.08 What is @scoring?
**Answer:**
- **Purpose:** describes the scoring scheme for scores
- **Required:** no, but recommended for heuristic scripts with scoring
- **Format:** clear formula or description

**Example:**
```python
@scoring direct = max(ECG_AFib=50, TG_Episode=40)
```

---

### 2.09 What are the prompt tags (@prompt-classification, @prompt.de, @prompt.en)?
**Answer:**
- **@prompt-classification:** type of the prompt (LLM, VLM, both, none)
- **@prompt.de:** description of the prompt in German
- **@prompt.en:** description of the prompt in English
- **Use:** only for scripts that use an LLM/VLM

**Example:**
```python
@prompt-classification LLM
@prompt.de   Analysiert Symptome mit Large Language Model
@prompt.en   Analyzes symptoms using Large Language Model
```

---

### 2.10 What is `scripts/modules/confidence.py`, and when do I use it?
**Answer:** A shared module for analysis scripts that need to communicate
findings with varying certainty. Instead of inventing your own local
vocabulary, call `label_finding()` with one of the three levels
`"confirmed"` / `"suspected"` / `"lead"`:

```python
from modules.confidence import label_finding

de, en = label_finding("X bestätigt", "X confirmed", "confirmed")
# de == "✅ Bestätigt: X bestätigt"
```

Details, level definitions, and usage examples: [docstring_template.md,
section "Confidence labeling"](docstring_template.md#confidence-labeling-scriptsmodulesconfidencepy).

---

## ⚖️ Compliance & Medical Terminology

### 3.01 Which medical terms are forbidden?
**Answer:** **ALL** specific medical diagnoses:

❌ **Forbidden:**
- ME/CFS, POTS, MCAS
- Diabetes, hypertension, heart attack
- COVID-19, Long COVID, Post-COVID
- Autoimmune diseases
- Neurological diseases (MS, Parkinson's, etc.)
- Mental health conditions (depression, anxiety disorder, etc.)
- Gender (male, female, man, woman, etc.)
- Age (18 years, 30-40, seniors, children, etc.)
- Locations (Berlin, Munich, Germany, Europe, etc.)
- Personal data (patient, user, subject, etc.)

---

### 3.02 Which medical terms are allowed?
**Answer:** ✅ **Generic metrics and methods:**

| Category | Examples |
|----------|----------|
| **HRV metrics** | RMSSD, SDNN, DFA alpha1, HF, LF, LF/HF |
| **Heart rate** | resting heart rate (RHR), maximum heart rate, AFib burden |
| **Sleep** | deep sleep, REM sleep, sleep efficiency |
| **Activity** | steps, calorie expenditure, VO2max |
| **Sensors** | PPG, ECG, SpO₂ |
| **Methods** | heuristic, statistical, correlative |

---

### 3.03 How do I replace forbidden medical terms?
**Answer:**

| Forbidden term | Suggested replacement |
|------------------|---------------------|
| POTS | "orthostatic responses", "heart rate increase on standing" |
| PEM | "post-exertion response pattern", "heuristic exertion pattern" |
| ME/CFS | "chronic fatigue" (only as a symptom, not as a diagnosis) |
| Diabetes | "blood glucose values", "glucose metabolism" |
| Patient | "user", "person", "data source" |

---

### 3.04 Am I allowed to use "heart rate" or "HRV"?
**Answer:** ✅ **Yes!** Those are **metrics**, not diagnoses.

- ✅ **Allowed:** heart rate, HRV, RMSSD, blood pressure, sleep stages
- ❌ **Forbidden:** heart attack, atrial fibrillation (as a diagnosis), POTS, diabetes

---

### 3.05 How do I document that something isn't clinically validated?
**Answer:** Always communicate this clearly in the @limits tag:

```python
@limits.de   Heuristische Methode, nicht klinisch validiert; basierend auf Consumer-Sensorik (n=1)
@limits.en   Heuristic method, not clinically validated; based on consumer sensors (n=1)
```

---

### 3.06 Am I allowed to name devices?
**Answer:** ✅ **Yes!** Device names are allowed:

- Polar, Garmin, Apple Watch, Oura Ring
- Kubios, WHOOP, Fitbit
- Home Assistant, Open-Meteo

---

## 🔧 Validation & Tools

### 4.01 How do I run docstring validation?
**Answer:**

```bash
# Validate all scripts
python scripts/check_docstrings.py

# Just a specific directory or file
python scripts/check_docstrings.py --path scripts/analysis/analyse_overview.py

# Show only statistics
python scripts/check_docstrings.py --stats
```

`check_docstrings.py` has **no** `--fix`: errors must be fixed manually in
the docstring. `--path`/`-p` accepts either a directory or a single file;
more flags: `--quiet`/`-q` (error summary only), `--by-tier`,
`--by-category`.

---

### 4.02 How do I run the compliance check?
**Answer:**

```bash
python scripts/check_compliance.py
```

---

### 4.03 What's the difference between validation and compliance?
**Answer:**

| Check | Purpose | Tool |
|--------|-------|------|
| **Validation** | Checks the structure and required tags of docstrings | `check_docstrings.py` |
| **Compliance** | Checks for forbidden content (diagnoses, gender, age, locations) | `check_compliance.py` |

---

### 4.04 How do I set up pre-commit hooks?
**Answer:**

```bash
# Install pre-commit hooks (one-time)
pre-commit install

# Run manually
pre-commit run check-docstrings --all-files

# Automatically before every commit, this then runs:
# - Docstring validation
# - Compliance check
```

---

### 4.05 What do I do when validation reports an error?
**Answer:**

1. **Read the error:** the validation report shows exactly what's missing
2. **Adjust the docstring:** add the missing tags
3. **Re-validate:** `python scripts/check_docstrings.py`
4. **Check compliance:** `python scripts/check_compliance.py`

**Example error:**
```
scripts/my_script.py:
  ❌ Missing required tag: @purpose.de
  ❌ Missing required tag: @purpose.en
```

**Fix:** add the missing tags to the docstring.

---

## ✨ Best Practices

### 5.01 Should I have every tag in every language?
**Answer:** ✅ **Yes!** Bilingual documentation is required:
- @purpose.de **and** @purpose.en
- @method.de **and** @method.en
- @limits.de **and** @limits.en

---

### 5.02 Should I have @usage in infrastructure scripts?
**Answer:** ⚠️ **Optional, but recommended** for scripts with a CLI interface.

---

### 5.03 How long should a line in a docstring be?
**Answer:** maximum **80-100 characters** for good readability.

---

### 5.04 Should I explain abbreviations?
**Answer:** ✅ **Yes!** Explain unfamiliar abbreviations on first use:

```python
@method.de   HRV (Heart Rate Variability) Analyse via DFA (Detrended Fluctuation Analysis)
```

---

### 5.05 How do I document multiple input tables?
**Answer:** comma-separated, sorted by relevance:

```python
@reads       ppi_raw, measurements, sessions, symptoms
```

---

## 🛠️ Troubleshooting

### 6.01 Validation doesn't find my docstring
**Answer:**

**Common causes:**
1. **Docstring isn't at the top:** the docstring must come **directly** after the module header
2. **Blank lines before the docstring:** not allowed
3. **Code before the docstring:** variables like `__version__` must come **after** the docstring

**Correct:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Module docstring here...
"""

__version__ = "1.0.0"  # After the docstring!
```

**Wrong:**
```python
#!/usr/bin/env python3
__version__ = "1.0.0"  # Before the docstring!

"""
Module docstring here...
"""
```

---

### 6.02 Validation says my @tier tag is missing
**Answer:** Check:
1. Is `@tier` on the **first line** of the docstring?
2. Is one of the valid values used: `validated`, `calibrated`, `research`, `heuristic`, `experimental`, `infrastructure`?
3. Is there a colon or another character between `@tier` and the value, instead of whitespace? `@tier heuristic` ✅, also with multiple spaces (`@tier  heuristic` ✅ — `check_docstrings.py` uses the regex `@tier\s+(\w+)`), but `@tier: heuristic` ❌ (the colon breaks the match, `@tier` is then reported as missing)

---

### 6.03 The compliance check reports medical diagnoses
**Answer:**

**Common sources:**
1. **In the docstring:** direct mention of POTS, ME/CFS, etc.
2. **In the code:** variable names, comments, string literals
3. **In examples:** @usage or configuration examples

**Fix:**
- Adjust docstrings (remove diagnoses)
- Clean up code comments
- Replace example configurations with neutral terms

---

### 6.04 My script is reported as "no module docstring"
**Answer:** See [6.01](#601-validation-doesnt-find-my-docstring)

---

### 6.05 Validation says "Missing required tag: @refs"
**Answer:**

1. Check whether your script type requires @refs (see [2.05](#205-when-do-i-need-refs))
2. Add at least **1 reference with a DOI**
3. Format: `Author et al. Year, Journal, doi:xxx`

---

## 📚 More Resources

- **Main documentation:** [docs/docstring_template.md](docs/docstring_template.md)
- **Onboarding guide:** [docs/docstring_onboarding_guide.md](docs/docstring_onboarding_guide.md)
- **Prompt documentation:** [docs/prompts.md](docs/prompts.md)
- **Example scripts:** `scripts/compute/compute_hrv_advanced.py` (research), `scripts/compute/compute_clinical.py` (heuristic), `scripts/compute_all.py` (infrastructure)
- **Validation script:** [scripts/check_docstrings.py](scripts/check_docstrings.py)
- **Compliance script:** [scripts/check_compliance.py](scripts/check_compliance.py)

---

*Generated by Mistral Vibe. Co-Authored-By: Mistral Vibe <vibe@mistral.ai>*
*License: GPL-3.0-or-later*
