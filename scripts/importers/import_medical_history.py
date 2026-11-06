#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_medical_history.py — Extracts dated events from free-text medical history

@tier        infrastructure
@purpose.de  Extrahiert datierte Ereignisse aus Freitext-Medizinischer Anamnese
@purpose.en  Extracts dated events from free-text medical history
@method.de   Liest imports/manual/timeline_symptome.txt und verwendet ein LOKALES LLM,
             um datierte Ereignisse nach imports/manual/life_events.json zu extrahieren.
             WICHTIG: Dieses Skript verarbeitet sensible persoenliche Gesundheitsdaten.
             Es verweigert die Ausfuehrung mit externen/Cloud-LLM-Anbietern — bei
             Provider "multi" wird das tatsaechlich geroutete Backend geprueft
             (modules.llm.resolve_local_backend), nicht nur der Top-Level-String.
             Nur lokale Anbieter sind zugelassen: openvino, ovms, ollama, lmstudio,
             llamacpp, exo, mlx.
@method.en   Reads imports/manual/timeline_symptome.txt and uses a LOCAL LLM to extract
             dated events into imports/manual/life_events.json for user review and import.
             IMPORTANT: This script processes sensitive personal health data.
             It will refuse to run with any external/cloud LLM provider — for
             provider "multi" it checks the actually-routed backend
             (modules.llm.resolve_local_backend), not just the top-level string.
             Only local providers are permitted: openvino, ovms, ollama, lmstudio,
             llamacpp, exo, mlx.
@reads       imports/manual/timeline_symptome.txt
@writes      imports/manual/life_events.json
@limits.de   Nur lokale LLM-Anbieter. Keine Cloud-Integration.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Only local LLM providers. No cloud integration.
@usage
    python3 scripts/importers/import_medical_history.py
    python3 scripts/importers/import_medical_history.py --timeline path/to/file.txt
    python3 scripts/importers/import_medical_history.py --lang en
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.importers import PROMPT_DE, PROMPT_EN
from modules.llm import resolve_local_backend


def _require_local_provider(_unused: str = "") -> None:
    """Hard abort if the effective backend isn't local — sensitive data must
    not leave the device. Resolves "multi" routing via resolve_local_backend()
    (modules.llm) instead of inspecting the top-level provider string, which
    for "multi" would just say "multi" and tell us nothing about where the
    actual request would go."""
    is_local, effective = resolve_local_backend("importer")
    if not is_local:
        print(t(
            f"\nFEHLER: Effektiver Provider '{effective}' ist nicht lokal.\n"
            "Diese Datei enthält sensible Gesundheitsdaten und darf NICHT an externe\n"
            "Dienste gesendet werden. Bitte einen lokalen Provider konfigurieren:\n"
            "  z.B. openvino, ovms, ollama, lmstudio, llamacpp, exo, mlx\n"
            "  In ~/.config/kyoro/health_config.json: \"llm\": {\"provider\": \"ollama\"}\n"
            "  (oder bei \"multi\": einen lokalen Eintrag unter multi_backends[\"importer\"])",
            f"\nERROR: Effective provider '{effective}' is not local.\n"
            "This file contains sensitive health data and MUST NOT be sent to external\n"
            "services. Please configure a local provider:\n"
            "  e.g. openvino, ovms, ollama, lmstudio, llamacpp, exo, mlx\n"
            "  In ~/.config/kyoro/health_config.json: \"llm\": {\"provider\": \"ollama\"}\n"
            "  (or for \"multi\": add a local entry under multi_backends[\"importer\"])",
            ))
        sys.exit(1)


def _extract_json(text: str) -> list[dict]:
    """Extract JSON array from LLM response, tolerating markdown fences."""
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Find first '[' to last ']'
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    return json.loads(text[start : end + 1])


