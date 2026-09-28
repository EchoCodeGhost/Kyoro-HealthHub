# check_no_memory_links — Enforces that private memory-link syntax never reaches

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_no_memory_links.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft alle .py- und .md-Dateien auf `[[...]]`-Wikilink-Syntax — das Referenzformat des privaten, projektexternen Memory-Systems (nicht Teil dieses Repos, nie eingecheckt). Ein solcher Link ist in einer öffentlich sichtbaren Datei immer ein Kopier-Artefakt: der Zielknoten existiert für Leser:innen des Repos nicht, und das Muster taucht ausschließlich auf, wenn privater Kontext ungefiltert in ein öffentliches Dokument übernommen wurde.

## Relevanz

Verhindert, dass private Memory-Referenzen (Notiznamen, die auf ein projektexternes, nicht eingechecktes System verweisen) in ein öffentliches Repo durchsickern — ein wiederkehrendes Muster bei KI-unterstützter Dokumentationsarbeit, bei der privater Chat- Kontext und öffentlicher Dateiinhalt sich vermischen können.

## Methode

Regex `\[\[[a-zA-Z_][a-zA-Z0-9_]*\]\]` auf git-getrackten Dateien (git ls-files) — beschränkt auf identifier-artigen Inhalt (Buchstabe/Unterstrich am Anfang, dann alphanumerisch), weil ein naiver `\[\[[^\[\]]+\]\]`-Blindscan echten Python-Code falsch trifft: Fancy-Indexing wie `arr[0][[0, -1]]` oder `df.spines[['top','right']]` sieht syntaktisch wie ein Wikilink aus, ist aber doppeltes eckiges-Klammern-Indexing. Echte Memory-Notiznamen in diesem Projekt sind durchgehend snake_case (z.B. `project_mission`, `clinic_multi_patient`) und matchen das enge Muster; `[0, -1]` oder `'top','right'` nicht. private/ gitignorte Verzeichnisse (intern/, data/, …) sind über git ls-files ohnehin nie enthalten. Exit-Code: 0 = sauber, 1 = Findings gefunden.

## Datenfluss

- **Liest:** `all`, `git-tracked`, `.py/.md`, `files`, `in`, `the`, `scanned`, `directory`
- **Schreibt:** `stdout (report and JSON output)`

## Grenzen

Erkennt nur die `[[...]]`-Syntax selbst, nicht andere Formen von ungefiltert übernommenem privaten Kontext (z.B. Personenbezug in Fließtext wie "The user professionally is ...") — dafür gibt es keine zuverlässige, false-positive-arme Regel; das bleibt Review-Aufgabe.

## Aufruf

```bash
python scripts/utils/check_no_memory_links.py
python scripts/utils/check_no_memory_links.py --dir docs
python scripts/utils/check_no_memory_links.py --json
```
