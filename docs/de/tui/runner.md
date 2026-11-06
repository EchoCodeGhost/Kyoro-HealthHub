# Job-Runner der Pipeline-TUI: startet Skripte als Unterprozesse.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/tui/runner.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Führt höchstens einen Pipeline-Job gleichzeitig aus, streamt seine Ausgabe und beendet beim Abbrechen die ganze Prozessgruppe. Daneben laufen Dienste außerhalb der Job-Sperre und interaktive Skripte am echten Terminal.

## Relevanz

Grundlage dafür, dass die TUI nie parallel in dieselben Datenbanken schreibt

## Methode

Drei Modi. piped: eigene Session, stdin=DEVNULL, stdout und stderr zusammengeführt, PYTHONUNBUFFERED=1 und MPLBACKEND=Agg. interactive: läuft innerhalb des übergebenen suspend-Kontexts in derselben Session, damit das Skript das Terminal behält. service: eigene Session, Ausgabe wird dauerhaft gelesen, damit die Pipe nie volllaufen kann. Abbrechen sendet SIGTERM an die Prozessgruppe und nach der Wartezeit SIGKILL. Immer eine Argumentliste, nie eine Shell.

## Datenfluss

- **Liest:** `Keine`, `Tabellen`
- **Schreibt:** `Keine Tabellen, keine Dateien`

## Grenzen

Behält keine Ausgabe: Zeilen gehen nur an den Callback. Hintergrundprozesse, die ein normal beendeter Job hinterlässt, laufen weiter. Nur POSIX.

## Aufruf

```bash
runner = JobRunner()
result = await runner.run_piped([sys.executable, "script.py"], log.write_line)
await runner.cancel()
result = runner.run_interactive([sys.executable, "script.py"], app.suspend)
await runner.start_service("datasette", [sys.executable, "serve.py"])
```
