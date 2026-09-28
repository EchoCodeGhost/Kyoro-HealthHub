# Docstring Template for Kyoro-HealthHub

**Version:** 1.0
**Status:** Active

---

## 📋 Table of Contents

1. [Introduction](#introduction)
2. [General Structure](#general-structure)
3. [Template by Script Type](#template-by-script-type)
   - [3.1 Research Scripts](#31-research-scripts)
   - [3.2 Heuristic Scripts](#32-heuristic-scripts)
   - [3.3 Infrastructure Scripts](#33-infrastructure-scripts)
   - [3.4 Validated Scripts](#34-validated-scripts)
   - [3.5 Calibrated Scripts](#35-calibrated-scripts)
   - [3.6 Experimental Scripts](#36-experimental-scripts)
4. [Prompt Documentation](#prompt-documentation)
   - [4.1 Classification System](#41-classification-system)
   - [4.2 Tag Reference](#42-tag-reference)
   - [4.3 Examples](#43-examples)
5. [Function Docstrings](#function-docstrings)
6. [Medical Terminology Guidelines](#medical-terminology-guidelines)
7. [Reference Formatting](#reference-formatting)
8. [Best Practices](#best-practices)
9. [Common Mistakes & Fixes](#common-mistakes--fixes)
10. [Review Checklist](#review-checklist)
11. [`@relevance` — Why is this data type relevant?](#-relevance--why-is-this-data-type-relevant)
12. [Confidence labeling (`scripts/modules/confidence.py`)](#confidence-labeling-scriptsmodulesconfidencepy)

---

## 🎯 Introduction

### Why structured docstrings?

Structured docstrings are **essential** for:

- **Consistency:** uniform documentation across all 382 scripts
- **Understandability:** clear description for developers and medical users
- **Attribution:** traceability of scientific methods
- **Traceability:** transparency about inputs, outputs, and limitations
- **Medical correctness:** precise terminology for clinical applications

### DOCSTRING STANDARD

This template follows the **Kyoro-HealthHub docstring standard**, which:
- is based on **Google-style docstrings**
- extends them with an **@-tag system** for structured metadata
- provides **bilingual support** (German/English)
- ensures **medical validity**

---

## 📝 General Structure

Every **module docstring** (at the top of the Python file) MUST have the following structure:

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
{Short description of the script}

@tier        {research|heuristic|infrastructure}
@purpose.de  {German description of the purpose}
@purpose.en  {English description of the purpose}
@relevance.de {German justification for WHY this data type is relevant at all}
@relevance.en {English justification for WHY this data type is relevant at all}
@method.de   {Detailed methodology description in German}
@method.en   {Detailed methodology description in English}
@reads       {Comma-separated list of input tables}
@writes      {Comma-separated list of output tables}
@refs        {Scientific references with DOI}
@limits.de   {Limitations and validation status in German}
@limits.en   {Limitations and validation status in English}
@usage
    {Example call 1}
    {Example call 2}
    {Example call 3}
"""
```

### Required tags by @tier

| @tier | Required tags | Recommended tags |
|-------|--------------|-----------------|
| **validated** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @refs, @limits.de, @limits.en, **@usage** | @reads, @writes |
| **calibrated** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @refs, @limits.de, @limits.en, **@usage** | @reads, @writes |
| **research** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @refs, **@usage** | @reads, @writes, @limits.de, @limits.en |
| **heuristic** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @limits.de, @limits.en, **@usage**, **@scoring** | @reads, @writes, @refs |
| **experimental** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @limits.de, @limits.en, **@usage** | @reads, @writes, @refs |
| **infrastructure** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en | @reads, @writes, @limits.de, @limits.en, @usage |

> **Note:** @usage and @refs are required within their respective tier categories, @scoring is required for **heuristic**. **`@relevance.de`/`@relevance.en`** are required for **all** tiers, deliberately without exception for `heuristic` (unlike `@scoring`, which is only required there) — see [`@relevance` — Why is this data type relevant?](#-relevance--why-is-this-data-type-relevant).

### Bilingual tags

The following tags **MUST** be present bilingually (German/English):
- `@purpose.de` / `@purpose.en`
- `@relevance.de` / `@relevance.en`
- `@method.de` / `@method.en`
- `@limits.de` / `@limits.en`
- `@prompt.de` / `@prompt.en` (if @prompt-classification is present)

### Prompt-specific tags

If the script uses **LLM or VLM prompts**, the following tags **MUST** be added:
- `@prompt-classification` — classifies the prompt types (e.g. `LLM:System, VLM:Medical`)
- `@prompt.de` — German prompt text (optional, but recommended)
- `@prompt.en` — English prompt text (optional, but recommended)

---

## 🤖 Prompt Documentation

### 4.1 Classification system

Every prompt **MUST** be classified to clearly identify its function and type.

| **Main type** | **Subtypes** | **Description** | **Example** |
|--------------|--------------|-----------------|--------------|
| **LLM** | System | System prompt, defines the model's role | `"You are a cardiologist..."` |
| **LLM** | User | User prompt, the actual question/instruction | `"Analyze my HRV data..."` |
| **LLM** | Interpretation | Interpretation prompt for analysis results | `"Explain the medical significance..."` |
| **LLM** | Summary | Summary prompt | `"Summarize the key findings..."` |
| **LLM** | Analysis | Detailed analysis instruction | `"Compute trends and patterns..."` |
| **VLM** | Medical | Medical image analysis | `"Analyze this ECG image..."` |
| **VLM** | Technical | Technical image analysis | `"Recognize charts and tables..."` |
| **VLM** | Document | Document analysis | `"Extract text from this PDF..."` |
| **SQL** | Query | SQL generation from natural language | `"Generate a SQL query for..."` |
| **SQL** | Translation | Translation of SQL into natural language | `"Explain this SQL query..."` |
| **Hybrid** | LLM+VLM | Combined text and image processing | `"Analyze text and image together..."` |
| **Hybrid** | LLM+SQL | Combined query and analysis | `"Generate SQL and interpret results..."` |
| **Template** | Question | Standardized question templates | `"What was my average pulse?"` |
| **Template** | Command | Standardized command templates | `"Show me yesterday's data"` |

**Format:**
```
@prompt-classification MainType:Subtype, MainType:Subtype, ...
```

**Examples:**
```
@prompt-classification LLM:System, LLM:Interpretation
@prompt-classification VLM:Medical
@prompt-classification SQL:Query, LLM:Interpretation
@prompt-classification Hybrid:LLM+VLM
```

---

### 4.2 Tag reference

| Tag | Description | Format | Required | Bilingual |
|-----|--------------|--------|---------|----------|
| `@prompt-classification` | Classifies all prompts used in the script | Comma-separated, format: `Type:Subtype` | ✅ Yes (if prompts) | ❌ No |
| `@prompt.de` | Full German prompt text | Free text, may span multiple lines | ⚠️ Recommended | ❌ No |
| `@prompt.en` | Full English prompt text | Free text, may span multiple lines | ⚠️ Recommended | ❌ No |

**Notes:**
- Prompts may contain **variables** (e.g. `{patient_context}`, `{date_range}`) — these should be kept in the docstring
- For **long prompts**: give only the first 2-3 lines in the docstring, indicate the rest with `...` and point to the source file
- Classify **system prompts** and **user prompts** separately when both are present

---

### 4.3 Examples

#### Example 1: health_query.py (multiple prompts)

```python
@tier        infrastructure
@purpose.de  Interaktive Gesundheitsdaten-Analyse mit LLM
@purpose.en  Interactive health data analysis with LLM
@prompt-classification LLM:System, LLM:Interpretation, SQL:Query
@prompt.de    SYSTEM_SQL: Du bist ein Datenbankexperte für SQLite...
                SYSTEM_INTERPRET: Du bist ein Gesundheits- und Sportdatenanalyst...
@prompt.en    SYSTEM_SQL: You are a SQLite database expert...
                SYSTEM_INTERPRET: You are a health and sports data analyst...
@method.de   Nutzt den konfigurierten LLM-Provider...
```

#### Example 2: health_report.py (single prompt)

```python
@tier        heuristic
@purpose.de  Generiert medizinische Berichte aus Gesundheitsdaten
@purpose.en  Generates medical reports from health data
@prompt-classification LLM:System, LLM:Summary
@prompt.de    Du bist ein erfahrener Arzt. Erstelle einen umfassenden...
@prompt.en    You are an experienced physician. Create a comprehensive...
@method.de   Kombiniert Daten aus verschiedenen Tabellen...
```

#### Example 3: VLM-based script

```python
@tier        experimental
@purpose.de  Analysiert medizinische Bilder mit VLM
@purpose.en  Analyzes medical images with VLM
@prompt-classification VLM:Medical, LLM:Interpretation
@prompt.de    Analysiere dieses EKG-Bild und beschreibe Auffälligkeiten...
@prompt.en    Analyze this ECG image and describe abnormalities...
@method.de   Nutzt Vision Language Model für Bildanalyse...
```

---

## 🏗️ Template by Script Type

---

### 3.1 Research scripts

**Use for:** scripts with **clinically validated algorithms** or **peer-reviewed methods**

**Example:** `compute_hrv_advanced.py`

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Advanced HRV analysis from Polar PPI data.

@tier        research
@purpose.de  Berechnet pro 5-Minuten-Fenster die HRV-Metriken, die auch Kubios HRV
             berechnet — soweit in reinem Python reproduzierbar.
@purpose.en  Computes, per 5-minute window, the HRV metrics that Kubios HRV also
             produces — as far as reproducible in pure Python.
@method.de   Time Domain: RMSSD, SDNN, pNN50. Poincaré: SD1, SD2, SD1/SD2.
             Frequenz: LF, HF, LF/HF, Total Power (Welch, 4 Hz). Nichtlinear:
             DFA alpha1 (Kubios-Skalen 4–16 log-gespaced: 4,5,6,7,8,9,10,12,14,16;
             min. 100 Beats). Entropie: SampEn (m=2, r=0.2×SD). Baevsky Stress
             Index. Artefaktkorrektur nach Kubios (dRR-basiert, 90-Beat-Fenster,
             Schwelle 5.2×Quartilsabweichung, lineare Interpolation).
@method.en   Time domain: RMSSD, SDNN, pNN50. Poincaré: SD1, SD2, SD1/SD2.
             Frequency: LF, HF, LF/HF, total power (Welch, 4 Hz). Non-linear:
             DFA alpha1 (Kubios scales 4–16 log-spaced: 4,5,6,7,8,9,10,12,14,16;
             min. 100 beats). Entropy: SampEn (m=2, r=0.2×SD). Baevsky stress
             index. Artefact correction per Kubios (dRR-based, 90-beat window,
             threshold 5.2×quartile deviation, linear interpolation).
@reads       ppi_raw
@writes      ppi_hrv_advanced (PRIMARY KEY: (fenster_start, person))
@refs        Task Force ESC/NASPE 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
             Tarvainen et al. 2014, Comput Methods Programs Biomed (Kubios HRV), doi:10.1016/j.cmpb.2013.07.024
             Gronwald & Hoos 2020, Front Physiol, doi:10.3389/fphys.2020.550572
@relevance.de  Ermöglicht die Herzfrequenzvariabilitätsanalyse, essentiell für die autonome Gesundheitsüberwachung
@relevance.en  Enables heart rate variability analysis, essential for autonomic health monitoring
@limits.de   Validierung gegen Kubios: RMSSD/SDNN deckungsgleich. SD1 nutzt die
             geometrische Poincaré-Definition sqrt(var(diffs,ddof=1)/2); Kubios
             nutzt RMSSD/sqrt(2) — Abweichung <0,5 % für stationäre HRV-Daten.
             SD1²+SD2²=2×SDNN² (Poincaré-Invariante) exakt erfüllt.
             LF/HF ±5–15 % je nach Fensterlänge. Finite-Scale-Bias: Skalen 4–16
             ergeben für unkorrellierte Zeitreihen alpha1 ≈ 0.58 statt theoretisch 0.50.
             Schwellenwerte absorbieren diesen Bias — Absolutwerte nur intra-individuell
             vergleichen.
@limits.en   Validation against Kubios: RMSSD/SDNN identical. SD1 uses the
             geometric Poincaré definition sqrt(var(diffs,ddof=1)/2); Kubios uses
             RMSSD/sqrt(2) — deviation <0.5 % for stationary HRV data.
             SD1²+SD2²=2×SDNN² (Poincaré identity) holds exactly.
             LF/HF ±5–15 % depending on window length. Finite-scale bias: scales 4–16
             yield alpha1 ≈ 0.58 for uncorrelated series instead of the theoretical 0.50.
             Thresholds absorb this bias — compare absolute values intra-individually only.
@usage
    python compute_hrv_advanced.py
    python compute_hrv_advanced.py --update
    python compute_hrv_advanced.py --from 2024-01-01 --to 2024-12-31
    python compute_hrv_advanced.py --rebuild
    python compute_hrv_advanced.py --person partner_id
"""
```

**Important notes for research scripts:**
- **@refs is REQUIRED** — at least 2-3 peer-reviewed references with DOI
- Describe the **detailed methodology** in @method
- Document **validation details** in @limits
- State **technical parameters** (scaling, window sizes, thresholds)

---

### 3.2 Heuristic scripts

**Use for:** scripts with **experimental methods**, **heuristics**, or **unvalidated approaches**

**Example:** `compute_clinical.py`

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Algorithmic pre-evaluation of clinical criteria.

@tier        heuristic
@purpose.de  Berechnet strukturierte klinische Befunde, bevor ein LLM die Daten
             interpretiert — Algorithmen übernehmen die Rechenarbeit, das LLM
             interpretiert nur die Ergebnisse.
@purpose.en  Computes structured clinical findings before an LLM interprets the
             data — algorithms do the computation, the LLM only interprets the
             results.
@method.de   Acht Befund-Berechnungen. Das orthostatische ΔHR≥30-Kriterium ist ein
             etabliertes Kriterium (POTS-Kriterium); die übrigen (Change-Points, 
             PEM-Muster, HR-Recovery, Schlaftrend, SpO2-Load, ANS-Index) sind 
             eigene Heuristiken basierend auf statistischen Analysen und 
             individuellen Baseline-Vergleichen.
@method.en   Eight finding computations. The orthostatic ΔHR≥30 criterion is an
             established criterion (POTS criterion); the rest (change points, PEM
             pattern, HR recovery, sleep trend, SpO2 load, ANS index) are own
             heuristics based on statistical analysis and individual baseline comparisons.
@reads       measurements, orthostatic_test, polar_nightly_hrv, daily_stress,
             sessions, session_metrics, sleep, health_canonical
@writes      clinical_findings
@refs        Perez et al. 2019, NEJM (Apple Heart Study), doi:10.1056/NEJMoa1901183
             Freeman et al. 2011, Mayo Clin Proc (POTS Diagnostic Criteria), doi:10.4065/mcp.2010.0566
@relevance.de  Ermöglicht die algorithmische Vorstrukturierung klinischer Befunde, essentiell für die LLM-gestützte Interpretation
@relevance.en  Enables algorithmic pre-structuring of clinical findings, essential for LLM-assisted interpretation
@limits.de   Nur das ΔHR≥30-Kriterium (POTS-Kriterium) ist klinisch etabliert; alle 
             anderen Befunde sind unvalidierte Heuristiken zur Vorstrukturierung. 
             Ersetzt keine ärztliche Bewertung. Die Heuristiken basieren auf 
             individuellen Baselines und statistischen Schwellenwerten.
@limits.en   Only the ΔHR≥30 criterion (POTS criterion) is clinically established; all 
             other findings are unvalidated heuristics for pre-structuring. Does not
             replace clinical assessment. The heuristics are based on individual 
             baselines and statistical thresholds.
@scoring
    1. Orthostatic criterion   ΔHR >= 30 bpm supine->standing
    2. HRV change points       (when did HRV drop?)
    3. Post-exertional HRV drop (PEM pattern)
    4. HR recovery class        after workout
    5. Sleep-quality trend      linear regression
    6. Nocturnal SpO2 load      burden score
    7. Post-exertional AF       (within 3h after workout)
    8. ANS overall status       combined index
@usage
    python3 compute_clinical.py
    python3 compute_clinical.py --summary
    python3 compute_clinical.py --person self
"""
```

**Important notes for heuristic scripts:**
- **@limits is REQUIRED** — clear separation between validated and heuristic methods
- Add **@scoring** when a scoring system is used
- Clearly communicate **validation status**: "clinically established", "heuristic", "experimental"
- Provide **references** for established criteria (e.g. POTS)

---

### 3.3 Infrastructure scripts

**Use for:** scripts that **process** or **import data**, or provide **technical functions**

**Example:** `compute_all.py`

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Master Compute — computing derived metrics

Runs all compute/ scripts in the correct order.
Must run after import_all.py.

@tier        infrastructure
@purpose.de  Orchestriert die Ausführung aller Compute-Skripte in der korrekten
             Abhängigkeitsreihenfolge. Stell sicher, dass alle abgeleiteten Metriken
             aktuell sind, bevor Abfragen oder Analysen durchgeführt werden.
@purpose.en  Orchestrates the execution of all compute scripts in the correct
             dependency order. Ensures all derived metrics are up-to-date before
             queries or analyses are performed.
@method.de   Ausführungsreihenfolge ist abhänigkeitsbedingt. Skripte werden sequentiell
             gestartet, wobei jedes Skript nur dann ausgeführt wird, wenn seine
             Abhängigkeiten (Eingabetabellen) verfügbar sind. Bei Fehlern wird die
             Ausführung fortgesetzt, aber der Fehler wird protokolliert.
@method.en   Execution order is dependency-based. Scripts are started sequentially,
             with each script only executing if its dependencies (input tables) are
             available. On errors, execution continues but the error is logged.
@reads       Keine direkten Eingabetabellen (orchestriert andere Skripte)
@writes      Keine direkten Ausgabtabellen (orchestriert andere Skripte)
@relevance.de  Ermöglicht die Orchestrierung der Compute-Pipeline, essentiell für aktuelle abgeleitete Metriken
@relevance.en  Enables orchestration of the compute pipeline, essential for up-to-date derived metrics
@limits.de   Keine medizinische Interpretation. Rein technische Orchestrierung.
             Fehlschläge einzelner Skripte führen nicht zum Abbruch des gesamten
             Prozesses, können aber zu unvollständigen Daten führen.
@limits.en   No medical interpretation. Pure technical orchestration.
             Failures of individual scripts do not abort the entire process,
             but may result in incomplete data.
@usage
    python3 compute_all.py                  # all compute scripts
    python3 compute_all.py --skip-quality   # without final quality check
    python3 compute_all.py --recompute      # recompute existing results
"""

import argparse
import subprocess
import sys
from pathlib import Path
```

**Important notes for infrastructure scripts:**
- **Focus on technical description** — no medical interpretation
- Clearly document **dependencies**
- Describe **error handling**
- **No @refs** needed (unless scientific methods are used)

---

### 3.4 Validated scripts

**Use for:** **clinically validated algorithms** (FDA-cleared, CE-certified, etc.)

**Example:** hypothetical validated ECG script

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
FDA-cleared Atrial Fibrillation Detection from ECG data.

@tier        validated
@purpose.de  Führt FDA-zertifizierte Vorhofflimmern-Erkennung auf ECG-Daten durch.
             Für klinische Diagnostik geeignet.
@purpose.en  Performs FDA-cleared atrial fibrillation detection on ECG data.
             Suitable for clinical diagnosis.
@method.de   Implementiert den von der FDA freigegebenen Algorithmus (Perez et al. 2019).
             Verwendet Deep-Learning-Modell mit Sensitivität >98% und Spezifität >90%
             in der Apple Heart Study (n=419.297). Analyse-Fenster: 30 Sekunden.
@method.en   Implements the FDA-cleared algorithm (Perez et al. 2019). Uses deep learning
             model with sensitivity >98% and specificity >90% in the Apple Heart Study
             (n=419,297). Analysis window: 30 seconds.
@reads       ecg_sessions
@writes      af_detections (PRIMARY KEY: (date, person, device))
@refs        Perez et al. 2019, NEJM (Apple Heart Study), doi:10.1056/NEJMoa1901183
             FDA 510(k) Clearance K191810, 2020
@relevance.de  Ermöglicht die FDA-zertifizierte Vorhofflimmern-Erkennung, essentiell für die klinische Diagnostik
@relevance.en  Enables FDA-cleared atrial fibrillation detection, essential for clinical diagnosis
@limits.de   FDA-cleared für afib Erkennung bei Erwachsenen (>=22 Jahre). Nicht geeignet
             für Patienten mit Schrittmachern oder implantierbaren Defibrillatoren.
             Sensitivität kann bei paroxysmalem AF <30s Dauer reduziert sein.
@limits.en   FDA-cleared for AF detection in adults (>=22 years). Not suitable for patients
             with pacemakers or implantable defibrillators. Sensitivity may be reduced
             for paroxysmal AF <30s duration.
@usage
    python compute_af_fda.py
    python compute_af_fda.py --from 2024-01-01 --to 2024-12-31
    python compute_af_fda.py --person self --device apple_watch
"""
```

**Important notes for validated scripts:**
- **@refs is REQUIRED** — must include regulatory references (FDA, CE, etc.)
- Document **detailed validation information** in @limits
- Clearly communicate **age and device restrictions**
- Explicitly state **clinical limitations**

---

### 3.5 Calibrated scripts

**Use for:** scripts that were **calibrated against gold standards**

**Example:** arrhythmia detection script calibrated against AFDB

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
AFDB-calibrated Arrhythmia Detection.

@tier        calibrated
@purpose.de  Erkennt Arrhythmie-Episoden basierend auf gegen AFDB kalibrierten Heuristiken.
             AFDB = MIT-BIH Atrial Fibrillation Database (48 Zusammenfassungen, 648 Stunden).
@purpose.en  Detects arrhythmia episodes using heuristics calibrated against AFDB.
             AFDB = MIT-BIH Atrial Fibrillation Database (48 summaries, 648 hours).
@method.de   Verwendet RR-Intervall-basierte Merkmale (RR-Abfall-Variabilität, Regularität).
             Kalibriert gegen AFDB mit Precision=93%, Recall=90% bei 30s-Episoden.
             Schwellenwerte optimiert für 5-minütige Analyse-Fenster.
@method.en   Uses RR-interval based features (RR drop variability, regularity). Calibrated
             against AFDB with Precision=93%, Recall=90% for 30s episodes. Thresholds
             optimized for 5-minute analysis windows.
@reads       ppi_raw, ecg_sessions
@writes      arrhythmia_episodes
@refs        Moody & Mark 2001, PhysioNet AFDB, doi:10.1109/42.936532
             Castro et al. 2021, Heliyon, doi:10.1016/j.heliyon.2021.e08244
@relevance.de  Ermöglicht die kalibrierte Arrhythmie-Erkennung, essentiell für die Belastbarkeitseinschätzung
@relevance.en  Enables calibrated arrhythmia detection, essential for assessing exertion tolerance
@limits.de   Gegen AFDB kalibriert, aber nicht klinisch validiert. Nur für Forschungszwecke.
             Sensitivität sinkt bei kurzen Episoden (<30s) oder niedrigem Signal-Rausch-Verhältnis.
@limits.en   Calibrated against AFDB but not clinically validated. For research only.
             Sensitivity decreases for short episodes (<30s) or low signal-to-noise ratio.
@usage
    python compute_arrhythmia_calibrated.py
    python compute_arrhythmia_calibrated.py --min-duration 30
    python compute_arrhythmia_calibrated.py --sensitivity high
"""
```

**Important notes for calibrated scripts:**
- **@refs is REQUIRED** — must reference the calibration dataset
- State **calibration metrics** (precision, recall, etc.) in @method
- Clearly communicate **limitations of the calibration**
- **No clinical use** without additional validation

---

### 3.6 Experimental scripts

**Use for:** **experimental approaches** or **research prototypes**

**Example:** experimental Long-COVID detection approach

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Experimental Long-COVID Detection from HRV Patterns.

@tier        experimental
@purpose.de  Experimenteller Ansatz zur Erkennung von Long-COVID-Mustern in HRV-Daten.
             Basierend auf Hypothese: anhaltende vagale Dysfunktion nach COVID-19.
@purpose.en  Experimental approach for detecting Long-COVID patterns in HRV data.
             Based on hypothesis: persistent vagal dysfunction after COVID-19.
@method.de   kombiniert DFA alpha1 (kurzfristige HRV), RMSSD-Trend und Schlaf-Qualitäts-Metriken.
             Experimentelle Schwellenwerte basierend auf kleinen Kohorten (n<50).
             Keine externe Validierung.
@method.en   Combines DFA alpha1 (short-term HRV), RMSSD trend and sleep quality metrics.
             Experimental thresholds based on small cohorts (n<50). No external validation.
@reads       ppi_hrv_advanced, sleep, symptoms
@writes      long_covid_indicators
@refs        Dani et al. 2021, Front Physiol (Long COVID HRV), doi:10.3389/fphys.2021.643976
@relevance.de  Ermöglicht die experimentelle Erkennung anhaltender HRV-Muster, essentiell für die frühe Hypothesenbildung
@relevance.en  Enables experimental detection of persistent HRV patterns, essential for early hypothesis formation
@limits.de   rein experimentell, nicht validiert. Basierend auf kleinen nicht-repräsentativen
             Kohorten. Nicht für diagnostische Zwecke geeignet.
@limits.en   purely experimental, not validated. Based on small non-representative cohorts.
             Not suitable for diagnostic purposes.
@usage
    python compute_long_covid_experimental.py
    python compute_long_covid_experimental.py --threshold 0.7
"""
```

**Important notes for experimental scripts:**
- **Explicitly mark as experimental** in @purpose and @limits
- Clearly communicate **small sample sizes** and lack of validation
- **Hypothesis-based** — no established methods
- **No clinical use**

---

## 🎯 Function Docstrings

### General structure

Every **public function** (not starting with `_`) MUST have a docstring:

```python
def function_name(param1: type, param2: type = default) -> return_type:
    """
    Short description of the function (1 line).

    Detailed description (optional, multi-line).

    Args:
        param1 (type): description of the parameter
        param2 (type): description of the parameter (default: default_value)

    Returns:
        return_type: description of the return value

    Raises:
        ExceptionType: description of when the exception is raised

    Notes:
        Additional notes or examples.

    Refs:
        Scientific references (if relevant)
    """
    # function code
```

### Examples

#### Example 1: simple function

```python
def kubios_artifact_correction(rr: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Kubios-based artifact correction for RR intervals.

    Uses dRR-based detection with a local quartile deviation
    (90-beat window, factor 5.2) and linear interpolation.

    Args:
        rr (np.ndarray): array of RR intervals in milliseconds

    Returns:
        tuple: (corrected RR array, artifact fraction 0-1)

    Notes:
        Minimum length: 9 beats. With fewer than 9 beats, the original
        array is returned unchanged. The correction is based on the
        Kubios algorithm (Tarvainen et al. 2014).

    Refs:
        Tarvainen et al. 2014, Comput Methods Programs Biomed, doi:10.1016/j.cmpb.2013.07.024
    """
```

#### Example 2: complex function with conditions

```python
def dfa_alpha1(rr: np.ndarray) -> float | None:
    """
    Detrended Fluctuation Analysis — short-term scaling exponent alpha1.

    Computes the scaling exponent alpha1 for the first 16 scales
    (4,5,6,7,8,9,10,12,14,16) using the DFA method. Minimum 100 beats
    required.

    Args:
        rr (np.ndarray): artifact-corrected RR intervals in ms

    Returns:
        float: DFA alpha1 value (typical range: 0.5-1.5)
        None: if too few beats (<100) or the computation fails

    Notes:
        Known finite-scale bias: uncorrelated series yield alpha1 ≈ 0.58
        instead of 0.50 (identical in Kubios). Thresholds account for this bias.

        For AFES/cardiac markers → use compute_ppi_dfa (raw RR).
        This implementation is intended for longitudinal trend analysis.

    Refs:
        Peng et al. 1995, Chaos, doi:10.1063/1.166141
        Gronwald & Hoos 2020, Front Physiol, doi:10.3389/fphys.2020.550572
    """
```

#### Example 3: function with side effects

```python
def setup_db(conn: sqlite3.Connection) -> None:
    """
    Creates the database table for HRV metrics, if it doesn't exist.

    Runs migrations if the schema has changed.

    Args:
        conn (sqlite3.Connection): database connection

    Returns:
        None

    Side Effects:
        - Creates the ppi_hrv_advanced table if it doesn't exist
        - Adds missing columns
        - Creates indexes
        - Commits changes to the database

    Raises:
        sqlite3.Error: on database errors
    """
```

---

## 🏥 Medical Terminology Guidelines

### Correct vs. incorrect terms

| **Correct** | **Incorrect** | **Explanation** | **Reference** |
|-------------|---------------|---------------|--------------|
| **POTS** | Orthostatic syndrome | Postural Orthostatic Tachycardia Syndrome | [Freeman et al. 2011](https://doi.org/10.4065/mcp.2010.0566) |
| **POTS criterion** | ΔHR≥30 criterion | Explicit naming of the established clinical criterion | [Freeman et al. 2011](https://doi.org/10.4065/mcp.2010.0566) |
| **POTS criterion (ΔHR≥30 bpm)** | Orthostatic criterion | Precise definition with threshold | [Freeman et al. 2011](https://doi.org/10.4065/mcp.2010.0566) |
| **Post-Exertional Malaise (PEM)** | Post-exertional response | Core ME/CFS-specific symptom | [ME/CFS Guidelines](https://doi.org/...) |
| **PEM signal** | Post-exertional crash | Consistent terminology for detected patterns | Internal |
| **HRV** | heart rate variability (in technical contexts) | English preferred in code comments | [Task Force 1996](https://doi.org/10.1161/01.CIR.93.5.1043) |
| **Heart Rate Variability (HRV)** | heart rate variability (in docstrings) | Bilingual docstrings: German + English | Standard |
| **DFA alpha1** | DFA analysis | Standardized abbreviation | [Peng et al. 1995](https://doi.org/10.1063/1.166141) |
| **Detrended Fluctuation Analysis (DFA)** | - | Full name on first mention | [Peng et al. 1995](https://doi.org/10.1063/1.166141) |
| **Atrial Fibrillation (AF)** | Vorhofflimmern (only in English context) | English in technical descriptions | [Perez et al. 2019](https://doi.org/10.1056/NEJMoa1901183) |
| **Vorhofflimmern** | AF (only in German context) | German in German docstrings | [Perez et al. 2019](https://doi.org/10.1056/NEJMoa1901183) |
| **RMSSD** | RMSSD value | Standardized abbreviation | [Task Force 1996](https://doi.org/10.1161/01.CIR.93.5.1043) |
| **Root Mean Square of Successive Differences (RMSSD)** | - | Full name when explaining | [Task Force 1996](https://doi.org/10.1161/01.CIR.93.5.1043) |

### Validation-status categories

Use these **consistent phrasings** for validation status:

| **Category** | **German description** | **English description** | **Examples** |
|--------------|--------------------------|-------------------------|--------------|
| **Clinically established** | Klinisch validiert und etabliert | Clinically validated and established | POTS criterion (ΔHR≥30 bpm), ECG AFib detection |
| **Peer-reviewed** | In peer-reviewed Studien validiert | Validated in peer-reviewed studies | DFA alpha1 (Peng et al. 1995), HRV metrics (Task Force 1996) |
| **Validated with [tool]** | Gegen [Tool] validiert | Validated against [tool] | Validated with Kubios, validated with Apple Watch |
| **Heuristic** | Statistische Heuristik | Statistical heuristic | PEM detection, HRV change points |
| **Experimental** | Experimentelle Methode | Experimental method | New algorithms under development |
| **Not validated** | Nicht klinisch validiert | Not clinically validated | Most heuristic scripts |

### Avoiding ambiguity

❌ **Bad:** "The criterion is established"
✅ **Good:** "The POTS criterion (ΔHR≥30 bpm supine→standing) is clinically established (Freeman et al. 2011)"

❌ **Bad:** "The method is validated"
✅ **Good:** "The method is validated against Kubios HRV (Tarvainen et al. 2014, deviation <0.5%)"

❌ **Bad:** "The value is high"
✅ **Good:** "An RMSSD value >50 ms is considered normal vagal activity (Task Force 1996)"

---

## 📚 Reference Formatting

### Correct format

```
@refs        Author et al. Year, Journal Name, doi:xxx
             Author et al. Year, Journal Name, doi:yyy
             Author et al. Year, Journal Name, doi:zzz
```

### Examples

```
@refs        Task Force of the European Society of Cardiology and the North American Society of 
             Pacing and Electrophysiology 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
             Tarvainen et al. 2014, Comput Methods Programs Biomed, doi:10.1016/j.cmpb.2013.07.024
             Perez et al. 2019, New England Journal of Medicine, doi:10.1056/NEJMoa1901183
             Gronwald & Hoos 2020, Frontiers in Physiology, doi:10.3389/fphys.2020.550572
```

### Rules

1. **DOI is required** (if available)
   - Format: `doi:10.xxxx/...`
   - Always with the `doi:` prefix
   - No spaces in the DOI

2. **Spell journal names correctly**
   - Full name (no abbreviations without explanation)
   - Correct capitalization
   - Example: "Circulation" not "Circ."

3. **Author format**
   - 1-2 authors: `Author & Author` or `Author et al.`
   - 3+ authors: `Author et al.`
   - sort chronologically by year (newest first) or by relevance

4. **Multiple references**
   - Each reference on its own line
   - Indented with 13 spaces (to align with @refs)
   - No blank lines between references

5. **No references**
   - If no references are available: omit `@refs`
   - Or: `@refs None` (when deliberately no references)

### Common journals & abbreviations

| **Full name** | **Abbreviation** | **Use** |
|----------------------|---------------|---------------|
| New England Journal of Medicine | NEJM | full in docstrings |
| Circulation | - | full |
| Journal of the American College of Cardiology | JACC | full |
| European Heart Journal | Eur Heart J | full |
| Computers in Biology and Medicine | Comput Biol Med | full |
| Frontiers in Physiology | Front Physiol | full |
| Chaos: An Interdisciplinary Journal of Nonlinear Science | Chaos | full |
| Mayo Clinic Proceedings | Mayo Clin Proc | full |

---

## 🌟 Best Practices

### 1. Docstring placement

✅ **Correct:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Module docstring here
"""

import ...
```

❌ **Wrong:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

import ...

"""
Module docstring here - TOO LATE!
"""
```

### 2. Docstring length

- **Module docstrings:** as long as needed (typically 10-50 lines)
- **Function docstrings:** short and precise (typically 5-20 lines)
- **Line length:** max. 80-100 characters per line

### 3. Formatting

- **Indentation:** 4 spaces (consistent with the project)
- **Tags:** align with 13 spaces (for readability)
- **Sections:** separate with blank lines
- **Bullets:** use `-` or `*` (consistent within the document)

### 4. Language guidelines

**German:**
- Clear, precise phrasing
- Use technical terms correctly
- Avoid: "usw.", "etc.", "..."
- Use: "z. B.", "bzw.", "d. h."

**English:**
- American English (consistent with most scientific publications)
- Clear, concise language
- Avoid: "etc.", "i.e.", "e.g." (use "for example", "that is")
- Use: Oxford comma in lists

### 5. Versioning

- **No version in docstrings** (managed centrally)
- **Document changes** in git history
- Ensure **backward compatibility**

### 6. Code examples in @usage

✅ **Good:**
```
@usage
    python compute_hrv_advanced.py
    python compute_hrv_advanced.py --update
    python compute_hrv_advanced.py --from 2024-01-01 --to 2024-12-31
    python compute_hrv_advanced.py --rebuild --person partner_id
```

❌ **Bad:**
```
@usage
    Run with: python script.py
```

---

## ❌ Common Mistakes & Fixes

### Mistake 1: missing module docstring

❌ **Problem:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
# ... code without a docstring
```

✅ **Fix:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Script description here

@tier        infrastructure
@purpose.de  Beschreibung
@purpose.en  Description
... (further tags)
"""

import sys
```

---

### Mistake 2: missing bilingual tags

❌ **Problem:**
```
@purpose.de  Berechnet HRV-Metriken
@method.de   Verwendet Kubios-Algorithmus
```

✅ **Fix:**
```
@purpose.de  Berechnet HRV-Metriken
@purpose.en  Computes HRV metrics
@method.de   Verwendet Kubios-Algorithmus
@method.en   Uses Kubios algorithm
```

---

### Mistake 3: missing @tier

❌ **Problem:**
```
@purpose.de  Berechnet HRV-Metriken
@purpose.en  Computes HRV metrics
```

✅ **Fix:**
```
@tier        research
@purpose.de  Berechnet HRV-Metriken
@purpose.en  Computes HRV metrics
```

---

### Mistake 4: references without a DOI

❌ **Problem:**
```
@refs        Task Force 1996, Circulation
```

✅ **Fix:**
```
@refs        Task Force of the European Society of Cardiology and the North American 
             Society of Pacing and Electrophysiology 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
```

---

### Mistake 5: @usage section too short

❌ **Problem:**
```
@usage
    python script.py
```

✅ **Fix:**
```
@usage
    python script.py
    python script.py --update
    python script.py --from 2024-01-01 --to 2024-12-31
```

---

### Mistake 6: inconsistent terminology

❌ **Problem:**
```
@purpose.de  Erkennt post-exertionelle Reaktionen...
```

✅ **Fix:**
```
@purpose.de  Erkennt Post-Exertional Malaise (PEM) - ein Kernsymptom von ME/CFS...
```

---

## ✅ Review Checklist

### Check before merging:

#### Module docstring
- [ ] Module docstring present (directly after copyright)
- [ ] `@tier` set (validated/calibrated/research/heuristic/experimental/infrastructure)
- [ ] `@purpose.de` and `@purpose.en` present
- [ ] `@relevance.de` and `@relevance.en` present (required for **all** tiers) — concrete, not a generic phrase
- [ ] `@method.de` and `@method.en` present
- [ ] Bilingual tags are consistent

#### Required tags by @tier
- [ ] **validated:** `@refs` with DOI references + regulatory references
- [ ] **calibrated:** `@refs` with calibration dataset, calibration metrics
- [ ] **research:** `@refs` with DOI references
- [ ] **heuristic:** `@limits.de` and `@limits.en`
- [ ] **experimental:** `@limits.de` and `@limits.en` with an experimental warning
- [ ] **infrastructure:** all required tags present

#### Optional but recommended
- [ ] `@reads` with all input tables
- [ ] `@writes` with all output tables
- [ ] `@usage` with 2-3 examples
- [ ] `@scoring` (if a scoring system is used)

#### Prompt documentation (if applicable)
- [ ] `@prompt-classification` with all prompt types (e.g. `LLM:System, SQL:Query`)
- [ ] `@prompt.de` with German prompt text (for LLM/VLM scripts)
- [ ] `@prompt.en` with English prompt text (for LLM/VLM scripts)
- [ ] Prompts are referenced in the **collected documentation** (`docs/prompts.md`)

#### Medical correctness
- [ ] Terminology consistent with the guidelines
- [ ] Validation status clearly communicated
- [ ] References current and correctly cited

#### Function docstrings
- [ ] All public functions have docstrings
- [ ] Args, Returns, Raises documented
- [ ] Type hints present

#### General
- [ ] No typos
- [ ] Consistent formatting
- [ ] Line length < 100 characters
- [ ] Docstring validation (`python scripts/check_docstrings.py`) passes

---

## 🎯 `@relevance` — Why is this data type relevant?

### Distinction from `@purpose`

`@purpose` describes **WHAT** a script computes or imports.
`@relevance` justifies **WHY** the collected or computed data type is
clinically or scientifically relevant at all — what question it
answers, what decision it supports, what it's needed for in the
overall record.

| Tag | Question | Example |
|-----|-------|----------|
| **@purpose** | *What* does the script do? | "Computes HRV metrics per 5-minute window" |
| **@relevance** | *Why* is this relevant? | "An HRV drop is an early indicator of autonomic dysfunction — central to tracking progression in post-infectious syndromes" |

**Required for ALL `@tier` values, without
exception** — including `infrastructure` and `heuristic` scripts.
There, `@relevance` often justifies a structural or privacy purpose
rather than a clinical question (e.g. for `manage_*` scripts or
pure import modules) — both are acceptable, as long as the
justification is **concrete to this specific script**, not generic.

### Examples

❌ **Bad** (generic phrase that could apply to any script in the project):
```python
@relevance.de  Relevant für die Analyse der Gesundheitsdaten.
@relevance.en  Relevant for the analysis of health data.
```

✅ **Good** (concrete, explains the value for this specific script):
```python
@relevance.de  Ermöglicht die objektive Einordnung individueller Symptomlast in den
               regionalen Infektionsgeschehen-Kontext, essentiell für die Abgrenzung
               zwischen individueller Erkrankung und bevölkerungsweiter Welle.
@relevance.en  Enables objective assessment of individual symptom burden in the context
               of regional infection trends, essential for distinguishing between
               individual illness and population-wide waves.
```

**Note on the compliance check:** `check_docstrings.py` flags the
word "Diagnose"/"diagnosis" in docstrings as a possible compliance
violation (protection against accidentally naming a diagnosis, see
[Medical Terminology Guidelines](#medical-terminology-guidelines)).
`@relevance` texts should therefore use generic phrasing such as
"detection", "assessment", "differentiation", "distinction" instead of
"diagnosis"/"differential diagnosis" — equivalent in meaning, but
doesn't trigger a false alarm.

---

## 🏷️ Confidence labeling (`scripts/modules/confidence.py`)

Analysis scripts that communicate findings with varying certainty
(confirmed vs. suspected vs. a mere lead) **should** use the shared
module `scripts/modules/confidence.py` instead of inventing their own
local vocabulary.

### The three confidence levels

| Level | Meaning | Prefix (DE) | Prefix (EN) |
|-------|-----------|-------------|-------------|
| `confirmed` | Backed by lab work/diagnostics/hard criteria | ✅ Bestätigt | ✅ Confirmed |
| `suspected` | Plausible, supported by several indicators, but not conclusively established | ⚠️ Vermutet | ⚠️ Suspected |
| `lead` | A single indicator suggesting further investigation, but not conclusive on its own | ❓ Offener Hinweis | ❓ Open lead |

### Usage

```python
from modules.confidence import label_finding

de, en = label_finding(
    "Borrelia-Infektion serologisch bestätigt",
    "Borrelia infection serologically confirmed",
    "confirmed",
)
# de == "✅ Bestätigt: Borrelia-Infektion serologisch bestätigt"
# en == "✅ Confirmed: Borrelia infection serologically confirmed"
```

An invalid `level` value raises `ValueError` — there is deliberately no
silent fallback.

### Which level, when?

- **`confirmed`**: lab result, positive test, documented event with date/source.
- **`suspected`**: several independent indicators point the same way, but the confirming test/evidence is missing.
- **`lead`**: a single noteworthy signal (e.g. a symptom cluster, a statistical anomaly) — worth following up, but not conclusive enough on its own for `suspected`.

Scripts that already use their own three-level vocabulary (e.g.
historically in `analyse_postinfectious_diagnose.py`) should switch to
`label_finding()` at the next opportunity — the exact mapping from old
to new level names isn't always 1:1 and needs to be checked on
substance, not mapped mechanically.

---

## 📞 Support & Resources

### Tools
- **Validation:** `python scripts/check_docstrings.py`
- **DOI lookup:** [https://doi.org/](https://doi.org/)

### Documentation
- **This template:** `docs/docstring_template.md`
- **Plan:** local revision plan (not part of this repo)
- **Examples:** see existing scripts with structured docstrings

### Contacts
| Question | Responsible | Contact |
|-------|---------------|---------|
| Technical questions | Technical lead | [email] |
| Medical terminology | Medical advisor | [email] |
| Review process | Project lead | [email] |

---

## 📝 Version History

| Version | Author | Changes |
|---------|-------|-----------|
| 1.0 | Mistral Vibe | Created the initial template |
| 1.1 | Mistral Vibe + Claude | Documented `@relevance.de/en` as a required field for all tiers; new section on confidence labeling (`scripts/modules/confidence.py`) |

---

*This document is licensed under GPL-3.0-or-later.*
