# Daily Workflow

## Overview

The daily import covers two separate data paths: online sources (fetch/import)
and device exports (inbox sorting).

| Phase | Script | What happens |
|---|---|---|
| **Fetch** | `scripts/fetch_daily.py` | Pulls data from all online sources → `data/staging/YYYY-MM-DD/` |
| **Import** | `scripts/import_staged.py` | Reads staging files → writes to `health.db` |
| **Device import** | `scripts/process_inbox.py` | Sorts files from `imports/_inbox/` by filename pattern into the matching `imports/*/` subfolder and imports them |

**Benefits of this separation:**
- Data is saved even if the import fails
- Re-import possible without a repeat API call
- Offline import can be run later
- Each phase is debuggable on its own
- Device exports don't need manual sorting — `process_inbox.py` recognizes file types by filename pattern

---

## Sources

| Source | Script | Tables | Cost |
|---|---|---|---|
| Open-Meteo air quality + pollen | `import_airquality.py` | `air_quality`, `pollen` | free |
| Open-Meteo biometeo | `import_airquality.py` | `biometeo` | free |
| DWD pollen forecast | `import_pollen_dwd.py` | `pollen_dwd` | free |
| Google Pollen API | `import_pollen_google.py` | `pollen_google` | free (up to limit) |
| Dyson/VeSync via Home Assistant | `import_homeassistant.py` | `indoor_air_quality` | local |
| EcoWitt via Home Assistant | `import_homeassistant.py` | `weather_station` | local |

**Manual (no automatic fetch possible):**
```bash
python importers/import_lab_results.py <file.pdf>
python importers/import_hrv4training.py --file export.csv
python importers/import_apple.py       # Apple Health export
python importers/import_polar.py       # Polar GDPR export
python importers/import_garmin.py      # after garmin_download.py
```

---

## Usage

### Daily run

```bash
cd ~/Kyoro-HealthHub/scripts

# 1. Fetch (pull online data, no DB write access)
python fetch_daily.py

# 2. Import (staging → health.db)
python import_staged.py

# 3. Device exports (drop unsorted files into imports/_inbox/ first)
python process_inbox.py --dry-run   # preview: what would be recognised/sorted?
python process_inbox.py --import    # sort + import_all.py --update in one step
```

### List staged days
```bash
python import_staged.py --list
```

### Import a specific day
```bash
python import_staged.py --date 2026-06-01
```

### Import all staged days at once
```bash
python import_staged.py --all
```

### Catching up (e.g. after a vacation)
```bash
# Fetch the last 7 days
python fetch_daily.py --days-back 7

# Import everything
python import_staged.py --all
```

### Without Home Assistant (when HA is unreachable)
```bash
python fetch_daily.py --no-ha
```

---

## Staging Format

```
data/staging/
  YYYY-MM-DD/
    airquality_aq.json   ← Open-Meteo AQ API response (raw JSON)
    airquality_bio.json  ← Open-Meteo Archive API response
    pollen_dwd.json      ← DWD API response
    pollen_google.json   ← Google Pollen API response (if key present)
    dyson.json           ← HA statistics + entity metadata (Dyson/VeSync)
    ecowitt.json         ← HA statistics (EcoWitt weather station)
    manifest.json        ← fetch status, date, coordinates, region
```

Staging data is in `.gitignore` — it doesn't belong in the repository.

---

## Automation

### systemd user timer (recommended)

```bash
# Create the directory
mkdir -p ~/.config/systemd/user/

# Create the service file
cat > ~/.config/systemd/user/kyoro-fetch.service << 'EOF'
[Unit]
Description=Kyoro HealthHub — Daily Fetch
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=%h/Kyoro-HealthHub/scripts
ExecStart=/usr/bin/python3 %h/Kyoro-HealthHub/scripts/fetch_daily.py
ExecStartPost=/usr/bin/python3 %h/Kyoro-HealthHub/scripts/import_staged.py
StandardOutput=append:%h/Kyoro-HealthHub/logs/daily.log
StandardError=append:%h/Kyoro-HealthHub/logs/daily.log

[Install]
WantedBy=default.target
EOF

# Create the timer file (daily at 08:00)
cat > ~/.config/systemd/user/kyoro-fetch.timer << 'EOF'
[Unit]
Description=Kyoro HealthHub — Daily Fetch Timer

[Timer]
OnCalendar=*-*-* 17:30:00
Persistent=true
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
EOF

# Create the log directory
mkdir -p ~/Kyoro-HealthHub/logs

# Enable and start the timer
systemctl --user daemon-reload
systemctl --user enable --now kyoro-fetch.timer

# Check status
systemctl --user list-timers kyoro-fetch.timer
```

### Trigger the next run manually
```bash
systemctl --user start kyoro-fetch.service
```

### View logs
```bash
# systemd journal
journalctl --user -u kyoro-fetch.service -n 50

# Log file
tail -f ~/Kyoro-HealthHub/logs/daily.log
```

### Disable the timer
```bash
systemctl --user disable --now kyoro-fetch.timer
```

---

### Cron (alternative)

If systemd isn't available:

```bash
crontab -e
```

Add this line:
```
0 8 * * * cd ~/Kyoro-HealthHub/scripts && python3 fetch_daily.py >> ~/Kyoro-HealthHub/logs/daily.log 2>&1 && python3 import_staged.py >> ~/Kyoro-HealthHub/logs/daily.log 2>&1
```

---

## Troubleshooting

### Staging exists, but the import fails
```bash
# Check staging content
cat data/staging/$(date +%F)/manifest.json

# Re-import a single source
python import_staged.py --date $(date +%F)
```

### API error during fetch
```bash
# Fetch without a missing source, e.g. without HA
python fetch_daily.py --no-ha

# Test just one source
python importers/import_pollen_dwd.py
python importers/import_airquality.py --update
```

### Setting up the Google Pollen API
1. Google Cloud Console → APIs & Services → enable the Pollen API
2. Create an API key
3. Add it to `~/.config/kyoro/health_config.json`:
   ```json
   "google_pollen_key": "AIza..."
   ```
