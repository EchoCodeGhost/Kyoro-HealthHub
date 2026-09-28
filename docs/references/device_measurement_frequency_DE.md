# Wearables — Messfrequenz & HRV-Fähigkeiten

Generische Geräte-Fähigkeiten (Herstellerangaben/öffentliche Spezifikationen),
keine persönlichen Messdaten. Empirische Validierungsbefunde aus eigenen
Daten stehen in `docs/references/device_validation.md` (nur aggregierte
Kennzahlen wie Korrelationen, keine Rohwerte) bzw. bleiben, wo sie
Rohmesswerte enthalten, lokal in `intern/` (nicht Teil dieses Repos).

---

## Glossar: HRV, RMSSD, SDNN

**HRV (Herzratenvariabilität)** — Oberbegriff: die Schwankung der Zeitabstände
zwischen aufeinanderfolgenden Herzschlägen. Kein einzelner Wert, sondern eine
ganze Familie von Kennzahlen (RMSSD, SDNN, LF/HF, pNN50, ...), die
unterschiedliche Aspekte dieser Schwankung einfangen.

**RMSSD** (Root Mean Square of Successive Differences) — Kurzzeit-HRV-Kennzahl:
Differenz zwischen jeweils zwei benachbarten Schlag-Intervallen, quadriert,
gemittelt, Wurzel gezogen. Erfasst fast ausschließlich **parasympathische
(vagale) Aktivität** (respiratorische Sinusarrhythmie — der Vagusnerv moduliert
die Herzfrequenz im Atemrhythmus, das ist schnell genug, um RMSSD zu erzeugen;
der Sympathikus reagiert dafür zu träge). Deshalb der Standard-Marker für
"wie stark bremst der Vagus gerade". Höher = mehr vagale Aktivität, in Ruhe
meist "besser" (Erholung). Sinkt normalerweise beim Aufstehen (vagale
Rücknahme) — ein übermäßiger Abfall, gekoppelt mit einem starken HF-Sprung,
ist das Muster, nach dem heuristische Orthostase-Detektion sucht.

**SDNN** (Standard Deviation of NN Intervals) — Gesamtvariabilität aller
Schlag-Intervalle in einem Messfenster. Erfasst sowohl kurzfristige
(vagale) als auch langsamere Einflüsse (Thermoregulation, Hormonzyklen,
zirkadiane Rhythmik, Sympathikus) — weniger spezifisch für den Vagus als
RMSSD, dafür ein umfassenderes Bild der Gesamt-Anpassungsfähigkeit des
Systems. Wird oft für längere Messfenster (z.B. 24h) verwendet, RMSSD eher
für kurze Fenster (5 Min., eine Nacht). Nicht 1:1 austauschbar mit RMSSD,
auch wenn beide "HRV" heißen — unterschiedliche physiologische Anteile.
Ein Gerät, das nur SDNN liefert, ist deshalb nicht direkt gegen ein Gerät
vergleichbar, das nur RMSSD liefert, ohne Umrechnung oder getrennte
Betrachtung.

---

## Vergleichstabelle: Herzfrequenz & HRV

