# analyse_reha_klinik_empfehlung.py — LLM-gestützte Reha-Klinikempfehlung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_reha_klinik_empfehlung.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Gleicht das aktuelle Krankheitsbild (jüngster Konsil-Synthese-Bericht) gegen eine oder mehrere geparste Reha-Einrichtungslisten (DRV, dasrehaportal.de) ab und lässt ein LLM eine begründete, rangierte Empfehlung erstellen — als Diskussionsgrundlage für das Wunsch- und Wahlrecht nach §8 SGB IX, keine Zuweisung.

## Relevanz

Unterstützt die Reha-Planung mit KI-gestütztem Abgleich, direkter Bezug zu personenbezogenen Gesundheitsdaten (Krankheitsbild)

## Methode

Liest den neuesten vollständigen Synthese-Bericht aus analyses/synthesis/ (nur der Hauptteil vor dem Anhang) und die kompakte Einrichtungs-Übersicht der über --sources gewählten Quellen (Default: nur drv). Jede Quelle wird auf ein gemeinsames Schema normalisiert (Referenz/Quelle/Name/Ort/ Kategorien/Angebot/Kostenträger/Zusatzfeld) und mit einer eigenen Referenz (z. B. "DRV-55", "REHAPORTAL-1") versehen, damit das LLM Einrichtungen über Quellen hinweg eindeutig zitieren kann. Optional: --kostentraeger schließt in Python (nicht nur per LLM-Anweisung) Einrichtungen aus, für die belegt ist, dass sie keinen der genannten Träger abrechnen — Einrichtungen ohne Kostenträger-Datenlage bleiben drin und werden als "unbekannt" markiert. --priorities sucht nach Textübereinstimmungen in Kategorien/Angebot/Beschreibung/Zusatzfeld, reiht Treffer nach vorn und markiert sie mit ★ — gewichtet dabei nach Position in der --priorities-Liste (zuerst genannt zählt am meisten), nicht nach roher Trefferzahl, damit ein einzelner Treffer auf die wichtigste Priorität mehrere Treffer auf nachrangige Begriffe übertrumpft. Prioritäten ohne Treffer werden explizit gemeldet statt stillschweigend ignoriert. --question hängt eine freie Zusatzfrage/-einschränkung an. Das Ergebnis wird als Markdown-Bericht gespeichert.

## Berechnung

```
Rangfolge durch das LLM anhand inhaltlicher Übereinstimmung
zwischen Krankheitsbild und Kategorien/Klinikangebot der
jeweiligen Einrichtung — kein numerischer Score, freie Begründung.
```

## Datenfluss

- **Liest:** `analyses/synthesis/synthesis_*.md`, `(neuester`, `vollständiger`, `Bericht)`, `imports/drv-kliniken/kliniken.json`, `(Quelle`, `"drv")`, `imports/rehaportal/kliniken.json`, `(Quelle`, `"rehaportal")`
- **Schreibt:** `analyses/reha_klinik/empfehlung_<timestamp>.md`

## Grenzen

Heuristische LLM-Analyse, keine Zuweisungsentscheidung — der zuständige Kostenträger trifft die tatsächliche Wahl; das Ergebnis ist nur eine Diskussionsgrundlage für den eigenen Antrag. "Angebot" ist Freitext der Einrichtungen, keine kontrollierte Taxonomie. Kostenträger-Daten aus dasrehaportal.de existieren nur für Einrichtungen, deren Detailseite bereits per rehaportal_details_download.py geladen wurde. Kein automatischer Remote-Fallback — --backend muss explizit gewählt werden.

## Referenzen

- Muneer A, Zhang K, Hamdi I, Qureshi R, Waqas M, Fouad S, Ali H, Anwar SM, Wu J (2026). Foundation models in biomedical imaging: turning hype into reality. Nature Biomedical Engineering, 10:1557-1575. doi:10.1038/s41551-026-01762-z (REAL-FM framework — Grundlage für die über grounding_suffix() angehängte Konfidenz-/Beleg-Pflicht, dieselbe Referenz wie analyse_synthesis.py)

## Aufruf

```bash
python3 analyse_reha_klinik_empfehlung.py --list-backends
python3 analyse_reha_klinik_empfehlung.py --backend medical
python3 analyse_reha_klinik_empfehlung.py --backend default --top 8
python3 analyse_reha_klinik_empfehlung.py --backend default         --priorities "Orthopädie,Schmerztherapie" --question "nur Kliniken in Bayern"
python3 analyse_reha_klinik_empfehlung.py --backend default         --sources drv,rehaportal --kostentraeger "GKV,DRV"
```
