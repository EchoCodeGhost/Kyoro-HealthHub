<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Langzeit-HRV-Monitoring mit Brustgurt — Protokoll

> **English version:** [HRV_MONITORING_PROTOCOL.md](HRV_MONITORING_PROTOCOL.md)

**Zweck:** Eine belastbare persönliche HRV-Baseline etablieren und autonome
Muster (Tag/Nacht, Belastung/Erholung, Arrhythmie-Fenster) dokumentieren —
Grundlage für AFib-Risikobewertung (s. [AFES.md](AFES.md)) und für
Long-COVID-/ME-CFS-/autonome-Dysfunktions-Verlaufskontrolle.

Beat-to-beat-Brustgurtdaten (RR-Intervalle) sind die Datenquelle für mehrere
AFES-Komponenten (`h10_dfa`, `h10_poincare`, `h10_sampen`, `h10_turning`,
`h10_preaf` — s. [AFES.md](AFES.md#device-policy)). Dieses Protokoll
beschreibt, wie man diese Daten so aufnimmt, dass sie auswertbar sind.

---

## Geräteauswahl: Kurzaufnahme vs. autarke Langzeitaufnahme

| Eigenschaft | Brustgurt ohne internen Speicher (z.B. Polar H7) | Brustgurt mit internem Speicher (z.B. Polar H10) |
|---|---|---|
| Ohne Handy aufnehmen | ❌ nicht möglich | ✅ Knopfdruck → autark, bis zu mehreren Tagen |
| Handy muss die ganze Zeit in Reichweite bleiben | Ja | Nein |
| EKG-Qualität (beat-to-beat) | ✅ | ✅ |
| Einsatz | Kurzaufnahmen (24h), Handy verfügbar | Langzeit (mehrere Tage), autark |

**Kurzaufnahme (kein interner Speicher):** Aufzeichnungs-App auf dem Handy starten (z.B. Polar Beat oder vergleichbar), Gurt anlegen und anfeuchten, App läuft im Hintergrund, Handy muss in Bluetooth-Reichweite bleiben (~10m). Für 24h-Sessions praktikabel, wenn das Handy konsequent dabei ist.

**Langzeitaufnahme (interner Speicher):** Knopf drücken → interne Aufnahme startet, kein Handy nötig. Nach Ende der Trageperiode über die zugehörige App synchronisieren.

---

## Phasenkonzept

Eine einzelne Momentaufnahme ist wenig aussagekräftig — zwei Phasen liefern einen echten Vergleich:

### Phase 1 — Kurzer Testlauf (24h)

**Zweck:** Gerät und Workflow testen, Tragekomfort einschätzen, erste Orientierung.

Falls dieser Testlauf während einer untypischen Phase stattfindet (z.B. kurz nach einer Erkältung, im Urlaub, nach ungewöhnlicher Anstrengung): Ergebnis nur als groben Orientierungswert werten, nicht als Baseline. Solche Einflüsse (Infekt, Urlaubserholung) überlagern sich und lassen sich im Nachhinein nicht sauber trennen.

### Phase 2 — Alltags-Baseline (5–7 Tage)

**Zweck:** Echte Alltags-Baseline für Verlaufsmonitoring.

**Wann:** Mindestens 5–7 Tage nach vollständiger Symptomfreiheit von akuten Infekten; eine normale Woche ohne außergewöhnliche Belastungen oder Ausnahmesituationen (kein Urlaub, keine ungewohnt intensive Aktivität).

**Sport während Phase 2 nicht vermeiden:** Die post-exertionelle HRV-Reaktion (Erholungsverlauf der HRV nach Belastung) ist einer der klinisch wertvollsten Datenpunkte für autonome Dysfunktion und PEM (Post-Exertional Malaise) — ohne Belastung während der Aufnahme fehlt genau dieses Signal. Beim Training: Gurt kurz abnehmen, danach sofort wieder anlegen (kurze Datenlücke ist unproblematisch, die interessanten Daten kommen in den 2–6 Stunden danach). Trainingszeiten zusätzlich notieren, für spätere Korrelation.

**Ablauf (beide Phasen):**
1. Gurt anlegen, Aufnahme starten (Knopfdruck bei Langzeitgerät, oder App-Start bei Kurzaufnahme)
2. Tragen: Duschen ist meist unproblematisch (Wasserdichtigkeit je nach Gerät prüfen), beim Schlafen tragen, Gurt täglich 1–2 cm verschieben (Hautreizung vermeiden), Elektroden anfeuchten oder Gel für besseres Signal
3. Nach Ende der Periode: über die App synchronisieren
4. Daten importieren: `python3 scripts/import_all.py --update`
5. Standard-Pipeline weiterlaufen lassen: `python3 scripts/compute_all.py`

**Folgemessungen:** Nach der ersten Baseline-Messung alle 3–6 Monate wiederholen, besonders nach Infekten, Therapiebeginn oder Aktivitätsveränderungen, um den Verlauf zu dokumentieren.

---

## Was die Analyse zeigt

Nach `compute_all.py` stehen folgende Auswertungen zur Verfügung:

- **AFES-Score** (s. [AFES.md](AFES.md)) — inkl. der Brustgurt-spezifischen Komponenten `h10_dfa`, `h10_poincare`, `h10_sampen`, `h10_turning`, `h10_preaf`
- **HRV-Verlauf mit Ereignismarkern:** `python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py`
- **Orthostase-Auswertung** (falls parallel ein Schellong-Test gemacht wurde): s. [ORTHOSTATIC_TEST_PROTOCOL_DE.md](ORTHOSTATIC_TEST_PROTOCOL_DE.md)

### Interpretationshilfen

| Beobachtung | Bedeutung |
|---|---|
| RMSSD nachts deutlich höher als tagsüber | Gesundes autonomes Nervensystem |
| RMSSD nachts ≈ tagsüber | Autonome Dysfunktion (z.B. bei Long COVID, ME/CFS häufig) |
| Ruhepuls im Schlaf < 60 bpm | Gute kardiovaskuläre Fitness |
| Ruhepuls im Schlaf > 75 bpm | Erhöhte sympathische Aktivierung |
| **Arrhythmie-Fenster** (Stunden mit CV-RR > 0.15, also hoher Schlag-zu-Schlag-Variationskoeffizient) nachts | Mögliche Schlafapnoe-assoziierte Reaktion |
| Arrhythmie-Fenster nach Aktivität | Post-exertionelle Reaktion |
| RMSSD-Unterschied zwischen zwei Phasen > 5 ms | Klinisch beachtenswert |
| Ruhepuls-Unterschied zwischen zwei Phasen > 5 bpm | Klinisch beachtenswert |

**Methodische Einschränkung bei Phase-1-vs-Phase-2-Vergleichen:** Wenn Phase 1 während einer untypischen Zeit (Erkältung, Urlaub) stattfand, überlagern sich zwei Effekte (Erholung vom Infekt + Urlaubs-Erholung) und lassen sich nicht sauber trennen. Für einen methodisch sauberen Vergleich sind drei Phasen ideal: gesund+Urlaub, krank+Urlaub, gesund+Alltag — in der Praxis meist nur über mehrere Messzyklen hinweg erreichbar.

---

## Für den Kardiologen / Neurologen

Mitbringen:
- Rohdaten (RR-Intervall-Zeitreihe) für den relevanten Zeitraum
- AFES-Verlauf und auffällige Komponenten
- HRV-Verlaufsdiagramm mit Ereignismarkern (`analyse_hrv_verlauf.py`)
- Ergebnisse von Orthostase-Tests, falls parallel durchgeführt
