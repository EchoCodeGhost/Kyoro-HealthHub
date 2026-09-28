#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# llama-server-start.sh — Startet llama-server auf dem Master-Node
#
# Konfiguration via Umgebungsvariablen:
#   MODEL      Pfad zur GGUF-Datei (Pflicht)
#   RPC_NODES  Kommagetrennte RPC-Worker, z.B. "10.0.0.10:50052,10.0.0.11:50052"
#   PORT       API-Port (Standard: 8080)
#   GPU_LAYERS GPU-Layer-Offload (Standard: 99 = alle)
#   CTX_SIZE   Kontextfenster in Tokens (Standard: 131072 — kein künstl. Limit)
#   PARALLEL   Parallele Slots (Standard: 2)
#
# Beispiele:
#   MODEL=~/.lmstudio/models/.../model.gguf ./llama-server-start.sh
#   MODEL=~/models/70b.gguf RPC_NODES="10.0.0.10:50052" ./llama-server-start.sh

set -euo pipefail

# ── Konfiguration ──────────────────────────────────────────────────────────
MODEL="${MODEL:-}"
RPC_NODES="${RPC_NODES:-}"
PORT="${PORT:-8080}"
GPU_LAYERS="${GPU_LAYERS:-99}"
CTX_SIZE="${CTX_SIZE:-131072}"
PARALLEL="${PARALLEL:-2}"
NPROC=$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4)

LLAMA_SERVER="${LLAMA_SERVER:-$HOME/llama.cpp/build/bin/llama-server}"

# ── Validierung ────────────────────────────────────────────────────────────
if [[ -z "$MODEL" ]]; then
  echo "FEHLER: MODEL nicht gesetzt."
  echo "Verwendung: MODEL=/pfad/zum/modell.gguf $0"
  exit 1
fi

if [[ ! -f "$MODEL" ]]; then
  echo "FEHLER: Modell nicht gefunden: $MODEL"
  exit 1
fi

if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "FEHLER: llama-server nicht gefunden: $LLAMA_SERVER"
  echo "Tipp: bash scripts/cluster/setup_rpc_node.sh"
  exit 1
fi

# ── Argumente zusammenbauen ────────────────────────────────────────────────
ARGS=(
  --host 0.0.0.0
  --port "$PORT"
  --model "$MODEL"
  --n-gpu-layers "$GPU_LAYERS"
  --threads "$NPROC"
  --ctx-size "$CTX_SIZE"
  --parallel "$PARALLEL"
)

if [[ -n "$RPC_NODES" ]]; then
  ARGS+=(--rpc "$RPC_NODES")
  echo "==> RPC-Nodes: $RPC_NODES"
fi

echo "==> Modell:    $MODEL"
echo "==> Port:      $PORT"
echo "==> Threads:   $NPROC"
echo "==> GPU-Layer: $GPU_LAYERS"
echo "==> Ctx-Size:  $CTX_SIZE"
echo "==> Parallel:  $PARALLEL"
echo ""

exec "$LLAMA_SERVER" "${ARGS[@]}" "$@"