| Gerät | HR passiv (Alltag) | HR aktiv (Sport) | HRV-Messung | HRV-Metrik | HRV durchgängig? |
|---|---|---|---|---|---|
| Polar H10 (Brustgurt) | Beat-to-beat RAW (RR-Intervalle, ms) | Beat-to-beat RAW | Jederzeit bei Aufnahme | RMSSD | Nur bei aktiver Aufnahme |
| Polar H7 (Brustgurt) | Beat-to-beat RAW (RR-Intervalle, ms) | Beat-to-beat RAW | Jederzeit bei Aufnahme | RMSSD | Nur bei aktiver Aufnahme |
| Polar Loop | 1s kontinuierlich | 1s kontinuierlich | Nightly Recharge (Schlaf) | RMSSD | Nein (nur Schlaf) |
| Polar Ignite 2 | 1s kontinuierlich | 1s kontinuierlich | Schlaf (5-Min.-Fenster) | RMSSD | Nein |
| Polar Vantage V3 | 1s kontinuierlich | 1s kontinuierlich | Schlaf (5-Min.-Fenster) | RMSSD | Nein |
| Polar M430 | 1s kontinuierlich | 1s kontinuierlich | — | — | Nein |
| WHOOP 4.0/5.0 | ~100ms (10 Hz) | ~100ms (10 Hz) | Nur Schlaf (5-Min.-Fenster) | RMSSD | Nein |
| Oura Ring 4 | 5s kontinuierlich (API-Export); intern 1s PPG (nicht exportiert) | — (kein Sport-Modus) | Schlaf (5-Min.-Fenster) | RMSSD | Nein (nur Schlaf) |
| Garmin Fenix 6 Pro | ~alle 2 Min. | ~alle 2 Sek. | Erste 5h Schlaf | RMSSD | Nein |
| Apple Watch S9 | ~75s passiv (gemessen; variiert 75–225s) | 1s (Workout aktiv) | ~alle 2h | SDNN | Nein |
| Fitbit Sense 2 / Charge 6 | ~alle 1 Min. | ~alle 1 Min. | Nur Schlaf | RMSSD | Nein |
| Samsung Galaxy Watch 6/7 | ~alle 1 Min. | ~alle 1 Min. | Nur Schlaf | RMSSD | Nein |

**Warum Polar H7/H10 (Brustgurt) als Gold-Standard gelten:** anders als alle optischen
Handgelenk-/Ring-Geräte in dieser Tabelle (PPG — Licht durch die Haut) sitzen H7/H10 mit
echten EKG-Elektroden direkt auf der Haut und erkennen den R-Zacken elektrisch, nicht
optisch. Das liefert deutlich präzisere, weniger bewegungsanfällige Schlag-zu-Schlag-Zeiten
— deshalb sind sie in `compute_calibrate_sources.py` der Referenz-Anker für HR/RMSSD.
Peer-reviewte Validierung (mit DOI) dazu: `docs/references/device_validation.md`.
**Wichtige Einschränkung:** das ist trotzdem KEIN diagnostisches EKG (s. Tabelle unten) —
der Brustgurt liefert nur die Zeitabstände zwischen Herzschlägen (RR-Intervalle), keine
darstellbare EKG-Wellenform (P-QRS-T) zur kardiologischen Rhythmusbeurteilung.

---

## Warum gibt es kein 24/7-Sekunden-Gerät?

Drei physikalische Gründe:

1. **Akku** — Kontinuierliche PPG-Aktivierung im Sekunden-Takt würde den Akku
   in unter 24 Stunden leeren.
2. **Datenmenge** — Beat-to-beat 24/7 = ~100.000 RR-Intervalle pro Tag.
   Kein Consumer-Gerät ist darauf ausgelegt.
3. **Statistik** — HRV-Fenster unter 5 Minuten sind klinisch kaum
   aussagekräftig. 5-Min.-RMSSD ist der etablierte Standard.

---

## SpO2-Messfrequenz (für Schlafapnoe-Relevanz)

| Gerät | Gerätetyp | SpO2-Frequenz (Schlaf) | Für Schlafapnoe geeignet? |
|---|---|---|---|
| Wellue O2Ring | Ring, dediziertes Pulsoximeter | Alle 4 Sekunden | Ja — speziell dafür entwickelt, inkl. Nachtalarm |
| Beurer PO 40 / PO 60 | **Fingerclip-Pulsoximeter** | Momentanwert, Spot-Check | Nein — laut Herstellerhandbuch (beide Modelle) nicht für kontinuierliche Überwachung vorgesehen, keine Alarmfunktion, max. 2 Std. Messdauer pro Sitzung empfohlen |
| Oura Ring 4 | Ring, Multi-Sensor | Intern ~alle 15 Min. gemessen, aber nur EIN aggregierter Wert pro Nacht exportiert | Eingeschränkt — kein Rohdatenzugriff auf die Einzelmessungen |
| Apple Watch S9 | Handgelenk, Multi-Sensor | Sporadisch (Hintergrund) | Eingeschränkt |
| Polar (Consumer-Sportuhren, kein Modell mit durchgehender Nacht-SpO2-Funktion) | Handgelenk, Multi-Sensor | Einzelmessungen/Spot-Check | Nein |
| Garmin Fenix 6 Pro | Handgelenk, Multi-Sensor | Schlaf-Durchschnitt | Nein |

