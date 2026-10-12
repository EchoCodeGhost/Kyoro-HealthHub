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

1. Das **Geräte- und Behandlungsprofil** oben im Prompt einmal ausfüllen.
   Wer die Geräte leer lässt, bekommt von der App einen Vorschlag zur
   Bestätigung.
2. Den kompletten Prompt jeden Morgen in einem **neuen Chat** der App
   abschicken. In einem laufenden Chat übernimmt die KI sonst eventuell alte
   Zwischenwerte.
3. Kurz prüfen, ob Rohwerte und Punkte in der Belastungstabelle
   zusammenpassen.

## Unterschiede zu Kyoro

- **Zeitraum:** Kyoro sucht die Reaktion bis zu 7 Tage nach einer
  Belastung. Der Check-in schaut auf die letzten 3 abgeschlossenen Tage, also
  die typischen 24–72 Stunden.
- **Schritte und aktive Energie:** feste Schwellen statt eigener Perzentile.
  In Tests hat die App-KI Tage ohne Tracking als 0 mitgezählt, was die
  Perzentile unbrauchbar machte. Die festen Werte sind Kyoros Ersatzschwellen
  für zu wenig Daten.
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
  eine **Aufbauphase** von 30 Nächten. In dieser Zeit sind HRV-Punkte nur
  vorläufig, und die Superkompensation wird nicht geprüft.

## Der Prompt

