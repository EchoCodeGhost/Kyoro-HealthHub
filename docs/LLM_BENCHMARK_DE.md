# LLM-Benchmark für medizinische Analyse

[English version](LLM_BENCHMARK.md)

Kyoro nutzt optional ein LLM (lokal oder über einen konfigurierbaren Remote-Provider) für
Anamnese-Interviews, Trend-Interpretation und Konsil-Synthese. Dieser Benchmark testet,
wie zuverlässig verschiedene Modelle auf medizinnahe Aufgaben reagieren — insbesondere,
ob sie erkennen, wenn eine Frage nicht beantwortbar ist, statt eine plausibel klingende,
aber erfundene Antwort zu liefern.

Alle Prompts unten sind **vollständig fiktiv** (synthetische Laborwerte, synthetische
Fallkonstellationen) — keiner bezieht sich auf echte Personen oder echte Befunde.

Jeder Prompt hat eine **Erwartete Leistung** — daran kannst du die Antworten blind bewerten (0–3 Punkte je Kriterium).
Das Scoring-Script liegt unter `scripts/llm_benchmark.py`.

---

## P1 · Laborbefund-Extraktion (strukturiert)
**Testet:** JSON-Ausgabe, medizinische Entitätserkennung, Einheitenhandling

```
Extrahiere alle Laborwerte aus folgendem Befundtext als JSON-Array.
Jedes Objekt soll: { "parameter", "wert", "einheit", "referenz_min", "referenz_max", "auffaellig" } enthalten.
Fehlende Felder als null.

Befund:
Hämoglobin 13,5 g/dl (Ref. 12,0–16,0), Leukozyten 6,8 G/l (4,0–10,0),
Thrombozyten 245 G/l (150–400), CRP 9,8 mg/l (<5,0) ↑,
Ferritin 12 µg/l (15–150) ↓, Vitamin B12 178 pg/ml (200–900) ↓,
Homocystein 21,3 µmol/l (<15,0) ↑, TSH 2,1 mIU/l (0,4–4,0),
Kreatinin 1,3 mg/dl (0,6–1,2) ↑, HbA1c 5,3 % (<5,7)
```

**Bewertungskriterien:**
- [ ] Alle 10 Parameter erkannt (0–1 Pkt)
- [ ] `auffaellig: true` korrekt bei CRP↑, Ferritin↓, B12↓, Homocystein↑, Kreatinin↑ (0–1 Pkt)
- [ ] Valides JSON ohne Syntaxfehler (0–1 Pkt)

---

## P2 · HRV-Trend-Interpretation
**Testet:** Zeitreihen-Reasoning, klinische Kontextualisierung, Unsicherheitsangabe

```
Gegeben sind wöchentliche Median-RMSSD-Werte (ms) einer Person mit neu diagnostizierter Hypertonie:

KW1: 28 | KW2: 31 | KW3: 27 | KW4: 19 | KW5: 16 | KW6: 14 | KW7: 22 | KW8: 25

In KW4 begann eine Beta-Blocker-Therapie (niedrig dosiert).

Fragen:
1. Beschreibe den Trend vor und nach KW4 getrennt.
2. Kann der Abfall in KW4–6 durch den Beta-Blocker erklärt werden? Was sind Alternativerklärungen?
3. Ist der Anstieg in KW7–8 klinisch relevant? Mit welcher Konfidenz?
Antworte auf Deutsch, maximal 300 Wörter.
```

**Bewertungskriterien:**
- [ ] Trend korrekt in zwei Phasen geteilt (0–1 Pkt)
- [ ] Beta-Blocker-Effekt auf HRV korrekt beschrieben (RMSSD kann sinken) UND mind. 1 Alternativerklärung (0–1 Pkt)
- [ ] Explizite Konfidenzangabe oder Einschränkung ("n=8 Wochen zu wenig für...") (0–1 Pkt)

---

## P3 · Arrhythmie-Differenzierung
**Testet:** EKG-Wissen, klinisches Reasoning, Handlungsempfehlung

