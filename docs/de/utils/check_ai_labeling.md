# KI-Kennzeichnungs-Compliance-Check

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_ai_labeling.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft automatisiert, dass kein Skript einen eigenen, handgestrickten LLM-Chat-Completion-Aufruf implementiert, ohne die zentrale KI-Kennzeichnung (modules.llm.ai_label()) zu verwenden. openspec/specs/ethics-enforcement/spec.md ("Labeling of AI-generated output") war bisher nur durch manuelle PR-Review durchgesetzt — ein Audit fand die meisten call_llm()-Aufrufer ohne Kennzeichnung, plus zwei Skripte (analyse_synthesis.py, analyse_clinical_addendum.py), die modules.llm.call_llm() komplett umgehen und daher auch dessen automatische Kennzeichnung (call_llm(..., label_output=True), seit diesem Fix Standard) nie erreicht hätten.

## Relevanz

Technische Durchsetzung der KI-Kennzeichnungspflicht (s. docs/ETHICS.md §6, openspec/specs/ethics-enforcement/spec.md) — ohne diesen Check kann eine neue Umgehung von call_llm() unbemerkt unmarkierte Ausgaben erzeugen.

## Methode

Durchsucht scripts/**/*.py nach dem OpenAI-kompatiblen Chat-Message-Muster ("role": "system" UND "role": "user" im selben File — die Signatur eines selbstgebauten Chat-Completion-Requests). Trifft das zu, muss dieselbe Datei auch ai_label( aufrufen. modules/llm.py und utils/llm_provider.py sind die kanonische Implementierung (dort entsteht die Kennzeichnung) und ausgenommen; llm_benchmark.py ist ein Entwickler-Werkzeug zum Modellvergleich, keine für Endnutzer angezeigte klinische Ausgabe, und dokumentiert ausgenommen.

## Datenfluss

- **Liest:** `scripts/**/*.py`
- **Schreibt:** `STDOUT/STDERR (Fehlermeldungen)`

## Grenzen

Heuristik über Quelltext-Substrings (kein AST/Datenfluss-Tracking) — erkennt keine dynamisch aus Strings zusammengesetzten Chat-Payloads und keine Kennzeichnung über Aliase/Re-Exports von ai_label.

## Aufruf

```bash
python3 scripts/utils/check_ai_labeling.py
python3 scripts/utils/check_ai_labeling.py --path scripts
```
