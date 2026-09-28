<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Urine Home Monitoring — Test Protocol

> **Deutsche Version:** [URINE_STRIP_PROTOCOL_DE.md](URINE_STRIP_PROTOCOL_DE.md)

**Device:** 12-parameter urine dipstick test
**Import:** `python3 scripts/importers/import_urine_strip.py my_urine_test.csv`
**Template:** `templates/urine_strip_template.csv`

---

## Standard protocol (routine)

**Frequency:** 1x/week, always the same weekday (e.g. Monday morning)
**Additionally:** on symptom flare-up, after an infection, before/after a doctor's appointment

### Preparation

1. **Vitamin C:** last supplement/ascorbic acid at least **4 hours before the test** — high vitamin C concentrations skew the blood and glucose result (false negative). If the ascorbic acid field shows `+` or `++`: interpret the blood and glucose result with caution.
2. **Urine:** use the first morning urine (most concentrated, highest sensitivity for protein and blood).
3. **Midstream technique:** let it run briefly first, then position the collection container in the stream — this minimizes contamination (vaginal flora, skin bacteria).
4. **Strip:** dip briefly in the urine (1-2 seconds), then lay on a clean, horizontal surface — don't blot the strip.

### Reading the result

- Read exactly per the manufacturer's timing (usually 30-60 seconds, varies by parameter)
- Read **in daylight** or good artificial light
- Use the reference color chart on the package
- Record all 12 fields, even if negative — missing values make trend analysis harder

### Recording (CSV entry)

```
Date,        Time,    Sample,    Volume_ml, Leu, Uro, Pro, Bil, Glu, Asc, SG,    Ket, Nit, Cre, pH,  Blood, Method,      Comment
2026-06-28,  07:30,   spot,      ,          neg, 0.2, neg, neg, neg, neg, 1.020, neg, neg, 100, 6.0, neg,   Home test,   Routine Mon
```

---

## Parameters — what they mean

This table gives examples of which conditions make each parameter especially relevant. It does not replace individual clinical interpretation.

| Parameter | Normal | Relevant among others for |
|---|---|---|
| Leukocytes | neg | Urinary tract infection vs. autoimmune nephritis (e.g. Sjögren's syndrome, lupus), tubulointerstitial nephritis |
| Urobilinogen | 0.2-1.0 mg/dl | Liver function (relevant in mast cell disorders, antiphospholipid syndrome) |
| Protein | neg | Autoimmune nephritis (Sjögren's, lupus), antiphospholipid syndrome nephropathy, tubular dysfunction |
| Bilirubin | neg | Liver involvement |
| Glucose | neg | Tubular reabsorption disorder (e.g. Sjögren-associated Fanconi syndrome), under GLP-1 receptor agonist therapy (e.g. semaglutide, tirzepatide) |
| Ascorbic acid | neg | Interpretation aid (skews blood/glucose result when high) |
| Specific gravity | 1.010-1.025 | Concentrating ability, hydration status |
| Ketones | neg | Monitoring under GLP-1 receptor agonist therapy (elevated ketosis risk from reduced caloric intake) |
| Nitrite | neg | Bacterial urinary tract infection (gram-negative organisms) |
| Creatinine | 20-370 mg/dl | Combined with protein → rough protein/creatinine ratio |
| pH | 5.0-8.0 | Renal tubular acidosis (classically in Sjögren's syndrome, pH > 6.5 fasting) |
| Blood | neg | Microhematuria in antiphospholipid syndrome, Sjögren's syndrome, urinary tract infection |

### Protein/creatinine ratio (PCR) — home calculation

If the strip shows numeric values:
`PCR (mg/g) = protein (mg/dl) ÷ creatinine (mg/dl) × 1000`
Normal: < 150 mg/g | Pathological: > 300 mg/g

The analysis script calculates this automatically if both fields are numeric.

---

## Alarm signals — when to call your doctor

| Finding | Urgency | Action |
|---|---|---|
| Protein `++` or `+++` (≥100 mg/dl) | 🟡 timely | Lab confirmation: ACR, creatinine, urine sediment for casts |
| Blood `++` or `+++` without UTI symptoms | 🟡 timely | Urology / nephrology, sediment analysis |
| Ketones `++` or `+++` under GLP-1 therapy | 🟡 timely | Rule out euglycemic ketoacidosis (venous blood gas) |
| Leukocytes `+` + nitrite `pos` | 🟢 elective | Treat UTI, repeat after antibiotics |
| pH > 6.5 fasting, repeatedly | 🟢 elective | Renal tubular acidosis (type 1 RTA, among others in Sjögren's syndrome) — mention to your rheumatologist |
| Glucose `+` with normal blood glucose | 🟢 elective | Tubular glucosuria (e.g. Sjögren-associated Fanconi syndrome) — consult a nephrologist |
| Protein `trace` or `+` (30 mg/dl), new | 🟢 monitor | Repeat at the next routine test |

---

## Limitations of the strip test

- **Albuminuria < 30 mg/dl** is not detected — a lab ACR is more sensitive for early detection of autoimmune nephritis
- **Tubular proteins** (β2-microglobulin, NAG) — only measurable in a lab, clinically relevant for Sjögren-associated tubular involvement
- **Sediment** (red cell casts, dysmorphic RBCs) — requires a microscope
- Strips are **screening tests**, not a diagnosis

---

## Kyoro import after each test

```bash
# Fill out the CSV (copy the template, enter values)
cp templates/urine_strip_template.csv my_urine_tests.csv
# ... enter values ...

# Import
python3 scripts/importers/import_urine_strip.py my_urine_tests.csv

# Analysis
python3 scripts/analysis/manual/analyse_urine.py --plot
```
