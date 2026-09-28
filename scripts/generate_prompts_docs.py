#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
generate_prompts_docs.py — Automatische Generierung von docs/prompts.md

@tier        infrastructure
@purpose.de  Generiert docs/prompts.md automatisch aus der zentralen Prompt-Registry
             (modules.prompts). Ersetzt die manuelle Pflege der Dokumentation.
@purpose.en  Automatically generates docs/prompts.md from the central prompt registry
             (modules.prompts). Replaces manual maintenance of the documentation.
@method.de   1) Importiert alle Prompt-Module, 2) Liest alle registrierten Prompts via
             all_prompts(), 3) Generiert Markdown mit Übersichtstabelle und
             detaillierten Prompt-Informationen, 4) Behält erklärende Abschnitte aus
             der Vorlage bei, 5) Fügt Versionshistorie hinzu.
@method.en   1) Imports all prompt modules, 2) Reads all registered prompts via
             all_prompts(), 3) Generates markdown with overview table and
             detailed prompt information, 4) Preserves explanatory sections from
             the template, 5) Adds version history.
@reads       Alle Dateien in scripts/modules/prompts/
@writes      docs/prompts.md
@limits.de   Generiert nur die Tabellen-Teile automatisch; erklärende Abschnitte
             werden aus einer Vorlage übernommen.
@limits.en   Only generates the table parts automatically; explanatory sections
             are taken from a template.
@relevance.de  Hält den Prompt-Katalog synchron mit der Registry, verhindert
               erneutes manuelles Auseinanderdriften von Dokumentation und Code.
@relevance.en  Keeps the prompt catalog in sync with the registry, preventing
               documentation and code from drifting apart again.
@usage
    python scripts/generate_prompts_docs.py
    python scripts/generate_prompts_docs.py --check
"""

import argparse
import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from modules.prompts import all_prompts


# Template sections that are preserved from the original docs/prompts.md
TEMPLATE_SECTIONS = {
    "header": """# 🤖 LLM & VLM Prompt-Katalog

**Projekt:** Kyoro-HealthHub  
**Version:** {version}  
**Status:** Aktiv  
**Verantwortlich:** Technisches Team / LLM-Experten  

---

## 📋 Inhaltsverzeichnis

