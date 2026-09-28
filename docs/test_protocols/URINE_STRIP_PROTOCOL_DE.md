<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Urin-Heimmonitoring — Testprotokoll

> **English version:** [URINE_STRIP_PROTOCOL.md](URINE_STRIP_PROTOCOL.md)

**Gerät:** 12-Parameter-Urinschnelltest (Streifentest)
**Import:** `python3 scripts/importers/import_urine_strip.py mein_urintest.csv`
**Template:** `templates/urine_strip_template.csv`

---

## Standardprotokoll (Routine)

**Frequenz:** 1× pro Woche, immer gleicher Wochentag (z.B. Montag morgens)
**Zusätzlich:** Bei Symptomverschlechterung, nach Infekt, vor/nach Arzttermin

### Vorbereitung

1. **Vitamin C:** Letztes Supplement/Ascorbinsäure mind. **4 Stunden vor dem Test** — hohe Vit-C-Konzentrationen verfälschen Blut- und Glukose-Ergebnis (falsch negativ). Wenn Ascorbinsäure-Feld `+` oder `++` zeigt: Blut- und Glukose-Ergebnis mit Vorbehalt interpretieren.
2. **Urin:** Ersten Morgenurin verwenden (konzentriertester Urin, höchste Sensitivität für Protein und Blut).
3. **Mittelstrahltechnik:** Erst kurz laufen lassen, dann Auffangbehälter in den Strahl — so werden Kontaminationen (Scheidenflora, Hautkeime) minimiert.
4. **Streifen:** Kurz in den Urin tauchen (1–2 Sekunden), dann auf eine saubere, horizontale Fläche legen — nicht auf dem Streifen abtupfen.

### Ablesen

- Exakt nach Herstellerangabe ablesen (meist 30–60 Sekunden, je Parameter unterschiedlich)
- **Bei Tageslicht** oder guter Kunstlichtbeleuchtung ablesen
- Referenzfarbtafel auf der Packung nutzen
- Alle 12 Felder eintragen, auch wenn negativ — fehlende Werte erschweren die Trendanalyse

### Dokumentation (CSV-Eintrag)

```
Datum,       Uhrzeit, Probe_Art, Volumen_ml, Leu, Uro, Pro, Bil, Glu, Asc, SpG, Ket, Nit, Kre, pH,  Blut, Labor,       Kommentar
2026-06-28,  07:30,   spot,      ,           neg, 0.2, neg, neg, neg, neg, 1.020, neg, neg, 100, 6.0, neg,  Selbsttest,  Routine Mo
```

---

## Parameter — Was bedeutet was

Diese Tabelle nennt beispielhaft, bei welchen Erkrankungsbildern die einzelnen Parameter besonders relevant werden. Sie ersetzt keine individuelle ärztliche Einordnung.

| Parameter | Normal | Relevant u.a. bei |
|---|---|---|
| Leukozyten | neg | Harnwegsinfekt vs. autoimmune Nephritis (z.B. bei Sjögren-Syndrom, Lupus), tubulointerstitielle Nephritis |
| Urobilinogen | 0,2–1,0 mg/dl | Leberfunktion (relevant bei Mastzellerkrankungen, Antiphospholipid-Syndrom) |
| Protein | neg | Autoimmune Nephritis (Sjögren, Lupus), Antiphospholipid-Syndrom-Nephropathie, tubuläre Dysfunktion |
| Bilirubin | neg | Leberbeteiligung |
| Glukose | neg | Tubuläre Reabsorptionsstörung (z.B. Sjögren-assoziiertes Fanconi-Syndrom), unter GLP-1-Rezeptoragonisten-Therapie (z.B. Semaglutid, Tirzepatid) |
| Ascorbinsäure | neg | Interpretationshilfe (verfälscht Blut/Glukose wenn hoch) |
| Spez. Gewicht | 1,010–1,025 | Konzentrierungsfähigkeit, Hydratationsstatus |
| Ketone | neg | Monitoring unter GLP-1-Rezeptoragonisten-Therapie (erhöhtes Ketoserisiko durch verminderte Kalorienaufnahme) |
| Nitrit | neg | Bakterielle Harnwegsinfektion (Gram-negative Keime) |
| Kreatinin | 20–370 mg/dl | Zusammen mit Protein → grober Protein/Kreatinin-Quotient |
| pH | 5,0–8,0 | Renale tubuläre Azidose (klassisch bei Sjögren-Syndrom, pH > 6,5 nüchtern) |
| Blut | neg | Mikrohämaturie bei Antiphospholipid-Syndrom, Sjögren-Syndrom, Harnwegsinfekt |

### Protein/Kreatinin-Quotient (PCR) — Heimberechnung

Wenn der Streifen numerische Werte zeigt:
`PCR (mg/g) = Protein (mg/dl) ÷ Kreatinin (mg/dl) × 1000`
Normal: < 150 mg/g | Pathologisch: > 300 mg/g

Das Analyse-Script berechnet das automatisch wenn beide Felder numerisch sind.

---

## Alarmsignale — Wann zum Arzt / Hausarzt

| Befund | Dringlichkeit | Aktion |
|---|---|---|
| Protein `++` oder `+++` (≥100 mg/dl) | 🟡 zeitnah | Laborbestätigung ACR, Kreatinin, Zylinder-Sediment |
| Blut `++` oder `+++` ohne Harnwegsinfekt-Symptome | 🟡 zeitnah | Urologie / Nephrologie, Sediment |
| Ketone `++` oder `+++` unter GLP-1-Therapie | 🟡 zeitnah | Euglykämische Ketoazidose ausschließen (venöse Blutgasanalyse) |
| Leukozyten `+` + Nitrit `pos` | 🟢 elektiv | Harnwegsinfekt behandeln, Wiederholung nach Antibiotika |
| pH > 6,5 nüchtern wiederholt | 🟢 elektiv | Renale tubuläre Azidose (RTA Typ 1, u.a. bei Sjögren-Syndrom) — dem Rheumatologen mitteilen |
| Glukose `+` bei normaler Blutzucker-Messung | 🟢 elektiv | Tubuläre Glukosurie (z.B. Sjögren-assoziiertes Fanconi-Syndrom) — Nephrologen konsultieren |
| Protein `trace` oder `+` (30 mg/dl) neu | 🟢 Verlauf | Im nächsten Routinetest wiederholen |

---

## Einschränkungen des Streifentests

- **Albuminurie < 30 mg/dl** wird nicht erkannt — für Frühdiagnostik einer autoimmunen Nephritis ist ein Labor-ACR empfindlicher
- **Tubuläre Proteine** (β2-Mikroglobulin, NAG) — nur im Labor messbar, klinisch relevant bei Sjögren-assoziierter tubulärer Beteiligung
- **Sediment** (Erythrozytenzylinder, dysmorphe Erys) — braucht Mikroskop
- Streifen sind **Screening-Tests**, keine Diagnose

---

## Kyoro-Import nach jedem Test

```bash
# CSV ausfüllen (Template kopieren, Werte eintragen)
cp templates/urine_strip_template.csv meine_urintests.csv
# ... Werte eintragen ...

# Import
python3 scripts/importers/import_urine_strip.py meine_urintests.csv

# Auswertung
python3 scripts/analysis/manual/analyse_urine.py --plot
```
