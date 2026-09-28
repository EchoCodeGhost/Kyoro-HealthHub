#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
utils/llm_provider.py — Unified LLM provider for all Kyoro-HealthHub scripts.

@tier        infrastructure
@purpose.de  Bietet eine vereinheitlichte Schnittstelle für verschiedene LLM-Anbieter
@purpose.en  Provides a unified interface for various LLM providers
@method.de   Unterstützt lokale (OpenVINO, MLX, Ollama) und Cloud-Anbieter (Anthropic, Mistral, OpenRouter, Azure). Automatische Erkennung und Konfiguration. Vision-Unterstützung für multimodale Modelle.
@method.en   Supports local (OpenVINO, MLX, Ollama) and cloud providers (Anthropic, Mistral, OpenRouter, Azure). Automatic detection and configuration. Vision support for multimodal models.
@limits.de   Performanz und Fähigkeiten variieren zwischen den Anbietern. Lokale Modelle erfordern Hardware-Ressourcen.

@relevance.de  Bietet Schnittstellen zu Sprachmodellen, essentiell für die KI-gestützte Datenanalyse
@relevance.en  Provides interfaces to language models, essential for AI-powered data analysis
@limits.en   Performance and capabilities vary between providers. Local models require hardware resources.

Supported providers (set "provider" under "llm" in ~/.config/kyoro/health_config.json):
  openvino     — local OpenVINO GenAI (LLMPipeline / VLMPipeline) [default]
  ovms         — OpenVINO Model Server  (OpenAI-compatible REST)
  ollama       — Ollama                 (OpenAI-compatible REST, local)
  lmstudio     — LM Studio             (OpenAI-compatible REST, local)
  mlx          — MLX / mlx-lm          (Apple Silicon, direct Python import)
  openrouter   — OpenRouter             (OpenAI-compatible REST)
  anthropic    — Anthropic Claude       (own API format)
  mistral      — Mistral AI             (OpenAI-compatible REST)
  perplexity   — Perplexity AI          (OpenAI-compatible REST, no vision)
  mammouth     — Mammouth / Scaleway AI Endpoints (OpenAI-compatible REST)
  huggingface  — HuggingFace Serverless Inference API (OpenAI-compatible REST)
  dr7ai        — dr7.ai                 (OpenAI-compatible REST)
  nvidia       — NVIDIA NIM             (OpenAI-compatible REST)
  azure        — Microsoft Azure OpenAI (own auth, deployment-based URL)
  exo          — exo cluster            (OpenAI-compatible REST, :52415)
  llamacpp     — llama.cpp server       (OpenAI-compatible REST, :8080)
  multi        — routes to multiple backends by system-prompt keywords

Minimal config examples:
  { "llm": { "provider": "anthropic",   "anthropic_api_key":   "sk-ant-..." } }
  { "llm": { "provider": "openrouter",  "openrouter_api_key":  "sk-or-..." } }
  { "llm": { "provider": "mistral",     "mistral_api_key":     "..." } }
  { "llm": { "provider": "perplexity",  "perplexity_api_key":  "..." } }
  { "llm": { "provider": "mammouth",    "mammouth_api_key":    "...", "mammouth_model": "llama-3.3-70b-instruct" } }
  { "llm": { "provider": "huggingface", "huggingface_api_key": "hf_...", "huggingface_model": "meta-llama/Llama-3.1-8B-Instruct" } }
  { "llm": { "provider": "dr7ai",       "dr7ai_api_key":       "...", "dr7ai_api_url": "https://api.dr7.ai/v1", "dr7ai_model": "dr7-llama-3.1-8b-instruct" } }
  { "llm": { "provider": "nvidia",      "nvidia_api_key":      "nvapi-...", "nvidia_model": "meta/llama-3.1-8b-instruct" } }
  { "llm": { "provider": "azure",       "azure_api_key": "...", "azure_endpoint": "https://RESOURCE.openai.azure.com", "azure_deployment": "gpt-4o" } }
  { "llm": { "provider": "ollama",      "ollama_model":        "qwen3:30b" } }
  { "llm": { "provider": "lmstudio",    "lmstudio_model":      "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF" } }
  { "llm": { "provider": "mlx",         "mlx_model":           "mlx-community/Qwen3-30B-A3B-4bit" } }
  { "llm": { "provider": "ovms",        "ovms_url": "http://localhost:8080/v1" } }
  { "llm": { "provider": "exo",         "exo_url": "http://192.168.x.x:52415/v1", "exo_model": "llama-3.2-3b" } }
  { "llm": { "provider": "llamacpp",    "llamacpp_url": "http://localhost:8080/v1", "llamacpp_model": "local-model" } }
  { "llm": { "provider": "multi",
             "multi_backends": {
               "default": { "provider": "llamacpp", "llamacpp_url": "http://localhost:8080/v1" },
               "specialized": { "provider": "llamacpp", "llamacpp_url": "http://localhost:8081/v1" }
             },
             "multi_routing": {
               "specialized": ["technical", "analysis", "report", "summary", "detailed", "expert", "data", "stats"]
             }
           }
  }

