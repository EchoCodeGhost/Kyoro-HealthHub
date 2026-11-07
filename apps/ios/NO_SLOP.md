# No-slop check

Run this list at the end of **every** development step (feature, screen, copy change,
mockup) and note the result in the commit message or PR. A step is not done while
an item fails.

## UI

- [ ] Liquid Glass only where the system puts it (tab bar, toolbars, sheets). No glass on content.
- [ ] No decorative gradients, glows or shadows. Lime appears only in success moments.
- [ ] Icons are SF Symbols or the Kyoro octopus. No emoji as icons, no stock illustrations.
- [ ] One primary action per screen. At most three suggestion cards on Today.
- [ ] All spacing, radii and colours come from `KyoroTheme`. No literal numbers or hex values in views.
- [ ] Works with the largest Dynamic Type size, VoiceOver, Reduce Motion and dark and light mode.
- [ ] Status is never shown by colour alone (symbol and text as well).

## Copy

- [ ] Every label is concrete. Buttons are verbs ("Symptom erfassen", not "Los geht's").
- [ ] No filler or marketing phrases ("Unlock your health journey").
- [ ] No invented numbers, sample values that look real, or fake testimonials, also not in previews or mockups.
- [ ] Empty states say what to do next. Error messages say what happened and what the user can do.
- [ ] Findings are framed as "worth asking your doctor about", never as a diagnosis. AI text is labelled.
- [ ] Kyoro documents and does not rate: no erkennen, warnen, screenen, auffällig, Diagnose, and no test named as a test for a condition (EU MDR, see the "Intended purpose is documentation" requirement).

## Code

- [ ] No dead code, no commented-out code, no unused abstractions "for later".
- [ ] No placeholder logic that pretends to work: a stub says so in its name or doc comment.
- [ ] Comments explain why, not what.
- [ ] No new dependency without a reason written in the PR.
- [ ] No personal data, real names or real measurements in code, tests or previews.