**Zu Fingerclip-Pulsoximetern allgemein** (Beurer und vergleichbare Modelle anderer Hersteller):
diese Geräteklasse ist medizinisch oft die genaueste Einzelmessung (Beurer PO60 z.B. CE-
Medizinprodukt Klasse IIa), aber **grundsätzlich als Spot-Check-Gerät konzipiert** — der Finger
muss ruhig im Clip liegen, das schließt Schlaf-Dauermessung durch die Bauform selbst aus
(anders als ein Ring oder Armband, das man durchgehend tragen kann). Das ist kein
Hersteller-spezifisches Beurer-Detail, sondern eine Eigenschaft der Fingerclip-Bauform
generell.

---

## Blutdruck-Messfrequenz

| Gerät | Messfrequenz | Kontinuierlich möglich? |
|---|---|---|
| Oberarm-/Handgelenk-Blutdruckmessgerät (Omron u.ä.) | Spot-Check, manuell ausgelöst | Nein — physikalisch prinzipbedingt (Oszillometrie/Manschette), keine Dauermessung |
| Withings ScanWatch/BPM | Spot-Check, manuell ausgelöst | Nein, gleiches Prinzip |
| Optische Handgelenk-PPG-Schätzung (diverse Fitness-Uhren, "Blutdruck-Trend") | Kontinuierlich möglich, aber unkalibriert | Technisch ja, aber ohne regelmäßigen Abgleich gegen eine Manschette driftet die Schätzung — von keiner Aufsichtsbehörde als medizinisch genau zugelassen |
| Ambulantes 24h-Blutdruckmessgerät (ABDM, über Arzt) | Alle 15–30 Min. automatisch, auch nachts | Ja — der einzige Consumer-nahe Weg zu echter Tag/Nacht-Dipping-Analyse |

**Grundproblem:** eine echte kontinuierliche, beat-by-beat Blutdruckmessung ohne Manschette
(z.B. via Pulswellenlaufzeit/PTT) existiert bislang nur in Forschungs-/Klinikgeräten, nicht
im Consumer-Segment mit belastbarer Zulassung.

---

## EKG-Messfrequenz

| Gerät | Aufzeichnungsdauer | Auslösung | Ableitungen | Liefert Wellenform (P-QRS-T)? |
|---|---|---|---|---|
| Apple Watch (ab Series 4) | 30 Sekunden pro Messung | Manuell ausgelöst | 1 (Einkanal, Arm-zu-Arm) | Ja |
| Polar/Garmin mit EKG-Feature | 30 Sekunden pro Messung | Manuell ausgelöst | 1 | Ja |
| KardiaMobile 6L | 30 Sekunden bis mehrere Minuten | Manuell ausgelöst | 6 | Ja |
| Withings BPM Core | ~30 Sekunden, während der Blutdruckmessung | Manuell ausgelöst (Teil der Blutdruckmessung, s. Blutdruck-Tabelle oben) | 1 (Einkanal, Hand-zu-Hand über Gehäuse-Elektroden) | Ja |
| Polar H7/H10 (Brustgurt) | Durchgehend bei aktiver Aufnahme | Manuell gestartet, dann kontinuierlich | 1 (intern) | **Nein** — nur RR-Intervalle (Zeitabstände) werden exportiert, keine darstellbare Wellenform |
| Holter-EKG (über Kardiologen) | 24–48h durchgehend | Automatisch, kontinuierlich | Meist 2–12, geräteabhängig | Ja |
| Zio Patch (iRhythm) | Bis zu 14 Tage durchgehend | Automatisch, kontinuierlich | 1 (Patch-Ableitung) | Ja |

