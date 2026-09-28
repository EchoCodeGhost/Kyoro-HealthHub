#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# download-medgemma-hf.sh — Lädt MedGemma-27B im HuggingFace-Format herunter
#
# Konfiguration via Umgebungsvariablen:
#   HF_TOKEN    HuggingFace Access Token (Pflicht — Modell ist gated)
#   MODEL_DIR   Zielverzeichnis (Standard: ~/models/medgemma-27b-text-it)
#
# Beispiel:
#   HF_TOKEN=hf_xxx ./download-medgemma-hf.sh

set -euo pipefail

HF_REPO="google/medgemma-27b-text-it"
MODEL_DIR="${MODEL_DIR:-$HOME/models/medgemma-27b-text-it}"
HF_TOKEN="${HF_TOKEN:-}"

if [[ -z "$HF_TOKEN" ]]; then
  # Fallback: ~/.huggingface/token
  if [[ -f "$HOME/.huggingface/token" ]]; then
    HF_TOKEN="$(cat "$HOME/.huggingface/token")"
  else
    echo "FEHLER: HF_TOKEN nicht gesetzt und ~/.huggingface/token nicht gefunden."
    echo "Tipp: HF_TOKEN=hf_xxx $0"
    exit 1
  fi
fi

if [[ -d "$MODEL_DIR" && -f "$MODEL_DIR/config.json" ]]; then
  echo "==> Modell bereits vorhanden: $MODEL_DIR"
  echo "==> Zum Neudownload: rm -rf $MODEL_DIR"
  exit 0
fi

echo "==> Ziel:   $MODEL_DIR"
echo "==> Modell: $HF_REPO"
echo ""

mkdir -p "$MODEL_DIR"

if command -v huggingface-cli &>/dev/null; then
  huggingface-cli download "$HF_REPO" \
    --local-dir "$MODEL_DIR" \
    --token "$HF_TOKEN" \
    --exclude "*.gguf" "*.bin"
elif python3 -c "import huggingface_hub" &>/dev/null; then
  python3 - <<PYEOF
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="$HF_REPO",
    local_dir="$MODEL_DIR",
    token="$HF_TOKEN",
    ignore_patterns=["*.gguf", "*.bin"],
)
PYEOF
else
  echo "FEHLER: huggingface-cli oder huggingface_hub nicht gefunden."
  echo "Tipp: pip install huggingface_hub"
  exit 1
fi

echo ""
echo "==> Download abgeschlossen: $MODEL_DIR"
