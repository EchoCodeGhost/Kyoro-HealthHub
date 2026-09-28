# LLM Medical Analysis Benchmark

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/llm_benchmark.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Sends the embedded prompts P1–P4 + P6 (see docs/LLM_BENCHMARK.md for full text + scoring criteria) to configurable OpenRouter models and scores the answers. P1 and P6 are auto-scored; P2–P4 are scored interactively. Results are saved to benchmark_YYYYMMDD_HHMMSS/.

## Relevance

Provides health data functions, essential for medical data processing

## Method

For each model × prompt: HTTP POST to OpenRouter API, response saved as plain text. P1: JSON parsing + regex comparison against known expected values (10 params, 5 auffaellig flags). P6: keyword matching for hallucination indicators (K.O. criterion: percentage score for non-existent CHADS2-VASc-AD score). P2–P4: interactive scoring in terminal. Final: markdown table.

## Data flow

- **Reads:** `keine`
- **Writes:**

  ```
  benchmark_YYYYMMDD_HHMMSS/<model-slug>_P<n>.txt,
  benchmark_YYYYMMDD_HHMMSS/results.md
  ```

## Limitations

P5 (long context) is not run automatically — requires a manually anonymised letter via --letter. P6 K.O. detection via keyword matching, not 100% reliable. Rate limits and API costs are the user's responsibility.

## Usage

```bash
python3 llm_benchmark.py
python3 llm_benchmark.py --models "anthropic/claude-opus-4-8,z-ai/glm-5.2"
python3 llm_benchmark.py --prompts P1,P6 --auto-only
python3 llm_benchmark.py --models "google/gemini-3.5-flash" --delay 3
python3 llm_benchmark.py --letter path/to/anonymised_letter.txt
```