**Zu Polar H7/H10:** technisch sitzen echte EKG-Elektroden auf der Haut (kein PPG) — das
macht die Schlag-zu-Schlag-Zeiten sehr präzise (s. Tabelle oben, Gold-Standard-Anker für
HR/HRV). Aber der Brustgurt selbst exportiert nur die RR-Intervalle daraus, nicht die
zugrundeliegende Spannungskurve — für eine kardiologische Rhythmusbeurteilung (Erkennen von
Vorhofflimmern, ST-Hebungen etc.) fehlt die Wellenform, dafür braucht es eins der Geräte mit
"Ja" in der letzten Spalte.

**Grundproblem:** alle Consumer-EKG-Geräte mit Wellenform liefern nur Momentaufnahmen (Spot-Checks von
Sekunden bis Minuten), keine durchgehende Aufzeichnung — für die Erfassung seltener/
paroxysmaler Rhythmusereignisse ist ein Langzeit-Gerät (Holter, Patch) nötig, ein
Spot-Check-EKG kann ein Ereignis, das gerade nicht stattfindet, prinzipbedingt nicht erfassen.

---

## Atemfrequenz-Messfrequenz

| Gerät | Wann gemessen | Tagsüber verfügbar? |
|---|---|---|
| Apple Watch | Nur während des Schlafs (dokumentiertes HealthKit-Sleep-Feature) | Nein — strukturelle Geräte-Grenze, keine Konfigurationsoption |
| Garmin (moderne Modelle mit Atemfrequenz-Sensor) | Kontinuierlich, auch tagsüber | Ja |
| Oura Ring | Nur während des Schlafs | Nein |
| Whoop | Nur während des Schlafs | Nein |

---

## Hauttemperatur-Messfrequenz

| Gerät | Wann gemessen | Auflösung |
|---|---|---|
| Oura Ring | Kontinuierlich während des Schlafs | Abweichung von persönlicher Baseline, kein Absolutwert |
| Polar (Modelle mit Hauttemperatur-Sensor) | Kontinuierlich, geräteabhängiges Sampling | Absolutwert in °C |
| Apple Watch (ab Series 8/Ultra) | Nur während des Schlafs | Abweichung von persönlicher Baseline, kein Absolutwert |
| Withings ScanWatch | Kontinuierlich während des Schlafs | Absolutwert |

---

## CGM / Glukose-Messfrequenz

| Gerät | Frequenz | Zulassung | Kalibrierung |
|---|---|---|---|
| Dexcom G6/G7 | Alle 5 Minuten, kontinuierlich | FDA/CE-zugelassenes Medizinprodukt | G6 werksseitig oder mit Fingerstich, G7 werksseitig |
| FreeStyle Libre 3 | Kontinuierliche Übertragung (~jede Minute) | FDA/CE-zugelassenes Medizinprodukt | Werksseitig |
| FreeStyle Libre 2 (klassischer Scan-Modus) | Sensor misst alle Minute, aber nur beim manuellen Scan abrufbar (sonst nur Alarm-Ereignisse) | FDA/CE-zugelassenes Medizinprodukt | Werksseitig |
| Optische/nicht-invasive Glukose-Schätzung (diverse Fitness-Wearables) | Kontinuierlich beworben | **Kein Gerät mit dieser Methode hat bislang eine Zulassung als genaues Blutzucker-Messgerät** | — |

**Grundproblem/Einordnung:** CGM ist die einzige Kategorie in dieser Übersicht, bei der
"kontinuierlich" tatsächlich die Norm ist (Prinzip des Sensors: subkutane Nadel, dauerhaft
im Gewebe) — anders als bei HR/SpO2/BP, wo kontinuierliche Consumer-Messung die Ausnahme
ist. Nicht-invasive (nadelfreie) optische Glukose-Schätzung über PPG bleibt trotz
wiederkehrender Marketing-Ankündigungen bislang ohne validierte, zugelassene Umsetzung.

---

## Schlafstadien-Erkennung

