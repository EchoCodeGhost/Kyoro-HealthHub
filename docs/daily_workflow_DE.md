# Daily Workflow / Täglicher Daten-Import

## Übersicht / Overview

Der tägliche Import deckt zwei getrennte Datenwege ab: Online-Quellen (Fetch/Import)
und Geräteexporte (Inbox-Sortierung).

| Phase | Skript | Was passiert |
|---|---|---|
| **Fetch** | `scripts/fetch_daily.py` | Holt Daten von allen Online-Quellen → `data/staging/YYYY-MM-DD/` |
| **Import** | `scripts/import_staged.py` | Liest Staging-Dateien → schreibt in `health.db` |
| **Geräte-Import** | `scripts/process_inbox.py` | Sortiert Dateien aus `imports/_inbox/` nach Dateimuster in die passenden `imports/*/`-Unterordner und importiert sie |

**Vorteile dieser Trennung:**
- Daten werden gespeichert, auch wenn der Import fehlschlägt
- Re-Import ohne erneuten API-Abruf möglich
- Offline-Import nachträglich ausführbar
- Jede Phase einzeln debugbar
- Geräteexporte müssen nicht manuell einsortiert werden — `process_inbox.py` erkennt Dateitypen am Namensmuster

---

## Quellen / Sources

| Quelle | Skript | Tabellen | Kosten |
|---|---|---|---|
| Open-Meteo Luftqualität + Pollen | `import_airquality.py` | `air_quality`, `pollen` | kostenlos |
| Open-Meteo Biometeo | `import_airquality.py` | `biometeo` | kostenlos |
| DWD Pollenflug | `import_pollen_dwd.py` | `pollen_dwd` | kostenlos |
| Google Pollen API | `import_pollen_google.py` | `pollen_google` | kostenlos (bis Limit) |
| Dyson/VeSync via Home Assistant | `import_homeassistant.py` | `indoor_air_quality` | lokal |
| EcoWitt via Home Assistant | `import_homeassistant.py` | `weather_station` | lokal |

**Manuell (kein automatischer Fetch möglich):**
```bash
python importers/import_lab_results.py <datei.pdf>
python importers/import_hrv4training.py --file export.csv
python importers/import_apple.py       # Apple Health Export
python importers/import_polar.py       # Polar GDPR Export
python importers/import_garmin.py      # nach garmin_download.py
```

---

## Verwendung / Usage

### Täglich ausführen / Daily run

```bash
cd ~/Kyoro-HealthHub/scripts

# 1. Fetch (Online-Daten holen, kein DB-Schreibzugriff)
python fetch_daily.py

# 2. Import (Staging → health.db)
python import_staged.py

# 3. Geräteexporte (Dateien vorher unsortiert in imports/_inbox/ ablegen)
python process_inbox.py --dry-run   # Vorschau: was würde erkannt/einsortiert?
python process_inbox.py --import    # Einsortieren + import_all.py --update in einem Schritt
```

### Staging-Tage anzeigen
```bash
python import_staged.py --list
```

### Bestimmten Tag importieren
```bash
python import_staged.py --date 2026-06-01
```

### Alle gestagten Tage auf einmal importieren
```bash
python import_staged.py --all
```

### Rückstand aufholen (z.B. nach Urlaub)
```bash
# Letzten 7 Tage fetchen
python fetch_daily.py --days-back 7

# Alles importieren
python import_staged.py --all
```

### Ohne Home Assistant (wenn HA nicht erreichbar)
```bash
python fetch_daily.py --no-ha
```

---

## Staging-Format / Staging Format

```
data/staging/
  YYYY-MM-DD/
    airquality_aq.json   ← Open-Meteo AQ API-Antwort (Roh-JSON)
    airquality_bio.json  ← Open-Meteo Archive API-Antwort
    pollen_dwd.json      ← DWD API-Antwort
    pollen_google.json   ← Google Pollen API-Antwort (falls Key vorhanden)
    dyson.json           ← HA-Statistics + Entity-Metadaten (Dyson/VeSync)
    ecowitt.json         ← HA-Statistics (EcoWitt-Wetterstation)
    manifest.json        ← Fetch-Status, Datum, Koordinaten, Region
```

Staging-Daten sind in `.gitignore` — sie gehören nicht ins Repository.

---

## Automatisierung / Automation

### systemd User-Timer (empfohlen)

```bash
# Verzeichnis anlegen
mkdir -p ~/.config/systemd/user/

# Service-Datei erstellen
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

# Timer-Datei erstellen (täglich 08:00 Uhr)
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

# Log-Verzeichnis anlegen
mkdir -p ~/Kyoro-HealthHub/logs

# Timer aktivieren und starten
systemctl --user daemon-reload
systemctl --user enable --now kyoro-fetch.timer

# Status prüfen
systemctl --user list-timers kyoro-fetch.timer
```

### Nächsten Lauf manuell auslösen
```bash
systemctl --user start kyoro-fetch.service
```

### Logs anzeigen
```bash
# Systemd Journal
journalctl --user -u kyoro-fetch.service -n 50

# Log-Datei
tail -f ~/Kyoro-HealthHub/logs/daily.log
```

### Timer deaktivieren
```bash
systemctl --user disable --now kyoro-fetch.timer
```

---

### Cron (Alternative)

Falls systemd nicht verfügbar:

```bash
crontab -e
```

Zeile hinzufügen:
```
0 8 * * * cd ~/Kyoro-HealthHub/scripts && python3 fetch_daily.py >> ~/Kyoro-HealthHub/logs/daily.log 2>&1 && python3 import_staged.py >> ~/Kyoro-HealthHub/logs/daily.log 2>&1
```

---

## Troubleshooting

### Staging vorhanden, aber Import schlägt fehl
```bash
# Staging-Inhalt prüfen
cat data/staging/$(date +%F)/manifest.json

# Einzelne Quelle neu importieren
python import_staged.py --date $(date +%F)
```

### API-Fehler beim Fetch
```bash
# Ohne fehlende Quelle fetchen, z.B. ohne HA
python fetch_daily.py --no-ha

# Nur bestimmte Quelle testen
python importers/import_pollen_dwd.py
python importers/import_airquality.py --update
```

### Google Pollen API einrichten
1. Google Cloud Console → APIs & Services → Pollen API aktivieren
2. API-Key erstellen
3. In `~/.config/kyoro/health_config.json` eintragen:
   ```json
   "google_pollen_key": "AIza..."
   ```
