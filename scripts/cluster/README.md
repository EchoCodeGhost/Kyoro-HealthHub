# Cluster Setup — llama.cpp RPC

The master node distributes model layers via RPC to worker nodes. Each
worker node exposes its VRAM/RAM as a remote backend; the llama-server on
the master node coordinates inference and the API.

## Architecture

```
Clients (HealthHub, Browser, LocallyAI)
        │
        ▼
  Master node :8080  ← Qwen3.5-35B   (Vulkan GPU, ~28 GB VRAM + 64 GB RAM)
  Master node :8081  ← MedGemma-27B  (local, no cluster needed)
        │
        ├─── RPC ──▶  Linux CPU node  :50052  (CPU, ~15 GB RAM)
        └─── RPC ──▶  Win GPU node    :50052  (Vulkan GPU, ~32 GB VRAM)

Optional:
        └─── RPC ──▶  macOS Metal node :50052  (Metal GPU, ~24 GB unified)
```

**Important:** An RPC node can only serve one llama-server at a time. If two
servers run in parallel, each needs its own nodes or must run locally.

---

## Step 1 — Start the RPC nodes

### Linux worker node

```bash
# One-time deploy (from the master node):
scp cluster/rpc-node.service <user>@<node-ip>:~/.config/systemd/user/
ssh <user>@<node-ip> 'systemctl --user daemon-reload && systemctl --user enable --now rpc-node.service'

# Check status:
ssh <user>@<node-ip> 'systemctl --user status rpc-node'
# Logs:
ssh <user>@<node-ip> 'journalctl --user -u rpc-node -f'
```

### Windows worker node

```powershell
# Copy rpc-node-win.ps1 to the node, then in PowerShell:
powershell -ExecutionPolicy Bypass -File rpc-node-win.ps1
```

The script disables sleep for the duration and automatically restores the
power settings on exit.

### macOS worker node

```bash
# One-time deploy:
scp cluster/rpc-node-mac.sh <user>@<node-ip>:~/
ssh <user>@<node-ip> 'chmod +x ~/rpc-node-mac.sh && ~/rpc-node-mac.sh'
```

Uses `caffeinate -i` to prevent macOS sleep.

---

## Step 2 — Start the LLM server on the master node

```bash
# With worker nodes (set the RPC_NODES environment variable):
RPC_NODES="<node1-ip>:50052,<node2-ip>:50052" ./llama-server-start.sh

# Local, without a cluster:
RPC_NODES="" ./llama-server-start.sh

# Second model locally on a different port:
RPC_NODES="" ./llama-server-medgemma.sh
```

---

## Step 3 — Test

```bash
curl http://localhost:8080/health
curl http://localhost:8081/health

curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local","messages":[{"role":"user","content":"Hello!"}],"max_tokens":50}'
```

---

## Monitoring

```bash
# Check connections to RPC nodes:
watch -n2 'ss -tn | grep 50052'

# Server processes:
ps aux | grep llama-server

# RAM usage:
free -h
```

---

## Known limitations & flags

| Flag | Reason |
|---|---|
| `-fit off` | Prevents "RPC did not report memory" spam when a node responds slowly |
| `--no-warmup` | Prevents a crash during warmup inference on RPC nodes |
| `RPC_NODES=""` | Empty string = no cluster; unset variable = default nodes from the script |

**No output after server start?** → Port already in use (`lsof -i :8080`) or
an RPC node isn't responding (another server already connected).

---

## Model capacity per cluster configuration

| Nodes | Total VRAM/RAM (rough) | Recommended model |
|---|---|---|
| Master alone | ~28 GB GPU + 64 GB CPU | 27B Q4, 35B MoE Q4 |
| + Win GPU node | ~60 GB GPU | 35B Q4 in cluster |
| + Linux CPU node | ~75 GB total | larger models, but CPU is the bottleneck |
| + macOS Metal node | ~99 GB GPU | 70B Q4 possible |

---

## Troubleshooting

**RPC port unreachable:**
```bash
nc -zv <node-ip> 50052
```

**Linux firewall:**
```bash
sudo ufw allow 50052
```

**Windows firewall (PowerShell as admin):**
```powershell
New-NetFirewallRule -DisplayName "llama.cpp RPC" -Direction Inbound -Protocol TCP -LocalPort 50052 -Action Allow
```

**Master node WiFi freezing under load:**
```bash
iw dev <wifi-interface> set power_save off
# Permanent via NetworkManager (/etc/NetworkManager/conf.d/wifi-power-save-off.conf):
# [connection]
# wifi.powersave = 2
```