| Gerät | Methode | Vergleich zum Goldstandard |
|---|---|---|
| Polysomnographie (PSG, Schlaflabor) | EEG (Hirnströme) + EOG + EMG, direkte neurologische Messung | Goldstandard — alle Consumer-Geräte werden hieran validiert |
| Oura, Apple Watch, Garmin, Whoop, Fitbit (alle Consumer-Wearables) | Indirekt: Bewegungssensor (Beschleunigungsmesser) + HF-/HRV-Muster, algorithmisch zu Leicht-/Tief-/REM-Schlaf verrechnet | Keine direkte Hirnstrom-Messung — Genauigkeit variiert je nach Gerät/Algorithmus-Version, in Validierungsstudien meist moderate bis gute Übereinstimmung bei Gesamtschlafzeit, schwächer bei einzelnen Schlafstadien (v.a. Leichtschlaf vs. Wachphasen) |

**Grundproblem:** kein Consumer-Wearable misst Schlafstadien direkt — alle leiten sie aus
Bewegung und Herzsignalen ab. Das ist grundsätzlich anders als bei HR/SpO2, wo zumindest
im Prinzip eine direkte physiologische Messung stattfindet.

---

## Schritte / Aktivität

Im Unterschied zu den übrigen Kategorien hier ist **Kontinuierlich messen** bei Schritten/
Aktivität der Normalfall, nicht die Ausnahme — praktisch jedes Wearable mit Beschleunigungsmesser
zählt durchgehend. Der relevante Unterschied liegt nicht in der Frequenz, sondern in der
**Zählmethode/Tragestelle**:

| Trageposition | Typische Genauigkeit | Bekannte Schwäche |
|---|---|---|
| Handgelenk (die meisten Fitness-Uhren/Ringe) | Gut bei Gehen/Laufen | Überzählt bei repetitiven Armbewegungen (Radfahren, Geschirrspülen), unterzählt bei Aktivitäten ohne Armbewegung (Schieben eines Kinderwagens, manche Kraftübungen) |
| Hüfte (ältere Pedometer, klinische Aktigraphie) | Historisch als genauer gegolten für reines Gehen | Kaum noch verbreitet im Consumer-Segment |
| Smartphone (in der Tasche) | Ungenau, geräteabhängig | Zählt nichts, wenn Telefon nicht mitgeführt wird |

---

## AFib-Erkennung (Vorhofflimmern)

Zwei grundsätzlich verschiedene Mechanismen, oft im selben Gerät kombiniert:

| Gerät | Mechanismus | Modus | Medizinisch zugelassen? |
|---|---|---|---|
| Apple Watch (ab Series 4, mit EKG-Feature) | Aktives Einkanal-EKG (manuell ausgelöst) | Spot-Check, 30s | Ja — FDA-cleared (ECG-App), CE-Kennzeichnung |
| Apple Watch (alle Modelle mit optischem Sensor) | Passive Puls-Unregelmäßigkeits-Benachrichtigung (PPG-basiert, Hintergrund) | Kontinuierlich im Hintergrund, nur Benachrichtigung bei Verdacht, kein Diagnose-EKG | Ja — FDA-cleared als Benachrichtigungsfunktion, ersetzt keine Diagnose |
| KardiaMobile 6L | Aktives 6-Kanal-EKG | Spot-Check, manuell | Ja — FDA-cleared, CE-Medizinprodukt |
| Fitbit (aktuelle Generation mit EKG-App) | Aktives Einkanal-EKG + passive PPG-Benachrichtigung | Beides, wie Apple | Ja — FDA-cleared |
| Samsung Galaxy Watch (ab Watch 3, mit EKG-Feature) | Aktives Einkanal-EKG | Spot-Check, manuell | Ja — FDA-cleared (regional unterschiedlich verfügbar) |
| Whoop (aktuelle Generation, mit EKG-Feature) | Aktives Einkanal-EKG | Spot-Check, manuell | Ja — FDA 510(k)-cleared |
| Polar H7/H10, reine Fitness-Brustgurte ohne AFib-Feature | Kein AFib-Erkennungsalgorithmus | — | Nein — liefert nur Rohdaten (RR-Intervalle), keine Rhythmus-Interpretation |
| CardiacSense CSF-3 | Kontinuierliches Beat-by-Beat-Monitoring | Durchgehend, nicht nur Spot-Check | Ja — FDA- UND CE-MDR-zugelassen für kontinuierliches AFib-Monitoring (Stand der zuletzt geprüften Zulassungsinformation; vor Kauf aktuellen Status prüfen) |

