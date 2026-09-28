# Docstring FAQ — Kyoro-HealthHub

**Version:** 1.1  
**Ziel:** Häufige Fragen und Antworten zu Docstrings im Kyoro-HealthHub  

---

## 📋 Inhaltsverzeichnis

1. [Allgemeine Fragen](#-allgemeine-fragen)
2. [Tag-spezifische Fragen](#-tag-spezifische-fragen)
3. [Compliance & Medizinische Terminologie](#-compliance--medizinische-terminologie)
4. [Validierung & Tools](#-validierung--tools)
5. [Best Practices](#-best-practices)
6. [Fehlerbehebung](#-fehlerbehebung)

---

## 🤔 Allgemeine Fragen

### 1.01 Warum sind Docstrings im Kyoro-HealthHub so wichtig?
**Antwort:** 
Im Kyoro-HealthHub sind Docstrings nicht nur Dokumentation, sondern **Compliance-Anforderung** und **Qualitätssicherungsinstrument**:
- **Medizinische Validität:** Klare Trennung zwischen validierten und heuristischen Methoden
- **Rechtssicherheit:** Vermeidung von medizinischen Diagnosen, Geschlecht, Alter, Orten
- **Forschungsfähigkeit:** Nachvollziehbare Methoden für wissenschaftliche Nutzung
- **Community:** Einfacheres Onboarding und Wartbarkeit

---

### 1.02 Wer ist für Docstrings verantwortlich?
**Antwort:** Jeder Contributor! Die Pflicht liegt beim Entwickler, der Code schreibt oder ändert. Vor jedem Pull Request:
- Docstring-Validierung durchführen
- Compliance-Prüfung durchführen
- Peer-Review einholen

---

### 1.03 Wie oft müssen Docstrings aktualisiert werden?
**Antwort:**
- **Immer:** Bei Code-Änderungen (neue Funktionen, geänderte Methodik)
- **Monatlich:** Team-Review aller Docstrings
- **Vor jedem PR:** Automatische Validierung
- **Jährlich:** Vollständiges Template-Review

---

## 🏷️ Tag-spezifische Fragen

### 2.01 Welche @tier-Kategorien gibt es und wann verwende ich welche?

| Tier | Beschreibung | Beispiele |
|------|--------------|----------|
| **validated** | Klinisch validierte Algorithmen (FDA-cleared, peer-reviewed) | KI-basierte Arrhythmie-Erkennung (falls zertifiziert) |
| **calibrated** | Kalibrierte Methoden mit individueller Anpassung | Trainings-Performance-Analyse |
| **research** | Komplexe Algorithmen mit wissenschaftlicher Grundlage | HRV-Analyse, DFA alpha1 |
| **heuristic** | Heuristische Methoden, experimentell | PEM-Erkennung, Stress-Scores |
| **experimental** | Experimentelle Ansätze in Entwicklung | Neue Algorithmen in Testphase |
| **infrastructure** | System-Skripte (Import, Konfiguration, Utilities) | import_polar.py, health_config.py |

---

### 2.02 Was ist der Unterschied zwischen @purpose und @method?
**Antwort:**

| Tag | Frage | Beispiel |
|-----|-------|----------|
| **@purpose** | *Was* macht das Skript? | "Berechnet HRV-Metriken" |
| **@method** | *Wie* macht es das? | "Verwendet DFA alpha1-Analyse mit Kubios-Skalen" |

**Merksatz:** Purpose = Ziel, Method = Weg

---

### 2.03 Was ist der Unterschied zwischen @purpose und @relevance?
**Antwort:**

| Tag | Frage | Beispiel |
|-----|-------|----------|
| **@purpose** | *Was* macht das Skript? | "Berechnet HRV-Metriken pro 5-Minuten-Fenster" |
| **@relevance** | *Warum* ist das relevant? | "HRV-Abfall ist ein früher Indikator für autonome Dysfunktion — zentral für die Verlaufsbeurteilung" |

`@relevance.de`/`@relevance.en` ist für
**alle** `@tier`-Werte Pflicht, ohne Ausnahme (auch `infrastructure`
und `heuristic`). Details und Beispiele: [docstring_template.md,
Abschnitt „@relevance"](docstring_template.md#-relevance--warum-ist-dieser-datentyp-relevant).

---

### 2.04 Wann brauche ich @reads und @writes?
**Antwort:**
- **@reads:** Immer, wenn das Skript Daten aus der Datenbank liest
- **@writes:** Immer, wenn das Skript Daten in die Datenbank schreibt
- **Format:** Komma-separierte Liste der Tabellennamen

**Beispiel:**
```python
@reads       ppi_raw, measurements, sessions
@writes      hrv_daily, hrv_advanced
```

---

### 2.05 Wann brauche ich @refs?
**Antwort:**

| Tier | @refs Pflicht? | Begründung |
|------|---------------|------------|
| validated | ✅ Ja | Klinische Validierung muss referenziert werden |
| calibrated | ✅ Ja | Kalibrierungsgrundlage muss nachvollziehbar sein |
| research | ✅ Ja | Wissenschaftliche Grundlage muss zitiert werden |
| heuristic | ⚠️ Optional | Empfohlen, wenn medizinische Kontexte referenziert werden |
| experimental | ❌ Nein | Entwicklungsstatus macht Referenzen schwierig |
| infrastructure | ❌ Nein | Keine wissenschaftliche Grundlage nötig |

---

### 2.06 Wie viele Referenzen brauche ich?
**Antwort:**
- **Minimum:** 1 Referenz (für research/calibrated/validated)
- **Empfohlen:** 2-3 Referenzen (primäre + sekundäre Quellen)
- **Format:** Immer mit DOI, wenn verfügbar

---

### 2.07 Was ist @usage und wann brauche ich es?
**Antwort:**
- **Zweck:** Zeigt konkrete Verwendungsbeispiele
- **Pflicht für:** heuristic, calibrated Skripte
- **Empfohlen für:** Alle Skripte mit CLI-Schnittstelle
- **Format:** 2-3 konkrete Befehlszeilen

**Beispiel:**
```python
@usage
    python analyse_overview.py --plot
    python analyse_overview.py --from 2024-01-01 --weeks 12
    python analyse_overview.py --no-llm
```

---

### 2.08 Was ist @scoring?
**Antwort:**
- **Zweck:** Beschreibt das Bewertungsschema für Scores
- **Pflicht:** Nein, aber empfohlen für heuristic Skripte mit Scoring
- **Format:** Klare Formel oder Beschreibung

**Beispiel:**
```python
@scoring direct = max(ECG_AFib=50, TG_Episode=40)
```

---

### 2.09 Was sind die Prompt-Tags (@prompt-classification, @prompt.de, @prompt.en)?
**Antwort:**
- **@prompt-classification:** Typ des Prompts (LLM, VLM, both, none)
- **@prompt.de:** Beschreibung des Prompts auf Deutsch
- **@prompt.en:** Beschreibung des Prompts auf Englisch
- **Verwendung:** Nur für Skripte, die LLM/VLM verwenden

**Beispiel:**
```python
@prompt-classification LLM
@prompt.de   Analysiert Symptome mit Large Language Model
@prompt.en   Analyzes symptoms using Large Language Model
```

---

### 2.10 Was ist `scripts/modules/confidence.py` und wann benutze ich es?
**Antwort:** Ein gemeinsames Modul für Analyse-Skripte, die Befunde mit
unterschiedlicher Sicherheit kommunizieren. Statt ein eigenes lokales
Vokabular zu erfinden, `label_finding()` mit einer der drei Stufen
`"confirmed"` / `"suspected"` / `"lead"` aufrufen:

```python
from modules.confidence import label_finding

de, en = label_finding("X bestätigt", "X confirmed", "confirmed")
# de == "✅ Bestätigt: X bestätigt"
```

Details, Stufen-Definitionen und Anwendungsbeispiele: [docstring_template.md,
Abschnitt „Konfidenz-Kennzeichnung"](docstring_template.md#konfidenz-kennzeichnung-scriptsmodulesconfidencepy).

---

## ⚖️ Compliance & Medizinische Terminologie

### 3.01 Welche medizinischen Begriffe sind verboten?
**Antwort:** **ALLE** spezifischen medizinischen Diagnosen:

❌ **Verboten:**
- ME/CFS, POTS, MCAS
- Diabetes, Bluthochdruck, Herzinfarkt
- COVID-19, Long COVID, Post-COVID
- Autoimmunerkrankungen
- Neurologische Erkrankungen (MS, Parkinson, etc.)
- Psychische Erkrankungen (Depression, Angststörung, etc.)
- Geschlecht (männlich, weiblich, Mann, Frau, etc.)
- Alter (18 Jahre, 30-40, Senioren, Kinder, etc.)
- Orte (Berlin, München, Deutschland, Europa, etc.)
- Personenbezogene Daten (Patient, Nutzer, Proband, etc.)

---

### 3.02 Welche medizinischen Begriffe sind erlaubt?
**Antwort:** ✅ **Generische Metriken und Methoden:**

| Kategorie | Beispiele |
|----------|----------|
| **HRV-Metriken** | RMSSD, SDNN, DFA alpha1, HF, LF, LF/HF |
| **Herzfrequenz** | Ruhepuls (RHR), maximale Herzfrequenz, AFib-Burden |
| **Schlaf** | Tiefschlaf, REM-Schlaf, Schlafeffizienz |
| **Aktivität** | Schritte, Kalorienverbrauch, VO2max |
| **Sensorik** | PPG, ECG, SpO₂ |
| **Methoden** | Heuristisch, statistisch, korrelativ |

---

### 3.03 Wie ersetze ich verbotene medizinische Begriffe?
**Antwort:**

| Verbotener Begriff | Ersetzungsvorschlag |
|------------------|---------------------|
| POTS | "Orthostatische Reaktionen", "Herzfrequenzanstieg im Stehen" |
| PEM | "Reaktionsmuster nach Belastung", "heuristisches Belastungsmuster" |
| ME/CFS | "Chronische Erschöpfung" (nur als Symptom, nicht als Diagnose) |
| Diabetes | "Blutzuckerwerte", "Glukosestoffwechsel" |
| Patient | "Nutzer", "Person", "Datenquelle" |

---

### 3.04 Darf ich "Herzfrequenz" oder "HRV" verwenden?
**Antwort:** ✅ **Ja!** Das sind **Metriken**, keine Diagnosen.

- ✅ **Erlaubt:** Herzfrequenz, HRV, RMSSD, Blutdruck, Schlafphasen
- ❌ **Verboten:** Herzinfarkt, Vorhofflimmern (als Diagnose), POTS, Diabetes

---

### 3.05 Wie dokumentiere ich, dass etwas nicht klinisch validiert ist?
**Antwort:** Immer im @limits Tag klar kommunizieren:

```python
@limits.de   Heuristische Methode, nicht klinisch validiert; basierend auf Consumer-Sensorik (n=1)
@limits.en   Heuristic method, not clinically validated; based on consumer sensors (n=1)
```

---

### 3.06 Darf ich Gerätenamen nennen?
**Antwort:** ✅ **Ja!** Gerätenamen sind erlaubt:

- Polar, Garmin, Apple Watch, Oura Ring
- Kubios, WHOOP, Fitbit
- Home Assistant, Open-Meteo

---

## 🔧 Validierung & Tools

### 4.01 Wie führe ich die Docstring-Validierung aus?
**Antwort:**

```bash
# Alle Skripte validieren
python scripts/check_docstrings.py

# Nur ein spezifisches Verzeichnis oder eine Datei
python scripts/check_docstrings.py --path scripts/analysis/analyse_overview.py

# Nur Statistik anzeigen
python scripts/check_docstrings.py --stats
```

`check_docstrings.py` hat **kein** `--fix`: Fehler müssen manuell im
Docstring behoben werden. `--path`/`-p` akzeptiert sowohl ein Verzeichnis
als auch eine einzelne Datei; weitere Flags: `--quiet`/`-q` (nur
Fehlerzusammenfassung), `--by-tier`, `--by-category`.

---

### 4.02 Wie führe ich die Compliance-Prüfung aus?
**Antwort:**

```bash
python scripts/check_compliance.py
```

---

### 4.03 Was sind die Unterschiede zwischen Validierung und Compliance?
**Antwort:**

| Prüfung | Zweck | Tool |
|--------|-------|------|
| **Validierung** | Prüft Struktur und Pflicht-Tags der Docstrings | `check_docstrings.py` |
| **Compliance** | Prüft auf verbotene Inhalte (Diagnosen, Geschlecht, Alter, Orte) | `check_compliance.py` |

---

### 4.04 Wie richte ich Pre-commit Hooks ein?
**Antwort:**

```bash
# Pre-commit Hooks installieren (einmalig)
pre-commit install

# Manuell ausführen
pre-commit run check-docstrings --all-files

# Automatisch vor jedem Commit läuft dann:
# - Docstring-Validierung
# - Compliance-Prüfung
```

---

### 4.05 Was mache ich, wenn die Validierung einen Fehler meldet?
**Antwort:**

1. **Fehler lesen:** Der Validierungsreport zeigt genau, was fehlt
2. **Docstring anpassen:** Fehlende Tags hinzufügen
3. **Neu validieren:** `python scripts/check_docstrings.py`
4. **Compliance prüfen:** `python scripts/check_compliance.py`

**Beispiel-Fehler:**
```
scripts/mein_skript.py:
  ❌ Missing required tag: @purpose.de
  ❌ Missing required tag: @purpose.en
```

**Lösung:** Docstring mit den fehlenden Tags ergänzen.

---

## ✨ Best Practices

### 5.01 Soll ich alle Tags in jeder Sprache haben?
**Antwort:** ✅ **Ja!** Bilinguale Dokumentation ist Pflicht:
- @purpose.de **und** @purpose.en
- @method.de **und** @method.en
- @limits.de **und** @limits.en

---

### 5.02 Soll ich @usage in infrastructure-Skripten haben?
**Antwort:** ⚠️ **Optional, aber empfohlen** für Skripte mit CLI-Schnittstelle.

---

### 5.03 Wie lang sollte eine Zeile in einem Docstring sein?
**Antwort:** Maximal **80-100 Zeichen** für gute Lesbarkeit.

---

### 5.04 Soll ich Abkürzungen erklären?
**Antwort:** ✅ **Ja!** Unbekannte Abkürzungen bei erstmaliger Verwendung erklären:

```python
@method.de   HRV (Heart Rate Variability) Analyse via DFA (Detrended Fluctuation Analysis)
```

---

### 5.05 Wie dokumentiere ich mehrere Eingabetabellen?
**Antwort:** Komma-separiert, nach Relevanz sortiert:

```python
@reads       ppi_raw, measurements, sessions, symptoms
```

---

## 🛠️ Fehlerbehebung

### 6.01 Die Validierung findet meinen Docstring nicht
**Antwort:** 

**Häufige Ursachen:**
1. **Docstring steht nicht am Anfang:** Der Docstring muss **direkt** nach dem Modul-Header kommen
2. **Leere Zeilen vor dem Docstring:** Nicht erlaubt
3. **Code vor dem Docstring:** Variablen wie `__version__` müssen **nach** dem Docstring stehen

**Korrekt:**
```python
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Modul-Docstring hier...
"""

__version__ = "1.0.0"  # Nach dem Docstring!
```

**Falsch:**
```python
#!/usr/bin/env python3
__version__ = "1.0.0"  # Vor dem Docstring!

"""
Modul-Docstring hier...
"""
```

---

### 6.02 Der Validierung fehlt mein @tier Tag
**Antwort:** Prüfe:
1. Ist `@tier` in der **ersten Zeile** des Docstrings?
2. Ist einer der gültigen Werte verwendet: `validated`, `calibrated`, `research`, `heuristic`, `experimental`, `infrastructure`?
3. Steht zwischen `@tier` und dem Wert ein Doppelpunkt oder ein anderes Zeichen statt Leerzeichen? `@tier heuristic` ✅, auch mit mehreren Leerzeichen (`@tier  heuristic` ✅ — `check_docstrings.py` nutzt die Regex `@tier\s+(\w+)`), aber `@tier: heuristic` ❌ (der Doppelpunkt verhindert das Matching, `@tier` gilt dann als fehlend)

---

### 6.03 Die Compliance-Prüfung meldet medizinische Diagnosen
**Antwort:**

**Häufige Quellen:**
1. **Im Docstring:** Direkte Erwähnung von POTS, ME/CFS, etc.
2. **Im Code:** Variablennamen, Kommentare, String-Literale
3. **In Beispielen:** @usage oder Konfigurationsbeispiele

**Lösung:**
- Docstrings anpassen (Diagnosen entfernen)
- Code-Kommentare bereinigen
- Beispiel-Konfigurationen mit neutralen Begriffen ersetzen

---

### 6.04 Mein Skript wird als "kein Modul-Docstring" gemeldet
**Antwort:** Siehe [6.01](#601-die-validierung-findet-meinen-docstring-nicht)

---

### 6.05 Die Validierung sagt "Missing required tag: @refs"
**Antwort:**

1. Prüfe, ob dein Skript-Typ @refs benötigt (siehe [2.05](#205-wann-brauche-ich-refs))
2. Füge mindestens **1 Referenz mit DOI** hinzu
3. Format: `Autor et al. Jahr, Journal, doi:xxx`

---

## 📚 Weitere Ressourcen

- **Haupt-Dokumentation:** [docs/docstring_template.md](docs/docstring_template.md)
- **Onboarding Guide:** [docs/docstring_onboarding_guide.md](docs/docstring_onboarding_guide.md)
- **Prompt-Dokumentation:** [docs/prompts.md](docs/prompts.md)
- **Beispiel-Skripte:** `scripts/compute/compute_hrv_advanced.py` (research), `scripts/compute/compute_clinical.py` (heuristic), `scripts/compute_all.py` (infrastructure)
- **Validierungsskript:** [scripts/check_docstrings.py](scripts/check_docstrings.py)
- **Compliance-Skript:** [scripts/check_compliance.py](scripts/check_compliance.py)

---

*Generated by Mistral Vibe. Co-Authored-By: Mistral Vibe <vibe@mistral.ai>*
*Lizenz: GPL-3.0-or-later*
