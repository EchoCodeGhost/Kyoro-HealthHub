# Docstring Onboarding Guide — Kyoro-HealthHub

**Version:** 1.0
**Audience:** New contributors & developers

---

## 🎯 Why docstrings in Kyoro-HealthHub?

Good docstrings are essential for:
- **Maintainability:** faster debugging and understanding of the code
- **Medical validity:** clear separation between validated and heuristic methods
- **Compliance:** adherence to privacy standards (no diagnoses, gender, age, locations)
- **Community:** easier onboarding for new contributors
- **Research:** traceable methods for scientific use

---

## 📋 Required tags by script type

### 🏗️ Infrastructure (`@tier infrastructure`)
```python
@tier        infrastructure
@purpose.de  [German purpose description]
@purpose.en  [English purpose description]
@method.de   [German methodology]
@method.en   [English methodology]
@reads       [Input tables, comma-separated]
@writes      [Output tables, comma-separated]
@relevance.de [German justification for WHY this data type is relevant at all]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Limitations in German]
@limits.en   [Limitations in English]
```

**Example:** import scripts, helper functions, database utilities

---

### 🔬 Research (`@tier research`)
```python
@tier        research
@purpose.de  [German purpose description]
@purpose.en  [English purpose description]
@method.de   [Detailed methodology in German]
@method.en   [Detailed methodology in English]
@refs        Author et al. Year, Journal, doi:xxx
             Author et al. Year, Journal, doi:yyy
@relevance.de [German justification for WHY this data type is relevant at all]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Validation status in German]
@limits.en   [Validation status in English]
```

**Example:** `compute_hrv_advanced.py`, `compute_ppi_dfa.py`

---

### ⚖️ Calibrated (`@tier calibrated`)
```python
@tier        calibrated
@purpose.de  [German purpose description]
@purpose.en  [English purpose description]
@method.de   [Methodology with calibration details]
@method.en   [Methodology with calibration details]
@refs        Author et al. Year, Journal, doi:xxx
@relevance.de [German justification for WHY this data type is relevant at all]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Calibration status in German]
@limits.en   [Calibration status in English]
```

**Example:** `analyse_workout_performance.py`, `analyse_overview.py`

---

### 💡 Heuristic (`@tier heuristic`)
```python
@tier        heuristic
@purpose.de  [German purpose description]
@purpose.en  [English purpose description]
@method.de   [Methodology description]
@method.en   [Methodology description]
@reads       [Input tables]
@writes      [Output tables]
@relevance.de [German justification for WHY this data type is relevant at all]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Limitations: "Heuristic method, not clinically validated"]
@limits.en   [Limitations: "Heuristic method, not clinically validated"]
@usage
    python script.py --from 2024-01-01 --to 2024-12-31
    python script.py --plot --no-llm
```

**Example:** `compute_pem.py`, `analyse_afib_burden.py`

---

### 🧪 Experimental (`@tier experimental`)
```python
@tier        experimental
@purpose.de  [German purpose description]
@purpose.en  [English purpose description]
@method.de   [Methodology description]
@method.en   [Methodology description]
@relevance.de [German justification for WHY this data type is relevant at all]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Limitations: "Experimental approach, under development"]
@limits.en   [Limitations: "Experimental approach, under development"]
```

---

### ✅ Validated (`@tier validated`)
```python
@tier        validated
@purpose.de  [German purpose description]
@purpose.en  [English purpose description]
@method.de   [Methodology with validation details]
@method.en   [Methodology with validation details]
@refs        Author et al. Year, Journal, doi:xxx
@relevance.de [German justification for WHY this data type is relevant at all]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Validation status in German]
@limits.en   [Validation status in English]
```

**Note:** only for clinically validated algorithms (e.g. FDA-cleared, peer-reviewed)

---

## 📝 Docstring structure template

### Module docstring (at the top of every Python file)

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Script name — short description

@tier        [infrastructure|research|calibrated|heuristic|experimental|validated]
@purpose.de  [German description of the purpose]
@purpose.en  [English description of the purpose]
@method.de   [Detailed methodology description in German]
@method.en   [Detailed methodology description in English]
@reads       [Comma-separated list of input tables]
@writes      [Comma-separated list of output tables]
@refs        Author et al. Year, Journal, doi:xxx
             Author et al. Year, Journal, doi:yyy
