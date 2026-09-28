# Decision Impact Log

Motivated by the "Clinical value" axis of the REAL-FM framework (Muneer et
al. 2026, *Foundation models in biomedical imaging: turning hype into
reality*, Nature Biomedical Engineering, 10:1557-1575,
doi:10.1038/s41551-026-01762-z): a calibration/bias/robustness spot-check
(see `docs/ETHICS.md` § "Calibration and grounding") only tells you how the
model behaves on a single call. It says nothing about whether its output,
once acted on, actually helped. This log closes that loop.

This is a personal, manual practice — not a database table, not a script.
Nothing here is automated on purpose: the point is a deliberate moment of
review, not another feed to skim past. Keep the filled-in log **out of the
public repo** (personal health decisions are exactly the kind of content
`docs/ETHICS.md` § "Prohibited uses" and the privacy rules in `CLAUDE.md`
exist to keep local) — copy this template into a private location, e.g.
`intern/decision_impact_log.md` (already gitignored), and fill it in there.

## When to add an entry

Whenever an LLM-generated analysis (a `analyse_*.py` report, a query
answer, a synthesis panel opinion) meaningfully influenced a real decision:
contacting a clinician, changing pacing/activity, requesting a specific
test, ruling something out, or deciding *not* to act on a flagged concern.
Skip entries where the output was read but changed nothing — the log is
for decisions, not for every report generated.

## Entry format

```
## YYYY-MM-DD — <one-line description of the decision>

- **Source:** which script/query produced the output (e.g.
  `analyse_hrv_verlauf.py`, `health_query.py`, synthesis panel)
- **What it said:** the specific claim or recommendation that drove the
  decision (not the whole report — just the load-bearing part)
- **Confidence as stated:** what confidence level the output itself
  reported for that claim (grounding section)
- **Decision made:** what was actually done as a result
- **Outcome (fill in later, once known):** did the decision turn out to be
  the right call? Was the LLM's claim confirmed, partially confirmed, or
  wrong? By what (lab result, clinician assessment, symptom course)?
- **Would a differently-calibrated confidence have changed the decision?**
  optional, but the most useful question for catching over/under-confidence
  over time
```

## Review cadence

No fixed schedule — but worth a skim whenever the calibration/bias
spot-check in `docs/ETHICS.md` is revisited, since this is the other half
of the same question: not just "does the model sound consistent and
well-calibrated," but "was it actually right when it mattered."