Backward-compatible: existing "anthropic_api_key" (top-level) and
"models.llm_path" / "models.llm_device" continue to work.

Vision support matrix:
  openvino     ✓  (requires openvino_vlm_path in config, or auto-guessed)
  ovms         ✓  (VLM-capable model required)
  ollama       ✓  (multimodal model required, e.g. llava / llama3.2-vision)
  lmstudio     ✓  (multimodal model required)
  mlx          ✓  (set mlx_vlm_model; requires mlx-vlm package)
  openrouter   ✓  (model-dependent)
  anthropic    ✓
  mistral      ✓  (Pixtral models)
  nvidia       ✓  (model-dependent)
  azure        ✓  (GPT-4o and GPT-4-vision deployments)
  exo          ✓  (multimodal model required, e.g. llama3.2-vision)
  llamacpp     ✓  (multimodal model required, e.g. llava)
  perplexity   ✗  (not supported)
  mammouth     ✗  (not supported)
  huggingface  ✗  (not supported)
  dr7ai        ✗  (not supported)

@reads       ~/.config/kyoro/health_config.json (Provider-Konfiguration)
@writes      Keine Tabellen (gibt LLM-Antworten zurueck)
@usage
    python llm_provider.py
    python llm_provider.py --help
"""

import base64
import json
import sys
import urllib.request
import urllib.error
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import KYORO_CONFIG_DIR


# ── Config ────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_raw() -> dict:
    p = KYORO_CONFIG_DIR / "health_config.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        import sys
        print(f"WARNING: {p} is not valid JSON: {e}", file=sys.stderr)
        return {}
    except OSError:
        return {}


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _http_post(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout or None) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:400]}") from e


def _openai_chat(base_url: str, api_key: str, model: str,
                 messages: list[dict], max_tokens: int | None,
                 temperature: float = 0.3, timeout: int = 120) -> str:
    payload: dict = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    resp = _http_post(
        f"{base_url.rstrip('/')}/chat/completions",
        payload,
        {"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    return resp["choices"][0]["message"]["content"].strip()


def _img_b64(image_path: Path) -> tuple[str, str]:
    b64 = base64.standard_b64encode(image_path.read_bytes()).decode()
    mime = {".png": "image/png", ".webp": "image/webp"}.get(
        image_path.suffix.lower(), "image/jpeg"
    )
    return b64, mime


# ── Base class ────────────────────────────────────────────────────────────────

class LLMProvider:
    """Unified interface to all supported LLM backends."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def is_local(self) -> bool:
        """True for providers running locally or on LAN."""
        return False

    @property
    def needs_max_tokens(self) -> bool:
        """True when the caller's max_tokens should be enforced.

        Single local models: True  — n_ctx is the hard limit; cap early.
        Multi / cluster:     False — cluster manages context itself.
        Cloud (non-Anthropic): False — API manages context.
        """
        return self.is_local  # default: local=cap, cloud=no cap

    def chat(self, system: str, user: str, max_tokens: int = 3000) -> str:
        """Public API — applies needs_max_tokens automatically before calling _chat()."""
        effective: int | None = max_tokens if self.needs_max_tokens else None
        return self._chat(system, user, max_tokens=effective)

    def _chat(self, system: str, user: str, max_tokens: int | None) -> str:
        raise NotImplementedError

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        raise NotImplementedError(f"Vision not supported by {self.name}")

    @staticmethod
    def from_config(raw: dict | None = None) -> "LLMProvider":
        if raw is None:
            raw = _load_raw()
        llm      = raw.get("llm", {})
        provider = llm.get("provider", "openvino").lower()
        if provider == "openvino":
            return _OpenVINOProvider(raw)
        if provider == "ovms":
            return _OVMSProvider(llm)
        if provider == "openrouter":
            return _OpenRouterProvider(llm)
        if provider == "anthropic":
            return _AnthropicProvider(raw)
        if provider == "mistral":
            return _MistralProvider(llm)
        if provider == "perplexity":
            return _PerplexityProvider(llm)
        if provider == "mammouth":
            return _MammouthProvider(llm)
        if provider == "huggingface":
            return _HuggingFaceProvider(llm)
        if provider == "dr7ai":
            return _Dr7AIProvider(llm)
        if provider == "nvidia":
            return _NvidiaProvider(llm)
        if provider == "azure":
            return _MicrosoftAzureProvider(llm)
        if provider == "ollama":
            return _OllamaProvider(llm)
        if provider == "lmstudio":
            return _LMStudioProvider(llm)
        if provider == "mlx":
            return _MLXProvider(llm)
        if provider == "exo":
            return _ExoProvider(llm)
        if provider in ("llamacpp", "llama.cpp", "llama_cpp"):
            return _LlamaCppProvider(llm)
        if provider == "multi":
            return _MultiProvider(llm)
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. "
            "Valid: openvino, ovms, ollama, lmstudio, mlx, openrouter, "
            "anthropic, mistral, perplexity, mammouth, huggingface, dr7ai, nvidia, azure, "
            "exo, llamacpp, multi"
        )


