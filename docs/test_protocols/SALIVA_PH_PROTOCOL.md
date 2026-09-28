<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Saliva pH Home Monitoring — Test Protocol

> **Deutsche Version:** [SALIVA_PH_PROTOCOL_DE.md](SALIVA_PH_PROTOCOL_DE.md)

**Import:** `python3 scripts/importers/import_saliva_ph.py --ph <value> --context <context>`
**Template:** `templates/saliva_ph_template.csv`
**Reference ranges:** configurable in `~/.config/kyoro/saliva_ph_ranges.json`

---

## Standard protocol (routine)

**Frequency:** daily, fasting in the morning (context `fasting_morning`); optionally also 1-2h after a meal, after an antihistamine, in the evening, or when a symptomatic flare is suspected.

> ⚠️ **Don't swap the order: test first, everything else after.** The `fasting_morning` test belongs right after waking up, **before** brushing teeth, breakfast, or medication.

### Procedure (always in this order)

1. **Right after waking up** — before eating, drinking, brushing teeth, or taking medication.
2. **Collect saliva** (not stimulated/provoked — just let it accumulate naturally in the mouth) and dip the test strip for 1-2 seconds, or wet it with saliva.
3. **Read immediately** per the manufacturer's instructions (10-15 seconds for most strips) — in daylight or good artificial light, using the reference color chart on the package.
4. **Only afterward:** brushing teeth, breakfast, medication.
5. **Always record the same context** (see table below) — a value without a context tag isn't usable for trend analysis, since reference ranges differ by time of day/meal.

### Rinsing before the test — yes or no?

Two possible variants of the `fasting_morning` test, each with a different tradeoff:

- **With rinsing** (water + a 5 min wait before the test): removes leftover food residue from the previous evening, which creates a more reproducible starting point. Downside: saliva is briefly diluted by the water (pH ≈ 7, neutral), which pulls the measured value artificially upward (less acidic than it actually is). Whether, after 5 minutes, 100% of the residual water has really been replaced by fresh saliva remains unclear — a residual bias is never fully ruled out.
- **Without rinsing:** measures the raw, overnight state directly. When hyposalivation is suspected (e.g. Sjögren's syndrome, a medication side effect, dehydration), this is exactly the clinically interesting value, because it shows what the mucosa/teeth actually experience overnight. Leftover food from the previous evening is a smaller problem hours after the last meal (mostly cleared by overnight swallowing anyway) than the systematic dilution bias from rinsing itself.

**Important if you switch protocols mid-use:** rinsed and non-rinsed values aren't directly comparable — when switching from one variant to the other, note in the measurement's comment field when the switch happened, so trend analysis can account for the break.

### Context keys

| Context | Timing | Reference range (pH) |
|---|---|---|
| `fasting_morning` | fasting in the morning, before brushing teeth/breakfast/medication | 6.8-7.4 (realistically lower without rinsing, see above) |
| `post_meal_1h` | 1h after the end of a meal | 6.5-7.4 |
| `post_meal_2h` | 2h after the end of a meal — should have recovered | 6.8-7.4 |
| `post_antihistamine` | 1-2h after taking an H1/H2 blocker | 6.8-7.6 |
| `suspected_flare` | symptom-triggered, when an acute flare is suspected | no fixed range |
| `evening_baseline` | 2h after the last meal, before sleep | 6.8-7.5 |

### Recording

**Direct entry (recommended for single measurements):**
```bash
python3 scripts/importers/import_saliva_ph.py --ph 6.5 --context fasting_morning
python3 scripts/importers/import_saliva_ph.py --ph 5.5 --context suspected_flare --symptome "Flushing,Tachycardia"
```

**Via CSV (for multiple measurements at once):**
```bash
cp templates/saliva_ph_template.csv my_saliva_ph.csv
# ... enter values ...
python3 scripts/importers/import_saliva_ph.py my_saliva_ph.csv
```

Always specify the measurement method (`--methode`), e.g. `Streifen_4.5-9.0`, `pH-Meter` — different methods have different accuracy (strips ±0.5, pH meter ±0.01).

---

## Alarm signals

| Finding | Urgency | Meaning |
|---|---|---|
| pH < 6.0 | 🔴 high | strongly acidic saliva — mast cell mediator flare or reflux possible |
| pH < 6.2 | 🟡 medium | hyposalivation possible (e.g. Sjögren's syndrome, medication side effect, dehydration) or histamine-mediated acidification |
| pH > 7.8 | 🟡 medium | alkaline — check for a proton-pump-inhibitor effect or measurement error |
| `fasting_morning` repeatedly < 6.5 | 🟢 elective | discuss with a doctor/rheumatologist if a hyposalivation work-up is planned |

---

## Limitations of strip tests

- Test strips typically have ±0.5 accuracy — don't over-interpret single values; the **trend** across multiple measurements is more informative.
- A protocol change (e.g. with/without rinsing, see above) systematically shifts values — account for this when comparing across such a change.
- Strips are a screening tool, not a diagnosis — for a formal Sjögren's diagnosis, the Schirmer test + anti-SSA/Ro + anti-SSB/La are what counts, not saliva pH.

---

## Analysis

```bash
python3 scripts/analysis/manual/analyse_saliva_ph.py
```