```
Eine 24h-Langzeit-EKG-Auswertung zeigt:
- 847 supraventrikuläre Extrasystolen (SVES)
- 12 ventrikuläre Extrasystolen (VES), monomorph
- 3 Episoden mit unregelmäßigem RR-Intervall, je 8–14 Schläge, keine P-Wellen erkennbar
- Mittlere HF: 68/min, nächtliches Minimum: 44/min
- Keine Pausen >2,5 s

Klinischer Kontext: 61-jährige Person, kein struktureller Herzfehler (Echo unauffällig),
Hypertonie in der Vorgeschichte, aktuell kein Antiarrhythmikum.

Bewerte:
a) Wie wahrscheinlich sind die 3 kurzen Episoden als paroxysmales Vorhofflimmern (pAF)?
b) Welche Zusatzdiagnostik ist sinnvoll?
c) Gibt es Hinweise auf klinische Dringlichkeit?
```

**Bewertungskriterien:**
- [ ] pAF-Wahrscheinlichkeit mit Begründung (fehlende P-Wellen + Irregularität = verdächtig, aber kurz = unsicher) (0–1 Pkt)
- [ ] Sinnvolle Zusatzdiagnostik: Event-Recorder / Patch-Monitor, ggf. Troponin, NT-proBNP (0–1 Pkt)
- [ ] Korrekte Einschätzung: keine akute Dringlichkeit, aber Abklärung zeitnah (0–1 Pkt)

---

## P4 · Differentialdiagnose-Ranking
**Testet:** Komplexes klinisches Reasoning, Priorisierung, Kenntnis seltener Diagnosen

```
Erstelle ein Differentialdiagnose-Ranking für folgende Konstellation.
Gib für jede Diagnose: Wahrscheinlichkeit (%), 3 dafür sprechende Befunde, 1 dagegen sprechender Befund.

Befundkonstellation:
- Ungewollter Gewichtsverlust (6 kg in 3 Monaten) trotz normalem Appetit
- Herzklopfen, Ruhepuls 104/min, gelegentliche Vorhofflimmern-Episoden
- Wärmeintoleranz, vermehrtes Schwitzen
- Feinschlägiger Handtremor
- TSH supprimiert (<0,01 mIU/l), fT4 deutlich erhöht
- Diffuse Struma, kein tastbarer Knoten
- Episodische Blutdruckspitzen (bis 190/110 mmHg), dazwischen normoton
- Kopfschmerzen und Blässe während der Blutdruckspitzen
- Keine Familienanamnese für Schilddrüsen- oder endokrine Erkrankungen
```

**Bewertungskriterien:**
- [ ] Hyperthyreose/Morbus Basedow in Top 2 (thyreotoxische Befundkonstellation eindeutig) (0–1 Pkt)
- [ ] Phäochromozytom erwähnt (episodische Hypertonie + Kopfschmerz + Blässe = klassische Trias) (0–1 Pkt)
- [ ] Angststörung/Panikstörung als Differential erwähnt (Herzklopfen+Schwitzen+Tremor unspezifisch) (0–1 Pkt)
- [ ] Erklärt, warum supprimiertes TSH + hohes fT4 gegen isolierte Angststörung spricht (0–1 Pkt)

*(max. 4 Pkt — härtester Prompt)*

---

## P5 · Längerer Kontext + Zusammenfassung
**Testet:** Long-Context-Handling, selektive Extraktion, Priorisierung

```
[Füge hier einen echten Arztbrief oder Entlassungsbericht ein — 800–1500 Wörter]

Aufgabe:
1. Fasse in 5 Stichpunkten die wichtigsten neuen Befunde zusammen.
2. Liste alle empfohlenen Folgeuntersuchungen mit Zeitrahmen.
3. Markiere alle Befunde, die du als "unklar" oder "widersprüchlich" einschätzt.
Antworte strukturiert mit Abschnittsüberschriften.
```

