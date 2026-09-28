# check_syndrome_endemic_regions — Haelt scripts/analysis/syndromes/*.json in Sync mit den echten Ausbruchsdaten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_syndrome_endemic_regions.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prueft automatisch, ob die `endemic_regions`-Liste jeder Syndrom-JSON-Datei (scripts/analysis/syndromes/*.json) mit den tatsaechlichen, strukturierten Endemie-/FSME-Referenzdaten aus import_outbreak_data.py (ENDEMIC_REFERENCE, FSME_RISIKOKREISE_BUNDESWEIT) uebereinstimmt -- ohne dieses Skript faellt eine Erweiterung der Ausbruchsdaten (z.B. ein neues Bundesland mit FSME-Risikokreisen, ein neues Land in ENDEMIC_REFERENCE) nicht automatisch in den entsprechenden Syndrom-Dateien auf, die weiterhin die alte, kuerzere Liste zeigen. Genau dieses Muster wurde bereits manuell gefunden (fsme.json fehlten mehrere echte Bundeslaender, dengue/ chikungunya/zika.json fehlte Deutschland komplett, obwohl Landkreise mit Tigermuecken-Vektor laengst in ENDEMIC_REFERENCE standen) -- dieses Skript soll verhindern, dass das ein zweites Mal nur durch Zufall auffaellt.

## Relevanz

Schliesst genau die Luecke, die zur manuellen Audit-Arbeit an den Syndrom-Dateien fuehrte -- ohne diesen Check bleibt der Sync zwischen Ausbruchsdaten und Syndrom-Dateien rein gedaechtnisbasiert.

## Methode

Zwei Pruefungen: (1) FSME-Spezialfall -- jeder Bundesland- Schluessel in FSME_RISIKOKREISE_BUNDESWEIT muss als Eintrag in fsme.json's endemic_regions vorkommen. (2) Allgemein -- fuer jeden syndrome_slug in ENDEMIC_REFERENCE (Tigermuecken-Eintraege eingeschlossen, da sie dort per Append landen) wird die Menge der vorkommenden Laender (country-Feld) gegen die endemic_regions-Liste der gleichnamigen JSON-Datei geprueft (nur wenn diese Datei existiert -- nicht jeder ENDEMIC_REFERENCE- Slug hat zwingend eine eigene Syndrom-Datei). Exakter String-Vergleich, kein Fuzzy-Matching -- entspricht damit exakt der Vergleichslogik in analyse_postinfectious_diagnose.py (`endemisch & visited_regions`, eine Mengen-Schnittmenge), sodass eine hier bestandene Pruefung auch tatsaechlich einen funktionierenden "Reise-Boost" bedeutet. Zusaetzlich ein informativer (nicht fehlschlagender) Lint-Hinweis auf ungewoehnlich lange endemic_regions-Eintraege (>40 Zeichen), die typischerweise mehrere Namen in einem String buendeln und dadurch nie exakt matchen koennen (dieselbe Bug-Klasse, die bereits mehrfach gefunden wurde) -- AUSSER der Eintrag ist eine exakte Kopie eines echten travel_history-Eintrags (dann ist er absichtlich personalisiert, kein Bug).

## Datenfluss

- **Liest:** `scripts/analysis/syndromes/*.json`, `ENDEMIC_REFERENCE`, `and`, `FSME_RISIKOKREISE_BUNDESWEIT`, `(import_outbreak_data.py)`, `~/.config/kyoro/health_config.json`, `(travel_history`, `fuer`, `den`, `Lint-Hinweis)`
- **Schreibt:**

  ```
  Keine (reiner Pruefbericht, kein Auto-Fix -- die Syndrom-Dateien
  enthalten handgeschriebene klinische Texte, die ein Skript
  nicht sicher automatisch bearbeiten sollte)
  ```

## Grenzen

Deckt nur `country`-Ebene ab, nicht bundeslandgenau fuer die Tigermuecken-/Endemie-Eintraege (nur FSME hat dafuer eine eigene Bundesland-Struktur in FSME_RISIKOKREISE_BUNDESWEIT) -- eine fehlende Bundeslandzeile bei Dengue/Chikungunya/Zika faellt also NICHT automatisch auf, nur ein komplett fehlendes Land. Der Lint-Hinweis auf lange Eintraege ist eine Heuristik (Zeichenlaenge), kein semantisches Verstehen -- kann sowohl echte Bugs uebersehen (kurzer, aber trotzdem gebuendelter String) als auch false positives liefern (lange, aber legitime Einzelbezeichnung).

## Aufruf

```bash
python3 scripts/utils/check_syndrome_endemic_regions.py
python3 scripts/utils/check_syndrome_endemic_regions.py --quiet
```
