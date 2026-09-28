#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# setup_rpc_node.sh — Richtet einen llama.cpp RPC-Node ein
#
# Verwendung:
#   bash setup_rpc_node.sh [--port PORT] [--rpc-only] [--server-host HOST]
#
# Optionen:
#   --port PORT          RPC-Port (Standard: 50052)
#   --rpc-only           Nur rpc-server bauen, kein llama-server (für Worker-Nodes)
#   --server-host HOST   Nur für Master-Node: Hosts der Worker, z.B. "10.0.0.10,10.0.0.11"
#
# Unterstützte Plattformen:
#   - Linux x86_64       CPU-only Build (apt-basiert)
#   - Linux x86_64       Vulkan-Build wenn --vulkan übergeben
#   - macOS arm64        Metal-Build (Apple Silicon)
#
# Beispiele:
#   # Worker-Node:
#   bash setup_rpc_node.sh --rpc-only
#
#   # Master-Node mit allen Workern:
#   bash setup_rpc_node.sh --server-host "10.0.0.10:50052,10.0.0.11:50052,10.0.0.12:50052"

set -euo pipefail

# ── Argumente ──────────────────────────────────────────────────────────────
RPC_PORT=50052
RPC_ONLY=false
SERVER_HOST=""
USE_VULKAN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --port)       RPC_PORT="$2"; shift 2 ;;
    --rpc-only)   RPC_ONLY=true; shift ;;
    --server-host) SERVER_HOST="$2"; shift 2 ;;
    --vulkan)     USE_VULKAN=true; shift ;;
    *) echo "Unbekannte Option: $1"; exit 1 ;;
  esac
done

# ── Plattform erkennen ─────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
INSTALL_DIR="$HOME/llama.cpp"
BUILD_DIR="$INSTALL_DIR/build"

echo "==> Plattform: $OS / $ARCH"
echo "==> Zielverzeichnis: $INSTALL_DIR"
echo "==> RPC-Port: $RPC_PORT"

# ── Abhängigkeiten installieren ────────────────────────────────────────────
install_deps_linux() {
  echo "==> Installiere Build-Abhängigkeiten (apt)..."
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends \
    git cmake build-essential pkg-config \
    libcurl4-openssl-dev ca-certificates

  if $USE_VULKAN; then
    echo "==> Installiere Vulkan-Abhängigkeiten..."
    sudo apt-get install -y --no-install-recommends \
      libvulkan-dev mesa-vulkan-drivers glslang-tools spirv-tools
  fi
}

install_deps_macos() {
  echo "==> Prüfe macOS-Abhängigkeiten..."
  if ! command -v cmake &>/dev/null; then
    if command -v brew &>/dev/null; then
      brew install cmake
    else
      echo "FEHLER: cmake nicht gefunden. Bitte Homebrew installieren: https://brew.sh"
      exit 1
    fi
  fi
  if ! xcode-select -p &>/dev/null; then
    echo "FEHLER: Xcode Command Line Tools fehlen. Bitte ausführen: xcode-select --install"
    exit 1
  fi
}

case "$OS" in
  Linux)  install_deps_linux ;;
  Darwin) install_deps_macos ;;
  *)      echo "FEHLER: Nicht unterstütztes Betriebssystem: $OS"; exit 1 ;;
esac

# ── llama.cpp klonen oder aktualisieren ────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "==> Aktualisiere llama.cpp..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "==> Klone llama.cpp..."
  git clone https://github.com/ggml-org/llama.cpp "$INSTALL_DIR"
fi

# ── CMake-Flags je Plattform ───────────────────────────────────────────────
CMAKE_FLAGS=(
  "-DCMAKE_BUILD_TYPE=Release"
  "-DGGML_RPC=ON"
  "-DLLAMA_CURL=ON"
)

