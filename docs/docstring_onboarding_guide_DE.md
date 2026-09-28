# Docstring Onboarding Guide — Kyoro-HealthHub

**Version:** 1.0  
**Zielgruppe:** Neue Contributors & Entwickler  

---

## 🎯 Warum Docstrings im Kyoro-HealthHub?

Gute Docstrings sind essenziell für:
- **Wartbarkeit:** Schnellere Fehlersuche und Verständnis des Codes
- **Medizinische Validität:** Klare Trennung zwischen validierten und heuristischen Methoden
- **Compliance:** Einhaltung von Datenschutzstandards (keine Diagnosen, Geschlecht, Alter, Orte)
- **Community:** Einfacheres Onboarding neuer Contributors
- **Forschung:** Nachvollziehbare Methoden für wissenschaftliche Nutzung

---

## 📋 Pflicht-Tags nach Skript-Typ

### 🏗️ Infrastructure (`@tier infrastructure`)
```python
@tier        infrastructure
@purpose.de  [Deutsche Zielbeschreibung]
@purpose.en  [English purpose description]
@method.de   [Deutsche Methodik]
@method.en   [English methodology]
@reads       [Eingabetabellen, kommagetrennt]
@writes      [Ausgabtabellen, kommagetrennt]
@relevance.de [Deutsche Begründung, WARUM dieser Datentyp überhaupt relevant ist]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Einschränkungen auf Deutsch]
@limits.en   [Limitations in English]
```

**Beispiel:** Import-Skripte, Hilfsfunktionen, Datenbank-Utilities

---

### 🔬 Research (`@tier research`)
```python
@tier        research
@purpose.de  [Deutsche Zielbeschreibung]
@purpose.en  [English purpose description]
@method.de   [Detaillierte Methodik auf Deutsch]
@method.en   [Detailed methodology in English]
@refs        Autor et al. Jahr, Journal, doi:xxx
             Autor et al. Jahr, Journal, doi:yyy
@relevance.de [Deutsche Begründung, WARUM dieser Datentyp überhaupt relevant ist]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Validierungsstatus auf Deutsch]
@limits.en   [Validation status in English]
```

**Beispiel:** `compute_hrv_advanced.py`, `compute_ppi_dfa.py`

---

### ⚖️ Calibrated (`@tier calibrated`)
```python
@tier        calibrated
@purpose.de  [Deutsche Zielbeschreibung]
@purpose.en  [English purpose description]
@method.de   [Methodik mit Kalibrierungsdetails]
@method.en   [Methodology with calibration details]
@refs        Autor et al. Jahr, Journal, doi:xxx
@relevance.de [Deutsche Begründung, WARUM dieser Datentyp überhaupt relevant ist]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Kalibrierungsstatus auf Deutsch]
@limits.en   [Calibration status in English]
```

**Beispiel:** `analyse_workout_performance.py`, `analyse_overview.py`

---

### 💡 Heuristic (`@tier heuristic`)
```python
@tier        heuristic
@purpose.de  [Deutsche Zielbeschreibung]
@purpose.en  [English purpose description]
@method.de   [Methodik-Beschreibung]
@method.en   [Methodology description]
@reads       [Eingabetabellen]
@writes      [Ausgabtabellen]
@relevance.de [Deutsche Begründung, WARUM dieser Datentyp überhaupt relevant ist]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Einschränkungen: "Heuristische Methode, nicht klinisch validiert"]
@limits.en   [Limitations: "Heuristic method, not clinically validated"]
@usage
    python script.py --from 2024-01-01 --to 2024-12-31
    python script.py --plot --no-llm
```

**Beispiel:** `compute_pem.py`, `analyse_afib_burden.py`

---

### 🧪 Experimental (`@tier experimental`)
```python
@tier        experimental
@purpose.de  [Deutsche Zielbeschreibung]
@purpose.en  [English purpose description]
@method.de   [Methodik-Beschreibung]
@method.en   [Methodology description]
@relevance.de [Deutsche Begründung, WARUM dieser Datentyp überhaupt relevant ist]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Einschränkungen: "Experimenteller Ansatz, in Entwicklung"]
@limits.en   [Limitations: "Experimental approach, under development"]
```

