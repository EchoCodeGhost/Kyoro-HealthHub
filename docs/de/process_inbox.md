# process_inbox.py — Inbox-Prozessor für Import-Dateien

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/process_inbox.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erkennt und routet Dateien aus imports/_inbox/ an die entsprechenden Importer. Ermöglicht einfaches Ablegen von Dateien ohne manuelle Zuordnung.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Unterstützt ZIP-Archive (Apple Health, Polar GDPR, Garmin GDPR, Oura CSV) und Einzeldateien (Symptom-History, WomanLog, Bearable, HRV4Training, Ecowitt, HealthManager Pro, RENPHO, Wellue O2Ring, ECGLogger, Omron, FDDB (diary_*.csv, userhistory_*.csv, kombinierter complete_*.csv-Export), Hilo-Blutdruckbericht, PDF-Laborergebnisse, Migraine-App, Shotsy, Kubios-Screenshots, Kubios-TXT, GPX). ECGLogger und Omron werden per Header-Sniffing erkannt (Dateinamen sind app-generisch, kein festes Muster). Dateien werden nach Verarbeitung nach _inbox/processed/ verschoben.

## Datenfluss

- **Liest:** `imports/_inbox/`, `Verzeichnis`
- **Schreibt:** `Verschiedene imports/*/ Verzeichnisse, imports/_inbox/processed/`

## Grenzen

Erkennung basiert auf Dateinamen-Mustern. Unbekannte Formate werden stillschweigend uebersprungen.

## Aufruf

```bash
python3 scripts/process_inbox.py              # alle Dateien in _inbox/
python3 scripts/process_inbox.py --dry-run    # zeigt was passieren würde
python3 scripts/process_inbox.py --import     # danach import_all.py --update
python3 scripts/process_inbox.py --file a.zip
```
