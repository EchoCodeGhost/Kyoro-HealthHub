# orthostatic_test — Geführter Orthostase-Test (modifizierter Schellong-Test)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/orthostatic_test.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Führt einen geführten Orthostase-Test durch — oder wertet einen bereits anderweitig aufgezeichneten Test aus (--evaluate, z.B. eine manuell mit ECGLogger erfasste Sitzung, optional mit --auto-detect ohne manuelle Zeiteingabe) — und speichert die Ergebnisse in sessions/session_metrics (type='orthostatic', source_app='guided_test'), derselben Zielstruktur wie die echten Polar-Tests und die heuristische Kandidaten-Erkennung, damit analyse_orthostatic.py sie einheitlich sieht. Implementiert einen modifizierten Schellong-Test: 10 Minuten Liegen, 10 Minuten Stehen. Datenquellen: Primär ppi_raw (RR-Intervalle von H10/H7 für exakte RMSSD-Berechnung), Fallback: measurements mit metric='heart_rate' (HR-Werte, RMSSD näherungsweise). Zusätzlich, geräteagnostisch und optional (nur falls im Zeitfenster vorhanden): SpO2 aus measurements (z.B. Wellue O2Ring) und Blutdruck aus blood_pressure (z.B. Withings BPM Core) — jedes Gerät, das parallel zur H10-Aufzeichnung lief, fließt automatisch mit ein.

## Relevanz

Ermöglicht orthostatische Tests und Analysen, essentiell für die kardiovaskuläre Diagnostik

## Methode

Interaktiver Modus: Zeigt Anleitung mit ASCII-Art, führt durch die Testphasen mit Countdown-Timer. Bewertungsmodus (--evaluate): Manuelle Eingabe von Zeitfenstern — liest, wie der geführte Modus, aus bereits importierten ppi_raw/measurements-Daten, egal aus welchem Importer sie stammen (ECGLogger, HRV Logger, Polar, ...). Mit --evaluate --auto-detect: statt exakter Zeiten nur ein grobes Suchfenster nötig — der Aufsteh-Moment wird über dieselbe Sprung- Heuristik wie compute_orthostatic_detection.py gefunden (scharfer, anhaltender HF-Anstieg ≥HR_JUMP_MIN bpm, dieselbe Funktion importiert, nicht neu implementiert), Liegephase = REF_WINDOW_S davor, Stehphase = 10 Min danach (oder bis Suchfenster-Ende). Alle Nutzereingaben/datetime.now() sind lokale Wanduhrzeit und werden vor jeder DB-Abfrage nach UTC konvertiert (ppi_raw/measurements/ blood_pressure/sessions.ts_start sind projektweit UTC gespeichert) — nur für Anzeige/Print wird gezielt zurück nach lokal konvertiert. Berechnet: hr_supine, hr_stand, hr_stand_peak, hr_delta, rmssd_supine, rmssd_stand, rmssd_delta, und falls vorhanden spo2_supine_avg/min, spo2_stand_avg/min, bp_supine_sys/dia_avg, bp_stand_sys/dia_min, bp_drop_sys/dia. Bewertung: POTS-Kriterium (ΔHR), orthostatische Hypotonie (RR-Abfall ≥20/10mmHg falls Blutdruckdaten vorhanden), SpO2-Abfall <92% im Stehen. Vergleich mit persönlicher Baseline (Ø aller früheren guided_test-Sessions DERSELBEN Person, nicht mit echten Polar-Tests oder ppi_detected-Kandidaten vermischt) nach 2+ Tests. Speichert Ergebnisse in sessions/session_metrics und als Markdown-Datei.

## Berechnung

```
Bewertungs-Score basierend auf Herzfrequenzänderung (ΔHR) und HRV-Reaktion
```

## Datenfluss

- **Liest:** `health.db.ppi_raw`, `health.db.measurements`, `health.db.blood_pressure`, `health.db.sessions`, `health.db.session_metrics`
- **Schreibt:** `health.db.sessions, health.db.session_metrics, analyses/orthostatic/*.md`

## Grenzen

Heuristische Methode: Benötigt ausreichend Messwerte (≥2 pro Phase) für valide Ergebnisse. RMSSD aus HR-Werten ist nur eine Näherung. Dient nur der Selbstbeobachtung, kein medizinisches Gerät. --person wird jetzt tatsächlich bis zu den Schreibpfaden durchgereicht (vorher deklariert, aber ignoriert — beide Schreib-/Vergleichspfade hingen fest an OWN_PERSON_ID) — wichtig bei geteilten Geräten, wo die Geräte-ID allein nichts über die Person aussagt. --auto-detect findet nur EINEN Kandidaten pro Suchfenster (den mit dem größten ΔHR) — bei mehreren Lagewechseln im Fenster (z.B. mehrere Steh-Tests hintereinander) das Suchfenster entsprechend eng wählen. Blutdruckwerte fließen als Ø (liegend) bzw. Minimum (stehend) ein, nicht als Zeitreihe — für die vollständige Messreihe mit Einzelzeitstempeln direkt in blood_pressure nachschauen.

## Referenzen

- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183

## Aufruf

```bash
python scripts/utils/orthostatic_test.py
python scripts/utils/orthostatic_test.py --evaluate
python scripts/utils/orthostatic_test.py --evaluate --auto-detect
python scripts/utils/orthostatic_test.py --notes "Test nach Mittagessen"
python scripts/utils/orthostatic_test.py --evaluate --person PER-xxxxxxxx
# Geführter Test: Interaktive Anleitung mit Countdown
# --evaluate: Nachauswertung bestehender Daten (manuelle Zeitfenstereingabe) —
#   funktioniert mit jeder bereits importierten Quelle (ECGLogger, HRV Logger, ...)
# --evaluate --auto-detect: wie --evaluate, aber Aufsteh-Zeitpunkt automatisch
#   aus H10-HF-Sprung gefunden — nur grobes Suchfenster statt exakter Zeiten
# --notes: Freitext-Notiz zum Test
# --person: Person-ID für Test (Standard: eigene Person) — wichtig bei
#   geteilten Geräten, wird jetzt tatsächlich bis zum Schreibpfad durchgereicht
```