# ── dr7.ai ────────────────────────────────────────────────────────────────────────

_D7_BASE  = "https://api.dr7.ai/v1"
_D7_MODEL = "dr7-llama-3.1-8b-instruct"


class _Dr7AIProvider(LLMProvider):
    def __init__(self, llm: dict):
        self._key   = llm.get("dr7ai_api_key", "")
        self._model = llm.get("dr7ai_model", _D7_MODEL)
        self._url   = llm.get("dr7ai_api_url", _D7_BASE)

    @property
    def name(self) -> str:
        return f"dr7.ai ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(self._url, self._key, self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], None)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        raise NotImplementedError("dr7.ai does not support image/vision inputs")


# ── OpenVINO GenAI (local) ────────────────────────────────────────────────────

_OPENVINO_TEMPLATES = {
    "chatml":  "<|im_start|>system\n{sys}<|im_end|>\n<|im_start|>user\n{usr}<|im_end|>\n<|im_start|>assistant\n",
    "llama3":  "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n{sys}<|eot_id|><|start_header_id|>user<|end_header_id|>\n{usr}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n",
    "gemma":   "<start_of_turn>user\n{sys}\n\n{usr}<end_of_turn>\n<start_of_turn>model\n",
}


class _OpenVINOProvider(LLMProvider):
    is_local = True

    def __init__(self, raw: dict):
        models        = raw.get("models", {})
        llm           = raw.get("llm", {})
        self._path    = Path(
            llm.get("openvino_path") or
            models.get("llm_path", "/opt/voice-assistant/qwen3-30b-a3b-genai")
        )
        self._device  = (
            llm.get("openvino_device") or
            models.get("llm_device", "GPU")
        )
        default_vlm   = str(self._path).replace("-genai", "-vlm-genai")
        self._vlm_path      = Path(llm.get("openvino_vlm_path", default_vlm))
        self._template_key  = llm.get("openvino_template", "chatml")
        self._pipe_instance     = None
        self._vlm_pipe_instance = None

    @property
    def name(self) -> str:
        return f"OpenVINO ({self._path.name})"

    def _pipe_lazy(self):
        if self._pipe_instance is None:
            import openvino_genai as ov_genai
            self._pipe_instance = ov_genai.LLMPipeline(
                str(self._path), self._device
            )
        return self._pipe_instance

    def _vlm_lazy(self):
        if self._vlm_pipe_instance is None:
            import openvino_genai as ov_genai
            self._vlm_pipe_instance = ov_genai.VLMPipeline(
                str(self._vlm_path), self._device
            )
        return self._vlm_pipe_instance

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        import openvino_genai as ov_genai
        template = _OPENVINO_TEMPLATES.get(self._template_key, _OPENVINO_TEMPLATES["chatml"])
        prompt = template.format(sys=system, usr=user)
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens     = max_tokens
        cfg.temperature        = 0.3
        cfg.do_sample          = True
        cfg.repetition_penalty = 1.1
        return self._pipe_lazy().generate(prompt, cfg).strip()

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        import openvino_genai as ov_genai
        from PIL import Image
        pipe  = self._vlm_lazy()
        image = Image.open(str(image_path))
        cfg   = ov_genai.GenerationConfig()
        cfg.max_new_tokens = max_tokens
        return pipe.generate(prompt, image=image, generation_config=cfg).strip()


