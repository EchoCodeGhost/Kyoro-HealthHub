# FHIR Export

## Overview

The FHIR export feature enables exporting health data from Kyoro HealthHub in FHIR R4 format. This allows for interoperability with other healthcare systems that support the FHIR standard.

## Features

- **FHIR R4 Compliance**: Exports data in FHIR R4 format
- **LOINC Mappings**: Uses standardized LOINC codes for observations
- **Resource Types**: Supports Patient, Observation, Condition, and MedicationStatement resources
- **Unmapped Metrics Tracking**: Automatically tracks and reports metrics that don't have LOINC mappings

## Usage

### Basic Export

```bash
python scripts/export_health.py --profile cardiology --format fhir --person self
```

### Export with Date Range

```bash
python scripts/export_health.py --profile general_practitioner --format fhir \
  --from 2024-01-01 --to 2024-12-31 --person all
```

### Export to Specific Directory

```bash
python scripts/export_health.py --profile research --format fhir \
  --out /path/to/output/directory
```

## Output Files

When using `--format fhir`, the following files are created:

1. **fhir_bundle.json**: Main FHIR Bundle containing all resources
2. **fhir_export_unmapped_metrics.txt**: Report of metrics that couldn't be mapped to LOINC codes (only created if there are unmapped metrics)
3. **_manifest.json**: Export manifest with metadata

## FHIR Resources

### Patient Resource

Minimal patient resource with pseudonym identifier:

```json
{
  "resourceType": "Patient",
  "id": "PAT-ABCD",
  "identifier": [{
    "system": "https://kyoro.healthhub/patient",
    "value": "PAT-ABCD"
  }],
  "active": true
}
```

### Observation Resource

Observations are created from metric data with LOINC codings:

```json
{
  "resourceType": "Observation",
  "id": "obs-123",
  "status": "final",
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "8867-4",
      "display": "Heart rate"
    }]
  },
  "subject": {
    "reference": "Patient/PAT-ABCD"
  },
  "effectiveDateTime": "2024-01-01T12:00:00Z",
  "valueQuantity": {
    "value": 72,
    "unit": "/min",
    "system": "http://unitsofmeasure.org",
    "code": "/min"
  }
}
```

### Condition Resource

Conditions are created from clinical events with diagnosis type:

```json
{
  "resourceType": "Condition",
  "id": "cond-456",
  "clinicalStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
      "code": "active",
      "display": "Active"
    }]
  },
  "verificationStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
      "code": "confirmed",
      "display": "Confirmed"
    }]
  },
  "code": {
    "text": "Hypertension"
  },
  "subject": {
    "reference": "Patient/PAT-ABCD"
  },
  "onsetDateTime": "2024-01-01"
}
```

### MedicationStatement Resource

Medication statements are created from medication data:

```json
{
  "resourceType": "MedicationStatement",
  "id": "med-001",
  "status": "completed",
  "medicationCodeableConcept": {
    "text": "Ibuprofen"
  },
  "subject": {
    "reference": "Patient/PAT-ABCD"
  },
  "effectiveDateTime": "2024-01-01",
  "dosage": [{
    "text": "200 mg oral",
    "timing": {
      "repeat": {
        "frequency": 1,
        "period": 1,
        "periodUnit": "d"
      }
    },
    "route": {
      "text": "oral"
    },
    "doseAndRate": [{
      "doseQuantity": {
        "value": 200,
        "unit": "mg",
        "system": "http://unitsofmeasure.org",
        "code": "mg"
      }
    }]
  }]
}
```

## FHIR Bundle Structure

The main output is a FHIR Bundle of type "collection" containing all resources:

```json
{
  "resourceType": "Bundle",
  "id": "kyoro-export-2024-07-15T12:00:00",
  "type": "collection",
  "timestamp": "2024-07-15T12:00:00Z",
  "entry": [
    {
      "fullUrl": "urn:uuid:PAT-ABCD",
      "resource": { ... }
    },
    {
      "fullUrl": "urn:uuid:obs-123",
      "resource": { ... }
    },
    {
      "fullUrl": "urn:uuid:cond-456",
      "resource": { ... }
    }
  ]
}
```

## LOINC Mappings

### Current Mappings

The following metrics are currently mapped to LOINC codes:

| Kyoro Metric | LOINC Code | LOINC Display |
|--------------|------------|---------------|
| `heart_rate` | 8867-4 | Heart rate |
| `hrv_rmssd` | — | no confirmed LOINC code found, deliberately left unmapped (see `fhir_metric_codes.json`, `_pending_verification`) rather than guessed |
| `hrv_sdnn` | 80404-7 | R-R interval.standard deviation (Heart rate variability) |
| `oxygen_saturation` | 59408-5 | Oxygen saturation in Arterial blood by Pulse oximetry |
| `total_sleep_min` | 93832-4 | Sleep duration |

### Adding New Mappings

To add a new metric mapping:

1. **Verify the LOINC code**: Visit [loinc.org](https://loinc.org) and search for the appropriate code
2. **Edit the mapping file**: Add the mapping to `scripts/exporters/fhir_metric_codes.json`
3. **Add verification information**: Include `verified_by` and `source_url_or_reference`

Example:
```json
{
  "mappings": {
    "new_metric": {
      "system": "http://loinc.org",
      "code": "12345-6",
      "display": "New Metric Display Name",
      "verified_by": "Your Name",
      "source_url_or_reference": "https://loinc.org/12345-6/"
    }
  }
}
```

### Unmapped Metrics

Metrics that don't have LOINC mappings are listed in the `_unmapped_for_now` array and reported in `fhir_export_unmapped_metrics.txt`.

Current unmapped metrics:
- `blood_pressure_systolic`
- `blood_pressure_diastolic`
- `body_weight`
- `body_temperature`
- `respiratory_rate`

## Validation

The FHIR export includes basic validation:
- All required fields are present
- Resource types are correct
- References between resources are valid

For full FHIR R4 validation, use external tools like:
- [HL7 FHIR Validator](https://confluence.hl7.org/display/FHIR/Using+the+FHIR+Validator)
- [HAPI FHIR Validator](https://hapifhir.io/hapi-fhir/docs/validation/)

## Limitations

1. **Export Only**: This is an export-only feature. Kyoro HealthHub does not currently support FHIR import or act as a FHIR server.
2. **No HL7 v2 Support**: Only FHIR R4 format is supported.
3. **Limited Resource Types**: Currently supports Patient, Observation, Condition, and MedicationStatement.
4. **Manual Code Verification**: LOINC/SNOMED codes must be manually verified before adding to the mapping file.

## Compliance

- **Privacy**: All exports use pseudonyms, no real names or identifiable information
- **Data Minimization**: Only data specified in the export profile is included
- **Audit Trail**: Exports are logged in the system's access logs

## Troubleshooting

### No FHIR Bundle Created

- Check that the export profile includes queries with metric data
- Verify that the metrics have LOINC mappings in `fhir_metric_codes.json`
- Check the console output for error messages

### Unmapped Metrics Report

If you see many unmapped metrics:
- Check `fhir_export_unmapped_metrics.txt` for the list
- Consider adding LOINC mappings for frequently used metrics
- Verify that your data uses the expected metric names

### Validation Errors

Use external FHIR validators to check the bundle:
```bash
# Example using HAPI validator
java -jar fhir-validator-cli.jar fhir_bundle.json
```

## Where an export could go (manual submission, not automated)

Kyoro never uploads or transmits anything on its own — every export
(`export_research_cohort.py`, this FHIR export) only ever writes a local
file. If you want to donate an anonymized export to research, you have to
submit it yourself. This section only documents realistic destinations
that currently exist; it is not a recommendation to use one over the
other, and it is not legal or ethical advice about whether donating your
own data is right for you.

**[Zenodo](https://zenodo.org/)** (operated by CERN) — general-purpose
open research data repository. No institutional affiliation required, free
account, up to 50GB per upload, any file type, immediate DOI on
publication. Supports **restricted access** (not just fully public) —
relevant if you want the export discoverable/citable but not openly
downloadable by anyone. Straightforward fit for a FHIR bundle or a
research-cohort CSV export as-is.

**[PhysioNet](https://physionet.org/)** — repository specifically for
physiological/wearable signal data (ECG, HRV, and similar), reaches the
research community that actually works with this kind of data more
directly than a general-purpose repository would. Free PhysioNetWorks
account, then a project with your files plus a short README describing
the dataset. More formal than Zenodo (comparable to submitting to a
journal) and legally requires the data to be de-identified first — which
is exactly what `export_research_cohort.py`'s k-anonymity/date-shifting
step is for.

**DeSci ("Decentralized Science")** — not a submission destination in
itself, but background worth knowing if you're weighing where to donate.
DeSci is a set of funding/publishing mechanisms (IP-NFTs, topic-specific
DAOs, quadratic funding) built to route around exactly the bottleneck that
hits niche or unconventional research hardest: traditional grant bodies
are slow, risk-averse, and concentrated in a handful of institutions, so
under-resourced fields (e.g. longevity/aging, ME/CFS, Long-COVID, other
post-infectious or rare conditions) struggle to get funded through them
even when the science is sound. DeSci mechanisms let many small funders
back a project directly instead of waiting on one large gatekeeper, and
some DeSci-funded groups actively look for exactly the kind of
longitudinal, patient-owned data an export like this contains. Concrete
entry point: **[VitaDAO](https://www.vitadao.com/)** funds longevity/aging
research through a community-governed treasury and is the most
established example of the model. Most DeSci funding activity currently
runs on **Ethereum** — VitaDAO and most comparable projects are built on
Ethereum infrastructure, and Ethereum co-founder Vitalik Buterin is a
notable public supporter/funder of VitaDAO specifically and of DeSci and
longevity research more broadly. Kyoro itself has no blockchain component
and isn't a DeSci project — this is purely about a funding/community angle
worth knowing about when deciding where a donated export might do the
most good.

**Specific institutions/research groups** (e.g. a university hospital's
Long-COVID/ME-CFS or cardiology research group) — a different kind of
path than the two self-service repositories above: there's no generic
upload portal, you'd contact a specific research group directly and ask
whether they want the data, which usually means going through their own
consent/ethics process rather than Kyoro's export alone. Best fit when
there's already a real connection (an existing clinical relationship, a
group whose published research topic matches the data closely) rather
than a cold submission.

Before submitting anywhere: re-read the export's own manifest/consent
records, and double-check the target's own data-sharing policy for
health-adjacent data — requirements differ per platform and can change.

## Future Enhancements

- Add support for more FHIR resource types
- Implement automatic LOINC code lookup (with human verification)
- Add FHIR schema validation
- Support for SNOMED-CT codes in addition to LOINC
- Implement FHIR search parameters in export

## References

- [HL7 FHIR R4 Specification](http://hl7.org/fhir/R4/)
- [LOINC User Guide](https://loinc.org/usage/guide/)
- [UCUM Units Specification](https://ucum.org/ucum.html)
- [FHIR Bundle Resource](http://hl7.org/fhir/R4/bundle.html)

## See Also

- [Export Profiles](../README.md#doctor-export-profiles) — profile list and usage in the README
- [Privacy Architecture](PRIVACY_ARCHITECTURE.md)
- [Contributing Guide](CONTRIBUTING.md)