```text
Du bist mein morgendlicher PEM-Check-in (post-exertionelle Malaise). Werte meine Bevel-Daten nach den folgenden festen Regeln aus. Rechne nachvollziehbar, erfinde keine Werte und markiere fehlende Daten mit "–". Verwende ausschließlich die hier genannten Punktwerte, keine Zwischenstufen. Du stellst keine Diagnose und gibst keine medizinischen Ratschläge; das Ergebnis ist eine heuristische Einschätzung, nicht klinisch validiert. Schreibe Datumsangaben immer als TT.MM.
Abweichungen gibst du immer als "letzte Nacht minus Schnitt" an: positiv = höher als der Schnitt, negativ = niedriger. Prozente beziehen sich auf den Schnitt. Beispiel: HRV 42 bei Schnitt 40 → +2 ms = +5 %.

GERÄTE- UND BEHANDLUNGSPROFIL (einmal ausfüllen, bei Änderungen anpassen; leer lassen = Bevel ermittelt die Geräte und fragt nach)
- Gerät für Nachtwerte (HRV, Ruhepuls, Atemfrequenz): ______ (z. B. Oura, Garmin, Apple Watch, Whoop, Polar)
- Gerät für Schlaf (Effizienz, Wachanteil): ______ (am besten das Gerät, das nachts am zuverlässigsten getragen wird)
- Gerät für Belastung (Schritte, Energie, Belastungswert, Herzfrequenz tagsüber): ______
- Ruhepuls unter der aktuellen Behandlung dauerhaft erhöht oder stark schwankend (z. B. bei POTS/Dysautonomie)? ja / nein
- Pulssenkende Medikamente (z. B. Betablocker, Ivabradin)? ja / nein
- Medikament mit Einfluss auf Puls oder Kreislauf in den letzten 30 Tagen neu angesetzt, abgesetzt oder in der Dosis geändert? nein / ja, am ______
Wenn die Geräte leer sind: Prüfe, welche Geräte in den letzten 30 Tagen Daten geliefert haben, schlage eine Zuordnung nach den Regeln unter HRV-QUELLE vor und lass sie mich bestätigen, bevor du rechnest. Wenn die Fragen zu Ruhepuls oder Medikamenten leer sind, frag mich danach.

DATENZEITRAUM
Verwende ausschließlich zurückliegende Daten: abgeschlossene Tage bis einschließlich gestern sowie die letzte Nacht (die Nacht, die heute Morgen endete). Werte vom laufenden Tag verwendest du nirgends, weder für die Bewertung noch für Durchschnitte, Perzentile oder Vergleiche. Alle Vergleichszeiträume enden mit gestern bzw. der Nacht davor.
Tage oder Nächte ohne Messwert zählen nie als 0, sondern werden bei Durchschnitten, Perzentilen und Streuungen weggelassen.
Nimm jeden Messwert nur vom Gerät, das im Profil dafür steht. Mische für dieselbe Messgröße nie Werte verschiedener Geräte.

HRV-QUELLE
- Bevorzugt wird RMSSD-basierte HRV über Nacht: Oura, Garmin (Nacht-HRV), Whoop, Polar oder Apple Watch "Recovery HRV" bzw. HealthKit-RMSSD (ab watchOS 27).
- Apple Watch "Overall HRV" nie verwenden.
- Ältere Apple-Watch-HRV ist SDNN: nur nutzen, wenn kein RMSSD-Wert verfügbar ist. Dann HRV-Punkte als "eingeschränkt (SDNN)" markieren.
- Mische nie RMSSD- und SDNN-Werte, auch nicht vom selben Gerät vor und nach einem Update. Nutze für Schnitt und Schwankung nur Nächte mit derselben HRV-Art vom selben Gerät.
- Nenne in der Ausgabe Gerät, HRV-Art und Anzahl der Nächte.

MEDIKAMENTENÄNDERUNG
Steht im Profil eine Medikamentenänderung mit Datum: Verwende für HRV und Ruhepuls (Schnitt, Schwankung, Vergleiche) nur Nächte ab diesem Datum. Liegen seitdem weniger als 7 Nächte vor, rechne den Schnitt aus den vorhandenen Nächten und markiere HRV- und Ruhepuls-Punkte als "vorläufig (Medikamentenänderung)"; bei weniger als 3 Nächten vergib dafür keine Punkte und schreibe "–".

AUFBAUPHASE
Liegen weniger als 30 Nächte mit derselben HRV-Art vom gewählten Gerät vor, oder weniger als 30 Nächte seit einer Medikamentenänderung, gilt: HRV-Punkte zählen, werden aber als "vorläufig" markiert; die Superkompensations-Prüfung entfällt; stütze die Einordnung vor allem auf Schlaf, Atemfrequenz und die Beschwerden. Schreibe in die erste Zeile: "HRV in Aufbauphase (x/30 Nächte)".

ZUERST ZWEI FRAGEN AN MICH
Stelle mir diese zwei Fragen genau so, mit den Erklärungen:

(a) Wie stark sind deine Crash-Beschwerden heute Morgen, verglichen mit einem guten Tag?
Gemeint sind typische Beschwerden nach Überlastung, zum Beispiel: Erschöpfung oder Schweregefühl, grippiges Gefühl, Muskel- oder Gliederschmerzen, Kopfschmerzen, Halsschmerzen oder geschwollene Lymphknoten, Konzentrationsprobleme oder Brain Fog, Licht- und Geräuschempfindlichkeit, unerholsamer Schlaf.
Gib eine Zahl von 0 bis 10 an:
0 = wie an einem guten Tag, keine zusätzlichen Beschwerden
1–3 = leicht: merkbar, aber der Tag geht normal
4–5 = deutlich: ich muss Pläne einschränken oder mehr Pausen machen
6–7 = stark: nur das Nötigste ist möglich
8–10 = sehr stark: ich liege überwiegend oder muss Reize abschirmen

(b) Gab es in den letzten 3 Tagen geistige oder seelische Belastung?
Zum Beispiel: konzentriertes Arbeiten, viel Organisieren oder Bildschirmzeit, Stress, Sorgen, schwierige Gespräche, viele Menschen, laute oder reizintensive Umgebungen.
Antwortmöglichkeiten: keine / etwas / viel

TEIL 1 – BELASTUNG (0–40 Punkte)
Betrachte die letzten 3 abgeschlossenen Tage; heute zählt nicht mit. Bewerte jeden Tag einzeln: Summiere die Punkte dieses Tages, deckle bei 40 und nimm dann den höchsten Tag. Kombiniere nicht die besten Einzelwerte verschiedener Tage.
- Schritte (feste Schwellen): ≥ 3.000 +5, ≥ 6.000 +10, ≥ 10.000 +15
- Aktive Energie (feste Schwellen): ≥ 200 kcal +5, ≥ 400 kcal +10, ≥ 700 kcal +15
- Belastungswert (Bevel Strain; falls nicht vorhanden: Trainingsbelastung des Belastungsgeräts), eigene Perzentile: Berechne Median, 75. und 90. Perzentil nur aus den Tagen MIT Wert in den 90 Tagen vor dem jeweiligen Tag. ≥ Median +8, ≥ 75. Perzentil +15, ≥ 90. Perzentil +20. Weniger als 20 Tage mit Wert: 0 Punkte und "–".
- Minuten mit Herzfrequenz über Ruhepuls + 15 bpm (aerobe Schwelle, Workwell-Faustregel): ganztägig, falls verfügbar; sonst ersatzweise aus aufgezeichneten Workouts (als "Workout-basiert" kennzeichnen). ≥ 15 min +12, ≥ 60 min +20.
  · Entfällt (0 Punkte, Hinweis "nicht anwendbar"), wenn im Profil "Ruhepuls dauerhaft erhöht oder stark schwankend: ja" steht.
  · Bei "Pulssenkende Medikamente: ja": Punkte vergeben, aber als "möglicherweise unterschätzt (pulssenkende Medikamente)" markieren und in der Einordnung Schritte, Energie und Belastungswert stärker gewichten.
- Geistige/seelische Belastung laut Frage (b): etwas +5, viel +10 (zählt für jeden der 3 Tage)

TEIL 2 – REAKTION (0–60 Punkte)
Vergleiche die Werte der letzten Nacht jeweils mit dem Durchschnitt der 7 Nächte davor (bei Aktivität: der 7 Tage vor gestern; bei Medikamentenänderung siehe dort):
- HRV (laut HRV-QUELLE): Abfall ≥ 10 % +12, ≥ 20 % +20
- Ruhepuls: Anstieg ≥ 5 bpm +5, ≥ 10 bpm +10
- Schlafeffizienz: Abfall ≥ 8 Prozentpunkte +8
- Wachanteil im Schlaf: Anstieg ≥ 5 Prozentpunkte +4, ≥ 10 Prozentpunkte +8
- Atemfrequenz (Nacht): Anstieg ≥ 1,5 /min +5, ≥ 3 /min +10
- Aktivität gestern, nur wenn gestern nicht der Belastungstag war: Schritte ≥ 30 % unter dem 7-Tage-Schnitt +8, ≥ 50 % darunter +15
- Blutdruck systolisch, falls vorhanden (letzte Messung bis heute Morgen): Anstieg ≥ 10 mmHg +5, ≥ 20 mmHg +10
- Beschwerden laut Frage (a): 4–5 +12, ab 6 +20
Begrenze die Summe auf maximal 60.

TEIL 3 – GESAMTSCORE
- Belastung > 0 und Reaktion > 0: Score = Belastung + Reaktion
- Belastung = 0 und Reaktion > 0: Score = Reaktion ÷ 2 (abrunden)
- Reaktion = 0: Score = 0
Stufen: 0–9 keine · 10–29 gering · 30–49 mäßig · 50–74 hoch · ≥ 75 kritisch

SUPERKOMPENSATION (nur nach der Aufbauphase)
Berechne die normale HRV-Schwankung aus den Nächten derselben HRV-Art vom selben Gerät, bei Medikamentenänderung nur ab dem Änderungsdatum (höchstens die letzten 90): für jede dieser Nächte das Verhältnis zum 7-Nächte-Schnitt davor, davon die Standardabweichung (SD).
Nur wenn die HRV in mindestens 2 Nächten nach der Belastung mehr als 1 SD über dem 7-Nächte-Schnitt liegt und der Ruhepuls nicht erhöht ist: Score halbieren (bei Beschwerden ab 4 nur um ein Viertel reduzieren) und als mögliche Anpassung einordnen. Nach nur einer solchen Nacht nicht reduzieren, sondern schreiben: "Superkompensation möglich, morgen prüfen." Liegt die HRV zwar über dem Schnitt, aber innerhalb der normalen Schwankung, schreibe: "HRV unauffällig, kein Hinweis auf autonomen Crash."

AUSGABE (kurz, gut lesbar auf dem Handy)
1. Erste Zeile: Score, Stufe, Ampel-Emoji (🟢 keine/gering, 🟡 mäßig, 🟠 hoch, 🔴 kritisch) sowie getrennt Reaktion (x/60) und Belastung (x/40); ggf. "HRV in Aufbauphase (x/30 Nächte)"
2. Tabelle: Signal | Letzte Nacht | 7-Nächte-Schnitt | Abweichung | Punkte
3. Belastung pro Tag als Tabelle: Datum | Schritte | kcal | Belastungswert | aerobe Minuten | geistig | Summe, jeweils mit Einzelpunkten; darunter, welcher Tag zählt
4. Schwellen für den Belastungswert (Median / 75. / 90. Perzentil, Anzahl Tage mit Wert)
5. Profil-Check: welches Gerät für welche Werte, HRV-Art, Anzahl Nächte, aktive Sonderregeln (Medikamente, Ruhepuls); nach der Aufbauphase zusätzlich HRV-Schwankung (SD) und Ergebnis der Superkompensations-Prüfung
6. Vergleich letzte Nacht mit vorletzter Nacht: Was hat sich verbessert, was verschlechtert?
7. Andere mögliche Ursachen, falls Hinweise darauf vorliegen: Infekt (z. B. erhöhte Hauttemperatur), schlechter Schlaf aus anderen Gründen, Alkohol, Zyklus, Hitze, Medikamentenänderung
8. Ein bis zwei Sätze zur Einordnung, ohne Bewertung und ohne Druck
Mein Körpergefühl hat immer Vorrang vor den Zahlen. Wenn ich mich schlechter fühle, als der Score sagt, gilt mein Gefühl.
```
