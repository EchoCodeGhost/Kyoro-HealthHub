# utils/llm_provider.py — Unified LLM provider for all Kyoro-HealthHub scripts.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/llm_provider.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet eine vereinheitlichte Schnittstelle für verschiedene LLM-Anbieter

## Relevanz

Bietet Schnittstellen zu Sprachmodellen, essentiell für die KI-gestützte Datenanalyse

## Methode

Unterstützt lokale (OpenVINO, MLX, Ollama) und Cloud-Anbieter (Anthropic, Mistral, OpenRouter, Azure). Automatische Erkennung und Konfiguration. Vision-Unterstützung für multimodale Modelle.

## Datenfluss

- **Liest:** `~/.config/kyoro/health_config.json`, `(Provider-Konfiguration)`
- **Schreibt:** `Keine Tabellen (gibt LLM-Antworten zurueck)`

## Grenzen

Performanz und Fähigkeiten variieren zwischen den Anbietern. Lokale Modelle erfordern Hardware-Ressourcen.

## Aufruf

```bash
python llm_provider.py
python llm_provider.py --help
```