# ── OVMS (OpenAI-compatible REST) ─────────────────────────────────────────────

class _OVMSProvider(LLMProvider):
    is_local = True

    def __init__(self, llm: dict):
        self._base  = llm.get("ovms_url", "http://localhost:8080/v1")
        self._model = llm.get("ovms_model", "qwen3")

    @property
    def name(self) -> str:
        return f"OVMS ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(self._base, "EMPTY", self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], max_tokens)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        return _openai_chat(self._base, "EMPTY", self._model, [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], max_tokens)


# ── OpenRouter ────────────────────────────────────────────────────────────────

_OR_BASE  = "https://openrouter.ai/api/v1"
_OR_MODEL = "meta-llama/llama-3.1-8b-instruct:free"


class _OpenRouterProvider(LLMProvider):
    def __init__(self, llm: dict):
        self._key       = llm.get("openrouter_api_key", "")
        self._model     = llm.get("openrouter_model", _OR_MODEL)
        self._vlm_model = llm.get("openrouter_vlm_model", self._model)

    @property
    def name(self) -> str:
        return f"OpenRouter ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(_OR_BASE, self._key, self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], None)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        return _openai_chat(_OR_BASE, self._key, self._vlm_model, [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], None)


# ── Anthropic ─────────────────────────────────────────────────────────────────

