# llm.py — LLM/VLM-Brücke

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/llm.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides a unified interface for LLM and VLM calls. Delegates to the configured provider in health_config.json.

## Relevance

Provides language model interfaces, essential for AI integration

## Method

Text calls use the provider under "llm" in health_config.json. Vision calls use the provider under "vlm" (falls back to "llm" provider if "vlm" is absent). Supports text-only and multi-modal prompts.

## Data flow

- **Reads:** `~/.config/kyoro/health_config.json`, `(Provider-Konfiguration)`
- **Writes:** `Keine Tabellen (gibt LLM-Antworten zurück)`

## Limitations

Dependent on configured LLM provider. No guarantee of response quality or data privacy.

## References

- Muneer, A., Zhang, K., Hamdi, I., Qureshi, R., Waqas, M., Fouad, S., Ali, H., Anwar, S.M., Wu, J. (2026). Foundation models in biomedical imaging: turning hype into reality. Nature Biomedical Engineering, 10:1557-1575. doi:10.1038/s41551-026-01762-z (REAL-FM framework — Grundlage fuer _GROUNDING_SUFFIX/require_grounding und ai_label()/label_output unten: Kalibrierung/Unsicherheitsangabe sowie die KI-Kennzeichnungspflicht aus openspec/specs/ethics-enforcement/spec.md fehlten projektweit bis auf ein einzelnes Skript)

## Usage

```bash
from modules.llm import call_llm
response = call_llm(prompt, system="You are …")
import base64
b64 = base64.b64encode(Path("scan.jpg").read_bytes()).decode()
response = call_llm(prompt, image_b64=b64, image_mime="image/jpeg")
```
