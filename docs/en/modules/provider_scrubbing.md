# provider_scrubbing.py — Pseudonymisierung von Leistungserbringer-/Adress-Freitext

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/provider_scrubbing.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Detects treating-provider name mentions and addresses in free text (e.g. from scanned documents) and removes them before the text is written to a table or an intermediate file. Central, reusable module instead of per-importer scrubbing logic.

## Relevance

Prevents treating-provider name mentions/addresses in free text from landing unpseudonymized in tables or intermediate files, essential for the privacy of every free-text-processing importer

## Method

Four-tier, purely regex/registry-based, no NER/ML: 1. Exact match against the local, never-committed registry (~/.config/kyoro/provider_registry.json) — strips the raw string, sets category/city/country/region from the registry entry, resolves provider_pseudonym via identity_resolver.resolve("provider", <canonical key>). 2. No registry match but a German postal-code pattern (\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+) → reduce to city name, set country="DE". 3. Title+name pattern (Dr., Dr. med., Prof., Prof. Dr., Facharzt/Fachärztin für ..., Zahnarzt/Zahnärztin, ...) + 1-2 capitalized words → strip, needs_review=True, unless step 1 already resolved the name. 4. Safety net: remaining street-suffix words, a leftover 5-digit number, or several consecutive capitalized words → needs_review=True, text is kept (never discarded).

## Data flow

- **Reads:** `~/.config/kyoro/provider_registry.json`
- **Writes:**

  ```
  keine Tabellen (reine Textverarbeitungsfunktion; Aufrufer
  entscheiden, was mit dem Ergebnis in ihre eigenen Tabellen
  geschrieben wird)
  ```

## Limitations

No real named-entity recognition — a bare name with neither a title nor an address (e.g. "mit Michael treffen") is NOT detected; this is a documented, accepted gap. The heuristics (postal-code pattern, title+name pattern) were designed against calendar-style free text, not against OCR noise from scanned documents — for OCR input, the exact registry match carries more weight than the pattern heuristics, since OCR errors (transposed characters, dropped umlauts) break the patterns faster than a dictionary lookup.

## Usage

```bash
from modules.provider_scrubbing import scrub_provider_text
result = scrub_provider_text("Termin bei Dr. Müller, Musterstr. 1, 12345 Musterstadt")
result.clean_text          # -> "Termin bei , 12345 Musterstadt" (falls kein Registry-Treffer) oder vollständig bereinigt (falls Registry-Treffer)
result.provider_pseudonym  # -> "PRV-xxxxxxxx" oder None
result.needs_review        # -> True/False
```
