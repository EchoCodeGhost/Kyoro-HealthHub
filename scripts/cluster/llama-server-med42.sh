#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# llama-server-med42.sh — Startet Llama3-Med42-70B auf dem Master-Node
#
# Konfiguration via Umgebungsvariablen oder scripts/cluster/cluster.env:
#   MODEL          Pfad zur GGUF-Datei
#   RPC_NODES      Kommagetrennte RPC-Worker, z.B. "10.0.0.1:50052,10.0.0.2:50052"
#   TENSOR_SPLIT   Layer-Verhältnis Arc,CPU,Node1,Node2,... (Standard: 8,4,1,4)
#   PORT           API-Port (Standard: 8080)
#   CTX_SIZE       Kontextfenster in Tokens (Standard: 131072 — kein künstl. Limit)
#   PARALLEL       Parallele Slots (Standard: 2 — Balance zwischen Parallelität und Ctx pro Slot)
#
# --tensor-split Reihenfolge: Arc, CPU, RPC-Node1, RPC-Node2, ...
#   Node mit Vulkan-Instabilität: konservativen Wert (1) wählen (~3 GB)
#   Node nebenbei genutzt:        moderaten Wert (4) wählen (~9 GB)
#
# Beispiele:
#   ./llama-server-med42.sh                    # mit Werten aus cluster.env
#   RPC_NODES="" ./llama-server-med42.sh       # nur lokale GPU
#   TENSOR_SPLIT="8,4,2,4" ./llama-server-med42.sh

set -euo pipefail

# ── Cluster-Konfiguration laden (nicht im Repo) ────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/cluster.env" ]]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/cluster.env"
fi

# ── Konfiguration ──────────────────────────────────────────────────────────
MODEL="${MODEL:-}"
RPC_NODES="${RPC_NODES-}"
TENSOR_SPLIT="${TENSOR_SPLIT:-8,4,1,4}"
PORT="${PORT:-8080}"
CTX_SIZE="${CTX_SIZE:-131072}"
PARALLEL="${PARALLEL:-2}"
NPROC=$(nproc 2>/dev/null || echo 4)
LLAMA_SERVER="${LLAMA_SERVER:-$HOME/llama.cpp/build/bin/llama-server}"

# ── Validierung ────────────────────────────────────────────────────────────
if [[ -z "$MODEL" ]]; then
  echo "FEHLER: MODEL nicht gesetzt."
  echo "Tipp: MODEL=/pfad/Llama3-Med42-70B.Q4_K_M.gguf $0"
  echo "      oder MODEL in scripts/cluster/cluster.env setzen"
  exit 1
fi

if [[ ! -f "$MODEL" ]]; then
  echo "FEHLER: Modell nicht gefunden: $MODEL"
  exit 1
fi

if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "FEHLER: llama-server nicht gefunden: $LLAMA_SERVER"
  exit 1
fi

# ── Argumente zusammenbauen ────────────────────────────────────────────────
ARGS=(
  --host 0.0.0.0
  --port "$PORT"
  --model "$MODEL"
  --n-gpu-layers 99
  -fit off
  --no-warmup
  --threads "$NPROC"
  --tensor-split "$TENSOR_SPLIT"
  --ctx-size "$CTX_SIZE"
  --parallel "$PARALLEL"
)

if [[ -n "$RPC_NODES" ]]; then
  ARGS+=(--rpc "$RPC_NODES")
  echo "==> RPC-Nodes:    $RPC_NODES"
fi

echo "==> Modell:       $MODEL"
echo "==> Port:         $PORT"
echo "==> Tensor-Split: $TENSOR_SPLIT"
echo "==> Ctx-Size:     $CTX_SIZE"
echo "==> Parallel:     $PARALLEL"
echo ""

exec "$LLAMA_SERVER" "${ARGS[@]}" "$@"