@relevance.de [German justification for WHY this data type is relevant at all]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Limitations and validation status in German]
@limits.en   [Limitations and validation status in English]
@usage
    python script.py --from 2024-01-01
    python script.py --plot
    python script.py --help
"""

[Code starts here...]
```

### Function docstring (Google style)

```python
def compute_hrv_metrics(rr_intervals: np.ndarray) -> dict:
    """
    Computes HRV metrics from RR intervals.

    Uses DFA alpha1, RMSSD, and other standard metrics.

    Args:
        rr_intervals (np.ndarray): array of RR intervals in milliseconds

    Returns:
        dict: dictionary of HRV metrics (rmssd, dfa_alpha1, etc.)

    Refs:
        Task Force ESC/NASPE 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
        Gronwald & Hoos 2020, Front Physiol, doi:10.3389/fphys.2020.550572

    Notes:
        Minimum length: 10 beats. Shorter arrays return None.
    """
    [function code...]
```

---

## 🚫 Compliance rules (IMPORTANT!)

### ❌ **Forbidden in docstrings:**
- **Medical diagnoses:** ME/CFS, POTS, MCAS, diabetes, etc.
- **Gender:** male, female, man, woman, etc.
- **Age:** 18 years, 30-40 years, seniors, children, etc.
- **Locations:** Berlin, Munich, Germany, Europe, etc.
- **Personal data:** patient, user, subject, etc.

### ✅ **Allowed:**
- **Symptoms:** Post-Exertional Malaise (PEM), fatigue, pain (as a symptom description, not as a diagnosis)
- **Metrics:** heart rate, HRV, RMSSD, DFA alpha1, etc.
- **Methods:** heuristic, statistical, correlative, etc.
- **Devices:** Polar, Garmin, Apple Watch, Oura Ring, etc.

---

## 🔍 Reference formatting

### Correct:
```python
@refs        Perez et al. 2019, NEJM, doi:10.1056/NEJMoa1901183
             Task Force ESC/NASPE 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
             Shaffer & Ginsberg 2017, Frontiers in Public Health, doi:10.3389/fpubh.2017.00258
```

### Rules:
- ✅ Always include a DOI (if available)
- ✅ Spell out journal names correctly (no abbreviations)
- ✅ Sort chronologically or by relevance
- ✅ Each reference on its own line, indented

---

## 🛠️ Tools & validation

### Run docstring validation:
```bash
# Check all scripts
python scripts/check_docstrings.py

# Check just a specific directory or file
python scripts/check_docstrings.py --path scripts/analysis/analyse_overview.py

# Show only statistics (e.g. broken down by @tier or directory)
python scripts/check_docstrings.py --stats --by-tier
```

There is **no** `--fix` — docstring errors must be fixed manually.
More flags: `--quiet`/`-q` (error summary only), `--by-category`.

### Check compliance:
```bash
python scripts/check_compliance.py
```

### Pre-commit hooks (run automatically before every commit):
```bash
# One-time setup
pre-commit install

# Run manually
pre-commit run check-docstrings --all-files
```

---

## 📚 Resources

- **Main template:** [`docs/docstring_template.md`](docs/docstring_template.md)
- **Prompt documentation:** [`docs/prompts.md`](docs/prompts.md)
- **Example scripts:**
  - Research: [`scripts/compute/compute_hrv_advanced.py`](../scripts/compute/compute_hrv_advanced.py)
  - Heuristic: [`scripts/compute/compute_clinical.py`](../scripts/compute/compute_clinical.py)
  - Infrastructure: [`scripts/compute_all.py`](../scripts/compute_all.py)
- **Validation script:** [`scripts/check_docstrings.py`](scripts/check_docstrings.py)
- **Compliance script:** [`scripts/check_compliance.py`](scripts/check_compliance.py)

---

## ❓ FAQ (Frequently Asked Questions)

### 1. When do I need @refs?
**Answer:** For all **research**, **calibrated**, and **validated** scripts. For **heuristic** scripts it's optional, but recommended when medical context is referenced.

---

### 2. How do I format @reads and @writes?
**Answer:** As a comma-separated list of table names:
```python
@reads       ppi_raw, measurements, sessions
@writes      hrv_daily, hrv_advanced
```

---

### 3. What's the difference between @purpose and @method?
**Answer:**
- **@purpose:** *what* the script does (its goal)
- **@method:** *how* the script does it (implementation details)

**Example:**
```python
@purpose.de  Berechnet erweiterte HRV-Metriken aus PPG-Daten
@purpose.en  Computes advanced HRV metrics from PPG data
@method.de   Verwendet DFA alpha1-Analyse mit Kubios-Skalen (1-20 Beats)
@method.en   Uses DFA alpha1 analysis with Kubios scales (1-20 beats)
```

---

### 4. Am I allowed to use abbreviations like PEM or HRV?
**Answer:**
- ✅ **HRV, RMSSD, DFA, ECG**, etc. are allowed (standard metrics)
- ❌ **PEM, POTS, MCAS**, etc. are **not** allowed (medical diagnoses)
- ✅ Replace with: "Post-Exertional Malaise" → "post-exertion response pattern" or "heuristic exertion pattern"

---

### 5. How long should a docstring be?
**Answer:**
- **Module docstring:** 10-20 lines (including all tags)
- **Function docstring:** 5-15 lines
- **Line per tag:** max. 80 characters (for readability)

---

### 6. What do I do if my script has multiple purposes?
**Answer:** Main purpose in @purpose, secondary purposes in @method:
```python
@purpose.de  Berechnet HRV-Metriken und erkennt Anomalien
@method.de   Primär: DFA alpha1-Berechnung; Sekundär: Anomalie-Erkennung via Z-Score > 2
```

---

### 7. How do I document limitations?
**Answer:** Always be honest and specific:
```python
@limits.de   Heuristische Methode, nicht klinisch validiert; basierend auf Consumer-Sensorik (n=1)
@limits.en   Heuristic method, not clinically validated; based on consumer sensors (n=1)
```

---

### 8. Do I need @usage in every script?
**Answer:** No, it's only required for **heuristic** and **calibrated** scripts. For **infrastructure** it's optional, but recommended.

---

### 9. What's the difference between infrastructure and utility?
**Answer:**
- **infrastructure:** scripts that keep the system running (import, database, configuration)
- **heuristic/calibrated/research:** scripts that perform analyses
- **utility:** helper functions used by multiple scripts

**Examples:**
- `import_polar.py` → **infrastructure**
- `compute_hrv_advanced.py` → **research**
- `health_config.py` → **infrastructure**

---

### 10. How often should I update my docstrings?
**Answer:**
- **Always:** for new features or methodology changes
- **Monthly:** team review of all docstrings
- **Before every PR:** run validation with `check_docstrings.py`

---

### 11. Where do I find good references?
**Answer:**
- **DOI search:** [doi.org](https://doi.org/)
- **PubMed:** [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/)
- **HRV standard:** Task Force ESC/NASPE 1996, doi:10.1161/01.CIR.93.5.1043
- **Sleep standard:** Iber et al. 2007, doi:10.1093/sleep/30.11.1587

---

### 12. How do I test whether my docstring is valid?
**Answer:**
```bash
# Run validation
python scripts/check_docstrings.py

# Check just your script
python scripts/check_docstrings.py --path scripts/compute/my_script.py

# Check compliance
python scripts/check_compliance.py
```

---

## 🎓 Best practices

### ✅ DO:
- Always document **bilingually** (@purpose.de + @purpose.en, etc.)
- Stay **consistent** with existing docstrings
- Be **specific** in the methodology description
- Be **honest** about limitations
- Always give **DOIs** when available

### ❌ DON'T:
- Name medical diagnoses
- Mention gender, age, or locations
- Use unclear abbreviations (without explanation)
- Give references without a DOI
- Leave @usage without actual examples

---

## 📞 Support

- **Questions about docstrings:** open an issue labeled `documentation`
- **Medical terminology:** ask in the project's discussion channel
- **Pull request template:** [`/.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)

---

## 📝 Quick checklist for new scripts

- [ ] Module docstring with all required tags
- [ ] @tier set correctly
- [ ] @purpose.de and @purpose.en present
- [ ] @method.de and @method.en with details
- [ ] @reads and @writes (if applicable)
- [ ] @refs with DOI (if medically relevant)
- [ ] @limits.de and @limits.en
- [ ] @usage with examples (if heuristic/calibrated)
- [ ] All public functions have docstrings
- [ ] Medical terms are compliant
- [ ] Validation: `python scripts/check_docstrings.py` ✅
- [ ] Compliance: `python scripts/check_compliance.py` ✅

---

*Generated by Mistral Vibe. Co-Authored-By: Mistral Vibe <vibe@mistral.ai>*
*License: GPL-3.0-or-later*
