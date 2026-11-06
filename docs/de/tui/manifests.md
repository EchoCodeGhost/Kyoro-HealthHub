# Manifest-Typen und Ausschlüsse der Pipeline-TUI.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/tui/manifests.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Beschreibt Skripte ohne eigenes Register und legt fest, welche Flags die TUI übergeben darf und welche Werkzeuge sie nie anbietet.

## Relevanz

Verhindert, dass die Oberfläche Schutzmaßnahmen abschwächt

## Methode

Allowlist: build_args() erzeugt Argumente nur aus deklarierten Feldern, und ein Eintrag mit gesperrtem Flag lässt sich gar nicht erst anlegen. Pfade in EXCLUDED sind relativ zu scripts/; * passt auch über Verzeichnisse hinweg.

## Datenfluss

- **Liest:** `Keine`, `Tabellen`
- **Schreibt:** `Keine Tabellen`

## Grenzen

Enthält nur Typen und Ausschlüsse. Die Einträge pro Skript folgen getrennt.

## Aufruf

```bash
entry = ScriptEntry("analysis/manual/analyse_ecg_session.py", ("EKG", "ECG"), "analyse_manual",
                    fields=(IntField("--session", required=True), BoolField("--plot")))
entry.build_args({"--session": 42, "--plot": True})
is_excluded("utils/decrypt_db.py")
```