---

### ✅ Validated (`@tier validated`)
```python
@tier        validated
@purpose.de  [Deutsche Zielbeschreibung]
@purpose.en  [English purpose description]
@method.de   [Methodik mit Validierungsdetails]
@method.en   [Methodology with validation details]
@refs        Autor et al. Jahr, Journal, doi:xxx
@relevance.de [Deutsche Begründung, WARUM dieser Datentyp überhaupt relevant ist]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Validierungsstatus auf Deutsch]
@limits.en   [Validation status in English]
```

**Hinweis:** Nur für klinisch validierte Algorithmen (z.B. FDA-cleared, peer-reviewed)

---

## 📝 Docstring-Struktur Vorlage

### Modul-Docstring (am Anfang jeder Python-Datei)

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Skriptname — Kurze Beschreibung

@tier        [infrastructure|research|calibrated|heuristic|experimental|validated]
@purpose.de  [Deutsche Beschreibung der Zielsetzung]
@purpose.en  [English description of the purpose]
@method.de   [Detaillierte Methodik-Beschreibung auf Deutsch]
@method.en   [Detailed methodology description in English]
@reads       [Komma-separierte Liste der Eingabetabellen]
@writes      [Komma-separierte Liste der Ausgabtabellen]
@refs        Autor et al. Jahr, Journal, doi:xxx
             Autor et al. Jahr, Journal, doi:yyy
@relevance.de [Deutsche Begründung, WARUM dieser Datentyp überhaupt relevant ist]
@relevance.en [English justification for WHY this data type is relevant at all]
@limits.de   [Einschränkungen und Validierungsstatus auf Deutsch]
@limits.en   [Limitations and validation status in English]
@usage
    python script.py --from 2024-01-01
    python script.py --plot
    python script.py --help
