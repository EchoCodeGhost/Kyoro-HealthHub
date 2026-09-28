#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fhir_validate.py — Strukturelle FHIR-R4(B)-Validierung für den Export-Bundle

@tier        infrastructure
@purpose.de  Validiert das gebaute FHIR-Bundle strukturell (Pflichtfelder,
             Kardinalitäten, Typen) bevor es auf die Platte geschrieben
             wird, und bricht mit einer klaren Fehlermeldung ab, wenn die
             Struktur nicht dem FHIR-Schema entspricht.
@purpose.en  Structurally validates the built FHIR bundle (required
             fields, cardinalities, types) before it is written to disk,
             aborting with a clear error message if the structure does
             not conform to the FHIR schema.
@method.de
  - validate_bundle(bundle: dict) -> None: wirft ValueError bei
    Strukturverstößen, RuntimeError wenn die Validierungs-Bibliothek
    fehlt. Kein Rückgabewert bei Erfolg.
@method.en
  - validate_bundle(bundle: dict) -> None: raises ValueError on
    structural violations, RuntimeError if the validation library is
    missing. No return value on success.
@reads      nichts von der Platte / nothing from disk — arbeitet nur mit
            dem übergebenen dict im Speicher
@writes     nichts / nothing
@limits.de
  - Validiert nur die Basis-FHIR-R4B-Ressourcenform (Pflichtfelder,
    Datentypen, Kardinalität) — KEINE Terminologie-Prüfung (ob ein
    LOINC-Code real existiert), KEINE US-Core- oder andere Profile.
  - "R4B" statt reinem "R4": siehe Provenienz-Kommentar unten — das
    verwendete Paket bietet in der installierten Version kein reines
    R4-Modellpaket an, nur R4B (HL7-Fehlerkorrekturversion von R4,
    für Bundle/Observation/Condition/Patient/MedicationStatement ohne
    Strukturbruch gegenüber R4).

@relevance.de  Bietet FHIR-Schnittstellen, essentiell für die standardisierte Datenübertragung
@relevance.en  Provides FHIR interfaces, essential for standardized data exchange
@limits.en
  - Validates only the base FHIR R4B resource shape (required fields,
    data types, cardinality) — NO terminology check (whether a LOINC
    code genuinely exists), NO US Core or other profiles.
  - "R4B" instead of pure "R4": see provenance note below — the
    installed version of the package used here ships no pure-R4 model
    package, only R4B (HL7's technical-correction release of R4; no
    structural break for Bundle/Observation/Condition/Patient/
    MedicationStatement versus R4).
@usage
    from fhir_validate import validate_bundle
    validate_bundle(bundle_dict)  # raises on failure, returns None on success
"""

from typing import Dict

# ---------------------------------------------------------------------------
# Provenance of the structural validation (see also docs/FHIR_EXPORT.md,
# "Validation" section, and openspec/changes/add-fhir-export/design.md D3):
#
# We deliberately do NOT hand-vendor a FHIR R4 JSON Schema file into this
# repo. Hand-transcribing (or having an LLM recall) a multi-thousand-line
# HL7 FHIR JSON Schema from memory would risk exactly the kind of silent
# fabrication this project's own conventions warn against (see D2 in the
# design doc, written about the LOINC mapping table but equally true here)
# — an LLM cannot reliably verify offline that a hand-written schema
# fragment is byte-for-byte faithful to the real HL7 distribution.
#
# Instead we depend on the `fhir.resources` PyPI package
# (https://pypi.org/project/fhir.resources/, source
# https://github.com/nazrulworld/fhir.resources, BSD-3 licensed). Its
# pydantic model classes are code-generated directly from HL7's official
# FHIR StructureDefinitions (not hand-authored), so parsing our built
# Bundle dict through these models gives genuine structural validation
# (required fields, cardinalities, value types, resourceType/discriminator
# checks) without any hallucination risk on our side — the schema-derived
# code lives in a versioned, independently maintained package, not in a
# file we wrote from memory.
#
# Version note: the installed release (fhir.resources 8.3.0, pydantic v2
# native) still only ships R4B / R5 / STU3 model packages, not a pure "R4"
# package — unchanged from earlier releases. We use R4B because it is the
# closest available FHIR-4-generation release; for the four resource types
# this export produces (Bundle, Patient, Observation, Condition) and the
# optional MedicationStatement, R4B introduced no structural break versus
# R4 (R4B's changes were additive — new resources and a handful of
# unrelated resource types — see HL7's R4B release notes). If a pure-R4
# model package becomes available as a dependency in the future, swapping
# the import below is the only change needed.
FHIR_VALIDATION_SOURCE = (
    "fhir.resources==8.3.0 (PyPI), pydantic models generated from HL7 FHIR "
    "R4B StructureDefinitions — https://pypi.org/project/fhir.resources/"
)

try:
    from fhir.resources.R4B.bundle import Bundle as _FHIRBundle
    _FHIR_RESOURCES_AVAILABLE = True
except ImportError:
    _FHIR_RESOURCES_AVAILABLE = False


def validate_bundle(bundle: Dict) -> None:
    """
    Validiert ein FHIR-Bundle-Dict strukturell. Wirft bei Verstößen eine
    Exception; gibt bei Erfolg nichts zurück.

    Validates a FHIR bundle dict structurally. Raises on violation;
    returns nothing on success.
    """
    # The underlying pydantic models default resourceType to the literal
    # value of the model being used (Bundle), so a *completely missing*
    # top-level "resourceType" key would otherwise silently pass — that
    # would defeat the explicit "reject a bundle missing resourceType"
    # requirement this validation exists for. Check it ourselves first.
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise ValueError(
            "FHIR bundle failed structural validation: top-level object is "
            "missing the required 'resourceType': 'Bundle' field (or it has "
            f"an unexpected value: {bundle.get('resourceType') if isinstance(bundle, dict) else type(bundle)!r}). "
            "Export aborted — no file was written."
        )

    if not _FHIR_RESOURCES_AVAILABLE:
        raise RuntimeError(
            "FHIR structural validation unavailable: the 'fhir.resources' "
            "package is not installed (see requirements.txt). Validation is "
            "mandatory before writing a FHIR export — install the dependency "
            "and re-run rather than skipping validation."
        )

    try:
        _FHIRBundle.model_validate(bundle)
    except Exception as e:  # pydantic ValidationError, but caught broadly
        # on purpose so any structural issue surfaces as one clear message
        raise ValueError(
            "FHIR bundle failed structural validation against "
            f"{FHIR_VALIDATION_SOURCE}:\n{e}\n"
            "Export aborted — no file was written."
        ) from e


if __name__ == "__main__":
    # Beispielnutzung / example usage
    ok = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": {
            "resourceType": "Patient", "id": "PAT-TEST", "active": True
        }}],
    }
    validate_bundle(ok)
    print("OK bundle passed validation as expected")

    bad = {"type": "collection", "entry": []}
    try:
        validate_bundle(bad)
        print("ERROR: bad bundle should have been rejected")
    except ValueError as e:
        print("bad bundle correctly rejected:", e)
