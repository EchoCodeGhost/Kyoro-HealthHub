# Docstring Template für Kyoro-HealthHub

**Version:** 1.0  
**Status:** Aktiv  

---

## 📋 Inhaltsverzeichnis

1. [Einleitung](#einleitung)
2. [Allgemeine Struktur](#allgemeine-struktur)
3. [Template nach Skript-Typ](#template-nach-skript-typ)
   - [3.1 Research-Skripte](#31-research-skripte)
   - [3.2 Heuristic-Skripte](#32-heuristic-skripte)
   - [3.3 Infrastructure-Skripte](#33-infrastructure-skripte)
   - [3.4 Validated-Skripte](#34-validated-skripte)
   - [3.5 Calibrated-Skripte](#35-calibrated-skripte)
   - [3.6 Experimental-Skripte](#36-experimental-skripte)
4. [Prompt-Dokumentation](#prompt-dokumentation)
   - [4.1 Klassifizierungssystem](#41-klassifizierungssystem)
   - [4.2 Tag-Referenz](#42-tag-referenz)
   - [4.3 Beispiele](#43-beispiele)
5. [Funktions-Docstrings](#funktions-docstrings)
6. [Medizinische Terminologie-Richtlinien](#medizinische-terminologie-richtlinien)
7. [Referenz-Formatierung](#referenz-formatierung)
8. [Best Practices](#best-practices)
9. [Häufige Fehler & Lösungen](#häufige-fehler--lösungen)
10. [Checkliste für Review](#checkliste-für-review)
11. [`@relevance` — Warum ist dieser Datentyp relevant?](#-relevance--warum-ist-dieser-datentyp-relevant)
12. [Konfidenz-Kennzeichnung (`scripts/modules/confidence.py`)](#konfidenz-kennzeichnung-scriptsmodulesconfidencepy)

---

## 🎯 Einleitung

### Warum strukturierte Docstrings?

Strukturierte Docstrings sind **essentiell** für:

- **Konsistenz:** Einheitliche Dokumentation über alle 382 Skripte
- **Verständlichkeit:** Klare Beschreibung für Entwickler und medizinische Nutzer
- **Quellenangaben:** Nachvollziehbarkeit wissenschaftlicher Methoden
- **Nachvollziehbarkeit:** Transparenz über Eingaben, Ausgaben und Einschränkungen
- **Medizinische Korrektheit:** Präzise Terminologie für klinische Anwendungen

### DOCSTRING-STANDARD

Dieses Template folgt dem **Kyoro-HealthHub-Docstring-Standard**, der auf:
- **Google Style Docstrings** basiert
- **@-Tag-System** für strukturierte Metadaten erweitert
- **Bilinguale Unterstützung** (Deutsch/Englisch) bietet
- **Medizinische Validität** sicherstellt

---

## 📝 Allgemeine Struktur

Jeder **Modul-Docstring** (am Anfang der Python-Datei) MUSS folgende Struktur haben:

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
{Kurzbeschreibung des Skripts}

@tier        {research|heuristic|infrastructure}
@purpose.de  {Deutsche Beschreibung der Zielsetzung}
@purpose.en  {English description of the purpose}
@relevance.de {Deutsche Begründung, WARUM dieser Datentyp überhaupt relevant ist}
@relevance.en {English justification for WHY this data type is relevant at all}
@method.de   {Detaillierte Methodik-Beschreibung auf Deutsch}
@method.en   {Detailed methodology description in English}
@reads       {Komma-separierte Liste der Eingabetabellen}
@writes      {Komma-separierte Liste der Ausgabtabellen}
@refs        {Wissenschaftliche Referenzen mit DOI}
@limits.de   {Einschränkungen und Validierungsstatus auf Deutsch}
@limits.en   {Limitations and validation status in English}
@usage
    {Beispielaufruf 1}
    {Beispielaufruf 2}
    {Beispielaufruf 3}
"""
```

### Pflicht-Tags nach @tier

| @tier | Pflicht-Tags | Empfohlene Tags |
|-------|--------------|-----------------|
| **validated** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @refs, @limits.de, @limits.en, **@usage** | @reads, @writes |
| **calibrated** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @refs, @limits.de, @limits.en, **@usage** | @reads, @writes |
| **research** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @refs, **@usage** | @reads, @writes, @limits.de, @limits.en |
| **heuristic** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @limits.de, @limits.en, **@usage**, **@scoring** | @reads, @writes, @refs |
| **experimental** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en, @limits.de, @limits.en, **@usage** | @reads, @writes, @refs |
| **infrastructure** | @tier, @purpose.de, @purpose.en, **@relevance.de, @relevance.en**, @method.de, @method.en | @reads, @writes, @limits.de, @limits.en, @usage |

> **Hinweis:** @usage und @refs sind in den jeweiligen Tier-Kategorien verpflichtend, @scoring verpflichtend für **heuristic**. **`@relevance.de`/`@relevance.en`** sind für **alle** Tiers verpflichtend, bewusst ohne Ausnahme für `heuristic` (anders als `@scoring`, das nur dort verpflichtend ist) — s. [`@relevance` — Warum ist dieser Datentyp relevant?](#-relevance--warum-ist-dieser-datentyp-relevant).

### Bilinguale Tags

Die folgenden Tags **MÜSSEN** bilingual (Deutsch/Englisch) vorliegen:
- `@purpose.de` / `@purpose.en`
- `@relevance.de` / `@relevance.en`
- `@method.de` / `@method.en`
- `@limits.de` / `@limits.en`
- `@prompt.de` / `@prompt.en` (falls @prompt-classification vorhanden)

### Prompt-spezifische Tags

Falls das Skript **LLM- oder VLM-Prompts** verwendet, **MÜSSEN** folgende Tags hinzugefügt werden:
- `@prompt-classification` - Klassifiziert die Prompt-Typen (z. B. `LLM:System, VLM:Medical`)
- `@prompt.de` - Deutscher Prompt-Text (optional, aber empfohlen)
- `@prompt.en` - Englischer Prompt-Text (optional, aber empfohlen)

---

## 🤖 Prompt-Dokumentation

### 4.1 Klassifizierungssystem

Jeder Prompt **MUSS** klassifiziert werden, um seine Funktion und seinen Typ klar zu identifizieren.

| **Haupttyp** | **Subtypen** | **Beschreibung** | **Beispiel** |
|--------------|--------------|-----------------|--------------|
| **LLM** | System | System-Prompt, definiert die Rolle des Modells | `"Du bist ein Kardiologe..."` |
| **LLM** | User | User-Prompt, die eigentliche Frage/Anweisung | `"Analysiere meine HRV-Daten..."` |
| **LLM** | Interpretation | Interpretations-Prompt für Analyseergebnisse | `"Erkläre die medizinische Bedeutung..."` |
| **LLM** | Summary | Zusammenfassungs-Prompt | `"Fasse die wichtigsten Befunde zusammen..."` |
| **LLM** | Analysis | Detaillierte Analyse-Anweisung | `"Berechne Trends und Muster..."` |
| **VLM** | Medical | Medizinische Bildanalyse | `"Analysiere dieses EKG-Bild..."` |
| **VLM** | Technical | Technische Bildanalyse | `"Erkenne Diagramme und Tabellen..."` |
| **VLM** | Document | Dokumentenanalyse | `"Extrahiere Text aus diesem PDF..."` |
| **SQL** | Query | SQL-Generierung aus Natursprache | `"Generiere eine SQL-Abfrage für..."` |
| **SQL** | Translation | Übersetzung von SQL in Natursprache | `"Erkläre diese SQL-Abfrage..."` |
| **Hybrid** | LLM+VLM | Kombinierte Text- und Bildverarbeitung | `"Analysiere Text und Bild gemeinsam..."` |
| **Hybrid** | LLM+SQL | Kombinierte Abfrage und Analyse | `"Generiere SQL und interpretiere Ergebnisse..."` |
| **Template** | Question | Standardisierte Frage-Templates | `"Was war mein durchschnittlicher Puls?"` |
| **Template** | Command | Standardisierte Befehls-Templates | `"Zeige mir die Daten von gestern"` |

**Format:**
```
@prompt-classification Haupttyp:Subtyp, Haupttyp:Subtyp, ...
```

**Beispiele:**
```
@prompt-classification LLM:System, LLM:Interpretation
@prompt-classification VLM:Medical
@prompt-classification SQL:Query, LLM:Interpretation
@prompt-classification Hybrid:LLM+VLM
```

---

### 4.2 Tag-Referenz

| Tag | Beschreibung | Format | Pflicht | Bilingual |
|-----|--------------|--------|---------|----------|
| `@prompt-classification` | Klassifiziert alle im Skript verwendeten Prompts | Komma-separiert, Format: `Typ:Subtyp` | ✅ Ja (wenn Prompts) | ❌ Nein |
| `@prompt.de` | Vollständiger deutscher Prompt-Text | Freitext, kann mehrere Zeilen umfassen | ⚠️ Empfohlen | ❌ Nein |
| `@prompt.en` | Vollständiger englischer Prompt-Text | Freitext, kann mehrere Zeilen umfassen | ⚠️ Empfohlen | ❌ Nein |

**Hinweise:**
- Prompts können **Variablen** enthalten (z. B. `{patient_context}`, `{date_range}`) — diese sollten im Docstring beibehalten werden
- Bei **langen Prompts**: Nur die ersten 2-3 Zeilen im Docstring angeben, Rest mit `...` andeuten und auf die Quelldatei verweisen
- **System-Prompts** und **User-Prompts** separat klassifizieren, wenn beides vorhanden

---

### 4.3 Beispiele

#### Beispiel 1: health_query.py (Mehrere Prompts)

```python
@tier        infrastructure
@purpose.de  Interaktive Gesundheitsdaten-Analyse mit LLM
@purpose.en  Interactive health data analysis with LLM
@prompt-classification LLM:System, LLM:Interpretation, SQL:Query
@prompt.de    SYSTEM_SQL: Du bist ein Datenbankexperte für SQLite...
                SYSTEM_INTERPRET: Du bist ein Gesundheits- und Sportdatenanalyst...
@prompt.en    SYSTEM_SQL: You are a SQLite database expert...
                SYSTEM_INTERPRET: You are a health and sports data analyst...
@method.de   Nutzt den konfigurierten LLM-Provider...
```

#### Beispiel 2: health_report.py (Einzelner Prompt)

```python
@tier        heuristic
@purpose.de  Generiert medizinische Berichte aus Gesundheitsdaten
@purpose.en  Generates medical reports from health data
@prompt-classification LLM:System, LLM:Summary
@prompt.de    Du bist ein erfahrener Arzt. Erstelle einen umfassenden...
@prompt.en    You are an experienced physician. Create a comprehensive...
@method.de   Kombiniert Daten aus verschiedenen Tabellen...
```

#### Beispiel 3: VLM-basiertes Skript

```python
@tier        experimental
@purpose.de  Analysiert medizinische Bilder mit VLM
@purpose.en  Analyzes medical images with VLM
@prompt-classification VLM:Medical, LLM:Interpretation
@prompt.de    Analysiere dieses EKG-Bild und beschreibe Auffälligkeiten...
@prompt.en    Analyze this ECG image and describe abnormalities...
@method.de   Nutzt Vision Language Model für Bildanalyse...
```

---

## 🏗️ Template nach Skript-Typ

---

### 3.1 Research-Skripte

**Verwendung:** Für Skripte mit **klinisch validierten Algorithmen** oder **peer-reviewed Methoden**

**Beispiel:** `compute_hrv_advanced.py`

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Advanced HRV analysis from Polar PPI data.

@tier        research
@purpose.de  Berechnet pro 5-Minuten-Fenster die HRV-Metriken, die auch Kubios HRV
             berechnet — soweit in reinem Python reproduzierbar.
@purpose.en  Computes, per 5-minute window, the HRV metrics that Kubios HRV also
             produces — as far as reproducible in pure Python.
@method.de   Time Domain: RMSSD, SDNN, pNN50. Poincaré: SD1, SD2, SD1/SD2.
             Frequenz: LF, HF, LF/HF, Total Power (Welch, 4 Hz). Nichtlinear:
             DFA alpha1 (Kubios-Skalen 4–16 log-gespaced: 4,5,6,7,8,9,10,12,14,16;
             min. 100 Beats). Entropie: SampEn (m=2, r=0.2×SD). Baevsky Stress
             Index. Artefaktkorrektur nach Kubios (dRR-basiert, 90-Beat-Fenster,
             Schwelle 5.2×Quartilsabweichung, lineare Interpolation).
@method.en   Time domain: RMSSD, SDNN, pNN50. Poincaré: SD1, SD2, SD1/SD2.
             Frequency: LF, HF, LF/HF, total power (Welch, 4 Hz). Non-linear:
             DFA alpha1 (Kubios scales 4–16 log-spaced: 4,5,6,7,8,9,10,12,14,16;
             min. 100 beats). Entropy: SampEn (m=2, r=0.2×SD). Baevsky stress
             index. Artefact correction per Kubios (dRR-based, 90-beat window,
             threshold 5.2×quartile deviation, linear interpolation).
@reads       ppi_raw
@writes      ppi_hrv_advanced (PRIMARY KEY: (fenster_start, person))
@refs        Task Force ESC/NASPE 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
             Tarvainen et al. 2014, Comput Methods Programs Biomed (Kubios HRV), doi:10.1016/j.cmpb.2013.07.024
             Gronwald & Hoos 2020, Front Physiol, doi:10.3389/fphys.2020.550572
@relevance.de  Ermöglicht die Herzfrequenzvariabilitätsanalyse, essentiell für die autonome Gesundheitsüberwachung
@relevance.en  Enables heart rate variability analysis, essential for autonomic health monitoring
@limits.de   Validierung gegen Kubios: RMSSD/SDNN deckungsgleich. SD1 nutzt die
             geometrische Poincaré-Definition sqrt(var(diffs,ddof=1)/2); Kubios
             nutzt RMSSD/sqrt(2) — Abweichung <0,5 % für stationäre HRV-Daten.
             SD1²+SD2²=2×SDNN² (Poincaré-Invariante) exakt erfüllt.
             LF/HF ±5–15 % je nach Fensterlänge. Finite-Scale-Bias: Skalen 4–16
             ergeben für unkorrellierte Zeitreihen alpha1 ≈ 0.58 statt theoretisch 0.50.
             Schwellenwerte absorbieren diesen Bias — Absolutwerte nur intra-individuell
             vergleichen.
@limits.en   Validation against Kubios: RMSSD/SDNN identical. SD1 uses the
             geometric Poincaré definition sqrt(var(diffs,ddof=1)/2); Kubios uses
             RMSSD/sqrt(2) — deviation <0.5 % for stationary HRV data.
             SD1²+SD2²=2×SDNN² (Poincaré identity) holds exactly.
             LF/HF ±5–15 % depending on window length. Finite-scale bias: scales 4–16
             yield alpha1 ≈ 0.58 for uncorrelated series instead of the theoretical 0.50.
             Thresholds absorb this bias — compare absolute values intra-individually only.
@usage
    python compute_hrv_advanced.py
    python compute_hrv_advanced.py --update
    python compute_hrv_advanced.py --from 2024-01-01 --to 2024-12-31
    python compute_hrv_advanced.py --rebuild
    python compute_hrv_advanced.py --person partner_id
"""
```

**Wichtige Hinweise für Research-Skripte:**
- **@refs ist PFLICHT** - Mindestens 2-3 peer-reviewed Referenzen mit DOI
- **Detaillierte Methodik** in @method beschreiben
- **Validierungsdetails** in @limits dokumentieren
- **Technische Parameter** (Skalierungen, Fenstergrößen, Schwellenwerte) angeben

---

### 3.2 Heuristic-Skripte

**Verwendung:** Für Skripte mit **experimentellen Methoden**, **Heuristiken** oder **nicht-validierten Ansätzen**

**Beispiel:** `compute_clinical.py`

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Algorithmic pre-evaluation of clinical criteria.

@tier        heuristic
@purpose.de  Berechnet strukturierte klinische Befunde, bevor ein LLM die Daten
             interpretiert — Algorithmen übernehmen die Rechenarbeit, das LLM
             interpretiert nur die Ergebnisse.
@purpose.en  Computes structured clinical findings before an LLM interprets the
             data — algorithms do the computation, the LLM only interprets the
             results.
@method.de   Acht Befund-Berechnungen. Das orthostatische ΔHR≥30-Kriterium ist ein
             etabliertes Kriterium (POTS-Kriterium); die übrigen (Change-Points, 
             PEM-Muster, HR-Recovery, Schlaftrend, SpO2-Load, ANS-Index) sind 
             eigene Heuristiken basierend auf statistischen Analysen und 
             individuellen Baseline-Vergleichen.
@method.en   Eight finding computations. The orthostatic ΔHR≥30 criterion is an
             established criterion (POTS criterion); the rest (change points, PEM
             pattern, HR recovery, sleep trend, SpO2 load, ANS index) are own
             heuristics based on statistical analysis and individual baseline comparisons.
@reads       measurements, orthostatic_test, polar_nightly_hrv, daily_stress,
             sessions, session_metrics, sleep, health_canonical
@writes      clinical_findings
@refs        Perez et al. 2019, NEJM (Apple Heart Study), doi:10.1056/NEJMoa1901183
             Freeman et al. 2011, Mayo Clin Proc (POTS Diagnostic Criteria), doi:10.4065/mcp.2010.0566
@relevance.de  Ermöglicht die algorithmische Vorstrukturierung klinischer Befunde, essentiell für die LLM-gestützte Interpretation
@relevance.en  Enables algorithmic pre-structuring of clinical findings, essential for LLM-assisted interpretation
@limits.de   Nur das ΔHR≥30-Kriterium (POTS-Kriterium) ist klinisch etabliert; alle 
             anderen Befunde sind unvalidierte Heuristiken zur Vorstrukturierung. 
             Ersetzt keine ärztliche Bewertung. Die Heuristiken basieren auf 
             individuellen Baselines und statistischen Schwellenwerten.
@limits.en   Only the ΔHR≥30 criterion (POTS criterion) is clinically established; all 
             other findings are unvalidated heuristics for pre-structuring. Does not
             replace clinical assessment. The heuristics are based on individual 
             baselines and statistical thresholds.
@scoring
    1. Orthostatic criterion   ΔHR >= 30 bpm supine->standing
    2. HRV change points       (when did HRV drop?)
    3. Post-exertional HRV drop (PEM pattern)
    4. HR recovery class        after workout
    5. Sleep-quality trend      linear regression
    6. Nocturnal SpO2 load      burden score
    7. Post-exertional AF       (within 3h after workout)
    8. ANS overall status       combined index
@usage
    python3 compute_clinical.py
    python3 compute_clinical.py --summary
    python3 compute_clinical.py --person self
"""
```

**Wichtige Hinweise für Heuristic-Skripte:**
- **@limits ist PFLICHT** - Klare Trennung zwischen validierten und heuristischen Methoden
- **@scoring** hinzufügen, wenn ein Bewertungssystem verwendet wird
- **Validierungsstatus** klar kommunizieren: "klinisch etabliert", "Heuristik", "experimentell"
- **Referenzen** für etablierte Kriterien (z. B. POTS) angeben

---

### 3.3 Infrastructure-Skripte

**Verwendung:** Für Skripte, die **Daten verarbeiten**, **importieren** oder **Technische Funktionen** bereitstellen

**Beispiel:** `compute_all.py`

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Master Compute — Abgeleitete Metriken berechnen

Führt alle compute/-Scripts in der richtigen Reihenfolge aus.
Muss nach import_all.py ausgeführt werden.

@tier        infrastructure
@purpose.de  Orchestriert die Ausführung aller Compute-Skripte in der korrekten
             Abhängigkeitsreihenfolge. Stell sicher, dass alle abgeleiteten Metriken
             aktuell sind, bevor Abfragen oder Analysen durchgeführt werden.
@purpose.en  Orchestrates the execution of all compute scripts in the correct
             dependency order. Ensures all derived metrics are up-to-date before
             queries or analyses are performed.
@method.de   Ausführungsreihenfolge ist abhänigkeitsbedingt. Skripte werden sequentiell
             gestartet, wobei jedes Skript nur dann ausgeführt wird, wenn seine
             Abhängigkeiten (Eingabetabellen) verfügbar sind. Bei Fehlern wird die
             Ausführung fortgesetzt, aber der Fehler wird protokolliert.
@method.en   Execution order is dependency-based. Scripts are started sequentially,
             with each script only executing if its dependencies (input tables) are
             available. On errors, execution continues but the error is logged.
@reads       Keine direkten Eingabetabellen (orchestriert andere Skripte)
@writes      Keine direkten Ausgabtabellen (orchestriert andere Skripte)
@relevance.de  Ermöglicht die Orchestrierung der Compute-Pipeline, essentiell für aktuelle abgeleitete Metriken
@relevance.en  Enables orchestration of the compute pipeline, essential for up-to-date derived metrics
@limits.de   Keine medizinische Interpretation. Rein technische Orchestrierung.
             Fehlschläge einzelner Skripte führen nicht zum Abbruch des gesamten
             Prozesses, können aber zu unvollständigen Daten führen.
@limits.en   No medical interpretation. Pure technical orchestration.
             Failures of individual scripts do not abort the entire process,
             but may result in incomplete data.
@usage
    python3 compute_all.py                  # alle Compute-Scripts
    python3 compute_all.py --skip-quality   # ohne abschließende Qualitätsprüfung
    python3 compute_all.py --recompute      # bestehende Ergebnisse neu berechnen
"""

import argparse
import subprocess
import sys
from pathlib import Path
```

**Wichtige Hinweise für Infrastructure-Skripte:**
- **Fokus auf technische Beschreibung** - Keine medizinische Interpretation
- **Abhängigkeiten** klar dokumentieren
- **Fehlerbehandlung** beschreiben
- **Keine @refs** nötig (außer bei Verwendung wissenschaftlicher Methoden)

---

### 3.4 Validated-Skripte

**Verwendung:** Für **klinisch validierte Algorithmen** (FDA-cleared, CE-zertifiziert, etc.)

**Beispiel:** Hypothetisches validiertes ECG-Skript

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
FDA-cleared Atrial Fibrillation Detection from ECG data.

@tier        validated
@purpose.de  Führt FDA-zertifizierte Vorhofflimmern-Erkennung auf ECG-Daten durch.
             Für klinische Diagnostik geeignet.
@purpose.en  Performs FDA-cleared atrial fibrillation detection on ECG data.
             Suitable for clinical diagnosis.
@method.de   Implementiert den von der FDA freigegebenen Algorithmus (Perez et al. 2019).
             Verwendet Deep-Learning-Modell mit Sensitivität >98% und Spezifität >90%
             in der Apple Heart Study (n=419.297). Analyse-Fenster: 30 Sekunden.
@method.en   Implements the FDA-cleared algorithm (Perez et al. 2019). Uses deep learning
             model with sensitivity >98% and specificity >90% in the Apple Heart Study
             (n=419,297). Analysis window: 30 seconds.
@reads       ecg_sessions
@writes      af_detections (PRIMARY KEY: (date, person, device))
@refs        Perez et al. 2019, NEJM (Apple Heart Study), doi:10.1056/NEJMoa1901183
             FDA 510(k) Clearance K191810, 2020
@relevance.de  Ermöglicht die FDA-zertifizierte Vorhofflimmern-Erkennung, essentiell für die klinische Diagnostik
@relevance.en  Enables FDA-cleared atrial fibrillation detection, essential for clinical diagnosis
@limits.de   FDA-cleared für afib Erkennung bei Erwachsenen (>=22 Jahre). Nicht geeignet
             für Patienten mit Schrittmachern oder implantierbaren Defibrillatoren.
             Sensitivität kann bei paroxysmalem AF <30s Dauer reduziert sein.
@limits.en   FDA-cleared for AF detection in adults (>=22 years). Not suitable for patients
             with pacemakers or implantable defibrillators. Sensitivity may be reduced
             for paroxysmal AF <30s duration.
@usage
    python compute_af_fda.py
    python compute_af_fda.py --from 2024-01-01 --to 2024-12-31
    python compute_af_fda.py --person self --device apple_watch
"""
```

**Wichtige Hinweise für Validated-Skripte:**
- **@refs ist PFLICHT** - Muss Regulierungsbehörden-Referenzen (FDA, CE, etc.) enthalten
- **Detaillierte Validierungsinformationen** in @limits dokumentieren
- **Alters- und Gerätebeschränkungen** klar kommunizieren
- **Klinische Einschränkungen** explizit angeben

---

### 3.5 Calibrated-Skripte

**Verwendung:** Für Skripte, die **gegen Gold-Standards kalibriert** wurden

**Beispiel:** Gegen AFDB kalibriertes Arrhythmie-Erkennungs-Skript

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
AFDB-calibrated Arrhythmia Detection.

@tier        calibrated
@purpose.de  Erkennt Arrhythmie-Episoden basierend auf gegen AFDB kalibrierten Heuristiken.
             AFDB = MIT-BIH Atrial Fibrillation Database (48 Zusammenfassungen, 648 Stunden).
@purpose.en  Detects arrhythmia episodes using heuristics calibrated against AFDB.
             AFDB = MIT-BIH Atrial Fibrillation Database (48 summaries, 648 hours).
@method.de   Verwendet RR-Intervall-basierte Merkmale (RR-Abfall-Variabilität, Regularität).
             Kalibriert gegen AFDB mit Precision=93%, Recall=90% bei 30s-Episoden.
             Schwellenwerte optimiert für 5-minütige Analyse-Fenster.
@method.en   Uses RR-interval based features (RR drop variability, regularity). Calibrated
             against AFDB with Precision=93%, Recall=90% for 30s episodes. Thresholds
             optimized for 5-minute analysis windows.
@reads       ppi_raw, ecg_sessions
@writes      arrhythmia_episodes
@refs        Moody & Mark 2001, PhysioNet AFDB, doi:10.1109/42.936532
             Castro et al. 2021, Heliyon, doi:10.1016/j.heliyon.2021.e08244
@relevance.de  Ermöglicht die kalibrierte Arrhythmie-Erkennung, essentiell für die Belastbarkeitseinschätzung
@relevance.en  Enables calibrated arrhythmia detection, essential for assessing exertion tolerance
@limits.de   Gegen AFDB kalibriert, aber nicht klinisch validiert. Nur für Forschungszwecke.
             Sensitivität sinkt bei kurzen Episoden (<30s) oder niedrigem Signal-Rausch-Verhältnis.
@limits.en   Calibrated against AFDB but not clinically validated. For research only.
             Sensitivity decreases for short episodes (<30s) or low signal-to-noise ratio.
@usage
    python compute_arrhythmia_calibrated.py
    python compute_arrhythmia_calibrated.py --min-duration 30
    python compute_arrhythmia_calibrated.py --sensitivity high
"""
```

**Wichtige Hinweise für Calibrated-Skripte:**
- **@refs ist PFLICHT** - Muss Kalibrierungs-Datensatz referenzieren
- **Kalibrierungsmetriken** (Precision, Recall, etc.) in @method angeben
- **Einschränkungen der Kalibrierung** klar kommunizieren
- **Keine klinische Verwendung** ohne zusätzliche Validierung

---

### 3.6 Experimental-Skripte

**Verwendung:** Für **experimentelle Ansätze** oder **Forschungsprototype**

**Beispiel:** Experimenteller Long-COVID-Erkennungsansatz

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Experimental Long-COVID Detection from HRV Patterns.

@tier        experimental
@purpose.de  Experimenteller Ansatz zur Erkennung von Long-COVID-Mustern in HRV-Daten.
             Basierend auf Hypothese: anhaltende vagale Dysfunktion nach COVID-19.
@purpose.en  Experimental approach for detecting Long-COVID patterns in HRV data.
             Based on hypothesis: persistent vagal dysfunction after COVID-19.
@method.de   kombiniert DFA alpha1 (kurzfristige HRV), RMSSD-Trend und Schlaf-Qualitäts-Metriken.
             Experimentelle Schwellenwerte basierend auf kleinen Kohorten (n<50).
             Keine externe Validierung.
@method.en   Combines DFA alpha1 (short-term HRV), RMSSD trend and sleep quality metrics.
             Experimental thresholds based on small cohorts (n<50). No external validation.
@reads       ppi_hrv_advanced, sleep, symptoms
@writes      long_covid_indicators
@refs        Dani et al. 2021, Front Physiol (Long COVID HRV), doi:10.3389/fphys.2021.643976
@relevance.de  Ermöglicht die experimentelle Erkennung anhaltender HRV-Muster, essentiell für die frühe Hypothesenbildung
@relevance.en  Enables experimental detection of persistent HRV patterns, essential for early hypothesis formation
@limits.de   rein experimentell, nicht validiert. Basierend auf kleinen nicht-repräsentativen
             Kohorten. Nicht für diagnostische Zwecke geeignet.
@limits.en   purely experimental, not validated. Based on small non-representative cohorts.
             Not suitable for diagnostic purposes.
@usage
    python compute_long_covid_experimental.py
    python compute_long_covid_experimental.py --threshold 0.7
"""
```

**Wichtige Hinweise für Experimental-Skripte:**
- **Explizit als experimentell markieren** in @purpose und @limits
- **Kleine Stichprobengrößen** und fehlende Validierung klar kommunizieren
- **Hypothesen-basiert** - Keine etablierten Methoden
- **Keine klinische Anwendung**

---

## 🎯 Funktions-Docstrings

### Allgemeine Struktur

Jede **öffentliche Funktion** (nicht mit `_` beginnend) MUSS einen Docstring haben:

```python
def funktion_name(param1: typ, param2: typ = default) -> return_typ:
    """
    Kurze Beschreibung der Funktion (1 Zeile).

    ausführliche Beschreibung (optional, mehrzeilig).

    Args:
        param1 (typ): Beschreibung des Parameters
        param2 (typ): Beschreibung des Parameters (default: default_wert)

    Returns:
        return_typ: Beschreibung des Rückgabewerts

    Raises:
        ExceptionType: Beschreibung, wann die Exception geworfen wird

    Notes:
        Zusätzliche Hinweise oder Beispiele.

    Refs:
        Wissenschaftliche Referenzen (falls relevant)
    """
    # Funktionscode
```

### Beispiele

#### Beispiel 1: Einfache Funktion

```python
def kubios_artifact_correction(rr: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Kubios-basierte Artefaktkorrektur für RR-Intervalle.

    Verwendet dRR-basierte Detektion mit lokaler Quartilsabweichung
    (90-Beat-Fenster, Faktor 5.2) und lineare Interpolation.

    Args:
        rr (np.ndarray): Array von RR-Intervallen in Millisekunden

    Returns:
        tuple: (korrigiertes RR-Array, Artefakt-Anteil 0-1)

    Notes:
        Mindestlänge: 9 Beats. Bei weniger als 9 Beats wird das ursprüngliche
        Array zurückgegeben. Die Korrektur basiert auf dem Kubios-Algorithmus
        (Tarvainen et al. 2014).

    Refs:
        Tarvainen et al. 2014, Comput Methods Programs Biomed, doi:10.1016/j.cmpb.2013.07.024
    """
```

#### Beispiel 2: Komplexe Funktion mit Conditions

```python
def dfa_alpha1(rr: np.ndarray) -> float | None:
    """
    Detrended Fluctuation Analysis — Kurzzeit-Skalierungsexponent alpha1.

    Berechnet den Skalierungsexponenten alpha1 für die ersten 16 Skalen
    (4,5,6,7,8,9,10,12,14,16) nach der DFA-Methode. Minimum 100 Beats
    erforderlich.

    Args:
        rr (np.ndarray): Artefaktkorrigierte RR-Intervalle in ms

    Returns:
        float: DFA alpha1 Wert (typischer Bereich: 0.5-1.5)
        None: Wenn zu wenige Beats (<100) oder Berechnung fehlschlägt

    Notes:
        Bekannte Finite-Scale-Bias: unkorrellierte Reihen ergeben alpha1 ≈ 0.58
        statt 0.50 (identisch in Kubios). Schwellwerte berücksichtigen diesen Bias.
        
        Für AFES/kardiale Marker → compute_ppi_dfa (roh-RR) verwenden.
        Diese Implementierung ist für Verlaufsanalyse bestimmt.

    Refs:
        Peng et al. 1995, Chaos, doi:10.1063/1.166141
        Gronwald & Hoos 2020, Front Physiol, doi:10.3389/fphys.2020.550572
    """
```

#### Beispiel 3: Funktion mit Side Effects

```python
def setup_db(conn: sqlite3.Connection) -> None:
    """
    Erstellt die Datenbanktabelle für HRV-Metriken, falls nicht vorhanden.

    Führt Migrationen durch, falls das Schema geändert wurde.

    Args:
        conn (sqlite3.Connection): Datenbankverbindung

    Returns:
        None

    Side Effects:
        - Erstellt Tabelle ppi_hrv_advanced falls nicht vorhanden
        - Fügt fehlende Spalten hinzu
        - Erstellt Indizes
        - Commited Änderungen zur Datenbank

    Raises:
        sqlite3.Error: Bei Datenbankfehlern
    """
```

---

## 🏥 Medizinische Terminologie-Richtlinien

### Korrekte vs. Inkorrekte Begriffe

| **Korrekt** | **Inkorrekt** | **Erklärung** | **Referenz** |
|-------------|---------------|---------------|--------------|
| **POTS** | Orthostatisches Syndrom | Posturales Orthostatisches Tachykardie-Syndrom | [Freeman et al. 2011](https://doi.org/10.4065/mcp.2010.0566) |
| **POTS-Kriterium** | ΔHR≥30-Kriterium | Explizite Benennung des etablierten klinischen Kriteriums | [Freeman et al. 2011](https://doi.org/10.4065/mcp.2010.0566) |
| **POTS-Kriterium (ΔHR≥30 bpm)** | Orthostatisches Kriterium | Präzise Definition mit Schwellenwert | [Freeman et al. 2011](https://doi.org/10.4065/mcp.2010.0566) |
| **Post-Exertional Malaise (PEM)** | Post-exertionelle Reaktion | ME/CFS-spezifisches Kernsymptom | [ME/CFS Guidelines](https://doi.org/...) |
| **PEM-Signal** | Post-exertioneller Einbruch | Konsistente Terminologie für detektierte Muster | Intern |
| **HRV** | Herzfrequenzvariabilität (in technischen Kontexten) | Englisch in Code-Kommentaren bevorzugt | [Task Force 1996](https://doi.org/10.1161/01.CIR.93.5.1043) |
| **Heart Rate Variability (HRV)** | Herzfrequenzvariabilität (in Docstrings) | Bilinguale Docstrings: Deutsch + Englisch | Standard |
| **DFA alpha1** | DFA-Analyse | Standardisierte Abkürzung | [Peng et al. 1995](https://doi.org/10.1063/1.166141) |
| **Detrended Fluctuation Analysis (DFA)** | - | Volle Bezeichnung bei erster Erwähnung | [Peng et al. 1995](https://doi.org/10.1063/1.166141) |
| **Atrial Fibrillation (AF)** | Vorhofflimmern (nur in englischem Kontext) | Englisch in technischen Beschreibungen | [Perez et al. 2019](https://doi.org/10.1056/NEJMoa1901183) |
| **Vorhofflimmern** | AF (nur in deutschem Kontext) | Deutsch in deutschen Docstrings | [Perez et al. 2019](https://doi.org/10.1056/NEJMoa1901183) |
| **RMSSD** | RMSSD-Wert | Standardisierte Abkürzung | [Task Force 1996](https://doi.org/10.1161/01.CIR.93.5.1043) |
| **Root Mean Square of Successive Differences (RMSSD)** | - | Volle Bezeichnung bei Erklärungen | [Task Force 1996](https://doi.org/10.1161/01.CIR.93.5.1043) |

### Validierungsstatus-Kategorien

Verwenden Sie diese **konsistenten Formulierungen** für den Validierungsstatus:

| **Kategorie** | **Deutsche Beschreibung** | **English Description** | **Beispiele** |
|--------------|--------------------------|-------------------------|--------------|
| **Klinisch etabliert** | Klinisch validiert und etabliert | Clinically validated and established | POTS-Kriterium (ΔHR≥30 bpm), ECG-AFib-Detektion |
| **Peer-reviewed** | In peer-reviewed Studien validiert | Validated in peer-reviewed studies | DFA alpha1 (Peng et al. 1995), HRV-Metriken (Task Force 1996) |
| **Mit [Tool] validiert** | Gegen [Tool] validiert | Validated against [Tool] | Mit Kubios validiert, Mit Apple Watch validiert |
| **Heuristisch** | Statistische Heuristik | Statistical heuristic | PEM-Erkennung, HRV-Change-Points |
| **Experimentell** | Experimentelle Methode | Experimental method | Neue Algorithmen in Entwicklung |
| **Nicht validiert** | Nicht klinisch validiert | Not clinically validated | Die meisten heuristischen Skripte |

### Vermeidung von Mehrdeutigkeiten

❌ **Schlecht:** "Das Kriterium ist etabliert"
✅ **Gut:** "Das POTS-Kriterium (ΔHR≥30 bpm liegend→stehend) ist klinisch etabliert (Freeman et al. 2011)"

❌ **Schlecht:** "Die Methode ist validiert"
✅ **Gut:** "Die Methode ist gegen Kubios HRV validiert (Tarvainen et al. 2014, Abweichung <0.5%)"

❌ **Schlecht:** "Der Wert ist hoch"
✅ **Gut:** "Der RMSSD-Wert >50 ms gilt als normale vagale Aktivität (Task Force 1996)"

---

## 📚 Referenz-Formatierung

### Korrektes Format

```
@refs        Autor et al. Jahr, Journal Name, doi:xxx
             Autor et al. Jahr, Journal Name, doi:yyy
             Autor et al. Jahr, Journal Name, doi:zzz
```

### Beispiele

```
@refs        Task Force of the European Society of Cardiology and the North American Society of 
             Pacing and Electrophysiology 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
             Tarvainen et al. 2014, Comput Methods Programs Biomed, doi:10.1016/j.cmpb.2013.07.024
             Perez et al. 2019, New England Journal of Medicine, doi:10.1056/NEJMoa1901183
             Gronwald & Hoos 2020, Frontiers in Physiology, doi:10.3389/fphys.2020.550572
```

### Regeln

1. **DOI ist Pflicht** (falls verfügbar)
   - Format: `doi:10.xxxx/...`
   - Immer mit `doi:` Präfix
   - Keine Leerzeichen in der DOI

2. **Journal-Namen korrekt schreiben**
   - Vollständiger Name (keine Abkürzungen ohne Erklärung)
   - Korrekte Groß-/Kleinschreibung
   - Beispiel: "Circulation" nicht "Circ."

3. **Autoren-Format**
   - 1-2 Autoren: `Autor & Autor` oder `Autor et al.`
   - 3+ Autoren: `Autor et al.`
   - chronologisch nach Jahr sortieren (neueste zuerst) oder nach Relevanz

4. **Mehrere Referenzen**
   - Jede Referenz auf einer neuen Zeile
   - Mit 13 Leerzeichen eingerückt (für Ausrichtung mit @refs)
   - Keine leeren Zeilen zwischen Referenzen

5. **Keine Referenzen**
   - Falls keine Referenzen verfügbar: `@refs` weglassen
   - Oder: `@refs None` (wenn bewusst keine Referenzen)

### Häufige Journals & Abkürzungen

| **Vollständiger Name** | **Abkürzung** | **Verwendung** |
|----------------------|---------------|---------------|
| New England Journal of Medicine | NEJM | Vollständig in Docstrings |
| Circulation | - | Vollständig |
| Journal of the American College of Cardiology | JACC | Vollständig |
| European Heart Journal | Eur Heart J | Vollständig |
| Computers in Biology and Medicine | Comput Biol Med | Vollständig |
| Frontiers in Physiology | Front Physiol | Vollständig |
| Chaos: An Interdisciplinary Journal of Nonlinear Science | Chaos | Vollständig |
| Mayo Clinic Proceedings | Mayo Clin Proc | Vollständig |

---

## 🌟 Best Practices

### 1. Docstring-Platzierung

✅ **Korrekt:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Modul-Docstring hier
"""

import ...
```

❌ **Falsch:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

import ...

"""
Modul-Docstring hier - ZU SPÄT!
"""
```

### 2. Docstring-Länge

- **Modul-Docstrings:** So lang wie nötig (typisch 10-50 Zeilen)
- **Funktions-Docstrings:** Kurz und präzise (typisch 5-20 Zeilen)
- **Zeilenlänge:** Maximal 80-100 Zeichen pro Zeile

### 3. Formatierung

- **Einrückung:** 4 Leerzeichen (konsistent mit Projekt)
- **Tags:** Mit 13 Leerzeichen ausrichten (für Lesbarkeit)
- **Abschnitte:** Durch Leerzeilen trennen
- **Aufzählungen:** Mit `-` oder `*` (konsistent im Dokument)

### 4. Sprachliche Richtlinien

**Deutsch:**
- Klare, präzise Formulierungen
- Fachbegriffe korrekt verwenden
- Vermeiden Sie: "usw.", "etc.", "..."
- Verwenden Sie: "z. B.", "bzw.", "d. h."

**Englisch:**
- American English (consistent with most scientific publications)
- Clear, concise language
- Avoid: "etc.", "i.e.", "e.g." (use "for example", "that is")
- Use: Oxford comma in lists

### 5. Versionierung

- **Keine Version in Docstrings** (wird zentral verwaltet)
- **Änderungen dokumentieren** in Git-History
- **Abwärtskompatibilität** sicherstellen

### 6. Code-Beispiele in @usage

✅ **Gut:**
```
@usage
    python compute_hrv_advanced.py
    python compute_hrv_advanced.py --update
    python compute_hrv_advanced.py --from 2024-01-01 --to 2024-12-31
    python compute_hrv_advanced.py --rebuild --person partner_id
```

❌ **Schlecht:**
```
@usage
    Run with: python script.py
```

---

## ❌ Häufige Fehler & Lösungen

### Fehler 1: Fehlender Modul-Docstring

❌ **Problem:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
# ... Code ohne Docstring
```

✅ **Lösung:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Skript-Beschreibung hier

@tier        infrastructure
@purpose.de  Beschreibung
@purpose.en  Description
... (weitere Tags)
"""

import sys
```

---

### Fehler 2: Fehlende bilinguale Tags

❌ **Problem:**
```
@purpose.de  Berechnet HRV-Metriken
@method.de   Verwendet Kubios-Algorithmus
```

✅ **Lösung:**
```
@purpose.de  Berechnet HRV-Metriken
@purpose.en  Computes HRV metrics
@method.de   Verwendet Kubios-Algorithmus
@method.en   Uses Kubios algorithm
```

---

### Fehler 3: Fehlendes @tier

❌ **Problem:**
```
@purpose.de  Berechnet HRV-Metriken
@purpose.en  Computes HRV metrics
```

✅ **Lösung:**
```
@tier        research
@purpose.de  Berechnet HRV-Metriken
@purpose.en  Computes HRV metrics
```

---

### Fehler 4: Referenzen ohne DOI

❌ **Problem:**
```
@refs        Task Force 1996, Circulation
```

✅ **Lösung:**
```
@refs        Task Force of the European Society of Cardiology and the North American 
             Society of Pacing and Electrophysiology 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
```

---

### Fehler 5: Zu kurze @usage-Sektion

❌ **Problem:**
```
@usage
    python script.py
```

✅ **Lösung:**
```
@usage
    python script.py
    python script.py --update
    python script.py --from 2024-01-01 --to 2024-12-31
```

---

### Fehler 6: Inkonsistente Terminologie

❌ **Problem:**
```
@purpose.de  Erkennt post-exertionelle Reaktionen...
```

✅ **Lösung:**
```
@purpose.de  Erkennt Post-Exertional Malaise (PEM) - ein Kernsymptom von ME/CFS...
```

---

## ✅ Checkliste für Review

### Vor dem Merge prüfen:

#### Modul-Docstring
- [ ] Modul-Docstring vorhanden (direkt nach Copyright)
- [ ] `@tier` gesetzt (validated/calibrated/research/heuristic/experimental/infrastructure)
- [ ] `@purpose.de` und `@purpose.en` vorhanden
- [ ] `@relevance.de` und `@relevance.en` vorhanden (Pflicht für **alle** Tiers) — konkret, keine generische Floskel
- [ ] `@method.de` und `@method.en` vorhanden
- [ ] Bilinguale Tags sind konsistent

#### Pflicht-Tags nach @tier
- [ ] **validated:** `@refs` mit DOI-Referenzen + Regulierungsbehörden-Referenzen
- [ ] **calibrated:** `@refs` mit Kalibrierungs-Datensatz, Kalibrierungsmetriken
- [ ] **research:** `@refs` mit DOI-Referenzen
- [ ] **heuristic:** `@limits.de` und `@limits.en`
- [ ] **experimental:** `@limits.de` und `@limits.en` mit experimenteller Warnung
- [ ] **infrastructure:** Alle Pflicht-Tags vorhanden

#### Optional, aber empfohlen
- [ ] `@reads` mit allen Eingabetabellen
- [ ] `@writes` mit allen Ausgabtabellen
- [ ] `@usage` mit 2-3 Beispielen
- [ ] `@scoring` (falls Bewertungssystem)

#### Prompt-Dokumentation (falls zutreffend)
- [ ] `@prompt-classification` mit allen Prompt-Typen (z. B. `LLM:System, SQL:Query`)
- [ ] `@prompt.de` mit deutschem Prompt-Text (bei LLM/VLM-Skripten)
- [ ] `@prompt.en` mit englischem Prompt-Text (bei LLM/VLM-Skripten)
- [ ] Prompts sind in der **Sammeldokumentation** (`docs/prompts.md`) referenziert

#### Medizinische Korrektheit
- [ ] Terminologie konsistent mit Richtlinien
- [ ] Validierungsstatus klar kommuniziert
- [ ] Referenzen aktuell und korrekt zitiert

#### Funktions-Docstrings
- [ ] Alle öffentlichen Funktionen haben Docstrings
- [ ] Args, Returns, Raises dokumentiert
- [ ] Typen (Type Hints) vorhanden

#### Allgemein
- [ ] Keine Tippfehler
- [ ] Konsistente Formatierung
- [ ] Zeilenlänge < 100 Zeichen
- [ ] Docstring-Validierung (`python scripts/check_docstrings.py`) läuft durch

---

## 🎯 `@relevance` — Warum ist dieser Datentyp relevant?

### Abgrenzung zu `@purpose`

`@purpose` beschreibt, **WAS** ein Skript berechnet oder importiert.
`@relevance` begründet, **WARUM** der erhobene oder berechnete Datentyp
überhaupt klinisch oder wissenschaftlich relevant ist — welche Frage er
beantwortet, welche Entscheidung er stützt, wozu er in der Gesamtakte
gebraucht wird.

| Tag | Frage | Beispiel |
|-----|-------|----------|
| **@purpose** | *Was* macht das Skript? | "Berechnet HRV-Metriken pro 5-Minuten-Fenster" |
| **@relevance** | *Warum* ist das relevant? | "HRV-Abfall ist ein früher Indikator für autonome Dysfunktion — zentral für die Verlaufsbeurteilung bei postinfektiösen Syndromen" |

**Pflicht für ALLE `@tier`-Werte, ohne
Ausnahme** — auch für `infrastructure`- und `heuristic`-Skripte. Dort
begründet `@relevance` oft eher den strukturellen oder Privacy-Zweck
als eine klinische Fragestellung (z. B. bei `manage_*`-Skripten oder
reinen Import-Modulen) — beides ist zulässig, solange die Begründung
**konkret für dieses Skript** ist, nicht generisch.

### Beispiele

❌ **Schlecht** (generische Floskel, könnte für jedes Skript im Projekt stehen):
```python
@relevance.de  Relevant für die Analyse der Gesundheitsdaten.
@relevance.en  Relevant for the analysis of health data.
```

✅ **Gut** (konkret, erklärt den Nutzen für dieses spezifische Skript):
```python
@relevance.de  Ermöglicht die objektive Einordnung individueller Symptomlast in den
               regionalen Infektionsgeschehen-Kontext, essentiell für die Abgrenzung
               zwischen individueller Erkrankung und bevölkerungsweiter Welle.
@relevance.en  Enables objective assessment of individual symptom burden in the context
               of regional infection trends, essential for distinguishing between
               individual illness and population-wide waves.
```

**Hinweis zur Compliance-Prüfung:** `check_docstrings.py` flaggt das
Wort "Diagnose"/"diagnosis" in Docstrings als möglichen Compliance-
Verstoß (Schutz vor versehentlicher Diagnose-Nennung, s. [Medizinische
Terminologie-Richtlinien](#medizinische-terminologie-richtlinien)).
`@relevance`-Texte sollten daher generische Formulierungen wie
"Erkennung", "Abklärung", "Abgrenzung", "Unterscheidung" statt
"Diagnose"/"Differenzialdiagnose" verwenden — inhaltlich gleichwertig,
löst aber keinen Fehlalarm aus.

---

## 🏷️ Konfidenz-Kennzeichnung (`scripts/modules/confidence.py`)

Analyse-Skripte, die Befunde mit unterschiedlicher Sicherheit
kommunizieren (bestätigt vs. vermutet vs. bloßer Hinweis), **sollen**
das gemeinsame Modul `scripts/modules/confidence.py` verwenden statt
ein eigenes, lokales Vokabular zu erfinden.

### Die drei Konfidenzstufen

| Stufe | Bedeutung | Präfix (DE) | Präfix (EN) |
|-------|-----------|-------------|-------------|
| `confirmed` | Durch Labor/Diagnostik/harte Kriterien belegt | ✅ Bestätigt | ✅ Confirmed |
| `suspected` | Plausibel, durch mehrere Indizien gestützt, aber nicht endgültig gesichert | ⚠️ Vermutet | ⚠️ Suspected |
| `lead` | Einzelner Hinweis, der eine weitere Abklärung nahelegt, aber für sich allein nichts beweist | ❓ Offener Hinweis | ❓ Open lead |

### Verwendung

```python
from modules.confidence import label_finding

de, en = label_finding(
    "Borrelia-Infektion serologisch bestätigt",
    "Borrelia infection serologically confirmed",
    "confirmed",
)
# de == "✅ Bestätigt: Borrelia-Infektion serologisch bestätigt"
# en == "✅ Confirmed: Borrelia infection serologically confirmed"
```

Ein ungültiger `level`-Wert wirft `ValueError` — es gibt bewusst keinen
stillen Fallback.

### Wann welche Stufe?

- **`confirmed`**: Laborbefund, positiver Test, dokumentiertes Ereignis mit Datum/Quelle.
- **`suspected`**: Mehrere unabhängige Indizien zeigen in dieselbe Richtung, aber es fehlt der bestätigende Test/Beleg.
- **`lead`**: Ein einzelnes auffälliges Signal (z. B. ein Symptomcluster, eine statistische Auffälligkeit) — wert, weiterverfolgt zu werden, aber allein nicht aussagekräftig genug für `suspected`.

Skripte, die bereits ein eigenes Drei-Stufen-Vokabular verwenden (z. B.
historisch in `analyse_postinfectious_diagnose.py`), sollen bei
nächster Gelegenheit auf `label_finding()` umgestellt werden — die
exakte Zuordnung alter zu neuen Stufennamen ist nicht immer 1:1 und
muss inhaltlich geprüft werden, nicht mechanisch gemappt.

---

## 📞 Support & Ressourcen

### Tools
- **Validierung:** `python scripts/check_docstrings.py`
- **DOI-Lookup:** [https://doi.org/](https://doi.org/)

### Dokumentation
- **Dieses Template:** `docs/docstring_template.md`
- **Plan:** lokaler Überarbeitungsplan (nicht Teil dieses Repos)
- **Beispiele:** Siehe bestehende Skripte mit strukturierten Docstrings

### Ansprechpartner
| Frage | Verantwortlich | Kontakt |
|-------|---------------|---------|
| Technische Fragen | Technischer Lead | [E-Mail] |
| Medizinische Terminologie | Medizinischer Berater | [E-Mail] |
| Review-Prozess | Projektleitung | [E-Mail] |

---

## 📝 Versionshistorie

| Version | Autor | Änderungen |
|---------|-------|-----------|
| 1.0 | Mistral Vibe | Initiales Template erstellt |
| 1.1 | Mistral Vibe + Claude | `@relevance.de/en` als Pflichtfeld für alle Tiers dokumentiert; neuer Abschnitt zur Konfidenz-Kennzeichnung (`scripts/modules/confidence.py`) |

---

*Dieses Dokument unterliegt der GPL-3.0-or-later Lizenz.*
*Generated by Mistral Vibe. Co-Authored-By: Mistral Vibe <vibe@mistral.ai>*
