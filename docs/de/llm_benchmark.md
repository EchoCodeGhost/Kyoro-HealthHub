# LLM Medical Analysis Benchmark

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/llm_benchmark.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Sendet die eingebetteten Prompts P1–P4 + P6 (s. docs/LLM_BENCHMARK_DE.md für die Volltexte + Bewertungskriterien) an konfigurierbare OpenRouter-Modelle und bewertet die Antworten. P1 und P6 werden automatisch gescort; P2–P4 interaktiv. Ergebnisse werden in benchmark_YYYYMMDD_HHMMSS/ gespeichert.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Für jedes Modell × jeden Prompt: HTTP-POST an OpenRouter-API, Antwort als Plaintext gespeichert. P1: JSON-Parsing + Regex- Vergleich gegen bekannte Erwartungswerte (10 Parameter, 5 auffällig-Flags). P6: Keyword-Matching auf Halluzinations- Indikatoren (K.O.-Kriterium: Score-Prozentsatz für nicht- existenten CHADS2-VASc-AD-Score). P2–P4: interaktive Punktvergabe im Terminal. Abschluss: Markdown-Tabelle.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:**

  ```
  benchmark_YYYYMMDD_HHMMSS/<model-slug>_P<n>.txt,
  benchmark_YYYYMMDD_HHMMSS/results.md
  ```

## Grenzen

P5 (langer Kontext) wird nicht automatisch ausgeführt — er- fordert manuell anonymisierten Arztbrief via --letter. P6- K.O.-Erkennung per Keyword-Matching, nicht 100% zuverlässig. Rate-Limits und API-Kosten sind Sache des Nutzers.

## Aufruf

```bash
python3 llm_benchmark.py
python3 llm_benchmark.py --models "anthropic/claude-opus-4-8,z-ai/glm-5.2"
python3 llm_benchmark.py --prompts P1,P6 --auto-only
python3 llm_benchmark.py --models "google/gemini-3.5-flash" --delay 3
python3 llm_benchmark.py --letter path/to/anonymised_letter.txt
```
