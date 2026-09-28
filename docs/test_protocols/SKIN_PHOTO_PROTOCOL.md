<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Photographing a Skin Lesion — Measurement & Capture Protocol

> **Deutsche Version:** [SKIN_PHOTO_PROTOCOL_DE.md](SKIN_PHOTO_PROTOCOL_DE.md)
> **Import workflow & triage:** [SKIN_LESION_TRACKING.md](SKIN_LESION_TRACKING.md)

A consistent capture protocol makes photos of a lesion actually comparable
across months/years — for your own tracking, for the dermatologist, and for
app-/AI-assisted assessments (Skinscreener, VLM photo checks). Without
standardization, neither size growth nor color change can be objectively
determined, and capture artifacts (flash reflections, compression) can be
mistaken for real lesion features.

**Why this matters:** Capture artifacts like flash reflections or JPEG
compression can look like clinically relevant lesion features on a photo
(dark spots, apparent color changes) — causing unnecessary worry until the
finding turns out to be a capture artifact rather than a real change. This
protocol exists to prevent exactly that kind of misjudgment.

## 1. Scale/reference

- Place a **ruler or small measuring tape** directly next to the lesion, in
  the same image plane — otherwise growth over time can't be objectively
  compared.
- Optional: place a small gray/color reference card next to it — makes color
  changes between sessions with different lighting comparable.

## 2. Distance & zoom

- **No digital zoom** — degrades actual detail resolution. Instead, physically
  move closer (use macro mode if available).
- **Two shots per session:**
  - Overview shot (~30 cm) — shows body location/context (exactly where on
    the body, relative to nearby moles/landmarks)
  - Close-up (~10–15 cm) — lesion fills the frame with some surrounding skin

## 3. Light

- **No flash.** Flash creates harsh reflections and hard shadows and can
  produce artifacts that get mistaken for real lesion features.
- **Even, indirect daylight** preferred (e.g. by a window, not direct sun).
- More important than "bright" is **"consistent"** — photograph at a similar
  time of day / same location whenever possible, so photos stay comparable
  across months.

## 4. Format

- **HEIC or RAW instead of compressed JPEG**, where possible — fewer
  compression artifacts, more actual image detail.
- If only JPEG is available: set the camera app's highest quality setting (no
  "small file size" option).

## 5. Angle/position

- Hold the camera **directly perpendicular over the lesion**, not at an
  angle — a skewed perspective distorts shape and size assessment (relevant
  for asymmetry evaluation under ABCDE criteria).

## 6. Optional accessory: from clip-on lens to a full DSLR macro setup

**Simple clip-on macro lenses (cheap, ~$10–20):** closer focus distance, more
detail — but cheap lenses often introduce distortion, color fringing
(chromatic aberration), and edge softness. This can create the same problem
as a flash artifact: an optical artifact of the lens gets mistaken for a real
lesion feature. Also very shallow depth of field at high magnification
without a tripod.

**Polarized dermatoscope attachments (everyday recommendation):**
Cross-polarized light eliminates surface reflections and reveals subsurface
structures (pigment network, vascular patterns, "blue-white veil") — exactly
the features dermatologists look for with a dermatoscope, and which are
invisible in regular photos. Fixes the flash-reflection problem at the root
instead of just avoiding it.

- **DermLite HÜD 2** (~$99–195 depending on retailer) — designed specifically
  for home monitoring, made by DermLite/3Gen, the established manufacturer of
  professional dermatoscopes (the same devices dermatologists themselves
  use). Supports live video streaming for teledermatology consultations, no
  cloud lock-in. **Ordered** — after comparing against Scaut
  (multispectral, no polarization), IBOOLO DE-500 (~$399, polarized + UV, but
  $90 more expensive for comparable-or-slightly-weaker image quality per
  independent reviews), and MoleScope II (~€399, polarized, but tied to the
  DermEngine cloud).
- **IBOOLO DE-500** (~$399) — adds UV mode (365nm, for fungal
  infections/pigment disorders, not core-relevant for melanoma follow-up),
  metal housing, magnetic adapter — worth it if those extras matter more than
  the price gap.

**Thermal camera attachment (FLIR One, Seek Thermal) — a complement, not a
replacement:** Thermal image instead of/alongside a photo. Makes
inflammation visible (rosacea flares, local infections — inflamed tissue is
often warmer), potentially also circulation issues (Raynaud-like patterns).
Not based on polarization, so it doesn't solve the dermoscopy problem — it
provides a different, additional kind of information.

