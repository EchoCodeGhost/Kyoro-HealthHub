# check_source_privacy — Source-Code- und Doku-Privacy-Compliance-Check für Kyoro-HealthHub

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_source_privacy.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft Python-Quelldateien UND Doku/Config-Dateien (.md, .json) auf Datenschutz-Compliance-Verstöße. Identifiziert: verbotene Bezeichner aus privacy_check.forbidden_identifiers (alle Dateitypen), exakte Datenmengen-Statistiken über die eigene Nutzung (alle Dateitypen — Fund war eine archivierte OpenSpec-tasks.md, kein Skript), hardcodierte Person-IDs (Literale 'self' statt OWN_PERSON_ID), hardcodierte IANA-Zeitzonen-Strings, Fallback-Dicts mit Entity-IDs (nur .py — diese Kategorien sind Code-Konventionen, keine Doku-Fehler).

## Relevanz

Bietet Prüfungsfunktionen für Datenqualität und Datenschutz, essentiell für die Datenintegrität

## Methode

Lädt verbotene Bezeichner aus ~/.config/kyoro/health_config.json → privacy_check.forbidden_identifiers. Scannt standardmäßig das gesamte Repo (.py, .md, .json) — genauer: alle git-getrackten Dateien mit diesen Endungen (git ls-files), d.h. gitignorte/private Verzeichnisse (intern/, data/, imports/, analyses/, exports/, logs/, medicine/, medizin/) fallen automatisch raus, ohne hier ein zweites Mal gepflegt werden zu müssen. Statische Checks: Hardcodierte Person-IDs in SQL und Zuweisungen, IANA-Zeitzonen-Strings (Africa/, America/, etc.), Fallback-Dicts mit Entity-IDs, hartkodierte Config-Pfade — alle vier Kategorien nur für .py, da sie Code-Antipatterns sind und in Doku-Beispielen (z.B. SQL-Snippets mit person='self' oder einer IANA-Zeitzone als dokumentiertem Schema-Default) falsch-positiv wären. Der Bezeichner-Check (forbidden_identifiers) läuft auf allen Dateitypen — das ist der Mechanismus, der personenbezogene Daten in Markdown/JSON fängt. Unterstützt rekursives Scannen von Verzeichnissen, JSON-Ausgabe und Strict-Modus. Überspringt eigene Datei (Selbst-Exclude) und spezifische Verzeichnisse. Exit-Code: 0 = sauber, 1 = Findings gefunden.

## Datenfluss

- **Liest:** `~/.config/kyoro/health_config.json`, `alle`, `.py/.md/.json-Dateien`, `im`, `gescannten`, `Verzeichnis`
- **Schreibt:** `stdout (Berichte und JSON-Ausgabe)`

## Grenzen

Kann falsch-positive Ergebnisse liefern (z.B. in t()-Aufrufen oder Kommentaren). Dokstrings und Kommentare (.py) werden nicht gescannt. Freitext-Statistiken (z.B. "sechs EKG mit AFib") sind nicht mechanisch erkennbar — nur über privacy_check.forbidden_identifiers oder menschliches Review.

## Aufruf

```bash
python scripts/utils/check_source_privacy.py
python scripts/utils/check_source_privacy.py --dir /path/to/scan
python scripts/utils/check_source_privacy.py --json
python scripts/utils/check_source_privacy.py --strict
python scripts/utils/check_source_privacy.py --high-only
python scripts/utils/check_source_privacy.py --ext .py .md .json
# --dir: Verzeichnis zum Scannen angeben (Standard: Repo-Root)
# --json: Ausgabe als JSON
# --strict: Wertet auch low-confidence Findings als Fehler
# --high-only: Nur high-confidence Findings ausgeben
# --ext: Zu scannende Dateiendungen (Standard: .py .md .json)
```