1. [Einleitung & Zweck](#einleitung--zweck)
2. [Übersichtstabelle](#übersichtstabelle)
3. [Prompt-Typen](#prompt-typen)
   - [3.1 LLM-Prompts](#31-llm-prompts)
   - [3.2 VLM-Prompts](#32-vlm-prompts)
   - [3.3 SQL-Prompts](#33-sql-prompts)
   - [3.4 Hybrid-Prompts](#34-hybrid-prompts)
4. [Skript-spezifische Prompts](#skript-spezifische-prompts)
5. [Best Practices für Prompt-Design](#best-practices-für-prompt-design)
6. [Wartung & Aktualisierung](#wartung--aktualisierung)

---

## 🎯 Einleitung & Zweck

Dieses Dokument **sammelt und dokumentiert alle LLM- und VLM-Prompts**, die in den Kyoro-HealthHub-Skripten verwendet werden.

### Warum ist das wichtig?

1. **Transparenz:** Alle Prompts sind an einer zentralen Stelle einsehbar
2. **Wartbarkeit:** Änderungen an Prompts können nachvollzogen werden
3. **Qualitätssicherung:** Prompts können auf Konsistenz und medizinische Korrektheit geprüft werden
4. **Compliance:** Datenschutz- und ethische Richtlinien werden eingehalten
5. **Wiederverwendung:** Ähnliche Prompts können in anderen Skripten wiederverwendet werden

### Dokumentationsstandard

Jeder Prompt **MUSS** im Skript-Docstring dokumentiert werden:
```python
@prompt-classification LLM:System, LLM:Interpretation
@prompt.de    [Deutscher Prompt-Text]
@prompt.en    [Englischer Prompt-Text]
```""",

    "prompt_types": """## 🏷️ Prompt-Typen

### Klassifizierungssystem

| **Haupttyp** | **Subtyp** | **Beschreibung** | **Verwendungszweck** |
|--------------|------------|-----------------|---------------------|
| **LLM** | System | Definiert die Rolle/Identität des Modells | Rollenbeschreibung, Kontextsetzung |
| **LLM** | User | Die eigentliche Frage/Anweisung an das Modell | Benutzeranfragen, Analysen |
| **LLM** | Interpretation | Interpretation von Daten/Ergebnissen | Medizinische Bewertung, Mustererkennung |
| **LLM** | Summary | Zusammenfassung von Daten/Ergebnissen | Berichte, Überblicke |
| **LLM** | Analysis | Detaillierte Datenanalyse | Trendanalyse, statistische Auswertung |
| **VLM** | Medical | Medizinische Bildanalyse | EKG, Röntgen, MRT, andere medizinische Bilder |
| **VLM** | Technical | Technische Bildanalyse | Diagramme, Tabellen, Grafiken |
| **VLM** | Document | Dokumentenanalyse | PDFs, Scans, Formulare |
| **SQL** | Query | SQL-Abfragegenerierung | Natursprache → SQL |
| **SQL** | Translation | SQL-Erklärung | SQL → Natursprache |
| **Hybrid** | LLM+VLM | Kombinierte Text- und Bildverarbeitung | Multimodale Analysen |
| **Hybrid** | LLM+SQL | Kombinierte Abfrage und Analyse | Datenabfrage + Interpretation |""",

    "best_practices": """## 📖 Best Practices für Prompt-Design

### 1. **Rollendefinition (System-Prompts)**

✅ **Gut:**
```text
Du bist ein erfahrener Kardiologe mit 10 Jahren Erfahrung in der
Analyse von Herzrhythmusstörungen. Du bist vorsichtig und konservativ
in deinen Bewertungen.
```

❌ **Schlecht:**
```text
Du bist ein Chatbot.
```

**Begründung:** Spezifische Rollen führen zu besseren, kontextgerechten Antworten.

---

### 2. **Kontext bereitzustellen**

✅ **Gut:**
```text
Verfügbare Daten: heart_rate, resting_heart_rate, steps, sleep_analysis
Zeitraum: 2024-01-01 bis 2024-12-31
Person: Anonymisiert
```

❌ **Schlecht:**
```text
Analysiere die Daten.
```

**Begründung:** Modell weiß, welche Daten verfügbar sind und kann gezielt darauf eingehen.

---

### 3. **Medizinische Vorsicht**

✅ **Gut:**
```text
WICHTIG: Erfinde KEINE medizinischen Diagnosen, die nicht durch die Daten
belegt sind. Empfehle bei Auffälligkeiten ärztliche Abklärung.
```

❌ **Schlecht:**
```text
Stelle eine Diagnose.
```

**Begründung:** Vermeidet falsche medizinische Aussagen und rechtliche Probleme.

---

### 4. **Sprachliche Konsistenz**

✅ **Gut:**
```text
Antworte ausschließlich auf Deutsch.
```

❌ **Schlecht:**
```text
Antworte auf Deutsch oder Englisch.
```

**Begründung:** Vermeidet Sprachmischungen und sichert Qualität.

---

### 5. **Strukturierte Ausgaben**

✅ **Gut:**
```text
Formatierung:
1. Zusammenfassung (1 Absatz)
2. Detaillierte Analyse (Aufzählungen)
3. Empfehlungen (nummeriert)
4. Einschränkungen (falls zutreffend)
```

❌ **Schlecht:**
```text
Schreib einfach was du denkst.
```

**Begründung:** Strukturierte Ausgaben sind leichter zu parsen und zu verstehen.

---

### 6. **Begrenzungen setzen**

✅ **Gut:**
```text
- MAX_TOKENS: 2000
- Temperatur: 0.3 (deterministisch)
- Antwortlänge: 3-5 Absätze
```

❌ **Schlecht:**
```text
Schreib so viel du willst.
```

**Begründung:** Vermeidet zu lange, unstrukturierte Antworten.""",

    "maintenance": """## 🔄 Wartung & Aktualisierung

### Prozess für neue Prompts

1. **Prompt im Skript erstellen** (mit Variablen für Flexibilität)
2. **Skript-Docstring aktualisieren** mit @prompt-Tags
3. **Prompt hier dokumentieren** (Kopie der ersten 2-3 Zeilen)
4. **Validierung durchführen** (`python scripts/check_docstrings.py`)
5. **Medizinische Review** (falls medizinisch relevant)
6. **Compliance-Check** (keine Diagnosen, Geschlecht, Alter, Orte)

### Regelmäßige Reviews

| Aufgabe | Häufigkeit | Verantwortlich |
|---------|------------|----------------|
| Prompt-Validität prüfen | Monatlich | LLM-Experte |
| Medizinische Korrektheit | Quartalsweise | Medizinischer Berater |
| Compliance-Check | Vor jedem Release | Projektleitung |
| Performance-Optimierung | Bei Bedarf | Technisches Team |""",

    "support": """## 📞 Support & Ressourcen

### Tools
- **Validierung:** `python scripts/check_docstrings.py`
- **Prompt-Extraktion:** `python scripts/generate_prompts_docs.py`

### Dokumentation
- **Dieser Katalog:** `docs/prompts.md`
- **Docstring-Template:** `docs/docstring_template.md`

### Ansprechpartner
| Frage | Verantwortlich | Kontakt |
|-------|---------------|---------|
| Prompt-Design | LLM-Experte | [E-Mail] |
| Medizinische Inhalte | Medizinischer Berater | [E-Mail] |
| Technische Integration | Technischer Lead | [E-Mail] |""",

    "footer": """---

*Dieses Dokument unterliegt der GPL-3.0-or-later Lizenz.*
*Automatisch aus scripts/modules/prompts/ generiert*
*Generated by Mistral Vibe. Co-Authored-By: Mistral Vibe <vibe@mistral.ai>*"""
}


def _get_lang_display(lang: str) -> str:
    """Get display name for language field."""
    lang_map = {
        "de": "Deutsch",
        "en": "Englisch",
        "bilingual": "Bilingual (DE/EN)",
        "de_only": "Nur Deutsch"
    }
    return lang_map.get(lang, lang)


def _get_owner_display(owner: str) -> str:
    """Convert owner path to display format."""
    # Keep the full path for display
    return owner


def _get_prompt_type(classification: str) -> str:
    """Extract main prompt type from classification."""
    if "VLM" in classification:
        return "VLM"
    elif "SQL" in classification:
        return "SQL"
    elif "Hybrid" in classification:
        return "Hybrid"
    else:
        return "LLM"


def _generate_overview_table(prompts: list) -> str:
    """Generate the overview table section."""
    # Group by owner
    by_owner = {}
    for prompt in prompts:
        owner = prompt.owner
        if owner not in by_owner:
            by_owner[owner] = []
        by_owner[owner].append(prompt)
    
    # Sort owners
    sorted_owners = sorted(by_owner.keys())
    
    # Build table rows
    rows = []
    for owner in sorted_owners:
        owner_prompts = by_owner[owner]
        
        # Get classifications and types
        classifications = set()
        types = set()
        for p in owner_prompts:
            classifications.update(p.classification.split(", "))
            types.add(_get_prompt_type(p.classification))
        
        # Count prompts
        prompt_count = len(owner_prompts)
        
        # Get language info
        langs = set(p.lang for p in owner_prompts)
        lang_display = ", ".join(sorted(_get_lang_display(l) for l in langs))
        
        # Build classification string
        class_str = ", ".join(sorted(classifications))
        type_str = ", ".join(sorted(types))
        
        # Create relative path for link
        owner_display = _get_owner_display(owner)
        # Remove 'scripts/' prefix for display and link
        if owner_display.startswith("scripts/"):
            display_name = owner_display[8:]  # "scripts/" is 8 characters
            link_path = owner_display
        else:
            display_name = owner_display
            link_path = owner_display
        file_link = f"[{display_name}](../{link_path})"
        
        # Status - all registered prompts are documented
        status = "✅ Dokumentiert"
        
        rows.append(f"| {file_link} | {class_str} | {type_str} | {prompt_count} | {lang_display} | {status} |")
    
    # Build table
    table = """## 📊 Übersichtstabelle

| **Skript** | **Klassifizierung** | **Typ** | **Anzahl** | **Sprache** | **Status** |
|------------|---------------------|---------|------------|-------------|-----------|
"""
    
    table += "\n".join(rows) + "\n\n"
    
    table += """**Legende:**
- ✅ **Dokumentiert:** Prompts sind in der Registry registriert und hier dokumentiert
- ⚠️ **Teilweise:** Einige Prompts dokumentiert
- ❌ **Pendend:** Prompts noch nicht dokumentiert

---
"""
    
    return table


def _generate_script_specific_prompts(prompts: list) -> str:
    """Generate the script-specific prompts section."""
    # Group by owner
    by_owner = {}
    for prompt in prompts:
        owner = prompt.owner
        if owner not in by_owner:
            by_owner[owner] = []
        by_owner[owner].append(prompt)
    
    # Sort owners
    sorted_owners = sorted(by_owner.keys())
    
    content = "## 📝 Skript-spezifische Prompts\n\n"
    
    for owner in sorted_owners:
        owner_prompts = by_owner[owner]
        owner_display = _get_owner_display(owner)
        
        # Get classifications for this owner
        classifications = set()
        for p in owner_prompts:
            classifications.update(p.classification.split(", "))
        class_str = ", ".join(sorted(classifications))
        
        # Format display name (remove scripts/ prefix)
        if owner_display.startswith("scripts/"):
            display_name = owner_display[8:]  # "scripts/" is 8 characters
        else:
            display_name = owner_display
        
        content += f"### 🔹 {display_name}\n\n"
        content += f"**Pfad:** [`{owner}`](../{owner})  \n"
        content += f"**Klassifizierung:** `{class_str}`  \n"
        content += f"**Status:** ✅ Dokumentiert  \n"
        content += f"**Verantwortlich:** LLM-Infrastruktur  \n\n"
        
        # Add each prompt
        for i, prompt in enumerate(owner_prompts, 1):
            content += f"#### Prompt {i}: {prompt.name} ({prompt.classification})\n\n"
            content += f"**Klassifizierung:** {prompt.classification}  \n"
            content += f"**Zweck:** {_get_prompt_purpose(prompt)}  \n"
            
            # Add text based on language
            if prompt.text:
                content += "**Deutsch:**\n```text\n"
                content += prompt.text + "\n```\n\n"
            elif prompt.text_de:
                content += "**Deutsch:**\n```text\n"
                content += prompt.text_de + "\n```\n\n"
                content += "**Englisch:**\n```text\n"
                content += (prompt.text_en or "") + "\n```\n\n"
            
            content += f"**Quellcode:** Konstante `{prompt.name}` in [`{owner}`](../{owner})  \n"
            content += "**Variablen:** " + _get_prompt_variables(prompt) + "  \n"
            content += "**Besonderheiten:**\n"
            content += _get_prompt_special_notes(prompt) + "\n\n"
            content += "---\n\n"
    
    return content


def _get_prompt_purpose(prompt) -> str:
    """Extract purpose from prompt text or classification."""
    # Simple heuristic based on classification
    if "SQL" in prompt.classification:
        return "Generiert SQL-Abfragen aus Natursprache"
    elif "Interpretation" in prompt.classification:
        return "Interpretiert Daten und beantwortet medizinische Fragen"
    elif "Summary" in prompt.classification:
        return "Generiert strukturierte medizinische Berichte"
    elif "System" in prompt.classification:
        return "Definiert die Rolle/Identität des Modells"
    elif "VLM" in prompt.classification:
        return "Analysiert medizinische Bilder/Dokumente"
    else:
        return "Allgemeine LLM-Anfrage"


def _get_prompt_variables(prompt) -> str:
    """Extract variables from prompt text."""
    import re
    if prompt.text:
        text = prompt.text
    elif prompt.text_de:
        text = prompt.text_de
    else:
        return "Keine (statisch)"
    
    # Find placeholder patterns
    variables = re.findall(r'\{[^}]+\}', text)
    if variables:
        return ", ".join(variables)
    return "Keine (statisch)"


def _get_prompt_special_notes(prompt) -> str:
    """Generate special notes for a prompt."""
    notes = []
    
    if prompt.text and "WICHTIG" in prompt.text:
        notes.append("- Enthält medizinische Vorsichtsanweisungen")
    if prompt.text and "Antworte ausschließlich auf Deutsch" in prompt.text:
        notes.append("- Sprachliche Beschränkung: Nur Deutsch")
    if prompt.text and "Answer exclusively in" in prompt.text:
        notes.append("- Sprachliche Beschränkung: Exklusive Sprachausgabe")
    if "SQL" in prompt.classification:
        notes.append("- Verhindert Halluzinationen von Tabellen/Spalten")
        notes.append("- Begrenzt Ergebnisse auf 50 Zeilen")
    
    if not notes:
        notes.append("- Keine besonderen Merkmale")
    
    return "\n".join(notes)


def _generate_version_history() -> str:
    """Generate version history table."""
    history = """### Versionshistorie

| Version | Autor | Änderungen |
|---------|-------|-----------|
| 1.0 | Mistral Vibe | Initialer Prompt-Katalog erstellt |
| — | — | Automatisch aus scripts/modules/prompts/ generiert |
"""
    return history


def generate_prompts_md(output_path: Path, version: str = "2.0") -> str:
    """Generate the complete prompts.md content."""
    # Import all prompt modules to ensure registration
    try:
        # Import query prompts
        from modules.prompts import query
        # Import analysis prompts
        from modules.prompts import analysis_activity
        from modules.prompts import analysis_cardiovascular
        from modules.prompts import analysis_cycle
        from modules.prompts import analysis_environment
        from modules.prompts import analysis_immunology
        from modules.prompts import analysis_infectious
        from modules.prompts import analysis_internal_medicine
        from modules.prompts import analysis_longevity
        from modules.prompts import analysis_manual
        from modules.prompts import analysis_metabolic
        from modules.prompts import analysis_neurology
        from modules.prompts import analysis_ophthalmology
        from modules.prompts import analysis_psychology
        from modules.prompts import analysis_sleep
        from modules.prompts import importers
    except ImportError as e:
        print(f"ERROR: Failed to import prompt modules: {e}")
        sys.exit(1)
    
    # Get all prompts
    prompts = all_prompts()
    
    # Build content
    content = TEMPLATE_SECTIONS["header"].format(version=version)
    content += TEMPLATE_SECTIONS["prompt_types"]
    content += _generate_overview_table(prompts)
    content += _generate_script_specific_prompts(prompts)
    content += TEMPLATE_SECTIONS["best_practices"]
    content += TEMPLATE_SECTIONS["maintenance"]
    content += _generate_version_history()
    content += TEMPLATE_SECTIONS["support"]
    content += TEMPLATE_SECTIONS["footer"]
    
    return content


def check_prompts_docs_sync() -> bool:
    """Check if docs/prompts.md is in sync with the registry."""
    import re
    
    # Import all prompt modules
    try:
        from modules.prompts import query
        from modules.prompts import analysis_activity
        from modules.prompts import analysis_cardiovascular
        from modules.prompts import analysis_cycle
        from modules.prompts import analysis_environment
        from modules.prompts import analysis_immunology
        from modules.prompts import analysis_infectious
        from modules.prompts import analysis_internal_medicine
        from modules.prompts import analysis_longevity
        from modules.prompts import analysis_manual
        from modules.prompts import analysis_metabolic
        from modules.prompts import analysis_neurology
        from modules.prompts import analysis_ophthalmology
        from modules.prompts import analysis_psychology
        from modules.prompts import analysis_sleep
        from modules.prompts import importers
    except ImportError as e:
        print(f"ERROR: Failed to import prompt modules: {e}")
        return False
    
    prompts = all_prompts()
    
    # Check if docs/prompts.md exists
    prompts_md_path = Path(__file__).parent.parent / "docs" / "prompts.md"
    if not prompts_md_path.exists():
        print("ERROR: docs/prompts.md does not exist")
        return False
    
    # Read current content
    current_content = prompts_md_path.read_text(encoding="utf-8")
    
    # Check for auto-generated marker
    if "Automatisch aus scripts/modules/prompts/ generiert" not in current_content:
        print("ERROR: docs/prompts.md does not contain auto-generated marker")
        return False
    
    # Count prompts in registry vs. documented
    registry_count = len(prompts)
    
    # Count documented prompts (look for "#### Prompt" patterns)
    documented_count = len(re.findall(r'#### Prompt \d+:', current_content))
    
    if registry_count != documented_count:
        print(f"ERROR: Prompt count mismatch - Registry: {registry_count}, Documented: {documented_count}")
        return False
    
    print(f"OK: {registry_count} prompts in registry match {documented_count} documented prompts")
    return True


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate docs/prompts.md from prompt registry"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="docs/prompts.md",
        help="Output file path (default: docs/prompts.md)"
    )
    parser.add_argument(
        "--version", 
        type=str, 
        default="2.0",
        help="Version number for the generated document"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if docs/prompts.md is in sync with registry"
    )

    args = parser.parse_args()

    if args.check:
        success = check_prompts_docs_sync()
        return 0 if success else 1

    # Generate content
    output_path = Path(args.output)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate content
    content = generate_prompts_md(output_path, args.version)
    
    # Write file
    output_path.write_text(content, encoding="utf-8")
    print(f"Generated {output_path} with {len(all_prompts())} prompts")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
