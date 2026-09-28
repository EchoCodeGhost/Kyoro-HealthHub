# manage_shared_devices.py — Gemeinsamer Geräte-Katalog (Provisionierungsquelle)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/shared_access/manage_shared_devices.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet einen gemeinsamen Katalog geteilter Geräte (z. B. ein gemeinsam genutztes Blutdruckmessgerät im Haushalt) als reine Kopiervorlage für neue Personen-Instanzen — kein geteilter Laufzeit-Zustand. Für den privaten Mehrpersonen-Kontext gedacht, siehe SHARED_ACCESS_DEPLOYMENT.md.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Liest/schreibt ~/.config/kyoro-master/master.db (Tabelle practice_devices, immer im echten Betreiber-Home, nicht in einer aktiven Personen- Instanz). `manage_people.py add` kann daraus Einträge in die neue Instanz-Config kopieren (einmalig, danach unabhängig).

## Datenfluss

- **Liest:** `~/.config/kyoro-master/master.db`, `(practice_devices)`
- **Schreibt:** `~/.config/kyoro-master/master.db (practice_devices)`

## Grenzen

Kein geteilter Zustand nach dem Kopieren — Änderungen am Katalog wirken sich NICHT auf bereits angelegte Instanzen aus (bewusst, sonst Isolationsverletzung). Keine echten Personendaten in dieser Tabelle.

## Aufruf

```bash
python3 scripts/utils/manage/shared_access/manage_shared_devices.py list
python3 scripts/utils/manage/shared_access/manage_shared_devices.py add omron-haushalt-1 Omron "X7 Smart" AABBCC112233 bp_monitor
python3 scripts/utils/manage/shared_access/manage_shared_devices.py remove omron-haushalt-1
```
