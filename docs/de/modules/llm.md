# llm.py — LLM/VLM-Brücke

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/llm.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet eine einheitliche Schnittstelle für LLM- und VLM-Aufrufe. delegiert an den konfigurierten Provider in health_config.json.

## Relevanz

Bietet Sprachmodell-Schnittstellen, essentiell für die KI-Integration

## Methode

Text-Aufrufe verwenden den Provider unter "llm" in health_config.json. Vision-Aufrufe verwenden den Provider unter "vlm" (fällt auf "llm" zurück, falls "vlm" nicht konfiguriert). Unterstützt Text-Only und Multi-Modal-Prompts.

## Datenfluss

- **Liest:** `~/.config/kyoro/health_config.json`, `(Provider-Konfiguration)`
- **Schreibt:** `Keine Tabellen (gibt LLM-Antworten zurück)`

## Grenzen

Abhaengig vom konfigurierten LLM-Provider. Keine Garantie fuer Antwortqualitaet oder Datenschutz.

## Referenzen

- Muneer, A., Zhang, K., Hamdi, I., Qureshi, R., Waqas, M., Fouad, S., Ali, H., Anwar, S.M., Wu, J. (2026). Foundation models in biomedical imaging: turning hype into reality. Nature Biomedical Engineering, 10:1557-1575. doi:10.1038/s41551-026-01762-z (REAL-FM framework — Grundlage fuer _GROUNDING_SUFFIX/require_grounding und ai_label()/label_output unten: Kalibrierung/Unsicherheitsangabe sowie die KI-Kennzeichnungspflicht aus openspec/specs/ethics-enforcement/spec.md fehlten projektweit bis auf ein einzelnes Skript)

## Aufruf

```bash
from modules.llm import call_llm
response = call_llm(prompt, system="You are …")
import base64
b64 = base64.b64encode(Path("scan.jpg").read_bytes()).decode()
response = call_llm(prompt, image_b64=b64, image_mime="image/jpeg")
```
