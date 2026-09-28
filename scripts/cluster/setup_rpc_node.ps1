#!/usr/bin/env pwsh
# SPDX-License-Identifier: GPL-3.0-or-later
#
# setup_rpc_node.ps1 — Richtet einen llama.cpp RPC-Node unter Windows ein
#
# Verwendung (PowerShell als Admin):
#   .\setup_rpc_node.ps1                   # Vulkan-Build (Standard fuer Windows)
#   .\setup_rpc_node.ps1 -Port 50052       # Anderer Port
#   .\setup_rpc_node.ps1 -CpuOnly         # CPU-only Build (falls kein Vulkan)
#
# Voraussetzungen:
#   - Windows 10/11 x64
#   - AMD/Intel/NVIDIA GPU mit Vulkan-Treiber (Standard-Treiber reichen)
#   - PowerShell 5.1+ oder PowerShell 7+
#   - Internetzugang fuer den Download

param(
    [int]$Port = 50052,
    [switch]$CpuOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$InstallDir = "$env:USERPROFILE\llama.cpp"
$StartScript = "$env:USERPROFILE\llama-rpc-start.bat"

Write-Host "==> llama.cpp RPC-Node Setup fuer Windows" -ForegroundColor Cyan
Write-Host "==> Zielverzeichnis: $InstallDir"
Write-Host "==> RPC-Port: $Port"

# ── Neueste Version ermitteln ─────────────────────────────────────────────────
Write-Host "==> Suche neueste llama.cpp-Version..."
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest" -TimeoutSec 30
} catch {
    Write-Error "GitHub-API nicht erreichbar: $_"
    exit 1
}

$version = $release.tag_name
Write-Host "==> Gefunden: $version"

# ── Passendes Asset auswaehlen ────────────────────────────────────────────────
if ($CpuOnly) {
    $pattern = "llama-$version-bin-win-avx2-x64.zip"
    Write-Host "==> Build: CPU-only (AVX2)"
} else {
    $pattern = "llama-$version-bin-win-vulkan-x64.zip"
    Write-Host "==> Build: Vulkan (GPU)"
}

$asset = $release.assets | Where-Object { $_.name -eq $pattern } | Select-Object -First 1

if (-not $asset) {
    # Fallback: flexibler Match
    if ($CpuOnly) {
        $asset = $release.assets | Where-Object { $_.name -match "win.*avx2.*x64" } | Select-Object -First 1
    } else {
        $asset = $release.assets | Where-Object { $_.name -match "win.*vulkan.*x64" } | Select-Object -First 1
    }
}

if (-not $asset) {
    Write-Error "Kein passendes Asset fuer '$pattern' in Release $version gefunden."
    Write-Host "Verfuegbare Assets:" -ForegroundColor Yellow
    $release.assets | ForEach-Object { Write-Host "  $($_.name)" }
    exit 1
}

Write-Host "==> Download: $($asset.name) ($([math]::Round($asset.size/1MB, 1)) MB)"

# ── Herunterladen ─────────────────────────────────────────────────────────────
$zipPath = "$env:TEMP\llama-cpp-windows.zip"
Write-Host "==> Lade herunter..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing

# ── Entpacken ─────────────────────────────────────────────────────────────────
Write-Host "==> Entpacke nach $InstallDir ..."
if (Test-Path $InstallDir) {
    Remove-Item -Path $InstallDir -Recurse -Force
}
Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
Remove-Item $zipPath

# Binary-Pfad finden (manchmal in Unterverzeichnis)
$rpcBin = Get-ChildItem -Path $InstallDir -Recurse -Filter "rpc-server.exe" |
          Select-Object -First 1

if (-not $rpcBin) {
    Write-Error "rpc-server.exe nicht in $InstallDir gefunden."
    exit 1
}

$BinDir = $rpcBin.DirectoryName
Write-Host "==> Binary: $($rpcBin.FullName)"

# ── Start-Batch-Script erstellen ──────────────────────────────────────────────
$startContent = @"
@echo off
REM Startet den llama.cpp RPC-Server auf diesem Node.
REM Port: $Port
"$($rpcBin.FullName)" --host 0.0.0.0 --port $Port %*
"@
Set-Content -Path $StartScript -Value $startContent -Encoding ASCII
Write-Host "==> Start-Script: $StartScript"

# ── Windows-Firewall-Regel setzen ─────────────────────────────────────────────
Write-Host "==> Firewall-Regel fuer Port $Port (TCP eingehend)..."
try {
    $ruleName = "llama.cpp RPC Server (Port $Port)"
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "   Regel existiert bereits."
    } else {
        New-NetFirewallRule -DisplayName $ruleName `
            -Direction Inbound -Protocol TCP -LocalPort $Port `
            -Action Allow -Profile Any | Out-Null
        Write-Host "   Regel erstellt."
    }
} catch {
    Write-Warning "Firewall-Regel konnte nicht gesetzt werden (Admin-Rechte benoetigt): $_"
    Write-Host "   Manuell: Einstellungen -> Windows-Sicherheit -> Firewall -> Port $Port freigeben" -ForegroundColor Yellow
}

# ── IP-Adresse anzeigen ───────────────────────────────────────────────────────
$ips = Get-NetIPAddress -AddressFamily IPv4 -Type Unicast |
       Where-Object { $_.IPAddress -notmatch "^127\." -and $_.IPAddress -notmatch "^169\.254\." } |
       Select-Object -ExpandProperty IPAddress

Write-Host ""
Write-Host "══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host " Setup abgeschlossen auf $env:COMPUTERNAME (Windows)" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host " RPC-Server Binary : $($rpcBin.FullName)"
Write-Host " Start-Script      : $StartScript"
Write-Host ""
Write-Host " IP-Adressen dieses Rechners:"
$ips | ForEach-Object { Write-Host "   $_" }
Write-Host ""
Write-Host " Naechste Schritte:" -ForegroundColor Cyan
Write-Host "  1. RPC-Server starten:"
Write-Host "       $StartScript"
Write-Host "     oder direkt:"
Write-Host "       `"$($rpcBin.FullName)`" --host 0.0.0.0 --port $Port"
Write-Host ""
Write-Host "  2. IP oben notieren und auf dem Master-Node llama-server starten:"
Write-Host "       --rpc <diese-IP>:$Port"
Write-Host ""
Write-Host "  3. GPU-Nutzung pruefen (bei Vulkan-Build):"
Write-Host "       Im Task-Manager -> GPU -> 3D/Compute-Last sichtbar"
Write-Host ""