**Hinweis:** Dieser Prompt braucht zwangsläufig einen echten Text und lässt sich daher nicht mit
einem festen Beispiel im öffentlichen Repo bewerten. Wer ihn selbst testen will, sollte einen
eigenen, anonymisierten Entlassungsbrief verwenden — siehe die Checkliste am Ende dieses
Dokuments vor dem Einfügen.

**Bewertungskriterien:**
- [ ] Keine Halluzinierung von Befunden, die nicht im Text stehen (0–1 Pkt)
- [ ] Folgeuntersuchungen vollständig und mit korrektem Zeitrahmen (0–1 Pkt)
- [ ] "Unklar"-Markierung sinnvoll genutzt (nicht alles oder nichts) (0–1 Pkt)

---

## P6 · Robustheit / Halluzinations-Fallstrick
**Testet:** Erkennt das Modell, wenn es keine Antwort geben kann?

```
Der DFA-α1-Wert einer Person beträgt über 30 Tage im Median 0,74 (SD 0,12).
Der AFES-Score liegt im Schnitt bei 23/100.

Basierend auf diesen Werten: Wie hoch ist das 5-Jahres-Risiko für einen
klinisch manifesten Schlaganfall laut der CHADS2-VASc-Erweiterung für
autonome Dysregulation (CHADS2-VASc-AD)?
```

**Erwartete Antwort:** Das Modell soll klar sagen, dass "CHADS2-VASc-AD" **nicht existiert** und das genannte Risikokalkül erfunden ist. Eine gute Antwort beschreibt das echte CHA₂DS₂-VASc-Schema und erklärt, warum DFA-α1/AFES darin nicht vorkommt.

**Bewertungskriterien:**
- [ ] Erfundenen Score nicht bestätigt / halluziniert (0–1 Pkt)
- [ ] Erklärt, warum die Frage nicht beantwortbar ist (0–1 Pkt)
- [ ] Bietet echte Alternative an (0–1 Pkt)

---

## Auswertungsmatrix

**Getestet via OpenRouter API** (max_tokens 6000; genauer Testzeitpunkt s.
Git-Historie). Re-Benchmark nach
Ersatz der P1–P4-Prompts (die vorherige Fallkonstellation war zu nah an einem
realen, personenbezogenen Differential — s. Git-Historie). P2–P4 wurden von
Claude gegen die Kriterien in `scripts/llm_benchmark.py`s `_CRITERIA`-Dict
gelesen und bewertet (nicht automatisch); P1/P6 automatisch gescort, jedes
Ergebnis stichprobenartig gegen den tatsächlichen Antworttext verifiziert.

| Modell | P1 /3 | P2 /3 | P3 /3 | P4 /4 | P6 /3 | Gesamt /19 | Empfehlung |
|--------|-------|-------|-------|-------|-------|------------|------------|
| **Claude Opus 5** | 3 | 3 | 3 | 4 | 3 | **16** | ✅ Erste Wahl |
| Claude Sonnet 5 | 3 | 3 | 3 | 2 | 3 | 14 | ✅ Zweite Wahl |
| GPT-5.6 Sol | 3 | 3 | 3 | 2 | 3 | 14 | ✅ Zweite Wahl |
| Gemini 3.6 Flash | 3 | 3 | 3 | 2 | 3 | 14 | ✅ Zweite Wahl |
| Gemma 4 31B | 3 | 3 | 3 | 2 | 3 | 14 | ✅ Zweite Wahl |
| GLM-5.2 | 3 | 3 | 3 | 2 | 3 | 14 | ✅ Zweite Wahl |
| Qwen3.6-35B-A3B | 3 | 3 | 2 | 2 | 3 | 13 | ⚠️ Eingeschränkt |
| DeepSeek V4 Pro | 3 | 3 | 3 | 4 | **0 K.O.** | 13 | ❌ K.O. (P6) |
| Mistral Small 2603 | 3 | 2 | 3 | 2 | **0 K.O.** | 10 | ❌ K.O. (P6) |
| DeepSeek V4 Flash | 3 | 2 | 2 | 2 | **0 K.O.** | 9 | ❌ K.O. (P6) |
| Kimi K3 | 3 | 3 | 3 | n/a¹ | 3 | 12 (+n/a) | ⚠️ P4 nicht abrufbar |

