# Bevölkerungs-Hintergrundaktivität × Symptom-Korrelation

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/analyse_background_infection_activity.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Korreliert fünf bevölkerungsweite RKI/UBA-Hintergrundserien (GrippeWeb, ARE-Konsultationsinzidenz, RKI SurvStat, AMELAG-Abwasser, Notaufnahmesurveillance) mit der wöchentlichen Symptomlast aus dem eigenen Symptomtagebuch.

## Relevanz

Ermöglicht die objektive Einordnung der individuellen Symptomlast in den regionalen Infektionsgeschehen-Kontext, essentiell für die Abgrenzung zwischen individueller Erkrankung und bevölkerungsweiter Welle

## Methode

Spearman-Rangkorrelation + Lag-Analyse (0/-1/-2 Wochen, Symptom nach Hintergrundaktivität) je Hintergrundserie × wöchentliche Symptomlast. Symptomlast = Anzahl AKTIV VORHANDENER Symptome (value_num > 0) + deren Ø Schweregrad, NICHT rohe Zeilenzahl — strukturierte Tagebuch-Importe schreiben jedes abgefragte Feld als eigene Zeile auch wenn nichts vorlag (value_num=0), reines Zeilenzählen misst sonst den Fragebogen-Umfang statt der Symptomlast. Nicht-Symptom-Kategorien (Behandlung, Zyklus-Tracking, Medikation, ...) ausgeschlossen. Zusätzlich: direkter Soll-Ist-Vergleich objektiv dokumentierter Infektionsereignisse (clinical.events, type infection/reinfection) gegen die Hintergrundserien in derselben Woche — schärfer als die verrauschte Symptomtagebuch-Korrelation. Regionale Serie pro ISO-Woche aus der TATSÄCHLICHEN Aufenthaltsregion abgeleitet, nicht mehr fest aus der Heimatkoordinate (modules/geo_bundesland.py, kein hartkodiertes Bundesland): _build_weekly_region_map() bestimmt pro Tag die wahrscheinlichste Position (Priorität location_stays — automatisches Handy-GPS via Oura-App-Export, ab ca. 2026-05 verfügbar — vor cfg.location_for_date(), das travel_history/location_history aus der Config nutzt), verwirft Positionen außerhalb Deutschlands (kein deutsches Bundesland zutreffend, z.B. bei Auslandsreisen), und aggregiert per Mehrheitsvotum auf Wochenebene. Ohne Reisedaten für eine Woche fällt das automatisch auf die Heimatregion zurück — identisch zum alten Verhalten für den Normalfall "war die ganze Woche zuhause". Die bundesweite Serie ist immer zusätzlich enthalten, unabhängig von der Konfiguration, damit das Skript auch ohne location.lat/lon funktioniert.

## Berechnung

```
Korrelationsstärke: |ρ| <0.2 schwach | 0.2-0.4 moderat | 0.4-0.7 stark | >0.7 sehr stark
Lag: 0/-1/-2 Wochen (Symptom 0/1/2 Wochen nach Hintergrund-Peak)
```

## Datenfluss

- **Liest:** `outbreak_events`, `(source=rki_grippeweb`, `rki_are_konsultationsinzidenz`, `rki_survstat)`, `wastewater_amelag`, `ed_syndromic_surveillance`, `symptoms`, `location_stays`, `clinical.events`, `(config`, `type=infection/reinfection)`, `cfg.travel_history/location_history`, `(config`, `via`, `location_for_date)`
- **Schreibt:** `analyses/infectious/*.{md,png}`

## Grenzen

Rein observationelle Korrelation ohne Kausalitätsnachweis. RKI/UBA- Aggregatdaten sind bevölkerungsweite Schätzungen, keine individuelle Expositionsmessung. p<0.2-Berichtsschwelle liberaler als Standardniveau p<0.05 (erhöhte Falsch-Positiv-Rate). Keine Multiple-Testing-Korrektur bei Dutzenden gleichzeitig getesteten Serien-Paaren — "signifikante" Treffer bei p<0.2 sind bei dieser Anzahl an Vergleichen teils allein durch Zufall zu erwarten. Symptomtagebuch-Kategorisierung ist installationsspezifisch (_NON_SYMPTOM_CATEGORIES ist gegen die tatsächlich beobachteten Kategorien dieses Projekts kalibriert, nicht universell). Wochenweise Regionszuordnung ist Mehrheitsvotum über die Tage einer ISO-Woche, keine exakte Tageszuordnung pro Datenpunkt — bei gemischten An-/Abreise-Wochen kann das im Einzelfall ungenau sein. Bundesland-Zuordnung selbst ist Zentroid-Distanz (modules/geo_bundesland.py), kein echtes Polygon-Grenzmatching — grenznahe Aufenthalte können dem falschen Nachbar-Bundesland zugeordnet werden. location_stays deckt nur den Oura-App-Nutzungszeitraum ab (ab ca. 2026-05); außerhalb davon so genau wie die manuell gepflegten travel_history/location_history-Einträge.

## Referenzen

- Exner T, Flügel I, Greiner T, Lukas M, Obermaier N, Pütz P, Saravia CJ, Schattschneider A (2026). Wastewater surveillance: a national concept for Germany — a refined approach to surveillance site selection. Microorganisms, 14(6), 1197. doi:10.3390/microorganisms14061197
- Beach M, Corchis-Scott R, Geng Q, Podadera Gonzalez AM, Corchis-Scott O, Harrop E, et al. (2025). Wastewater-based surveillance of respiratory syncytial virus reveals a temporal disconnect in disease trajectory across an active international land border. Environment & Health, 3(4), 425-435. doi:10.1021/envhealth.4c00168
- Buda S, Tolksdorf K, Schuler E, Kuhlen R, Haas W (2017). Establishing an ICD-10 code based SARI-surveillance in Germany - description of the system and first results from five recent influenza seasons. BMC Public Health, 17(1), 612. doi:10.1186/s12889-017-4515-1

## Aufruf

```bash
python3 analyse_background_infection_activity.py
python3 analyse_background_infection_activity.py --plot
python3 analyse_background_infection_activity.py --no-llm
python3 analyse_background_infection_activity.py --from 2023-01-01
```
