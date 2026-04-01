# Candidate Fixes for OpenClaw on Pi 3B

Use these as candidate interventions, not defaults. Apply only after measurements and include rollback steps.

## Memory Survival Stack (candidate)

| Layer | Fix | Notes |
|---|---|---|
| OS buoyancy | Install zram swap | Use only if swap storms are present. Validate with `vmstat 1`. |
| Node tuning | Set `NODE_OPTIONS=--max-old-space-size=<MiB>` | Pick based on observed RSS and headroom target. |
| GPU reduction | Set `gpu_mem=16` (headless only) | Requires reboot; confirm with `vcgencmd get_mem gpu`. |
| Swappiness | Adjust `vm.swappiness` | Start conservative (60). Raise only if swap use is stable. |

## API Key Authentication (OpenClaw)

When daemonized, prefer environment variables in `~/.openclaw/.env`.

```bash
echo "GOOGLE_API_KEY=..." >> ~/.openclaw/.env
echo "GEMINI_API_KEY=..." >> ~/.openclaw/.env
sudo systemctl restart openclaw
```

Verify:

```bash
openclaw models status
```

## Minimal Config Template (example only)

```json
{
  "agents": {
    "defaults": {
      "model": { "primary": "google/gemini-3-flash-preview" },
      "heartbeat": { "every": "20m" },
      "maxConcurrent": 1,
      "subagents": { "maxConcurrent": 1 }
    }
  },
  "gateway": { "auth": { "token": "your-token" } },
  "channels": {
    "telegram": {
      "enabled": true,
      "tokenFile": "${OPENCLAW_HOME:-~/.openclaw}/telegram.token"
    }
  }
}
```

## Systemd Service Template (example only)

Fill in MemoryHigh/MemoryMax based on measured headroom, not defaults.

```ini
[Unit]
Description=OpenClaw Gateway
After=network.target

[Service]
Type=simple
User=pi
Environment=NODE_OPTIONS=--max-old-space-size=<MiB>
ExecStart=/usr/bin/openclaw gateway --port 18789 --allow-unconfigured
Restart=always
RestartSec=30
MemoryHigh=<MiB>
MemoryMax=<MiB>
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
```

## Acceptance Tests (baseline)

- Uptime targets: 6h, 24h, 72h
- Memory: no unbounded RSS growth, swap stays under ceiling
- Latency: response time does not degrade catastrophically
- Logs: no OOM kill entries, no repeated restart loops

PASS if all targets met. FAIL if any target missed, then select next ranked fix.
