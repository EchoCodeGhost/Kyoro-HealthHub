# symptom_synonyms.py — Kanonische Symptomnamen fuer den Abgleich Tagebuch <-> Syndromprofil

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/symptom_synonyms.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bildet Symptomnamen auf kanonische Namen ab, damit gleichbedeutende Begriffe beim Abgleich als dasselbe Symptom zaehlen (z.B. "Myalgie" im Syndromprofil und "Muskelschmerzen" im Symptomtagebuch, oder der kombinierte Tagebuch- eintrag "Erschoepfung/Fatigue" und "Fatigue" im Profil).

## Relevanz

Ohne Synonyme gehen Treffer verloren, sobald Tagebuch und Syndromprofil unterschiedliche Begriffe fuer dasselbe Symptom verwenden.

## Methode

Zwei Stufen. (1) Rohe Tagebuchnamen ueber config/symptom_map.json (bzw. die Nutzerkopie in ~/.config/kyoro/symptom_map.json, wie compute_symptoms.py) auf deren kanonischen deutschen Namen. (2) Synonymgruppen und kombinierte Eintraege aus scripts/analysis/syndromes/_symptom_synonyms.json auf die Namen der Syndromprofile; ein kombinierter Eintrag kann mehrere Profil- symptome treffen. Abgleich ohne Gross-/Kleinschreibung, mit normalisierten Leerzeichen/Bindestrichen. Unbekannte Namen bleiben unveraendert (getrimmt). Symptom-Tage werden pro kanonischem Namen ueber distinkte Daten gezaehlt.

## Datenfluss

- **Liest:** `config/symptom_map.json`, `(oder`, `~/.config/kyoro/symptom_map.json)`, `scripts/analysis/syndromes/_symptom_synonyms.json`, `Tabelle`, `symptoms`, `(nur`, `raw_symptom_names:`, `distinkte`, `Symptomnamen)`
- **Schreibt:** `Keine (reine Hilfsfunktionen)`

## Grenzen

Nur exakte Synonyme bzw. engere Begriffe auf den breiteren Profilbegriff; keine unscharfe Suche, keine Teilwort-Treffer. Mehrdeutige Begriffe sind bewusst nicht enthalten (s. _meta in der JSON-Datei).

## Aufruf

```bash
from modules.symptom_synonyms import canonical_symptoms, canonicalize, count_symptom_days
from modules.symptom_synonyms import FATIGUE_LIKE, raw_symptom_names
canonical_symptoms("Myalgie")                          # -> {"Muskelschmerzen"}
canonical_symptoms("Brainfog/Konzentrationsstörungen") # -> {"Brain Fog", "Konzentrationsstörungen"}
canonicalize(["PEM", "Tachykardie"])                   # -> {"Post-Exertionelle Malaise", "Herzrasen"}
count_symptom_days([("Myalgie", "2026-01-01"), ("Muskelschmerzen", "2026-01-01")])
                                                       # -> {"Muskelschmerzen": 1}
raw_symptom_names(conn, FATIGUE_LIKE)   # -> ["Erschöpfung/Fatigue", "erschoepfung_fatigue", ...]
```
