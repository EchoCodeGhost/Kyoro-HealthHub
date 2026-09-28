# name_validation — Generisches Namensvalidierungs- und Erkennungsmodul

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/name_validation.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides functions to detect and validate names using configuration from name_lists.json. Works alongside the pseudonymization system to identify potential personal information in text data. Key features: Detect common German first and last names, identify name patterns (e.g., "Firstname Lastname"), validate name formats, integrate with pseudonymization system.

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

Loads name lists from name_lists.json in utils/ directory or uses built-in fallback lists. Uses regular expressions for efficient pattern matching. The NameDetector class provides methods for: checking individual first/last names, detecting full names, detecting title+name combinations, comprehensive name detection in texts, person_id validation. A singleton object (detector) is provided for easy use.

## Data flow

- **Reads:** `scripts/utils/name_lists/name_lists.json`
- **Writes:** `(keine Schreiboperationen)`

## Limitations

Only detects names configured in the name lists. Case-insensitive comparison for better match rate. Does not process real personal data - only used for pattern detection.

## Usage

```bash
from utils.name_validation import NameDetector, is_common_first_name, detect_names_in_text
detector = NameDetector()
# Einzelne Namen prüfen
is_first = is_common_first_name("Anna")
is_last = is_common_last_name("Müller")
# Umfassende Erkennung in Text
names = detect_names_in_text("Dr. med. Anna Müller war hier")
# Person-ID validieren
valid = detector.validate_person_id("user_123")
```