**Wichtige Unterscheidung:** eine "AFib-Benachrichtigung" (passiv, PPG-basiert, im Hintergrund)
ist KEINE Diagnose — sie löst nur einen Hinweis aus, dass eine Unregelmäßigkeit vorliegen
könnte. Erst ein aktives Einkanal-EKG (oder ein klinisches Mehrkanal-EKG) liefert eine
darstellbare Wellenform, die tatsächlich zur Diagnose taugt. Die meisten "AFib-Erkennung"-
Werbeaussagen von Fitness-Wearables beziehen sich auf die passive Benachrichtigungsfunktion,
nicht auf ein diagnostisches EKG.

---

## Medizinisch validierte Geräte — Gesamtübersicht

Konsolidiert aus allen Tabellen oben: nur Geräte mit einer **konkreten FDA-Zulassung
(510(k)/De-Novo) oder CE-Kennzeichnung als Medizinprodukt** für den jeweiligen Parameter —
nicht zu verwechseln mit allgemeiner CE-Kennzeichnung als Elektrogerät (die praktisch jedes
Consumer-Wearable hat, aber nichts über medizinische Genauigkeit aussagt).

| Gerät | Validierter Parameter | Zulassungsart |
|---|---|---|
| Apple Watch (ab Series 4) | EKG (Einkanal-Spot-Check) | FDA-cleared, CE |
| Apple Watch (alle mit optischem Sensor) | Puls-Unregelmäßigkeits-Benachrichtigung | FDA-cleared (Benachrichtigung, keine Diagnose) |
| KardiaMobile 6L | EKG (6-Kanal-Spot-Check) | FDA-cleared, CE-Medizinprodukt |
| Fitbit (aktuelle Generation) | EKG (Einkanal-Spot-Check) | FDA-cleared |
| Samsung Galaxy Watch (ab Watch 3) | EKG (Einkanal-Spot-Check) | FDA-cleared |
| Whoop (aktuelle Generation) | EKG (Einkanal-Spot-Check) | FDA 510(k)-cleared (K243236) |
| Beurer PO 40 / PO 60 | SpO2 (Spot-Check) | CE-Medizinprodukt, MDR Klasse IIa |
| CardiacSense CSF-3 | Kontinuierliches Beat-by-Beat-HR + SpO2, AFib-Monitoring | FDA- und CE-MDR-zugelassen |
| Holter-EKG / Zio Patch / ActiHeart | EKG bzw. Aktigraphie (klinisch) | Medizinprodukt, über Arzt verordnet |
| Ambulantes 24h-Blutdruckmessgerät (ABDM) | Blutdruck, Tag/Nacht | Medizinprodukt, über Arzt verordnet |
| Dexcom G6/G7, FreeStyle Libre 2/3 | Kontinuierliche Glukose | FDA/CE-zugelassenes Medizinprodukt |

**Nicht in dieser Liste = keine bekannte medizinische Zulassung für den genannten Parameter**
(auch wenn das Gerät sonst weit verbreitet/vertrauenswürdig ist) — SpO2/HRV/Atemfrequenz/
Schlafstadien von Fitness-Uhren und -Ringen gelten branchenweit als "Wellness-Grade", nicht
als medizinisch zugelassen, auch wenn dasselbe Gerät für einen ANDEREN Parameter (z.B. EKG)
eine echte Zulassung hat — Zulassungen gelten immer nur für den spezifischen geprüften
Parameter, nie pauschal für das ganze Gerät.

---

## Medizinische Alternativen (über Arzt/Kardiologen)

| Gerät | Frequenz | Dauer | Verfügbarkeit |
|---|---|---|---|
| Holter-EKG | 500 Hz, beat-to-beat | 24–48h | Über Kardiologen, GKV-Leistung |
| Zio Patch (iRhythm) | 200 Hz kontinuierlich | 14 Tage | Rezept, Privatleistung |
| ActiHeart | 128 Hz | 7 Tage | Nur Forschung/Klinik |