_ANT_BASE          = "https://api.anthropic.com/v1"
_ANT_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class _AnthropicProvider(LLMProvider):
    def __init__(self, raw: dict):
        llm = raw.get("llm", {})
        self._key   = (
            llm.get("anthropic_api_key") or
            raw.get("anthropic_api_key", "")
        )
        self._model = llm.get("anthropic_model", _ANT_DEFAULT_MODEL)

    @property
    def name(self) -> str:
        return f"Anthropic ({self._model})"

    def _post(self, payload: dict) -> dict:
        return _http_post(f"{_ANT_BASE}/messages", payload, {
            "x-api-key":         self._key,
            "anthropic-version": "2023-06-01",
        })

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        resp = self._post({
            "model":      self._model,
            "max_tokens": 16000,
            "system":     system,
            "messages":   [{"role": "user", "content": user}],
        })
        return resp["content"][0]["text"].strip()

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        resp = self._post({
            "model":      self._model,
            "max_tokens": 16000,
            "messages":   [{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64",
                                "media_type": mime, "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        })
        return resp["content"][0]["text"].strip()


# ── Mistral AI ────────────────────────────────────────────────────────────────

_MST_BASE          = "https://api.mistral.ai/v1"
_MST_DEFAULT_MODEL = "mistral-small-latest"
_MST_VIS_MODEL     = "pixtral-12b-2409"


class _MistralProvider(LLMProvider):
    def __init__(self, llm: dict):
        self._key       = llm.get("mistral_api_key", "")
        self._model     = llm.get("mistral_model", _MST_DEFAULT_MODEL)
        self._vis_model = llm.get("mistral_vision_model", _MST_VIS_MODEL)

    @property
    def name(self) -> str:
        return f"Mistral ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(_MST_BASE, self._key, self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], None)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        return _openai_chat(_MST_BASE, self._key, self._vis_model, [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], None)


# ── Perplexity ────────────────────────────────────────────────────────────────

_PPX_BASE  = "https://api.perplexity.ai"
_PPX_MODEL = "sonar"


class _PerplexityProvider(LLMProvider):
    def __init__(self, llm: dict):
        self._key   = llm.get("perplexity_api_key", "")
        self._model = llm.get("perplexity_model", _PPX_MODEL)

    @property
    def name(self) -> str:
        return f"Perplexity ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(_PPX_BASE, self._key, self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], None)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        raise NotImplementedError("Perplexity does not support image/vision inputs")


# ── Mammouth / Scaleway AI Endpoints ─────────────────────────────────────────

_MAM_BASE  = "https://api.scaleway.ai/v1"
_MAM_MODEL = "llama-3.3-70b-instruct"


class _MammouthProvider(LLMProvider):
    def __init__(self, llm: dict):
        self._key   = llm.get("mammouth_api_key", "")
        self._model = llm.get("mammouth_model", _MAM_MODEL)

    @property
    def name(self) -> str:
        return f"Mammouth ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(_MAM_BASE, self._key, self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], None)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        raise NotImplementedError("Mammouth does not support image/vision inputs")


# ── HuggingFace Serverless Inference API ──────────────────────────────────────

_HF_BASE  = "https://api-inference.huggingface.co/v1"
_HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


class _HuggingFaceProvider(LLMProvider):
    def __init__(self, llm: dict):
        self._key   = llm.get("huggingface_api_key", "")
        self._model = llm.get("huggingface_model", _HF_MODEL)

    @property
    def name(self) -> str:
        return f"HuggingFace ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(_HF_BASE, self._key, self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], None)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        raise NotImplementedError("HuggingFace Serverless does not support image/vision inputs")


# ── NVIDIA NIM ────────────────────────────────────────────────────────────────

_NIM_BASE  = "https://integrate.api.nvidia.com/v1"
_NIM_MODEL = "meta/llama-3.1-8b-instruct"


class _NvidiaProvider(LLMProvider):
    def __init__(self, llm: dict):
        self._key   = llm.get("nvidia_api_key", "")
        self._model = llm.get("nvidia_model", _NIM_MODEL)

    @property
    def name(self) -> str:
        return f"NVIDIA NIM ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(_NIM_BASE, self._key, self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], None)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        return _openai_chat(_NIM_BASE, self._key, self._model, [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], None)


# ── Microsoft Azure OpenAI ────────────────────────────────────────────────────

_AZ_API_VERSION = "2024-02-01"


class _MicrosoftAzureProvider(LLMProvider):
    def __init__(self, llm: dict):
        self._key         = llm.get("azure_api_key", "")
        self._endpoint    = llm.get("azure_endpoint", "").rstrip("/")
        self._deployment  = llm.get("azure_deployment", "gpt-4o")
        self._api_version = llm.get("azure_api_version", _AZ_API_VERSION)

    @property
    def name(self) -> str:
        return f"Azure OpenAI ({self._deployment})"

    def _url(self) -> str:
        return (
            f"{self._endpoint}/openai/deployments/{self._deployment}"
            f"/chat/completions?api-version={self._api_version}"
        )

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        resp = _http_post(self._url(), {
            "messages":    [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": 0.3,
        }, {"api-key": self._key})
        return resp["choices"][0]["message"]["content"].strip()

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        resp = _http_post(self._url(), {
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            "temperature": 0.3,
        }, {"api-key": self._key})
        return resp["choices"][0]["message"]["content"].strip()


# ── Ollama (local) ────────────────────────────────────────────────────────────

_OLLAMA_BASE  = "http://localhost:11434/v1"
_OLLAMA_MODEL = "qwen3:30b"


class _OllamaProvider(LLMProvider):
    is_local = True

    def __init__(self, llm: dict):
        self._base  = llm.get("ollama_url", _OLLAMA_BASE)
        self._model = llm.get("ollama_model", _OLLAMA_MODEL)

    @property
    def name(self) -> str:
        return f"Ollama ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(self._base, "ollama", self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], max_tokens)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        return _openai_chat(self._base, "ollama", self._model, [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], max_tokens)


# ── LM Studio (local) ─────────────────────────────────────────────────────────

_LMS_BASE  = "http://localhost:1234/v1"
_LMS_MODEL = "local-model"


class _LMStudioProvider(LLMProvider):
    is_local = True

    def __init__(self, llm: dict):
        self._base    = llm.get("lmstudio_url", _LMS_BASE)
        self._model   = llm.get("lmstudio_model", _LMS_MODEL)
        self._timeout = int(llm.get("timeout", 600))

    @property
    def name(self) -> str:
        return f"LM Studio ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(self._base, "lm-studio", self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], max_tokens, timeout=self._timeout)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        return _openai_chat(self._base, "lm-studio", self._model, [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], max_tokens, timeout=self._timeout)


# ── exo cluster (local / LAN, OpenAI-compatible) ─────────────────────────────

_EXO_BASE  = "http://localhost:52415/v1"
_EXO_MODEL = "llama-3.2-3b"


class _ExoProvider(LLMProvider):
    is_local = True

    def __init__(self, llm: dict):
        self._base  = llm.get("exo_url", _EXO_BASE)
        self._model = llm.get("exo_model", _EXO_MODEL)

    @property
    def name(self) -> str:
        return f"exo ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(self._base, "exo", self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], max_tokens)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        return _openai_chat(self._base, "exo", self._model, [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], max_tokens)


# ── llama.cpp server (local / LAN, OpenAI-compatible) ────────────────────────

_LLAMACPP_BASE  = "http://localhost:8080/v1"
_LLAMACPP_MODEL = "local-model"


class _LlamaCppProvider(LLMProvider):
    is_local = True

    def __init__(self, llm: dict):
        self._base    = llm.get("llamacpp_url", _LLAMACPP_BASE)
        self._model   = llm.get("llamacpp_model", _LLAMACPP_MODEL)
        self._timeout = int(llm.get("timeout", 120))

    @property
    def name(self) -> str:
        return f"llama.cpp ({self._model})"

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return _openai_chat(self._base, "llamacpp", self._model, [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], max_tokens, timeout=self._timeout)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        b64, mime = _img_b64(image_path)
        return _openai_chat(self._base, "llamacpp", self._model, [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], max_tokens, timeout=self._timeout)


# ── MLX / mlx-lm (Apple Silicon, local) ──────────────────────────────────────

_MLX_MODEL = "mlx-community/Qwen3-30B-A3B-4bit"


class _MLXProvider(LLMProvider):
    is_local = True

    def __init__(self, llm: dict):
        self._model_id  = llm.get("mlx_model", _MLX_MODEL)
        self._vlm_id    = llm.get("mlx_vlm_model", "")
        self._model     = None
        self._tokenizer = None
        self._vlm_model = None
        self._vlm_proc  = None

    @property
    def name(self) -> str:
        return f"MLX ({self._model_id})"

    def _load_lazy(self):
        if self._model is None:
            from mlx_lm import load
            self._model, self._tokenizer = load(self._model_id)
        return self._model, self._tokenizer

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        from mlx_lm import generate
        model, tokenizer = self._load_lazy()
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return generate(model, tokenizer, prompt=prompt,
                        max_tokens=max_tokens, verbose=False).strip()

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        if not self._vlm_id:
            raise NotImplementedError(
                "Set mlx_vlm_model in config to use vision "
                "(e.g. mlx-community/llava-1.5-7b-4bit). "
                "Requires: pip install mlx-vlm"
            )
        if self._vlm_model is None:
            from mlx_vlm import load
            self._vlm_model, self._vlm_proc = load(self._vlm_id)
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config
        config = load_config(self._vlm_id)
        formatted = apply_chat_template(
            self._vlm_proc, config, prompt, num_images=1
        )
        return generate(
            self._vlm_model, self._vlm_proc,
            str(image_path), formatted, max_tokens=max_tokens
        ).strip()


# ── Multi-Provider (keyword-based routing) ────────────────────────────────────

class _MultiProvider(LLMProvider):
    """Routes requests to different backends based on keywords in the system prompt.

    Config:
      "multi_backends": dict of named provider configs, must include "default".
      "multi_routing":  dict mapping backend names to keyword lists checked
                        against the system prompt (case-insensitive, first match wins).

    Falls back to "default" when no keyword matches or a routed backend fails.
    Nesting multi inside multi is not supported.
    """

    def __init__(self, llm: dict):
        self._backends_cfg: dict[str, dict] = llm.get("multi_backends", {})
        self._routing: dict[str, list[str]] = llm.get("multi_routing", {})
        self._instances: dict[str, LLMProvider] = {}
        if "default" not in self._backends_cfg:
            raise ValueError(
                "multi provider requires a 'default' entry in multi_backends"
            )
        for name, cfg in self._backends_cfg.items():
            if cfg.get("provider", "").lower() == "multi":
                raise ValueError(f"multi_backends['{name}'] cannot itself be 'multi'")

    @property
    def name(self) -> str:
        return f"Multi ({', '.join(self._backends_cfg)})"

    @property
    def is_local(self) -> bool:
        return self._build("default").is_local

    @property
    def needs_max_tokens(self) -> bool:
        # Informational only — chat() below makes the real, per-backend
        # decision, since which backend gets selected (and therefore whether
        # it needs a cap) depends on `system`, which isn't known yet here.
        return self._build("default").needs_max_tokens

    def _build(self, name: str) -> "LLMProvider":
        if name not in self._instances:
            self._instances[name] = LLMProvider.from_config(
                {"llm": self._backends_cfg[name]}
            )
        return self._instances[name]

    def _select(self, system: str) -> tuple[str, "LLMProvider"]:
        text = system.lower()
        for backend_name, keywords in self._routing.items():
            if backend_name not in self._backends_cfg:
                continue
            if any(kw.lower() in text for kw in keywords):
                return backend_name, self._build(backend_name)
        return "default", self._build("default")

    def chat(self, system: str, user: str, max_tokens: int = 3000) -> str:
        """Override the base class: whether a cap applies depends on which
        backend gets selected, which itself depends on `system` — the base
        class's chat()/needs_max_tokens combo decides this too early to know
        that. Previously every multi-routed call disabled the cap
        unconditionally, which let a local (non-clustered) backend's reply
        run away with no limit when it got stuck in a repetition loop —
        found dogfooding the anamnesis interview against a local MedGemma
        server: one turn ran past 3700+ tokens with no end in sight."""
        name, backend = self._select(system)
        effective = max_tokens if backend.needs_max_tokens else None
        try:
            return backend._chat(system, user, max_tokens=effective)
        except Exception as primary_exc:
            if name != "default":
                try:
                    default_backend = self._build("default")
                    default_effective = max_tokens if default_backend.needs_max_tokens else None
                    return default_backend._chat(system, user, max_tokens=default_effective)
                except Exception as fallback_exc:
                    # Every caller in this project already wraps .chat() in
                    # try/except and shows the error (e.g. "LLM nicht
                    # verfügbar: {e}") — silently returning "" instead hid
                    # real failures (a dropped connection, a context-window
                    # overflow, ...) as a blank, seemingly-successful reply
                    # with no explanation. Found dogfooding the anamnesis
                    # interview: three turns went silently blank when the
                    # server was killed mid-request during a benchmark.
                    raise RuntimeError(
                        f"Multi-provider: '{name}' backend failed ({primary_exc}), "
                        f"and 'default' fallback also failed ({fallback_exc})"
                    ) from fallback_exc
            else:
                raise RuntimeError(
                    f"Multi-provider: 'default' backend failed: {primary_exc}"
                ) from primary_exc

    def _chat(self, system: str, user: str, max_tokens: int | None = None) -> str:
        # chat() above is the real entry point for this class (it needs the
        # selected backend to decide on a cap); kept for interface
        # completeness, honors whatever max_tokens it's explicitly given.
        _, backend = self._select(system)
        return backend._chat(system, user, max_tokens=max_tokens)

    def vision(self, image_path: Path, prompt: str, max_tokens: int = 400) -> str:
        return self._build("default").vision(image_path, prompt, max_tokens)


# ── Public helper ────────────────────────────────────────────────────────────

def llm_chat(provider: LLMProvider, system: str, user: str,
             max_tokens: int = 3000) -> str:
    """Thin wrapper around provider.chat(). Token-cap logic is in chat() itself."""
    return provider.chat(system, user, max_tokens=max_tokens)


# ── CLI (self-test / provider info) ──────────────────────────────────────────

if __name__ == "__main__":
    raw = _load_raw()
    try:
        p = LLMProvider.from_config(raw)
        print(f"Active provider: {p.name}")
        reply = p.chat("You are a helpful assistant.", "Say hello in one word.", max_tokens=10)
        print(f"Response: {reply}")
    except Exception as e:
        print(f"Error: {e}")
