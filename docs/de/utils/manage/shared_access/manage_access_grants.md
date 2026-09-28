# manage_access_grants.py — Zugriffsfreigaben verwalten (erteilen/auflisten/widerrufen)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/shared_access/manage_access_grants.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet Zugriffsfreigaben pro Person für einen benannten Zweck (Scope) — z. B. "Datenexport für Ärzt:in X" oder "Auswertung durch Familienmitglied Y". Jede Person kann für verschiedene Zwecke separat freigeben oder die Freigabe widerrufen. Ohne gültige Freigabe wird eine Person von entsprechenden Exporten ausgeschlossen. Für den privaten Mehrpersonen-Kontext gedacht, siehe SHARED_ACCESS_DEPLOYMENT.md.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Schreibt/liest die Freigabe-Tabelle in master.db (siehe create_master_schema.py). Unterstützt grant (neue Freigabe), list (Anzeige aller Freigaben), und revoke (Widerruf einer bestehenden Freigabe).

## Datenfluss

- **Liest:** `~/.config/kyoro-master/master.db`, `(Freigabe-Tabelle`, `Personen-Zuordnung)`
- **Schreibt:** `~/.config/kyoro-master/master.db (Freigabe-Tabelle)`

## Grenzen

Keine automatische Prüfung der Zweck-Bezeichnungen — der Betreiber ist verantwortlich, sinnvolle, eindeutige Bezeichnungen zu verwenden. Widerruf ist nicht retroaktiv — bereits exportierte Daten bleiben unberührt.

## Aufruf

```bash
python3 scripts/utils/manage/shared_access/manage_access_grants.py grant --person PT-ABC12345 --scope export-2026-review
python3 scripts/utils/manage/shared_access/manage_access_grants.py list
python3 scripts/utils/manage/shared_access/manage_access_grants.py list --person PT-ABC12345
python3 scripts/utils/manage/shared_access/manage_access_grants.py revoke --person PT-ABC12345 --scope export-2026-review
```
