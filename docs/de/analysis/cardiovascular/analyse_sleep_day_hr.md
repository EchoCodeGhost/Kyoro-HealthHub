# Schlaf- vs. Tag-Herzfrequenz-Vergleich

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_sleep_day_hr.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Vergleicht die durchschnittliche Herzfrequenz waehrend echter, geraetegestuetzter Schlafphasen mit der Herzfrequenz in den folgenden Wachstunden desselben Tages, ueber die gesamte Aufzeichnungsdauer hinweg. Ziel: sichtbar machen, ob/wann sich der normale Tag/Nacht-Abstand (Schlaf deutlich niedriger als Tag) verkleinert -- ein anerkanntes Zeichen fuer autonome Dysregulation (verminderte naechtliche parasympathische Erholung).

## Relevanz

Macht einen langfristigen autonomen Erholungstrend sichtbar, der sich mit dem klinisch dokumentierten EKG-Befund und dem Orthostase-Kandidaten-Trend (s. compute_orthostatic_detection.py) deckt -- eigenstaendige, methodisch unabhaengige Evidenzlinie.

## Methode

Schlaffenster: primaer Polar-Schlafsessions (sessions.type='sleep', id LIKE 'polar%') mit echtem ts_end -- geprueft gegen die anderen vorhandenen Quellen: Garmin-Schlafsessions haben in dieser DB durchgehend ts_start=Mitternacht und ts_end=NULL (reine Datums-Platzhalter, keine echten Zeitfenster), Oura hat zwar ts_end, aber nur ab Mai 2026 (zu kurze Historie fuer einen Verlaufsvergleich). Fuer Naechte OHNE Polar-Session (z.B. eine Phase, in der primaer ein anderes Geraet getragen wurde) Naeherungsfenster aus Apple Health 'sleep_analysis'-Stage-Samples, s. APPLE_SLEEP_GAP_HOURS/_derive_apple_sleep_nights() -- diese Naechte sind im Report separat als n(Apple) ausgewiesen, da sie KEIN vom Geraet selbst berechnetes Schlafintervall sind, sondern nur Min/Max der Sample-Zeitstempel je erkannter Nacht-Episode. Tagesfenster: die DAY_WINDOW_HOURS Stunden direkt nach dem Schlafende (ts_end), NICHT der volle Kalendertag -- vermeidet Ueberlappung mit der naechsten Schlafphase und haelt Schlaf-/Tagfenster fuer denselben Uebergang vergleichbar. Herzfrequenz aus measurements (metric='heart_rate'); sowohl fuer das Schlaffenster als auch fuer 'day_raw' ALLE Quellen (Polar, Apple, Garmin, Oura, ...) -- pro Minute aber ueber device_registry.collapse_concurrent() auf EIN Geraet reduziert, wenn mehrere gleichzeitig Werte melden (Regel B der cross-cutting-conventions-Spec: Prioritaets-Sieger statt Mittelung, sonst wuerden Zeitraeume mit mehr gleichzeitig getragenen Geraeten kuenstlich staerker gewichtet als Zeitraeume mit nur einem Geraet). 'day_rest' (Aktivitaets-gefiltert) dagegen NUR aus Samples, deren Quelle UND Minute tatsaechlich eine bestaetigte Schrittzahl hat -- aktuell Polar (per minutengenauer 'steps_1min'-Metrik, s. import_polar.py::import_polar_activity, Importer-Fix vom gleichen Tag wie dieses Skript) und Apple Health (dort 'steps' bereits minutengenau). Andere Quellen (Garmin, Oura, Bearable, Polar-Accesslink) liefern fuer 'steps' nachweislich nur einen Wert pro Kalendertag (keine Fensterbestaetigung moeglich) und tragen deshalb nur zu 'sleep' und 'day_raw' bei, nicht zu 'day_rest' -- ihre HF-Samples ohne Aktivitaetsbestaetigung werden NICHT als Ruhe angenommen (kein Default-Wert, s. STEPS_MINUTE_SOURCES/load_data()). 'day_raw' bleibt fuer alle Quellen ungefiltert und zeigt den Unterschied, den die Filterung macht. Ruhe-Schwelle STEPS_MAX Schritte/Minute (Default 10) angelehnt an den STEPS_MAX-Wert aus compute_orthostatic_detection.py, dort aber fuer ein enges Bestaetigungsfenster um einen HF-Sprung kalibriert -- hier bewusst nicht als validierter Wert zu verstehen, nur als plausible Ruhe-Grenze.

## Berechnung

```
Kein Evidenz-Score -- reine Kennzahlen-Gegenueberstellung
(Ø-HF Schlaf vs. Ø-HF Tagfenster, deren Differenz/Verhaeltnis).
Keine Punkte, keine Schwellen, kein Level. Fuer eine gescorte
Verdachtsbewertung s. compute_ans_dysfunction_evidence.py.
```

## Datenfluss

- **Liest:** `sessions`, `session_metrics`, `(auto_detected`, `distance_m)`, `measurements`, `(heart_rate`, `hrv_rmssd`, `steps`, `steps_1min`, `sleep_analysis`, `body_mass`, `body_weight`, `weight_kg)`
- **Schreibt:** `analyses/cardiovascular/sleep_day_hr_*.{md,png}`

## Grenzen

Heuristisch, kein validiertes klinisches Instrument. Das 12-Stunden-Tagesfenster ist eine Naeherung, kein exaktes Wach-Intervall (Aufwachzeit != Schlafende bei allen Naechten exakt gleich). Aktivitaetsfilterung nur fuer Polar/Apple moeglich (s. @method) -- 'day_raw' bleibt fuer alle Quellen ungefiltert und damit sport-konfundiert. Die Apple-Health- Naeherungsschlaffenster (n(Apple)-Naechte, s. @method) sind KEIN vom Geraet selbst berechnetes Schlafintervall, nur eine grobe Min/Max-Clusterung der Sample-Zeitstempel -- weniger praezise als die Polar-Sessions, deshalb separat ausgewiesen, nicht mit ihnen vermischt gewertet. Monate mit sehr wenigen Naechten (n<5) sind statistisch instabil, werden aber nicht automatisch ausgeblendet -- im Report an der n-Spalte erkennbar. Kein Kausalitaetsnachweis: der beobachtete Trend korreliert zeitlich mit anderen Befunden, beweist aber keinen Zusammenhang.

## Aufruf

```bash
python3 analyse_sleep_day_hr.py
python3 analyse_sleep_day_hr.py --plot
python3 analyse_sleep_day_hr.py --from 2020-01-01 --to 2022-12-31
python3 analyse_sleep_day_hr.py --steps-max 5
```