"""

[Code beginnt hier...]
```

### Funktions-Docstring (Google Style)

```python
def berechne_hrv_metriken(rr_intervalle: np.ndarray) -> dict:
    """
    Berechnet HRV-Metriken aus RR-Intervallen.

    Verwendet DFA alpha1, RMSSD und andere Standardmetriken.

    Args:
        rr_intervalle (np.ndarray): Array von RR-Intervallen in Millisekunden

    Returns:
        dict: Dictionary mit HRV-Metriken (rmssd, dfa_alpha1, etc.)

    Refs:
        Task Force ESC/NASPE 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
        Gronwald & Hoos 2020, Front Physiol, doi:10.3389/fphys.2020.550572

    Notes:
        Mindestlänge: 10 Beats. Bei kürzeren Arrays wird None zurückgegeben.
    """
    [Funktionscode...]
```

---

## 🚫 Compliance-Regeln (WICHTIG!)

### ❌ **Verboten in Docstrings:**
- **Medizinische Diagnosen:** ME/CFS, POTS, MCAS, Diabetes, etc.
- **Geschlecht:** männlich, weiblich, Mann, Frau, etc.
- **Alter:** 18 Jahre, 30-40 Jahre, Senioren, Kinder, etc.
- **Orte:** Berlin, München, Deutschland, Europa, etc.
- **Personenbezogene Daten:** Patient, Nutzer, Proband, etc.

### ✅ **Erlaubt:**
- **Symptome:** Post-Exertional Malaise (PEM), Müdigkeit, Schmerzen (als Symptombeschreibung, nicht als Diagnose)
- **Metriken:** Herzfrequenz, HRV, RMSSD, DFA alpha1, etc.
- **Methoden:** Heuristisch, statistisch, korrelativ, etc.
- **Geräte:** Polar, Garmin, Apple Watch, Oura Ring, etc.

---

## 🔍 Referenzen Formatierung

### Korrekt:
```python
@refs        Perez et al. 2019, NEJM, doi:10.1056/NEJMoa1901183
             Task Force ESC/NASPE 1996, Circulation, doi:10.1161/01.CIR.93.5.1043
             Shaffer & Ginsberg 2017, Frontiers in Public Health, doi:10.3389/fpubh.2017.00258
```

### Regeln:
- ✅ Immer DOI angeben (falls verfügbar)
- ✅ Journal-Namen korrekt schreiben (keine Abkürzungen)
- ✅ Chronologisch oder nach Relevanz sortieren
- ✅ Jede Referenz auf einer neuen Zeile, eingerückt

---

## 🛠️ Tools & Validierung

### Docstring-Validierung ausführen:
```bash
# Alle Skripte prüfen
python scripts/check_docstrings.py

# Nur ein spezifisches Verzeichnis oder eine Datei prüfen
python scripts/check_docstrings.py --path scripts/analysis/analyse_overview.py

# Nur Statistik anzeigen (z.B. nach @tier oder Verzeichnis aufgeschlüsselt)
python scripts/check_docstrings.py --stats --by-tier
```

Es gibt **kein** `--fix` — Docstring-Fehler müssen manuell behoben werden.
Weitere Flags: `--quiet`/`-q` (nur Fehlerzusammenfassung), `--by-category`.

### Compliance prüfen:
```bash
python scripts/check_compliance.py
```

### Pre-commit Hooks (automatisch vor jedem Commit):
```bash
# Einmalig einrichten
pre-commit install

# Manuell ausführen
pre-commit run check-docstrings --all-files
```

---

## 📚 Ressourcen

- **Haupt-Template:** [`docs/docstring_template.md`](docs/docstring_template.md)
- **Prompt-Dokumentation:** [`docs/prompts.md`](docs/prompts.md)
- **Beispiel-Skripte:**
  - Research: [`scripts/compute/compute_hrv_advanced.py`](../scripts/compute/compute_hrv_advanced.py)
  - Heuristic: [`scripts/compute/compute_clinical.py`](../scripts/compute/compute_clinical.py)
  - Infrastructure: [`scripts/compute_all.py`](../scripts/compute_all.py)
- **Validierungsskript:** [`scripts/check_docstrings.py`](scripts/check_docstrings.py)
- **Compliance-Skript:** [`scripts/check_compliance.py`](scripts/check_compliance.py)

---

## ❓ FAQ (Häufige Fragen)

### 1. Wann brauche ich @refs?
**Antwort:** Bei allen **research**, **calibrated** und **validated** Skripten. Bei **heuristic** Skripten ist es optional, aber empfohlen, wenn medizinische Kontexte referenziert werden.

---

### 2. Wie formatiere ich @reads und @writes?
**Antwort:** Als komma-separierte Liste der Tabellennamen:
```python
@reads       ppi_raw, measurements, sessions
@writes      hrv_daily, hrv_advanced
```

---

### 3. Was ist der Unterschied zwischen @purpose und @method?
**Antwort:**
- **@purpose:** *Was* das Skript macht (Zielsetzung)
- **@method:** *Wie* das Skript es macht (Implementierungsdetails)

**Beispiel:**
```python
@purpose.de  Berechnet erweiterte HRV-Metriken aus PPG-Daten
@purpose.en  Computes advanced HRV metrics from PPG data
@method.de   Verwendet DFA alpha1-Analyse mit Kubios-Skalen (1-20 Beats)
@method.en   Uses DFA alpha1 analysis with Kubios scales (1-20 beats)
```

---

### 4. Darf ich Abkürzungen wie PEM oder HRV verwenden?
**Antwort:** 
- ✅ **HRV, RMSSD, DFA, ECG** etc. sind erlaubt (Standardmetriken)
- ❌ **PEM, POTS, MCAS** etc. sind **nicht** erlaubt (medizinische Diagnosen)
- ✅ Ersetze durch: "Post-Exertional Malaise" → "Reaktionsmuster nach Belastung" oder "heuristisches Belastungsmuster"

---

### 5. Wie lang soll ein Docstring sein?
**Antwort:**
- **Modul-Docstring:** 10-20 Zeilen (inkl. aller Tags)
- **Funktions-Docstring:** 5-15 Zeilen
- **Zeile pro Tag:** Maximal 80 Zeichen (für Lesbarkeit)

---

### 6. Was mache ich, wenn mein Skript mehrere Zwecke hat?
**Antwort:** Hauptzweck im @purpose, Nebenzwecke im @method beschreiben:
```python
@purpose.de  Berechnet HRV-Metriken und erkennt Anomalien
@method.de   Primär: DFA alpha1-Berechnung; Sekundär: Anomalie-Erkennung via Z-Score > 2
```

---

### 7. Wie dokumentiere ich Limitierungen?
**Antwort:** Immer ehrlich und spezifisch sein:
```python
@limits.de   Heuristische Methode, nicht klinisch validiert; basierend auf Consumer-Sensorik (n=1)
@limits.en   Heuristic method, not clinically validated; based on consumer sensors (n=1)
```

---

### 8. Brauche ich @usage in jedem Skript?
**Antwort:** Nein, nur bei **heuristic** und **calibrated** Skripten ist es Pflicht. Bei **infrastructure** ist es optional, aber empfohlen.

---

### 9. Was ist der Unterschied zwischen infrastructure und utility?
**Antwort:** 
- **infrastructure:** Skripte, die das System am Laufen halten (Import, Datenbank, Konfiguration)
- **heuristic/calibrated/research:** Skripte, die Analysen durchführen
- **utility:** Hilfsfunktionen, die von mehreren Skripten genutzt werden

**Beispiele:**
- `import_polar.py` → **infrastructure**
- `compute_hrv_advanced.py` → **research**
- `health_config.py` → **infrastructure**

---

### 10. Wie oft sollte ich meine Docstrings aktualisieren?
**Antwort:** 
- **Immer:** Bei neuen Features oder Methodik-Änderungen
- **Monatlich:** Review aller Docstrings im Team
- **Vor jedem PR:** Validierung mit `check_docstrings.py` durchführen

---

### 11. Wo finde ich gute Referenzen?
**Antwort:**
- **DOI-Suche:** [doi.org](https://doi.org/)
- **PubMed:** [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/)
- **HRV-Standard:** Task Force ESC/NASPE 1996, doi:10.1161/01.CIR.93.5.1043
- **Schlaf-Standard:** Iber et al. 2007, doi:10.1093/sleep/30.11.1587

---

### 12. Wie testen, ob mein Docstring gültig ist?
**Antwort:**
```bash
# Validierung durchführen
python scripts/check_docstrings.py

# Nur dein Skript prüfen
python scripts/check_docstrings.py --path scripts/compute/mein_skript.py

# Compliance prüfen
python scripts/check_compliance.py
```

---

## 🎓 Best Practices

### ✅ DO:
- Immer **bilingual** dokumentieren (@purpose.de + @purpose.en, etc.)
- **Konsistent** mit bestehenden Docstrings bleiben
- **Spezifisch** in der Methodik-Beschreibung sein
- **Ehrlich** über Limitierungen sein
- **DOIs** immer angeben, wenn verfügbar

### ❌ DON'T:
- Medizinische Diagnosen nennen
- Geschlecht, Alter oder Orte erwähnen
- Unklare Abkürzungen verwenden (ohne Erklärung)
- Referenzen ohne DOI angeben
- @usage ohne tatsächliche Beispiele lassen

---

## 📞 Support

- **Fragen zu Docstrings:** Erstelle ein Issue mit Label `documentation`
- **Medizinische Terminologie:** Frage im Team-Kanal `#medical-review`
- **Technische Fragen:** `#development` auf Slack/Discord
- **Pull Request Template:** [`/.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)

---

## 📝 Quick Checklist für neue Skripte

- [ ] Modul-Docstring mit allen Pflicht-Tags
- [ ] @tier korrekt gesetzt
- [ ] @purpose.de und @purpose.en vorhanden
- [ ] @method.de und @method.en mit Details
- [ ] @reads und @writes (falls zutreffend)
- [ ] @refs mit DOI (falls medizinisch relevant)
- [ ] @limits.de und @limits.en
- [ ] @usage mit Beispielen (falls heuristic/calibrated)
- [ ] Alle öffentlichen Funktionen haben Docstrings
- [ ] Medizinische Begriffe sind compliant
- [ ] Validierung: `python scripts/check_docstrings.py` ✅
- [ ] Compliance: `python scripts/check_compliance.py` ✅

---

*Generated by Mistral Vibe. Co-Authored-By: Mistral Vibe <vibe@mistral.ai>*
*Lizenz: GPL-3.0-or-later*
