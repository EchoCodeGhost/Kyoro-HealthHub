<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Skin Lesions — Tracking Workflow

> **Deutsche Version:** [SKIN_LESION_TRACKING_DE.md](SKIN_LESION_TRACKING_DE.md)

For the capture technique itself, see [SKIN_PHOTO_PROTOCOL.md](SKIN_PHOTO_PROTOCOL.md) —
this document covers the workflow around importing, tracking, and triaging
an already-captured lesion.

**Importer:** `python3 scripts/importers/import_skin.py`
**Analysis:** VLM (ABCDE criteria + triage recommendation) via OpenRouter
**DB:** `medicine_imaging.db` → `skin_lesions` + `imaging_files`

---

## Retrospective lesion history from old photos

If a lesion has been there for a while by the time you get to a
dermatologist, but was never systematically photographed: photo albums/
cloud photos (Google Photos, Apple Photos, old phone backups) can still
give you a rough timeline — vacation photos, family photos, gym/mirror
selfies often show the affected skin area unintentionally.

**Approach:**
1. Filter your photos app by location/time range (e.g. "beach", "pool",
   "summer 2023") — photos with uncovered skin are more likely to help
2. For every usable find: **note the capture date from the EXIF metadata**
   (more reliable than your own memory)
3. Crop/zoom into the lesion area from the old photo, as far as the
   resolution allows
4. Import with the **actual historical capture date** (`--date`), not
   today's date:
   ```bash
   python3 scripts/importers/import_skin.py old_photo_crop.jpg \
     --lesion-id 1 --date 2023-07-15 --source other
   ```

**Important — manage your expectations on image quality:** old phone
photos usually weren't taken for dermatological purposes (wrong angle, no
scale reference, low resolution, possible compression artifacts). The VLM
can still give a rough assessment of such photos, but it's less
informative than a photo taken following
[SKIN_PHOTO_PROTOCOL.md](SKIN_PHOTO_PROTOCOL.md). The main value here is
the **timestamp** ("did this already exist two years ago?"), not detailed
assessment.

**Especially valuable for your dermatologist:** a clearly dated old photo
can objectively answer "how long has this been there?" instead of relying
on memory — that can make the difference in judging whether a change is
actually recent (criterion E in ABCDE).

---

## Supported sources

| Source | `--source` | Quality | Notes |
|---|---|---|---|
| Smartphone camera (direct) | `camera` | good | AirDrop/USB to computer |
| Screenshot from a skin-scanning app | `screenshot` | good | app score visible in the image |
| DSLR + macro lens | `dslr` | very good | best detail resolution |
| Other | `other` | variable | — |

---

## Workflow

### First capture of a new lesion

```bash
python3 scripts/importers/import_skin.py photo.jpg \
  --location "Lower back left, ~5cm below shoulder blade" \
  --date 2026-01-15 \
  --source camera
```

→ New lesion created: **ID 1**

### Triggering VLM analysis (separate step)

The import itself does not run image analysis — that's `analyse_skin.py`:

```bash
python3 scripts/analysis/manual/analyse_skin.py --analyse
```

→ Analyzes all not-yet-evaluated photos, shows the triage result
→ Report is saved under `analyses/manual/`

### Follow-up photo (same lesion)

```bash
python3 scripts/importers/import_skin.py followup.jpg \
  --lesion-id 1 --date 2026-04-15
```

### Adding an app score later (e.g. after a skin-scanning app result)

```bash
python3 scripts/importers/import_skin.py \
  --update-lesion 1 --app-score medium --app-name "Skin-scanning app"
```

### Recording a dermatologist assessment

```bash
python3 scripts/importers/import_skin.py \
  --update-lesion 1 \
  --derm-assessment "Clinically unremarkable, follow-up in 12 months" \
  --derm-date 2026-04-20
```

### Recording surgery + histology

```bash
python3 scripts/importers/import_skin.py \
  --update-lesion 1 \
  --operated --operation-date 2026-05-01 \
  --histology "[histology result]" --histology-subtype "[subtype]" \
  --histology-date 2026-05-08
```

### Listing all lesions

```bash
python3 scripts/importers/import_skin.py --list-lesions
```

---

## Triage traffic light

| Symbol | Meaning | Action |
|---|---|---|
| 🔴 Immediate | Highly suspicious — multiple ABCDE criteria flagged | Dermatologist within 1-2 weeks |
| 🟡 Soon | A few individual concerns | Dermatologist within 4-8 weeks |
| 🟢 Monitor | Unremarkable, but monitoring recommended | Self-photo in 6-12 months, dermatologist if it changes |
| ✅ Unremarkable | No cause for concern | No action |
| ❓ Image quality | Photo too blurry/dark to assess | Take a better photo |

**Important:** The VLM is not a substitute for a dermatological exam. For 🔴 or 🟡, always see a dermatologist — regardless of the app score.

---

## Body location quick reference (for `--location`)

Free text works, but consistent naming helps with tracking:

```
Face:    "cheek left", "nasal bridge", "forehead right", "lower lip"
Head:    "crown", "back of head left", "temple right"
Neck:    "front of neck", "nape left"
Trunk:   "chest center upper", "back left upper", "back right lower", "shoulder right"
         "abdomen left", "flank right", "coccyx"
Arms:    "upper arm left outer", "forearm right inner", "back of hand right"
Legs:    "thigh right inner", "lower leg left front", "top of foot left"
Genital: as needed
```

---

## ABCDE self-check (for capture)

If you answer "yes" to any of these while photographing → run VLM analysis (details on the rule: [SKIN_PHOTO_PROTOCOL.md](SKIN_PHOTO_PROTOCOL.md#7-self-check-the-abcde-rule)):

- **A:** Is one half different from the other?
- **B:** Is the border ragged, irregular, or blurred?
- **C:** More than one color (brown/black/red/white)?
- **D:** Larger than a pencil eraser (~6 mm)?
- **E:** Has the lesion changed recently (color, size, shape, itching, bleeding)?

---

> **Note for treating physicians:** Full prior findings, medication history, and long-term wearable data are stored in the **electronic patient record**. Please request access via your practice software's national health-data interface.