def _validate_events(events: list[dict]) -> list[dict]:
    """Validate and normalise extracted events; drop malformed ones."""
    valid = []
    required = {"date", "type", "label"}
    valid_types = {
        "infection", "vaccination", "diagnosis", "medication_start", "medication_stop",
        "hospitalization", "test_result", "symptom_onset", "symptom_resolution", "other",
    }
    valid_precision = {"day", "month", "year"}

    for ev in events:
        if not required.issubset(ev.keys()):
            continue
        # Validate date format
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(ev.get("date", ""))):
            continue
        ev.setdefault("date_precision", "day")
        ev.setdefault("notes", "")
        ev["type"] = ev["type"] if ev["type"] in valid_types else "other"
        ev["date_precision"] = ev["date_precision"] if ev["date_precision"] in valid_precision else "day"
        ev["label"] = str(ev["label"])[:60]
        ev["notes"] = str(ev["notes"])[:120]
        valid.append(ev)

    return sorted(valid, key=lambda e: e["date"])


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Ereignisse aus Timeline-Datei extrahieren (nur lokales LLM)",
        "Extract life events from timeline file (local LLM only)",
    ))
    parser.add_argument(
        "--timeline",
        type=Path,
        default=None,
        help=t(
            "Pfad zur Timeline-Datei (Standard: imports/manual/timeline_symptome.txt)",
            "Path to timeline file (default: imports/manual/timeline_symptome.txt)",
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=t(
            "Ausgabe-JSON (Standard: imports/manual/life_events.json)",
            "Output JSON (default: imports/manual/life_events.json)",
        ),
    )
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    repo_root = Path(__file__).parents[2]

    timeline_path: Path = args.timeline or (repo_root / "imports" / "manual" / "timeline_symptome.txt")
    output_path: Path = args.output or (repo_root / "imports" / "manual" / "life_events.json")

    if not timeline_path.exists():
        print(t(
            f"Fehler: Timeline-Datei nicht gefunden: {timeline_path}",
            f"Error: Timeline file not found: {timeline_path}",
        ))
        sys.exit(1)

    _require_local_provider()  # hard-aborts if the effective backend isn't local
    is_local, effective = resolve_local_backend("importer")
    print(t(
        f"LLM-Provider: {effective} (lokal — Daten verlassen das Gerät nicht)",
        f"LLM provider: {effective} (local — data stays on device)",
    ))

    timeline_text = timeline_path.read_text(encoding="utf-8").strip()
    if not timeline_text:
        print(t("Fehler: Timeline-Datei ist leer.", "Error: Timeline file is empty."))
        sys.exit(1)

    print(t(
        f"Timeline geladen: {timeline_path.name} ({len(timeline_text)} Zeichen)",
        f"Timeline loaded: {timeline_path.name} ({len(timeline_text)} chars)",
    ))

    lang = getattr(args, "lang", "de") or "de"
    system_prompt = PROMPT_DE if lang == "de" else PROMPT_EN
    user_msg = timeline_text

    print(t("Sende an lokales LLM ...", "Sending to local LLM ..."))
    from modules.llm import call_llm_importer_only
    try:
        response = call_llm_importer_only(
            user_msg, system=system_prompt, purpose="Medizinische Anamnese-Timeline",
            max_tokens=4096, require_grounding=False, label_output=False,
        )
    except Exception as e:
        print(t(f"Fehler beim LLM-Aufruf: {e}", f"LLM call failed: {e}"))
        sys.exit(1)
    if response is None:
        sys.exit(1)  # require_local_llm inside call_llm_importer_only already printed why

    try:
        raw_events = _extract_json(response)
    except json.JSONDecodeError as e:
        print(t(
            f"Fehler: LLM-Antwort konnte nicht als JSON geparst werden: {e}\n"
            f"Antwort (erste 500 Zeichen):\n{response[:500]}",
            f"Error: Could not parse LLM response as JSON: {e}\n"
            f"Response (first 500 chars):\n{response[:500]}",
        ))
        sys.exit(1)

    events = _validate_events(raw_events)

    if not events:
        print(t(
            "Warnung: Keine validen Ereignisse extrahiert.",
            "Warning: No valid events extracted.",
        ))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(t(
        f"\n{len(events)} Ereignis(se) extrahiert → {output_path}",
        f"\n{len(events)} event(s) extracted → {output_path}",
    ))
    print(t(
        "Bitte Datei prüfen, bevor sie in die Datenbank importiert wird.",
        "Please review the file before importing it into the database.",
    ))

    # Show summary
    from collections import Counter
    type_counts = Counter(ev["type"] for ev in events)
    for etype, count in sorted(type_counts.items()):
        print(f"  {etype}: {count}")


if __name__ == "__main__":
    main()
