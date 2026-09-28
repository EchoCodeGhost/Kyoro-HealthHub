<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Speichel-pH-Heimmonitoring — Testprotokoll

> **English version:** [SALIVA_PH_PROTOCOL.md](SALIVA_PH_PROTOCOL.md)

**Import:** `python3 scripts/importers/import_saliva_ph.py --ph <wert> --context <kontext>`
**Template:** `templates/saliva_ph_template.csv`
**Referenzwerte:** konfigurierbar in `~/.config/kyoro/saliva_ph_ranges.json`

---

## Standardprotokoll (Routine)

**Frequenz:** täglich nüchtern morgens (Kontext `fasting_morning`); zusätzlich optional 1–2h nach Mahlzeit, nach Antihistaminikum, abends oder bei Verdacht auf einen symptomatischen Schub.

> ⚠️ **Reihenfolge nicht vertauschen: erst Test, dann alles andere.** Der `fasting_morning`-Test gehört direkt nach dem Aufwachen, **vor** Zähneputzen, Frühstück, Medikamenten.

### Durchführung (immer in dieser Reihenfolge)

1. **Direkt nach dem Aufwachen** — noch nicht gegessen, getrunken, Zähne geputzt oder Medikamente genommen.
2. **Speichel sammeln** (nicht provoziert/stimuliert — einfach natürlich im Mund ansammeln lassen) und den Teststreifen 1–2 Sekunden eintauchen bzw. mit Speichel benetzen.
3. **Sofort ablesen** nach Herstellerangabe (bei den meisten Streifen 10–15 Sekunden) — bei Tageslicht oder guter Kunstlichtbeleuchtung, Referenzfarbtafel der Packung nutzen.
4. **Erst danach:** Zähneputzen, Frühstück, Medikamente.
5. **Immer denselben Kontext dokumentieren** (siehe Tabelle unten) — ein Wert ohne Kontextangabe ist für die Verlaufsanalyse nicht auswertbar, da sich die Referenzbereiche je nach Tageszeit/Mahlzeit unterscheiden.

### Spülen vor dem Test — ja oder nein?

Zwei mögliche Varianten des `fasting_morning`-Tests, mit unterschiedlichem Zielkonflikt:

- **Mit Spülung** (Wasser + 5 Min. Wartezeit vor dem Test): entfernt Speisereste vom Vorabend, was eine reproduzierbarere Ausgangslage schafft. Nachteil: Speichel wird durch das Wasser (pH ≈ 7, neutral) kurzzeitig verdünnt, was den gemessenen Wert künstlich nach oben zieht (weniger sauer als tatsächlich). Ob nach 5 Minuten wirklich 100 % des Restwassers durch neuen Speichel ersetzt ist, bleibt unklar — ein Rest-Bias ist nie ganz ausgeschlossen.
- **Ohne Spülung:** misst den rohen übernächtigten Zustand direkt. Bei Verdacht auf Hyposalivation (z.B. Sjögren-Syndrom, Medikamentennebenwirkung, Dehydratation) ist genau das der klinisch interessante Wert, weil er zeigt, was Schleimhaut/Zähne über Nacht real erleben. Essensreste vom Vorabend sind Stunden nach der letzten Mahlzeit (durch nächtliches Schlucken größtenteils ohnehin abgebaut) ein kleineres Problem als der systematische Verdünnungs-Bias durch das Spülen selbst.

**Wichtig, falls du das Protokoll während der Nutzung umstellst:** Miss- und Spül-Werte sind nicht direkt vergleichbar — beim Wechsel von einer Variante zur anderen im Kommentarfeld der Messung vermerken, ab wann welche Variante galt, damit die Verlaufsanalyse den Bruch berücksichtigen kann.

### Kontext-Schlüssel

| Kontext | Zeitpunkt | Referenzbereich (pH) |
|---|---|---|
| `fasting_morning` | nüchtern morgens, vor Zähneputzen/Frühstück/Medikamenten | 6,8–7,4 (ohne Spülung realistisch eher niedriger, s. o.) |
| `post_meal_1h` | 1h nach Ende der Mahlzeit | 6,5–7,4 |
| `post_meal_2h` | 2h nach Ende der Mahlzeit — sollte erholt sein | 6,8–7,4 |
| `post_antihistamine` | 1–2h nach H1/H2-Blocker-Einnahme | 6,8–7,6 |
| `suspected_flare` | symptomgetriggert bei Verdacht auf akuten Schub | kein fixer Bereich |
| `evening_baseline` | 2h nach letzter Mahlzeit, vor dem Schlafen | 6,8–7,5 |

### Dokumentation

**Direkteingabe (empfohlen für Einzelmessungen):**
```bash
python3 scripts/importers/import_saliva_ph.py --ph 6.5 --context fasting_morning
python3 scripts/importers/import_saliva_ph.py --ph 5.5 --context suspected_flare --symptome "Flushing,Tachykardie"
```

**Per CSV (für mehrere Messungen auf einmal):**
```bash
cp templates/saliva_ph_template.csv meine_speichel_ph.csv
# ... Werte eintragen ...
python3 scripts/importers/import_saliva_ph.py meine_speichel_ph.csv
```

Messmethode immer mit angeben (`--methode`), z. B. `Streifen_4.5-9.0`, `pH-Meter` — unterschiedliche Methoden haben unterschiedliche Genauigkeit (Streifen ±0,5, pH-Meter ±0,01).

---

## Alarmsignale

| Befund | Dringlichkeit | Bedeutung |
|---|---|---|
| pH < 6,0 | 🔴 hoch | stark saurer Speichel — Mastzell-Mediator-Schub oder Reflux möglich |
| pH < 6,2 | 🟡 mittel | Hyposalivation (z.B. Sjögren-Syndrom, Medikamentennebenwirkung, Dehydratation) oder histaminvermittelte Säuerung möglich |
| pH > 7,8 | 🟡 mittel | alkalisch — Protonenpumpenhemmer-Effekt oder Messfehler prüfen |
| `fasting_morning` wiederholt < 6,5 | 🟢 elektiv | mit Arzt/Rheumatologen besprechen, falls eine Hyposalivation-Abklärung ansteht |

---

## Einschränkungen des Streifentests

- Teststreifen haben typisch ±0,5 Genauigkeit — Einzelwerte nicht überinterpretieren, der **Verlauf** über mehrere Messungen ist aussagekräftiger.
- Ein Protokollwechsel (z.B. mit/ohne Spülen, s. o.) verschiebt die Werte systematisch — beim Vergleich über einen solchen Wechsel hinweg berücksichtigen.
- Streifen sind ein Screening-Instrument, keine Diagnose — für eine formale Sjögren-Diagnostik zählen Schirmer-Test + Anti-SSA/Ro + Anti-SSB/La, nicht der Speichel-pH.

---

## Auswertung

```bash
python3 scripts/analysis/manual/analyse_saliva_ph.py
```
