#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# exo-start.sh — Startet exo auf diesem Node
#
# Verwendung:
#   ./exo-start.sh                    # Inference-Node (macOS/MLX)
#   ./exo-start.sh --no-worker        # Coordinator only (Linux, kein MLX)
#   ./exo-start.sh --no-worker --verbose
#
# Hinweise:
#   - macOS (Apple Silicon): MLX-Inference, voller Node
#   - Linux: kein MLX → --no-worker verwenden, dieser Node als Coordinator/API-Gateway
#   - Discovery via IPv6-Multicast (ff12::e0a1:de89, UDP 52413)
#   - API-Port: 52415 (OpenAI-kompatibel)
#   - Zenoh-Port: 52414

set -euo pipefail

# ── exo-Binary finden ──────────────────────────────────────────────────────
if [[ -x "$HOME/exo-venv/bin/exo" ]]; then
  EXO="$HOME/exo-venv/bin/exo"
elif command -v exo &>/dev/null; then
  EXO="$(command -v exo)"
else
  echo "FEHLER: exo nicht gefunden."
  echo "Installation: pip install exo  oder  pip install exo --target ~/exo-venv/"
  exit 1
fi

# ── Cargo/NVM laden falls vorhanden ───────────────────────────────────────
[[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
[[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]] && source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"

echo "==> exo starten: $EXO $*"
exec "$EXO" "$@"
