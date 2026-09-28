#!/usr/bin/env bash
# llama.cpp RPC-Node Startskript für macOS (Apple Silicon)
#
# caffeinate verhindert System-Sleep solange der RPC-Server läuft.
# Deployment (vom Master-Node aus):
#   scp cluster/rpc-node-mac.sh <user>@<node-ip>:~/
#   chmod +x ~/rpc-node-mac.sh
#   ssh <user>@<node-ip> '~/rpc-node-mac.sh'

LLAMA_RPC="${LLAMA_RPC:-$HOME/llama.cpp/build/bin/llama-rpc-server}"
PORT="${PORT:-50052}"

if [[ ! -x "$LLAMA_RPC" ]]; then
  echo "Fehler: llama-rpc-server nicht gefunden: $LLAMA_RPC" >&2
  echo "Überschreiben mit: LLAMA_RPC=/pfad/llama-rpc-server $0" >&2
  exit 1
fi

# Nur Metal-Backend anbieten — verhindert, dass der CPU-Backend als zweites
# RPC-Device (0 GB) gemeldet wird und im tensor-split einen Slot belegt.
# Fallback falls --dev nicht unterstützt: GGML_NO_CPU=1 vor dem Aufruf setzen.
DEV="${DEV:-metal}"

echo "==> RPC-Node (macOS) | Port $PORT | $(hostname)"
echo "==> Binary: $LLAMA_RPC"
echo "==> Device: $DEV"
echo "==> caffeinate aktiv — System schläft nicht ein"

exec caffeinate -i "$LLAMA_RPC" --host 0.0.0.0 --port "$PORT" --dev "$DEV"
