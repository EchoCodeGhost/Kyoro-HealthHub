#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# ovms-medgemma.sh — Startet MedGemma-27B via OpenVINO Model Server (Docker)
#
# Konfiguration via Umgebungsvariablen:
#   MODEL_DIR     Pfad zum HF-Modell (Standard: ~/models/medgemma-27b-text-it)
#   PORT          REST-Port (Standard: 8081)
#   TARGET_DEVICE OpenVINO-Gerät: GPU, CPU, AUTO (Standard: GPU)
#   CONTAINER     Docker-Container-Name (Standard: ovms-medgemma)
#
# Voraussetzung: HF-Format unter MODEL_DIR — einmalig laden mit:
#   HF_TOKEN=hf_xxx ./download-medgemma-hf.sh
#
# Endpoint nach Start: http://localhost:8081/v3/chat/completions

set -euo pipefail

MODEL_DIR="${MODEL_DIR:-$HOME/models/medgemma-27b-text-it}"
PORT="${PORT:-8081}"
TARGET_DEVICE="${TARGET_DEVICE:-GPU}"
CONTAINER="${CONTAINER:-ovms-medgemma}"
RENDER_GID="${RENDER_GID:-$(stat -c '%g' /dev/dri/renderD128 2>/dev/null || echo 992)}"

# ── Validierung ────────────────────────────────────────────────────────────
if [[ ! -f "$MODEL_DIR/config.json" ]]; then
  echo "FEHLER: Kein HF-Modell gefunden: $MODEL_DIR"
  echo "Tipp: HF_TOKEN=hf_xxx ./download-medgemma-hf.sh"
  exit 1
fi

if ! command -v docker &>/dev/null; then
  echo "FEHLER: Docker nicht gefunden."
  exit 1
fi

# ── Alten Container entfernen wenn vorhanden ───────────────────────────────
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "==> Stoppe bestehenden Container: $CONTAINER"
  docker rm -f "$CONTAINER"
fi

echo "==> Modell:  $MODEL_DIR"
echo "==> Port:    $PORT"
echo "==> Device:  $TARGET_DEVICE"
echo ""

docker run -d \
  --name "$CONTAINER" \
  --device /dev/dri/renderD128 \
  --group-add "$RENDER_GID" \
  -p "${PORT}:${PORT}" \
  -v "$MODEL_DIR:/model:ro" \
  openvino/model_server:latest \
  --model_name medgemma \
  --source_model /model \
  --task text_generation \
  --rest_port "$PORT" \
  --target_device "$TARGET_DEVICE"

echo ""
echo "==> Container gestartet: $CONTAINER"
echo "==> Endpoint: http://localhost:${PORT}/v3/chat/completions"
echo "==> Logs:     docker logs -f $CONTAINER"