**DSLR + macro lens + ring flash with cross-polarizing filters (highest
quality, more effort):** A used DSLR body with a macro lens
(e.g. Nikon 60mm f/2.8G Micro or 105mm f/2.8G VR Micro, both 1:1
magnification) delivers noticeably more detail than a phone camera plus
dermatoscope attachment, because a real camera sensor sits behind the lens
instead of a phone camera. A plain ring flash is **not polarized**, though —
same reflection risk as any flash (see Section 3). Fix: a
**cross-polarization setup** — a linear polarizing filter on the lens, a
polarizing film on the ring flash, both rotated 90° relative to each other.
Eliminates surface reflections on the same principle as a dermatoscope
attachment, just with a higher-quality sensor. Polarizing film is available
as cut-to-size roll stock from photography suppliers; a lens polarizing
filter is standard gear. **RAW format (NEF on Nikon)** is directly
supported by `import_skin.py` (the original is preserved,
PII metadata is stripped, and a JPEG preview is generated alongside it — see
`scripts/modules/imaging_utils.py`). More effort per shot (setting up a
camera instead of grabbing a phone) — better suited to important follow-up
milestones (e.g. quarterly dermatologist check-ins) than everyday use,
complementing the DermLite rather than replacing it.

Important for any attachment: always also take a regular overview shot
**without** it — close-ups lose the body-location context.

Prices and availability change — check current listings before buying.

## 7. Self-check: the ABCDE rule

The ABCDE rule is the standard screening grid for pigmented lesions (used by
dermatology associations worldwide). It doesn't replace a clinical
assessment, but it helps you compare photos against the same specific
features instead of a vague overall impression:

- **A — Asymmetry:** Along an imagined midline, are the two halves
  irregular, not mirror-symmetric?
- **B — Border:** Is the edge blurred, notched, or ragged instead of smooth
  and even?
- **C — Color:** Multiple shades within the same lesion (e.g. mixed brown,
  black, red, gray, or blue) instead of one uniform color?
- **D — Diameter:** Larger than about 5 mm (reference: a pencil eraser)?
  The absolute value matters less than change over time — that's what the
  scale reference in section 1 is for.
- **E — Evolving:** Change over time — growth, new elevation, color shift,
  itching/bleeding? This is the entire reason this protocol exists: without
  comparable photos, "E" can't be judged objectively.

A single matching criterion isn't proof, and several matching criteria
aren't a rule-out either — this grid is a **reason to get it checked
promptly**, not a diagnosis. When in doubt: **better one visit too many than
one too few.** And regardless of whether insurance covers the visit:
**prevention saves lives and spares suffering.**

**Appeal:** Have a partner or close friend check hard-to-see body areas
(back, scalp, neck) regularly (at least once a quarter) — your own eyes and
a mirror can't reach everywhere. And get a professional skin cancer
screening at a dermatologist at least every two years, regardless of
whether anything currently looks suspicious.

**Beyond a standard visual screening:** ask whether your dermatologist offers
**video dermatoscopy** (digital, magnified, storable images per lesion — far
more sensitive to subtle change over time than a naked-eye check) or,
better yet, **full-body mapping** (systematic photographic documentation of
the entire skin surface, so new or changing lesions stand out against a
baseline instead of relying on memory) — increasingly offered with
**AI-assisted comparison** between visits to flag change a human reviewer
might miss. Not universally available or reimbursed, and it doesn't replace
the dermatologist's own judgment, but worth asking for if you have risk
factors (many moles, a personal or family melanoma history, previous
atypical findings).

## Quick checklist before every photo

- [ ] Ruler/scale next to the lesion?
- [ ] No digital zoom, moved closer instead?
- [ ] Both overview **and** close-up shot taken?
- [ ] No flash, even lighting?
- [ ] HEIC/RAW instead of compressed JPEG?
- [ ] Camera perpendicular over the lesion?
- [ ] Went through the ABCDE criteria when comparing against earlier photos?

## Import

Import photos as usual afterward:

```bash
python3 scripts/importers/import_skin.py photo.jpg --location "left big toe"
python3 scripts/importers/import_skin.py followup.jpg --lesion-id 3
```

Importer details: `docs/en/importers/import_skin.md` (generated from the
script docstring).
