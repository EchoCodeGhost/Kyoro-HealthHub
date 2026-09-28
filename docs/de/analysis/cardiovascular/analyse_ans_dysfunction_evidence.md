# Autonome-Dysfunktion-Evidenz — Bericht über compute_ans_dysfunction_evidence.py

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_ans_dysfunction_evidence.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Berichts-Gegenstueck zu compute/compute_ans_dysfunction_evidence.py: liest die dort geschriebene Tabelle `ans_dysfunction_evidence` und bereitet sie auf -- Jahresuebersicht, Verlauf, Liste der kritischen Tage mit Komponenten-Aufschluesselung, Kanal- Abdeckungspruefung und der Vergleich mit Polars eigenem naechtlichen ANS-Signal (Kontext, s. dortiger Docstring). Das compute-Skript selbst schreibt nur eine kurze Konsolen- Zusammenfassung -- alles hier war zuvor Ad-hoc-SQL waehrend der Entwicklung, jetzt als wiederverwendbares Skript.

## Relevanz

Macht den in compute_ans_dysfunction_evidence.py berechneten Verdachtsscore lesbar, statt ihn nur als Rohtabelle liegen zu lassen -- inkl. der Kontext-Vergleiche, die sonst bei jeder Nachfrage neu ad-hoc abgefragt werden muessten.

## Methode

Liest ausschliesslich aus `ans_dysfunction_evidence` (bereits berechnet von compute_ans_dysfunction_evidence.py -- dieses Skript berechnet nichts neu) und `polar_nightly_hrv` fuer den Kontext-Vergleich. Jahres-/Monatsuebersicht per SQL-GROUP BY. Kritische Tage: `level='critical'`, Komponenten aus der gespeicherten `components`-JSON-Spalte geparst und lesbar formatiert. Polar-Vergleich: Pearson r(score, ans_status) gepoolt UND pro Jahr (s. @limits -- der gepoolte Wert kann einen gemeinsamen Mehrjahres-Trend als Korrelation vortaeuschen, s. compute-Skript-Docstring fuer die schon gefundenen Werte). Kanal-Abdeckung: dieselbe Pruefung wie im compute-Skript (`_print_coverage_check()`), hier zusaetzlich als Report-Sektion, damit sie auch ohne Konsolenzugriff sichtbar ist.

## Berechnung

```
Berechnet nichts neu -- liest den fertigen Score aus
compute_ans_dysfunction_evidence.py::ans_dysfunction_evidence,
s. dortiges @scoring fuer die Formel (direct=max(...),
support=min(20,sum(...)), score=direct+support, max. 50).
```

## Datenfluss

- **Liest:** `ans_dysfunction_evidence`, `polar_nightly_hrv`
- **Schreibt:** `analyses/cardiovascular/ans_dysfunction_evidence_*.md (+ .png bei --plot)`

## Grenzen

Rein deskriptiv -- keine neue Statistik/Kriterien gegenueber dem compute-Skript, nur Aufbereitung. Der gepoolte Polar- Vergleich (mehrere Jahre zusammen) ist anfaellig fuer einen Scheinkorrelations-Effekt durch einen gemeinsamen Trend -- deshalb wird IMMER zusaetzlich die Pro-Jahr-Aufschluesselung gezeigt, nie nur der gepoolte Wert. Setzt voraus, dass compute_ans_dysfunction_evidence.py bereits gelaufen ist -- zeigt sonst eine leere Tabelle, rechnet nichts nach.

## Referenzen

- s. compute/compute_ans_dysfunction_evidence.py @refs (Sheldon 2015, ESC BP-dipping) -- cited there, not re-derived here.

## Aufruf

```bash
python3 analyse_ans_dysfunction_evidence.py
python3 analyse_ans_dysfunction_evidence.py --from 2023-01-01 --to 2023-12-31
python3 analyse_ans_dysfunction_evidence.py --plot
python3 analyse_ans_dysfunction_evidence.py --no-llm
```