case "$OS" in
  Darwin)
    CMAKE_FLAGS+=("-DGGML_METAL=ON")
    echo "==> Build: Metal (Apple Silicon)"
    ;;
  Linux)
    if $USE_VULKAN; then
      CMAKE_FLAGS+=("-DGGML_VULKAN=ON")
      echo "==> Build: Vulkan (Linux GPU)"
    else
      echo "==> Build: CPU-only (Linux)"
    fi
    ;;
esac

# ── Bauen ──────────────────────────────────────────────────────────────────
NPROC=$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4)
echo "==> Baue llama.cpp mit $NPROC Threads..."
echo "==> CMake-Flags: ${CMAKE_FLAGS[*]}"

# Build-Verzeichnis leeren damit cmake-Cache keine Flags überschreibt
rm -rf "$BUILD_DIR"

cmake -S "$INSTALL_DIR" -B "$BUILD_DIR" "${CMAKE_FLAGS[@]}"
cmake --build "$BUILD_DIR" --config Release -j"$NPROC"

echo "==> Build abgeschlossen."

# ── Start-Scripts erstellen ────────────────────────────────────────────────
RPC_BIN="$BUILD_DIR/bin/rpc-server"
SERVER_BIN="$BUILD_DIR/bin/llama-server"
RPC_START="$HOME/llama-rpc-start.sh"
SERVER_START="$HOME/llama-server-start.sh"

# RPC-Server Script (für alle Nodes)
cat > "$RPC_START" << EOF
#!/usr/bin/env bash
# Startet den llama.cpp RPC-Server auf diesem Node.
exec "$RPC_BIN" --host 0.0.0.0 --port $RPC_PORT "\$@"
EOF
chmod +x "$RPC_START"
echo "==> RPC-Start-Script: $RPC_START"

# llama-server Script (nur Master-Node)
if ! $RPC_ONLY; then
  RPC_ARGS=""
  if [[ -n "$SERVER_HOST" ]]; then
    RPC_ARGS="--rpc $SERVER_HOST"
  fi

  cat > "$SERVER_START" << EOF
#!/usr/bin/env bash
# Startet llama-server auf dem Master-Node.
# Modell via MODEL= überschreibbar: MODEL=/pfad/zum/modell.gguf $SERVER_START
MODEL="\${MODEL:-}"
if [[ -z "\$MODEL" ]]; then
  echo "FEHLER: MODEL-Pfad nicht gesetzt."
  echo "Verwendung: MODEL=/pfad/zum/modell.gguf $SERVER_START"
  exit 1
fi

NPROC=\$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4)

exec "$SERVER_BIN" \\
  --host 0.0.0.0 \\
  --port 8080 \\
  --model "\$MODEL" \\
  --n-gpu-layers 99 \\
  --threads "\$NPROC" \\
  $RPC_ARGS \\
  "\$@"
EOF
  chmod +x "$SERVER_START"
  echo "==> Server-Start-Script: $SERVER_START"
fi

# ── Zusammenfassung ────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo " Setup abgeschlossen auf $(hostname) ($OS/$ARCH)"
echo "══════════════════════════════════════════════════"
echo ""
echo " Binaries:"
echo "   RPC-Server : $RPC_BIN"
[[ -f "$SERVER_BIN" ]] && echo "   LLM-Server : $SERVER_BIN"
echo ""
echo " Nächste Schritte:"
echo ""
if $RPC_ONLY; then
  echo "  1. RPC-Server starten:"
  echo "     $RPC_START"
  echo ""
  echo "  2. IP dieser Maschine notieren:"
  ip -4 addr show scope global 2>/dev/null | awk '/inet/{print "     " $2}' \
    || ifconfig 2>/dev/null | awk '/inet /{print "     " $2}'
  echo ""
  echo "  3. Auf dem Master-Node llama-server mit --rpc <diese-IP>:$RPC_PORT starten"
else
  echo "  1. RPC-Nodes zuerst starten"
  echo "  2. Dann llama-server starten:"
  echo "     MODEL=/pfad/zum/modell.gguf $SERVER_START"
fi
echo ""
