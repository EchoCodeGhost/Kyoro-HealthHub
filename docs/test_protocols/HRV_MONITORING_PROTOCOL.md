<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Long-Term HRV Monitoring with a Chest Strap — Protocol

> **Deutsche Version:** [HRV_MONITORING_PROTOCOL_DE.md](HRV_MONITORING_PROTOCOL_DE.md)

**Purpose:** Establish a reliable personal HRV baseline and document autonomic
patterns (day/night, exertion/recovery, arrhythmia windows) — the foundation
for AFib risk assessment (see [AFES.md](AFES.md)) and for tracking Long
COVID / ME/CFS / autonomic dysfunction over time.

Beat-to-beat chest-strap data (RR intervals) is the data source for several
AFES components (`h10_dfa`, `h10_poincare`, `h10_sampen`, `h10_turning`,
`h10_preaf` — see [AFES.md](AFES.md#device-policy)). This protocol describes
how to capture that data so it's actually usable for analysis.

---

## Device choice: short recording vs. self-contained long-term recording

| Property | Chest strap without internal storage (e.g. Polar H7) | Chest strap with internal storage (e.g. Polar H10) |
|---|---|---|
| Recording without a phone | ❌ not possible | ✅ button press → self-contained, up to several days |
| Phone must stay in range the whole time | Yes | No |
| ECG-grade quality (beat-to-beat) | ✅ | ✅ |
| Best for | Short recordings (24h), phone available | Long-term (multiple days), self-contained |

**Short recording (no internal storage):** start a recording app on your phone (e.g. Polar Beat or similar), put on and dampen the strap, the app runs in the background, the phone must stay within Bluetooth range (~10m). Practical for 24h sessions if the phone stays with you consistently.

**Long-term recording (internal storage):** press the button → internal recording starts, no phone needed. Sync via the matching app once the wear period is over.

---

## Two-phase approach

A single snapshot isn't very informative — two phases give you an actual comparison:

### Phase 1 — Short test run (24h)

**Purpose:** test the device and workflow, gauge wearing comfort, get an initial orientation.

If this test run happens during an atypical period (e.g. shortly after a cold, on vacation, after unusual exertion): treat the result only as a rough orientation value, not a baseline. Such influences (illness, vacation recovery) overlap and can't be cleanly separated after the fact.

### Phase 2 — Everyday baseline (5-7 days)

**Purpose:** a genuine everyday baseline for ongoing monitoring.

**When:** at least 5-7 days after full recovery from any acute infection; a normal week without unusual exertion or exceptional circumstances (no vacation, no unusually intense activity).

**Don't avoid exercise during Phase 2:** the post-exertional HRV response (how HRV recovers after exertion) is one of the most clinically valuable data points for autonomic dysfunction and PEM (post-exertional malaise) — without exertion during the recording, exactly that signal is missing. When training: briefly remove the strap, then put it right back on afterward (a short data gap is fine; the interesting data comes in the 2-6 hours after). Also note training times, for later correlation.

**Procedure (both phases):**
1. Put on the strap, start recording (button press for a long-term device, or app start for a short recording)
2. Wearing: showering is usually fine (check the waterproof rating for your specific device), wear it while sleeping, shift the strap 1-2 cm daily (to avoid skin irritation), dampen the electrodes or use gel for a better signal
3. After the period ends: sync via the app
4. Import the data: `python3 scripts/import_all.py --update`
5. Let the standard pipeline continue: `python3 scripts/compute_all.py`

**Follow-up measurements:** repeat every 3-6 months after the first baseline measurement, especially after infections, starting a new therapy, or activity changes, to track the trend over time.

---

## What the analysis shows

After `compute_all.py`, the following analyses are available:

- **AFES score** (see [AFES.md](AFES.md)) — including the chest-strap-specific components `h10_dfa`, `h10_poincare`, `h10_sampen`, `h10_turning`, `h10_preaf`
- **HRV trend with event markers:** `python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py`
- **Orthostatic test results** (if a Schellong test was also done): see [ORTHOSTATIC_TEST_PROTOCOL.md](ORTHOSTATIC_TEST_PROTOCOL.md)

### Interpretation aids

| Observation | Meaning |
|---|---|
| RMSSD notably higher at night than during the day | Healthy autonomic nervous system |
| RMSSD at night ≈ during the day | Autonomic dysfunction (common e.g. in Long COVID, ME/CFS) |
| Resting HR during sleep < 60 bpm | Good cardiovascular fitness |
| Resting HR during sleep > 75 bpm | Elevated sympathetic activation |
| **Arrhythmia window** (hours with CV-RR > 0.15, i.e. a high beat-to-beat coefficient of variation) at night | Possible sleep-apnea-associated response |
| Arrhythmia window after activity | Post-exertional response |
| RMSSD difference between two phases > 5 ms | Clinically noteworthy |
| Resting HR difference between two phases > 5 bpm | Clinically noteworthy |

**Methodological limitation for Phase 1 vs. Phase 2 comparisons:** if Phase 1 happened during an atypical time (illness, vacation), two effects overlap (recovery from illness + vacation recovery) and can't be cleanly separated. For a methodologically clean comparison, three phases are ideal: healthy+vacation, ill+vacation, healthy+everyday — in practice, usually only achievable across multiple measurement cycles.

---

## For your cardiologist / neurologist

Bring along:
- Raw data (RR-interval time series) for the relevant period
- AFES trend and any flagged components
- HRV trend chart with event markers (`analyse_hrv_verlauf.py`)
- Orthostatic test results, if done in parallel
