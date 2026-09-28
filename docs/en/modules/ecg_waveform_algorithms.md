# ecg_waveform_algorithms.py — P/QRS-Wellen-Delineation aus EKG-Rohwellenform

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/ecg_waveform_algorithms.py`

**Evidence tier:** research (peer-reviewed literature basis, but no formal clinical validation study with endpoints)

## Purpose

Provides pure mathematical functions for detecting the P wave and QRS complex in raw single-lead ECG waveform, and for computing the PR interval and QRS duration. Operates on voltage samples (mV), not RR intervals — the counterpart to modules/rr_interval_algorithms.py, which operates exclusively on interval sequences (see that module's @limits for the deliberate separation between the two).

## Relevance

Enables PR/QRS interval measurement from consumer ECG raw data (Apple Watch, ECG Logger/H10) that do not compute/report these values themselves — Withings BPM Core already reports PR/QRS/QT/QTc via its own certified on-device algorithm and does not need this module.

## Method

Uses neurokit2 (required dependency, see requirements.txt) for the actual signal processing: nk.ecg_clean(method="biosppy") for preprocessing, nk.ecg_peaks() for R-peak detection, then nk.ecg_delineate(method="dwt") for wavelet-based delineation (Martinez et al. 2004 — the same method family neurokit2 implements internally). From the delineated fiducial points per beat, the following are computed: PR interval  = R-Onset - P-Onset QRS duration = R-Offset - R-Onset QT interval/QTc are NOT computed (see @limits — T-wave offset detection was not empirically reliable enough to report). Choice of method="biosppy" over neurokit2's default cleaning: empirically checked against a Withings BPM Core reference value (its own certified device result, PR=144ms/QRS=60ms for the same recording). The default cleaning method consistently gave implausible QRS durations (130-190ms, clinically bundle-branch- block territory, but on practically every beat) — biosppy+dwt hit the QRS reference value exactly and came much closer on PR (122ms) than the default combination (94ms), while covering almost twice as many beats (106 vs. 51 of 114 R-peaks fully delineated).

## Data flow

- **Reads:** `Keine`, `Tabellen`, `(reine`, `Mathematik)`
- **Writes:** `Keine Tabellen (gibt Berechnungsergebnisse zurück)`

## Limitations

Neither the delineation (neurokit2/DWT) nor the conclusions drawn here are clinically validated on consumer single-lead ECG — Martinez et al. 2004 validated on clinical 12-lead databases (QT Database etc.), not on Apple Watch/H10 single- lead signals. QT/QTc were deliberately dropped from scope: T-wave offset detection proved unstable in an empirical test against a Withings BPM Core reference recording (QT values ranging from 102ms to 386ms *within the same 60-second recording*, not physiologically plausible) — better a reliable PR/QRS than a PR/QRS/QT/QTc set with a silently unreliable QT component. The P wave is low-amplitude and harder to reliably delineate than the QRS complex — PR interval values are correspondingly less certain than QRS duration (P-onset error propagates directly and undamped into PR). Individual beats without complete delineation (P or R onset/offset not detected) are skipped, not guessed — no interpolating missing fiducial points. Not a replacement for a clinical 12-lead ECG or physician interpretation.

## References

- Martinez JP, Almeida R, Olmos S, Rocha AP, Laguna P (2004). A wavelet-based ECG delineator: evaluation on standard databases. IEEE Transactions on Biomedical Engineering, 51(4):570-581. doi:10.1109/TBME.2003.821031
- Makowski D, Pham T, Lau ZJ et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. Behavior Research Methods, 53(4):1689-1696. doi:10.3758/s13428-020-01516-y

## Usage

```bash
from modules.ecg_waveform_algorithms import delineate_and_measure
beats = delineate_and_measure(signal_mv, fs_hz=512)
```
