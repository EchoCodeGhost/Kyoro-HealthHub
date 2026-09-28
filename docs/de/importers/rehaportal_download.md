# dasrehaportal.de → Kategorie-Listen-Download

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/rehaportal_download.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt die paginierten Ergebnislisten der Reha-Kliniken von dasrehaportal.de für eine konfigurierbare Menge von Indikations-Kategorien herunter.

## Relevanz

Beschafft Rohdaten für die Reha-Planung, kein direkter Bezug zu persönlichen Gesundheitsdaten — die tatsächlich gesuchten Indikationen stehen nur in der lokalen Konfigurationsdatei

## Methode

Die Kategorie-Slugs (z. B. "rueckenschmerzen") kommen ausschließlich aus einer lokalen, nicht versionierten Konfigurationsdatei (~/.config/kyoro/rehaportal_kategorien.json) — das Skript selbst enthält keine einzige Indikation fest codiert, damit weder der Quellcode noch ein Commit Rückschlüsse auf die tatsächlich gesuchten Indikationen zulässt. Neue Kategorien hinzufügen = Slug in der Konfigurationsdatei ergänzen, kein Code-Änderung nötig. Pro Kategorie wird https://www.dasrehaportal.de/reha/rehakliniken/<slug>?page=N seitenweise abgerufen, bis eine Seite keine "clinic-result-box"-Treffer mehr enthält (kein Rückgriff auf die Paginierungs-Widget-Struktur, robuster gegen Layout-Änderungen). Kurze Pause zwischen den Requests.

## Datenfluss

- **Liest:** `https://www.dasrehaportal.de/reha/rehakliniken/<slug>`, `(online)`, `~/.config/kyoro/rehaportal_kategorien.json`, `(Kategorie-Liste)`
- **Schreibt:** `imports/rehaportal/kategorien/<slug>/page_<N>.html`

## Grenzen

Reverse-engineert die serverseitig gerenderte Paginierung einer kommerziellen Bewertungsplattform anhand ihrer eigenen Markup- Struktur — bei Layout-Änderungen muss dieses Skript neu geprüft werden. robots.txt der Seite wurde vor Erstellung geprüft (keine Sperre für diesen Pfad, kein Crawl-Delay vorgegeben); die hartcodierte Pause zwischen Requests ist trotzdem beibehalten, um den Server nicht zu belasten.

## Aufruf

```bash
python3 rehaportal_download.py
python3 rehaportal_download.py --help
```
