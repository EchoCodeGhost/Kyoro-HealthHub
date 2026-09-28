#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
debug_page.py — Testlauf für einzelne PDF-Seite

@tier        infrastructure
@purpose.de  Testet die Tabellenextraktion für eine einzelne PDF-Seite mittels
             OpenVINO VLMPipeline oder LLM-Provider. Nützlich für Debugging und Entwicklung.
@purpose.en  Tests table extraction for a single PDF page using OpenVINO VLMPipeline
             or LLM provider. Useful for debugging and development.
@method.de   Extrahiere eine spezifizierte Seite aus einem PDF, konvertiert zu Bild und
             verarbeitet es durch die VLMPipeline. Unterstützt Sprach- und Provider-Auswahl.
@method.en   Extracts a specified page from a PDF, converts to image, and processes it
             through the VLMPipeline. Supports language and provider selection.
@reads       PDF-Dateien (z.B. medicine/krankenakte/*.pdf)
@writes      STDOUT (extrahierte Tabellen als Markdown)
@limits.de   Nur für eine Seite. Benötigt OpenVINO oder LLM-Provider.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Single page only. Requires OpenVINO or LLM provider.
@usage
    python medical/debug_page.py 1
    python medical/debug_page.py 5 --lang de --provider openvino
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t, set_lang

# --lang / --provider support without argparse (page number is positional)
_use_provider = "--provider" in sys.argv
if _use_provider:
    sys.argv.remove("--provider")

if "--lang" in sys.argv:
    idx = sys.argv.index("--lang")
    if idx + 1 < len(sys.argv):
        set_lang(sys.argv[idx + 1])
        sys.argv.pop(idx); sys.argv.pop(idx)

from pdf2image import convert_from_path
from medical.tables_llm import PROMPT, parse_tables_from_response, MAX_SIZE

PDF_PATH   = Path(__file__).parents[2] / "medicine" / "krankenakte" / "00_Auszug_Krankenakte.pdf"
MODEL_PATH = str(Path.home() / "models" / "qwen25vl-7b-genai")
SEITE      = int(sys.argv[1]) if len(sys.argv) > 1 else 1

pages = convert_from_path(str(PDF_PATH), dpi=150, first_page=SEITE, last_page=SEITE)
img = pages[0]
if max(img.size) > MAX_SIZE:
    img.thumbnail((MAX_SIZE, MAX_SIZE))
print(t(f"Bildgröße: {img.size}", f"Image size: {img.size}"))

if _use_provider:
    from utils.llm_provider import LLMProvider
    provider = LLMProvider.from_config()
    print(t(f"LLM-Provider: {provider.name}", f"LLM provider: {provider.name}"))
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    img.save(str(tmp_path), format="JPEG", quality=90)
    try:
        text = provider.vision(tmp_path, PROMPT, max_tokens=2048)
    finally:
        tmp_path.unlink(missing_ok=True)
else:
    import numpy as np
    import openvino as ov
    import openvino_genai as ov_genai
    print(t(f"Lade Modell: {MODEL_PATH} ...", f"Loading model: {MODEL_PATH} ..."))
    pipe = ov_genai.VLMPipeline(MODEL_PATH, "GPU")
    print(t("Modell geladen.\n", "Model loaded.\n"))
    rgb    = np.array(img.convert("RGB"))
    ov_img = ov.Tensor(rgb)
    config = ov_genai.GenerationConfig()
    config.temperature    = 0.0
    config.max_new_tokens = 2048
    result = pipe.generate(PROMPT, images=[ov_img], generation_config=config)
    text   = result.texts[0] if hasattr(result, "texts") else str(result)

print(t("\n--- ROHE ANTWORT ---", "\n--- RAW RESPONSE ---"))
print(text)

print(t("\n--- GEPARSTE TABELLEN ---", "\n--- PARSED TABLES ---"))
tables = parse_tables_from_response(text, SEITE)
for tbl in tables:
    print(f"\n{tbl['title']}:")
    print(tbl["df"].to_string())
if not tables:
    print(t("(keine)", "(none)"))
