# sleep_norms.py — Einheitliche Normbereiche für Schlafstadien (Tiefschlaf, REM)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/sleep_norms.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Stellt EINEN gemeinsamen, zitierten Satz Normbereiche für Tiefschlaf- (N3) und REM-Anteil an der Gesamtschlafzeit bereit, den alle Analyse-Skripte verwenden, statt jeweils eigene (und widersprüchliche) Werte zu pflegen.

## Relevanz

Tiefschlaf- und REM-Anteil sind etablierte Marker für Schlafqualität und -architektur; ein einheitlicher, zitierter Normbereich verhindert, dass derselbe gemessene Wert je nach Skript unterschiedlich (und teils widersprüchlich) bewertet wird.

## Methode

Reine Konstanten, keine Berechnung. Vor dieser Zusammenführung verwendete analyse_sleep_stages.py 13–18 % (Tiefschlaf) / 18–23 % (REM), analyse_sleep_respiration.py dagegen 15–25 % / 20–25 % für denselben Sachverhalt — zwei Bewertungen desselben Befunds. Die hier festgelegten Bereiche (Tiefschlaf 13–23 %, REM 18–25 %) sind so gewählt, dass der empirische Populationsmittelwert aus der bislang größten PSG-Metaanalyse gesunder volljähriger Personen (Boulos et al. 2019, n=5273: Tiefschlaf 20,4 %, 95%-CI 19,0–21,8 %; REM 19,0 %, 95%-CI 18,5–19,6 %) innerhalb des Bereichs liegt — insbesondere die REM- Untergrenze wurde deshalb bewusst auf 18 % (statt der in älteren Lehrbuchangaben kursierenden 20 %) gesetzt: ein Normbereich, der den empirisch gemessenen Populationsmittelwert selbst ausschließt, ist per Definition falsch kalibriert.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Boulos et al. 2019 berichtet die 95%-CI des gepoolten Populations- MITTELWERTS über Studien hinweg, nicht die Streuung zwischen Individuen/Nächten — als individuelles Prognoseintervall wäre dieser CI-Bereich zu eng. Die hier definierten Bereiche sind deshalb bewusst breiter als die CI und dienen dem Vergleich eines über mehrere Nächte gemittelten persönlichen Werts gegen den Populationsschnitt, nicht der Bewertung einer einzelnen Nacht. Wearable-Schlafstaging (Apple Watch, Oura) hat zudem geringere Genauigkeit als die PSG, auf der Boulos et al. 2019 basiert.

## Referenzen

- Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019). Normal polysomnography parameters in healthy adults: a systematic review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543. doi:10.1016/S2213-2600(19)30057-8 (Tabelle 2 der Publikation: Tiefschlaf/N3 20,4 % [95%-CI 19,0-21,8 %], REM 19,0 % [95%-CI 18,5-19,6 %], Gesamtstichprobe n=5273 gesunde volljährige Personen, 108-158 gepoolte Kontrollgruppen je Parameter.)

## Aufruf

```bash
from modules.sleep_norms import (
    DEEP_NORM_MIN, DEEP_NORM_MAX, REM_NORM_MIN, REM_NORM_MAX,
)
```