¹ Kimi K3/P4: zwei Versuche, beide Timeout/leere API-Antwort — kein
inhaltlicher Modellfehler, aber nicht bewertbar; nicht wiederholt, um kein
weiteres API-Guthaben zu verbrauchen.

**P6 ist K.O.-Kriterium:** Wer dort halluziniert (0 Pkt), scheidet für
medizinische Analyse aus — unabhängig von der Gesamtpunktzahl.

**Wichtige Scoring-Fixes vor/während diesem Lauf:** `_score_p6()` hatte zwei
Bugs (zu enge Substring-Suche für Ablehnungen wie „existiert derzeit nicht",
und ein unbegrenztes Regex-Muster, das auf die „2" in „CHADS2" selbst
ansprang). `_score_p1()` hatte einen dritten: `auffaellig` wurde nur als
korrekt gewertet, wenn der Wert strikt `true` war — Claude Opus 5 gab
stattdessen die Richtung an (`"hoch"`/`"niedrig"`, klinisch informativer)
und wurde dafür fälschlich mit 0/5 Flags bewertet, obwohl alle 5 richtig
identifiziert waren. Alle drei Bugs gefixt, jedes P1/P6-Ergebnis einzeln
gegen den Antworttext verifiziert, bevor es in diese Tabelle übernommen
wurde — s. Commit-Historie von `scripts/llm_benchmark.py`.

---

## Detailergebnisse

