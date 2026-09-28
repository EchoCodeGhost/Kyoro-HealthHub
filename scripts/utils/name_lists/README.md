# Name Lists Configuration

This directory contains configuration files for name detection in the pseudonymization process.

## `name_lists.json`

This file contains lists of common German names, titles, and medical facility patterns used for detecting and pseudonymizing personal information in health data.

### Structure

```json
{
  "common_first_names": [...],      // Common German first names
  "common_last_names": [...],       // Common German last names  
  "common_arzt_titles": [...],      // Medical professional titles
  "common_mvz_names": [...]         // Medical facility name patterns
}
```

### Usage

The `anonymize.py` module automatically loads these lists when available. If the file is missing or invalid, it falls back to built-in lists.

### Security

- This file contains only common names and patterns, not actual patient data
- The names are used solely for detection purposes in the pseudonymization process
- No personal data is stored in this file

### Customization

You can modify this file to:
- Add additional common names relevant to your use case
- Remove names that cause false positives
- Adjust the sensitivity of name detection

### Fallback Mechanism

If `name_lists.json` is missing or corrupted, the system automatically falls back to built-in name lists embedded in the code. This ensures the pseudonymization process continues to work even if the configuration file is unavailable.

## Adding New Name Lists

To add names to any category:

1. Edit `name_lists.json`
2. Add the new names to the appropriate array
3. Save the file
4. The changes will be automatically loaded on the next run

## Best Practices

- Keep the lists focused on common names to avoid false positives
- Use lowercase letters consistently
- Test changes with real data to ensure proper detection
- Consider cultural and regional naming conventions