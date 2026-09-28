# anamnese_interview.py — LLM-geführtes Anamnese-Interview

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/query/anamnese_interview.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Führt ein offenes, LLM-geführtes Interview über sechs Tracks: Expositions-/Reisegeschichte, Tierkontakt, Familienanamnese, beruflicher Werdegang & Expositionen, Freizeit & Hobbies, Sozialanamnese (Rauchen/E-Zigaretten/Substanzkonsum/Sexualanamnese). Das Modell fragt assoziativ nach, wenn eine Aussage eine bekannte epidemiologische/genetische Verbindung hat. Sitzungen sind über mehrere Sitzungen hinweg fortsetzbar.

## Relevanz

Ermöglicht die Durchführung von Anamnese-Interviews, essentiell für die klinische Datenerhebung

## Methode

1) Track-Auswahl oder Sitzungsfortsetzung, 2) LLM-Provider initialisieren (lokal oder remote), 3) Gesprächsverlauf mit inkrementeller Extraktion strukturierter Befunde, 4) Sitzungsstatus und Transkript persistent speichern, 5) Review-Export als Markdown.

## Datenfluss

- **Liest:** `health.db`, `(anamnese_sessions`, `anamnese_findings)`
- **Schreibt:** `health.db (anamnese_sessions, anamnese_findings)`

## Grenzen

Erfordert Python 3.10+. Sitzungen mit Remote-Provider zeigen eine Warnung an (Datenübertragung). Extraktion ist unverifiziert und muss manuell überprüft werden.

## Aufruf

```bash
python3 scripts/query/anamnese_interview.py --track exposure
python3 scripts/query/anamnese_interview.py --track social --lang en
python3 scripts/query/anamnese_interview.py --resume <session_id>
python3 scripts/query/anamnese_interview.py --export <session_id>
```