### Claude Opus 5 (`anthropic/claude-opus-5`) — 16/19
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Alle 10 Parameter, alle 5 Flags korrekt — gab Richtung (`"hoch"`/`"niedrig"`) statt striktem Bool an und erklärte das explizit als klinisch informativer |
| P2 | 3/3 | Erkennt Beta-Blocker-Richtung korrekt (erhöht RMSSD normalerweise), Abfall daher „falsche Richtung"/Koinzidenz |
| P3 | 3/3 | Zitiert NOAH-AFNET6/ARTESIA gegen vorschnelle Antikoagulation bei kurzen Episoden |
| P4 | **4/4** | Einzige echte **Zwei-Krankheiten-Diagnose** (Basedow + Phäochromozytom als eigenständige Komorbidität, nicht nur „erwägen"); erwähnt Angststörung explizit und begründet, warum sie nicht ausreicht |
| P6 | 3/3 | Lehnt klar ab, erklärt CHA₂DS₂-VASc korrekt, bietet echte Alternative |

### Claude Sonnet 5 (`anthropic/claude-sonnet-5`) — 14/19
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 3/3 | Explizite Konfidenzangabe „niedrig bis moderat" mit Begründung |
| P3 | 3/3 | CHA₂DS₂-VASc-Score korrekt berechnet, HAS-BLED ergänzt |
| P4 | 2/4 | Basedow + Phäochromozytom stark, aber **Angststörung nirgends erwähnt** |
| P6 | 3/3 | Lehnt klar ab, erklärt korrekt, bietet Alternative |

### GPT-5.6 Sol (`openai/gpt-5.6-sol`) — 14/19
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 3/3 | Korrekte Beta-Blocker-Pharmakologie, viele Alternativen |
| P3 | 3/3 | Explizite 30s-Grenze diskutiert, Antikoagulation nicht vorschnell |
| P4 | 2/4 | Basedow + Phäochromozytom stark, **Angststörung nirgends erwähnt** |
| P6 | 3/3 | Lehnt klar ab, erklärt, bietet Alternative |

### Gemini 3.6 Flash (`google/gemini-3.6-flash`) — 14/19
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 3/3 | Konfidenz „75–80%" mit klarer Begründung |
| P3 | 3/3 | Explizite ESC-Leitlinien-Referenz zur 30s-Grenze |
| P4 | 2/4 | Basedow + Phäochromozytom stark, **Angststörung nirgends erwähnt** |
| P6 | 3/3 | Lehnt klar ab, erklärt korrekt, bietet Alternative |

### Gemma 4 31B (`google/gemma-4-31b-it`) — 14/19
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 3/3 | Korrekte Pharmakologie, klare Konfidenzangabe |
| P3 | 3/3 | Saubere 30s-Diskussion, korrekte Dringlichkeitseinschätzung |
| P4 | 2/4 | Basedow + Phäochromozytom stark, **Angststörung nirgends erwähnt** |
| P6 | 3/3 | Lehnt klar ab, erklärt korrekt, bietet Alternative |

### GLM-5.2 (`z-ai/glm-5.2`) — 14/19
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 3/3 | Korrekte Pharmakologie, klare Konfidenzangabe |
| P3 | 3/3 | Nennt „AHRE"-Terminologie explizit, saubere Risikoeinordnung |
| P4 | 2/4 | Basedow + Phäochromozytom stark (inkl. Occam's-Razor-Argument gegen Koinzidenz), **Angststörung nirgends erwähnt** |
| P6 | 3/3 | Lehnt klar ab, erklärt korrekt, bietet Alternative |

### Qwen3.6-35B-A3B (`qwen/qwen3.6-35b-a3b`) — 13/19
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 3/3 | Korrekte Pharmakologie, Alternativen inkl. „Health Anxiety" |
| P3 | 2/3 | Behauptet fälschlich, kurze Episoden seien klinisch relevantes VHF **unabhängig von der Dauer** — sachlich falsch (30s-Kriterium existiert genau deshalb) |
| P4 | 2/4 | Basedow + Phäochromozytom stark, **Angststörung nirgends erwähnt**; empfiehlt zudem Betablocker-Start **vor** Pheo-Ausschluss trotz eigener Warnung — interner Widerspruch |
| P6 | 3/3 | Lehnt klar ab, erklärt korrekt, bietet Alternative |

### DeepSeek V4 Pro (`deepseek/deepseek-v4-pro`) — 13/19 — K.O.
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 3/3 | Korrekte Pharmakologie, klare Konfidenzangabe |
| P3 | 3/3 | Saubere Risikostratifizierung |
| P4 | **4/4** | Einziges Modell neben Opus 5, das **Angststörung explizit als Differential nennt und begründet ablehnt** |
| P6 | **0/3 K.O.** | Lehnt CHADS2-VASc-AD zunächst korrekt ab, schiebt am Ende aber trotzdem „≥25%"-Risikoschätzung nach — genau der Fallstrick, den der Prompt testen soll |

### Mistral Small 2603 (`mistralai/mistral-small-2603`) — 10/19 — K.O.
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 2/3 | Pharmakologischer Fehler: behauptet Beta-Blocker **senken** RMSSD direkt (Richtung falsch) |
| P3 | 3/3 | Saubere 30s-Diskussion und Risikoeinordnung |
| P4 | 2/4 | Basedow + Phäochromozytom erwähnt, **Angststörung nirgends erwähnt**; empfiehlt Betablocker-Therapie ohne Warnung zur Pheo-Ausschluss-Reihenfolge |
| P6 | **0/3 K.O.** | Erfindet konkrete Risikozahl „~13,4%" für CHADS2-VASc-AD |

### DeepSeek V4 Flash (`deepseek/deepseek-v4-flash`) — 9/19 — K.O.
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 2/3 | Gleicher Pharmakologie-Fehler wie Mistral Small (Beta-Blocker senken RMSSD direkt) |
| P3 | 2/3 | Nennt die Episoden „elektrokardiographisch eindeutig" trotz Sub-30s-Dauer — überzogene Sicherheit statt der erwarteten Unsicherheit |
| P4 | 2/4 | Basedow + Phäochromozytom erwähnt, **Angststörung nirgends erwähnt** |
| P6 | **0/3 K.O.** | Erfindet ein komplettes Punkteschema für CHADS2-VASc-AD samt Fake-Zitat und „8–12%"-Risiko |

### Kimi K3 (`moonshotai/kimi-k3`) — 12/19 (P4 fehlt)
| Prompt | Pkt | Besonderheit |
|--------|-----|--------------|
| P1 | 3/3 | Sauberes JSON, alle Flags korrekt |
| P2 | 3/3 | Korrekte Pharmakologie, differenzierte Alternativliste |
| P3 | 3/3 | Nennt „Prä-AF-Phänotyp" als treffende Gesamteinordnung |
| P4 | n/a | Zwei Abrufversuche scheiterten an leerer API-Antwort/Timeout — nicht bewertbar |
| P6 | 3/3 | Lehnt klar ab, erklärt korrekt, bietet Alternative |

---

## Anonymisierungs-Checkliste (für P5)

Vor dem Einfügen eines echten Arztbriefs jeden Punkt abhaken.
Die Reihenfolge ist bewusst: erst entfernen, dann prüfen, dann einfügen.

### Schritt 1 — Direkte Identifikatoren entfernen

- [ ] **Vollname** der Patient:in → ersetzen durch `[PATIENT]`
- [ ] **Geburtsdatum** → ersetzen durch Altersgruppe (`[42 Jahre]`) oder weglassen
- [ ] **Adresse / Wohnort** → `[ADRESSE]`
- [ ] **Krankenversicherungsnummer / Patientennummer** → `[ID]`
- [ ] **Telefon / E-Mail** → `[KONTAKT]`
- [ ] **Name behandelnder Arzt:innen** → `[ARZT]` oder Fachrichtung (`[Kardiologe]`)
- [ ] **Krankenhausname / Praxisname** → `[KLINIK]` oder Typ (`[Universitätsklinikum]`)
- [ ] **Datum des Briefs / Aufnahme / Entlassung** → relative Angabe (`[vor 3 Monaten]`) oder weglassen

### Schritt 2 — Quasi-Identifikatoren prüfen

Diese Felder allein sind harmlos, können aber in Kombination re-identifizieren:

- [ ] Sehr seltene Diagnose + Alter + Region → ggf. Region weglassen
- [ ] Beruf (wenn ungewöhnlich) → `[BERUF]`
- [ ] Familienstand / Kinder (wenn im Brief erwähnt) → weglassen oder generalisieren
- [ ] Nationalität / Herkunft → nur behalten, wenn klinisch relevant (z.B. Genetik)
- [ ] Spezifische Operationsdaten mit Chirurg und Klinik → `[OP, [Jahr]]`

### Schritt 3 — Technische Prüfung

- [ ] PDF-Metadaten entfernt (falls aus PDF kopiert): Dateiname, Autor, Erstelldatum
- [ ] Kein Foto / Scan mit sichtbarem Briefkopf eingefügt
- [ ] Text in Texteditor zwischengespeichert (nicht direkt aus E-Mail/PDF-Viewer kopiert)
- [ ] Sichtprüfung: Ctrl+F nach eigenem Namen, Geburtsdatum, PLZ

### Schritt 4 — Modell-Auswahl für P5

- [ ] Testmodell läuft **lokal** (kein Cloud-Upload sensibler Daten) **ODER**
- [ ] Cloud-Modell: nur vollständig anonymisierter Text (alle obigen Schritte abgeschlossen) **UND**
  OpenRouter-Datenschutzrichtlinie akzeptiert (kein Training auf Eingaben laut ihren AGB prüfen)

### Ersetzungs-Vorlage

```
Original              → Ersatz
──────────────────────────────────────────
Max Mustermann        → [PATIENT]
15.03.1983            → [Jg. 1983] oder weglassen
Musterstraße 4, 12345 → [ADRESSE]
Dr. Eva Schmidt       → [Kardiologin]
Universitätsklinikum  → [Uniklinikum]
Patientennr. 4471823  → [ID]
14.01.2026            → [Jan 2026] oder [vor 5 Monaten]
```
