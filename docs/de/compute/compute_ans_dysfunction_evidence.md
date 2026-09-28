# Autonome-Dysfunktion-Evidenz-Score — tageweise über die gesamte Historie

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_ans_dysfunction_evidence.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Berechnet fuer jeden Tag mit verfuegbaren Signalen einen Evidenz-Score fuer Verdacht auf autonome Dysfunktion, ueber die gesamte verfuegbare Historie (nicht nur "heute") -- Architektur 1:1 nach dem Vorbild von compute_af_evidence.py (AFES) uebernommen: direkte Evidenz (max der Kandidaten, nicht Summe, um Doppel- zaehlung eines einzelnen starken Signals zu vermeiden) plus gedeckelte, additive Stuetz-Evidenz.

## Relevanz

Historische, tageweise Verlaufsansicht der Verdachtsevidenz fuer autonome Dysfunktion -- Ergaenzung zu analyse_ans_battery.py (Korrelationen + aktuellster Stand je Kanal), das bewusst keinen taeglichen Evidenz-Score fuehrt.

## Methode

Direkte Evidenz (validierte externe Kriterien, nicht neu hergeleitet): - Orthostatischer Kandidat ΔHF≥OI_HR_THRESHOLD (Sheldon 2015 POTS-Kriterium, s. compute_clinical.py) an dem Tag -> 30 Pkt. (hoechste Gewichtung von den dreien -- einziges mit einem benannten klinischen Syndrom-Kriterium dahinter), grenzwertig (OI_HR_BORDERLINE bis <THRESHOLD) -> 15 Pkt. - Naechtlicher HF-Abfall <5% (in compute_af_evidence.py:: load_hr_nightdip() bereits als "autonome Dysregulation"- Schwelle dokumentiert, hier fuer denselben Signaltyp wiederverwendet, nicht neu erfunden) -> 15 Pkt., <10% (Non- Dipper) -> 8 Pkt. - Naechtliches BP-Non-/Reverse-Dipping (ESC-Kriterien, s. analyse_bp_sleep.py::_dipping_class()): Reverse-Dipper (<0%) -> 15 Pkt., Non-Dipper (0-10%) -> 8 Pkt. direct_pts = max(...) dieser drei Kandidaten pro Tag. Stuetz-Evidenz (graduelle Abweichung von der eigenen personal_baseline, s. modules/baseline.py -- kein absoluter klinischer Grenzwert, deshalb niedriger gewichtet): - HRV (RMSSD) < -50% ggue. Baseline -> 10 Pkt., < -30% -> 5 Pkt. - Ruhe-HF > +20% ggue. Baseline -> 10 Pkt., > +10% -> 5 Pkt. - Atemstoerung, geraeteagnostisch (Apple sleep_breathing_ disturbances >1.0/h=5/>0.7/h=2, Oura breathing_disturbance_ index >10=5/>5=2, Sleep Cycle breathing_disrupt >15=5/>10=2 -- alle drei Schwellenpaare 1:1 aus compute_af_evidence.py uebernommen, nicht neu erfunden; Polar liefert dafuer nachweislich keine Daten, s. Coverage-Check in main()). - SpO2 < 92% -> 10 Pkt., < 94% -> 5 Pkt., NUR naechtliches Minimum (measurements.metric='sleep_spo2_min' aus compute_sleep_spo2.py -- Garmin/Apple/Wellue O2Ring; Oura/ Polar/Beurer/Withings bewusst nicht darin enthalten, s. dortiger Docstring: kein echter Nachtwert ableitbar). Bei mehreren Quellen fuer dieselbe Nacht: EIN Gewinner nach spo2_priority() (Regel B, device_registry.py), NICHT MIN() ueber alle Quellen -- MIN() wuerde ein verrauschtes Geraet durch einen zufaelligen Ausreisser systematisch "gewinnen" lassen, s. _load_spo2(). Bewusst auf die Nacht beschraenkt statt Tagesmittel (frueherer Stand: daily_context.spo2_avg_pct) -- Kyoro hat fuer SpO2 keine durchgehende Tagesabdeckung bei keinem Geraet, ein Ganztages-Kriterium waere fast immer leer gewesen. Schwelle 1:1 aus compute_af_evidence.py:: _load_spo2() uebernommen. support_pts = min(20, Summe). score = direct_pts+support_pts (max. 50 -- deutlich weniger als AFES' 100, da hier nur 3 direkte + 4 Stuetz-Kriterien einfliessen statt ~20; LEVELS- Schwellen deshalb proportional auf diese kleinere Skala herunterskaliert, s. Kommentar bei LEVELS im Code, NICHT 1:1 von AFES uebernommen). KONTEXT (nicht gescort, nur informativ im components-JSON mitgefuehrt): Dekonditionierung (Alltagsaktivitaet/met_minutes ggue. eigener Baseline -- URSPRUENGLICH als Stuetzkriterium gescort, nach Nutzerinnen-Einwand korrigiert: im Unterschied zu den uebrigen Kriterien misst Aktivitaet nur VERHALTEN, nicht die ANS-Funktion selbst -- niedrige Aktivitaet kann aus Dysfunktion folgen, aber genauso aus jedem anderen Grund; zusaetzlich empirisch bestaetigt: ueberlappte als Stuetzkriterium an 41.5% der relevanten Naechte mit hrv_low, vermutlich Doppelzaehlung desselben Phaenomens, s. _load_deconditioning_context()); Zyklustag (cycle_day, kein ANS-Symptom, sondern moeglicher Modulator ueber Oestrogen/Progesteron-Wirkung auf Baroreflex- Sensitivitaet); Progesteron:Oestradiol-Verhaeltnis und eGFR aus medicine.db::lab_manual, jeweils dem naechstgelegenen Score-Tag zugeordnet (±30 Tage) -- beides punktuelle Laborwerte ohne etablierten ANS-Tages-Cutoff, deshalb bewusst nicht gescort. Polars eigenes naechtliches ANS-Signal (polar_nightly_hrv: ans_status, ans_rate, recovery_indicator/-sublevel, rmssd_ms/rri_ms/respiration_ms je ggue. Polars eigener baseline_*-Berechnung, s. _load_polar_nightly_context()) -- nach Pruefung bewusst NICHT gescort: ans_status korreliert nur schwach mit diesem Score (r=-0.072, n=941, p=0.028, praktisch vernachlässigbarer Effekt trotz statistischer Signifikanz), ans_rate ist nachweislich nur eine 5-stufige Rundung von ans_status (identische schwache Korrelation), und beide sind ein unveroeffentlichter, proprietaerer Polar-Algorithmus ohne externe klinische Validierung -- anders als die uebrigen Kriterien hier (Sheldon 2015, ESC). Nur als Kontext/Vergleich mitgefuehrt, um Polars eigenes System und unseres bei Bedarf gegeneinander abzugleichen. WICHTIG: personal_baseline speichert nur EINEN aktuellen Baseline-Snapshot pro Metrik (keine Zeitreihen-Baseline) -- historische Tage werden also gegen dieselbe, aus einer spaeteren Phase berechnete Baseline verglichen, nicht gegen eine fuer den jeweiligen Zeitpunkt passende. Zeilen mit unplausiblem n_days (s. Fund zu compute_personal_baseline.py, analyse_ans_battery.py:: _baseline_n_days_plausible()) werden uebersprungen statt eine falsche Abweichung zu berechnen.

## Berechnung

```
direct  = max(Orthostatic=30/15, NightHRDip=15/8, BPDipping=15/8)
support = sum(HRV_low=10/5, RHR_high=10/5, Breathing=5/2, SpO2=10/5)
          capped at 20
score   = direct_pts + support_pts  (max 50)
```

## Datenfluss

- **Liest:** `sessions`, `session_metrics`, `(type='orthostatic')`, `daily_context`, `personal_baseline`, `blood_pressure`, `(via`, `analyse_bp_sleep.py)`
- **Schreibt:** `ans_dysfunction_evidence`

## Grenzen

BEWUSST kein Ersatz fuer eine klinische Diagnostik (Schellong- Test, Kipptisch, 24h-BP-Messung, formale HRV-Analyse). Die drei direkten Kriterien sind einzeln validiert, ihre Kombination zu EINEM Score (max/Summe/Deckelung) ist eine projektinterne Heuristik, keine in der Literatur validierte Kombinationsregel -- analog zu AFES, dort mit derselben Einschraenkung dokumentiert. Baseline-Vergleich ist retrospektiv gegen eine einzelne, spaeter berechnete Baseline (s. @method), nicht zeitpunktgenau. Tage ohne jedes Signal bekommen keinen Eintrag (nicht score=0 als "unauffaellig" missverstehen -- s. signals_used-Spalte). Keine Multiple-Testing-Korrektur. Score < absichtlich ausgelassenes Kanal (z.B. Symptomtagebuch, Sportkardiologie- Belastungsdaten) -- kann bei zukuenftiger Erweiterung ergaenzt werden.

## Referenzen

- Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus
- Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029 (cited via compute_clinical.py, not re-derived).
- ESC 2024 nocturnal BP dipping criteria (cited via analyse_bp_sleep.py, not re-derived).

## Aufruf

```bash
python3 compute_ans_dysfunction_evidence.py
python3 compute_ans_dysfunction_evidence.py --recompute
python3 compute_ans_dysfunction_evidence.py --from 2023-01-01 --to 2023-12-31
```
