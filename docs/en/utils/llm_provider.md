# utils/llm_provider.py — Unified LLM provider for all Kyoro-HealthHub scripts.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/llm_provider.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides a unified interface for various LLM providers

## Relevance

Provides interfaces to language models, essential for AI-powered data analysis

## Method

Supports local (OpenVINO, MLX, Ollama) and cloud providers (Anthropic, Mistral, OpenRouter, Azure). Automatic detection and configuration. Vision support for multimodal models.

## Data flow

- **Reads:** `~/.config/kyoro/health_config.json`, `(Provider-Konfiguration)`
- **Writes:** `Keine Tabellen (gibt LLM-Antworten zurueck)`

## Limitations

Performance and capabilities vary between providers. Local models require hardware resources.

## Usage

```bash
python llm_provider.py
python llm_provider.py --help
```
