# llama.cpp RPC-Node Startskript fuer Windows
#
# Deaktiviert Sleep/Standby fuer die Dauer des RPC-Servers.
# Stellt Energieeinstellungen beim Beenden automatisch wieder her.
#
# Ausfuehren (als normaler User, kein Admin noetig):
#   powershell -ExecutionPolicy Bypass -File rpc-node-win.ps1
#
# Binary-Pfad anpassen:
#   $env:LLAMA_RPC = "C:\anderer\pfad\llama-rpc-server.exe"
#   powershell -ExecutionPolicy Bypass -File rpc-node-win.ps1

$LLAMA_RPC = if ($env:LLAMA_RPC) { $env:LLAMA_RPC } `
             else { "$env:USERPROFILE\llama.cpp\build\bin\llama-rpc-server.exe" }
$PORT = if ($env:PORT) { $env:PORT } else { "50052" }

if (-not (Test-Path $LLAMA_RPC)) {
    Write-Error "llama-rpc-server nicht gefunden: $LLAMA_RPC"
    Write-Error "Ueberschreiben mit: `$env:LLAMA_RPC='C:\pfad\llama-rpc-server.exe'"
    exit 1
}

# Aktuelle Standby-Timeouts sichern
$acStandby  = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE  | Select-String "Aktueller AC").ToString().Split()[-1]
$acMonitor  = (powercfg /query SCHEME_CURRENT SUB_VIDEO VIDEOIDLE    | Select-String "Aktueller AC").ToString().Split()[-1]

Write-Host "==> RPC-Node (Windows) | Port $PORT | $env:COMPUTERNAME"
Write-Host "==> Binary: $LLAMA_RPC"
Write-Host "==> Sleep deaktiviert fuer Dauer des Servers"

# Sleep/Monitor-Timeout deaktivieren
powercfg /change standby-timeout-ac 0  | Out-Null
powercfg /change monitor-timeout-ac 0  | Out-Null

try {
    & $LLAMA_RPC --host 0.0.0.0 --port $PORT
} finally {
    # Timeouts wiederherstellen
    Write-Host "`n==> RPC-Node beendet — Energieeinstellungen wiederhergestellt"
    powercfg /change standby-timeout-ac 30 | Out-Null
    powercfg /change monitor-timeout-ac 15 | Out-Null
}
