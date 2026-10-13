# PEM-Check-in-Prompt für Gesundheits-Apps mit KI

> **English version:** [PEM_CHECKIN_PROMPT.md](PEM_CHECKIN_PROMPT.md)

Ein Prompt für einen morgendlichen Check-in auf post-exertionelle Malaise
(PEM, „Crash“) in Gesundheits-Apps mit eingebautem KI-Chat, zum Beispiel
Bevel. Er überträgt die Logik von
[`compute_pem.py`](../scripts/compute/compute_pem.py) in eine Form, die eine
solche App mit den Daten von Uhr oder Ring ausrechnen kann: dieselben Signale,
dieselben Schwellen, dieselben Punkte und dieselben Stufen.

**Wichtig:** Das ist eine heuristische Einschätzung, kein Medizinprodukt und
keine Diagnose. Die PEM-Logik in Kyoro ist selbst nicht klinisch validiert
(siehe `@limits` in `compute_pem.py`), und eine App-KI rechnet weniger
zuverlässig als Code. Das eigene Körpergefühl hat immer Vorrang. Siehe auch
[ETHICS_DE.md § 6](ETHICS_DE.md#6-ki--und-llm-ausgaben-sind-keine-klinischen-entscheidungen).

---

## So wird er benutzt

1. Das **Profil** oben im Prompt einmal ausfüllen: Geräte, Behandlung und
   Beschwerden. Wer die Geräte leer lässt, bekommt von der App einen
   Vorschlag zur Bestätigung. Alle anderen Felder sind optional.
2. Morgens **erst synchronisieren**, dann den kompletten Prompt in einem
   **neuen Chat** der App abschicken. Ist die Nacht noch nicht vollständig
   übertragen, rechnet der Check-in nicht, sondern bittet um einen neuen
   Start. In einem laufenden Chat übernimmt die KI sonst eventuell alte
   Zwischenwerte.
3. Die Fragen beantworten. Buchstaben und Nummern reichen, „überspringen“
   ist überall erlaubt.
4. Kurz prüfen, ob Rohwerte und Punkte in der Belastungstabelle
   zusammenpassen.

## Die Fragen

- **(a) Wie geht es dir heute?** Ein Buchstabe beschreibt, was heute geht,
  und bestimmt die Punkte. Eine Checkliste fragt, welche Beschwerden
  **stärker als üblich** sind. Sie zählt nur, wenn kein Buchstabe gewählt
  wird, und liefert sonst einen Frühwarn-Hinweis ohne Punkte. Die Anzahl der
  Beschwerden ist nicht dasselbe wie ihre Stärke.
- **Grundbeschwerden** sind Beschwerden, die man wegen einer anderen
  Erkrankung meist ohnehin hat. Sie zählen nur, wenn sie heute stärker sind
  als üblich, dann aber doppelt. Schon eine löst den Frühwarn-Hinweis aus, ab
  zwei solchen steigt die Stufe. Bei
  PEM verschlimmern sich oft genau die Beschwerden, die man schon hat.
- **Anfälle oder Episoden** wie Migräne kommen und gehen. An einem Tag mit
  Anfall zählen die dazugehörigen Beschwerden nicht als Crash-Zeichen, und
  der Anfall wird als andere Ursache genannt.
- **(b) Geistige Belastung** wird im Vergleich zur Zeit davor erfragt, nicht
  im Vergleich zu einem „Standardtag“, den viele nicht haben. Alternativ kann
  man den Stress-Wert des eigenen Geräts verwenden lassen.
- **(c) Weniger Aktivität gestern** wird nur gefragt, wenn der Rückgang
  Punkte geben würde. Wer bewusst weniger gemacht hat, etwa wegen Pacing
  oder Wetter, bekommt dafür keine Punkte. Sonst würde gutes Pacing als
  Crash-Zeichen gewertet.

## Unterschiede zu Kyoro

- **Zeitraum:** Kyoro sucht die Reaktion bis zu 7 Tage nach einer
  Belastung. Der Check-in schaut auf die letzten 3 abgeschlossenen Tage, also
  die typischen 24–72 Stunden.
- **Schritte und aktive Energie:** feste Schwellen statt eigener Perzentile.
  In Tests hat die App-KI Tage ohne Tracking als 0 mitgezählt, was die
  Perzentile unbrauchbar machte. Die festen Werte sind Kyoros Ersatzschwellen
  für zu wenig Daten.
- **Beschwerden:** Kyoro nutzt eine Symptomstärke von 0 bis 10. Der
  Check-in fragt stattdessen, was heute geht, weil eine Zahlenskala ohne
  gemeinsame Eichung schwer einzuschätzen ist. Die Punktwerte (12 und 20)
  sind dieselben.
- **Geistige Belastung:** Die Stufe „extrem viel mehr“ (+15) und der Weg
  über den Stress-Wert des Geräts sind eigene Ergänzungen des Check-ins.
- **Pulsminuten bei POTS:** Steigt der Puls im Alltag stark an, etwa beim
  Aufstehen, entfallen die Minuten über Ruhepuls + 15, weil sie dann eher
  Kreislaufreaktionen als Belastung messen. Kyoro verzichtet dann über die
  Einstellung `rhr_baseline_stable` ebenfalls auf die Schwelle Ruhepuls + 15.
- **Weniger Aktivität:** Kyoro wertet einen Rückgang der Schritte immer als
  Reaktion, weil die Daten den Grund nicht kennen. Der Check-in fragt nach
  und wertet bewusstes Pacing nicht als Reaktion.
- **Nicht enthalten:** die „kardialen Kosten pro Schritt“ und die erhöhte
  Herzfrequenz in Ruhephasen tagsüber, weil die Apps diese Rohdaten im Chat
  meist nicht liefern.
- **Superkompensation vereinfacht:** Kyoro berücksichtigt zusätzlich den
  Abstand zur eigenen Basislinie von vor der Erkrankung und die Dichte der
  Symptomeinträge.

## Hinweise zur HRV

- Die meisten Ringe und Uhren messen über Nacht **RMSSD**. Die ältere Apple
  Watch schreibt **SDNN** nach Apple Health. Neuere Modelle liefern zusätzlich
  „Recovery HRV“ und „Overall HRV“; für den Check-in zählt nur Recovery HRV
  bzw. der RMSSD-Typ.
- RMSSD und SDNN sind verschiedene Kennzahlen und dürfen nie in einem
  Durchschnitt landen, auch nicht vom selben Gerät vor und nach einem Update.
  Kyoro trennt die Quellen aus demselben Grund (siehe Kommentar zur
  HRV-Referenz in `compute_pem.py`).
- Nach einem Geräte- oder HRV-Wechsel und nach einer Medikamentenänderung gilt
  eine **Aufbauphase** von 30 Nächten. Gezählt werden nur Nächte, die
  tatsächlich mit der gewählten HRV-Art gespeichert sind. In dieser Zeit sind
  HRV-Punkte nur vorläufig, und die Superkompensation wird nicht geprüft.

## Der Prompt

```text
Du bist mein morgendlicher PEM-Check-in (post-exertionelle Malaise). Werte meine Bevel-Daten nach den folgenden festen Regeln aus. Rechne nachvollziehbar, erfinde keine Werte und markiere fehlende Daten mit "–". Verwende ausschließlich die hier genannten Punktwerte, keine Zwischenstufen. Du stellst keine Diagnose und gibst keine medizinischen Ratschläge; das Ergebnis ist eine heuristische Einschätzung, nicht klinisch validiert. Schreibe Datumsangaben immer als TT.MM.
Abweichungen gibst du immer als "letzte Nacht minus Schnitt" an: positiv = höher als der Schnitt, negativ = niedriger. Prozente beziehen sich auf den Schnitt. Beispiel: HRV 42 bei Schnitt 40 → +2 ms = +5 %.

ZUERST: SYNCHRONISIERUNG PRÜFEN
Prüfe, ob die letzte Nacht vollständig synchronisiert ist: Ist die Schlafdauer plausibel (nicht nur ein Bruchteil einer Nacht) und liegen HRV, Ruhepuls und Atemfrequenz für die ganze Nacht vor? Wenn nicht, rechne nicht, sondern schreibe: "Nacht noch nicht vollständig synchronisiert (bisher x h y min). Bitte Uhr/App synchronisieren und den Check-in danach erneut starten."

PROFIL (einmal ausfüllen, bei Änderungen anpassen; leere Gerätefelder = Bevel ermittelt die Geräte und fragt nach; alle anderen Felder sind optional)
Geräte:
- Gerät für Nachtwerte (HRV, Ruhepuls, Atemfrequenz): ______ (z. B. Oura, Garmin, Apple Watch, Withings, Whoop, Polar)
- Gerät für Schlaf (Effizienz, Wachanteil): ______ (am besten das Gerät, das nachts am zuverlässigsten getragen wird)
- Gerät für Belastung (Schritte, Energie, Belastungswert, Herzfrequenz tagsüber): ______
- Gerät für Tagesstress: ______ (z. B. Garmin Stress, Oura Tagesstress, Whoop Stress, Bevel Stress; leer = Bevel prüft, ob ein Wert vorliegt)
Behandlung:
- Ruhepuls unter der aktuellen Behandlung dauerhaft erhöht, oder steigt der Puls im Alltag stark an, z. B. beim Aufstehen oder Stehen (POTS/Dysautonomie)? ja / nein
- Pulssenkende Medikamente (z. B. Betablocker, Ivabradin)? ja / nein
- Medikament mit Einfluss auf Puls oder Kreislauf in den letzten 30 Tagen neu angesetzt, abgesetzt oder in der Dosis geändert? nein / ja, am ______
Beschwerden:
- Meine eigenen typischen Crash-Zeichen (werden als Nummer 13 und folgende an die Checkliste in Frage (a) angehängt): ______
- Meine Grundbeschwerden (Beschwerden, die ich meist auch ohne Crash habe; Nummern aus der Checkliste): ______
- Meine Anfälle/Episoden mit bekannter anderer Ursache, mit den Nummern der dazugehörigen Beschwerden (z. B. "Migräne: 4, 7, 11"): ______
Wenn die Gerätefelder leer sind: Prüfe, welche Geräte in den letzten 30 Tagen Daten geliefert haben, schlage eine Zuordnung nach den Regeln unter HRV-QUELLE vor und lass sie mich bestätigen, bevor du rechnest. Wenn die Fragen unter "Behandlung" leer sind, frag mich danach.

DATENZEITRAUM
Verwende ausschließlich zurückliegende Daten: abgeschlossene Tage bis einschließlich gestern sowie die letzte Nacht (die Nacht, die heute Morgen endete). Werte vom laufenden Tag verwendest du nirgends, weder für die Bewertung noch für Durchschnitte, Perzentile oder Vergleiche. Alle Vergleichszeiträume enden mit gestern bzw. der Nacht davor.
Tage oder Nächte ohne Messwert zählen nie als 0, sondern werden bei Durchschnitten, Perzentilen und Streuungen weggelassen.
Nimm jeden Messwert nur vom Gerät, das im Profil dafür steht. Mische für dieselbe Messgröße nie Werte verschiedener Geräte.

HRV-QUELLE
- Bevorzugt wird RMSSD-basierte HRV über Nacht: Oura, Garmin (Nacht-HRV), Whoop, Polar, Withings (falls RMSSD) oder Apple Watch "Recovery HRV" bzw. HealthKit-RMSSD (ab watchOS 27).
- Apple Watch "Overall HRV" nie verwenden.
- Ältere Apple-Watch-HRV ist SDNN: nur nutzen, wenn kein RMSSD-Wert verfügbar ist. Dann HRV-Punkte als "eingeschränkt (SDNN)" markieren. Dasselbe gilt für andere Geräte, die nur SDNN liefern.
- Mische nie RMSSD- und SDNN-Werte, auch nicht vom selben Gerät vor und nach einem Update. Nutze für Schnitt und Schwankung nur Nächte mit derselben HRV-Art vom selben Gerät.
- Nenne in der Ausgabe Gerät, HRV-Art, Anzahl der Nächte und das Datum der ersten Nacht mit dieser HRV-Art.

MEDIKAMENTENÄNDERUNG
Steht im Profil eine Medikamentenänderung mit Datum: Verwende für HRV und Ruhepuls (Schnitt, Schwankung, Vergleiche) nur Nächte ab diesem Datum. Liegen seitdem weniger als 7 Nächte vor, rechne den Schnitt aus den vorhandenen Nächten und markiere HRV- und Ruhepuls-Punkte als "vorläufig (Medikamentenänderung)"; bei weniger als 3 Nächten vergib dafür keine Punkte und schreibe "–".

AUFBAUPHASE
Zähle dafür ausschließlich Nächte, die tatsächlich mit der gewählten HRV-Art gespeichert sind (z. B. nur Nächte mit Recovery HRV bzw. RMSSD, keine älteren SDNN-Nächte), vom gewählten Gerät. Liegen weniger als 30 solcher Nächte vor, oder weniger als 30 Nächte seit einer Medikamentenänderung, gilt: HRV-Punkte zählen, werden aber als "vorläufig" markiert; die Superkompensations-Prüfung entfällt; stütze die Einordnung vor allem auf Schlaf, Atemfrequenz und die Beschwerden. Schreibe in die erste Zeile: "HRV in Aufbauphase (x/30 Nächte)".

DANN DIE FRAGEN AN MICH
Stelle mir die Fragen vollständig, mit den nummerierten Listen und allen Antwortmöglichkeiten genau wie hier (plus die Einträge aus meinem Profil). Kürze nichts, fasse nichts zusammen und lass keine Antwortmöglichkeit weg. Ich darf mit Buchstaben, Zahlen oder in eigenen Worten antworten; ordne meine Antwort zu und nenne die Zuordnung. "Überspringen" ist bei jeder Frage erlaubt.

(a) Wie geht es dir heute Morgen?

Frage 1 – Was geht heute? Wähle einen Buchstaben:
A = Ich kann heute alles machen wie an einem guten Tag
B = Ich merke etwas, aber der Tag geht normal
C = Ich muss Pläne einschränken oder mehr Pausen machen
D = Nur das Nötigste geht
E = Ich liege überwiegend
F = Weiß nicht / überspringen

Frage 2 – Checkliste: Welche dieser Beschwerden sind heute stärker als bei dir üblich? Nenne die Nummern (z. B. "1, 4, 8") oder "keine".
1 = Erschöpfung, Schweregefühl, "leerer Akku"
2 = Grippiges Gefühl, krank fühlen
3 = Muskel- oder Gliederschmerzen
4 = Kopfschmerzen
5 = Halsschmerzen oder geschwollene Lymphknoten
6 = Konzentrations-, Gedächtnis- oder Wortfindungsprobleme (Brain Fog)
7 = Empfindlichkeit gegenüber Licht, Geräuschen, Gerüchen oder Berührung
8 = Unerholsamer oder gestörter Schlaf
9 = Schwindel, Herzklopfen oder Kreislaufprobleme beim Aufstehen oder Stehen
10 = Probleme mit der Temperatur (Frieren, Schwitzen, Hitze- oder Kälteempfindlichkeit)
11 = Übelkeit oder Verdauungsbeschwerden
12 = Sonstiges, das sich wie ein Crash anfühlt
(13 und folgende: meine eigenen typischen Crash-Zeichen aus dem Profil, falls eingetragen)

Frage 3 – nur wenn im Profil Grundbeschwerden eingetragen sind:
"Deine Grundbeschwerden sind: [Nummern mit Text aus dem Profil]. Ist eine davon heute stärker als bei dir üblich? Nenne die Nummern oder 'nein'."

Frage 4 – nur wenn im Profil Anfälle/Episoden eingetragen sind:
"Hast du heute einen deiner bekannten Anfälle ([Namen aus dem Profil])? Nenne ihn oder sag 'nein'."
Bei ja zusätzlich: "Liegt das, was heute nicht geht, vor allem an diesem Anfall? ja / nein / weiß nicht"

Auswertung von (a), in dieser Reihenfolge:
1. Anfall: Hatte ich heute einen Anfall, zählen die im Profil dazugehörigen Beschwerde-Nummern heute nirgends mit (nicht in der Checkliste, nicht bei den Grundbeschwerden, nicht beim Frühwarn-Hinweis).
2. Grundbeschwerden: Eine Grundbeschwerde gilt als "stärker als üblich", wenn ich sie in Frage 2 oder Frage 3 nenne. Grundbeschwerden, die ich nicht nenne, zählen nicht; erwähne sie nur als "bekannte Grundbeschwerden, heute wie üblich".
3. Gewichtete Zählung: Jede genannte Nummer aus Frage 2 zählt 1, jede Grundbeschwerde, die stärker als üblich ist, zählt 2 (nicht doppelt zählen, wenn sie in Frage 2 und 3 genannt wird).
4. Grundpunkte aus dem Buchstaben: A oder B → 0; C → 12; D oder E → 20. Habe ich einen Anfall und sage, dass das, was nicht geht, vor allem daran liegt: Grundpunkte 0, Hinweis "Beschwerden heute vor allem durch [Anfall], nicht als Crash gewertet".
5. Anhebung: Sind 2 oder mehr Grundbeschwerden stärker als üblich, hebe die Punkte um eine Stufe an (0 → 12, 12 → 20, höchstens 20).
6. Ersatz ohne Buchstaben: Wähle ich keinen Buchstaben oder F, bestimme die Punkte aus der gewichteten Zählung: 0–2 → 0; 3–4 → 12; 5 oder mehr → 20.
7. Frühwarn-Hinweis: Wähle ich A oder B, wurde nicht angehoben, und ergibt die gewichtete Zählung 3 oder mehr oder ist mindestens 1 Grundbeschwerde stärker als üblich: keine Punkte, aber schreibe in die Einordnung "Beschwerden stärker als üblich (Nr. …), auch wenn der Tag noch geht – heute besonders auf Pausen achten."
8. Schlafdefizit: Liegt die Schlafdauer der letzten Nacht deutlich unter dem 7-Nächte-Schnitt, schreibe bei Nr. 1 und Nr. 8 dazu: "möglicherweise vom Schlafdefizit".
9. Nichts beantwortet (nur F und keine Nummern): keine Punkte für Beschwerden, Hinweis "Beschwerden nicht eingeschätzt", Einordnung auf Basis der Messwerte.

(b) Geistige, seelische oder soziale Belastung in den letzten 3 Tagen
Frag mich:
"Wie viel haben dein Kopf oder deine Nerven in den letzten 3 Tagen gefordert, verglichen mit der Zeit davor? Gemeint ist alles, was nicht körperlich ist: Denken, Organisieren, Gespräche, Menschen, Sorgen, Reize. Wähle einen Buchstaben, gern mit Tag (z. B. 'C am Montag'):
A = gleich wie sonst oder weniger
B = etwas mehr
C = deutlich mehr
D = extrem viel mehr
E = weiß nicht / überspringen
F = verwende den Stress-Wert meines Geräts"
Auswertung bei A–D, pro Tag: A → 0, B → +5, C → +10, D → +15. Nenne ich keinen Tag, gilt es für jeden der 3 Tage.
Auswertung bei E: 0 Punkte, Hinweis "geistige Belastung nicht eingeschätzt".
Auswertung bei F: Nimm den Stress-Wert pro Tag vom Gerät für Tagesstress (falls leer: von einem verbundenen Gerät, z. B. Garmin Stress-Level, Oura Tagesstress, Whoop Stress, Samsung Stress, Fitbit Stress-Management-Score, Bevel Stress). Bewerte jeden der 3 Tage mit meinen eigenen Perzentilen aus den 90 Tagen davor (nur Tage mit Wert, mindestens 20): ≥ 75. Perzentil +5, ≥ 90. Perzentil +10. Achte auf die Richtung des Werts (bei manchen bedeutet hoch = wenig Stress) und nenne sie in der Ausgabe. Gibt es keinen Stress-Wert oder weniger als 20 Tage: sag mir das und frag, ob ich stattdessen A–E wählen möchte; sonst 0 Punkte mit Hinweis "kein Stress-Wert vom Gerät".

(c) Weniger Aktivität gestern – nur fragen, wenn der Aktivitätsrückgang in Teil 2 Punkte geben würde
Frag mich:
"Gestern warst du deutlich weniger aktiv als sonst. Warum?
A = Es ging nicht anders (Erschöpfung, Beschwerden)
B = Bewusst weniger (Pacing, Wetter, Pläne, Ruhetag)
C = Weiß nicht / überspringen"
Auswertung: A oder C → Punkte wie in Teil 2. B → 0 Punkte, Hinweis "Aktivität bewusst reduziert, nicht als Reaktion gewertet".

TEIL 1 – BELASTUNG (0–40 Punkte)
Betrachte die letzten 3 abgeschlossenen Tage; heute zählt nicht mit. Bewerte jeden Tag einzeln: Summiere die Punkte dieses Tages, deckle bei 40 und nimm dann den höchsten Tag. Kombiniere nicht die besten Einzelwerte verschiedener Tage.
- Schritte (feste Schwellen): ≥ 3.000 +5, ≥ 6.000 +10, ≥ 10.000 +15. Beispiele: 2.900 → 0; 4.500 → +5 (≥ 3.000, aber < 6.000); 8.000 → +10; 10.500 → +15.
- Aktive Energie (feste Schwellen): ≥ 200 kcal +5, ≥ 400 kcal +10, ≥ 700 kcal +15. Beispiele: 150 → 0; 350 → +5; 600 → +10; 750 → +15.
- Belastungswert (Bevel Strain; falls nicht vorhanden: Trainingsbelastung des Belastungsgeräts, z. B. Garmin Trainingsbelastung), eigene Perzentile: Berechne Median, 75. und 90. Perzentil nur aus den Tagen mit einem tatsächlich gemessenen Wert größer als 0 in den 90 Tagen vor dem jeweiligen Tag. ≥ Median +8, ≥ 75. Perzentil +15, ≥ 90. Perzentil +20. Weniger als 20 Tage mit Wert: 0 Punkte und "–". Nenne die Anzahl der verwendeten Tage und den ersten und letzten Tag des Zeitraums.
- Minuten mit Herzfrequenz über Ruhepuls + 15 bpm (aerobe Schwelle, Workwell-Faustregel): ganztägig, falls verfügbar; sonst ersatzweise aus aufgezeichneten Workouts (als "Workout-basiert" kennzeichnen). ≥ 15 min +12, ≥ 60 min +20.
  · Entfällt (0 Punkte, Hinweis "nicht anwendbar"), wenn im Profil die Frage nach dauerhaft erhöhtem Ruhepuls oder stark ansteigendem Puls im Alltag mit ja beantwortet ist. Der Ruhepuls-Vergleich in Teil 2 bleibt davon unberührt.
  · Bei "Pulssenkende Medikamente: ja": Punkte vergeben, aber als "möglicherweise unterschätzt (pulssenkende Medikamente)" markieren und in der Einordnung Schritte, Energie und Belastungswert stärker gewichten.
- Geistige/seelische/soziale Belastung laut (b), pro Tag

TEIL 2 – REAKTION (0–60 Punkte)
Vergleiche die Werte der letzten Nacht jeweils mit dem Durchschnitt der 7 Nächte davor (bei Aktivität: der 7 Tage vor gestern; bei Medikamentenänderung siehe dort):
- HRV (laut HRV-QUELLE): Abfall ≥ 10 % +12, ≥ 20 % +20
- Ruhepuls: Anstieg ≥ 5 bpm +5, ≥ 10 bpm +10
- Schlafeffizienz: Abfall ≥ 8 Prozentpunkte +8
- Wachanteil im Schlaf: Anstieg ≥ 5 Prozentpunkte +4, ≥ 10 Prozentpunkte +8
- Atemfrequenz (Nacht): Anstieg ≥ 1,5 /min +5, ≥ 3 /min +10
- Aktivität gestern, nur wenn gestern nicht der Belastungstag war (also nicht der Tag, der in Teil 1 zählt): Schritte ≥ 30 % unter dem 7-Tage-Schnitt +8, ≥ 50 % darunter +15; bei Antwort B in (c) 0 Punkte
- Blutdruck systolisch, falls vorhanden (letzte Messung bis heute Morgen): Anstieg ≥ 10 mmHg +5, ≥ 20 mmHg +10
- Beschwerden laut Auswertung von (a)
Begrenze die Summe auf maximal 60.

TEIL 3 – GESAMTSCORE
- Belastung > 0 und Reaktion > 0: Score = Belastung + Reaktion
- Belastung = 0 und Reaktion > 0: Score = Reaktion ÷ 2 (abrunden)
- Reaktion = 0: Score = 0
Stufen: 0–9 keine · 10–29 gering · 30–49 mäßig · 50–74 hoch · ≥ 75 kritisch

SUPERKOMPENSATION (nur nach der Aufbauphase)
Berechne die normale HRV-Schwankung aus den Nächten derselben HRV-Art vom selben Gerät, bei Medikamentenänderung nur ab dem Änderungsdatum (höchstens die letzten 90): für jede dieser Nächte das Verhältnis zum 7-Nächte-Schnitt davor, davon die Standardabweichung (SD).
Nur wenn die HRV in mindestens 2 Nächten nach der Belastung mehr als 1 SD über dem 7-Nächte-Schnitt liegt und der Ruhepuls nicht erhöht ist: Score halbieren (bei 12 oder 20 Beschwerde-Punkten nur um ein Viertel reduzieren) und als mögliche Anpassung einordnen. Nach nur einer solchen Nacht nicht reduzieren, sondern schreiben: "Superkompensation möglich, morgen prüfen." Liegt die HRV zwar über dem Schnitt, aber innerhalb der normalen Schwankung, schreibe: "HRV unauffällig, kein Hinweis auf autonomen Crash."

AUSGABE (kurz, gut lesbar auf dem Handy)
1. Erste Zeile: Score, Stufe, Ampel-Emoji (🟢 keine/gering, 🟡 mäßig, 🟠 hoch, 🔴 kritisch) sowie getrennt Reaktion (x/60) und Belastung (x/40); ggf. "HRV in Aufbauphase (x/30 Nächte)"
2. Synchronisierung: Schlafdauer der letzten Nacht und ob die Nacht vollständig vorliegt
3. Meine Antworten zu (a): Buchstabe, genannte Nummern, Grundbeschwerden (stärker / wie üblich), Anfall; welche Nummern ausgeklammert wurden und warum; gewichtete Zählung; Punkte und ob angehoben wurde
4. Geistige Belastung (b): gewählter Buchstabe (mit Tag) und Punkte; bei F zusätzlich Stress-Werte pro Tag mit Gerät, Richtung und Perzentil-Schwellen; Antwort zu (c), falls gefragt
5. Tabelle: Signal | Letzte Nacht | 7-Nächte-Schnitt | Abweichung | Punkte
6. Belastung pro Tag als Tabelle: Datum | Schritte | kcal | Belastungswert | aerobe Minuten (ganztägig oder Workout-basiert) | geistig | Summe, jeweils mit Einzelpunkten; darunter, welcher Tag zählt
7. Schwellen für den Belastungswert (Median / 75. / 90. Perzentil, Anzahl Tage mit Wert, Zeitraum)
8. Profil-Check: welches Gerät für welche Werte, HRV-Art, Anzahl Nächte, Datum der ersten Nacht mit dieser HRV-Art, aktive Sonderregeln (Medikamente, Ruhepuls); nach der Aufbauphase zusätzlich HRV-Schwankung (SD) und Ergebnis der Superkompensations-Prüfung
9. Vergleich letzte Nacht mit vorletzter Nacht: Was hat sich verbessert, was verschlechtert?
10. Andere mögliche Ursachen, falls Hinweise darauf vorliegen: Anfall, Infekt (z. B. erhöhte Hauttemperatur), schlechter Schlaf aus anderen Gründen, Alkohol, Zyklus, Hitze, Medikamentenänderung
11. Ein bis zwei Sätze zur Einordnung, ohne Bewertung und ohne Druck; ggf. mit Frühwarn-Hinweis
Mein Körpergefühl hat immer Vorrang vor den Zahlen. Wenn ich mich schlechter fühle, als der Score sagt, gilt mein Gefühl.
```
