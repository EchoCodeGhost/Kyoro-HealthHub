# check_commit_message_privacy — Blocks personal data in commit messages

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_commit_message_privacy.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft eine Commit-Message auf konkrete, aus der echten Gesundheits-/ Gerätedatenbank abgelesene persönliche Werte (Prozentsätze, Zeilenzahlen, Messwerte mit klinischer Einheit, exakte Daten, Monat+Jahr-Zeiträume) — Commit-Messages sind in diesem öffentlichen Repo genauso einsehbar wie Code, ein Bugfix-Kommentar darf den Mechanismus erklären, aber keine konkreten Zahlen aus der eigenen Krankengeschichte/Gerätehistorie zitieren.

## Relevanz

Verhindert, dass konkrete persönliche Gesundheits-/Gerätewerte über Commit-Messages in die öffentliche Repo-Historie gelangen

## Methode

Wortnahe Regex-Muster, analog zu check_no_dates.py: Dezimal-Prozentsatz, Dezimalwert mit klinischer/technischer Einheit (mg/dl, mmol, ms, bpm, min, kg, km/h, dB, °C, ml/kg/min), "N Zeilen/rows/entries/Werte/Tage betroffen", exaktes ISO-Datum, Monatsname+Jahr. Zeilen mit Zitat-Signalwörtern (doi:, WHO, AWMF, guideline, Leitlinie, et al., …) sind ausgenommen — externe Referenzwerte aus medizinischer Literatur sind Domäneninhalt, kein personenbezogener Befund.

## Datenfluss

- **Liest:** `commit`, `message`, `text`, `(file`, `path`, `or`, `stdin)`
- **Schreibt:** `stdout (report), process exit code`

## Grenzen

Heuristisch, nicht erschöpfend — ungewöhnliche Formulierungen können durchrutschen oder legitime technische Werte (z.B. ein Schwellenwert im Code selbst) fälschlich anschlagen. Prüft nur die Message, nicht den Diff — ein Fund heißt nicht zwingend, dass der referenzierte Wert aus echten persönlichen Daten stammt, nur dass er verdächtig aussieht.

## Aufruf

```bash
python scripts/utils/check_commit_message_privacy.py .git/COMMIT_EDITMSG
echo "some message" | python scripts/utils/check_commit_message_privacy.py -
```
