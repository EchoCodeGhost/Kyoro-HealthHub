# manage_people.py — Personenregistratur für gemeinsam genutzte Kyoro-Instanzen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/shared_access/manage_people.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet die Zuordnung von Personennummern zu isolierten Kyoro-Instanzverzeichnissen (jede Person hat eigene health.db + eigenen db_key). Für den privaten Mehrpersonen-Kontext gedacht (z. B. Familie, Freundeskreis) — Kyoro-HealthHub ist bewusst auf Privatnutzung ausgerichtet, siehe SHARED_ACCESS_DEPLOYMENT.md. Optionale interaktive Übernahme gemeinsam genutzter Geräte.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Schreibt/liest die Personen-Zuordnung in master.db (siehe create_master_schema.py). Legt bei `add` ein neues Instanzverzeichnis mit eigenem .config/kyoro/ + data/ an. `activate` gibt NUR den Export-Befehl aus — die eigentliche Berechtigungsprüfung passiert im Broker (Abschnitt 4.2 des Shared-Access-Plans), dieses Skript selbst kennt kein Login/keine Rollen.

## Datenfluss

- **Liest:** `~/.config/kyoro-master/master.db`, `(Personen-Zuordnung)`
- **Schreibt:** `~/.config/kyoro-master/master.db (Personen-Zuordnung), neue Instanzverzeichnisse`

## Grenzen

Kein Zugriffskontroll-Layer — wer Shell-Zugriff auf die Maschine hat, kann jedes Instanzverzeichnis manuell aktivieren. Physische/ OS-Zugriffskontrolle (Nutzerkonten, Dateiberechtigungen) bleibt Aufgabe des Betreibers; der Broker (Abschnitt 4) autorisiert nur den Web-/API-Pfad über Kyoro SymptomTrack, nicht direkten Shell-Zugriff.

## Aufruf

```bash
python3 scripts/utils/manage/shared_access/manage_people.py list
python3 scripts/utils/manage/shared_access/manage_people.py add "12345" "Familie-A"
python3 scripts/utils/manage/shared_access/manage_people.py deactivate PT-A3F9C21B
python3 scripts/utils/manage/shared_access/manage_people.py activate PT-A3F9C21B
```
