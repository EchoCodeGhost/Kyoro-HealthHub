# Name Validation Module

## Overview

The `name_validation.py` module provides comprehensive name detection and validation capabilities for the Kyoro-HealthHub system. It works alongside the pseudonymization system to identify potential personal information in text data.

## Features

### Name Detection
- **Common German Names**: Detect first and last names from configured lists
- **Full Name Patterns**: Identify "Firstname Lastname" combinations
- **Medical Titles**: Recognize title + name patterns (e.g., "Dr. med. Müller")
- **Comprehensive Scanning**: Full text analysis with duplicate avoidance

### Validation
- **Person ID Validation**: Check if person_ids contain obvious personal names
- **Quick Checks**: Fast detection of potential names in text
- **Case-Insensitive**: Robust matching regardless of capitalization

### Integration
- **Shared Configuration**: Uses the same name lists as `anonymize.py`
- **Consistent Behavior**: Results align with pseudonymization logic
- **Fallback Support**: Works even if configuration files are missing

## Usage

### Basic Name Checks

```python
from utils.name_validation import is_common_first_name, is_common_last_name

# Check individual names
is_common_first_name("Michael")  # True
is_common_last_name("Müller")   # True
```

### Comprehensive Detection

```python
from utils.name_validation import detect_names_in_text

text = "Patient Michael Müller wurde von Dr. med. Schmidt behandelt."
detection = detect_names_in_text(text)

# Results include:
# - full_names: [(full_match, first, last), ...]
# - title_names: [(full_match, title, last), ...]
# - single_first: [first_name, ...]
# - single_last: [last_name, ...]
```

### Person ID Validation

```python
from utils.name_validation import validate_person_id

# Validate person IDs
validate_person_id("P-ABC123")  # True - safe
validate_person_id("Michael")    # False - contains common name
validate_person_id("müller")     # False - contains common name
```

### Quick Checks

```python
from utils.name_validation import contains_potential_names

# Fast check for any names in text
contains_potential_names("Patient Michael Müller")  # True
contains_potential_names("Medical record #123")    # False
```

## Advanced Usage

### Using the NameDetector Class

```python
from utils.name_validation import NameDetector

# Create detector instance
detector = NameDetector()

# Detect full names
full_names = detector.detect_full_names("Anna Bauer und Thomas Weber")
# Returns: [("Anna Bauer", "Anna", "Bauer"), ("Thomas Weber", "Thomas", "Weber")]

# Detect title + name combinations
title_names = detector.detect_title_names("Dr. med. Müller und Prof. Dr. Schmidt")
# Returns: [("Dr. med. Müller", "Dr. med.", "Müller"), ("Prof. Dr. Schmidt", "Prof. Dr.", "Schmidt")]
```

## Configuration

The module uses the same `name_lists.json` configuration as the pseudonymization system:

```json
{
  "common_first_names": [...],
  "common_last_names": [...],
  "common_arzt_titles": [...],
  "common_mvz_names": [...]
}
```

### Customizing Name Lists

Edit `scripts/utils/name_lists/name_lists.json` to:
- Add or remove names
- Adjust sensitivity
- Add regional variations

Changes take effect immediately on the next run.

## Technical Details

### Algorithm

1. **Initialization**: Loads name lists from JSON configuration
2. **Pattern Compilation**: Creates optimized regex patterns for efficient matching
3. **Detection**: Uses regex with word boundaries for precise matching
4. **Duplicate Avoidance**: Tracks match positions to avoid overlapping detections

### Performance

- **Regex Compilation**: Patterns are compiled once at initialization
- **Set Lookups**: O(1) complexity for individual name checks
- **Efficient Scanning**: Single pass through text for comprehensive detection

### Case Handling

- **Storage**: Names stored in lowercase for consistent comparison
- **Matching**: Case-insensitive regex matching
- **Preservation**: Original case preserved in match results

## Integration with Existing Systems

### Pseudonymization System

The module is designed to work seamlessly with `anonymize.py`:

```python
from utils.anonymize import scrub_sensitive_health_data
from utils.name_validation import contains_potential_names

# First check if text contains names
if contains_potential_names(text):
    # Then pseudonymize
    clean_text = scrub_sensitive_health_data(text)
```

### Identity Database

Can be used to validate `person_name_map` entries:

```python
from utils.name_validation import validate_person_id

# Validate before adding to identity.db
if validate_person_id(proposed_person_id):
    # Safe to use
else:
    # Contains potential personal information
```

## Error Handling

- **Missing Configuration**: Falls back to built-in name lists
- **Invalid Input**: Gracefully handles None, empty strings, non-string types
- **Edge Cases**: Robust handling of partial matches and overlaps

## Testing

Run the comprehensive test suite:

```bash
python3 test_name_validation.py
```

## Best Practices

1. **Pre-Screening**: Use `contains_potential_names()` for quick checks before detailed processing
2. **Validation**: Always validate person_ids before storing in identity.db
3. **Integration**: Combine with pseudonymization for complete data protection
4. **Customization**: Adapt name lists to your specific use case and region

## Security Considerations

- **No Personal Data**: Module contains only common names, not actual patient data
- **Detection Only**: Used to identify potential personal information, not to store it
- **Configuration Security**: name_lists.json should have appropriate file permissions (644)

## Future Enhancements

Potential improvements:
- **Fuzzy Matching**: Handle typos and variations
- **International Names**: Support for non-German names
- **Context Awareness**: Better distinction between names and similar words
- **Performance Optimization**: Caching for repeated checks on similar text